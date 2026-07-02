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
except ModuleNotFoundError:  # pragma: no cover - depend de l'image Docker finale
    redis = None


"""
Contrôle d'accès Redis pour les applications Streamlit.

#### VARIABLES D'ENVIRONNEMENT À MODIFIER SI BESOIN

Variables d'environnement à modifier si besoin :

- REDIS_URL
  URL de connexion Redis obligatoire.
  Exemple : redis://:motdepasse@redis-tickets:6379/0

- APP_TICKET_ID
  Identifiant technique de l'application dans Redis.
  Exemple : iramuteq-lite, mp3_to_text, symbolic_connectors

- APP_TICKET_MAX_ACTIVE
  Nombre maximal d'utilisateurs actifs pour l'application.
  Pour tes applications exclusives, laisse 1.
  Si un jour tu veux ouvrir à 2 utilisateurs simultanés :
  APP_TICKET_MAX_ACTIVE=2

- APP_TICKET_COST
  Coût de charge de l'application dans la capacité globale du serveur.
  Les grosses applications peuvent rester a 4.

- CAPACITE_SERVEUR
  Capacité globale du VPS. Le helper la lit pour ne pas activer trop
  d'applications lourdes en même temps.

- APP_TICKET_TTL_SECONDS
  Durée de vie d'un ticket si le navigateur ne donne plus signe de vie.
  Exemple : 1800 pour 30 minutes.

- APP_TICKET_MAX_WAITING
  Taille maximale de la file d'attente par application.

- APP_TICKET_WAIT_REFRESH_MS
  Fréquence de rafraîchissement automatique pour un utilisateur en attente.
  Exemple : 10000 pour 10 secondes.

- APP_TICKET_HEARTBEAT_MS
  Fréquence de heartbeat pour un utilisateur actif.
  Exemple : 300000 pour 5 minutes.

- APP_TICKET_ENFORCED
  Mettre 0 pour désactiver temporairement le contrôle d'accès.

- APP_TICKET_RELEASE_URL
  URL absolue du service dashboard qui expose `/api/tickets/release`.
  Exemple : https://ton-dashboard.codeandcortex.fr/api/tickets/release

- APP_TICKET_HIDDEN_RELEASE_SECONDS
  Délai optionnel avant libération automatique si l'onglet devient caché.
  Mettre 0 pour désactiver ce garde-fou.

Conseil pratique pour Coolify :
- laisse APP_TICKET_MAX_ACTIVE=1 pour une grosse application monopolistique
- augmente APP_TICKET_TTL_SECONDS si un traitement peut durer longtemps
- ajuste APP_TICKET_COST selon la charge CPU/RAM réelle sur ton VPS
"""


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
.ticket-status-card.is-active .ticket-status-meta,
.ticket-status-card.is-active .ticket-status-meta * {
  color: #15803d !important;
}
.ticket-status-card.is-active .ticket-status-meta strong {
  color: #15803d !important;
}
.ticket-status-card.is-waiting .ticket-status-meta strong {
  color: #b45309 !important;
}
.ticket-status-card.is-error .ticket-status-meta strong {
  color: #b91c1c !important;
}
.ticket-status-card.is-released .ticket-status-meta strong {
  color: #475569 !important;
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
        "ttl_seconds": max(60, _env_int("APP_TICKET_TTL_SECONDS", 1800)),
        "max_waiting": max(0, _env_int("APP_TICKET_MAX_WAITING", 20)),
        "wait_refresh_ms": max(2000, _env_int("APP_TICKET_WAIT_REFRESH_MS", 10000)),
        "heartbeat_ms": max(30000, _env_int("APP_TICKET_HEARTBEAT_MS", 300000)),
        "release_url": os.getenv("APP_TICKET_RELEASE_URL", "").strip(),
        "hidden_release_seconds": max(0, _env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 0)),
    }


def _redis_client():
    if redis is None:
        return None, "Le paquet Python 'redis' n'est pas installé dans l'application."
    redis_url_env = os.getenv("REDIS_URL", "").strip()
    if not redis_url_env:
        return None, "REDIS_URL absent : configure une URL Redis complète avec mot de passe dans Coolify."
    try:
        client = redis.from_url(redis_url_env, decode_responses=True)
        client.ping()
        return client, None
    except Exception as exc:  # pragma: no cover - depend du runtime Redis
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


def _snapshot(client, cfg: dict[str, Any], ticket_id: str | None, bypass_message: str | None = None) -> dict[str, Any]:
    if client is None:
        return {
            "enabled": False,
            "ticket_id": None,
            "statut": "actif",
            "position": None,
            "active": 0,
            "queued": 0,
            "max_active": cfg["max_active"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "message": bypass_message or "Contrôle d'accès désactivé.",
        }

    active = _active_count(client, cfg)
    queued = _waiting_count(client, cfg)
    if not ticket_id:
        return {
            "enabled": True,
            "ticket_id": None,
            "statut": "inconnu",
            "position": None,
            "active": active,
            "queued": queued,
            "max_active": cfg["max_active"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "message": "Aucun ticket associé à cette session.",
        }

    data = client.hgetall(_ticket_key(ticket_id)) or {}
    return {
        "enabled": True,
        "ticket_id": ticket_id,
        "statut": data.get("status", "inconnu"),
        "position": _waiting_position(client, cfg, ticket_id),
        "active": active,
        "queued": queued,
        "max_active": cfg["max_active"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "message": data.get("message", ""),
    }


def _bypass_snapshot(cfg: dict[str, Any], message: str) -> dict[str, Any]:
    return _snapshot(None, cfg, None, bypass_message=message)


def _error_snapshot(cfg: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "ticket_id": None,
        "statut": "erreur",
        "position": None,
        "active": 0,
        "queued": 0,
        "max_active": cfg["max_active"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "message": message,
    }


def _released_snapshot(client, cfg: dict[str, Any], message: str) -> dict[str, Any]:
    active = _active_count(client, cfg) if client is not None else 0
    queued = _waiting_count(client, cfg) if client is not None else 0
    return {
        "enabled": True,
        "ticket_id": None,
        "statut": "released",
        "position": None,
        "active": active,
        "queued": queued,
        "max_active": cfg["max_active"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "message": message,
    }


def _claim_or_refresh(client, cfg: dict[str, Any], session_id: str) -> dict[str, Any]:
    if client is None:
        return _error_snapshot(cfg, "Redis indisponible : impossible de réserver un ticket.")

    _cleanup_expired(client, cfg)
    _promote_waiting(client, cfg)

    session_key = _session_key(cfg["app_id"], session_id)
    existing_ticket = client.get(session_key)

    if existing_ticket and client.exists(_ticket_key(existing_ticket)):
        client.expire(session_key, cfg["ttl_seconds"])
        client.expire(_ticket_key(existing_ticket), cfg["ttl_seconds"])
        _promote_waiting(client, cfg)
        return _snapshot(client, cfg, existing_ticket)

    if existing_ticket:
        client.delete(session_key)

    ticket_id = uuid.uuid4().hex
    waiting_key = _keys(cfg["app_id"])["waiting"]
    active_key = _keys(cfg["app_id"])["active"]

    if _waiting_count(client, cfg) >= cfg["max_waiting"]:
        return {
            "enabled": True,
            "ticket_id": None,
            "statut": "refuse",
            "position": None,
            "active": _active_count(client, cfg),
            "queued": _waiting_count(client, cfg),
            "max_active": cfg["max_active"],
            "wait_refresh_ms": cfg["wait_refresh_ms"],
            "heartbeat_ms": cfg["heartbeat_ms"],
            "message": "File d'attente pleine pour cette application.",
        }

    status = "actif" if _waiting_count(client, cfg) == 0 and _can_activate(client, cfg) else "attente"
    client.hset(
        _ticket_key(ticket_id),
        mapping={
            "ticket_id": ticket_id,
            "session_id": session_id,
            "application_id": cfg["app_id"],
            "application_label": cfg["app_label"],
            "cost": cfg["cost"],
            "status": status,
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


def _reset_local_ticket_state(mark_released: bool) -> None:
    st.session_state.pop(SESSION_STATE_KEY, None)
    if mark_released:
        st.session_state[RELEASED_STATE_KEY] = True
    else:
        st.session_state.pop(RELEASED_STATE_KEY, None)


def _resume_local_ticket_state() -> None:
    st.session_state.pop(RELEASED_STATE_KEY, None)
    st.session_state[SESSION_STATE_KEY] = uuid.uuid4().hex


def _install_release_hooks(cfg: dict[str, Any], session_id: str | None) -> None:
    release_url = cfg.get("release_url", "").strip()
    if not release_url or not session_id:
        return

    payload = {
        "releaseUrl": release_url,
        "applicationId": cfg["app_id"],
        "sessionId": session_id,
        "hiddenReleaseMs": int(cfg.get("hidden_release_seconds", 0)) * 1000,
    }
    components.html(
        f"""
        <script>
        (function () {{
          const config = {json.dumps(payload)};
          window.__ticketGateReleaseConfig = config;

          if (window.__ticketGateReleaseHookInstalled) {{
            return;
          }}

          window.__ticketGateReleaseHookInstalled = true;
          window.__ticketGateReleaseSent = false;

          function buildReleaseUrl() {{
            const current = window.__ticketGateReleaseConfig || config;
            const separator = current.releaseUrl.includes("?") ? "&" : "?";
            return current.releaseUrl + separator
              + "application_id=" + encodeURIComponent(current.applicationId)
              + "&session_id=" + encodeURIComponent(current.sessionId);
          }}

          function sendRelease() {{
            const current = window.__ticketGateReleaseConfig || config;
            if (!current.releaseUrl || !current.applicationId || !current.sessionId || window.__ticketGateReleaseSent) {{
              return;
            }}

            window.__ticketGateReleaseSent = true;
            const url = buildReleaseUrl();

            try {{
              const sent = navigator.sendBeacon && navigator.sendBeacon(
                url,
                new Blob([""], {{ type: "text/plain;charset=UTF-8" }})
              );
              if (sent) {{
                return;
              }}
            }} catch (error) {{}}

            try {{
              fetch(url, {{
                method: "POST",
                mode: "no-cors",
                keepalive: true,
                body: "",
              }}).catch(() => {{}});
            }} catch (error) {{}}
          }}

          let hiddenTimer = null;

          function clearHiddenTimer() {{
            if (hiddenTimer !== null) {{
              window.clearTimeout(hiddenTimer);
              hiddenTimer = null;
            }}
          }}

          function scheduleHiddenRelease() {{
            clearHiddenTimer();
            const current = window.__ticketGateReleaseConfig || config;
            if (!current.hiddenReleaseMs || current.hiddenReleaseMs <= 0) {{
              return;
            }}
            hiddenTimer = window.setTimeout(() => {{
              sendRelease();
            }}, current.hiddenReleaseMs);
          }}

          document.addEventListener("visibilitychange", () => {{
            if (document.visibilityState === "hidden") {{
              scheduleHiddenRelease();
            }} else {{
              clearHiddenTimer();
              window.__ticketGateReleaseSent = false;
            }}
          }});

          window.addEventListener("pagehide", () => {{
            sendRelease();
          }});

          window.addEventListener("beforeunload", () => {{
            sendRelease();
          }});
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def release_ticket_for_session(default_app_id: str, app_label: str, *, persist_local_release: bool = True) -> bool:
    cfg = _config(default_app_id, app_label)
    client, _message = _redis_client()
    if client is None:
        return False

    session_id = st.session_state.get(SESSION_STATE_KEY)
    if not session_id:
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
    _reset_local_ticket_state(mark_released=persist_local_release)
    return True


def keep_ticket_alive(default_app_id: str, app_label: str) -> dict[str, Any]:
    cfg = _config(default_app_id, app_label)
    if not cfg["enabled"]:
        return _bypass_snapshot(cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0.")

    client, message = _redis_client()
    if st.session_state.get(RELEASED_STATE_KEY):
        return _released_snapshot(
            client,
            cfg,
            "Accès libéré pour cette page. Clique sur 'Reprendre l'accès' pour revenir dans la file.",
        )
    session_id = st.session_state.setdefault(SESSION_STATE_KEY, uuid.uuid4().hex)
    return _claim_or_refresh(client, cfg, session_id) if client else _error_snapshot(cfg, message or "Redis indisponible.")


def enforce_streamlit_access(default_app_id: str, app_label: str) -> dict[str, Any]:
    cfg = _config(default_app_id, app_label)
    snapshot = keep_ticket_alive(default_app_id, app_label)
    session_id = st.session_state.get(SESSION_STATE_KEY)

    if not snapshot["enabled"]:
        return snapshot

    if snapshot["statut"] in {"actif", "attente"}:
        _install_release_hooks(cfg, session_id)

    with st.sidebar:
        st.markdown("### Accès utilisateur")
        st.markdown(TICKET_STATUS_STYLE, unsafe_allow_html=True)

        if snapshot["statut"] == "actif":
            st.markdown(
                f"""
                <div class="ticket-status-card is-active">
                  <span class="ticket-status-dot is-active"></span>
                  <div class="ticket-status-meta"><strong>Application active</strong><br>{snapshot['active']} utilisateur(s) actif(s) sur {snapshot['max_active']} autorisé(s).</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.success(f"Accès actif ({snapshot['active']} / {snapshot['max_active']}).")
            if st.button("Libérer l'accès", use_container_width=True):
                if release_ticket_for_session(default_app_id, app_label):
                    st.rerun()
                st.warning("Impossible de libérer le ticket courant pour le moment.")
        elif snapshot["statut"] == "attente":
            position = snapshot["position"] or "?"
            st.markdown(
                f"""
                <div class="ticket-status-card is-waiting">
                  <span class="ticket-status-dot is-waiting"></span>
                  <div class="ticket-status-meta"><strong>Application occupée</strong><br>Position actuelle dans la file : {position}.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.warning(f"Application occupée. Position dans la file : {position}.")
        elif snapshot["statut"] == "refuse":
            st.markdown(
                """
                <div class="ticket-status-card is-error">
                  <span class="ticket-status-dot is-error"></span>
                  <div class="ticket-status-meta"><strong>File d'attente pleine</strong><br>Impossible d'ajouter un nouvel utilisateur pour le moment.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.error("File d'attente pleine pour cette application.")
        elif snapshot["statut"] == "released":
            st.markdown(
                """
                <div class="ticket-status-card is-released">
                  <span class="ticket-status-dot is-released"></span>
                  <div class="ticket-status-meta"><strong>Accès libéré</strong><br>Cette page n'occupe plus l'application.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.info("Accès libéré pour cette page.")
            if st.button("Reprendre l'accès", use_container_width=True):
                _resume_local_ticket_state()
                st.rerun()
        else:
            st.markdown(
                """
                <div class="ticket-status-card is-error">
                  <span class="ticket-status-dot is-error"></span>
                  <div class="ticket-status-meta"><strong>Accès indisponible</strong><br>Le ticket courant n'a pas pu être validé.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.error("Contrôle d'accès temporairement indisponible.")
            if snapshot["message"]:
                st.error(snapshot["message"])

    if snapshot["statut"] == "actif":
        st_autorefresh(interval=snapshot["heartbeat_ms"], key=f"{default_app_id}-heartbeat")
        return snapshot

    if snapshot["statut"] == "attente":
        st_autorefresh(interval=snapshot["wait_refresh_ms"], key=f"{default_app_id}-wait")
        st.warning(
            f"{app_label} est actuellement utilisée par un autre utilisateur. "
            f"Votre position dans la file d'attente : {snapshot['position'] or '?'}."
        )
        st.stop()

    if snapshot["statut"] == "released":
        st.info("Accès libéré. Clique sur 'Reprendre l'accès' pour revenir dans la file.")
        st.stop()

    if snapshot["statut"] == "refuse":
        st.error("File d'attente pleine pour cette application.")
    else:
        st.error("Contrôle d'accès temporairement indisponible.")
        if snapshot["message"]:
            st.error(snapshot["message"])
    st.stop()
