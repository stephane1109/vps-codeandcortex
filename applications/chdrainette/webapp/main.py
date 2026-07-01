from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import runtime
from . import ticket_gate


app = FastAPI(title="CHD Rainette Web", docs_url=None, redoc_url=None)


def with_session_id(snapshot: dict[str, Any], session_id: str | None) -> dict[str, Any]:
    payload = dict(snapshot)
    payload["session_id"] = session_id
    return payload


def read_index_html() -> str:
    return (runtime.frontend_root() / "index.html").read_text(encoding="utf-8")


async def request_payload(request: Request) -> dict[str, Any]:
    raw_body = await request.body()
    if not raw_body:
        return {}
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=400, detail=f"JSON invalide : {error}") from error
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Le corps JSON doit être un objet.")
    return payload


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tickets/status")
def ticket_status(request: Request) -> JSONResponse:
    snapshot, session_id = ticket_gate.status_for_request(request)
    response = JSONResponse(with_session_id(snapshot, session_id))
    ticket_gate.apply_session_cookie_headers(response, session_id)
    return response


@app.post("/api/tickets/claim")
def ticket_claim(request: Request) -> JSONResponse:
    snapshot, session_id = ticket_gate.claim_ticket_for_request(request)
    response = JSONResponse(with_session_id(snapshot, session_id))
    ticket_gate.apply_session_cookie_headers(response, session_id)
    return response


@app.post("/api/tickets/heartbeat")
def ticket_heartbeat(request: Request) -> JSONResponse:
    snapshot, session_id = ticket_gate.heartbeat_ticket_for_request(request)
    response = JSONResponse(with_session_id(snapshot, session_id))
    ticket_gate.apply_session_cookie_headers(response, session_id)
    return response


@app.post("/api/tickets/release")
def ticket_release(request: Request) -> JSONResponse:
    snapshot = ticket_gate.release_ticket_for_request(request)
    response = JSONResponse(with_session_id(snapshot, None))
    ticket_gate.clear_session_cookie_headers(response)
    return response


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    snapshot, session_id = ticket_gate.claim_ticket_for_request(request)
    response = HTMLResponse(read_index_html())
    ticket_gate.apply_session_cookie_headers(response, session_id)
    response.headers["X-Ticket-Status"] = str(snapshot.get("statut") or "")
    return response


@app.post("/api/analyze")
async def analyze(request: Request) -> dict[str, str]:
    try:
        ticket_gate.require_active_ticket(request)
    except PermissionError as error:
        raise HTTPException(status_code=423, detail=str(error)) from error

    payload = await request_payload(request)
    corpus_name = str(payload.get("corpusName") or payload.get("corpus_name") or "corpus.txt").strip() or "corpus.txt"
    corpus_text = str(payload.get("corpusText") or payload.get("corpus_text") or "")
    config = payload.get("config") or {}

    if not corpus_text.strip():
        raise HTTPException(status_code=400, detail="Le corpus texte est vide.")
    if not isinstance(config, dict):
        raise HTTPException(status_code=400, detail="La configuration doit être un objet JSON.")

    try:
        return runtime.start_analysis(corpus_name, corpus_text, config)
    except RuntimeError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/jobs/{job_id}/status")
def job_status(job_id: str) -> dict[str, Any]:
    try:
        return runtime.read_analysis_status(job_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/jobs/{job_id}/explorer/plot")
def explorer_plot(
    job_id: str,
    k: int = Query(..., ge=2),
    measure: str = Query("chi2"),
    n_terms: int = Query(20, ge=5, le=50),
    same_scales: bool = Query(True),
    show_negative: bool = Query(False),
    text_size: int = Query(12, ge=6, le=24),
) -> FileResponse:
    params = {
        "k": k,
        "measure": measure,
        "n_terms": n_terms,
        "same_scales": same_scales,
        "show_negative": show_negative,
        "text_size": text_size,
    }
    try:
        file_path = runtime.render_explorer_plot(job_id, params)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return FileResponse(file_path, media_type="image/png")


@app.get("/api/jobs/{job_id}/explorer/docs")
def explorer_docs(
    job_id: str,
    k: int = Query(..., ge=2),
    cluster: int = Query(1, ge=1),
    ndoc: int = Query(100, ge=1),
    nchar: int = Query(1000, ge=10),
    random_sample: bool = Query(False),
    filter_term: str = Query(""),
) -> dict[str, Any]:
    params = {
        "k": k,
        "cluster": cluster,
        "ndoc": ndoc,
        "nchar": nchar,
        "random_sample": random_sample,
        "filter_term": filter_term,
    }
    try:
        return runtime.render_explorer_docs(job_id, params)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/jobs/{job_id}/explorer/code")
def explorer_code(
    job_id: str,
    k: int = Query(..., ge=2),
    measure: str = Query("chi2"),
    n_terms: int = Query(20, ge=5, le=50),
    same_scales: bool = Query(True),
    show_negative: bool = Query(False),
    text_size: int = Query(12, ge=6, le=24),
) -> dict[str, Any]:
    params = {
        "k": k,
        "measure": measure,
        "n_terms": n_terms,
        "same_scales": same_scales,
        "show_negative": show_negative,
        "text_size": text_size,
    }
    try:
        return runtime.render_explorer_code(job_id, params)
    except (FileNotFoundError, ValueError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


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


app.mount("/", StaticFiles(directory=runtime.frontend_root(), html=True), name="frontend")
