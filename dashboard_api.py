from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

from gestion_tickets import (
    connecter_redis,
    construire_tableau_de_bord,
    construire_tableau_de_bord_indisponible,
)


ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
STYLE_FILE = ROOT / "style.css"

app = FastAPI(title="Code & Cortex VPS Dashboard", docs_url=None, redoc_url=None)


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


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")


@app.get("/index.html")
def index_alias() -> FileResponse:
    return FileResponse(INDEX_FILE, media_type="text/html; charset=utf-8")


@app.get("/style.css")
def style() -> FileResponse:
    return FileResponse(STYLE_FILE, media_type="text/css; charset=utf-8")
