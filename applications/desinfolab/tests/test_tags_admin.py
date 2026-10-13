"""Les visiteurs consultent les tags ; seuls les administrateurs les gèrent."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from streamlit.testing.v1 import AppTest
from desinfolab.api import app
from desinfolab.base import transaction
from desinfolab.catalogue import donnees_editables, obtenir_fiche
from desinfolab.contributions import enregistrer_tag, soumettre
from desinfolab.interface import PAGES
from desinfolab.modeles import Contribution, Historique, Tag
from desinfolab.securite import ErreurMetier
from conftest import RACINE

DONNEES = {"nom": "Sciences", "nature": "thematique"}


@pytest.mark.parametrize("cible", [None, 1])
def test_soumission_publique_tag_interdite(cible):
    with pytest.raises(ErreurMetier, match="réservées à l'administration"):
        soumettre("tag", DONNEES, "", "", cible_id=cible)
    with transaction() as session:
        assert session.scalar(select(func.count()).select_from(Contribution)) == 0


@pytest.mark.parametrize("jeton", [None, "faux"])
@pytest.mark.parametrize("identifiant", [None, 1])
def test_gestion_tag_exige_admin(jeton, identifiant):
    with pytest.raises(ErreurMetier, match="Session"):
        enregistrer_tag(jeton, DONNEES, "Création", identifiant=identifiant)


def test_creation_modification_audit_et_version(admin, reference):
    identifiant = enregistrer_tag(admin, {**DONNEES, "references": [reference]}, "Création documentée")
    with transaction() as session:
        donnees = donnees_editables(session, "tag", identifiant)
    enregistrer_tag(admin, {**donnees, "nom": "Sciences et recherche"}, "Nom précisé", identifiant, 1)
    with transaction() as session:
        fiche = obtenir_fiche(session, "tag", identifiant)
        assert fiche["nom"] == "Sciences et recherche"
        assert fiche["version"] == 2
        assert fiche["references"][0]["url"] == reference["url"]
        actions = list(session.scalars(select(Historique).order_by(Historique.id)))
        assert [h.action for h in actions] == ["creation", "modification"]
        assert actions[1].avant["nom"] == "Sciences"
        assert actions[1].apres["nom"] == "Sciences et recherche"
    with pytest.raises(ErreurMetier, match="autre session"):
        enregistrer_tag(admin, DONNEES, "Ancien formulaire", identifiant, 1)
    with pytest.raises(ErreurMetier, match="nature.*stable"):
        enregistrer_tag(admin, {**DONNEES, "nature": "discours"}, "Changer famille", identifiant, 2)


def test_doublon_et_motif_obligatoire(admin):
    with pytest.raises(ErreurMetier, match="motif"):
        enregistrer_tag(admin, DONNEES, " ")
    enregistrer_tag(admin, DONNEES, "Création")
    with pytest.raises(ErreurMetier, match="existe déjà"):
        enregistrer_tag(admin, {**DONNEES, "nom": "SCIENCES"}, "Doublon")


def test_api_tags_lecture_seule(admin):
    identifiant = enregistrer_tag(admin, DONNEES, "Création")
    client = TestClient(app)
    assert client.get("/v1/tags").status_code == 200
    for methode in (client.post, client.put, client.patch, client.delete):
        assert methode(f"/v1/tags/{identifiant}").status_code == 405
    assert client.post("/v1/tags", json=DONNEES).status_code == 405


def test_interface_tags_admin_et_lecture_publique(admin):
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=15).run()
    at.session_state["admin"] = admin
    at.sidebar.radio[0].set_value(PAGES[5]).run()
    next(w for w in at.radio if w.label == "Espace de gestion").set_value("Tags").run()
    next(w for w in at.text_input if w.label == "Nom du tag").set_value("Sciences")
    assert not any("motif" in w.label.lower() for w in at.text_input)
    next(w for w in at.button if w.label == "Créer le tag").click().run()
    assert not at.exception and not at.error
    next(w for w in at.radio if w.label == "Gestion des tags").set_value("Modifier / supprimer un tag").run()
    next(w for w in at.text_input if w.label == "Nom du tag").set_value("Sciences et recherche")
    assert not any("motif" in w.label.lower() for w in at.text_input)
    next(w for w in at.button if w.label == "Enregistrer le tag").click().run()
    assert not at.exception and not at.error
    with transaction() as session:
        tag = session.scalar(select(Tag))
        assert tag.nom == "Sciences et recherche" and tag.version == 2
        identifiant = tag.id
    next(w for w in at.button if w.label == "Se déconnecter").click().run()
    assert not any(w.label == "Gestion des tags" for w in at.radio)
    at.sidebar.radio[0].set_value(PAGES[3]).run()
    assert "Tag" not in next(w for w in at.selectbox if w.label == "Type de proposition").options
    at.sidebar.radio[0].set_value(PAGES[4]).run()
    assert not any(w.label == "Proposer un nouveau tag" for w in at.button)
    at.session_state["fiche_entite"] = "tag"
    at.session_state["fiche_id"] = identifiant
    at.sidebar.radio[0].set_value(PAGES[2]).run()
    assert not at.exception and not at.error
    assert not any(w.label == "Proposer une modification de cette fiche" for w in at.button)
    at.session_state["modifier_cible"] = ("tag", identifiant)
    at.sidebar.radio[0].set_value(PAGES[3]).run()
    assert not at.exception
    assert any("réservées à l'administration" in w.value for w in at.info)
    assert not any(w.label == "Envoyer pour validation" for w in at.button)


def test_supprimer_tag_et_conserver_historique(admin, reference):
    from desinfolab.contributions import supprimer_tag
    from desinfolab.modeles import Reference

    identifiant = enregistrer_tag(admin, {**DONNEES, "references": [reference]}, "Création")
    supprimer_tag(admin, identifiant, 1)
    with transaction() as session:
        assert session.get(Tag, identifiant) is None
        assert session.scalar(select(func.count()).select_from(Reference)) == 0
        historique = session.scalar(select(Historique).where(Historique.action == "suppression"))
        assert historique.avant["nom"] == "Sciences"
        assert historique.avant["references"][0]["url"] == reference["url"]
    with pytest.raises(ErreurMetier, match="n'existe plus"):
        supprimer_tag(admin, identifiant, 1)


def test_suppression_tag_authentification_et_version(admin):
    from desinfolab.contributions import supprimer_tag

    identifiant = enregistrer_tag(admin, DONNEES, "Création")
    with pytest.raises(ErreurMetier, match="Session"):
        supprimer_tag(None, identifiant, 1)
    enregistrer_tag(admin, {**DONNEES, "nom": "Recherche"}, "Correction", identifiant, 1)
    with pytest.raises(ErreurMetier, match="autre session"):
        supprimer_tag(admin, identifiant, 1)
    with transaction() as session:
        assert session.get(Tag, identifiant).nom == "Recherche"


@pytest.mark.parametrize("publie", [False, True])
def test_suppression_tag_utilise_refusee(admin, source, publie):
    from desinfolab.contributions import supprimer_tag
    from conftest import proposer, publier

    identifiant = enregistrer_tag(admin, DONNEES, "Création")
    donnees = {**source, "tags": [identifiant]}
    if publie:
        publier(admin, "source", donnees)
    else:
        proposer("source", donnees)
    with pytest.raises(ErreurMetier, match="publiées" if publie else "en attente"):
        supprimer_tag(admin, identifiant, 1)
    with transaction() as session:
        assert session.get(Tag, identifiant) is not None
        assert (
            session.scalar(
                select(func.count()).select_from(Historique).where(Historique.action == "suppression")
            )
            == 0
        )


def test_suppression_ancien_parent_refusee(admin):
    from desinfolab.contributions import supprimer_tag

    identifiant = enregistrer_tag(admin, DONNEES, "Création")
    enregistrer_tag(admin, {**DONNEES, "nom": "Santé", "parent_id": identifiant}, "Ancienne hiérarchie")
    with pytest.raises(ErreurMetier, match="rattachés"):
        supprimer_tag(admin, identifiant, 1)


def test_interface_suppression_et_absence_champ_parent(admin):
    identifiant = enregistrer_tag(admin, DONNEES, "Création")
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=15).run()
    at.session_state["admin"] = admin
    at.sidebar.radio[0].set_value(PAGES[5]).run()
    next(w for w in at.radio if w.label == "Espace de gestion").set_value("Tags").run()
    assert not any(terme in w.label.lower() for w in at.selectbox for terme in ("parent", "famille"))
    next(w for w in at.radio if w.label == "Gestion des tags").set_value("Modifier / supprimer un tag").run()
    assert not any(terme in w.label.lower() for w in at.selectbox for terme in ("parent", "famille"))
    assert next(w for w in at.button if w.label == "Supprimer le tag").disabled
    next(w for w in at.checkbox if w.label.startswith("Confirmer la suppression du tag")).check().run()
    next(w for w in at.button if w.label == "Supprimer le tag").click().run()
    assert not at.exception and not at.error
    with transaction() as session:
        assert session.get(Tag, identifiant) is None
    assert any("Tag supprimé" in w.value for w in at.success)
    at.sidebar.radio[0].set_value(PAGES[4]).run()
    assert not at.exception and not at.error
    assert not any(w.label == "Hiérarchie complète" for w in at.expander)
    assert not any(terme in w.label.lower() for w in at.selectbox for terme in ("parent", "famille"))
    assert not any(col in at.dataframe[0].value.columns for col in ("Famille", "Parent"))
