from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_DATA_ROOT = Path(os.environ.get("TMPDIR", "/tmp")) / "chdrainette-data"
ANALYSIS_LOCK_FILENAME = "active-analysis.json"
ANALYSIS_LOCK_STALE_SECONDS = 900
TERMINAL_JOB_STATES = {"cancelled", "completed", "done", "error", "failed", "success", "succeeded"}


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def frontend_root() -> Path:
    return PROJECT_ROOT / "frontend"


def app_data_root() -> Path:
    configured = (
        os.environ.get("CHDRAINETTE_APP_DATA_DIR", "").strip()
        or os.environ.get("APP_DATA_DIR", "").strip()
    )
    path = Path(configured).expanduser() if configured else DEFAULT_APP_DATA_ROOT
    return ensure_directory(path.resolve())


def jobs_root() -> Path:
    return ensure_directory(app_data_root() / "jobs")


def r_library_dir() -> Path:
    configured = (
        os.environ.get("CHDRAINETTE_R_LIBS_USER", "").strip()
        or os.environ.get("R_LIBS_USER", "").strip()
    )
    path = Path(configured).expanduser() if configured else app_data_root() / "r-library"
    return ensure_directory(path.resolve())


def cache_dir() -> Path:
    configured = os.environ.get("CHDRAINETTE_CACHE_DIR", "").strip()
    path = Path(configured).expanduser() if configured else app_data_root() / "cache"
    return ensure_directory(path.resolve())


def write_json_file(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def try_read_json_file(path: Path) -> Any | None:
    try:
        return read_json_file(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def process_is_running(pid: Any) -> bool:
    try:
        numeric_pid = int(pid)
    except (TypeError, ValueError):
        return False
    if numeric_pid <= 0:
        return False
    try:
        os.kill(numeric_pid, 0)
    except OSError:
        return False
    return True


def analysis_lock_path() -> Path:
    return app_data_root() / ANALYSIS_LOCK_FILENAME


def clear_analysis_lock(expected_job_id: str | None = None) -> None:
    lock_path = analysis_lock_path()
    if not lock_path.exists():
        return
    if expected_job_id:
        payload = try_read_json_file(lock_path)
        current_job_id = str((payload or {}).get("job_id") or "").strip()
        if current_job_id and current_job_id != expected_job_id:
            return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def current_analysis_lock() -> dict[str, Any] | None:
    lock_path = analysis_lock_path()
    if not lock_path.exists():
        return None
    payload = try_read_json_file(lock_path)
    if not isinstance(payload, dict):
        clear_analysis_lock()
        return None

    job_id = str(payload.get("job_id") or "").strip()
    created_at = int(payload.get("created_at") or time.time())
    if job_id:
        job_root = jobs_root() / job_id
        results_file = job_root / "results.json"
        status_file = job_root / "status.json"
        if results_file.exists():
            clear_analysis_lock(expected_job_id=job_id)
            return None
        status_payload = try_read_json_file(status_file) if status_file.exists() else None
        if isinstance(status_payload, dict):
            state = str(status_payload.get("state") or "").strip().lower()
            if state in TERMINAL_JOB_STATES:
                clear_analysis_lock(expected_job_id=job_id)
                return None

    if process_is_running(payload.get("pid")):
        return payload

    if not job_id and time.time() - created_at <= ANALYSIS_LOCK_STALE_SECONDS:
        return payload

    clear_analysis_lock(expected_job_id=job_id or None)
    return None


def reserve_analysis_slot(corpus_name: str | None = None) -> None:
    active_lock = current_analysis_lock()
    if active_lock:
        details = []
        if active_lock.get("corpus_name"):
            details.append(f"corpus {active_lock['corpus_name']}")
        if active_lock.get("job_id"):
            details.append(f"job {active_lock['job_id']}")
        suffix = f" ({', '.join(details)})" if details else ""
        raise RuntimeError(
            "Une analyse CHD Rainette est deja en cours sur le serveur"
            f"{suffix}. Attendez la fin avant d'en lancer une nouvelle."
        )

    payload = {
        "job_id": "",
        "pid": None,
        "corpus_name": safe_input_name(corpus_name or "corpus.txt"),
        "created_at": int(time.time()),
    }
    lock_path = analysis_lock_path()
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        active_lock = current_analysis_lock()
        if active_lock:
            raise RuntimeError("Une analyse CHD Rainette est deja en cours sur le serveur.") from error
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def activate_analysis_lock(job_id: str, pid: int, corpus_name: str | None = None) -> None:
    write_json_file(
        analysis_lock_path(),
        {
            "job_id": str(job_id or "").strip(),
            "pid": int(pid),
            "corpus_name": safe_input_name(corpus_name or "corpus.txt"),
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
        },
    )


def build_command_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["APP_DATA_DIR"] = str(app_data_root())
    env["CHDRAINETTE_APP_DATA_DIR"] = str(app_data_root())
    env["CHDRAINETTE_R_LIBS_USER"] = str(r_library_dir())
    env["R_LIBS_USER"] = str(r_library_dir())
    env["CHDRAINETTE_CACHE_DIR"] = str(cache_dir())
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    if extra:
        env.update({key: str(value) for key, value in extra.items() if value is not None})
    return env


def resolve_rscript() -> str:
    explicit = os.environ.get("CHDRAINETTE_RSCRIPT", "").strip()
    if explicit:
        return explicit
    candidates = [
        "/usr/local/bin/Rscript",
        "/opt/homebrew/bin/Rscript",
        "/Library/Frameworks/R.framework/Resources/bin/Rscript",
        "/usr/bin/Rscript",
        "Rscript",
    ]
    for candidate in candidates:
        if candidate == "Rscript":
            found = shutil.which(candidate)
            if found:
                return found
            continue
        if Path(candidate).exists():
            return candidate
    return "Rscript"


def safe_input_name(name: str) -> str:
    return (
        Path(str(name or "").strip() or "corpus.txt")
        .name
        .replace("\x00", "")
        or "corpus.txt"
    )


def next_job_id(prefix: str = "rainette") -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


def create_job_inputs(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> tuple[str, Path, Path, Path]:
    job_id = next_job_id()
    job_root = ensure_directory(jobs_root() / job_id)
    input_path = job_root / f"input-{safe_input_name(corpus_name)}"
    config_path = job_root / "request-config.json"
    input_path.write_text(str(corpus_text or ""), encoding="utf-8")
    write_json_file(config_path, config)
    return job_id, job_root, input_path, config_path


def start_analysis(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> dict[str, str]:
    reserve_analysis_slot(corpus_name)
    try:
        job_id, job_root, input_path, config_path = create_job_inputs(corpus_name, corpus_text, config)
        process = subprocess.Popen(
            [
                sys.executable,
                str(PROJECT_ROOT / "backend" / "run_job.py"),
                "--input",
                str(input_path),
                "--config",
                str(config_path),
                "--output-root",
                str(jobs_root()),
                "--job-id",
                job_id,
            ],
            cwd=PROJECT_ROOT,
            env=build_command_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        activate_analysis_lock(job_id, process.pid, corpus_name)
    except Exception:
        clear_analysis_lock()
        raise
    return {
        "jobId": job_id,
        "statusFile": str(job_root / "status.json"),
        "resultsFile": str(job_root / "results.json"),
    }


def _artifact_download_url(path: Path) -> str:
    from urllib.parse import quote

    return f"/api/local-file?path={quote(str(path.resolve()))}"


def _augment_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for artifact in artifacts:
        item = dict(artifact)
        absolute_path = Path(str(item.get("absolutePath") or "")).resolve()
        item["downloadUrl"] = _artifact_download_url(absolute_path)
        out.append(item)
    return out


def _job_result_payload(job_root: Path) -> dict[str, Any] | None:
    results_file = job_root / "results.json"
    if not results_file.exists():
        return None
    payload = read_json_file(results_file)
    artifacts = payload.get("artifacts") or []
    payload["artifacts"] = _augment_artifacts([dict(item) for item in artifacts])
    return payload


def read_analysis_status(job_id: str) -> dict[str, Any]:
    cleaned_job_id = str(job_id or "").strip()
    if not cleaned_job_id:
        raise ValueError("Identifiant de job manquant.")

    job_root = jobs_root() / cleaned_job_id
    status_file = job_root / "status.json"
    stdout_log = job_root / "stdout.log"
    stderr_log = job_root / "stderr.log"

    if not status_file.exists():
        return {
            "jobId": cleaned_job_id,
            "state": "queued",
            "progress": 0,
            "message": "Initialisation du job CHD Rainette.",
            "logs": [],
        }

    payload = read_json_file(status_file)
    payload["jobId"] = cleaned_job_id
    payload["stdoutLog"] = str(stdout_log.resolve()) if stdout_log.exists() else ""
    payload["stderrLog"] = str(stderr_log.resolve()) if stderr_log.exists() else ""

    result_payload = _job_result_payload(job_root)
    if result_payload is not None:
        payload["result"] = result_payload

    state = str(payload.get("state") or "").strip().lower()
    if state in TERMINAL_JOB_STATES:
        clear_analysis_lock(expected_job_id=cleaned_job_id)

    return payload


def _job_output_dir(job_id: str) -> Path:
    output_dir = jobs_root() / str(job_id or "").strip() / "output"
    if not output_dir.exists():
        raise FileNotFoundError("Dossier de sortie du job introuvable.")
    return output_dir


def _job_bundle_path(job_id: str) -> Path:
    bundle_path = _job_output_dir(job_id) / "analysis_bundle.rds"
    if not bundle_path.exists():
        raise FileNotFoundError("Bundle Rainette introuvable pour ce job.")
    return bundle_path


def _write_params_file(job_root: Path, prefix: str, params: dict[str, Any]) -> Path:
    params_dir = ensure_directory(job_root / "explorer-params")
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    path = params_dir / f"{prefix}-{digest}.json"
    if not path.exists():
        write_json_file(path, params)
    return path


def render_explorer_plot(job_id: str, params: dict[str, Any]) -> Path:
    cleaned_job_id = str(job_id or "").strip()
    if not cleaned_job_id:
        raise ValueError("Identifiant de job manquant.")

    job_root = jobs_root() / cleaned_job_id
    bundle_path = _job_bundle_path(cleaned_job_id)
    params_path = _write_params_file(job_root, "plot", params)
    cache_root = ensure_directory(job_root / "explorer-cache")
    output_png = cache_root / f"plot-{params_path.stem}.png"

    if output_png.exists():
        return output_png

    process = subprocess.run(
        [
            resolve_rscript(),
            str(PROJECT_ROOT / "backend" / "render_explorer.R"),
            "plot",
            str(bundle_path),
            str(params_path),
            str(output_png),
        ],
        cwd=PROJECT_ROOT,
        env=build_command_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0 or not output_png.exists():
        message = ""
        for text in (process.stderr, process.stdout):
            for line in reversed((text or "").splitlines()):
                if line.strip():
                    message = line.strip()
                    break
            if message:
                break
        raise RuntimeError(message or "Impossible de générer rainette_plot().")
    return output_png


def render_explorer_docs(job_id: str, params: dict[str, Any]) -> dict[str, Any]:
    cleaned_job_id = str(job_id or "").strip()
    if not cleaned_job_id:
        raise ValueError("Identifiant de job manquant.")

    job_root = jobs_root() / cleaned_job_id
    bundle_path = _job_bundle_path(cleaned_job_id)
    params_path = _write_params_file(job_root, "docs", params)

    process = subprocess.run(
        [
            resolve_rscript(),
            str(PROJECT_ROOT / "backend" / "render_explorer.R"),
            "docs",
            str(bundle_path),
            str(params_path),
        ],
        cwd=PROJECT_ROOT,
        env=build_command_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "Impossible de générer les documents Rainette.")
    payload = json.loads(process.stdout or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("Réponse explorer/docs invalide.")
    return payload


def render_explorer_code(job_id: str, params: dict[str, Any]) -> dict[str, Any]:
    cleaned_job_id = str(job_id or "").strip()
    if not cleaned_job_id:
        raise ValueError("Identifiant de job manquant.")

    job_root = jobs_root() / cleaned_job_id
    bundle_path = _job_bundle_path(cleaned_job_id)
    params_path = _write_params_file(job_root, "code", params)

    process = subprocess.run(
        [
            resolve_rscript(),
            str(PROJECT_ROOT / "backend" / "render_explorer.R"),
            "code",
            str(bundle_path),
            str(params_path),
        ],
        cwd=PROJECT_ROOT,
        env=build_command_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip() or "Impossible de générer le code Rainette.")
    payload = json.loads(process.stdout or "{}")
    if not isinstance(payload, dict):
        raise RuntimeError("Réponse explorer/code invalide.")
    return payload


def mime_type_for_path(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def resolve_local_file_path(path: str) -> Path:
    requested = Path(str(path or "").strip()).expanduser()
    if not requested.is_absolute():
        raise ValueError("Le chemin doit être absolu.")
    resolved = requested.resolve()
    root = app_data_root().resolve()
    if root not in resolved.parents and resolved != root:
        raise PermissionError("Le fichier demandé doit rester dans l'espace applicatif du VPS.")
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError("Fichier introuvable.")
    return resolved
