import os
import json
from datetime import datetime
from typing import Any

from nonebot import get_driver, get_bot
from nonebot.log import logger

_NAME_CACHE: dict[str, tuple[float, dict]] = {}
_NAME_CACHE_TTL_SEC = int(os.getenv("ADMIN_NAME_CACHE_TTL_SEC", "600"))


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


def _parse_user_key(user_key: str):
    # returns (kind, group_id, user_id)
    uk = (user_key or "").strip()
    if uk.startswith("user_"):
        try:
            return ("private", None, int(uk.split("_", 1)[1]))
        except Exception:
            return (None, None, None)
    if uk.startswith("group_") and "_user_" in uk:
        try:
            # group_<gid>_user_<uid>
            rest = uk[len("group_") :]
            gid_s, uid_s = rest.split("_user_", 1)
            return ("group", int(gid_s), int(uid_s))
        except Exception:
            return (None, None, None)
    return (None, None, None)


def _cache_get(key: str) -> dict | None:
    now = datetime.utcnow().timestamp()
    cached = _NAME_CACHE.get(key)
    if cached and now - cached[0] < _NAME_CACHE_TTL_SEC:
        return cached[1]
    return None


def _cache_set(key: str, data: dict):
    _NAME_CACHE[key] = (datetime.utcnow().timestamp(), data)


def _build_display(kind: str | None, gid: int | None, uid: int | None, nickname: str, card: str, group_name: str) -> str:
    if not uid:
        return ""
    if kind == "private":
        name = nickname or ""
        return f"{name} ({uid})" if name else str(uid)
    if kind == "group" and gid:
        name = card or nickname or ""
        gn = group_name or ""
        if name:
            return f"{name} ({uid}) @ {gn}({gid})" if gn else f"{name} ({uid}) @ {gid}"
        return f"{uid} @ {gn}({gid})" if gn else f"{uid} @ {gid}"
    return str(uid)


def _init_meta(user_key: str) -> dict:
    kind, gid, uid = _parse_user_key(user_key)
    return {
        "user_key": user_key,
        "kind": kind,
        "group_id": gid,
        "user_id": uid,
        "nickname": "",
        "card": "",
        "group_name": "",
        "display": user_key,
    }


def _resolve_display_name_sync_fallback(user_key: str) -> dict:
    # fallback: no bot connected
    meta = _init_meta(user_key)
    meta["display"] = _build_display(meta["kind"], meta["group_id"], meta["user_id"], "", "", "") or user_key
    _cache_set(user_key, meta)
    return meta


def _get_bot_or_none():
    try:
        return get_bot()
    except Exception:
        return None


def _extract_identity(meta: dict):
    return (meta.get("kind"), meta.get("group_id"), meta.get("user_id"))

    return (meta.get("user_id"), meta.get("group_id"))


def _ensure_str(x) -> str:
    return x if isinstance(x, str) else ""


def _as_int(x):
    try:
        return int(x)
    except Exception:
        return None


def _safe_lower(s: str) -> str:
    return (s or "").lower()


def _split_search_query(q: str) -> list[str]:
    return [t for t in (q or "").strip().split() if t]


def _matches_any(hay: str, tokens: list[str]) -> bool:
    hl = _safe_lower(hay)
    return all(t.lower() in hl for t in tokens)


def _user_key_from_row(r) -> str:
    return r[0]


def _row_last_ts(r) -> str:
    return r[1]


def _row_count(r) -> int:
    return int(r[2] or 0)


def _resolve_display_name_cached_or_init(user_key: str) -> dict:
    cached = _cache_get(user_key)
    if cached:
        return cached
    return _init_meta(user_key)


def _should_resolve(meta: dict) -> bool:
    kind, gid, uid = meta.get("kind"), meta.get("group_id"), meta.get("user_id")
    return bool(kind and uid)


def _attach_display(meta: dict):
    meta["display"] = _build_display(
        meta.get("kind"),
        meta.get("group_id"),
        meta.get("user_id"),
        _ensure_str(meta.get("nickname")),
        _ensure_str(meta.get("card")),
        _ensure_str(meta.get("group_name")),
    ) or meta.get("user_key")


def _cache_and_return(user_key: str, meta: dict) -> dict:
    _cache_set(user_key, meta)
    return meta


def _resolve_via_onebot(kind: str, gid: int | None, uid: int, bot) -> dict:
    # async wrapper is below
    return {}


async def resolve_display_name(user_key: str) -> dict:
    cached = _cache_get(user_key)
    if cached:
        return cached

    meta = _init_meta(user_key)
    kind, gid, uid = _extract_identity(meta)

    bot = _get_bot_or_none()
    if not bot or not meta.get("kind") or not meta.get("user_id"):
        return _resolve_display_name_sync_fallback(user_key)

    try:
        if meta["kind"] == "private" and uid:
            info = await bot.call_api("get_stranger_info", user_id=uid)
            meta["nickname"] = (info or {}).get("nickname") or ""
        elif meta["kind"] == "group" and uid and gid:
            mi = await bot.call_api("get_group_member_info", group_id=gid, user_id=uid)
            meta["card"] = (mi or {}).get("card") or ""
            meta["nickname"] = (mi or {}).get("nickname") or ""
            try:
                gi = await bot.call_api("get_group_info", group_id=gid)
                meta["group_name"] = (gi or {}).get("group_name") or ""
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"[admin] resolve name failed for {user_key}: {e}")

    _attach_display(meta)
    return _cache_and_return(user_key, meta)


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
<html lang="zh">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>QQBot 管理后台</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" />
  <style>
    body{background:#f6f7fb; color:#0f172a;}
    .card{border:1px solid #e5e7eb; box-shadow:0 1px 2px rgba(15,23,42,.05);} 
    .mono{font-family: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono","Courier New";}
    .small-muted{color:#64748b; font-size:12px;}
    .table thead th{position:sticky; top:0; background:#fff; z-index:1;}
    .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;color:#fff;}
    .pill-user{background:#2563eb;}
    .pill-assistant{background:#16a34a;}
    .pill-system{background:#64748b;}
    .clickable{cursor:pointer;}
  </style>
</head>
<body>
<div class="container-fluid py-3">
  <div class="d-flex flex-wrap gap-2 align-items-center justify-content-between mb-3">
    <div>
      <h3 class="mb-0">QQBot 管理后台</h3>
      <div class="small-muted">对话记忆审核 / 运维面板</div>
    </div>
    <div class="d-flex gap-2 align-items-center">
      <input id="token" class="form-control form-control-sm" style="width:360px" placeholder="ADMIN_PANEL_TOKEN" />
      <button class="btn btn-sm btn-outline-secondary" onclick="saveToken()">保存</button>
      <button class="btn btn-sm btn-primary" onclick="reloadAll()">刷新</button>
    </div>
  </div>

  <div class="row g-3">
    <div class="col-12 col-xl-4">
      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="small-muted">状态</div>
            <div class="fw-semibold">运行与配置快照</div>
          </div>
          <div class="small-muted" id="statusTs">-</div>
        </div>
        <hr />
        <div class="row g-2" id="statusGrid"></div>
        <hr />
        <div class="small-muted">提示：token 放在 URL 有风险（按你要求先这样），后续建议接 Cloudflare Access。</div>
      </div>
    </div>

    <div class="col-12 col-xl-8">
      <div class="card p-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="small-muted">记忆管理</div>
            <div class="fw-semibold">用户列表</div>
          </div>
          <div class="d-flex gap-2">
            <input id="userQuery" class="form-control form-control-sm" style="width:320px" placeholder="搜索 user_key/QQ号/群号/昵称（支持空格多关键词）" />
            <button class="btn btn-sm btn-outline-secondary" onclick="loadUsers()">搜索</button>
            <button class="btn btn-sm btn-outline-secondary" onclick="loadUsers('')">全部</button>
          </div>
        </div>

        <div class="table-responsive mt-3" style="max-height:340px; overflow:auto;">
          <table class="table table-sm table-hover align-middle" id="usersTable">
            <thead>
              <tr>
                <th style="width:34%" role="button" onclick="sortUsers('display')">昵称/名片</th>
                <th style="width:16%" role="button" onclick="sortUsers('user_id')">QQ号</th>
                <th style="width:14%" role="button" onclick="sortUsers('group_id')">群号</th>
                <th style="width:18%" role="button" onclick="sortUsers('last_ts')">最后时间</th>
                <th style="width:8%" role="button" onclick="sortUsers('count')">条数</th>
                <th style="width:10%">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colspan="6" class="small-muted">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="card p-3 mt-3">
        <div class="d-flex justify-content-between align-items-center">
          <div>
            <div class="small-muted">当前用户</div>
            <div class="fw-semibold mono" id="selectedUser">(未选择)</div>
          </div>
          <div class="d-flex gap-2 align-items-center">
            <span class="small-muted">limit</span>
            <input id="limit" class="form-control form-control-sm" value="50" style="width:90px" />
            <span class="small-muted">offset</span>
            <input id="offset" class="form-control form-control-sm" value="0" style="width:90px" />
            <button class="btn btn-sm btn-outline-secondary" onclick="loadConvos()">刷新</button>
            <button class="btn btn-sm btn-danger" onclick="clearUser()">清空该用户</button>
          </div>
        </div>

        <div class="table-responsive mt-3" style="max-height:460px; overflow:auto;">
          <table class="table table-sm table-hover align-middle" id="convosTable">
            <thead>
              <tr>
                <th style="width:160px">时间</th>
                <th style="width:110px">角色</th>
                <th>内容</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colspan="3" class="small-muted">请选择一个用户</td></tr>
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
    s = String(s ?? "");
    return s.replace(/[&<>\"\x27]/g, function(c){
      switch(c){
        case "&": return "&amp;";
        case "<": return "&lt;";
        case ">": return "&gt;";
        case "\"": return "&quot;";
        case "\x27": return "&#39;";
        default: return c;
      }
    });
  }

  function statusChip(label, value){
    return '<div class="col-6"><div class="small-muted">'+esc(label)+'</div><div class="mono">'+esc(value)+'</div></div>';
  }

  async function loadStatus(){
    try{
      const data = await api('/admin/api/status');
      document.getElementById('statusTs').textContent = data.ts || '-';
      const g=document.getElementById('statusGrid');
      g.innerHTML='';
      if(data.bot){
        g.innerHTML += statusChip('转发阈值', data.bot.forward_threshold);
        g.innerHTML += statusChip('最大并发', data.bot.max_concurrent_requests);
        g.innerHTML += statusChip('智能路由', data.bot.enable_smart_router);
        g.innerHTML += statusChip('路由模型', data.bot.router_model);
      }
      if(data.models){
        g.innerHTML += statusChip('短聊', data.models.chat_short);
        g.innerHTML += statusChip('长聊', data.models.chat_long);
        g.innerHTML += statusChip('推理', data.models.thinking);
        g.innerHTML += statusChip('总结', data.models.summary);
      }
      if(data.db){
        g.innerHTML += statusChip('用户数', data.db.active_users);
        g.innerHTML += statusChip('对话条数', data.db.total_conversations);
        g.innerHTML += statusChip('群数', data.db.active_groups);
        g.innerHTML += statusChip('群消息数', data.db.total_group_messages);
      }
      if(data.db_error){
        g.innerHTML += '<div class="col-12 text-danger">db_error: '+esc(data.db_error)+'</div>';
      }
    }catch(e){
      document.getElementById('statusGrid').innerHTML = '<div class="col-12 text-danger">'+esc(e)+'</div>';
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
      tbody.innerHTML = '<tr><td colspan="6" class="small-muted">没有数据</td></tr>';
      return;
    }

    tbody.innerHTML = arr.map(u=>{
      const active = (u.user_key===selectedUser) ? 'table-primary' : '';
      return '<tr class="'+active+' clickable" onclick="selectUser(\''+esc(u.user_key)+'\')">'
        + '<td>'+esc(u.display||u.user_key)+'</td>'
        + '<td class="mono">'+esc(u.user_id||'')+'</td>'
        + '<td class="mono">'+esc(u.group_id||'')+'</td>'
        + '<td class="mono">'+esc(u.last_ts||'')+'</td>'
        + '<td class="mono">'+esc(u.count||0)+'</td>'
        + '<td><button class="btn btn-sm btn-outline-danger" onclick="event.stopPropagation(); quickClear(\''+esc(u.user_key)+'\');">清空</button></td>'
        + '</tr>';
    }).join('');
  }

  async function loadUsers(query){
    try{
      const q = (typeof query==='string') ? query : document.getElementById('userQuery').value.trim();
      const data = await api('/admin/api/users?query='+encodeURIComponent(q));
      usersState.items = data.users || [];
      renderUsers();
    }catch(e){
      document.querySelector('#usersTable tbody').innerHTML = '<tr><td colspan="6" class="text-danger">'+esc(e)+'</td></tr>';
    }
  }

  window.selectUser = async function(userKey){
    selectedUser = userKey;
    document.getElementById('selectedUser').textContent = userKey;
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
      const data = await api('/admin/api/conversations?user_id='+encodeURIComponent(selectedUser)+'&limit='+limit+'&offset='+offset);
      const tbody = document.querySelector('#convosTable tbody');
      const items = data.items || [];
      if(!items.length){
        tbody.innerHTML = '<tr><td colspan="3" class="small-muted">暂无对话</td></tr>';
        return;
      }
      tbody.innerHTML = items.map(it=>{
        const role = it.role || '';
        const cls = role==='user'?'pill pill-user':(role==='assistant'?'pill pill-assistant':'pill pill-system');
        return '<tr>'
          + '<td class="mono" style="width:160px">'+esc(it.timestamp||'')+'</td>'
          + '<td style="width:110px"><span class="'+cls+'">'+esc(role)+'</span></td>'
          + '<td class="mono">'+esc(it.content||'')+'</td>'
          + '</tr>';
      }).join('');
    }catch(e){
      document.querySelector('#convosTable tbody').innerHTML = '<tr><td colspan="3" class="text-danger">'+esc(e)+'</td></tr>';
    }
  }

  async function clearUser(){
    if(!selectedUser) return;
    if(!confirm('确认清空该用户所有记忆？\n'+selectedUser)) return;
    await api('/admin/api/conversations/clear', {method:'POST', body: JSON.stringify({user_id: selectedUser})});
    await loadConvos();
    await loadUsers();
  }

  window.quickClear = async function(userKey){
    if(!confirm('确认清空该用户所有记忆？\n'+userKey)) return;
    await api('/admin/api/conversations/clear', {method:'POST', body: JSON.stringify({user_id: userKey})});
    if(selectedUser===userKey){ await loadConvos(); }
    await loadUsers();
  }

  async function reloadAll(){
    await loadStatus();
    await loadUsers('');
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
  reloadAll();
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
        async def admin_users(request: Request, query: str = "", limit: int = 200):
            if not _require_token(request):
                raise HTTPException(status_code=401, detail="unauthorized")

            q = (query or "").strip()
            tokens = _split_search_query(q)

            conn = db._get_connection()  # type: ignore
            cursor = conn.cursor()

            # We first filter by user_key in SQL (fast), then filter by display in Python.
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

            users = []
            for r in rows:
                user_key = _user_key_from_row(r)
                meta = await resolve_display_name(user_key)
                item = {
                    "user_key": user_key,
                    "display": meta.get("display") or user_key,
                    "user_id": meta.get("user_id"),
                    "group_id": meta.get("group_id"),
                    "last_ts": _row_last_ts(r),
                    "count": _row_count(r),
                }
                # If tokens exist, allow filtering by display and ids
                if tokens:
                    hay = f"{item['user_key']} {item.get('display','')} {item.get('user_id','')} {item.get('group_id','')}"
                    if not _matches_any(hay, tokens):
                        continue
                users.append(item)

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
