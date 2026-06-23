from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import runtime


app = FastAPI(title="IRaMuTeQ Lite Web", docs_url=None, redoc_url=None)
_MISSING = object()


def build_web_index() -> str:
    index_path = runtime.frontend_root() / "index.html"
    html = index_path.read_text(encoding="utf-8")
    app_script = '<script type="module" src="./app.js"></script>'
    shim_script = '<script src="./web-runtime.js"></script>\n    <script type="module" src="./app.js"></script>'
    if app_script in html:
        return html.replace(app_script, shim_script, 1)
    return html.replace("</body>", '    <script src="./web-runtime.js"></script>\n  </body>', 1)


def get_payload_arg(payload: dict[str, Any], *names: str, default: Any = _MISSING) -> Any:
    for name in names:
        if name in payload:
            return payload[name]
    if default is not _MISSING:
        return default
    raise KeyError(names[0])


def dispatch_tauri_command(command: str, payload: dict[str, Any]) -> Any:
    if command == "bootstrap_dependencies":
        return runtime.bootstrap_dependencies()
    if command == "run_python_analysis":
        return runtime.run_python_analysis(
            get_payload_arg(payload, "corpusName", "corpus_name"),
            get_payload_arg(payload, "corpusText", "corpus_text"),
            get_payload_arg(payload, "config"),
        )
    if command == "start_python_analysis":
        return runtime.start_python_analysis(
            get_payload_arg(payload, "corpusName", "corpus_name"),
            get_payload_arg(payload, "corpusText", "corpus_text"),
            get_payload_arg(payload, "config"),
        )
    if command == "read_python_analysis_status":
        return runtime.read_python_analysis_status(get_payload_arg(payload, "jobId", "job_id"))
    if command == "preview_simi_terms":
        return runtime.preview_simi_terms(
            get_payload_arg(payload, "corpusName", "corpus_name"),
            get_payload_arg(payload, "corpusText", "corpus_text"),
            get_payload_arg(payload, "config"),
        )
    if command == "run_chd_action":
        return runtime.run_chd_action(
            get_payload_arg(payload, "outputDir", "output_dir"),
            get_payload_arg(payload, "action"),
            get_payload_arg(payload, "term"),
            get_payload_arg(payload, "classLabel", "class_label", default=None),
        )
    if command == "download_results_archive":
        return runtime.download_results_archive(
            get_payload_arg(payload, "outputDir", "output_dir"),
            get_payload_arg(payload, "archiveName", "archive_name", default=None),
        )
    if command == "save_results_archive":
        return runtime.save_results_archive(
            get_payload_arg(payload, "outputDir", "output_dir"),
            get_payload_arg(payload, "archiveName", "archive_name", default=None),
        )
    if command == "collect_output_artifacts":
        return runtime.collect_output_artifacts(get_payload_arg(payload, "outputDir", "output_dir"))
    if command == "read_help_file":
        return runtime.read_help_file(get_payload_arg(payload, "relativePath", "relative_path"))
    if command == "read_annotation_dictionary_file":
        return runtime.read_annotation_dictionary_file()
    if command == "write_annotation_dictionary_file":
        return runtime.write_annotation_dictionary_file(get_payload_arg(payload, "content"))
    if command == "reset_annotation_dictionary_file":
        return runtime.reset_annotation_dictionary_file()
    if command == "save_annotation_dictionary_export":
        return runtime.save_annotation_dictionary_export(
            get_payload_arg(payload, "content"),
            get_payload_arg(payload, "filename", default=None),
        )
    if command == "save_text_export":
        return runtime.save_text_export(
            get_payload_arg(payload, "content"),
            get_payload_arg(payload, "filename", default=None),
        )
    if command == "save_png_export":
        return runtime.save_png_export(
            get_payload_arg(payload, "data"),
            get_payload_arg(payload, "filename", default=None),
        )
    if command == "persist_multimodal_input":
        return runtime.persist_multimodal_input(
            get_payload_arg(payload, "slot"),
            get_payload_arg(payload, "filename"),
            get_payload_arg(payload, "data"),
        )
    if command == "persist_multimodal_image_batch":
        return runtime.persist_multimodal_image_batch(get_payload_arg(payload, "files"))
    if command == "pick_output_directory":
        return runtime.pick_output_directory()
    if command == "run_multimodal_script":
        return runtime.run_multimodal_script(
            get_payload_arg(payload, "scriptName", "script_name"),
            get_payload_arg(payload, "args", default=[]),
            get_payload_arg(payload, "outputDir", "output_dir"),
        )
    if command == "read_multimodal_progress":
        return runtime.read_multimodal_progress(
            get_payload_arg(payload, "outputDir", "output_dir"),
            get_payload_arg(payload, "analysisKey", "analysis_key"),
        )
    raise KeyError(command)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(build_web_index())


@app.get("/api/local-file")
def local_file(path: str) -> FileResponse:
    try:
        file_path = runtime.resolve_local_file_path(path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return FileResponse(file_path, media_type=runtime.mime_type_for_path(file_path))


@app.post("/api/tauri/{command}")
async def tauri_invoke(command: str, request: Request) -> Any:
    raw_body = await request.body()
    payload: dict[str, Any] = {}
    if raw_body:
        try:
            decoded = json.loads(raw_body)
        except json.JSONDecodeError as error:
            raise HTTPException(status_code=400, detail=f"JSON invalide: {error}") from error
        if decoded is None:
            payload = {}
        elif isinstance(decoded, dict):
            payload = decoded
        else:
            raise HTTPException(status_code=400, detail="Le corps JSON doit être un objet.")

    try:
        return dispatch_tauri_command(command, payload)
    except KeyError as error:
        missing = error.args[0] if error.args else command
        if missing == command:
            raise HTTPException(status_code=404, detail=f"Commande inconnue: {command}") from error
        raise HTTPException(status_code=400, detail=f"Paramètre manquant: {missing}") from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


app.mount("/", StaticFiles(directory=runtime.frontend_root(), html=True), name="frontend")
