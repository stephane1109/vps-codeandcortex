"""API publique en lecture seule ; aucun accès aux contributions ou à l'historique privé."""

from datetime import date
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text
from .base import transaction
from .catalogue import (
    construire_requete,
    iterer_resultats,
    lister_plateformes,
    lister_tags,
    obtenir_fiche,
    rechercher,
    statistiques,
)
from .exports import MIMES, exporter_lignes
from .securite import ErreurMetier
from .validation import Filtres

app = FastAPI(
    title="DésinfoLab — API publique",
    version="1.0.0",
    description="Fiches validées et corpus d'URL documentés. Aucun téléchargement de média.",
)


@app.exception_handler(ErreurMetier)
async def erreur_metier(request: Request, exc: ErreurMetier):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.middleware("http")
async def entetes(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def filtres_api(
    texte: str = Query("", max_length=300),
    url: str = Query("", max_length=2048),
    plateforme_id: int | None = Query(None, gt=0),
    type_media: Literal["video", "article", "publication", "podcast", "audio", "pdf", "autre"] | None = None,
    tags: Annotated[list[int] | None, Query(max_length=50)] = None,
    thematique_id: int | None = Query(None, gt=0),
    operateur: Literal["ET", "OU"] = "ET",
    descendants: bool = True,
    pays: str = Query("", max_length=100),
    langue: str = Query("", max_length=100),
    date_debut: date | None = None,
    date_fin: date | None = None,
    source_id: int | None = Query(None, gt=0),
    compte_id: int | None = Query(None, gt=0),
):
    if tags and any(i < 1 for i in tags):
        raise HTTPException(422, "Les identifiants de tags doivent être positifs.")
    return Filtres(
        texte=texte,
        url=url,
        plateforme_id=plateforme_id,
        type_media=type_media,
        tags=tags or [],
        thematique_id=thematique_id,
        operateur=operateur,
        descendants=descendants,
        pays=pays,
        langue=langue,
        date_debut=date_debut,
        date_fin=date_fin,
        source_id=source_id,
        compte_id=compte_id,
    )


@app.get("/sante", tags=["État"])
def sante():
    try:
        with transaction() as session:
            session.execute(text("SELECT version_num FROM alembic_version"))
    except Exception:
        raise HTTPException(503, "Base indisponible ou migrations manquantes.") from None
    return {"statut": "ok"}


@app.get("/v1/statistiques", tags=["Catalogue"])
def stats():
    with transaction() as session:
        return statistiques(session)


@app.get("/v1/plateformes", tags=["Catalogue"])
def plateformes():
    with transaction() as session:
        return lister_plateformes(session)


@app.get("/v1/tags", tags=["Catalogue"])
def tags():
    with transaction() as session:
        return lister_tags(session)


@app.get("/v1/tags/{identifiant}", tags=["Catalogue"])
def tag(identifiant: int):
    return detail("tags", identifiant)


RESSOURCES = {"sources": "source", "comptes": "compte", "contenus": "contenu", "tags": "tag"}


@app.get("/v1/urls", tags=["Corpus"])
def urls(
    entite: Literal["source", "compte", "contenu"] = "contenu",
    filtres: Filtres = Depends(filtres_api),
    page: int = Query(1, ge=1),
    taille: int = Query(100, ge=1, le=200),
):
    with transaction() as session:
        resultat = rechercher(session, entite, filtres, page, taille)
        resultat["resultats"] = [
            {k: r.get(k) for k in ("id", "url", "plateforme", "type_media")} for r in resultat["resultats"]
        ]
        return resultat


@app.get("/v1/export/{format_export}", tags=["Corpus"])
def export(
    format_export: Literal["txt", "csv", "json"],
    entite: Literal["source", "compte", "contenu"] = "contenu",
    filtres: Filtres = Depends(filtres_api),
):
    with transaction() as session:
        construire_requete(
            session, entite, filtres
        )  # Rejeter les filtres invalides avant l'envoi des en-têtes.

    def flux():
        with transaction() as session:
            if session.bind.dialect.name == "postgresql":
                session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            yield from exporter_lignes(iterer_resultats(session, entite, filtres), format_export)

    return StreamingResponse(
        flux(),
        media_type=MIMES[format_export],
        headers={"Content-Disposition": f'attachment; filename="desinfolab.{format_export}"'},
    )


@app.get("/v1/{ressource}", tags=["Catalogue"])
def liste(
    ressource: Literal["sources", "comptes", "contenus"],
    filtres: Filtres = Depends(filtres_api),
    page: int = Query(1, ge=1),
    taille: int = Query(25, ge=1, le=200),
):
    with transaction() as session:
        return rechercher(session, RESSOURCES[ressource], filtres, page, taille)


@app.get("/v1/{ressource}/{identifiant}", tags=["Catalogue"])
def detail(ressource: Literal["sources", "comptes", "contenus", "tags"], identifiant: int):
    with transaction() as session:
        try:
            return obtenir_fiche(session, RESSOURCES[ressource], identifiant)
        except ErreurMetier:
            raise HTTPException(404, "Fiche introuvable.") from None
