from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request
from starlette.responses import Response


OWNER_COOKIE_NAME = os.getenv("IRAMUTEQ_ANALYSIS_OWNER_COOKIE", "iramuteq_analysis_owner")


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except (TypeError, ValueError):
        return default


def retention_days() -> int:
    return _env_int("IRAMUTEQ_ANALYSIS_RETENTION_DAYS", 30)


def owner_cookie_days() -> int:
    return _env_int("IRAMUTEQ_ANALYSIS_OWNER_COOKIE_DAYS", 90)


def owner_cookie_secure() -> bool:
    value = os.getenv("IRAMUTEQ_ANALYSIS_OWNER_COOKIE_SECURE", "1")
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _hash_owner_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def owner_for_request(request: Request) -> tuple[str, str | None]:
    """Return the anonymous owner hash and a token to set when this is a new browser."""
    token = str(request.cookies.get(OWNER_COOKIE_NAME, "")).strip()
    if token:
        return _hash_owner_token(token), None

    token = secrets.token_urlsafe(32)
    return _hash_owner_token(token), token


def apply_owner_cookie(response: Response, token: str | None) -> None:
    if not token:
        return
    response.set_cookie(
        key=OWNER_COOKIE_NAME,
        value=token,
        max_age=owner_cookie_days() * 86400,
        httponly=True,
        secure=owner_cookie_secure(),
        samesite="lax",
        path="/",
    )


def database_path(data_root: Path) -> Path:
    return data_root / "analysis-history.sqlite3"


def _connect(data_root: Path) -> sqlite3.Connection:
    data_root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path(data_root), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id TEXT PRIMARY KEY,
            owner_hash TEXT NOT NULL,
            job_id TEXT NOT NULL UNIQUE,
            corpus_name TEXT NOT NULL,
            analysis_kind TEXT NOT NULL,
            navigation_target TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            status TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            success INTEGER,
            message TEXT NOT NULL DEFAULT '',
            summary_json TEXT,
            logs_json TEXT,
            output_dir TEXT,
            artifact_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS analyses_owner_created_idx ON analyses(owner_hash, created_at DESC)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS analyses_expiry_idx ON analyses(expires_at, completed)"
    )
    return connection


def _to_iso(value: Any) -> str:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_json(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str) or not value:
        return fallback
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _record_from_row(row: sqlite3.Row, *, include_internal: bool = False) -> dict[str, Any]:
    success_value = row["success"]
    record = {
        "id": str(row["id"]),
        "jobId": str(row["job_id"]),
        "corpusName": str(row["corpus_name"]),
        "analysisKind": str(row["analysis_kind"]),
        "navigationTarget": str(row["navigation_target"]),
        "createdAt": _to_iso(row["created_at"]),
        "updatedAt": _to_iso(row["updated_at"]),
        "expiresAt": _to_iso(row["expires_at"]),
        "status": str(row["status"]),
        "completed": bool(row["completed"]),
        "success": None if success_value is None else bool(success_value),
        "message": str(row["message"] or ""),
        "summary": _parse_json(row["summary_json"], None),
        "logs": _parse_json(row["logs_json"], []),
        "artifactCount": int(row["artifact_count"] or 0),
    }
    if include_internal:
        record["ownerHash"] = str(row["owner_hash"])
        record["outputDir"] = str(row["output_dir"] or "")
    return record


def _record_for_owner(
    data_root: Path,
    owner_hash: str,
    analysis_id: str,
    *,
    include_internal: bool = False,
) -> dict[str, Any] | None:
    with _connect(data_root) as connection:
        row = connection.execute(
            "SELECT * FROM analyses WHERE id = ? AND owner_hash = ?",
            (str(analysis_id or "").strip(), owner_hash),
        ).fetchone()
    return _record_from_row(row, include_internal=include_internal) if row else None


def create_analysis(
    data_root: Path,
    *,
    owner_hash: str,
    job_id: str,
    corpus_name: str,
    analysis_kind: str,
    navigation_target: str,
) -> dict[str, Any]:
    now = int(time.time())
    analysis_id = uuid.uuid4().hex
    record_values = (
        analysis_id,
        owner_hash,
        str(job_id).strip(),
        str(corpus_name or "corpus.txt").strip() or "corpus.txt",
        str(analysis_kind or "chd").strip() or "chd",
        str(navigation_target or "resultats_chd").strip() or "resultats_chd",
        now,
        now,
        now + retention_days() * 86400,
        "running",
    )
    with _connect(data_root) as connection:
        try:
            connection.execute(
                """
                INSERT INTO analyses (
                    id, owner_hash, job_id, corpus_name, analysis_kind, navigation_target,
                    created_at, updated_at, expires_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                record_values,
            )
        except sqlite3.IntegrityError as error:
            existing = connection.execute(
                "SELECT * FROM analyses WHERE job_id = ? AND owner_hash = ?",
                (str(job_id).strip(), owner_hash),
            ).fetchone()
            if existing:
                return _record_from_row(existing)
            raise RuntimeError("Impossible d'enregistrer cette analyse dans l'historique.") from error

        row = connection.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
    if not row:  # pragma: no cover - defensive guard for a failed SQLite write
        raise RuntimeError("Impossible de relire l'analyse enregistrée.")
    return _record_from_row(row)


def get_owned_analysis(data_root: Path, owner_hash: str, analysis_id: str) -> dict[str, Any] | None:
    return _record_for_owner(data_root, owner_hash, analysis_id, include_internal=True)


def get_analysis_by_job(data_root: Path, job_id: str) -> dict[str, Any] | None:
    with _connect(data_root) as connection:
        row = connection.execute(
            "SELECT * FROM analyses WHERE job_id = ?",
            (str(job_id or "").strip(),),
        ).fetchone()
    return _record_from_row(row, include_internal=True) if row else None


def list_owned_analyses(data_root: Path, owner_hash: str, limit: int = 40) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 100))
    with _connect(data_root) as connection:
        rows = connection.execute(
            "SELECT * FROM analyses WHERE owner_hash = ? ORDER BY created_at DESC LIMIT ?",
            (owner_hash, safe_limit),
        ).fetchall()
    return [_record_from_row(row) for row in rows]


def update_analysis_from_snapshot(
    data_root: Path,
    *,
    owner_hash: str,
    analysis_id: str,
    snapshot: dict[str, Any],
) -> dict[str, Any] | None:
    current = _record_for_owner(data_root, owner_hash, analysis_id, include_internal=True)
    if not current:
        return None

    now = int(time.time())
    completed = bool(snapshot.get("completed"))
    state = str(snapshot.get("state") or current["status"] or "running").strip().lower() or "running"
    success = snapshot.get("success") if completed else None
    summary = snapshot.get("summary")
    logs = snapshot.get("logs")
    output_dir = str(snapshot.get("outputDir") or "").strip()
    artifact_count = snapshot.get("artifactCount")
    if not isinstance(artifact_count, int):
        files = snapshot.get("files")
        artifact_count = len(files) if isinstance(files, list) else current["artifactCount"]

    with _connect(data_root) as connection:
        connection.execute(
            """
            UPDATE analyses
            SET updated_at = ?, status = ?, completed = ?, success = ?, message = ?,
                summary_json = ?, logs_json = ?, output_dir = ?, artifact_count = ?
            WHERE id = ? AND owner_hash = ?
            """,
            (
                now,
                state,
                int(completed),
                int(bool(success)) if completed else None,
                str(snapshot.get("message") or ""),
                json.dumps(summary, ensure_ascii=False) if summary is not None else None,
                json.dumps(logs, ensure_ascii=False) if isinstance(logs, list) else None,
                output_dir or current["outputDir"] or None,
                max(0, int(artifact_count or 0)),
                str(analysis_id),
                owner_hash,
            ),
        )

    return _record_for_owner(data_root, owner_hash, analysis_id, include_internal=True)


def delete_owned_analysis(data_root: Path, owner_hash: str, analysis_id: str) -> dict[str, Any] | None:
    record = _record_for_owner(data_root, owner_hash, analysis_id, include_internal=True)
    if not record:
        return None
    with _connect(data_root) as connection:
        connection.execute(
            "DELETE FROM analyses WHERE id = ? AND owner_hash = ?",
            (str(analysis_id), owner_hash),
        )
    return record


def purge_expired_analyses(data_root: Path) -> list[dict[str, Any]]:
    now = int(time.time())
    with _connect(data_root) as connection:
        rows = connection.execute(
            "SELECT * FROM analyses WHERE completed = 1 AND expires_at <= ?",
            (now,),
        ).fetchall()
        if rows:
            connection.executemany("DELETE FROM analyses WHERE id = ?", [(row["id"],) for row in rows])
    return [_record_from_row(row, include_internal=True) for row in rows]
