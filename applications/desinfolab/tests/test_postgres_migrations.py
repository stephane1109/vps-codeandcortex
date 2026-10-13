"""Régressions de migration et verrous réels PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from desinfolab.base import moteur, transaction
from desinfolab.contributions import moderer
from desinfolab.modeles import Contribution, Historique, Plateforme, Source
from desinfolab.securite import ErreurMetier, verifier_defi
from conftest import RACINE, defi_resolu, empreinte, proposer


def test_migrations_aller_retour_et_coherence():
    config = Config(str(RACINE / "alembic.ini"))
    command.downgrade(config, "0001")
    command.upgrade(config, "head")
    with transaction() as session:
        assert session.scalar(select(func.count()).select_from(Plateforme)) == 14
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)


def test_deux_moderateurs_ne_publient_qu_une_fois(admin, source):
    if moteur().dialect.name != "postgresql":
        pytest.skip("Ce test exige les verrous PostgreSQL.")
    cid = proposer("source", source)
    attendu = empreinte(cid)
    barriere = Barrier(2)

    def decision():
        barriere.wait(timeout=5)
        try:
            return moderer(admin, cid, "valider", attendu, "Relecture concurrente")
        except ErreurMetier as erreur:
            return str(erreur)

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultats = list(pool.map(lambda _: decision(), range(2)))
    assert sum(isinstance(r, int) for r in resultats) == 1
    assert any("plus en attente" in str(r) for r in resultats)
    with transaction() as session:
        assert session.scalar(select(func.count()).select_from(Source)) == 1
        assert (
            session.scalar(select(func.count()).select_from(Historique).where(Historique.action == "validee"))
            == 1
        )
        assert session.get(Contribution, cid).statut == "validee"


def test_defi_ne_peut_etre_consomme_deux_fois_en_parallele():
    if moteur().dialect.name != "postgresql":
        pytest.skip("Ce test exige les verrous PostgreSQL.")
    jeton, reponse = defi_resolu()
    barriere = Barrier(2)

    def essayer():
        barriere.wait(timeout=5)
        try:
            verifier_defi(jeton, reponse)
            return True
        except ErreurMetier:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: essayer(), range(2))) == [False, True]
