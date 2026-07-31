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
RELEASED_ACCESS_NOTICE_STYLE = """
<style>
.ticket-gate-main-notice {
  margin: 0.95rem 0 1rem;
  padding: 0.9rem 1rem;
  border-left: 4px solid #2563eb;
  border-radius: 10px;
  border-top: 1px solid rgba(37, 99, 235, 0.16);
  border-right: 1px solid rgba(37, 99, 235, 0.16);
  border-bottom: 1px solid rgba(37, 99, 235, 0.16);
  background: #eff6ff;
  color: #0f172a !important;
  font-size: 0.95rem;
  line-height: 1.45;
}
.ticket-gate-main-notice strong {
  color: #1d4ed8 !important;
}
.ticket-gate-main-notice p {
  margin: 0.25rem 0 0;
}
</style>
"""


def _render_released_access_notice() -> None:
    st.markdown(RELEASED_ACCESS_NOTICE_STYLE, unsafe_allow_html=True)
    st.markdown(
        """
        <div class="ticket-gate-main-notice" role="status">
          <strong>Acces libere</strong>
          <p>Cliquez sur <em>Reprendre l'acces</em> pour revenir dans la file.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    components.html(
        """
        <script>
        (function () {
          function resolveHostWindow() {
            try {
              if (window.parent && window.parent !== window) {
                return window.parent;
              }
            } catch (error) {}
            return window;
          }

          const host = resolveHostWindow();
          const current = host.__ticketGateReleaseConfig || {};
          const appId = String(current.applicationId || "");
          if (!appId || host.__ticketGateReleasedNoticeSent) {
            return;
          }

          host.__ticketGateReleasedNoticeSent = true;
          try {
            if (host.opener && typeof host.opener.postMessage === "function") {
              host.opener.postMessage(
                {
                  type: "codeandcortex-ticket:released",
                  appId: appId,
                  applicationId: appId,
                  sessionId: String(current.sessionId || ""),
                  at: Date.now(),
                },
                "*",
              );
            }
          } catch (error) {}
        })();
        </script>
        """,
        height=0,
        width=0,
    )


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
        "release_url": (
            str(os.getenv("APP_TICKET_RELEASE_URL")).strip()
            if os.getenv("APP_TICKET_RELEASE_URL") is not None
            else "https://vps.codeandcortex.fr/api/tickets/release"
        ),
        "hidden_release_seconds": max(0, _env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 300)),
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


def _config_key(app_id: str) -> str:
    return f"app:{app_id}:config"


def _publish_runtime_config(client, cfg: dict[str, Any]) -> None:
    now = int(time.time())
    client.hset(
        _config_key(cfg["app_id"]),
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
    client.expire(_config_key(cfg["app_id"]), max(3600, int(cfg["ttl_seconds"]), max(30, int(cfg["heartbeat_ms"]) // 1000) * 3))


def _list_members(client, key: str) -> list[str]:
    return [str(item) for item in client.zrange(key, 0, -1)]


def _safe_timestamp(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


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
    keys = _keys(cfg["app_id"])
    now = int(time.time())
    for key in (keys["active"], keys["waiting"], _global_active_key()):
        for ticket_id in _list_members(client, key):
            if not client.exists(_ticket_key(ticket_id)):
                client.zrem(key, ticket_id)
                continue
            data = client.hgetall(_ticket_key(ticket_id)) or {}
            status = str(data.get("status", "")).strip() or "attente"
            heartbeat_at = _safe_timestamp(data.get("updated_at")) or _safe_timestamp(data.get("created_at"))
            timeout_seconds = min(cfg["ttl_seconds"], 120) if status == "attente" else cfg["ttl_seconds"]
            session_id = str(data.get("session_id", "")).strip()
            app_id = str(data.get("application_id", cfg["app_id"])).strip() or cfg["app_id"]
            linked_ticket_id = client.get(_session_key(app_id, session_id)) if session_id else None
            if (
                heartbeat_at <= 0
                or heartbeat_at > now + 300
                or now - heartbeat_at > timeout_seconds
                or (status == "actif" and session_id and linked_ticket_id != ticket_id)
                or (status == "actif" and not session_id)
            ):
                _drop_ticket(client, cfg, ticket_id)


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
    if persist_local_release:
        st.session_state[RELEASED_STATE_KEY] = True
    return True


def _render_release_hooks(snapshot: dict[str, Any]) -> None:
    release_url = (
        str(os.getenv("APP_TICKET_RELEASE_URL")).strip()
        if os.getenv("APP_TICKET_RELEASE_URL") is not None
        else "https://vps.codeandcortex.fr/api/tickets/release"
    )
    session_id = st.session_state.get(SESSION_STATE_KEY)
    hidden_release_seconds = max(0, _env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 300))
    if not release_url or not session_id or snapshot.get("statut") not in {"actif", "attente"}:
        return
    components.html(
        f"""
        <script>
        (function () {{
          function resolveHostWindow() {{
            try {{
              if (window.parent && window.parent !== window) {{
                return window.parent;
              }}
            }} catch (error) {{}}
            return window;
          }}

          const releaseUrl = {release_url!r};
          const host = resolveHostWindow();
          const current = {{
            applicationId: {snapshot.get("application_id", "")!r},
            sessionId: {session_id!r},
            hiddenReleaseSeconds: {hidden_release_seconds}
          }};
          host.__ticketGateReleaseConfig = current;
          host.__ticketGateReleasedNoticeSent = false;
          let hiddenTimer = null;

          function notifyHomeDashboard(eventName) {{
            const appId = String(current.applicationId || "");
            if (!appId) {{
              return;
            }}
            try {{
              if (host.opener && typeof host.opener.postMessage === "function") {{
                host.opener.postMessage(
                  {{
                    type: "codeandcortex-ticket:" + eventName,
                    appId: appId,
                    applicationId: appId,
                    sessionId: String(current.sessionId || ""),
                    at: Date.now(),
                  }},
                  "*",
                );
              }}
            }} catch (error) {{}}
          }}

          function fireRelease() {{
            const url = releaseUrl
              + (releaseUrl.includes("?") ? "&" : "?")
              + "application_id=" + encodeURIComponent(current.applicationId)
              + "&session_id=" + encodeURIComponent(current.sessionId);
            notifyHomeDashboard("releasing");
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
          window.addEventListener("pagehide", fireRelease);
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
        _render_released_access_notice()
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
    _publish_runtime_config(client, cfg)

    snapshot = _claim_or_refresh(client, cfg, st.session_state[SESSION_STATE_KEY])
    _render_release_hooks(snapshot)

    col_status, col_action = st.columns([4, 1])
    with col_status:
        if snapshot["statut"] == "actif":
            st.success(f"Application active ({snapshot['active']} / {snapshot['max_active']}).")
        elif snapshot["statut"] == "attente":
            st.info(f"Application occupee. Position dans la file : {snapshot['position'] or '?'}.")
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
