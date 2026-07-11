#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from typing import Iterable

try:
    import redis
except Exception as exc:  # pragma: no cover - depends on container image
    print(f"Le paquet Python 'redis' n'est pas installe : {exc}", file=sys.stderr)
    sys.exit(2)


def redis_client():
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        print("REDIS_URL absent : configure une URL Redis complete avec mot de passe dans Coolify.", file=sys.stderr)
        sys.exit(2)
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return client
    except Exception as exc:  # pragma: no cover - depends on runtime Redis
        print(f"Connexion Redis impossible via REDIS_URL : {exc}", file=sys.stderr)
        sys.exit(2)


def emit_lines(values: Iterable[object]) -> None:
    for value in values:
        if value is None:
            continue
        print(str(value))


def main(argv: list[str]) -> int:
    if not argv:
        print("Commande Redis absente.", file=sys.stderr)
        return 2

    client = redis_client()
    command = argv[0].upper()
    args = argv[1:]

    try:
        if command == "PING":
            emit_lines([client.ping() and "PONG"])
        elif command == "EXISTS":
            emit_lines([client.exists(*args)])
        elif command == "GET":
            emit_lines([client.get(args[0]) if args else ""])
        elif command == "SETEX":
            client.setex(args[0], int(args[1]), args[2])
            emit_lines(["OK"])
        elif command == "EXPIRE":
            emit_lines([int(bool(client.expire(args[0], int(args[1]))))])
        elif command == "DEL":
            emit_lines([client.delete(*args) if args else 0])
        elif command == "ZREM":
            emit_lines([client.zrem(args[0], *args[1:])])
        elif command == "ZADD":
            key, score, member = args[0], float(args[1]), args[2]
            emit_lines([client.zadd(key, {member: score})])
        elif command == "ZRANGE":
            start = int(args[1])
            stop = int(args[2])
            emit_lines(client.zrange(args[0], start, stop))
        elif command == "ZCARD":
            emit_lines([client.zcard(args[0])])
        elif command == "HGETALL":
            data = client.hgetall(args[0])
            flattened: list[str] = []
            for key, value in data.items():
                flattened.extend([key, value])
            emit_lines(flattened)
        elif command == "HSET":
            key = args[0]
            flat = args[1:]
            mapping = {flat[index]: flat[index + 1] for index in range(0, len(flat), 2) if index + 1 < len(flat)}
            emit_lines([client.hset(key, mapping=mapping)])
        else:
            print(f"Commande Redis non prise en charge : {command}", file=sys.stderr)
            return 2
        return 0
    except Exception as exc:  # pragma: no cover - depends on runtime Redis
        print(f"Erreur Redis pendant {command} : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
