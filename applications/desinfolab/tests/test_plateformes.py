"""Gestion administrative des plateformes et conservation des relations."""

import pytest
from sqlalchemy import select
from desinfolab.base import transaction
from desinfolab.contributions import ajouter_plateforme, modifier_plateforme, supprimer_plateforme
from desinfolab.modeles import Historique, Plateforme, Source
from desinfolab.securite import ErreurMetier
from conftest import proposer, publier


def test_cycle_plateforme_et_historique(admin):
    identifiant = ajouter_plateforme(admin, "Nouvelle plateforme")
    modifier_plateforme(admin, identifiant, "  Plateforme renommée  ")
    with transaction() as session:
        assert session.get(Plateforme, identifiant).nom == "Plateforme renommée"
    supprimer_plateforme(admin, identifiant)
    with transaction() as session:
        assert session.get(Plateforme, identifiant) is None
        actions = list(
            session.scalars(
                select(Historique)
                .where(Historique.entite == "plateforme", Historique.entite_id == identifiant)
                .order_by(Historique.id)
            )
        )
        assert [h.action for h in actions] == ["creation", "modification", "suppression"]
        assert actions[1].avant == {"nom": "Nouvelle plateforme"}
        assert actions[2].avant == {"nom": "Plateforme renommée"}


@pytest.mark.parametrize("nom", ["", "   ", "x" * 101, "youtube"])
def test_refuser_nom_invalide_ou_doublon(admin, nom):
    with pytest.raises(ErreurMetier):
        modifier_plateforme(admin, 9, nom)
    with transaction() as session:
        assert session.get(Plateforme, 9).nom == "Site Internet"


@pytest.mark.parametrize(
    "operation",
    [
        lambda jeton: modifier_plateforme(jeton, 9, "Autre"),
        lambda jeton: supprimer_plateforme(jeton, 9),
    ],
)
def test_exiger_administration(operation):
    with pytest.raises(ErreurMetier):
        operation("jeton-invalide")


def test_proteger_contribution_en_attente(admin, source):
    proposer("source", source)
    with pytest.raises(ErreurMetier, match="en attente"):
        supprimer_plateforme(admin, source["plateforme_id"])
    with transaction() as session:
        assert session.get(Plateforme, source["plateforme_id"]) is not None


def test_renommer_plateforme_utilisee_et_refuser_suppression(admin, source):
    identifiant = publier(admin, "source", source)
    modifier_plateforme(admin, source["plateforme_id"], "Sites web")
    with transaction() as session:
        fiche = session.get(Source, identifiant)
        assert fiche.plateforme_id == source["plateforme_id"]
        assert fiche.plateforme.nom == "Sites web"
    with pytest.raises(ErreurMetier, match="publiées"):
        supprimer_plateforme(admin, source["plateforme_id"])


def test_plateforme_supprimee_entre_deux_actions(admin):
    supprimer_plateforme(admin, 7)
    with pytest.raises(ErreurMetier, match="n'existe plus"):
        supprimer_plateforme(admin, 7)
    with pytest.raises(ErreurMetier, match="n'existe plus"):
        modifier_plateforme(admin, 7, "Autre")
