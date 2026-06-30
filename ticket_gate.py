from __future__ import annotations

import os
import time
import uuid
from typing import Any

import streamlit as st
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover
    redis = None


SESSION_STATE_KEY = "__ticket_gate_session_id__"
RELEASED_STATE_KEY = "__ticket_gate_released__"


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _config(default_app_id: str, app_label: str) -> dict[str, Any]:
    return {
        "enabled": _env_bool("APP_TICKET_ENFORCED", True),
        "app_id": os.getenv("APP_TICKET_ID", default_app_id).strip() or default_app_id,
        "app_label": app_label,
        "max_active": max(1, _env_int("APP_TICKET_MAX_ACTIVE", 1)),
        "cost": max(0, _env_int("APP_TICKET_COST", 4)),
        "global_capacity": max(1, _env_int("CAPACITE_SERVEUR", 6)),
        "ttl_seconds": max(60, _env_int("APP_TICKET_TTL_SECONDS", 3600)),
        "max_waiting": max(0, _env_int("APP_TICKET_MAX_WAITING", 20)),
        "wait_refresh_ms": max(2000, _env_int("APP_TICKET_WAIT_REFRESH_MS", 10000)),
        "heartbeat_ms": max(30000, _env_int("APP_TICKET_HEARTBEAT_MS", 300000)),
        "release_url": os.getenv("APP_TICKET_RELEASE_URL", "").strip(),
        "hidden_release_seconds": max(0, _env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 0)),
    }


def _redis_client():
    if redis is None:
        return None, "Le paquet Python 'redis' n'est pas installe dans l'application."
    redis_url_env = os.getenv("REDIS_URL", "").strip()
    if not redis_url_env:
        return None, "REDIS_URL absent : configure une URL Redis complete avec mot de passe dans Coolify."
    try:
        client = redis.from_url(redis_url_env, decode_responses=True)
        client.ping()
        return client, None
    except Exception as exc:  # pragma: no cover
        return None, f"Connexion Redis impossible via REDIS_URL : {exc}"


def _keys(app_id: str) -> dict[str, str]:
    return {
        "active": f"app:{app_id}:tickets:actifs",
        "waiting": f"app:{app_id}:tickets:attente",
    }


def _ticket_key(ticket_id: str) -> str:
    return f"ticket:{ticket_id}"


def _session_key(app_id: str, session_id: str) -> str:
    return f"session:{app_id}:{session_id}:ticket"


def _global_active_key() -> str:
    return "tickets:global:actifs"


def _list_members(client, key: str) -> list[str]:
    return [str(item) for item in client.zrange(key, 0, -1)]


def _cleanup_expired(client, cfg: dict[str, Any]) -> None:
    keys = _keys(cfg["app_id"])
    for key in (keys["active"], keys["waiting"], _global_active_key()):
        for ticket_id in _list_members(client, key):
            if not client.exists(_ticket_key(ticket_id)):
                client.zrem(key, ticket_id)


def _active_load(client) -> int:
    total = 0
    for ticket_id in _list_members(client, _global_active_key()):
        data = client.hgetall(_ticket_key(ticket_id))
        if data:
            total += int(data.get("cost", 0))
    return total


def _active_count(client, cfg: dict[str, Any]) -> int:
    return int(client.zcard(_keys(cfg["app_id"])["active"]))


def _waiting_count(client, cfg: dict[str, Any]) -> int:
    return int(client.zcard(_keys(cfg["app_id"])["waiting"]))


def _waiting_position(client, cfg: dict[str, Any], ticket_id: str) -> int | None:
    waiting = _list_members(client, _keys(cfg["app_id"])["waiting"])
    if ticket_id not in waiting:
        return None
    return waiting.index(ticket_id) + 1


def _can_activate(client, cfg: dict[str, Any]) -> bool:
    return _active_count(client, cfg) < cfg["max_active"] and (_active_load(client) + cfg["cost"] <= cfg["global_capacity"])


def _promote_waiting(client, cfg: dict[str, Any]) -> None:
    waiting_key = _keys(cfg["app_id"])["waiting"]
    active_key = _keys(cfg["app_id"])["active"]
    for ticket_id in _list_members(client, waiting_key):
        if not _can_activate(client, cfg):
            break
        if not client.exists(_ticket_key(ticket_id)):
            client.zrem(waiting_key, ticket_id)
            continue
        client.hset(_ticket_key(ticket_id), mapping={"status": "actif", "updated_at": int(time.time())})
        client.zrem(waiting_key, ticket_id)
        client.zadd(active_key, {ticket_id: time.time()})
        client.zadd(_global_active_key(), {ticket_id: time.time()})


def _snapshot(client, cfg: dict[str, Any], ticket_id: str | None, message: str | None = None) -> dict[str, Any]:
    if client is None:
        return {
            "enabled": False,
            "ticket_id": None,
            "statut": "erreur",
            "position": None,
            "active": 0,
            "max_active": cfg["max_active"],
            "queued": 0,
            "application_id": cfg["app_id"],
            "application_label": cfg["app_label"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "message": message or "Redis indisponible.",
        }
    active = _active_count(client, cfg)
    queued = _waiting_count(client, cfg)
    data = client.hgetall(_ticket_key(ticket_id)) if ticket_id else {}
    return {
        "enabled": cfg["enabled"],
        "ticket_id": ticket_id,
        "statut": data.get("status", "inconnu"),
        "position": _waiting_position(client, cfg, ticket_id) if ticket_id else None,
        "active": active,
        "max_active": cfg["max_active"],
        "queued": queued,
        "application_id": cfg["app_id"],
        "application_label": cfg["app_label"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "message": message or "",
    }


def _claim_or_refresh(client, cfg: dict[str, Any], session_id: str) -> dict[str, Any]:
    _cleanup_expired(client, cfg)
    _promote_waiting(client, cfg)

    session_key = _session_key(cfg["app_id"], session_id)
    ticket_id = client.get(session_key)
    if ticket_id and client.exists(_ticket_key(ticket_id)):
        client.expire(session_key, cfg["ttl_seconds"])
        client.expire(_ticket_key(ticket_id), cfg["ttl_seconds"])
        client.hset(_ticket_key(ticket_id), "updated_at", int(time.time()))
        _promote_waiting(client, cfg)
        return _snapshot(client, cfg, ticket_id)

    if ticket_id:
        client.delete(session_key)

    waiting_key = _keys(cfg["app_id"])["waiting"]
    active_key = _keys(cfg["app_id"])["active"]

    if _waiting_count(client, cfg) >= cfg["max_waiting"]:
        return {
            "enabled": cfg["enabled"],
            "ticket_id": None,
            "statut": "refuse",
            "position": None,
            "active": _active_count(client, cfg),
            "max_active": cfg["max_active"],
            "queued": _waiting_count(client, cfg),
            "application_id": cfg["app_id"],
            "application_label": cfg["app_label"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "message": "File d'attente pleine pour cette application.",
        }

    ticket_id = uuid.uuid4().hex
    status = "actif" if _waiting_count(client, cfg) == 0 and _can_activate(client, cfg) else "attente"
    client.hset(
        _ticket_key(ticket_id),
        mapping={
            "ticket_id": ticket_id,
            "session_id": session_id,
            "application_id": cfg["app_id"],
            "status": status,
            "cost": cfg["cost"],
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        },
    )
    client.expire(_ticket_key(ticket_id), cfg["ttl_seconds"])
    client.setex(session_key, cfg["ttl_seconds"], ticket_id)

    if status == "actif":
        client.zadd(active_key, {ticket_id: time.time()})
        client.zadd(_global_active_key(), {ticket_id: time.time()})
    else:
        client.zadd(waiting_key, {ticket_id: time.time()})

    _promote_waiting(client, cfg)
    return _snapshot(client, cfg, ticket_id)


def release_ticket_for_session(default_app_id: str, app_label: str, *, persist_local_release: bool = True) -> bool:
    cfg = _config(default_app_id, app_label)
    client, _message = _redis_client()
    session_id = st.session_state.get(SESSION_STATE_KEY)
    if persist_local_release:
        st.session_state[RELEASED_STATE_KEY] = True
    if not client or not session_id:
        return False
    session_key = _session_key(cfg["app_id"], session_id)
    ticket_id = client.get(session_key)
    if ticket_id:
        client.zrem(_keys(cfg["app_id"])["active"], ticket_id)
        client.zrem(_keys(cfg["app_id"])["waiting"], ticket_id)
        client.zrem(_global_active_key(), ticket_id)
        client.delete(_ticket_key(ticket_id))
        client.delete(session_key)
    _promote_waiting(client, cfg)
    return True


def _render_release_hooks(snapshot: dict[str, Any]) -> None:
    release_url = os.getenv("APP_TICKET_RELEASE_URL", "").strip()
    session_id = st.session_state.get(SESSION_STATE_KEY)
    hidden_release_seconds = max(0, _env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 0))
    if not release_url or not session_id or snapshot.get("statut") not in {"actif", "attente"}:
        return
    components.html(
        f"""
        <script>
        (function () {{
          const releaseUrl = {release_url!r};
          const current = {{
            applicationId: {snapshot.get("application_id", "")!r},
            sessionId: {session_id!r},
            hiddenReleaseSeconds: {hidden_release_seconds}
          }};
          let hiddenTimer = null;
          function fireRelease() {{
            const url = releaseUrl
              + (releaseUrl.includes("?") ? "&" : "?")
              + "application_id=" + encodeURIComponent(current.applicationId)
              + "&session_id=" + encodeURIComponent(current.sessionId);
            try {{
              navigator.sendBeacon(url, new Blob([], {{ type: "text/plain" }}));
            }} catch (_error) {{
              fetch(url, {{ method: "POST", keepalive: true, mode: "no-cors" }}).catch(() => {{}});
            }}
          }}
          document.addEventListener("visibilitychange", () => {{
            if (document.visibilityState === "hidden" && current.hiddenReleaseSeconds > 0) {{
              hiddenTimer = window.setTimeout(fireRelease, current.hiddenReleaseSeconds * 1000);
            }} else if (hiddenTimer) {{
              window.clearTimeout(hiddenTimer);
              hiddenTimer = null;
            }}
          }});
          window.addEventListener("beforeunload", fireRelease);
        }})();
        </script>
        """,
        height=0,
    )


def enforce_streamlit_access(default_app_id: str, app_label: str) -> dict[str, Any]:
    cfg = _config(default_app_id, app_label)
    st.session_state.setdefault(SESSION_STATE_KEY, uuid.uuid4().hex)

    if st.session_state.get(RELEASED_STATE_KEY):
        st.info("Acces libere pour cette page.")
        if st.button("Reprendre l'acces", use_container_width=True):
            st.session_state[RELEASED_STATE_KEY] = False
            st.rerun()
        st.stop()

    if not cfg["enabled"]:
        return {
            "enabled": False,
            "ticket_id": None,
            "statut": "bypass",
            "position": None,
            "active": 0,
            "max_active": cfg["max_active"],
            "queued": 0,
            "application_id": cfg["app_id"],
            "application_label": cfg["app_label"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "message": "Controle d'acces desactive par APP_TICKET_ENFORCED=0.",
        }

    client, message = _redis_client()
    if client is None:
        st.error("Controle d'acces temporairement indisponible.")
        st.error(message or "Redis indisponible.")
        st.stop()

    snapshot = _claim_or_refresh(client, cfg, st.session_state[SESSION_STATE_KEY])
    _render_release_hooks(snapshot)

    col_status, col_action = st.columns([4, 1])
    with col_status:
        if snapshot["statut"] == "actif":
            st.success(f"Application active ({snapshot['active']} / {snapshot['max_active']}).")
        elif snapshot["statut"] == "attente":
            st.warning(f"Application occupee. Position dans la file : {snapshot['position'] or '?'}.")
        elif snapshot["statut"] == "refuse":
            st.error("File d'attente pleine pour cette application.")
        elif snapshot["message"]:
            st.info(snapshot["message"])
    with col_action:
        if snapshot["statut"] in {"actif", "attente"} and st.button("Liberer l'acces", use_container_width=True):
            if release_ticket_for_session(default_app_id, app_label):
                st.rerun()

    if snapshot["statut"] == "actif":
        st_autorefresh(interval=snapshot["heartbeat_ms"], key=f"{default_app_id}-heartbeat")
        return snapshot

    if snapshot["statut"] == "attente":
        st_autorefresh(interval=snapshot["wait_refresh_ms"], key=f"{default_app_id}-wait")
        st.stop()

    if snapshot["statut"] == "refuse":
        st.stop()

    if snapshot["message"]:
        st.error(snapshot["message"])
    st.stop()

