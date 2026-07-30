from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from dashboard_shared.app_catalog import build_dashboard_entries
from dashboard_shared.tickets import (
    charger_configurations_applications,
    connecter_redis,
    construire_tableau_de_bord,
    construire_tableau_de_bord_indisponible,
    liberer_ticket,
    lire_configuration_tickets,
)


ROOT = Path(__file__).resolve().parent
INDEX_FILE = ROOT / "index.html"
AIDE_FILE = ROOT / "aide.md"
ASSETS_DIR = ROOT / "assets"
FAVICON_FILE = ASSETS_DIR / "favicon.ico"

app = FastAPI(title="Code & Cortex VPS Dashboard", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


def construire_catalogue_dashboard() -> dict[str, object]:
    grouped: dict[str, dict[str, object]] = {}
    visible_ticketed_ids: list[str] = []

    for entry in build_dashboard_entries(include_hidden=False):
        payload = dict(entry)
        app_id = str(payload.get("appId") or "").strip()
        if payload.get("ticketed") and app_id:
            configuration = lire_configuration_tickets(app_id)
            payload["label"] = configuration["label"]
            payload["defaultMaxActive"] = configuration["max_active"]
            payload["defaultCost"] = configuration["cout"]
            payload["defaultMetaText"] = f"0 / {configuration['max_active']} actif · 0 attente"
            visible_ticketed_ids.append(app_id)

        family_id = str(payload["familyId"])
        bucket = grouped.setdefault(
            family_id,
            {
                "id": family_id,
                "label": payload["familyLabel"],
                "order": payload["familyOrder"],
                "entries": [],
            },
        )
        bucket["entries"].append(payload)

    families = sorted(grouped.values(), key=lambda item: (item["order"], item["label"]))
    for family in families:
        family["entries"].sort(key=lambda item: (item["order"], item["label"]))
        family.pop("order", None)

    return {
        "generatedAt": int(time.time()),
        "families": families,
        "visibleTicketedAppIds": visible_ticketed_ids,
        "allTicketedAppIds": sorted(charger_configurations_applications().keys()),
    }


@app.get("/api/health")
def health() -> dict[str, str]:
    try:
        connecter_redis()
    except Exception:
        return {"status": "degraded"}
    return {"status": "ok"}


@app.get("/api/tickets/apps")
def tickets_apps() -> dict[str, object]:
    return construire_catalogue_dashboard()


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
def style_alias() -> FileResponse:
    return FileResponse(ASSETS_DIR / "style.css", media_type="text/css; charset=utf-8")


@app.get("/aide.md")
def aide_markdown() -> FileResponse:
    return FileResponse(AIDE_FILE, media_type="text/markdown; charset=utf-8")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(FAVICON_FILE, media_type="image/x-icon")
