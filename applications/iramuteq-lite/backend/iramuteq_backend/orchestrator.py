from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import uuid
import importlib.util
from importlib import metadata as importlib_metadata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_placeholder_message(message: str) -> bool:
    normalized = " ".join((message or "").split())
    return normalized in {
        "",
        "Job préparé par Python.",
        "Initialisation du job.",
        "Analyse en cours...",
        "Le job Python a échoué.",
    }


@dataclass
class JobPaths:
    repo_root: Path
    job_root: Path
    export_dir: Path
    config_file: Path
    status_file: Path
    results_file: Path
    stdout_log: Path
    stderr_log: Path


def repo_root_from_file() -> Path:
    return Path(__file__).resolve().parents[2]


def locate_rscript(explicit: str | None = None) -> str:
    if explicit:
        return explicit

    env_value = os.environ.get("IRAMUTEQ_RSCRIPT", "").strip()
    if env_value:
        return env_value

    discovered = shutil.which("Rscript")
    if discovered:
        return discovered

    common_candidates = [
        "/usr/local/bin/Rscript",
        "/opt/homebrew/bin/Rscript",
        "/Library/Frameworks/R.framework/Resources/bin/Rscript",
    ]
    for candidate in common_candidates:
        if Path(candidate).is_file():
            return candidate

    raise FileNotFoundError("Rscript introuvable. Definir IRAMUTEQ_RSCRIPT si necessaire.")


def prepare_job_paths(output_root: Path | None, job_id: str | None = None) -> JobPaths:
    repo_root = repo_root_from_file()
    base_root = output_root or (repo_root / "backend" / "jobs")
    current_job_id = job_id or uuid.uuid4().hex[:12]
    job_root = base_root / current_job_id
    export_dir = job_root / "exports"
    return JobPaths(
        repo_root=repo_root,
        job_root=job_root,
        export_dir=export_dir,
        config_file=job_root / "job-config.json",
        status_file=job_root / "status.json",
        results_file=job_root / "results.json",
        stdout_log=job_root / "stdout.log",
        stderr_log=job_root / "stderr.log",
    )


def initialize_status(paths: JobPaths, payload: dict[str, Any]) -> None:
    write_json(
        paths.status_file,
        {
            "job_id": paths.job_root.name,
            "state": "queued",
            "progress": 0,
            "message": "Job préparé par Python.",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "config": payload,
        },
    )


def finalize_failure(paths: JobPaths, message: str, returncode: int | None = None) -> dict[str, Any]:
    status = read_json(paths.status_file) if paths.status_file.exists() else {}
    status.update(
        {
            "state": "failed",
            "progress": status.get("progress", 0),
            "message": message,
            "updated_at": utc_now(),
        }
    )
    if returncode is not None:
        status["returncode"] = returncode
    write_json(paths.status_file, status)

    existing_results: dict[str, Any] = {}
    if paths.results_file.exists():
        try:
            existing_results = read_json(paths.results_file)
        except (json.JSONDecodeError, OSError, ValueError):
            existing_results = {}

    logs = existing_results.get("logs")
    if not isinstance(logs, list):
        logs = []

    payload = {
        "success": False,
        "job_id": paths.job_root.name,
        "message": message,
        "logs": logs,
        "status_file": str(paths.status_file),
        "stdout_log": str(paths.stdout_log),
        "stderr_log": str(paths.stderr_log),
    }
    write_json(paths.results_file, payload)
    return payload


def summarize_failure(process: subprocess.CompletedProcess[str], paths: JobPaths) -> str:
    if paths.results_file.exists():
        try:
            payload = read_json(paths.results_file)
            message = str(payload.get("message", "")).strip()
            if message and not is_placeholder_message(message):
                return message
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    if paths.status_file.exists():
        try:
            status = read_json(paths.status_file)
            message = str(status.get("message", "")).strip()
            if message and not is_placeholder_message(message):
                return message
        except (json.JSONDecodeError, OSError, ValueError):
            pass

    stdout_lines = [line.strip() for line in process.stdout.splitlines() if line.strip()]
    for line in reversed(stdout_lines):
        if "ERREUR:" in line:
            return line.split("ERREUR:", 1)[1].strip()

    stderr_lines = [line.strip() for line in process.stderr.splitlines() if line.strip()]
    filtered_stderr = [
        line
        for line in stderr_lines
        if "Setting LC_" not in line and "XType:" not in line
    ]
    if filtered_stderr:
        return filtered_stderr[-1]

    if stderr_lines:
        return stderr_lines[-1]

    return "Exécution R en échec."


def run_job(
    *,
    corpus_path: Path,
    config: dict[str, Any],
    output_root: Path | None = None,
    job_id: str | None = None,
    rscript_path: str | None = None,
) -> dict[str, Any]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus introuvable: {corpus_path}")

    paths = prepare_job_paths(output_root=output_root, job_id=job_id)
    paths.job_root.mkdir(parents=True, exist_ok=True)
    paths.export_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.config_file, config)
    initialize_status(paths, config)

    runner = paths.repo_root / "backend" / "r" / "run_iramuteq_batch.R"
    if not runner.exists():
        return finalize_failure(paths, f"Runner R introuvable: {runner}")

    resolved_rscript = locate_rscript(rscript_path)
    env = os.environ.copy()
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    command = [
        resolved_rscript,
        str(runner),
        "--input",
        str(corpus_path),
        "--config",
        str(paths.config_file),
        "--output-dir",
        str(paths.export_dir),
        "--status-file",
        str(paths.status_file),
        "--results-file",
        str(paths.results_file),
    ]

    process = subprocess.run(
        command,
        cwd=str(paths.repo_root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    paths.stdout_log.write_text(process.stdout, encoding="utf-8")
    paths.stderr_log.write_text(process.stderr, encoding="utf-8")

    if process.returncode != 0:
        message = summarize_failure(process, paths)
        return finalize_failure(paths, message, returncode=process.returncode)

    if not paths.results_file.exists():
        return finalize_failure(paths, "Le runner R n'a pas produit results.json.", returncode=process.returncode)

    results = read_json(paths.results_file)
    results.setdefault("job_id", paths.job_root.name)
    results.setdefault("status_file", str(paths.status_file))
    results.setdefault("stdout_log", str(paths.stdout_log))
    results.setdefault("stderr_log", str(paths.stderr_log))
    write_json(paths.results_file, results)
    return results


def preview_simi_terms(
    *,
    corpus_path: Path,
    config: dict[str, Any],
    output_root: Path | None = None,
    job_id: str | None = None,
    rscript_path: str | None = None,
) -> dict[str, Any]:
    if not corpus_path.exists():
        raise FileNotFoundError(f"Corpus introuvable: {corpus_path}")

    paths = prepare_job_paths(output_root=output_root, job_id=job_id)
    paths.job_root.mkdir(parents=True, exist_ok=True)
    paths.export_dir.mkdir(parents=True, exist_ok=True)
    write_json(paths.config_file, config)
    initialize_status(paths, config)

    runner = paths.repo_root / "backend" / "r" / "run_iramuteq_batch.R"
    if not runner.exists():
        return finalize_failure(paths, f"Runner R introuvable: {runner}")

    resolved_rscript = locate_rscript(rscript_path)
    env = os.environ.copy()
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    command = [
        resolved_rscript,
        str(runner),
        "--mode",
        "preview_simi_terms",
        "--input",
        str(corpus_path),
        "--config",
        str(paths.config_file),
        "--output-dir",
        str(paths.export_dir),
        "--status-file",
        str(paths.status_file),
        "--results-file",
        str(paths.results_file),
    ]

    process = subprocess.run(
        command,
        cwd=str(paths.repo_root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    paths.stdout_log.write_text(process.stdout, encoding="utf-8")
    paths.stderr_log.write_text(process.stderr, encoding="utf-8")

    if process.returncode != 0:
        message = summarize_failure(process, paths)
        return finalize_failure(paths, message, returncode=process.returncode)

    if not paths.results_file.exists():
        return finalize_failure(paths, "Le runner R n'a pas produit results.json.", returncode=process.returncode)

    results = read_json(paths.results_file)
    results.setdefault("job_id", paths.job_root.name)
    results.setdefault("status_file", str(paths.status_file))
    results.setdefault("stdout_log", str(paths.stdout_log))
    results.setdefault("stderr_log", str(paths.stderr_log))
    write_json(paths.results_file, results)
    return results


def check_environment(rscript_path: str | None = None) -> dict[str, Any]:
    repo_root = repo_root_from_file()
    runner = repo_root / "backend" / "r" / "run_iramuteq_batch.R"
    rscript = locate_rscript(rscript_path)
    probe = subprocess.run(
        [rscript, "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "python": sys.executable,
        "rscript": rscript,
        "runner": str(runner),
        "runner_exists": runner.exists(),
        "rscript_version": (probe.stdout or probe.stderr).strip(),
    }


def bootstrap_environment(rscript_path: str | None = None, auto_install: bool = True) -> dict[str, Any]:
    python_required = {
        "numpy": "numpy",
        "sklearn": "scikit-learn",
        "matplotlib": "matplotlib",
        "pyLDAvis": "pyLDAvis",
        "wordcloud": "wordcloud",
        "altair": "altair",
        "vl_convert": "vl-convert-python",
        "yt_dlp": "yt-dlp",
        "imageio_ffmpeg": "imageio-ffmpeg",
        "librosa": "librosa",
        "cv2": "opencv-python",
        "faster_whisper": "faster-whisper",
        "mediapipe": "mediapipe",
    }
    python_install_targets = {
        "numpy": "numpy<2",
        "sklearn": "scikit-learn",
        "matplotlib": "matplotlib",
        "pyLDAvis": "pyLDAvis",
        "wordcloud": "wordcloud",
        "altair": "altair",
        "vl_convert": "vl-convert-python",
        "yt_dlp": "yt-dlp",
        "imageio_ffmpeg": "imageio-ffmpeg",
        "librosa": "librosa",
        "cv2": "opencv-python",
        "faster_whisper": "faster-whisper",
        "mediapipe": "mediapipe==0.10.9",
    }
    python_min_versions = {
        "yt_dlp": "2025.01.15",
    }

    def parse_version_token(version: str) -> tuple[int, ...]:
        raw = str(version or "").strip()
        if not raw:
            return tuple()
        parts: list[int] = []
        for chunk in raw.replace("-", ".").split("."):
            digits = "".join(char for char in chunk if char.isdigit())
            if digits:
                parts.append(int(digits))
        return tuple(parts)

    def detect_outdated_python_packages() -> list[str]:
        outdated: list[str] = []
        for import_name, minimum in python_min_versions.items():
            if importlib.util.find_spec(import_name) is None:
                continue
            try:
                installed = importlib_metadata.version(python_required[import_name])
            except Exception:
                continue
            if parse_version_token(installed) < parse_version_token(minimum):
                outdated.append(import_name)
        if importlib.util.find_spec("numpy") is not None:
            try:
                installed_numpy = importlib_metadata.version(python_required["numpy"])
            except Exception:
                installed_numpy = ""
            if parse_version_token(installed_numpy) >= (2,):
                outdated.append("numpy")
        return outdated

    def detect_missing_python_packages() -> list[str]:
        missing: list[str] = []
        for import_name in python_required:
            if importlib.util.find_spec(import_name) is None:
                missing.append(import_name)
        return missing

    def detect_broken_python_packages() -> list[str]:
        packages_to_check = ["mediapipe"]
        broken: list[str] = []
        for import_name in packages_to_check:
            if importlib.util.find_spec(import_name) is None:
                continue
            process = subprocess.run(
                [sys.executable, "-c", f"import {import_name}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={
                    **os.environ,
                    "PYTHONNOUSERSITE": "1",
                },
            )
            if process.returncode != 0:
                broken.append(import_name)
        return broken

    def install_or_upgrade_python_packages(packages: list[str], *, upgrade: bool = False) -> tuple[list[str], list[str], str | None]:
        if not packages:
            return [], [], None

        in_virtualenv = getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        command = [sys.executable, "-m", "pip", "install"]
        if not in_virtualenv:
            command.append("--user")
        if upgrade:
            command.append("--upgrade")
        command.extend([python_install_targets[name] for name in packages])
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={
                **os.environ,
                "PYTHONNOUSERSITE": "1",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            },
        )

        missing_after_install = detect_missing_python_packages()
        broken_after_install = detect_broken_python_packages()
        installed_now = [
            name
            for name in packages
            if name not in missing_after_install and name not in broken_after_install
        ]
        missing_after_install = sorted(set(missing_after_install + broken_after_install))

        if process.returncode == 0 and not missing_after_install:
            return installed_now, missing_after_install, None

        stderr = (process.stderr or "").strip()
        stdout = (process.stdout or "").strip()
        details = stderr or stdout or "Installation pip en échec."
        return installed_now, missing_after_install, details

    repo_root = repo_root_from_file()
    script = repo_root / "backend" / "r" / "bootstrap_iramuteq_env.R"
    if not script.exists():
        return {
            "success": False,
            "message": f"Script bootstrap introuvable: {script}",
        }

    resolved_rscript = locate_rscript(rscript_path)
    env = os.environ.copy()
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    mode = "install" if auto_install else "check"
    process = subprocess.run(
        [resolved_rscript, str(script), "--mode", mode],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if process.returncode != 0:
        message = summarize_failure(
            process,
            prepare_job_paths(output_root=repo_root / "backend" / "jobs", job_id="bootstrap-temp"),
        )
        return {
            "success": False,
            "message": message,
            "stdout": process.stdout,
            "stderr": process.stderr,
        }

    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        return {
            "success": False,
            "message": f"Reponse bootstrap invalide: {error}",
            "stdout": process.stdout,
            "stderr": process.stderr,
        }

    payload.setdefault("success", False)
    payload["rscript"] = resolved_rscript
    payload["python"] = sys.executable
    if process.stderr.strip():
        payload["stderr"] = process.stderr

    missing_python_before = detect_missing_python_packages()
    broken_python_before = detect_broken_python_packages()
    outdated_python_before = detect_outdated_python_packages()
    repair_python_before = sorted(set(missing_python_before + broken_python_before + outdated_python_before))
    installed_python_now: list[str] = []
    python_install_error: str | None = None
    missing_python_after = sorted(set(missing_python_before + broken_python_before))

    if auto_install and repair_python_before:
        installed_python_now, missing_python_after, python_install_error = install_or_upgrade_python_packages(
            repair_python_before,
            upgrade=True,
        )
    else:
        missing_python_after = sorted(set(missing_python_before + broken_python_before))

    installed_now = list(payload.get("installed_now") or [])
    installed_now.extend([f"python:{name}" for name in installed_python_now])
    missing_after = list(payload.get("missing_after") or [])
    missing_after.extend([f"python:{name}" for name in missing_python_after])

    payload["installed_now"] = installed_now
    payload["missing_after"] = missing_after
    payload["python_missing_before"] = missing_python_before
    payload["python_broken_before"] = broken_python_before
    payload["python_missing_after"] = missing_python_after
    payload["python_outdated_before"] = outdated_python_before
    payload["success"] = bool(payload.get("success")) and not missing_python_after

    if python_install_error:
        existing_message = str(payload.get("message", "")).strip()
        payload["message"] = (
            f"{existing_message} " if existing_message else ""
        ) + f"Dependances Python manquantes, cassees ou non installables: {', '.join(missing_python_after)}. {python_install_error}"
    elif not payload["success"] and missing_python_after:
        existing_message = str(payload.get("message", "")).strip()
        payload["message"] = (
            f"{existing_message} " if existing_message else ""
        ) + f"Dependances Python encore manquantes ou cassees: {', '.join(missing_python_after)}."

    return payload
