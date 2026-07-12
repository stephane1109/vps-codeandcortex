#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from typing import Any

try:
    import redis
except Exception as exc:  # pragma: no cover - depends on container image
    redis = None
    REDIS_IMPORT_ERROR = exc
else:
    REDIS_IMPORT_ERROR = None


def env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def config(default_app_id: str = "chdrainette", app_label: str = "CHD Rainette") -> dict[str, Any]:
    ttl_seconds = max(60, env_int("APP_TICKET_TTL_SECONDS", 300))
    wait_stale_default = min(ttl_seconds, 120)
    return {
        "enabled": env_bool("APP_TICKET_ENFORCED", True),
        "app_id": os.getenv("APP_TICKET_ID", default_app_id).strip() or default_app_id,
        "app_label": app_label,
        "max_active": max(1, env_int("APP_TICKET_MAX_ACTIVE", 1)),
        "cost": max(0, env_int("APP_TICKET_COST", 4)),
        "global_capacity": max(1, env_int("CAPACITE_SERVEUR", 6)),
        "ttl_seconds": ttl_seconds,
        "max_waiting": max(0, env_int("APP_TICKET_MAX_WAITING", 20)),
        "wait_refresh_ms": max(2000, env_int("APP_TICKET_WAIT_REFRESH_MS", 10000)),
        "heartbeat_ms": max(15000, env_int("APP_TICKET_HEARTBEAT_MS", 30000)),
        "wait_stale_seconds": max(30, env_int("APP_TICKET_WAIT_STALE_SECONDS", wait_stale_default)),
    }


def redis_client():
    if redis is None:
        raise RuntimeError(f"Le paquet Python 'redis' n'est pas installe : {REDIS_IMPORT_ERROR}")
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        raise RuntimeError("REDIS_URL absent : configure une URL Redis complete avec mot de passe dans Coolify.")
    client = redis.from_url(redis_url, decode_responses=True)
    client.ping()
    return client


def keys(app_id: str) -> dict[str, str]:
    return {
        "active": f"app:{app_id}:tickets:actifs",
        "waiting": f"app:{app_id}:tickets:attente",
    }


def ticket_key(ticket_id: str) -> str:
    return f"ticket:{ticket_id}"


def session_key(app_id: str, session_id: str) -> str:
    return f"session:{app_id}:{session_id}:ticket"


def global_active_key() -> str:
    return "tickets:global:actifs"


def list_members(client, key: str) -> list[str]:
    return [str(item) for item in client.zrange(key, 0, -1)]


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def ticket_timeout_seconds(cfg: dict[str, Any], status: str) -> int:
    if status == "attente":
        return int(cfg["wait_stale_seconds"])
    return int(cfg["ttl_seconds"])


def drop_ticket(client, cfg: dict[str, Any], ticket_id: str) -> None:
    data = client.hgetall(ticket_key(ticket_id)) or {}
    session_id = str(data.get("session_id", "")).strip()
    app_keys = keys(cfg["app_id"])
    client.zrem(app_keys["active"], ticket_id)
    client.zrem(app_keys["waiting"], ticket_id)
    client.zrem(global_active_key(), ticket_id)
    client.delete(ticket_key(ticket_id))
    if session_id:
        client.delete(session_key(cfg["app_id"], session_id))


def cleanup_expired(client, cfg: dict[str, Any]) -> None:
    app_keys = keys(cfg["app_id"])
    seen: set[str] = set()
    now = int(time.time())

    for key in (app_keys["active"], app_keys["waiting"], global_active_key()):
        for ticket_id in list_members(client, key):
            if ticket_id in seen:
                continue
            seen.add(ticket_id)
            key_ticket = ticket_key(ticket_id)
            if not client.exists(key_ticket):
                client.zrem(app_keys["active"], ticket_id)
                client.zrem(app_keys["waiting"], ticket_id)
                client.zrem(global_active_key(), ticket_id)
                continue
            data = client.hgetall(key_ticket) or {}
            status = str(data.get("status") or "attente").strip() or "attente"
            heartbeat_at = safe_int(data.get("updated_at") or data.get("created_at"), now)
            if now - heartbeat_at > ticket_timeout_seconds(cfg, status):
                drop_ticket(client, cfg, ticket_id)


def active_count(client, cfg: dict[str, Any]) -> int:
    return int(client.zcard(keys(cfg["app_id"])["active"]))


def waiting_count(client, cfg: dict[str, Any]) -> int:
    return int(client.zcard(keys(cfg["app_id"])["waiting"]))


def active_load(client) -> int:
    total = 0
    for ticket_id in list_members(client, global_active_key()):
        data = client.hgetall(ticket_key(ticket_id)) or {}
        total += safe_int(data.get("cost"), 0)
    return total


def waiting_position(client, cfg: dict[str, Any], ticket_id: str) -> int | None:
    waiting = list_members(client, keys(cfg["app_id"])["waiting"])
    if ticket_id not in waiting:
        return None
    return waiting.index(ticket_id) + 1


def can_activate(client, cfg: dict[str, Any]) -> bool:
    return active_count(client, cfg) < cfg["max_active"] and active_load(client) + cfg["cost"] <= cfg["global_capacity"]


def promote_waiting(client, cfg: dict[str, Any]) -> None:
    app_keys = keys(cfg["app_id"])
    for ticket_id in list_members(client, app_keys["waiting"]):
        if not can_activate(client, cfg):
            break
        key_ticket = ticket_key(ticket_id)
        if not client.exists(key_ticket):
            client.zrem(app_keys["waiting"], ticket_id)
            continue
        now = int(time.time())
        client.hset(key_ticket, mapping={"status": "actif", "updated_at": now})
        client.expire(key_ticket, cfg["ttl_seconds"])
        client.zrem(app_keys["waiting"], ticket_id)
        client.zadd(app_keys["active"], {ticket_id: time.time()})
        client.zadd(global_active_key(), {ticket_id: time.time()})


def touch_existing_ticket(client, cfg: dict[str, Any], ticket_id: str, effective_session_id: str | None) -> None:
    data = client.hgetall(ticket_key(ticket_id)) or {}
    status = str(data.get("status") or "attente").strip() or "attente"
    now = int(time.time())
    timeout = ticket_timeout_seconds(cfg, status)
    client.hset(ticket_key(ticket_id), mapping={"updated_at": now})
    client.expire(ticket_key(ticket_id), timeout)
    if effective_session_id:
        client.expire(session_key(cfg["app_id"], effective_session_id), timeout)


def base_snapshot(cfg: dict[str, Any], **extra: Any) -> dict[str, Any]:
    result = {
        "enabled": True,
        "ticket_id": None,
        "statut": "inconnu",
        "position": None,
        "active": 0,
        "queued": 0,
        "max_active": cfg["max_active"],
        "wait_refresh_ms": cfg["wait_refresh_ms"],
        "heartbeat_ms": cfg["heartbeat_ms"],
        "message": "",
    }
    result.update(extra)
    return result


def disabled_snapshot(cfg: dict[str, Any], message: str) -> dict[str, Any]:
    return base_snapshot(cfg, enabled=False, statut="disabled", message=message)


def public_status(client, cfg: dict[str, Any], message: str = "") -> dict[str, Any]:
    cleanup_expired(client, cfg)
    promote_waiting(client, cfg)
    return base_snapshot(
        cfg,
        statut="public",
        active=active_count(client, cfg),
        queued=waiting_count(client, cfg),
        message=message,
    )


def snapshot(client, cfg: dict[str, Any], ticket_id: str | None, message: str = "") -> dict[str, Any]:
    cleanup_expired(client, cfg)
    promote_waiting(client, cfg)
    if not ticket_id or not client.exists(ticket_key(ticket_id)):
        return base_snapshot(
            cfg,
            statut="inconnu",
            active=active_count(client, cfg),
            queued=waiting_count(client, cfg),
            message=message or "Aucun ticket associe a cette session.",
        )

    data = client.hgetall(ticket_key(ticket_id)) or {}
    status = str(data.get("status") or "inconnu").strip() or "inconnu"
    app_keys = keys(cfg["app_id"])
    if status == "actif":
        if client.zscore(app_keys["waiting"], ticket_id) is not None:
            client.zrem(app_keys["waiting"], ticket_id)
        if client.zscore(app_keys["active"], ticket_id) is None:
            client.zadd(app_keys["active"], {ticket_id: time.time()})
        if client.zscore(global_active_key(), ticket_id) is None:
            client.zadd(global_active_key(), {ticket_id: time.time()})
    elif status == "attente" and client.zscore(app_keys["waiting"], ticket_id) is None:
        client.zadd(app_keys["waiting"], {ticket_id: safe_int(data.get("created_at"), int(time.time()))})

    return base_snapshot(
        cfg,
        ticket_id=ticket_id,
        statut=status,
        position=waiting_position(client, cfg, ticket_id),
        active=active_count(client, cfg),
        queued=waiting_count(client, cfg),
        message=str(data.get("message") or message or "").strip(),
    )


def claim_or_refresh(client, cfg: dict[str, Any], session_id: str) -> dict[str, Any]:
    cleanup_expired(client, cfg)
    promote_waiting(client, cfg)

    key_session = session_key(cfg["app_id"], session_id)
    existing_ticket = str(client.get(key_session) or "").strip()
    if existing_ticket and client.exists(ticket_key(existing_ticket)):
        touch_existing_ticket(client, cfg, existing_ticket, session_id)
        promote_waiting(client, cfg)
        return snapshot(client, cfg, existing_ticket)
    if existing_ticket:
        client.delete(key_session)

    if waiting_count(client, cfg) >= cfg["max_waiting"]:
        return base_snapshot(
            cfg,
            statut="refuse",
            active=active_count(client, cfg),
            queued=waiting_count(client, cfg),
            message="File d'attente pleine pour cette application.",
        )

    ticket_id = uuid.uuid4().hex
    status = "actif" if waiting_count(client, cfg) == 0 and can_activate(client, cfg) else "attente"
    now = int(time.time())
    client.hset(
        ticket_key(ticket_id),
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
    timeout = ticket_timeout_seconds(cfg, status)
    client.expire(ticket_key(ticket_id), timeout)
    client.setex(key_session, timeout, ticket_id)

    app_keys = keys(cfg["app_id"])
    if status == "actif":
        client.zadd(app_keys["active"], {ticket_id: time.time()})
        client.zadd(global_active_key(), {ticket_id: time.time()})
    else:
        client.zadd(app_keys["waiting"], {ticket_id: time.time()})

    promote_waiting(client, cfg)
    return snapshot(client, cfg, ticket_id)


def release(client, cfg: dict[str, Any], session_id: str | None) -> dict[str, Any]:
    if not session_id:
        return public_status(client, cfg)
    key_session = session_key(cfg["app_id"], session_id)
    ticket_id = str(client.get(key_session) or "").strip()
    if ticket_id:
        app_keys = keys(cfg["app_id"])
        client.zrem(app_keys["active"], ticket_id)
        client.zrem(app_keys["waiting"], ticket_id)
        client.zrem(global_active_key(), ticket_id)
        client.delete(ticket_key(ticket_id), key_session)
    promote_waiting(client, cfg)
    return public_status(client, cfg)


def emit_json(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Ticket Redis CHD Rainette")
    parser.add_argument("command", choices=["claim", "status", "release"])
    parser.add_argument("--session-id", default="")
    parser.add_argument("--app-label", default="CHD Rainette")
    args = parser.parse_args(argv)

    cfg = config(app_label=args.app_label)
    if not cfg["enabled"]:
        return emit_json(disabled_snapshot(cfg, "Controle d'acces desactive par APP_TICKET_ENFORCED=0."))

    try:
        client = redis_client()
        if args.command == "claim":
            session_id = args.session_id.strip() or uuid.uuid4().hex
            return emit_json(claim_or_refresh(client, cfg, session_id))
        if args.command == "status":
            if args.session_id.strip():
                ticket_id = str(client.get(session_key(cfg["app_id"], args.session_id.strip())) or "").strip()
                return emit_json(snapshot(client, cfg, ticket_id))
            return emit_json(public_status(client, cfg))
        if args.command == "release":
            return emit_json(release(client, cfg, args.session_id.strip() or None))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
