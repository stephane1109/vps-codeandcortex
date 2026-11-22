"""Tester la variable sociologique de ville sans géolocalisation inventée."""

import ast
import unittest
from pathlib import Path

from collecte.ville_etude import normaliser_ville_etude, balise_ville_etude
from collecte.import_comptes_csv import lire_plusieurs_csv
from corpus.corpus_legendes import construire_legendes
from corpus.corpus_commentaires import construire_commentaires
from corpus.export_iramuteq import construire_corpus
from corpus.publications_csv import COLONNES_PUBLICATIONS_CSV, ligne_publication_csv
from webapp import StartRequest, entete_publication, text_export


RACINE = Path(__file__).resolve().parents[1]


def requete(source="comptes", ville="Toulouse"):
    """Construire des paramètres locaux sans clé ni appel réseau TikTok."""
    donnees = {
        "source_collecte": source,
        "hashtags_saisis": ["manifestation"],
        "hashtag_moteur": "navigateur",
        "profil_moteur": "navigateur",
        "ville_etude": ville,
    }
    if source == "comptes":
        donnees["comptes"] = ["microbalade"]
    return StartRequest.model_validate(donnees)


class TestVilleEtudeIramuteq(unittest.TestCase):
    def test_normalisation_de_la_ville_et_balise(self):
        self.assertEqual(normaliser_ville_etude("Toulouse"), "toulouse")
        self.assertEqual(normaliser_ville_etude("Saint-Étienne"), "saint_etienne")
        self.assertEqual(balise_ville_etude("Toulouse"), "*ville_toulouse")
        self.assertEqual(balise_ville_etude("*ville_Toulouse"), "*ville_toulouse")
        self.assertEqual(balise_ville_etude(""), "")
        self.assertEqual(balise_ville_etude("Paris ****"), "*ville_paris")
        with self.assertRaises(ValueError):
            normaliser_ville_etude("!" * 81)

    def test_ville_reservee_au_mode_comptes(self):
        self.assertEqual(requete().ville_etude, "toulouse")
        self.assertEqual(requete("hashtags").ville_etude, "")

    def test_entete_txt_conserve_les_autres_variables(self):
        video = {
            "id": "1234", "author": "compte_test",
            "created_at": "2026-11-05T12:00:00Z",
            "ville_etude": "toulouse",
        }
        entete = entete_publication(video, ["date", "profil", "id"])
        self.assertIn("*ville_toulouse", entete)
        self.assertIn("*id_1234", entete)
        self.assertIn("*profil_", entete)
        self.assertEqual(entete.count("*ville_toulouse"), 1)
        video.pop("ville_etude")
        self.assertNotIn("*ville_", entete_publication(video, ["id"]))

    def test_original_et_ia_portent_meme_ville(self):
        video = {
            "id": "1234", "author": "compte_test",
            "created_at": "2026-11-05T12:00:00Z",
            "description": "Manifestation à Toulouse",
            "resume_ia_tiktok": "Manifestation étudiante",
            "ville_etude": "toulouse", "engagement": {},
        }
        texte = text_export(
            [video], include_sources=True,
            variables_txt=["date", "profil", "id"],
            inclure_texte_genere_ia=True)
        self.assertEqual(texte.count("*ville_toulouse"), 2)
        self.assertIn("*source_original", texte)
        self.assertIn("*source_ia", texte)

    def test_corpus_legendes_et_commentaires(self):
        publication = {
            "id": "1234", "author": "compte_test", "retenue": True,
            "description": "Manifestation pacifique", "ville_etude": "toulouse",
        }
        corpus = construire_corpus(construire_legendes([publication]))
        self.assertIn("*ville_toulouse", corpus)
        commentaire = {
            "id": "987", "publication_id": "1234",
            "texte": "Solidarité", "ville_etude": "toulouse",
        }
        corpus_commentaires = construire_corpus(
            construire_commentaires([commentaire]))
        self.assertIn("*ville_toulouse", corpus_commentaires)

    def test_csv_territorial_unique_ou_mixte(self):
        csv_toulouse = (
            "territoire;username\n"
            "Toulouse;@microbalade\n"
            "Toulouse;@actutoulouse\n"
        ).encode("utf-8")
        resultat = lire_plusieurs_csv([("comptes.csv", csv_toulouse)])
        self.assertEqual(resultat["territoire_commun"], "Toulouse")
        self.assertEqual(resultat["comptes"],
                         ["microbalade", "actutoulouse"])
        csv_paris = (
            "territoire;username\n"
            "Paris;@autrecompte\n"
        ).encode("utf-8")
        multi = lire_plusieurs_csv(
            [("toulouse.csv", csv_toulouse), ("paris.csv", csv_paris)])
        self.assertEqual(multi["territoire_commun"], "")
        self.assertEqual(set(multi["territoires"]), {"Toulouse", "Paris"})
        sans_ville = lire_plusieurs_csv([
            ("comptes.csv", b"username\n@microbalade\n")])
        self.assertEqual(sans_ville["territoire_commun"], "")

    def test_csv_publication_contient_ville(self):
        self.assertIn("ville_etude", COLONNES_PUBLICATIONS_CSV)
        video = {"id": "1234", "author": "compte_test",
                 "ville_etude": "toulouse", "engagement": {}}
        self.assertEqual(ligne_publication_csv(video)["ville_etude"],
                         "toulouse")

    def test_transfert_territorial_et_interface(self):
        interface = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        territoire = (RACINE / "collcompte.py").read_text(encoding="utf-8")
        moteur = (RACINE / "webapp.py").read_text(encoding="utf-8")
        for source in (interface, territoire, moteur):
            ast.parse(source)
        self.assertIn('key="ville_etude"', interface)
        self.assertIn('"ville_etude_en_attente"', territoire)
        self.assertIn('valeurs["ville_etude"] = (', interface)
        self.assertIn('record["ville_etude"] = job.settings.ville_etude',
                      moteur)
        self.assertIn('self.ville_etude = ""', moteur)


if __name__ == "__main__":
    unittest.main()
