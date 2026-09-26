from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APP_DATA_ROOT = Path(os.environ.get("TMPDIR", "/tmp")) / "iramuteq-lite-data"
ANALYSIS_LOCK_FILENAME = "active-analysis.json"
ANALYSIS_LOCK_STALE_SECONDS = 300
TERMINAL_JOB_STATES = {"cancelled", "completed", "done", "error", "failed", "success", "succeeded"}
TEXT_EXTENSIONS = {
    ".csv",
    ".html",
    ".htm",
    ".json",
    ".md",
    ".svg",
    ".txt",
    ".xml",
}


def env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def app_data_root() -> Path:
    configured = os.environ.get("IRAMUTEQ_APP_DATA_DIR", "").strip()
    base_path = Path(configured).expanduser() if configured else DEFAULT_APP_DATA_ROOT
    return ensure_directory(base_path.resolve())


def frontend_root() -> Path:
    return PROJECT_ROOT / "frontend"


def jobs_root() -> Path:
    return ensure_directory(app_data_root() / "jobs")


def downloads_root() -> Path:
    return ensure_directory(app_data_root() / "downloads")


def mplconfig_dir() -> Path:
    return ensure_directory(app_data_root() / "mplconfig")


def r_library_dir() -> Path:
    explicit = os.environ.get("IRAMUTEQ_R_LIBS_USER", "").strip()
    if explicit:
        return ensure_directory(Path(explicit).expanduser().resolve())
    return ensure_directory(app_data_root() / "r-library")


def python_site_dir() -> Path:
    explicit = os.environ.get("IRAMUTEQ_PYTHON_SITE_DIR", "").strip()
    if explicit:
        return ensure_directory(Path(explicit).expanduser().resolve())
    return ensure_directory(app_data_root() / "python-site-packages")


def annotation_dictionary_path() -> Path:
    explicit = os.environ.get("IRAMUTEQ_ADD_EXPRESSION_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return app_data_root() / "dictionnaires" / "add_expression_fr.csv"


def next_job_id(prefix: str = "web") -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


def analysis_lock_path() -> Path:
    return app_data_root() / ANALYSIS_LOCK_FILENAME


def write_json_file(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


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


def active_analysis_error_message(lock_payload: dict[str, Any]) -> str:
    job_id = str(lock_payload.get("job_id") or "").strip()
    corpus_name = str(lock_payload.get("corpus_name") or "").strip()
    details = []
    if corpus_name:
        details.append(f"corpus {corpus_name}")
    if job_id:
        details.append(f"job {job_id}")
    suffix = f" ({', '.join(details)})" if details else ""
    return (
        "Une analyse est deja en cours sur le serveur pour IRaMuTeQ Lite"
        f"{suffix}. Attendez sa fin avant d'en lancer une autre."
    )


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
        raise RuntimeError(active_analysis_error_message(active_lock))

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
            raise RuntimeError(active_analysis_error_message(active_lock)) from error
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


def safe_input_name(name: str) -> str:
    return (
        Path(str(name or "").strip() or "corpus.txt")
        .name
        .replace("\x00", "")
        or "corpus.txt"
    )


def safe_archive_name(name: str) -> str:
    sanitized = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in str(name or "").strip()
    ).strip("-")
    if not sanitized:
        return "resultats.zip"
    if sanitized.endswith(".zip"):
        return sanitized
    return f"{sanitized}.zip"


def safe_text_name(name: str) -> str:
    sanitized = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in str(name or "").strip()
    ).strip("-")
    if not sanitized:
        return "sous-corpus.txt"
    if sanitized.endswith(".txt"):
        return sanitized
    return f"{sanitized}.txt"


def safe_png_name(name: str) -> str:
    sanitized = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in str(name or "").strip()
    ).strip("-")
    if not sanitized:
        return "chi2-classes.png"
    if sanitized.endswith(".png"):
        return sanitized
    return f"{sanitized}.png"


def safe_csv_name(name: str) -> str:
    sanitized = "".join(
        character if character.isalnum() or character in "._-" else "-"
        for character in str(name or "").strip()
    ).strip("-")
    if not sanitized:
        return "add_expression_fr.csv"
    if sanitized.endswith(".csv"):
        return sanitized
    return f"{sanitized}.csv"


def next_available_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem or "fichier"
    suffix = Path(filename).suffix
    for index in range(1, 10_000):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    return directory / filename


def resolve_binary_path(env_var: str, fallback_name: str, absolute_candidates: list[str]) -> str:
    explicit = os.environ.get(env_var, "").strip()
    if explicit:
        return explicit

    discovered = shutil.which(fallback_name)
    if discovered:
        return discovered

    for candidate in absolute_candidates:
        path = Path(candidate)
        if path.is_file():
            return str(path)

    return fallback_name


def resolve_rscript() -> str:
    return resolve_binary_path(
        "IRAMUTEQ_RSCRIPT",
        "Rscript",
        [
            "/usr/local/bin/Rscript",
            "/opt/homebrew/bin/Rscript",
            "/Library/Frameworks/R.framework/Resources/bin/Rscript",
            "/usr/bin/Rscript",
        ],
    )


def build_command_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    env.setdefault("RGL_USE_NULL", "TRUE")
    env["IRAMUTEQ_APP_DATA_DIR"] = str(app_data_root())
    env["IRAMUTEQ_R_LIBS_USER"] = str(r_library_dir())
    env["IRAMUTEQ_PYTHON_SITE_DIR"] = str(python_site_dir())
    env["MPLCONFIGDIR"] = str(mplconfig_dir())
    current_pythonpath = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = (
        env["IRAMUTEQ_PYTHON_SITE_DIR"]
        if not current_pythonpath
        else env["IRAMUTEQ_PYTHON_SITE_DIR"] + os.pathsep + current_pythonpath
    )
    if extra:
        env.update({key: str(value) for key, value in extra.items() if value is not None})
    return env


def read_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def try_parse_json(text: str) -> dict[str, Any] | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def last_non_empty_line(*texts: str) -> str:
    for text in texts:
        for line in reversed(str(text or "").splitlines()):
            cleaned = line.strip()
            if cleaned:
                return cleaned
    return ""


def process_failure_message(process: subprocess.CompletedProcess[str], fallback: str) -> str:
    return last_non_empty_line(process.stderr, process.stdout) or fallback


def missing_artifacts_message(
    output_dir: Path,
    *,
    job_id: str | None = None,
    status_file: Path | None = None,
    results_file: Path | None = None,
    stdout_log: Path | None = None,
    stderr_log: Path | None = None,
) -> str:
    lines = [
        "L'analyse s'est terminee sans generer d'exports lisibles pour l'interface.",
        f"Dossier d'exports : {output_dir}",
    ]
    if job_id:
        lines.append(f"Job : {job_id}")
    if status_file:
        lines.append(f"Status : {status_file}")
    if results_file:
        lines.append(f"Results : {results_file}")
    if stdout_log:
        lines.append(f"Stdout : {stdout_log}")
    if stderr_log:
        lines.append(f"Stderr : {stderr_log}")
    lines.append(
        "Sur le VPS, cela indique en general un probleme de generation des fichiers cote R/Python, meme si le job a atteint sa fin."
    )
    return "\n".join(lines)


def mime_type_for_path(path: Path) -> str:
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def is_text_path(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTENSIONS


def collect_artifact_files(output_dir: Path) -> list[dict[str, str]]:
    root = output_dir.resolve()
    artifacts: list[dict[str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        relative_path = path.relative_to(root).as_posix()
        mime_type = mime_type_for_path(path)
        if is_text_path(path):
            data = path.read_text(encoding="utf-8", errors="replace")
            encoding = "utf8"
        else:
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            encoding = "base64"

        artifacts.append(
            {
                "relativePath": relative_path,
                "mimeType": mime_type,
                "encoding": encoding,
                "data": data,
            }
        )
    return artifacts


def resolve_help_path(relative_path: str) -> Path:
    requested = str(relative_path or "").replace("\\", "/").strip()
    if not requested:
        raise ValueError("Le chemin d'aide est vide.")
    if requested.startswith("/") or ".." in Path(requested).parts:
        raise ValueError("Le chemin d'aide doit rester relatif au dépôt.")
    if requested.startswith("images/"):
        return PROJECT_ROOT / "images" / requested.removeprefix("images/")
    return PROJECT_ROOT / "help" / requested


def create_job_inputs(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> tuple[str, Path, Path, Path]:
    job_id = next_job_id()
    job_root = ensure_directory(jobs_root() / job_id)
    input_path = job_root / f"input-{safe_input_name(corpus_name)}"
    config_path = job_root / "request-config.json"
    input_path.write_text(str(corpus_text or ""), encoding="utf-8")
    write_json_file(config_path, config)
    return job_id, job_root, input_path, config_path


def backend_runner_command(subcommand: str, input_path: Path, config_path: Path, job_id: str) -> list[str]:
    return [
        sys.executable,
        str(PROJECT_ROOT / "backend" / "run_job.py"),
        subcommand,
        "--input",
        str(input_path),
        "--config",
        str(config_path),
        "--output-root",
        str(jobs_root()),
        "--job-id",
        job_id,
    ]


def bootstrap_dependencies() -> dict[str, Any]:
    auto_install = env_truthy("IRAMUTEQ_BOOTSTRAP_AUTO_INSTALL")
    command = [sys.executable, str(PROJECT_ROOT / "backend" / "run_job.py"), "bootstrap"]
    if not auto_install:
        command.append("--check-only")

    process = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=build_command_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = try_parse_json(process.stdout)

    if payload is None:
        return {
            "success": False,
            "message": process_failure_message(process, "Bootstrap des dépendances impossible."),
            "installedNow": [],
            "missingAfter": [],
            "optionalMissing": [],
            "library": None,
            "rscript": resolve_rscript(),
            "python": sys.executable,
        }

    installed_now = [str(item) for item in payload.get("installed_now") or []]
    missing_after = [str(item) for item in payload.get("missing_after") or []]
    optional_missing: list[str] = []
    blocking_missing = missing_after
    blocking_labels = [
        item.split(":", 1)[1] if str(item).startswith("python:") else str(item)
        for item in blocking_missing
    ]
    optional_labels = [item.split(":", 1)[1] for item in optional_missing]

    success = bool(payload.get("success")) or not blocking_missing
    original_message = str(payload.get("message") or "").strip()
    message = original_message
    if success and not message:
        if installed_now:
            message = f"Dépendances prêtes : {', '.join(installed_now)}"
        else:
            message = "Dépendances R/Python déjà disponibles."
    elif not success and blocking_labels:
        message = f"Dépendances requises encore manquantes : {', '.join(blocking_labels)}."
    elif not success and not message:
        message = "Certaines dépendances requises restent manquantes."

    return {
        "success": success,
        "message": message,
        "detailsMessage": original_message if original_message and original_message != message else "",
        "installedNow": installed_now,
        "missingAfter": blocking_missing,
        "blockingMessage": message if not success else "",
        "optionalMissing": optional_missing,
        "optionalMessage": "",
        "library": payload.get("library"),
        "rscript": payload.get("rscript") or resolve_rscript(),
        "python": payload.get("python") or sys.executable,
    }


def run_python_analysis(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> dict[str, Any]:
    job_id, _job_root, input_path, config_path = create_job_inputs(corpus_name, corpus_text, config)
    process = subprocess.run(
        backend_runner_command("run", input_path, config_path, job_id),
        cwd=PROJECT_ROOT,
        env=build_command_env({"IRAMUTEQ_ADD_EXPRESSION_PATH": str(annotation_dictionary_path())}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = try_parse_json(process.stdout)
    if payload is None:
        raise RuntimeError(process_failure_message(process, "Le job Python n'a pas renvoyé de JSON lisible."))
    if not process.returncode == 0 or not payload.get("success"):
        message = str(payload.get("message") or "").strip() or process_failure_message(
            process,
            "Le job Python a échoué.",
        )
        logs = payload.get("logs") or []
        if logs:
            message = "\n".join([message, *[str(item) for item in logs if item]])
        raise RuntimeError(message)

    output_dir = str(payload.get("output_dir") or "").strip()
    if not output_dir:
        raise RuntimeError("Le job Python n'a pas renvoyé de dossier d'exports.")

    output_dir_path = Path(output_dir).resolve()
    artifact_files = collect_artifact_files(output_dir_path) if output_dir_path.is_dir() else []
    if not artifact_files:
        raise RuntimeError(
            missing_artifacts_message(
                output_dir_path,
                job_id=str(payload.get("job_id") or job_id),
                status_file=Path(str(payload.get("status_file") or "")) if payload.get("status_file") else None,
                results_file=job_root / "results.json",
                stdout_log=Path(str(payload.get("stdout_log") or "")) if payload.get("stdout_log") else None,
                stderr_log=Path(str(payload.get("stderr_log") or "")) if payload.get("stderr_log") else None,
            )
        )
    return {
        "success": True,
        "jobId": str(payload.get("job_id") or job_id),
        "outputDir": str(output_dir_path),
        "summary": payload.get("summary"),
        "logs": payload.get("logs") or [],
        "files": artifact_files,
        "statusFile": payload.get("status_file"),
        "stdoutLog": payload.get("stdout_log"),
        "stderrLog": payload.get("stderr_log"),
    }


def start_python_analysis(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> dict[str, str]:
    reserve_analysis_slot(corpus_name)
    try:
        job_id, job_root, input_path, config_path = create_job_inputs(corpus_name, corpus_text, config)
        process = subprocess.Popen(
            backend_runner_command("run", input_path, config_path, job_id),
            cwd=PROJECT_ROOT,
            env=build_command_env({"IRAMUTEQ_ADD_EXPRESSION_PATH": str(annotation_dictionary_path())}),
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


def read_python_analysis_status(job_id: str) -> dict[str, Any]:
    job_root = jobs_root() / str(job_id or "").strip()
    if not str(job_id or "").strip():
        raise ValueError("Identifiant de job manquant.")

    status_file = job_root / "status.json"
    results_file = job_root / "results.json"
    stdout_log = job_root / "stdout.log"
    stderr_log = job_root / "stderr.log"

    if not status_file.exists():
        return {
            "jobId": job_id,
            "state": "queued",
            "progress": 0,
            "message": "Initialisation du job.",
            "logs": [],
            "completed": False,
            "success": False,
            "outputDir": None,
            "summary": None,
            "files": [],
            "statusFile": str(status_file),
            "resultsFile": str(results_file),
            "stdoutLog": str(stdout_log),
            "stderrLog": str(stderr_log),
        }

    status = read_json_file(status_file)
    state = str(status.get("state") or "running")
    progress = int(status.get("progress") or 0)
    message = str(status.get("message") or "")
    logs = [str(item) for item in status.get("logs") or [] if str(item).strip()]

    if not results_file.exists():
        return {
            "jobId": job_id,
            "state": state,
            "progress": progress,
            "message": message,
            "logs": logs,
            "completed": False,
            "success": False,
            "outputDir": None,
            "summary": None,
            "files": [],
            "statusFile": str(status_file),
            "resultsFile": str(results_file),
            "stdoutLog": str(stdout_log),
            "stderrLog": str(stderr_log),
        }

    result_payload = read_json_file(results_file)
    success = bool(result_payload.get("success"))
    output_dir = result_payload.get("output_dir")
    files: list[dict[str, str]] = []
    if success and output_dir:
        output_dir_path = Path(str(output_dir)).resolve()
        if output_dir_path.is_dir():
            files = collect_artifact_files(output_dir_path)
        if not files:
            success = False
            message = missing_artifacts_message(
                output_dir_path,
                job_id=str(result_payload.get("job_id") or job_id),
                status_file=Path(str(result_payload.get("status_file") or status_file)),
                results_file=results_file,
                stdout_log=Path(str(result_payload.get("stdout_log") or stdout_log)),
                stderr_log=Path(str(result_payload.get("stderr_log") or stderr_log)),
            )
            if message not in logs:
                logs = [*logs, message]

    clear_analysis_lock(expected_job_id=job_id)

    return {
        "jobId": job_id,
        "state": state,
        "progress": max(progress, 100),
        "message": str(result_payload.get("message") or message),
        "logs": [str(item) for item in result_payload.get("logs") or logs if str(item).strip()],
        "completed": True,
        "success": success,
        "outputDir": str(Path(output_dir).resolve()) if output_dir else None,
        "summary": result_payload.get("summary"),
        "files": files,
        "statusFile": str(result_payload.get("status_file") or status_file),
        "resultsFile": str(results_file),
        "stdoutLog": str(result_payload.get("stdout_log") or stdout_log),
        "stderrLog": str(result_payload.get("stderr_log") or stderr_log),
    }


def preview_simi_terms(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> dict[str, Any]:
    job_id, _job_root, input_path, config_path = create_job_inputs(corpus_name, corpus_text, config)
    process = subprocess.run(
        backend_runner_command("preview-simi-terms", input_path, config_path, job_id),
        cwd=PROJECT_ROOT,
        env=build_command_env({"IRAMUTEQ_ADD_EXPRESSION_PATH": str(annotation_dictionary_path())}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = try_parse_json(process.stdout)
    if payload is None:
        raise RuntimeError(
            process_failure_message(process, "La prévisualisation des termes de similitudes a échoué.")
        )
    if not process.returncode == 0 or not payload.get("success"):
        message = str(payload.get("message") or "").strip() or process_failure_message(
            process,
            "La prévisualisation des termes de similitudes a échoué.",
        )
        logs = payload.get("logs") or []
        if logs:
            message = "\n".join([message, *[str(item) for item in logs if item]])
        raise RuntimeError(message)

    return {
        "success": True,
        "jobId": str(payload.get("job_id") or job_id),
        "terms": payload.get("terms") or [],
        "orderedTerms": payload.get("ordered_terms") or [],
        "logs": payload.get("logs") or [],
        "statusFile": payload.get("status_file"),
        "stdoutLog": payload.get("stdout_log"),
        "stderrLog": payload.get("stderr_log"),
    }


def run_chd_action(output_dir: str, action: str, term: str, class_label: str | None = None) -> dict[str, Any]:
    output_dir_path = Path(str(output_dir or "").strip()).expanduser().resolve()
    if not output_dir_path.is_dir():
        raise FileNotFoundError("Le dossier d'exports est introuvable pour cette action CHD.")

    safe_action = str(action or "").strip()
    if safe_action not in {"chi2-class", "segments-class", "segments-all-classes"}:
        raise ValueError("Action CHD non reconnue.")

    safe_term = str(term or "").strip()
    if not safe_term:
        raise ValueError("La forme sélectionnée est vide.")

    command = [
        resolve_rscript(),
        "--vanilla",
        str(PROJECT_ROOT / "backend" / "r" / "actions.R"),
        "--output-dir",
        str(output_dir_path),
        "--action",
        safe_action,
        "--term",
        safe_term,
    ]
    if class_label and str(class_label).strip():
        command.extend(["--class", str(class_label).strip()])

    process = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=build_command_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    payload = try_parse_json(process.stdout)
    if payload is None:
        raise RuntimeError(process_failure_message(process, "La réponse R est illisible."))
    if not process.returncode == 0 or not payload.get("success"):
        message = str(payload.get("message") or "").strip()
        if not message:
            logs = payload.get("logs") or []
            if logs:
                message = str(logs[-1])
        raise RuntimeError(message or process_failure_message(process, "L'action CHD a échoué."))
    return payload


def classify_archive_entry(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if normalized.endswith((".png", ".jpg", ".jpeg")):
        return "graphiques"
    if normalized.endswith(".csv"):
        return "csv"
    if normalized.endswith((".html", ".htm")):
        return "html"
    if normalized.endswith(".txt"):
        return "texte"
    if normalized.endswith(".json"):
        return "json"
    return "autres"


def build_archive_manifest(entries: list[str]) -> str:
    lines = [
        "Archive des resultats IRAMUTEQ Lite",
        "",
        f"Nombre de fichiers: {len(entries)}",
        "",
    ]
    for section in ["csv", "graphiques", "html", "texte", "json", "autres"]:
        section_entries = [entry for entry in entries if classify_archive_entry(entry) == section]
        if not section_entries:
            continue
        lines.append(f"[{section}]")
        lines.extend(f"- {entry}" for entry in section_entries)
        lines.append("")
    return "\n".join(lines)


def build_results_archive(output_dir: Path) -> bytes:
    root_prefix = output_dir.name or "exports"
    buffer = BytesIO()
    archive_paths: list[str] = []

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file():
                continue
            relative_path = path.relative_to(output_dir).as_posix()
            archive_path = f"{root_prefix}/{relative_path}"
            archive.write(path, archive_path)
            archive_paths.append(archive_path)

        archive.writestr(
            f"{root_prefix}/contenu_archive.txt",
            build_archive_manifest(archive_paths),
        )

    return buffer.getvalue()


def download_results_archive(output_dir: str, archive_name: str | None = None) -> dict[str, str]:
    output_dir_path = Path(str(output_dir or "").strip()).expanduser().resolve()
    if not output_dir_path.is_dir():
        raise FileNotFoundError("Le dossier de résultats à télécharger est introuvable.")

    filename = safe_archive_name(archive_name or output_dir_path.name or "resultats.zip")
    payload = build_results_archive(output_dir_path)
    return {
        "filename": filename,
        "mimeType": "application/zip",
        "encoding": "base64",
        "data": base64.b64encode(payload).decode("ascii"),
    }


def save_results_archive(output_dir: str, archive_name: str | None = None) -> dict[str, str]:
    output_dir_path = Path(str(output_dir or "").strip()).expanduser().resolve()
    if not output_dir_path.is_dir():
        raise FileNotFoundError("Le dossier de résultats à télécharger est introuvable.")

    filename = safe_archive_name(archive_name or output_dir_path.name or "resultats.zip")
    target_path = next_available_path(downloads_root(), filename)
    target_path.write_bytes(build_results_archive(output_dir_path))
    return {
        "filename": target_path.name,
        "savedPath": str(target_path),
    }


def save_text_export(content: str, filename: str | None = None) -> dict[str, str]:
    target_path = next_available_path(downloads_root(), safe_text_name(filename or "sous-corpus.txt"))
    target_path.write_text(str(content or ""), encoding="utf-8")
    return {
        "filename": target_path.name,
        "savedPath": str(target_path),
    }


def save_png_export(data: str, filename: str | None = None) -> dict[str, str]:
    target_path = next_available_path(downloads_root(), safe_png_name(filename or "chi2-classes.png"))
    target_path.write_bytes(base64.b64decode(str(data or "").encode("ascii")))
    return {
        "filename": target_path.name,
        "savedPath": str(target_path),
    }


def collect_output_artifacts(output_dir: str) -> dict[str, Any]:
    output_dir_path = Path(str(output_dir or "").strip()).expanduser().resolve()
    if not output_dir_path.is_dir():
        raise FileNotFoundError("Le dossier d'exports est introuvable.")
    return {
        "outputDir": str(output_dir_path),
        "files": collect_artifact_files(output_dir_path),
    }


def read_help_file(relative_path: str) -> dict[str, str]:
    path = resolve_help_path(relative_path)
    if not path.is_file():
        raise FileNotFoundError(f"Le fichier d'aide est introuvable : {relative_path}")

    if is_text_path(path):
        encoding = "utf8"
        data = path.read_text(encoding="utf-8", errors="replace")
    else:
        encoding = "base64"
        data = base64.b64encode(path.read_bytes()).decode("ascii")

    return {
        "relativePath": str(relative_path),
        "mimeType": mime_type_for_path(path),
        "encoding": encoding,
        "data": data,
    }


def read_annotation_dictionary_file() -> dict[str, Any]:
    path = annotation_dictionary_path()
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "content": "",
        }
    return {
        "path": str(path),
        "exists": True,
        "content": path.read_text(encoding="utf-8", errors="replace"),
    }


def write_annotation_dictionary_file(content: str) -> dict[str, Any]:
    path = annotation_dictionary_path()
    ensure_directory(path.parent)
    path.write_text(str(content or ""), encoding="utf-8")
    entries_count = sum(1 for line in str(content or "").splitlines()[1:] if line.strip())
    return {
        "path": str(path),
        "entriesCount": entries_count,
    }


def reset_annotation_dictionary_file() -> dict[str, Any]:
    path = annotation_dictionary_path()
    removed = False
    if path.exists():
        path.unlink()
        removed = True
    return {
        "path": str(path),
        "removed": removed,
    }


def save_annotation_dictionary_export(content: str, filename: str | None = None) -> dict[str, str]:
    target_path = next_available_path(downloads_root(), safe_csv_name(filename or "add_expression_fr.csv"))
    target_path.write_text(str(content or ""), encoding="utf-8")
    return {
        "filename": target_path.name,
        "savedPath": str(target_path),
    }


def path_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_local_file_path(raw_path: str) -> Path:
    safe_path = str(raw_path or "").strip()
    if not safe_path:
        raise ValueError("Chemin local vide.")

    candidate = Path(safe_path).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve()

    allowed_roots = [PROJECT_ROOT.resolve(), app_data_root().resolve()]
    if not any(path_within(resolved, root) for root in allowed_roots):
        raise PermissionError("Accès refusé en dehors des répertoires autorisés.")
    if not resolved.is_file():
        raise FileNotFoundError("Le fichier demandé est introuvable.")
    return resolved
