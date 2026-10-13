import csv
import io
import json
import pytest
from fastapi.testclient import TestClient
from desinfolab.api import app
from desinfolab.base import transaction
from desinfolab.catalogue import iterer_resultats, rechercher
from desinfolab.exports import exporter
from desinfolab.validation import Filtres
from conftest import proposer, publier


@pytest.fixture
def corpus(admin, source):
    parent = publier(admin, "tag", {"nom": "Sciences", "nature": "thematique"})
    enfant = publier(admin, "tag", {"nom": "Santé", "nature": "thematique", "parent_id": parent})
    discours = publier(admin, "tag", {"nom": "Rhétorique", "nature": "discours"})
    sid = publier(admin, "source", {**source, "tags": [enfant]})
    aid = publier(
        admin,
        "compte",
        {
            "source_id": sid,
            "plateforme_id": 1,
            "pseudonyme": "Compte vidéo",
            "url": "https://example.org/chaine",
        },
    )
    c1 = publier(
        admin,
        "contenu",
        {
            "source_id": sid,
            "compte_id": aid,
            "plateforme_id": 1,
            "titre": "Science et santé",
            "url": "https://youtu.be/abcdefghijk",
            "type_media": "video",
            "date": "2026-03-15",
            "tags": [enfant, discours],
        },
    )
    c2 = publier(
        admin,
        "contenu",
        {
            "source_id": sid,
            "plateforme_id": 9,
            "titre": "Note santé",
            "url": "https://example.org/note",
            "type_media": "article",
            "date": "2025-12-01",
            "tags": [enfant],
        },
    )
    c3 = publier(
        admin,
        "contenu",
        {
            "source_id": sid,
            "plateforme_id": 12,
            "titre": "Épisode débat",
            "url": "https://example.org/podcast",
            "type_media": "podcast",
            "tags": [discours],
        },
    )
    return dict(parent=parent, enfant=enfant, discours=discours, sid=sid, aid=aid, contenus=[c1, c2, c3])


def test_recherche_croisee_tags_dates_plateformes_et_hierarchie(corpus):
    with transaction() as session:
        assert rechercher(session, "contenu", Filtres(tags=[corpus["parent"]]))["total"] == 2
        assert (
            rechercher(session, "contenu", Filtres(tags=[corpus["parent"]], descendants=False))["total"] == 0
        )
        assert (
            rechercher(
                session, "contenu", Filtres(tags=[corpus["parent"], corpus["discours"]], operateur="ET")
            )["total"]
            == 1
        )
        assert (
            rechercher(
                session, "contenu", Filtres(tags=[corpus["parent"], corpus["discours"]], operateur="OU")
            )["total"]
            == 3
        )
        f = Filtres(
            texte="santé",
            pays="france",
            langue="FR",
            plateforme_id=1,
            type_media="video",
            date_debut="2026-01-01",
            date_fin="2026-12-31",
            thematique_id=corpus["parent"],
            url="youtu.be",
        )
        resultats = rechercher(session, "contenu", f)
        assert resultats["total"] == 1 and resultats["resultats"][0]["id"] == corpus["contenus"][0]
        assert rechercher(session, "source", Filtres(plateforme_id=1))["total"] == 1
        assert rechercher(session, "compte", Filtres(tags=[corpus["parent"]]))["total"] == 1
        assert rechercher(session, "contenu", Filtres(texte="%"))["total"] == 0


def test_pagination_et_export_complet(corpus):
    with transaction() as session:
        p1 = rechercher(session, "contenu", Filtres(), page=1, taille=2)
        p2 = rechercher(session, "contenu", Filtres(), page=2, taille=2)
        assert p1["total"] == 3 and len(p2["resultats"]) == 1
        assert not {r["id"] for r in p1["resultats"]} & {r["id"] for r in p2["resultats"]}
        resultats = list(iterer_resultats(session, "contenu", Filtres(tags=[corpus["parent"]])))
    assert len(resultats) == 2
    assert exporter(resultats, "txt").decode().splitlines() == [r["url"] for r in resultats]
    assert json.loads(exporter(resultats, "json")) == resultats
    lignes = list(csv.DictReader(io.StringIO(exporter(resultats, "csv").decode("utf-8-sig"))))
    assert len(lignes) == 2 and json.loads(lignes[0]["tags"])[0]["nom"]


def test_csv_protege_formules_et_preserve_json():
    donnees = [
        {
            "id": 1,
            "titre": '=HYPERLINK("https://exemple.fr")',
            "description": "\t=1+1",
            "url": "https://example.org/",
            "tags": [],
        }
    ]
    csv_texte = exporter(donnees, "csv").decode("utf-8-sig")
    ligne = next(csv.DictReader(io.StringIO(csv_texte)))
    assert ligne["titre"].startswith("'=") and ligne["description"].startswith("'\t")
    assert json.loads(exporter(donnees, "json"))[0]["titre"] == donnees[0]["titre"]
    assert json.loads(exporter([], "json")) == []


def test_api_consultation_exports_et_absence_routes_privees(corpus, source):
    proposer("source", {**source, "nom": "PRIVÉ EN ATTENTE", "url": "https://example.net/"})
    with TestClient(app) as client:
        assert client.get("/sante").status_code == 200
        reponse = client.get("/v1/sources")
        assert reponse.status_code == 200 and "PRIVÉ EN ATTENTE" not in reponse.text
        assert reponse.json()["total"] == 1
        assert client.get(f"/v1/sources/{corpus['sid']}").json()["comptes"][0]["id"] == corpus["aid"]
        assert len(client.get("/v1/tags").json()) == 3
        assert client.get(f"/v1/tags/{corpus['parent']}").status_code == 200
        assert client.get("/v1/urls", params={"plateforme_id": 1}).json()["total"] == 1
        for fmt in ("txt", "csv", "json"):
            r = client.get(f"/v1/export/{fmt}", params={"tags": corpus["parent"]})
            assert r.status_code == 200
            assert "podcast" not in r.text
            assert "attachment" in r.headers["content-disposition"]
        assert client.get("/v1/export/json", params={"tags": 99999}).status_code == 422
        assert client.get("/v1/contributions").status_code != 200
        assert client.get("/v1/historique").status_code != 200
        assert client.post("/v1/sources", json=source).status_code == 405
        assert client.get("/v1/sources/999999").status_code == 404
        assert client.get("/v1/contenus", params={"taille": 10000}).status_code == 422
        assert client.get("/v1/contenus", params={"tags": -1}).status_code == 422
        assert (
            client.get(
                "/v1/contenus", params={"date_debut": "2026-01-02", "date_fin": "2026-01-01"}
            ).status_code
            == 422
        )
        assert client.get("/openapi.json").status_code == 200
