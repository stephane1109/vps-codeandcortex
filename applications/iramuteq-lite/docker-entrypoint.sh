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


APP_DATA_DIR="${IRAMUTEQ_APP_DATA_DIR:-/data/app}"
MPLCONFIG_PATH="${MPLCONFIGDIR:-$APP_DATA_DIR/mplconfig}"
PORT="${PORT:-8000}"
PYTHON_SITE_DIR="${IRAMUTEQ_PYTHON_SITE_DIR:-$APP_DATA_DIR/python-site-packages}"
R_LIBRARY_DIR="${IRAMUTEQ_R_LIBS_USER:-$APP_DATA_DIR/r-library}"

mkdir -p "$APP_DATA_DIR"
mkdir -p "$APP_DATA_DIR/jobs"
mkdir -p "$APP_DATA_DIR/downloads"
mkdir -p "$APP_DATA_DIR/dictionnaires"
mkdir -p "$MPLCONFIG_PATH"
mkdir -p "$PYTHON_SITE_DIR"
mkdir -p "$R_LIBRARY_DIR"
mkdir -p /tmp/iramuteq-lite

export TMPDIR="${TMPDIR:-/tmp/iramuteq-lite}"
export MPLCONFIGDIR="$MPLCONFIG_PATH"
export IRAMUTEQ_PYTHON_SITE_DIR="$PYTHON_SITE_DIR"
export IRAMUTEQ_R_LIBS_USER="$R_LIBRARY_DIR"
export PYTHONPATH="${PYTHON_SITE_DIR}${PYTHONPATH:+:$PYTHONPATH}"
export R_LIBS_SITE="${R_LIBS_SITE:-${IRAMUTEQ_R_SYSTEM_LIBS:-/usr/lib/R/site-library:/usr/lib/R/library:/usr/local/lib/R/site-library:/usr/local/lib/R/library}}"

publish_ticket_runtime_config

exec python3 -m uvicorn webapp.main:app --host 0.0.0.0 --port "$PORT"
