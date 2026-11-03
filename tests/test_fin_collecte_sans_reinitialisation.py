"""Contrôler la fin de collecte sans réinitialisation et le quota Research."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from collecte.presse import charger_inventaire
from webapp import StartRequest, session_terminee_inactive


class TestsFinCollecteSansReinitialisation(unittest.TestCase):
    def parametres_presse(self, moteur, **options):
        media_id = charger_inventaire()[0]["id"]
        return StartRequest(
            source_collecte="presse", presse_moteur=moteur,
            medias=[media_id], nom_sauvegarde="Corpus expérimental",
            **({"research_client_key": "cle_test",
                "research_client_secret": "secret_test"} if moteur == "research"
               else {}), **options)

    def test_research_complet_enregistre_limit_null(self):
        """La limite affichée historiquement à 50 ne doit pas plafonner Research."""
        collecte = self.parametres_presse(
            "research", limit=50, collecte_research_complete=True)
        self.assertIsNone(collecte.limit)
        self.assertIsNone(collecte.model_dump()["limit"])
        self.assertTrue(collecte.collecte_research_complete)

    def test_research_sans_indicateur_historique_reste_illimite(self):
        """Une requête Research API directe doit suivre le même comportement."""
        collecte = self.parametres_presse("research", limit=50)
        self.assertIsNone(collecte.limit)
        self.assertTrue(collecte.collecte_research_complete)

    def test_test_research_reste_limite_a_dix(self):
        """Ne pas supprimer le mode test explicite sur dix publications."""
        collecte = self.parametres_presse(
            "research", test_research_10_publications=True, limit=50)
        self.assertEqual(collecte.limit, 10)
        self.assertEqual(collecte.model_dump()["limit"], 10)

    def test_autres_moteurs_conservent_leur_plafond(self):
        """Le fonctionnement des moteurs non Research ne doit pas changer."""
        collecte = self.parametres_presse("api", limit=50)
        self.assertEqual(collecte.limit, 50)
        with self.assertRaisesRegex(ValueError, "limite numérique"):
            self.parametres_presse("api", limit=None)

    def test_session_terminee_consultee_ne_peut_pas_expirer(self):
        """Une session active en consultation reste visible et téléchargeable."""
        session = SimpleNamespace(
            busy=False, video_busy=False, finished=100.0, last_seen=195.0)
        self.assertFalse(session_terminee_inactive(session, 201.0, 50.0))
        self.assertTrue(session_terminee_inactive(session, 300.0, 50.0))
        session.busy = True
        self.assertFalse(session_terminee_inactive(session, 300.0, 50.0))

    def test_finalisation_n_execute_plus_de_rechargement_global(self):
        """Le passage à terminé doit afficher les résultats sans st.rerun()."""
        interface = (Path(__file__).resolve().parents[1] /
                     "streamlit_app.py").read_text(encoding="utf-8")
        debut = interface.index("def afficher_resultats():")
        fin = interface.index('if actuel.get("source_collecte") == "presse":', debut)
        transition = interface[debut:fin]
        self.assertNotIn("st.rerun()", transition)
        self.assertIn('actuel.get("status") in ("completed", "partial", "stopped")',
                      transition)
        self.assertIn("Télécharger les résultats", interface)
        self.assertIn('valeurs["limit"] = (', interface)


if __name__ == "__main__":
    unittest.main()
