import json
from datetime import timedelta
import pytest
from sqlalchemy import func, select
from desinfolab.base import transaction
from desinfolab.catalogue import obtenir_fiche, rechercher
from desinfolab.contributions import ajouter_plateforme, moderer, reviser_proposition
from desinfolab.modeles import Contribution, Defi, Historique, Source, maintenant
from desinfolab.securite import ErreurMetier, connecter_admin, creer_defi, exiger_admin, verifier_defi
from desinfolab.validation import Filtres, canonicaliser_url, valider_url
from conftest import defi_resolu, empreinte, proposer, publier


def test_proposition_privee_puis_publication_et_historique(admin, source):
    identifiant = proposer("source", source)
    with transaction() as session:
        assert rechercher(session, "source", Filtres())["total"] == 0
        assert session.get(Contribution, identifiant).statut == "en_attente"
    source_id = moderer(admin, identifiant, "valider", empreinte(identifiant), "Vérification documentaire.")
    with transaction() as session:
        assert rechercher(session, "source", Filtres())["total"] == 1
        fiche = obtenir_fiche(session, "source", source_id)
        assert fiche["qualifications"] == []
        assert session.scalar(select(func.count()).select_from(Historique)) == 2
    with pytest.raises(ErreurMetier, match="plus en attente"):
        moderer(admin, identifiant, "valider", empreinte(identifiant), "Deuxième validation.")


def test_refus_sans_publication(admin, source):
    identifiant = proposer("source", source)
    moderer(admin, identifiant, "refuser", empreinte(identifiant), "Référence insuffisante.")
    with transaction() as session:
        assert session.get(Contribution, identifiant).statut == "refusee"
        assert session.scalar(select(func.count()).select_from(Source)) == 0


def test_aucune_moderation_sans_authentification(source):
    identifiant = proposer("source", source)
    with pytest.raises(ErreurMetier, match="Session"):
        moderer(None, identifiant, "valider", empreinte(identifiant), "Motif")
    with pytest.raises(ErreurMetier, match="Session"):
        ajouter_plateforme("faux", "Nouvelle")


def test_doublon_proposition_et_publication(admin, source):
    identifiant = proposer("source", source)
    with pytest.raises(ErreurMetier, match="identique"):
        proposer("source", source)
    moderer(admin, identifiant, "valider", empreinte(identifiant), "Vérifié")
    autre = proposer(
        "source", {**source, "url": "https://example.org/?utm_source=lettre", "description": "Complément"}
    )
    with pytest.raises(ErreurMetier, match="Doublon"):
        moderer(admin, autre, "valider", empreinte(autre), "Vérifié")
    with transaction() as session:
        assert session.get(Contribution, autre).statut == "en_attente"


def test_fusion_enrichit_sans_ecraser(admin, source, reference):
    sid = publier(admin, "source", source)
    tag = publier(admin, "tag", {"nom": "Santé", "nature": "thematique"})
    cid = proposer("source", {**source, "nom": "Autre nom", "tags": [tag], "references": [reference]})
    moderer(admin, cid, "fusionner", empreinte(cid), "Même source, références complémentaires", sid)
    with transaction() as session:
        fiche = obtenir_fiche(session, "source", sid)
        assert fiche["nom"] == source["nom"]
        assert [t["id"] for t in fiche["tags"]] == [tag]
        assert fiche["references"][0]["url"] == reference["url"]
        assert fiche["version"] == 2


def test_qualification_exige_justification_par_tag(admin, source, reference):
    q = publier(
        admin, "tag", {"nom": "Affirmation réfutée", "nature": "qualification", "references": [reference]}
    )
    with pytest.raises(ErreurMetier, match="Chaque qualification"):
        proposer("source", {**source, "tags": [q], "references": [reference]})
    sid = publier(
        admin, "source", {**source, "tags": [q], "references": [{**reference, "qualification_tag_id": q}]}
    )
    with transaction() as session:
        fiche = obtenir_fiche(session, "source", sid)
        assert fiche["qualifications"] == ["Affirmation réfutée"]
        assert fiche["references"][0]["qualification_tag_id"] == q


def test_qualification_ne_peut_etre_creee_sans_reference():
    with pytest.raises(ErreurMetier, match="référence documentaire"):
        proposer("tag", {"nom": "Qualification", "nature": "qualification"})


def test_modifications_concurrentes_et_revision_explicite(admin, source):
    sid = publier(admin, "source", source)
    a = proposer("source", {**source, "nom": "Correction A"}, cible_id=sid, version_cible=1)
    b = proposer("source", {**source, "nom": "Correction B"}, cible_id=sid, version_cible=1)
    moderer(admin, a, "valider", empreinte(a), "Correction")
    with pytest.raises(ErreurMetier, match="Conflit de version"):
        moderer(admin, b, "valider", empreinte(b), "Correction")
    reviser_proposition(
        admin, b, {**source, "nom": "Correction B relue"}, empreinte(b), "Comparaison faite", rebaser=True
    )
    moderer(admin, b, "valider", empreinte(b), "Correction relue")
    with transaction() as session:
        assert session.get(Source, sid).version == 3
        assert (
            session.scalar(select(Historique).where(Historique.action == "revision")).avant["nom"]
            == "Correction B"
        )


def test_revision_proposition_ne_publie_pas_et_protege_contre_revision_concurrente(admin, source):
    cid = proposer("source", source)
    ancienne = empreinte(cid)
    reviser_proposition(admin, cid, {**source, "nom": "Nom corrigé"}, ancienne, "Correction de forme")
    with transaction() as session:
        assert rechercher(session, "source", Filtres())["total"] == 0
    with pytest.raises(ErreurMetier, match="révisée"):
        moderer(admin, cid, "valider", ancienne, "Motif")


def test_tags_cycles_et_parent_meme_nature(admin):
    parent = publier(admin, "tag", {"nom": "Sciences", "nature": "thematique"})
    enfant = publier(admin, "tag", {"nom": "Santé", "nature": "thematique", "parent_id": parent})
    with pytest.raises(ErreurMetier, match="cycle"):
        proposer(
            "tag",
            {"nom": "Sciences", "nature": "thematique", "parent_id": enfant},
            cible_id=parent,
            version_cible=1,
        )
    with pytest.raises(ErreurMetier, match="même nature"):
        proposer("tag", {"nom": "Récit", "nature": "discours", "parent_id": parent})


def test_nouvelle_plateforme_et_relations_compte_contenu(admin, source):
    plateforme = ajouter_plateforme(admin, "Plateforme de recherche")
    sid = publier(admin, "source", source)
    aid = publier(
        admin,
        "compte",
        {
            "pseudonyme": "Compte exemple",
            "url": "https://example.org/compte",
            "source_id": sid,
            "plateforme_id": plateforme,
        },
    )
    donnees = {
        "titre": "Vidéo",
        "url": "https://example.org/video",
        "type_media": "video",
        "source_id": sid,
        "compte_id": aid,
        "plateforme_id": plateforme,
        "date": "2026-01-10",
    }
    cid = publier(admin, "contenu", donnees)
    with transaction() as session:
        fiche = obtenir_fiche(session, "source", sid)
        assert fiche["comptes"][0]["id"] == aid
        assert fiche["contenus"][0]["id"] == cid
    with pytest.raises(ErreurMetier, match="correspondre"):
        proposer("contenu", {**donnees, "url": "https://example.org/autre", "plateforme_id": 1})


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "http://localhost/",
        "http://127.0.0.1/",
        "http://[::1]/",
        "https://user:password@example.com/",
        "https://example.com:8000/",
        "http://192.168.1.1/",
        "http://2130706433/",
        "https://example.com/\nmalveillant",
    ],
)
def test_url_dangereuse_rejetee(url):
    with pytest.raises(ValueError):
        valider_url(url)


def test_canonicalisation_conserve_identite_video():
    canonique = canonicaliser_url("https://youtu.be/abcdefghijk?t=10&utm_source=mail")
    assert canonique == canonicaliser_url("https://www.youtube.com/shorts/abcdefghijk")
    assert canonique != canonicaliser_url("https://www.youtube.com/watch?v=abcdefghiJL")
    assert canonicaliser_url("https://example.org/A/") != canonicaliser_url("https://example.org/a/")


def test_defi_usage_unique_mauvaise_reponse_et_honeypot():
    jeton, reponse = defi_resolu()
    with pytest.raises(ErreurMetier, match="échouée"):
        verifier_defi(jeton, "-1")
    with pytest.raises(ErreurMetier):
        verifier_defi(jeton, reponse)
    jeton, reponse = defi_resolu()
    with pytest.raises(ErreurMetier):
        verifier_defi(jeton, reponse, "robot")
    jeton, reponse = defi_resolu()
    verifier_defi(jeton, reponse)
    with pytest.raises(ErreurMetier):
        verifier_defi(jeton, reponse)


def test_defi_trop_rapide_et_expire():
    defi = creer_defi()
    with pytest.raises(ErreurMetier):
        verifier_defi(defi["jeton"], "0")
    jeton, reponse = defi_resolu()
    with transaction() as session:
        session.get(Defi, jeton).cree_le = maintenant() - timedelta(hours=1)
    with pytest.raises(ErreurMetier):
        verifier_defi(jeton, reponse)


def test_quota_sans_identification(monkeypatch, source):
    monkeypatch.setenv("SOUMISSIONS_PAR_HEURE", "1")
    proposer("source", source)
    with pytest.raises(ErreurMetier, match="Limite"):
        proposer("source", {**source, "url": "https://example.net/"})
    with transaction() as session:
        c = session.scalar(select(Contribution))
        donnees = json.dumps(c.donnees)
        assert "email" not in donnees and "adresse_ip" not in donnees
        assert not {"ip", "email", "user_agent", "contributeur_id"} & set(
            Contribution.__table__.columns.keys()
        )


def test_connexion_session_et_echecs_limites():
    jeton = connecter_admin("mot-de-passe-de-test")
    exiger_admin(jeton)
    with pytest.raises(ErreurMetier):
        exiger_admin(jeton[:-1] + ("a" if jeton[-1] != "a" else "b"))
    for _ in range(29):
        with pytest.raises(ErreurMetier, match="incorrect"):
            connecter_admin("incorrect")
    with pytest.raises(ErreurMetier, match="Limite"):
        connecter_admin("mot-de-passe-de-test")
