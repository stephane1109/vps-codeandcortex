"""Chaque test utilise une base SQLite temporaire ou un schéma PostgreSQL isolé."""

import os
import re
import uuid
from datetime import timedelta
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from desinfolab.base import moteur, transaction
from desinfolab.configuration import url_base
from desinfolab.contributions import moderer, soumettre
from desinfolab.modeles import Contribution, Defi, maintenant
from desinfolab.securite import connecter_admin, creer_defi, hacher_mot_de_passe

RACINE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def base_isolee(tmp_path, monkeypatch):
    parent = os.getenv("TEST_DATABASE_URL")
    schema = "test_" + uuid.uuid4().hex
    admin_engine = None
    if parent:
        admin_engine = create_engine(parent)
        with admin_engine.begin() as connexion:
            connexion.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = (
            make_url(parent)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
    else:
        url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("APP_SECRET", "secret-de-test-uniquement-" * 3)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hacher_mot_de_passe("mot-de-passe-de-test"))
    url_base.cache_clear()
    moteur.cache_clear()
    cfg = Config(str(RACINE / "alembic.ini"))
    command.upgrade(cfg, "head")
    yield
    moteur().dispose()
    moteur.cache_clear()
    url_base.cache_clear()
    if admin_engine:
        with admin_engine.begin() as connexion:
            connexion.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin_engine.dispose()


@pytest.fixture
def admin():
    return connecter_admin("mot-de-passe-de-test")


def defi_resolu():
    defi = creer_defi()
    with transaction() as session:
        session.get(Defi, defi["jeton"]).cree_le = maintenant() - timedelta(seconds=3)
    a, b = map(int, re.findall(r"\d+", defi["question"]))
    return defi["jeton"], str(a + b)


def proposer(entite, donnees, **kwargs):
    jeton, reponse = defi_resolu()
    return soumettre(entite, donnees, jeton, reponse, **kwargs)["id"]


def empreinte(identifiant):
    with transaction() as session:
        return session.get(Contribution, identifiant).empreinte


def publier(admin, entite, donnees):
    identifiant = proposer(entite, donnees)
    return moderer(admin, identifiant, "valider", empreinte(identifiant), "Références et contexte vérifiés.")


@pytest.fixture
def source():
    return {
        "nom": "Observatoire exemple",
        "url": "https://example.org/",
        "description": "Une fiche de test fictive.",
        "pays": "France",
        "langue": "fr",
        "plateforme_id": 9,
        "tags": [],
        "references": [],
    }


@pytest.fixture
def reference():
    return {
        "titre": "Étude de contexte",
        "url": "https://example.com/etude",
        "type_reference": "scientifique",
        "citation": "Extrait documenté",
        "qualification_tag_id": None,
    }
