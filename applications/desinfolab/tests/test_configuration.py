"""Régressions des URL Coolify et des erreurs sans divulgation de secrets."""

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError
from streamlit.testing.v1 import AppTest
from desinfolab.configuration import ErreurConfiguration, secret_application, url_base
from desinfolab.base import moteur
from desinfolab.diagnostic import diagnostic_base
from conftest import RACINE


@pytest.mark.parametrize("prefixe", ["postgres", "postgresql", "postgresql+psycopg"])
def test_url_coolify_copiee_directement(monkeypatch, prefixe):
    with monkeypatch.context() as env:
        env.setenv(
            "DATABASE_URL",
            f"{prefixe}://lecteur:secret%40fictif@postgres-interne:5432/desinfolab?sslmode=prefer",
        )
        url_base.cache_clear()
        url = url_base()
        assert url.drivername == "postgresql+psycopg"
        assert url.username == "lecteur"
        assert url.password == "secret@fictif"
        assert url.host == "postgres-interne" and url.port == 5432
        assert url.database == "desinfolab" and url.query["sslmode"] == "prefer"
    url_base.cache_clear()


def test_ligne_env_collee_dans_valeur(monkeypatch):
    with monkeypatch.context() as env:
        env.setenv("DATABASE_URL", "DATABASE_URL=postgres://lecteur:fictif@db:5432/desinfolab")
        url_base.cache_clear()
        assert url_base().host == "db"
    url_base.cache_clear()


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://desinfolab:secret-fictif:5432/desinfolab",
        "postgresql+psycopg://desinfolab//secret-fictif:5432/desinfolab",
        "postgres://lecteur:secret-fictif@db/",
        "secret-fictif",
    ],
)
def test_url_invalide_sans_secret_dans_message(monkeypatch, url):
    with monkeypatch.context() as env:
        env.setenv("DATABASE_URL", url)
        url_base.cache_clear()
        with pytest.raises(ErreurConfiguration) as erreur:
            url_base()
        assert "secret-fictif" not in str(erreur.value)
        assert "DATABASE_URL" in str(erreur.value)
    url_base.cache_clear()


@pytest.mark.parametrize("configuration", ["absente", "url_invalide", "tables_absentes"])
def test_accueil_affiche_diagnostic_au_lieu_erreur_streamlit(monkeypatch, tmp_path, configuration):
    moteur_initial = moteur()
    try:
        with monkeypatch.context() as env:
            if configuration == "absente":
                env.delenv("DATABASE_URL", raising=False)
                env.delenv("POSTGRES_PASSWORD", raising=False)
                attendu = "Connexion à la base non configurée"
            elif configuration == "url_invalide":
                env.setenv("DATABASE_URL", "postgresql+psycopg://desinfolab:secret-fictif:5432/desinfolab")
                attendu = "DATABASE_URL est invalide"
            else:
                env.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vide.db'}")
                attendu = "Les tables de DésinfoLab sont absentes"
            url_base.cache_clear()
            moteur.cache_clear()
            at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=15).run()
            assert not at.exception
            assert attendu in at.error[0].value
            assert "secret-fictif" not in at.error[0].value
            if configuration == "tables_absentes":
                moteur().dispose()
    finally:
        moteur_initial.dispose()
        moteur.cache_clear()
        url_base.cache_clear()


def test_secret_court_est_une_erreur_configuration_controlee(monkeypatch):
    monkeypatch.setenv("APP_SECRET", "fictif")
    with pytest.raises(ErreurConfiguration, match="APP_SECRET"):
        secret_application()


@pytest.mark.parametrize(
    "code,attendu",
    [
        ("28P01", "refuse les identifiants"),
        ("3D000", "base demandée n'existe pas"),
        ("42P01", "tables de DésinfoLab"),
        ("42703", "tables de DésinfoLab"),
        (None, "Connexion à PostgreSQL impossible"),
    ],
)
def test_diagnostic_postgresql_ne_revele_pas_les_details(code, attendu):
    class Origine(Exception):
        sqlstate = code

    erreur = OperationalError(
        "SELECT secret-fictif", {"mot_de_passe": "secret-fictif"}, Origine("secret-fictif")
    )
    message = diagnostic_base(erreur)
    assert attendu in message
    assert "secret-fictif" not in message
    erreur = ProgrammingError("SELECT secret-fictif", {}, Exception("secret-fictif"))
    assert "secret-fictif" not in diagnostic_base(erreur)
