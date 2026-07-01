from __future__ import annotations

import os
import time
import uuid
from typing import Any

from fastapi import Request

try:
    import redis
except ModuleNotFoundError:  # pragma: no cover
    redis = None


"""
Contrôle d'accès Redis pour la version web de CHD Rainette.

#### VARIABLES D'ENVIRONNEMENT A REGLER DANS COOLIFY

- REDIS_URL
- APP_TICKET_ID
- APP_TICKET_MAX_ACTIVE
- APP_TICKET_COST
- CAPACITE_SERVEUR
- APP_TICKET_TTL_SECONDS
- APP_TICKET_MAX_WAITING
- APP_TICKET_WAIT_REFRESH_MS
- APP_TICKET_HEARTBEAT_MS
- APP_TICKET_IDLE_RELEASE_MS
- APP_TICKET_ENFORCED
"""


SESSION_COOKIE_NAME = os.getenv("APP_TICKET_SESSION_COOKIE", "chdrainette_ticket_session")


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


def _config(default_app_id: str = "chdrainette", app_label: str = "CHD Rainette") -> dict[str, Any]:
    return {
        "enabled": _env_bool("APP_TICKET_ENFORCED", True),
        "app_id": os.getenv("APP_TICKET_ID", default_app_id).strip() or default_app_id,
        "app_label": app_label,
        "max_active": max(1, _env_int("APP_TICKET_MAX_ACTIVE", 1)),
        "cost": max(0, _env_int("APP_TICKET_COST", 4)),
        "global_capacity": max(1, _env_int("CAPACITE_SERVEUR", 6)),
        "ttl_seconds": max(60, _env_int("APP_TICKET_TTL_SECONDS", 300)),
        "max_waiting": max(0, _env_int("APP_TICKET_MAX_WAITING", 20)),
        "wait_refresh_ms": max(2000, _env_int("APP_TICKET_WAIT_REFRESH_MS", 10000)),
        "heartbeat_ms": max(15000, _env_int("APP_TICKET_HEARTBEAT_MS", 300000)),
        "idle_release_ms": max(60000, _env_int("APP_TICKET_IDLE_RELEASE_MS", 900000)),
    }


def _redis_client():
    if redis is None:
        return None, "Le paquet Python 'redis' n'est pas installé dans CHD Rainette."
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None, "REDIS_URL absent : configure une URL Redis complète avec mot de passe dans Coolify."
    try:
        client = redis.from_url(redis_url, decode_responses=True)
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


def _build_snapshot(
    cfg: dict[str, Any],
    *,
    enabled: bool,
    statut: str,
    active: int,
    queued: int,
    ticket_id: str | None = None,
    position: int | None = None,
    message: str = "",
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "ticket_id": ticket_id,
        "statut": statut,
        "position": position,
        "active": active,
        "queued": queued,
        "max_active": cfg["max_active"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "idle_release_ms": cfg["idle_release_ms"],
        "message": message,
    }


def _disabled_snapshot(cfg: dict[str, Any], message: str) -> dict[str, Any]:
    return _build_snapshot(cfg, enabled=False, statut="actif", active=0, queued=0, message=message)


def _error_snapshot(cfg: dict[str, Any], message: str) -> dict[str, Any]:
    return _build_snapshot(cfg, enabled=True, statut="erreur", active=0, queued=0, message=message)


def _snapshot(client, cfg: dict[str, Any], ticket_id: str | None, bypass_message: str | None = None) -> dict[str, Any]:
    if client is None:
        return _disabled_snapshot(cfg, bypass_message or "Contrôle d'accès désactivé.")

    active = _active_count(client, cfg)
    queued = _waiting_count(client, cfg)
    if not ticket_id:
        return _build_snapshot(
            cfg,
            enabled=True,
            statut="inconnu",
            active=active,
            queued=queued,
            message="Aucun ticket associé à cette session.",
        )

    data = client.hgetall(_ticket_key(ticket_id)) or {}
    return _build_snapshot(
        cfg,
        enabled=True,
        statut=data.get("status", "inconnu"),
        active=active,
        queued=queued,
        ticket_id=ticket_id,
        position=_waiting_position(client, cfg, ticket_id),
        message=data.get("message", ""),
    )


def _public_status(client, cfg: dict[str, Any], bypass_message: str | None = None) -> dict[str, Any]:
    if client is None:
        return _disabled_snapshot(cfg, bypass_message or "Contrôle d'accès désactivé.")
    _cleanup_expired(client, cfg)
    _promote_waiting(client, cfg)
    active = _active_count(client, cfg)
    queued = _waiting_count(client, cfg)
    statut = "occupee" if active >= cfg["max_active"] else "disponible"
    message = "Application occupée." if statut == "occupee" else "Application disponible."
    return _build_snapshot(cfg, enabled=True, statut=statut, active=active, queued=queued, message=message)


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
        client.hset(_ticket_key(existing_ticket), mapping={"updated_at": int(time.time())})
        _promote_waiting(client, cfg)
        return _snapshot(client, cfg, existing_ticket)

    if existing_ticket:
        client.delete(session_key)

    ticket_id = uuid.uuid4().hex
    waiting_key = _keys(cfg["app_id"])["waiting"]
    active_key = _keys(cfg["app_id"])["active"]

    if _waiting_count(client, cfg) >= cfg["max_waiting"]:
        return _build_snapshot(
            cfg,
            enabled=True,
            statut="refuse",
            active=_active_count(client, cfg),
            queued=_waiting_count(client, cfg),
            message="File d'attente pleine pour cette application.",
        )

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


def _refresh_existing_ticket(client, cfg: dict[str, Any], session_id: str | None) -> dict[str, Any]:
    if client is None:
        return _error_snapshot(cfg, "Redis indisponible : impossible de vérifier le ticket.")
    if not session_id:
        return _public_status(client, cfg)

    _cleanup_expired(client, cfg)
    _promote_waiting(client, cfg)

    session_key = _session_key(cfg["app_id"], session_id)
    ticket_id = client.get(session_key)
    if not ticket_id:
        return _public_status(client, cfg)
    if not client.exists(_ticket_key(ticket_id)):
        client.delete(session_key)
        return _public_status(client, cfg)

    client.expire(session_key, cfg["ttl_seconds"])
    client.expire(_ticket_key(ticket_id), cfg["ttl_seconds"])
    client.hset(_ticket_key(ticket_id), mapping={"updated_at": int(time.time())})
    _promote_waiting(client, cfg)
    return _snapshot(client, cfg, ticket_id)


def _session_id_from_request(request: Request) -> str | None:
    value = request.cookies.get(SESSION_COOKIE_NAME, "").strip()
    if not value:
        value = request.headers.get("X-App-Ticket-Session", "").strip()
    return value or None


def status_for_request(request: Request) -> tuple[dict[str, Any], str | None]:
    cfg = _config()
    if not cfg["enabled"]:
        return _disabled_snapshot(cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0."), None
    client, message = _redis_client()
    session_id = _session_id_from_request(request)
    if client is None:
        return _error_snapshot(cfg, message or "Redis indisponible."), session_id
    return _refresh_existing_ticket(client, cfg, session_id), session_id


def claim_ticket_for_request(request: Request) -> tuple[dict[str, Any], str]:
    cfg = _config()
    session_id = _session_id_from_request(request) or uuid.uuid4().hex
    if not cfg["enabled"]:
        return _disabled_snapshot(cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0."), session_id
    client, message = _redis_client()
    if client is None:
        return _error_snapshot(cfg, message or "Redis indisponible."), session_id
    return _claim_or_refresh(client, cfg, session_id), session_id


def heartbeat_ticket_for_request(request: Request) -> tuple[dict[str, Any], str | None]:
    cfg = _config()
    session_id = _session_id_from_request(request)
    if not cfg["enabled"]:
        return _disabled_snapshot(cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0."), session_id
    client, message = _redis_client()
    if client is None:
        return _error_snapshot(cfg, message or "Redis indisponible."), session_id
    return _refresh_existing_ticket(client, cfg, session_id), session_id


def release_ticket_for_request(request: Request) -> dict[str, Any]:
    cfg = _config()
    session_id = _session_id_from_request(request)
    if not cfg["enabled"]:
        return _disabled_snapshot(cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0.")
    client, message = _redis_client()
    if client is None:
        return _error_snapshot(cfg, message or "Redis indisponible.")
    if not session_id:
        return _public_status(client, cfg)

    session_key = _session_key(cfg["app_id"], session_id)
    ticket_id = client.get(session_key)
    if ticket_id:
        client.zrem(_keys(cfg["app_id"])["active"], ticket_id)
        client.zrem(_keys(cfg["app_id"])["waiting"], ticket_id)
        client.zrem(_global_active_key(), ticket_id)
        client.delete(_ticket_key(ticket_id))
        client.delete(session_key)
    _promote_waiting(client, cfg)
    return _public_status(client, cfg)


def apply_session_cookie_headers(response, session_id: str | None) -> None:
    if not session_id:
        return
    ttl = _config()["ttl_seconds"]
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=ttl,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie_headers(response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def require_active_ticket(request: Request) -> dict[str, Any]:
    cfg = _config()
    if not cfg["enabled"]:
        return _disabled_snapshot(cfg, "Contrôle d'accès désactivé par APP_TICKET_ENFORCED=0.")
    client, message = _redis_client()
    if client is None:
        raise PermissionError(message or "Redis indisponible pour vérifier le ticket actif.")
    session_id = _session_id_from_request(request)
    snapshot = _refresh_existing_ticket(client, cfg, session_id)
    if snapshot["statut"] != "actif":
        raise PermissionError(snapshot.get("message") or "Aucun ticket actif pour lancer cette analyse.")
    return snapshot
