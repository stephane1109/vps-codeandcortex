from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from gestion_tickets import (
    connecter_redis,
    construire_tableau_de_bord,
    construire_tableau_de_bord_indisponible,
    liberer_ticket,
)


ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
STYLE_FILE = ROOT / "style.css"
AIDE_FILE = ROOT / "aide.md"

app = FastAPI(title="Code & Cortex VPS Dashboard", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        connecter_redis()
    except Exception:
        return {"status": "degraded"}
    return {"status": "ok"}


@app.get("/api/tickets/dashboard")
def tickets_dashboard(applications: str | None = Query(default=None)) -> dict:
    application_ids = [item.strip() for item in (applications or "").split(",") if item.strip()] or None
    try:
        client_redis = connecter_redis()
        return construire_tableau_de_bord(client_redis, application_ids)
    except Exception as exc:
        return construire_tableau_de_bord_indisponible(application_ids, str(exc))


@app.api_route("/api/tickets/release", methods=["GET", "POST"])
def release_ticket(application_id: str = Query(...), session_id: str = Query(...)) -> dict[str, str]:
    client_redis = connecter_redis()
    liberer_ticket(client_redis, session_id, application_id)
    return {"status": "released", "application_id": application_id, "session_id": session_id}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")


@app.get("/index.html")
def index_alias() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")


@app.get("/style.css")
def style() -> FileResponse:
    return FileResponse(STYLE_FILE, media_type="text/css; charset=utf-8")


@app.get("/aide.md")
def aide_markdown() -> FileResponse:
    return FileResponse(AIDE_FILE, media_type="text/markdown; charset=utf-8")
