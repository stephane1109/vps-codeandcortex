from __future__ import annotations

import os
import tempfile
from pathlib import Path


APP_ID = "extraction-multimedia"
APP_DATA_ENV = "APP_DATA_DIR"
DEFAULT_APP_DATA_DIR = "/tmp/appdata"

_RESOLVED_APP_DATA_DIR: Path | None = None


def _is_writable_directory(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def resolve_app_data_dir() -> Path:
    """Return a server-side data directory that the current container user can write."""
    global _RESOLVED_APP_DATA_DIR

    if _RESOLVED_APP_DATA_DIR is not None:
        return _RESOLVED_APP_DATA_DIR

    configured = os.getenv(APP_DATA_ENV, "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path(DEFAULT_APP_DATA_DIR))
    candidates.append(Path(tempfile.gettempdir()) / APP_ID)

    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if _is_writable_directory(candidate):
            _RESOLVED_APP_DATA_DIR = candidate
            os.environ[APP_DATA_ENV] = str(candidate)
            return candidate

    raise RuntimeError(
        "Aucun dossier de donnees inscriptible pour extraction-multimedia. "
        f"Verifiez {APP_DATA_ENV} ou les droits du volume Coolify."
    )
