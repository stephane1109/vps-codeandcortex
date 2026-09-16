from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import analysis_history
from . import runtime
from . import ticket_gate


app = FastAPI(title="IRaMuTeQ Lite Web", docs_url=None, redoc_url=None)
_MISSING = object()


def analysis_json_response(payload: dict[str, Any], owner_token: str | None = None) -> JSONResponse:
    response = JSONResponse(payload)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    analysis_history.apply_owner_cookie(response, owner_token)
    return response


def purge_expired_analysis_history() -> None:
    for record in analysis_history.purge_expired_analyses(runtime.app_data_root()):
        try:
            runtime.remove_job_directory(str(record.get("jobId") or ""))
        except (OSError, ValueError):
            continue


def history_descriptor(payload: dict[str, Any]) -> tuple[str, str]:
    history_payload = payload.get("history")
    requested_kind = ""
    if isinstance(history_payload, dict):
        requested_kind = str(history_payload.get("analysisKind") or "").strip().lower()

    if requested_kind not in {"chd", "simi", "suivi"}:
        analyses = payload.get("config", {}).get("analyses", {}) if isinstance(payload.get("config"), dict) else {}
        if isinstance(analyses, dict) and analyses.get("simi"):
            requested_kind = "simi"
        elif isinstance(analyses, dict) and analyses.get("suivi"):
            requested_kind = "suivi"
        else:
            requested_kind = "chd"

    navigation_target = {
        "chd": "resultats_chd",
        "simi": "similitudes",
        "suivi": "suivi_longitudinal",
    }[requested_kind]
    return requested_kind, navigation_target


def sync_owned_analysis(
    owner_hash: str,
    analysis_id: str,
    *,
    include_files: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data_root = runtime.app_data_root()
    purge_expired_analysis_history()
    record = analysis_history.get_owned_analysis(data_root, owner_hash, analysis_id)
    if not record:
        raise HTTPException(status_code=404, detail="Analyse introuvable ou non autorisée.")

    snapshot = runtime.read_python_analysis_status(record["jobId"], include_files=include_files)
    updated = analysis_history.update_analysis_from_snapshot(
        data_root,
        owner_hash=owner_hash,
        analysis_id=analysis_id,
        snapshot=snapshot,
    )
    if not updated:  # pragma: no cover - record deletion race guard
        raise HTTPException(status_code=404, detail="Analyse introuvable ou non autorisée.")
    if snapshot.get("completed"):
        runtime.remove_job_input(record["jobId"])
    return updated, snapshot


def owned_output_dir(record: dict[str, Any], snapshot: dict[str, Any]) -> str:
    raw_output_dir = str(snapshot.get("outputDir") or record.get("outputDir") or "").strip()
    if not raw_output_dir:
        raise HTTPException(status_code=409, detail="Les exports de cette analyse ne sont pas encore disponibles.")

    output_dir = Path(raw_output_dir).resolve()
    job_root = runtime.job_root_for_id(str(record["jobId"])).resolve()
    if not runtime.path_within(output_dir, job_root) or not output_dir.is_dir():
        raise HTTPException(status_code=404, detail="Le dossier d'exports de cette analyse est introuvable.")
    return str(output_dir)


def ticket_json_response(
    payload: dict[str, Any],
    *,
    session_id: str | None = None,
    clear_session: bool = False,
) -> JSONResponse:
    response = JSONResponse(payload)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    if clear_session:
        ticket_gate.clear_session_cookie_headers(response)
    else:
        ticket_gate.apply_session_cookie_headers(response, session_id)
    return response


def build_web_index() -> str:
    index_path = runtime.frontend_root() / "index.html"
    html = index_path.read_text(encoding="utf-8")
    app_script = '<script type="module" src="./app.js"></script>'
    shim_tag = '<script src="./web-runtime.js"></script>'
    shim_script = f"{shim_tag}\n    {app_script}"
    if shim_tag in html and app_script in html:
        return html
    if app_script in html:
        return html.replace(app_script, shim_script, 1)
    if shim_tag in html:
        return html
    return html.replace("</body>", f"    {shim_tag}\n  </body>", 1)


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
    raise KeyError(command)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tickets/status")
def ticket_status(request: Request) -> JSONResponse:
    snapshot, session_id = ticket_gate.status_for_request(request)
    return ticket_json_response(snapshot, session_id=session_id)


@app.post("/api/tickets/claim")
def ticket_claim(request: Request) -> JSONResponse:
    snapshot, session_id = ticket_gate.claim_ticket_for_request(request)
    return ticket_json_response(snapshot, session_id=session_id)


@app.post("/api/tickets/heartbeat")
def ticket_heartbeat(request: Request) -> JSONResponse:
    snapshot, session_id = ticket_gate.heartbeat_ticket_for_request(request)
    return ticket_json_response(snapshot, session_id=session_id)


@app.post("/api/tickets/release")
def ticket_release(request: Request) -> JSONResponse:
    snapshot = ticket_gate.release_ticket_for_request(request)
    return ticket_json_response(snapshot, clear_session=True)


@app.post("/api/analysis/abandon")
async def analysis_abandon(request: Request) -> JSONResponse:
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
        ticket_gate.require_active_ticket(request)
    except PermissionError as error:
        raise HTTPException(status_code=423, detail=str(error)) from error

    try:
        result = runtime.cancel_python_analysis(
            get_payload_arg(payload, "jobId", "job_id", default=None),
            get_payload_arg(payload, "reason", default=None),
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    snapshot = ticket_gate.release_ticket_for_request(request)
    response = JSONResponse({**result, "ticket": snapshot})
    ticket_gate.clear_session_cookie_headers(response)
    return response


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    # Ouvrir l'interface ne reserve pas de capacite. Le ticket est demande
    # uniquement au lancement effectif d'une analyse par le frontend.
    snapshot, session_id = ticket_gate.status_for_request(request)
    response = HTMLResponse(build_web_index())
    if session_id:
        ticket_gate.apply_session_cookie_headers(response, session_id)
    response.headers["X-Ticket-Status"] = str(snapshot.get("statut") or "")
    return response


@app.get("/api/analyses")
def list_analyses(request: Request) -> JSONResponse:
    owner_hash, owner_token = analysis_history.owner_for_request(request)
    data_root = runtime.app_data_root()
    purge_expired_analysis_history()

    # Only incomplete jobs need a filesystem refresh; finished records are read from SQLite.
    for record in analysis_history.list_owned_analyses(data_root, owner_hash):
        if record.get("completed"):
            continue
        try:
            snapshot = runtime.read_python_analysis_status(record["jobId"], include_files=False)
            analysis_history.update_analysis_from_snapshot(
                data_root,
                owner_hash=owner_hash,
                analysis_id=record["id"],
                snapshot=snapshot,
            )
            if snapshot.get("completed"):
                runtime.remove_job_input(record["jobId"])
        except (OSError, ValueError):
            continue

    return analysis_json_response(
        {
            "analyses": analysis_history.list_owned_analyses(data_root, owner_hash),
            "retentionDays": analysis_history.retention_days(),
        },
        owner_token,
    )


@app.get("/api/analyses/{analysis_id}/artifacts")
def read_analysis_artifacts(analysis_id: str, request: Request) -> JSONResponse:
    owner_hash, owner_token = analysis_history.owner_for_request(request)
    record, snapshot = sync_owned_analysis(owner_hash, analysis_id, include_files=True)
    if not snapshot.get("completed"):
        raise HTTPException(status_code=409, detail="Cette analyse est encore en cours de calcul.")
    if not snapshot.get("success"):
        raise HTTPException(status_code=409, detail=snapshot.get("message") or "Cette analyse n'a pas produit de résultats.")

    owned_output_dir(record, snapshot)
    return analysis_json_response(
        {
            "analysis": record,
            "snapshot": snapshot,
            "artifacts": snapshot.get("files") or [],
        },
        owner_token,
    )


@app.get("/api/analyses/{analysis_id}/archive")
def download_analysis_archive(analysis_id: str, request: Request) -> StreamingResponse:
    owner_hash, owner_token = analysis_history.owner_for_request(request)
    record, snapshot = sync_owned_analysis(owner_hash, analysis_id, include_files=False)
    if not snapshot.get("completed") or not snapshot.get("success"):
        raise HTTPException(status_code=409, detail="Cette analyse n'est pas prête à être téléchargée.")

    archive = runtime.build_results_archive(Path(owned_output_dir(record, snapshot)))
    response = StreamingResponse(
        BytesIO(archive),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="iramuteq-{record["jobId"]}-resultats.zip"',
            "Cache-Control": "no-store",
        },
    )
    analysis_history.apply_owner_cookie(response, owner_token)
    return response


@app.get("/api/analyses/{analysis_id}")
def read_analysis(analysis_id: str, request: Request) -> JSONResponse:
    owner_hash, owner_token = analysis_history.owner_for_request(request)
    record, snapshot = sync_owned_analysis(owner_hash, analysis_id, include_files=False)
    return analysis_json_response({"analysis": record, "snapshot": snapshot}, owner_token)


@app.delete("/api/analyses/{analysis_id}")
def delete_analysis(analysis_id: str, request: Request) -> JSONResponse:
    owner_hash, owner_token = analysis_history.owner_for_request(request)
    record, snapshot = sync_owned_analysis(owner_hash, analysis_id, include_files=False)
    if not snapshot.get("completed"):
        raise HTTPException(status_code=409, detail="Arrêtez l'analyse avant de la supprimer.")

    deleted = analysis_history.delete_owned_analysis(runtime.app_data_root(), owner_hash, analysis_id)
    if not deleted:  # pragma: no cover - deletion race guard
        raise HTTPException(status_code=404, detail="Analyse introuvable ou non autorisée.")
    runtime.remove_job_directory(record["jobId"])
    return analysis_json_response({"deleted": True, "analysisId": analysis_id}, owner_token)


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
        if command == "start_python_analysis":
            try:
                ticket_gate.require_active_ticket(request)
            except PermissionError as error:
                raise HTTPException(status_code=423, detail=str(error)) from error
            result = dispatch_tauri_command(command, payload)
            owner_hash, owner_token = analysis_history.owner_for_request(request)
            analysis_kind, navigation_target = history_descriptor(payload)
            try:
                record = analysis_history.create_analysis(
                    runtime.app_data_root(),
                    owner_hash=owner_hash,
                    job_id=str(result.get("jobId") or "").strip(),
                    corpus_name=str(get_payload_arg(payload, "corpusName", "corpus_name")),
                    analysis_kind=analysis_kind,
                    navigation_target=navigation_target,
                )
            except Exception as error:
                # A job without an owner record could no longer be restored safely.
                try:
                    runtime.cancel_python_analysis(
                        str(result.get("jobId") or "").strip(),
                        "Analyse arrêtée : l'enregistrement de l'historique a échoué.",
                    )
                except Exception:
                    pass
                raise RuntimeError("Impossible d'enregistrer cette analyse dans l'historique.") from error

            return analysis_json_response({**result, "analysisId": record["id"]}, owner_token)

        result = dispatch_tauri_command(command, payload)
        if command == "read_python_analysis_status":
            job_id = str(get_payload_arg(payload, "jobId", "job_id")).strip()
            owner_hash, owner_token = analysis_history.owner_for_request(request)
            registered = analysis_history.get_analysis_by_job(runtime.app_data_root(), job_id)
            if registered:
                if registered.get("ownerHash") != owner_hash:
                    raise HTTPException(status_code=404, detail="Analyse introuvable ou non autorisée.")
                analysis_history.update_analysis_from_snapshot(
                    runtime.app_data_root(),
                    owner_hash=owner_hash,
                    analysis_id=registered["id"],
                    snapshot=result,
                )
                if result.get("completed"):
                    runtime.remove_job_input(job_id)
            return analysis_json_response(result, owner_token)

        return result
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
