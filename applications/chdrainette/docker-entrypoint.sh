#!/bin/sh
set -eu

publish_ticket_runtime_config() {
  [ -n "${REDIS_URL:-}" ] || return 0

  if command -v python3 >/dev/null 2>&1; then
    PY_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PY_BIN="python"
  else
    return 0
  fi

  "$PY_BIN" - <<'PYTHON' || true
import os
import re
import time
from pathlib import Path

app_root = Path.cwd()
url = os.getenv("REDIS_URL", "").strip()
if not url:
    raise SystemExit(0)

try:
    import redis
except Exception:
    raise SystemExit(0)

candidate_files = [
    app_root / "ticket_gate.py",
    app_root / "webapp" / "ticket_gate.py",
    app_root / "main.py",
    app_root / "webapp" / "main.py",
    app_root / "README.md",
    app_root / "Dockerfile",
]
texts: list[tuple[str, str]] = []
for path in candidate_files:
    if not path.exists():
        continue
    try:
        texts.append((path.relative_to(app_root).as_posix(), path.read_text(encoding="utf-8")))
    except Exception:
        try:
            texts.append((path.relative_to(app_root).as_posix(), path.read_text()))
        except Exception:
            pass

if not texts:
    raise SystemExit(0)

joined_text = "\n".join(text for _, text in texts)
search_flags = re.MULTILINE | re.DOTALL


def extract(patterns, file_names=None):
    if isinstance(patterns, str):
        patterns = [patterns]
    allowed = set(file_names or [])
    for pattern in patterns:
        for relative_path, text in texts:
            if allowed and relative_path not in allowed:
                continue
            match = re.search(pattern, text, search_flags)
            if not match:
                continue
            for group_name in ("value", "label", "id"):
                value = match.groupdict().get(group_name)
                if value is not None:
                    value = str(value).strip().strip('"').strip("'")
                    if value:
                        return value
            if match.groups():
                value = str(match.group(1)).strip().strip('"').strip("'")
                if value:
                    return value
    return ""


def clean_label(value: str, fallback: str) -> str:
    label = str(value or "").strip()
    label = re.sub(r'^[#\s\-]+', '', label)
    label = re.sub(r'^(projet\s*:\s*)', '', label, flags=re.IGNORECASE)
    return label.strip() or fallback


def extract_int(name: str, fallback: int) -> int:
    raw = extract(
        [
            rf'_env_int\(\s*"{re.escape(name)}"\s*,\s*(?P<value>\d+)\s*\)',
            rf'\b{re.escape(name)}\b\s*=\s*"?(?P<value>\d+)"?',
        ]
    )
    try:
        return int(raw)
    except Exception:
        return fallback


def env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(float(os.getenv(name, str(default)))))
    except Exception:
        return max(minimum, default)


def infer_app_id() -> str:
    value = (os.getenv("APP_TICKET_ID") or "").strip()
    if value:
        return value
    value = extract(
        [
            r'def _config\([\s\S]*?default_app_id: str\s*=\s*"(?P<value>[^"]+)"',
            r'enforce_streamlit_access\(\s*"(?P<value>[^"]+)"\s*,',
            r'\bAPP_TICKET_ID\b\s*=\s*"?(?P<value>[A-Za-z0-9_\-]+)"?',
        ],
        file_names=["ticket_gate.py", "webapp/ticket_gate.py", "main.py", "webapp/main.py", "Dockerfile"],
    )
    if value:
        return value
    if any((app_root / relative).exists() for relative in ("ticket_gate.py", "webapp/ticket_gate.py", "main.py", "webapp/main.py", "README.md")):
        return app_root.name
    if any(hint in joined_text for hint in ("APP_TICKET_", "ticket_gate", "enforce_streamlit_access(", "APP_NAME", "APP_DISPLAY_NAME", "st.set_page_config(", "st.title(")):
        return app_root.name
    return ""


def infer_label(app_id: str) -> str:
    value = (os.getenv("APP_TICKET_LABEL") or os.getenv("APP_NAME") or "").strip()
    if value:
        return clean_label(value, app_id)
    value = extract(
        [
            r'def _config\([\s\S]*?app_label: str\s*=\s*"(?P<label>[^"]+)"',
            r'enforce_streamlit_access\(\s*"[^"]+"\s*,\s*"(?P<label>[^"]+)"',
            r'\bAPP_TICKET_LABEL\b\s*=\s*"?(?P<label>[^"\n]+)"?',
            r'\bAPP_DISPLAY_NAME\b\s*=\s*"(?P<label>[^"]+)"',
            r"\bAPP_DISPLAY_NAME\b\s*=\s*'(?P<label>[^']+)'",
            r'\bAPP_NAME\b\s*=\s*"(?P<label>[^"]+)"',
            r"\bAPP_NAME\b\s*=\s*'(?P<label>[^']+)'",
            r'st\.title\(\s*"(?P<label>[^"]+)"',
            r"st\.title\(\s*'(?P<label>[^']+)'",
            r'st\.set_page_config\([\s\S]*?page_title\s*=\s*"(?P<label>[^"]+)"',
            r"st\.set_page_config\([\s\S]*?page_title\s*=\s*'(?P<label>[^']+)'",
        ],
        file_names=["ticket_gate.py", "webapp/ticket_gate.py", "main.py", "webapp/main.py", "Dockerfile"],
    )
    if value:
        return clean_label(value, app_id)
    value = extract(r'^#{1,6}\s+(?P<label>[^\n]+)$', file_names=["README.md"])
    return clean_label(value, app_id)


app_id = infer_app_id()
if not app_id:
    raise SystemExit(0)

label = infer_label(app_id)
heartbeat_default = extract_int("APP_TICKET_HEARTBEAT_MS", 300000)
ttl_default = extract_int("APP_TICKET_TTL_SECONDS", 3600)
now = int(time.time())
heartbeat_ms = env_int("APP_TICKET_HEARTBEAT_MS", heartbeat_default, 0)
ttl_seconds = env_int("APP_TICKET_TTL_SECONDS", ttl_default, 60)
max_active_default = extract_int("APP_TICKET_MAX_ACTIVE", 1)
cost_default = extract_int("APP_TICKET_COST", 1)
global_capacity_default = extract_int("CAPACITE_SERVEUR", 6)
max_waiting_default = extract_int("APP_TICKET_MAX_WAITING", 20)
wait_refresh_default = extract_int("APP_TICKET_WAIT_REFRESH_MS", 10000)
enforced_default = extract_int("APP_TICKET_ENFORCED", 1)

payload = {
    "application_id": app_id,
    "application_label": label,
    "label": label,
    "max_active": env_int("APP_TICKET_MAX_ACTIVE", max_active_default, 1),
    "cost": env_int("APP_TICKET_COST", cost_default, 0),
    "cout": env_int("APP_TICKET_COST", cost_default, 0),
    "global_capacity": env_int("CAPACITE_SERVEUR", global_capacity_default, 1),
    "capacite_serveur": env_int("CAPACITE_SERVEUR", global_capacity_default, 1),
    "ttl_seconds": ttl_seconds,
    "max_waiting": env_int("APP_TICKET_MAX_WAITING", max_waiting_default, 0),
    "wait_refresh_ms": env_int("APP_TICKET_WAIT_REFRESH_MS", wait_refresh_default, 2000),
    "heartbeat_ms": heartbeat_ms,
    "enabled": 0 if str(os.getenv("APP_TICKET_ENFORCED", str(enforced_default))).strip().lower() in {"0", "false", "no", "off"} else 1,
    "published_at": now,
    "updated_at": now,
}

client = redis.from_url(url, decode_responses=True)
client.hset(f"app:{app_id}:config", mapping=payload)
client.expire(f"app:{app_id}:config", max(3600, ttl_seconds, max(30, heartbeat_ms // 1000) * 3))
PYTHON
}






PORT="${PORT:-8000}"

publish_ticket_runtime_config

exec python3 -m uvicorn webapp.main:app --host 0.0.0.0 --port "${PORT}"
