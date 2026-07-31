#!/bin/sh
set -eu

publish_ticket_runtime_config() {
  [ -n "${REDIS_URL:-}" ] || return 0
  [ -n "${APP_TICKET_ID:-}" ] || return 0

  if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
  else
    return 0
  fi

  "$PY_BIN" - <<'PYTHON' || true
import os
import time

url = os.getenv("REDIS_URL", "").strip()
app_id = os.getenv("APP_TICKET_ID", "").strip()
if not url or not app_id:
    raise SystemExit(0)

try:
    import redis
except Exception:
    raise SystemExit(0)


def env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(float(os.getenv(name, str(default)))))
    except Exception:
        return max(minimum, default)


label = (os.getenv("APP_TICKET_LABEL") or os.getenv("APP_NAME") or app_id).strip() or app_id
heartbeat_ms = env_int("APP_TICKET_HEARTBEAT_MS", 300000, 0)
ttl_seconds = env_int("APP_TICKET_TTL_SECONDS", 3600, 60)
now = int(time.time())

payload = {
    "application_id": app_id,
    "application_label": label,
    "label": label,
    "max_active": env_int("APP_TICKET_MAX_ACTIVE", 1, 1),
    "cost": env_int("APP_TICKET_COST", 1, 0),
    "cout": env_int("APP_TICKET_COST", 1, 0),
    "global_capacity": env_int("CAPACITE_SERVEUR", 6, 1),
    "capacite_serveur": env_int("CAPACITE_SERVEUR", 6, 1),
    "ttl_seconds": ttl_seconds,
    "max_waiting": env_int("APP_TICKET_MAX_WAITING", 20, 0),
    "wait_refresh_ms": env_int("APP_TICKET_WAIT_REFRESH_MS", 10000, 2000),
    "heartbeat_ms": heartbeat_ms,
    "enabled": 0 if str(os.getenv("APP_TICKET_ENFORCED", "1")).strip().lower() in {"0", "false", "no", "off"} else 1,
    "published_at": now,
    "updated_at": now,
}

client = redis.from_url(url, decode_responses=True)
client.hset(f"app:{app_id}:config", mapping=payload)
client.expire(f"app:{app_id}:config", max(3600, ttl_seconds, max(30, heartbeat_ms // 1000) * 3))
PYTHON
}


PORT="${PORT:-8501}"
BASE_URL_PATH="${STREAMLIT_SERVER_BASE_URL_PATH:-}"

set -- streamlit run app.py --server.address=0.0.0.0 --server.port="${PORT}"

if [ -n "${BASE_URL_PATH}" ]; then
  set -- "$@" --server.baseUrlPath="${BASE_URL_PATH}"
fi

publish_ticket_runtime_config

exec "$@"
