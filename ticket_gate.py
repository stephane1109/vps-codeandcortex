from __future__ import annotations

import json
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

TICKET_STATUS_STYLE = """
<style>
.ticket-status-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.75rem 0.9rem;
  margin-bottom: 0.8rem;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(248, 250, 252, 0.96);
  color: #0f172a !important;
}
.ticket-status-dot {
  width: 0.8rem;
  height: 0.8rem;
  border-radius: 999px;
  flex: 0 0 auto;
}
.ticket-status-dot.is-active {
  background: #16a34a;
  animation: ticket-pulse-green 1.25s infinite;
}
.ticket-status-dot.is-waiting {
  background: #f59e0b;
  animation: ticket-pulse-orange 1.25s infinite;
}
.ticket-status-dot.is-error {
  background: #dc2626;
}
.ticket-status-dot.is-released {
  background: #64748b;
}
.ticket-status-meta {
  font-size: 0.84rem;
  line-height: 1.35;
  color: #0f172a !important;
}
.ticket-status-meta strong {
  color: #0f172a !important;
}
.ticket-gate-main-notice {
  margin: 0.95rem 0 1rem;
  padding: 0.9rem 1rem;
  border-left: 4px solid #2563eb;
  border-radius: 10px;
  background: #eff6ff;
  color: #0f172a !important;
}
@keyframes ticket-pulse-green {
  0% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.45); }
  70% { box-shadow: 0 0 0 12px rgba(22, 163, 74, 0); }
  100% { box-shadow: 0 0 0 0 rgba(22, 163, 74, 0); }
}
@keyframes ticket-pulse-orange {
  0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.45); }
  70% { box-shadow: 0 0 0 12px rgba(245, 158, 11, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0); }
}
</style>
"""


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(float(os.getenv(name, str(default)))))
    except Exception:
        return max(minimum, default)


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
        "max_active": _env_int("APP_TICKET_MAX_ACTIVE", 2, 1),
        "cost": _env_int("APP_TICKET_COST", 1, 0),
        "global_capacity": _env_int("CAPACITE_SERVEUR", 6, 1),
        "ttl_seconds": _env_int("APP_TICKET_TTL_SECONDS", 3600, 60),
        "max_waiting": _env_int("APP_TICKET_MAX_WAITING", 20, 0),
        "wait_refresh_ms": _env_int("APP_TICKET_WAIT_REFRESH_MS", 10000, 2000),
        "heartbeat_ms": _env_int("APP_TICKET_HEARTBEAT_MS", 300000, 30000),
        "release_url": os.getenv("APP_TICKET_RELEASE_URL", "https://vps.codeandcortex.fr/api/tickets/release").strip(),
        "hidden_release_seconds": _env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 300, 0),
    }


def _redis_client():
    if redis is None:
        return None, "Le paquet Python 'redis' n'est pas installé dans l'application."
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None, "REDIS_URL absent dans Coolify."
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client, ""
    except Exception as exc:  # pragma: no cover
        return None, f"Connexion Redis impossible : {exc}"


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


def _publish_runtime_config(client, cfg: dict[str, Any]) -> None:
    now = int(time.time())
    client.hset(
        f"app:{cfg['app_id']}:config",
        mapping={
            "application_id": cfg["app_id"],
            "application_label": cfg["app_label"],
            "label": cfg["app_label"],
            "max_active": cfg["max_active"],
            "cost": cfg["cost"],
            "cout": cfg["cost"],
            "global_capacity": cfg["global_capacity"],
            "capacite_serveur": cfg["global_capacity"],
            "ttl_seconds": cfg["ttl_seconds"],
            "max_waiting": cfg["max_waiting"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "enabled": int(bool(cfg["enabled"])),
            "published_at": now,
            "updated_at": now,
        },
    )
    client.expire(f"app:{cfg['app_id']}:config", max(86400, cfg["ttl_seconds"], (cfg["heartbeat_ms"] // 1000) * 6))


def _list_members(client, key: str) -> list[str]:
    return [str(item) for item in client.zrange(key, 0, -1)]


def _drop_ticket(client, cfg: dict[str, Any], ticket_id: str) -> None:
    data = client.hgetall(_ticket_key(ticket_id)) or {}
    session_id = str(data.get("session_id", "")).strip()
    client.zrem(_keys(cfg["app_id"])["active"], ticket_id)
    client.zrem(_keys(cfg["app_id"])["waiting"], ticket_id)
    client.zrem(_global_active_key(), ticket_id)
    client.delete(_ticket_key(ticket_id))
    if session_id:
        client.delete(_session_key(cfg["app_id"], session_id))


def _cleanup_expired(client, cfg: dict[str, Any]) -> None:
    now = int(time.time())
    seen: set[str] = set()
    for key in (_keys(cfg["app_id"])["active"], _keys(cfg["app_id"])["waiting"], _global_active_key()):
        for ticket_id in _list_members(client, key):
            if ticket_id in seen:
                continue
            seen.add(ticket_id)
            data = client.hgetall(_ticket_key(ticket_id)) or {}
            if not data:
                client.zrem(key, ticket_id)
                continue
            updated_at = int(float(data.get("updated_at") or data.get("created_at") or now))
            if now - updated_at > cfg["ttl_seconds"]:
                _drop_ticket(client, cfg, ticket_id)


def _active_count(client, cfg: dict[str, Any]) -> int:
    return int(client.zcard(_keys(cfg["app_id"])["active"]))


def _waiting_count(client, cfg: dict[str, Any]) -> int:
    return int(client.zcard(_keys(cfg["app_id"])["waiting"]))


def _active_load(client) -> int:
    total = 0
    for ticket_id in _list_members(client, _global_active_key()):
        data = client.hgetall(_ticket_key(ticket_id)) or {}
        total += int(float(data.get("cost") or 0))
    return total


def _can_activate(client, cfg: dict[str, Any]) -> bool:
    return _active_count(client, cfg) < cfg["max_active"] and _active_load(client) + cfg["cost"] <= cfg["global_capacity"]


def _promote_waiting(client, cfg: dict[str, Any]) -> None:
    waiting_key = _keys(cfg["app_id"])["waiting"]
    active_key = _keys(cfg["app_id"])["active"]
    for ticket_id in _list_members(client, waiting_key):
        if not _can_activate(client, cfg):
            break
        if not client.exists(_ticket_key(ticket_id)):
            client.zrem(waiting_key, ticket_id)
            continue
        now = int(time.time())
        client.hset(_ticket_key(ticket_id), mapping={"status": "actif", "updated_at": now})
        client.expire(_ticket_key(ticket_id), cfg["ttl_seconds"])
        client.zrem(waiting_key, ticket_id)
        client.zadd(active_key, {ticket_id: time.time()})
        client.zadd(_global_active_key(), {ticket_id: time.time()})


def _position(client, cfg: dict[str, Any], ticket_id: str | None) -> int | None:
    if not ticket_id:
        return None
    waiting = _list_members(client, _keys(cfg["app_id"])["waiting"])
    return waiting.index(ticket_id) + 1 if ticket_id in waiting else None


def _snapshot(client, cfg: dict[str, Any], ticket_id: str | None, status: str = "inconnu", message: str = "") -> dict[str, Any]:
    if ticket_id and client.exists(_ticket_key(ticket_id)):
        data = client.hgetall(_ticket_key(ticket_id)) or {}
        status = str(data.get("status") or status)
    return {
        "enabled": True,
        "ticket_id": ticket_id,
        "statut": status,
        "position": _position(client, cfg, ticket_id),
        "active": _active_count(client, cfg),
        "queued": _waiting_count(client, cfg),
        "max_active": cfg["max_active"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "message": message,
    }


def _claim_or_refresh(client, cfg: dict[str, Any], session_id: str) -> dict[str, Any]:
    _cleanup_expired(client, cfg)
    _promote_waiting(client, cfg)
    session_key = _session_key(cfg["app_id"], session_id)
    ticket_id = str(client.get(session_key) or "").strip()
    if ticket_id and client.exists(_ticket_key(ticket_id)):
        now = int(time.time())
        client.hset(_ticket_key(ticket_id), mapping={"updated_at": now})
        client.expire(_ticket_key(ticket_id), cfg["ttl_seconds"])
        client.expire(session_key, cfg["ttl_seconds"])
        return _snapshot(client, cfg, ticket_id)

    if ticket_id:
        client.delete(session_key)
    if _waiting_count(client, cfg) >= cfg["max_waiting"]:
        return _snapshot(client, cfg, None, "refuse", "File d'attente pleine.")

    ticket_id = uuid.uuid4().hex
    status = "actif" if _waiting_count(client, cfg) == 0 and _can_activate(client, cfg) else "attente"
    now = int(time.time())
    client.hset(
        _ticket_key(ticket_id),
        mapping={
            "ticket_id": ticket_id,
            "session_id": session_id,
            "application_id": cfg["app_id"],
            "application_label": cfg["app_label"],
            "cost": cfg["cost"],
            "status": status,
            "created_at": now,
            "updated_at": now,
        },
    )
    client.expire(_ticket_key(ticket_id), cfg["ttl_seconds"])
    client.setex(session_key, cfg["ttl_seconds"], ticket_id)
    if status == "actif":
        client.zadd(_keys(cfg["app_id"])["active"], {ticket_id: time.time()})
        client.zadd(_global_active_key(), {ticket_id: time.time()})
    else:
        client.zadd(_keys(cfg["app_id"])["waiting"], {ticket_id: time.time()})
    _promote_waiting(client, cfg)
    return _snapshot(client, cfg, ticket_id)


def _reset_local_ticket_state(mark_released: bool) -> None:
    st.session_state.pop(SESSION_STATE_KEY, None)
    if mark_released:
        st.session_state[RELEASED_STATE_KEY] = True
    else:
        st.session_state.pop(RELEASED_STATE_KEY, None)


def _resume_local_ticket_state() -> None:
    st.session_state.pop(RELEASED_STATE_KEY, None)
    st.session_state[SESSION_STATE_KEY] = uuid.uuid4().hex


def _notify_home_script(cfg: dict[str, Any], session_id: str | None) -> None:
    if not session_id:
        return
    payload = {
        "releaseUrl": cfg["release_url"],
        "applicationId": cfg["app_id"],
        "sessionId": session_id,
        "hiddenReleaseMs": cfg["hidden_release_seconds"] * 1000,
    }
    components.html(
        f"""
        <script>
        (function () {{
          const config = {json.dumps(payload)};
          const host = window.parent && window.parent !== window ? window.parent : window;
          host.__ticketGateReleaseConfig = config;
          window.__ticketGateReleaseConfig = config;
          if (window.__ticketGateReleaseHookInstalled) return;
          window.__ticketGateReleaseHookInstalled = true;
          window.__ticketGateReleaseSent = false;

          function notify(eventName) {{
            try {{
              if (host.opener && typeof host.opener.postMessage === "function") {{
                host.opener.postMessage({{
                  type: "codeandcortex-ticket:" + eventName,
                  appId: config.applicationId,
                  applicationId: config.applicationId,
                  sessionId: config.sessionId,
                  at: Date.now()
                }}, "*");
              }}
            }} catch (error) {{}}
          }}

          function releaseUrl() {{
            const separator = config.releaseUrl.includes("?") ? "&" : "?";
            return config.releaseUrl + separator
              + "application_id=" + encodeURIComponent(config.applicationId)
              + "&session_id=" + encodeURIComponent(config.sessionId);
          }}

          function sendRelease() {{
            if (!config.releaseUrl || !config.applicationId || !config.sessionId || window.__ticketGateReleaseSent) return;
            window.__ticketGateReleaseSent = true;
            notify("releasing");
            const url = releaseUrl();
            try {{
              if (navigator.sendBeacon && navigator.sendBeacon(url, new Blob([""], {{ type: "text/plain;charset=UTF-8" }}))) return;
            }} catch (error) {{}}
            try {{ fetch(url, {{ method: "POST", mode: "no-cors", keepalive: true, body: "" }}).catch(() => {{}}); }} catch (error) {{}}
          }}

          let hiddenTimer = null;
          document.addEventListener("visibilitychange", () => {{
            if (document.visibilityState === "hidden" && config.hiddenReleaseMs > 0) {{
              hiddenTimer = window.setTimeout(sendRelease, config.hiddenReleaseMs);
            }} else if (hiddenTimer !== null) {{
              window.clearTimeout(hiddenTimer);
              hiddenTimer = null;
              window.__ticketGateReleaseSent = false;
            }}
          }});
          window.addEventListener("pagehide", sendRelease);
          window.addEventListener("beforeunload", sendRelease);
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def release_ticket_for_session(default_app_id: str, app_label: str, *, persist_local_release: bool = True) -> bool:
    cfg = _config(default_app_id, app_label)
    client, _message = _redis_client()
    session_id = st.session_state.get(SESSION_STATE_KEY)
    if client is None or not session_id:
        return False
    ticket_id = str(client.get(_session_key(cfg["app_id"], session_id)) or "").strip()
    if ticket_id:
        _drop_ticket(client, cfg, ticket_id)
    _promote_waiting(client, cfg)
    _reset_local_ticket_state(mark_released=persist_local_release)
    return True


def keep_ticket_alive(default_app_id: str, app_label: str) -> dict[str, Any]:
    cfg = _config(default_app_id, app_label)
    if not cfg["enabled"]:
        return {"enabled": False, "statut": "actif", "max_active": cfg["max_active"]}
    client, message = _redis_client()
    if client is None:
        return {
            "enabled": True,
            "statut": "erreur",
            "active": 0,
            "queued": 0,
            "max_active": cfg["max_active"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "message": message,
        }
    _publish_runtime_config(client, cfg)
    if st.session_state.get(RELEASED_STATE_KEY):
        return _snapshot(client, cfg, None, "released", "Accès libéré pour cette page.")
    session_id = st.session_state.setdefault(SESSION_STATE_KEY, uuid.uuid4().hex)
    return _claim_or_refresh(client, cfg, session_id)


def _render_released_notice(cfg: dict[str, Any]) -> None:
    st.markdown(TICKET_STATUS_STYLE, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ticket-gate-main-notice" role="status">
          <strong>Accès libéré</strong><br>
          Cette page n'occupe plus l'application. Cliquez sur <em>Reprendre l'accès</em> dans la barre latérale pour revenir dans la file.
        </div>
        """,
        unsafe_allow_html=True,
    )
    components.html(
        f"""
        <script>
        (function () {{
          const appId = {json.dumps(cfg["app_id"])};
          try {{
            const host = window.parent && window.parent !== window ? window.parent : window;
            if (host.opener && typeof host.opener.postMessage === "function") {{
              host.opener.postMessage({{ type: "codeandcortex-ticket:released", appId, applicationId: appId, at: Date.now() }}, "*");
            }}
          }} catch (error) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def enforce_streamlit_accèss(default_app_id: str, app_label: str) -> dict[str, Any]:
    cfg = _config(default_app_id, app_label)
    snapshot = keep_ticket_alive(default_app_id, app_label)
    session_id = st.session_state.get(SESSION_STATE_KEY)

    if not snapshot.get("enabled", True):
        return snapshot
    if snapshot["statut"] in {"actif", "attente"}:
        _notify_home_script(cfg, session_id)

    with st.sidebar:
        st.markdown("### Accès utilisateur")
        st.markdown(TICKET_STATUS_STYLE, unsafe_allow_html=True)
        if snapshot["statut"] == "actif":
            st.markdown(
                f"""
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-active"></span>
                  <div class="ticket-status-meta"><strong>Application active</strong><br>{snapshot['active']} utilisateur(s) actif(s) sur {snapshot['max_active']} autorisé(s).</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Libérer l'accès", use_container_width=True):
                if release_ticket_for_session(default_app_id, app_label):
                    st.rerun()
                st.warning("Impossible de libérer le ticket courant pour le moment.")
        elif snapshot["statut"] == "attente":
            position = snapshot["position"] or "?"
            st.markdown(
                f"""
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-waiting"></span>
                  <div class="ticket-status-meta"><strong>Application occupée</strong><br>Position actuelle dans la file : {position}.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        elif snapshot["statut"] == "released":
            st.markdown(
                """
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-released"></span>
                  <div class="ticket-status-meta"><strong>Accès libéré</strong><br>Cette page n'occupe plus l'application.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Reprendre l'accès", use_container_width=True):
                _resume_local_ticket_state()
                st.rerun()
        else:
            st.markdown(
                """
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-error"></span>
                  <div class="ticket-status-meta"><strong>Accès indisponible</strong><br>Le ticket courant n'a pas pu être validé.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if snapshot.get("message"):
                st.error(snapshot["message"])

    if snapshot["statut"] == "actif":
        st_autorefresh(interval=snapshot["heartbeat_ms"], key=f"{default_app_id}-heartbeat")
        return snapshot
    if snapshot["statut"] == "attente":
        st_autorefresh(interval=snapshot["wait_refresh_ms"], key=f"{default_app_id}-wait")
        st.warning(f"{app_label} est actuellement utilisée. Position dans la file : {snapshot['position'] or '?'}.")
        st.stop()
    if snapshot["statut"] == "released":
        _render_released_notice(cfg)
        st.stop()

    st.error("Contrôle d'accès temporairement indisponible.")
    if snapshot.get("message"):
        st.error(snapshot["message"])
    st.stop()
