from __future__ import annotations

import os
import time
import uuid
from typing import Any

import streamlit as st
from streamlit_autorefresh import st_autorefresh

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover - depend de l'image Docker finale
    redis = None


"""
Controle d'acces Redis pour les applications Streamlit.

#### VARIABLES D'ENVIRONNEMENT A MODIFIER SI BESOIN

Variables d'environnement a modifier si besoin :

- REDIS_URL
  URL de connexion Redis obligatoire.
  Exemple : redis://:motdepasse@redis-tickets:6379/0

- APP_TICKET_ID
  Identifiant technique de l'application dans Redis.
  Exemple : iramuteq-lite, mp3_to_text, symbolic_connectors

- APP_TICKET_MAX_ACTIVE
  Nombre maximal d'utilisateurs actifs pour l'application.
  Pour tes applications exclusives, laisse 1.
  Si un jour tu veux ouvrir a 2 utilisateurs simultanes :
  APP_TICKET_MAX_ACTIVE=2

- APP_TICKET_COST
  Cout de charge de l'application dans la capacite globale du serveur.
  Les grosses applications peuvent rester a 4.

- CAPACITE_SERVEUR
  Capacite globale du VPS. Le helper la lit pour ne pas activer trop
  d'applications lourdes en meme temps.

- APP_TICKET_TTL_SECONDS
  Duree de vie d'un ticket si le navigateur ne donne plus signe de vie.
  Exemple : 1800 pour 30 minutes.

- APP_TICKET_MAX_WAITING
  Taille maximale de la file d'attente par application.

- APP_TICKET_WAIT_REFRESH_MS
  Frequence de rafraichissement automatique pour un utilisateur en attente.
  Exemple : 10000 pour 10 secondes.

- APP_TICKET_HEARTBEAT_MS
  Frequence de heartbeat pour un utilisateur actif.
  Exemple : 300000 pour 5 minutes.

- APP_TICKET_ENFORCED
  Mettre 0 pour desactiver temporairement le controle d'acces.

Conseil pratique pour Coolify :
- laisse APP_TICKET_MAX_ACTIVE=1 pour une grosse application monopolistique
- augmente APP_TICKET_TTL_SECONDS si un traitement peut durer longtemps
- ajuste APP_TICKET_COST selon la charge CPU/RAM reelle sur ton VPS
"""


SESSION_STATE_KEY = "__ticket_gate_session_id__"
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
.ticket-status-meta {
  font-size: 0.84rem;
  line-height: 1.35;
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
            "message": bypass_message or "Controle d'acces desactive.",
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
            "message": "Aucun ticket associe a cette session.",
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


def _claim_or_refresh(client, cfg: dict[str, Any], session_id: str) -> dict[str, Any]:
    if client is None:
        return _error_snapshot(cfg, "Redis indisponible : impossible de reserver un ticket.")

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


def release_ticket_for_session(default_app_id: str, app_label: str) -> None:
    cfg = _config(default_app_id, app_label)
    client, _message = _redis_client()
    if client is None:
        return

    session_id = st.session_state.get(SESSION_STATE_KEY)
    if not session_id:
        return

    session_key = _session_key(cfg["app_id"], session_id)
    ticket_id = client.get(session_key)
    if ticket_id:
        client.zrem(_keys(cfg["app_id"])["active"], ticket_id)
        client.zrem(_keys(cfg["app_id"])["waiting"], ticket_id)
        client.zrem(_global_active_key(), ticket_id)
        client.delete(_ticket_key(ticket_id))
        client.delete(session_key)
    _promote_waiting(client, cfg)


def keep_ticket_alive(default_app_id: str, app_label: str) -> dict[str, Any]:
    cfg = _config(default_app_id, app_label)
    if not cfg["enabled"]:
        return _bypass_snapshot(cfg, "Controle d'acces desactive par APP_TICKET_ENFORCED=0.")

    client, message = _redis_client()
    session_id = st.session_state.setdefault(SESSION_STATE_KEY, uuid.uuid4().hex)
    return _claim_or_refresh(client, cfg, session_id) if client else _error_snapshot(cfg, message or "Redis indisponible.")


def enforce_streamlit_access(default_app_id: str, app_label: str) -> dict[str, Any]:
    snapshot = keep_ticket_alive(default_app_id, app_label)

    if not snapshot["enabled"]:
        return snapshot

    with st.sidebar:
        st.markdown("### Acces utilisateur")
        st.markdown(TICKET_STATUS_STYLE, unsafe_allow_html=True)

        if snapshot["statut"] == "actif":
            st.markdown(
                f"""
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-active"></span>
                  <div class="ticket-status-meta"><strong>Application active</strong><br>{snapshot['active']} utilisateur(s) actif(s) sur {snapshot['max_active']} autorise(s).</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.success(f"Acces actif ({snapshot['active']} / {snapshot['max_active']}).")
            if st.button("Liberer l'acces", use_container_width=True):
                release_ticket_for_session(default_app_id, app_label)
                st.rerun()
        elif snapshot["statut"] == "attente":
            position = snapshot["position"] or "?"
            st.markdown(
                f"""
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-waiting"></span>
                  <div class="ticket-status-meta"><strong>Application occupee</strong><br>Position actuelle dans la file : {position}.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.warning(f"Application occupee. Position dans la file : {position}.")
        elif snapshot["statut"] == "refuse":
            st.markdown(
                """
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-error"></span>
                  <div class="ticket-status-meta"><strong>File d'attente pleine</strong><br>Impossible d'ajouter un nouvel utilisateur pour le moment.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.error("File d'attente pleine pour cette application.")
        else:
            st.markdown(
                """
                <div class="ticket-status-card">
                  <span class="ticket-status-dot is-error"></span>
                  <div class="ticket-status-meta"><strong>Acces indisponible</strong><br>Le ticket courant n'a pas pu etre valide.</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.error("Controle d'acces temporairement indisponible.")
            if snapshot["message"]:
                st.caption(snapshot["message"])

    if snapshot["statut"] == "actif":
        st_autorefresh(interval=snapshot["heartbeat_ms"], key=f"{default_app_id}-heartbeat")
        return snapshot

    if snapshot["statut"] == "attente":
        st_autorefresh(interval=snapshot["wait_refresh_ms"], key=f"{default_app_id}-wait")
        st.warning(
            f"{app_label} est actuellement utilisee par un autre utilisateur. "
            f"Votre position dans la file d'attente : {snapshot['position'] or '?'}."
        )
        st.stop()

    if snapshot["statut"] == "refuse":
        st.error("File d'attente pleine pour cette application.")
    else:
        st.error("Controle d'acces temporairement indisponible.")
        if snapshot["message"]:
            st.caption(snapshot["message"])
    st.stop()
