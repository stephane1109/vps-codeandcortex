from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def build_env() -> dict[str, str]:
    env = os.environ.copy()
    app_data_dir = env.get("CHDRAINETTE_APP_DATA_DIR", "").strip() or env.get("APP_DATA_DIR", "").strip() or "/data/app"
    r_libs_user = env.get("CHDRAINETTE_R_LIBS_USER", "").strip() or env.get("R_LIBS_USER", "").strip() or str(Path(app_data_dir) / "r-library")
    cache_dir = env.get("CHDRAINETTE_CACHE_DIR", "").strip() or str(Path(app_data_dir) / "cache")

    env["APP_DATA_DIR"] = app_data_dir
    env["CHDRAINETTE_APP_DATA_DIR"] = app_data_dir
    env["CHDRAINETTE_R_LIBS_USER"] = r_libs_user
    env["R_LIBS_USER"] = r_libs_user
    env["CHDRAINETTE_CACHE_DIR"] = cache_dir
    env.setdefault("LANG", "en_US.UTF-8")
    env.setdefault("LC_CTYPE", "en_US.UTF-8")
    return env


def csv_rows(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for index, row in enumerate(reader):
            rows.append({str(key): str(value or "") for key, value in row.items()})
            if limit is not None and index + 1 >= limit:
                break
    return rows


def artifact_metadata(output_dir: Path) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        mime_type, _encoding = mimetypes.guess_type(str(path))
        artifacts.append(
            {
                "relativePath": path.relative_to(output_dir).as_posix(),
                "absolutePath": str(path.resolve()),
                "downloadUrl": f"/api/local-file?path={quote(str(path.resolve()))}",
                "mimeType": mime_type or "application/octet-stream",
                "sizeBytes": path.stat().st_size,
            }
        )
    return artifacts


def artifact_by_relative_path(artifacts: list[dict[str, object]], relative_path: str) -> dict[str, object] | None:
    target = str(relative_path or "").replace("\\", "/")
    for artifact in artifacts:
        if str(artifact.get("relativePath") or "").replace("\\", "/") == target:
            return artifact
    return None


def prefixed_artifacts(artifacts: list[dict[str, object]], prefix: str) -> list[dict[str, object]]:
    normalized_prefix = str(prefix or "").replace("\\", "/").rstrip("/") + "/"
    return [
        artifact
        for artifact in artifacts
        if str(artifact.get("relativePath") or "").replace("\\", "/").startswith(normalized_prefix)
    ]

def artifact_entry(base_root: Path, path: Path) -> dict[str, object]:
    mime_type, _encoding = mimetypes.guess_type(str(path))
    return {
        "relativePath": path.relative_to(base_root).as_posix(),
        "absolutePath": str(path.resolve()),
        "downloadUrl": f"/api/local-file?path={quote(str(path.resolve()))}",
        "mimeType": mime_type or "application/octet-stream",
        "sizeBytes": path.stat().st_size,
    }


def build_zip_archive(base_root: Path, zip_path: Path, files: list[Path]) -> Path:
    ensure_directory(zip_path.parent)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            resolved = path.resolve()
            if not path.is_file() or resolved == zip_path.resolve():
                continue
            archive.write(path, arcname=path.relative_to(base_root).as_posix())
    return zip_path


def export_zip_name(corpus_name: str) -> str:
    raw_name = Path(str(corpus_name or "").strip() or "corpus.txt").name
    stem = Path(raw_name).stem or "corpus"
    safe_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in stem)
    safe_stem = safe_stem.strip("._") or "corpus"
    return f"{safe_stem}.zip"


def build_export_catalog(job_root: Path, output_dir: Path, corpus_name: str) -> dict[str, object]:
    exports_dir = ensure_directory(job_root / "exports")
    source_files = [
        path
        for path in sorted(job_root.rglob("*"))
        if path.is_file() and path.suffix.lower() != ".zip"
    ]

    global_zip = build_zip_archive(
        job_root,
        exports_dir / export_zip_name(corpus_name),
        source_files,
    )

    return {
        "globalZip": artifact_entry(job_root, global_zip),
        "totalFiles": len(source_files),
        "jobRoot": str(job_root.resolve()),
        "outputRoot": str(output_dir.resolve()),
    }


def last_non_empty_line(*texts: str) -> str:
    for text in texts:
        for line in reversed((text or "").splitlines()):
            cleaned = line.strip()
            if cleaned:
                return cleaned
    return ""


def write_status(path: Path, *, job_id: str, state: str, progress: int, message: str, logs: list[str] | None = None) -> None:
    payload = {
        "jobId": job_id,
        "state": state,
        "progress": progress,
        "message": message,
        "logs": logs or [],
        "updatedAt": int(time.time()),
    }
    write_json(path, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute un job CHD Rainette pour le frontend web.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--job-id", required=True)
    args = parser.parse_args()

    job_root = ensure_directory(Path(args.output_root).expanduser().resolve() / args.job_id)
    output_dir = ensure_directory(job_root / "output")
    status_file = job_root / "status.json"
    results_file = job_root / "results.json"
    stdout_log = job_root / "stdout.log"
    stderr_log = job_root / "stderr.log"

    write_status(
        status_file,
        job_id=args.job_id,
        state="running",
        progress=5,
        message="Analyse CHD Rainette en cours...",
        logs=["[info] Initialisation du job CHD Rainette."],
    )

    command = [
        resolve_rscript(),
        str(PROJECT_ROOT / "backend" / "run_chdrainette.R"),
        str(Path(args.config).expanduser().resolve()),
        str(Path(args.input).expanduser().resolve()),
        str(output_dir),
    ]
    process = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=build_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stdout_log.write_text(process.stdout or "", encoding="utf-8")
    stderr_log.write_text(process.stderr or "", encoding="utf-8")

    logs = [line for line in (process.stdout or "").splitlines() if line.strip()]
    stderr_lines = [line for line in (process.stderr or "").splitlines() if line.strip()]

    if process.returncode != 0:
        message = last_non_empty_line(process.stderr, process.stdout) or "L'analyse CHD Rainette a échoué."
        write_status(
            status_file,
            job_id=args.job_id,
            state="error",
            progress=100,
            message=message,
            logs=[*logs, *stderr_lines],
        )
        return process.returncode

    metadata_path = output_dir / "metadata.json"
    metadata = read_json(metadata_path) if metadata_path.exists() else {}
    artifacts = artifact_metadata(output_dir)
    result_payload = {
        "success": True,
        "jobId": args.job_id,
        "outputDir": str(output_dir.resolve()),
        "bundlePath": str((output_dir / "analysis_bundle.rds").resolve()),
        "metadata": metadata,
        "summaryRows": csv_rows(output_dir / "resume_classes.csv"),
        "detailRows": csv_rows(output_dir / "mots_chi2_frequence_segments.csv", limit=200),
        "afc": {
            "error": metadata.get("afc_error") or "",
            "variablesError": metadata.get("afc_variables_error") or "",
            "classesPlot": artifact_by_relative_path(artifacts, "afc/afc_classes.png"),
            "termsPlot": artifact_by_relative_path(artifacts, "afc/afc_termes.png"),
            "variablesPlot": artifact_by_relative_path(artifacts, "afc/afc_variables_etoilees.png"),
            "termsRows": csv_rows(output_dir / "afc" / "stats_termes.csv", limit=200),
            "variablesRows": csv_rows(output_dir / "afc" / "stats_modalites.csv", limit=200),
            "eigenRows": csv_rows(output_dir / "afc" / "valeurs_propres.csv", limit=20),
            "variablesEigenRows": csv_rows(output_dir / "afc" / "valeurs_propres_vars.csv", limit=20),
        },
        "ner": {
            "enabled": bool(metadata.get("has_ner")),
            "summaryRows": csv_rows(output_dir / "ner" / "ner_resume.csv", limit=200),
            "detailRows": csv_rows(output_dir / "ner" / "ner_details.csv", limit=500),
            "globalPlot": artifact_by_relative_path(artifacts, "ner/ner_wordcloud_global.png"),
            "classPlots": prefixed_artifacts(artifacts, "ner"),
        },
        "artifacts": artifacts,
        "exports": build_export_catalog(job_root, output_dir, Path(args.input).name.removeprefix("input-")),
        "stdoutLog": str(stdout_log.resolve()),
        "stderrLog": str(stderr_log.resolve()),
    }
    write_json(results_file, result_payload)
    write_status(
        status_file,
        job_id=args.job_id,
        state="completed",
        progress=100,
        message="Analyse CHD Rainette terminée.",
        logs=[*logs, *stderr_lines],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
