import os
import json
from datetime import datetime
from typing import Any

from nonebot import get_driver
from nonebot.log import logger


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _require_token(request) -> bool:
    """Simple token auth.

    Accept:
    - Authorization: Bearer <token>
    - X-Admin-Token: <token>
    - ?token=<token> (requested; risky)
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

            return HTMLResponse(
                """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>QQBot Admin</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" />
  <style>
    body{background:#0b1220; color:#e5e7eb;}
    .card{background:#0f1a2e; border:1px solid #1f2a44;}
    .table{color:#e5e7eb;}
    .table thead th{color:#cbd5e1; border-bottom:1px solid #23314f;}
    .table td, .table th{border-color:#23314f;}
    .form-control, .form-select{background:#0b1220; color:#e5e7eb; border:1px solid #23314f;}
    .form-control::placeholder{color:#64748b;}
    .btn-outline-light{border-color:#334155;}
    .pill{display:inline-block; padding:2px 8px; border-radius:999px; font-size:12px;}
    .pill-user{background:#1d4ed8;}
    .pill-assistant{background:#16a34a;}
    .pill-system{background:#64748b;}
    .mono{font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New";}
    .small-muted{color:#94a3b8; font-size:12px;}
    a{color:#93c5fd;}
  </style>
</head>
<body>
<div class="container-fluid py-3">
  <div class="d-flex align-items-center justify-content-between mb-3">
    <div>
      <h3 class="mb-0">QQBot Admin Panel</h3>
      <div class="small-muted">Memory audit & ops console</div>
    </div>
    <div class="d-flex gap-2 align-items-center">
      <input id="token" class="form-control form-control-sm" style="width:360px" placeholder="ADMIN_PANEL_TOKEN" />
      <button class="btn btn-sm btn-outline-light" onclick="saveToken()">Save</button>
      <button class="btn btn-sm btn-primary" onclick="loadStatus()">Refresh</button>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-12 col-xl-4">
      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="small-muted">Status</div>
            <div class="fw-semibold">Runtime / Config Snapshot</div>
          </div>
          <div class="small-muted" id="statusTs">-</div>
        </div>
        <hr style="border-color:#23314f" />
        <div class="row g-2" id="statusGrid"></div>
        <hr style="border-color:#23314f" />
        <div class="small-muted">Tip: token in URL is risky; prefer header later (we keep URL for now per request).</div>
      </div>
    </div>

    <div class="col-12 col-xl-8">
      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="small-muted">Memory</div>
            <div class="fw-semibold">Users</div>
          </div>
          <div class="d-flex gap-2">
            <input id="userQuery" class="form-control form-control-sm" style="width:320px" placeholder="search user_id / group_... / user_..." />
            <button class="btn btn-sm btn-outline-light" onclick="loadUsers()">Search</button>
            <button class="btn btn-sm btn-outline-light" onclick="loadUsers('')">All</button>
          </div>
        </div>

        <div class="table-responsive mt-3" style="max-height:320px; overflow:auto;">
          <table class="table table-sm table-hover align-middle" id="usersTable">
            <thead>
              <tr>
                <th style="width:54%" onclick="sortUsers('user_id')" role="button">user_id</th>
                <th style="width:18%" onclick="sortUsers('last_ts')" role="button">last_ts</th>
                <th style="width:10%" onclick="sortUsers('count')" role="button">count</th>
                <th style="width:18%">actions</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colspan="4" class="small-muted">Load users to begin</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card p-3 mt-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="small-muted">Selected User</div>
            <div class="fw-semibold mono" id="selectedUser">(none)</div>
          </div>
          <div class="d-flex gap-2 align-items-center">
            <div class="small-muted">limit</div>
            <input id="limit" class="form-control form-control-sm" value="50" style="width:90px" />
            <div class="small-muted">offset</div>
            <input id="offset" class="form-control form-control-sm" value="0" style="width:90px" />
            <button class="btn btn-sm btn-outline-light" onclick="loadConvos()">Refresh</button>
            <button class="btn btn-sm btn-danger" onclick="clearUser()">Clear User</button>
          </div>
        </div>

        <div class="table-responsive mt-3" style="max-height:420px; overflow:auto;">
          <table class="table table-sm table-hover align-middle" id="convosTable">
            <thead>
              <tr>
                <th style="width:160px">time</th>
                <th style="width:110px">role</th>
                <th>content</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colspan="3" class="small-muted">Select a user to view conversations</td></tr>
            </tbody>
          </table>
        </div>

      </div>

    </div>
  </div>

</div>

<script>
  function getToken(){
    return document.getElementById('token').value.trim() || localStorage.getItem('ADMIN_TOKEN') || '';
  }
  function saveToken(){
    localStorage.setItem('ADMIN_TOKEN', document.getElementById('token').value.trim());
  }
  async function api(path, opts={}){
    const t=getToken();
    const url = path + (path.includes('?')?'&':'?') + 'token=' + encodeURIComponent(t);
    const res = await fetch(url, {headers:{'Content-Type':'application/json'}, ...opts});
    if(!res.ok){
      const txt = await res.text();
      throw new Error(res.status + ' ' + txt);
    }
    return await res.json();
  }

  function esc(s){
    return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
  }

  function statusChip(label, value){
    return `<div class="col-6">
      <div class="small-muted">${esc(label)}</div>
      <div class="mono">${esc(value)}</div>
    </div>`;
  }

  async function loadStatus(){
    try{
      const data = await api('/admin/api/status');
      document.getElementById('statusTs').textContent = data.ts || '-';
      const g=document.getElementById('statusGrid');
      g.innerHTML='';
      if(data.bot){
        g.innerHTML += statusChip('forward_threshold', data.bot.forward_threshold);
        g.innerHTML += statusChip('max_concurrent_requests', data.bot.max_concurrent_requests);
        g.innerHTML += statusChip('enable_smart_router', data.bot.enable_smart_router);
        g.innerHTML += statusChip('router_model', data.bot.router_model);
      }
      if(data.models){
        g.innerHTML += statusChip('chat_short', data.models.chat_short);
        g.innerHTML += statusChip('chat_long', data.models.chat_long);
        g.innerHTML += statusChip('thinking', data.models.thinking);
        g.innerHTML += statusChip('summary', data.models.summary);
      }
      if(data.db){
        g.innerHTML += statusChip('db.total_conversations', data.db.total_conversations);
        g.innerHTML += statusChip('db.total_group_messages', data.db.total_group_messages);
        g.innerHTML += statusChip('db.active_groups', data.db.active_groups);
        g.innerHTML += statusChip('db.total_summaries', data.db.total_summaries);
      }
      if(data.db_error){
        g.innerHTML += `<div class="col-12 small text-danger">db_error: ${esc(data.db_error)}</div>`;
      }
    }catch(e){
      document.getElementById('statusGrid').innerHTML = `<div class="col-12 text-danger">${esc(e)}</div>`;
    }
  }

  let usersState = {items:[], sortKey:'last_ts', sortDir:'desc'};
  let selectedUser = '';

  function sortUsers(key){
    if(usersState.sortKey === key){
      usersState.sortDir = usersState.sortDir === 'asc' ? 'desc' : 'asc';
    }else{
      usersState.sortKey = key;
      usersState.sortDir = 'asc';
    }
    renderUsers();
  }

  function renderUsers(){
    const tbody = document.querySelector('#usersTable tbody');
    const arr = [...usersState.items];
    const k = usersState.sortKey;
    const dir = usersState.sortDir;
    arr.sort((a,b)=>{
      const va=a[k]??''; const vb=b[k]??'';
      if(va<vb) return dir==='asc'?-1:1;
      if(va>vb) return dir==='asc'?1:-1;
      return 0;
    });

    if(!arr.length){
      tbody.innerHTML = '<tr><td colspan="4" class="small-muted">No users</td></tr>';
      return;
    }

    tbody.innerHTML = arr.map(u=>{
      const active = (u.user_id===selectedUser) ? 'table-active' : '';
      return `<tr class="${active}" onclick="selectUser('${esc(u.user_id)}')" style="cursor:pointer">
        <td class="mono">${esc(u.user_id)}</td>
        <td class="mono">${esc(u.last_ts||'')}</td>
        <td class="mono">${esc(u.count||0)}</td>
        <td>
          <button class="btn btn-sm btn-outline-light" onclick="event.stopPropagation(); selectUser('${esc(u.user_id)}');">View</button>
          <button class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation(); quickClear('${esc(u.user_id)}');">Clear</button>
        </td>
      </tr>`;
    }).join('');
  }

  async function loadUsers(query){
    try{
      const q = (typeof query==='string') ? query : document.getElementById('userQuery').value.trim();
      const data = await api('/admin/api/users?query='+encodeURIComponent(q));
      usersState.items = data.users || [];
      renderUsers();
    }catch(e){
      document.querySelector('#usersTable tbody').innerHTML = `<tr><td colspan="4" class="text-danger">${esc(e)}</td></tr>`;
    }
  }

  window.selectUser = async function(uid){
    selectedUser = uid;
    document.getElementById('selectedUser').textContent = uid;
    renderUsers();
    document.getElementById('offset').value = '0';
    await loadConvos();
  }

  async function loadConvos(){
    if(!selectedUser){
      return;
    }
    const limit = parseInt(document.getElementById('limit').value||'50',10);
    const offset = parseInt(document.getElementById('offset').value||'0',10);
    try{
      const data = await api(`/admin/api/conversations?user_id=${encodeURIComponent(selectedUser)}&limit=${limit}&offset=${offset}`);
      const tbody = document.querySelector('#convosTable tbody');
      const items = data.items || [];
      if(!items.length){
        tbody.innerHTML = '<tr><td colspan="3" class="small-muted">No conversations</td></tr>';
        return;
      }
      tbody.innerHTML = items.map(it=>{
        const role = it.role || '';
        const cls = role==='user'?'pill pill-user':(role==='assistant'?'pill pill-assistant':'pill pill-system');
        return `<tr>
          <td class="mono" style="width:160px">${esc(it.timestamp||'')}</td>
          <td style="width:110px"><span class="${cls}">${esc(role)}</span></td>
          <td class="mono">${esc(it.content||'')}</td>
        </tr>`;
      }).join('');
    }catch(e){
      document.querySelector('#convosTable tbody').innerHTML = `<tr><td colspan="3" class="text-danger">${esc(e)}</td></tr>`;
    }
  }

  async function clearUser(){
    if(!selectedUser) return;
    if(!confirm('Clear ALL memory for '+selectedUser+' ?')) return;
    await api('/admin/api/conversations/clear', {method:'POST', body: JSON.stringify({user_id: selectedUser})});
    await loadConvos();
    await loadUsers();
  }

  window.quickClear = async function(uid){
    if(!confirm('Clear ALL memory for '+uid+' ?')) return;
    await api('/admin/api/conversations/clear', {method:'POST', body: JSON.stringify({user_id: uid})});
    if(selectedUser===uid){ await loadConvos(); }
    await loadUsers();
  }

  // init
  const params = new URLSearchParams(location.search);
  const urlToken = params.get('token');
  if(urlToken){
    document.getElementById('token').value = urlToken;
    localStorage.setItem('ADMIN_TOKEN', urlToken);
  } else {
    document.getElementById('token').value = localStorage.getItem('ADMIN_TOKEN') || '';
  }
  loadStatus();
  loadUsers('');
</script>
</body>
</html>"""
            )

        @router.get("/admin/api/status")
        async def admin_status(request: Request):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

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
                data["db"] = db.get_stats()
            except Exception as e:
                data["db_error"] = str(e)
            return JSONResponse(data)

        @router.get("/admin/api/users")
        async def admin_users(request: Request, query: str = "", limit: int = 100):
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
            users = [{"user_id": r[0], "last_ts": r[1], "count": r[2]} for r in rows]
            return JSONResponse({"users": users})

        @router.get("/admin/api/conversations")
        async def admin_conversations(request: Request, user_id: str, limit: int = 50, offset: int = 0):
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
            items = [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]
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

        app.include_router(router)
        logger.info("[admin] panel mounted at /admin (token required)")

    except Exception as e:
        logger.exception(f"[admin] failed to mount panel: {e}")
