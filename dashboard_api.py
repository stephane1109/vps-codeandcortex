from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

from gestion_tickets import connecter_redis, construire_tableau_de_bord


ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
STYLE_FILE = ROOT / "style.css"

app = FastAPI(title="Code & Cortex VPS Dashboard", docs_url=None, redoc_url=None)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tickets/dashboard")
def tickets_dashboard(applications: str | None = Query(default=None)) -> dict:
    client_redis = connecter_redis()
    application_ids = [item.strip() for item in (applications or "").split(",") if item.strip()] or None
    return construire_tableau_de_bord(client_redis, application_ids)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")


@app.get("/index.html")
def index_alias() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")


@app.get("/style.css")
def style() -> FileResponse:
    return FileResponse(STYLE_FILE, media_type="text/css; charset=utf-8")
