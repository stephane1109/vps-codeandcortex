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
OPTIONAL_PYTHON_DEPENDENCIES = {
    "cv2",
    "faster_whisper",
    "imageio_ffmpeg",
    "librosa",
    "mediapipe",
    "yt_dlp",
}
ALLOWED_MULTIMODAL_SCRIPTS = {
    "alignement.py",
    "audio.py",
    "comparaison_ab.py",
    "mouvements.py",
    "noeuds.py",
    "synchronisation.py",
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


def multimodal_inputs_root() -> Path:
    return ensure_directory(app_data_root() / "multimodale-inputs")


def multimodal_outputs_root() -> Path:
    return ensure_directory(app_data_root() / "multimodale-outputs")


def mplconfig_dir() -> Path:
    return ensure_directory(app_data_root() / "mplconfig")


def annotation_dictionary_path() -> Path:
    explicit = os.environ.get("IRAMUTEQ_ADD_EXPRESSION_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return app_data_root() / "dictionnaires" / "add_expression_fr.csv"


def next_job_id(prefix: str = "web") -> str:
    return f"{prefix}-{int(time.time() * 1000)}"


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
    env["MPLCONFIGDIR"] = str(mplconfig_dir())
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


def is_optional_missing(item: Any) -> bool:
    value = str(item or "").strip()
    if not value.startswith("python:"):
        return False
    return value.split(":", 1)[1] in OPTIONAL_PYTHON_DEPENDENCIES


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
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
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
    optional_missing = [item for item in missing_after if is_optional_missing(item)]
    blocking_missing = [item for item in missing_after if item not in optional_missing]

    success = bool(payload.get("success")) or not blocking_missing
    message = str(payload.get("message") or "").strip()
    if success and optional_missing:
        optional_names = ", ".join(item.split(":", 1)[1] for item in optional_missing)
        prefix = f"{message} " if message else ""
        message = f"{prefix}L'application texte est prête. Dépendances multimodales optionnelles absentes : {optional_names}."
    elif success and not message:
        if installed_now:
            message = f"Dépendances prêtes : {', '.join(installed_now)}"
        else:
            message = "Dépendances R/Python déjà disponibles."
    elif not success and not message:
        message = "Certaines dépendances restent manquantes."

    return {
        "success": success,
        "message": message,
        "installedNow": installed_now,
        "missingAfter": blocking_missing,
        "optionalMissing": optional_missing,
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
    return {
        "success": True,
        "jobId": str(payload.get("job_id") or job_id),
        "outputDir": str(output_dir_path),
        "summary": payload.get("summary"),
        "logs": payload.get("logs") or [],
        "files": collect_artifact_files(output_dir_path) if output_dir_path.is_dir() else [],
        "statusFile": payload.get("status_file"),
        "stdoutLog": payload.get("stdout_log"),
        "stderrLog": payload.get("stderr_log"),
    }


def start_python_analysis(corpus_name: str, corpus_text: str, config: dict[str, Any]) -> dict[str, str]:
    job_id, job_root, input_path, config_path = create_job_inputs(corpus_name, corpus_text, config)
    subprocess.Popen(
        backend_runner_command("run", input_path, config_path, job_id),
        cwd=PROJECT_ROOT,
        env=build_command_env({"IRAMUTEQ_ADD_EXPRESSION_PATH": str(annotation_dictionary_path())}),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
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


def persist_multimodal_input(slot: str, filename: str, data: str) -> dict[str, Any]:
    normalized_slot = str(slot or "").strip()
    if normalized_slot not in {"audio", "cookies", "segments", "video"}:
        raise ValueError("Type de fichier multimodal non autorisé.")

    base_dir = ensure_directory(multimodal_inputs_root() / normalized_slot)
    safe_name = safe_input_name(filename)
    target_path = base_dir / f"{next_job_id()}-{safe_name}"
    payload = base64.b64decode(str(data or "").encode("ascii"))
    target_path.write_bytes(payload)
    return {
        "savedPath": str(target_path),
        "filename": safe_name,
        "bytesWritten": len(payload),
    }


def persist_multimodal_image_batch(files: list[dict[str, Any]]) -> dict[str, Any]:
    if not files:
        raise ValueError("Aucune image à préparer.")

    batch_dir = ensure_directory(multimodal_inputs_root() / "images" / next_job_id())
    saved_paths: list[str] = []
    for index, item in enumerate(files, start=1):
        safe_name = f"{index:04d}_{safe_input_name(str(item.get('filename') or 'image.png'))}"
        target_path = batch_dir / safe_name
        target_path.write_bytes(base64.b64decode(str(item.get("data") or "").encode("ascii")))
        saved_paths.append(str(target_path))

    return {
        "savedDir": str(batch_dir),
        "savedPaths": saved_paths,
        "fileCount": len(saved_paths),
    }


def pick_output_directory() -> str:
    target_dir = ensure_directory(multimodal_outputs_root() / next_job_id("sortie"))
    return str(target_dir)


def resolve_runtime_output_dir(output_dir: str) -> Path:
    raw_path = str(output_dir or "").strip()
    if not raw_path:
        raise ValueError("Le dossier de sortie est vide.")
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return candidate.resolve()


def run_multimodal_script(script_name: str, args: list[str], output_dir: str) -> dict[str, Any]:
    normalized_name = str(script_name or "").strip()
    if normalized_name not in ALLOWED_MULTIMODAL_SCRIPTS:
        raise ValueError("Script multimodal non autorisé.")

    script_path = PROJECT_ROOT / "multimodale" / normalized_name
    if not script_path.is_file():
        raise FileNotFoundError(f"Script multimodal introuvable : multimodale/{normalized_name}")

    process = subprocess.run(
        [sys.executable, str(script_path), *[str(item) for item in args or []]],
        cwd=PROJECT_ROOT,
        env=build_command_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stdout = process.stdout or ""
    stderr = process.stderr or ""
    if process.returncode != 0:
        raise RuntimeError(
            f"Le script multimodal {normalized_name} a échoué.\nstdout={stdout.strip()}\nstderr={stderr.strip()}"
        )

    output_dir_path = resolve_runtime_output_dir(output_dir)
    files = collect_artifact_files(output_dir_path) if output_dir_path.is_dir() else []
    logs = [
        line.strip()
        for line in [*stdout.splitlines(), *stderr.splitlines()]
        if line.strip()
    ]
    return {
        "success": True,
        "outputDir": str(output_dir_path),
        "logs": logs,
        "files": files,
        "stdout": stdout,
        "stderr": stderr,
    }


def read_multimodal_progress(output_dir: str, analysis_key: str) -> dict[str, Any]:
    output_dir_path = resolve_runtime_output_dir(output_dir)
    progress_path = output_dir_path / f"progression_{str(analysis_key or '').strip()}.json"
    if not progress_path.is_file():
        return {
            "exists": False,
            "progress": 0,
            "stage": "",
            "message": "",
            "payload": None,
        }

    payload = read_json_file(progress_path)
    return {
        "exists": True,
        "progress": max(0, min(100, int(payload.get("progress") or 0))),
        "stage": str(payload.get("stage") or ""),
        "message": str(payload.get("message") or ""),
        "payload": payload,
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
