import os
import json
from datetime import datetime
from typing import Optional, Any

from nonebot import get_driver
from nonebot.log import logger


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _require_token(request) -> bool:
    """Simple token auth.

    Accept:
    - Authorization: Bearer <token>
    - X-Admin-Token: <token>
    - ?token=<token> (NOT recommended but requested)
    """
    token = os.getenv("ADMIN_PANEL_TOKEN", "").strip()
    if not token:
        return False

    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        if auth.split(" ", 1)[1].strip() == token:
            return True

    if (request.headers.get("x-admin-token") or "").strip() == token:
        return True

    q = request.query_params.get("token")
    if q and q.strip() == token:
        return True

    return False


def _audit(conn, request, action: str, target: str = "", detail: Any = None):
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts DATETIME DEFAULT CURRENT_TIMESTAMP,
                ip TEXT,
                action TEXT,
                target TEXT,
                detail TEXT
            )
            """
        )
        cursor.execute(
            "INSERT INTO admin_audit (ip, action, target, detail) VALUES (?, ?, ?, ?)",
            (
                getattr(request.client, "host", "") if getattr(request, "client", None) else "",
                action,
                target,
                json.dumps(detail, ensure_ascii=False) if detail is not None else "",
            ),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"[admin] audit failed: {e}")


driver = get_driver()
app = getattr(driver, "server_app", None)

if app is None:
    logger.warning("[admin] FastAPI app not found; admin panel disabled")
else:
    try:
        from fastapi import APIRouter, Request, HTTPException
        from fastapi.responses import HTMLResponse, JSONResponse

        from src.utils.database import db

        router = APIRouter()

        @router.get("/admin", response_class=HTMLResponse)
        async def admin_index(request: Request):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

            # Minimal UI (no bundler). Token can be passed as ?token=... (requested),
            # but you should prefer Authorization header.
            return HTMLResponse(
                """<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>QQBot Admin</title>
  <style>
    body{font-family:system-ui, -apple-system, Segoe UI, Roboto, Arial; margin:16px;}
    input,button,select{padding:8px; font-size:14px;}
    .row{display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:10px 0;}
    .card{border:1px solid #ddd; border-radius:8px; padding:12px; margin:12px 0;}
    pre{white-space:pre-wrap; word-break:break-word; background:#f7f7f7; padding:10px; border-radius:6px;}
    table{border-collapse:collapse; width:100%;}
    td,th{border-bottom:1px solid #eee; padding:6px; text-align:left; font-size:13px;}
  </style>
</head>
<body>
  <h2>QQBot Admin Panel</h2>
  <div class=\"card\">
    <div class=\"row\">
      <label>Token:</label>
      <input id=\"token\" placeholder=\"ADMIN_PANEL_TOKEN\" style=\"width:320px\" />
      <button onclick=\"saveToken()\">Save</button>
      <button onclick=\"loadStatus()\">Load Status</button>
    </div>
    <pre id=\"status\">(status)</pre>
  </div>

  <div class=\"card\">
    <h3>User Memory</h3>
    <div class=\"row\">
      <input id=\"q\" placeholder=\"search user_id or qq number\" style=\"width:320px\" />
      <button onclick=\"searchUsers()\">Search</button>
      <select id=\"users\" style=\"min-width:320px\" onchange=\"loadConvos()\"></select>
      <button onclick=\"clearUser()\">Clear User</button>
    </div>
    <div class=\"row\">
      <button onclick=\"loadConvos()\">Refresh</button>
      <label>Limit</label><input id=\"limit\" value=\"30\" style=\"width:80px\" />
      <label>Offset</label><input id=\"offset\" value=\"0\" style=\"width:80px\" />
    </div>
    <pre id=\"convos\">(conversations)</pre>
  </div>

  <script>
    function token(){
      return document.getElementById('token').value.trim() || localStorage.getItem('ADMIN_TOKEN') || '';
    }
    function saveToken(){
      localStorage.setItem('ADMIN_TOKEN', document.getElementById('token').value.trim());
      alert('saved');
    }
    async function api(path, opts={}){
      const t = token();
      const url = path + (path.includes('?') ? '&' : '?') + 'token=' + encodeURIComponent(t);
      const res = await fetch(url, {headers: {'Content-Type':'application/json'}, ...opts});
      if(!res.ok){
        const txt = await res.text();
        throw new Error(res.status + ' ' + txt);
      }
      return await res.json();
    }
    async function loadStatus(){
      try{
        const data = await api('/admin/api/status');
        document.getElementById('status').textContent = JSON.stringify(data, null, 2);
      }catch(e){
        document.getElementById('status').textContent = String(e);
      }
    }
    async function searchUsers(){
      const q=document.getElementById('q').value.trim();
      const data = await api('/admin/api/users?query='+encodeURIComponent(q));
      const sel=document.getElementById('users');
      sel.innerHTML='';
      for(const u of data.users){
        const opt=document.createElement('option');
        opt.value=u.user_id; opt.textContent=u.user_id + '  (last:' + u.last_ts + ')';
        sel.appendChild(opt);
      }
      if(data.users.length){ await loadConvos(); }
    }
    async function loadConvos(){
      const uid=document.getElementById('users').value;
      if(!uid) return;
      const limit=document.getElementById('limit').value||30;
      const offset=document.getElementById('offset').value||0;
      const data = await api(`/admin/api/conversations?user_id=${encodeURIComponent(uid)}&limit=${limit}&offset=${offset}`);
      document.getElementById('convos').textContent = JSON.stringify(data, null, 2);
    }
    async function clearUser(){
      const uid=document.getElementById('users').value;
      if(!uid) return;
      if(!confirm('Clear all memory for '+uid+' ?')) return;
      await api('/admin/api/conversations/clear', {method:'POST', body: JSON.stringify({user_id: uid})});
      await loadConvos();
      alert('cleared');
    }

    // init
    document.getElementById('token').value = localStorage.getItem('ADMIN_TOKEN') || '';
  </script>
</body>
</html>"""
            )

        @router.get("/admin/api/status")
        async def admin_status(request: Request):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

            # basic env/status snapshot (avoid leaking secrets)
            data = {
                "ts": _now_iso(),
                "bot": {
                    "forward_threshold": int(os.getenv("FORWARD_THRESHOLD", "100")),
                    "max_concurrent_requests": int(os.getenv("MAX_CONCURRENT_REQUESTS", "4")),
                    "enable_smart_router": os.getenv("ENABLE_SMART_ROUTER", "false"),
                    "router_model": os.getenv("ROUTER_MODEL", ""),
                },
                "models": {
                    "chat_short": os.getenv("MODEL_CHAT_SHORT", ""),
                    "chat_long": os.getenv("MODEL_CHAT_LONG", ""),
                    "thinking": os.getenv("MODEL_THINKING", ""),
                    "summary": os.getenv("MODEL_SUMMARY", ""),
                    "image": os.getenv("MODEL_IMAGE", ""),
                },
            }
            try:
                data["db"] = db.get_database_stats()
            except Exception as e:
                data["db_error"] = str(e)
            return JSONResponse(data)

        @router.get("/admin/api/users")
        async def admin_users(request: Request, query: str = "", limit: int = 50):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

            q = (query or "").strip()
            conn = db._get_connection()  # type: ignore
            cursor = conn.cursor()

            if q:
                cursor.execute(
                    """
                    SELECT user_id, MAX(timestamp) as last_ts, COUNT(*) as cnt
                    FROM conversations
                    WHERE user_id LIKE ?
                    GROUP BY user_id
                    ORDER BY last_ts DESC
                    LIMIT ?
                    """,
                    (f"%{q}%", int(limit)),
                )
            else:
                cursor.execute(
                    """
                    SELECT user_id, MAX(timestamp) as last_ts, COUNT(*) as cnt
                    FROM conversations
                    GROUP BY user_id
                    ORDER BY last_ts DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                )

            rows = cursor.fetchall() or []
            users = [
                {
                    "user_id": r[0],
                    "last_ts": r[1],
                    "count": r[2],
                }
                for r in rows
            ]
            return JSONResponse({"users": users})

        @router.get("/admin/api/conversations")
        async def admin_conversations(request: Request, user_id: str, limit: int = 30, offset: int = 0):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

            uid = (user_id or "").strip()
            if not uid:
                raise HTTPException(status_code=400, detail="user_id required")

            conn = db._get_connection()  # type: ignore
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content, timestamp
                FROM conversations
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (uid, int(limit), int(offset)),
            )
            rows = cursor.fetchall() or []
            items = [
                {
                    "role": r[0],
                    "content": r[1],
                    "timestamp": r[2],
                }
                for r in rows
            ]
            return JSONResponse({"user_id": uid, "items": list(reversed(items)), "limit": limit, "offset": offset})

        @router.post("/admin/api/conversations/clear")
        async def admin_clear_conversations(request: Request):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

            body = await request.json()
            uid = (body.get("user_id") or "").strip()
            if not uid:
                raise HTTPException(status_code=400, detail="user_id required")

            conn = db._get_connection()  # type: ignore
            _audit(conn, request, action="clear_conversations", target=uid)

            db.clear_user_conversation(uid)
            return JSONResponse({"ok": True})

        # mount
        app.include_router(router)
        logger.info("[admin] panel mounted at /admin (token required)")

    except Exception as e:
        logger.exception(f"[admin] failed to mount panel: {e}")
