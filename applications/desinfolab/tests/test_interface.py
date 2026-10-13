"""Parcours Streamlit exécutés avec le moteur officiel AppTest."""

import re
from datetime import timedelta
from streamlit.testing.v1 import AppTest
from sqlalchemy import select
from desinfolab.base import transaction
from desinfolab.interface import PAGES
from desinfolab.modeles import Contribution, Defi, maintenant
from conftest import RACINE, publier


def ouvrir(page):
    at = AppTest.from_file(str(RACINE / "app.py"), default_timeout=15).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception
    return at


def test_pages_publiques_et_admin_verrouille():
    for page in (PAGES[0], PAGES[1], PAGES[3], PAGES[4], PAGES[5]):
        at = ouvrir(page)
        assert not at.exception
    assert any("Mot de passe" in w.label for w in at.text_input)


def test_formulaire_source_jusqua_moderation_interface():
    at = ouvrir(PAGES[3])
    at.text_input[0].set_value("Source depuis formulaire")
    at.text_input[1].set_value("https://example.org/formulaire")
    defi = at.session_state["defi"]
    with transaction() as session:
        session.get(Defi, defi["jeton"]).cree_le = maintenant() - timedelta(seconds=3)
    a, b = map(int, re.findall(r"\d+", defi["question"]))
    next(w for w in at.text_input if w.label.startswith("Combien")).set_value(str(a + b))
    next(b for b in at.button if b.label == "Envoyer pour validation").click().run()
    assert not at.exception and not at.error
    with transaction() as session:
        assert session.scalar(select(Contribution)).statut == "en_attente"
    at.sidebar.radio[0].set_value(PAGES[5]).run()
    at.text_input[0].set_value("mot-de-passe-de-test")
    next(b for b in at.button if b.label == "Se connecter").click().run()
    assert not at.exception and not at.error
    next(w for w in at.text_area if w.label == "Justification de la décision").set_value(
        "Formulaire vérifié."
    )
    at.checkbox[-1].check()
    next(b for b in at.button if b.label == "Appliquer la décision").click().run()
    assert not at.exception and not at.error
    with transaction() as session:
        assert session.scalar(select(Contribution)).statut == "validee"


def test_fiche_navigation_et_correction(admin, source):
    sid = publier(admin, "source", source)
    at = ouvrir(PAGES[2])
    assert not at.exception
    next(b for b in at.button if b.label == "Proposer une modification de cette fiche").click().run()
    assert not at.exception
    assert at.session_state["modifier_cible"] == ("source", sid)
    assert at.sidebar.radio[0].value == PAGES[3]


def test_recherche_export_interface(admin, source):
    publier(admin, "source", source)
    at = ouvrir(PAGES[1])
    at.segmented_control[0].set_value("source").run()
    assert not at.exception
    next(b for b in at.button if b.label == "Préparer les exports complets").click().run()
    assert not at.exception
    assert len(at.session_state["export_filtre"]) == 1
