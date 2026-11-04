"""Régressions des séquences Research hashtags, sans appel au réseau TikTok."""
import json
import unittest
from datetime import date
from pathlib import Path

from collecte.researchapi import collecter_videos_presse_research
from collecte.suivi_hashtags import positions_pagination_research


DATE_FIXE = date(2026, 10, 25)


def video(numero):
    """Construire un candidat Research comportant un hashtag vérifiable."""
    return {
        "id": str(7000000000000000000 + numero),
        "username": "exemple",
        "video_description": "Manifestation #17octobre",
        "hashtag_names": ["17octobre"],
        "region_code": "FR",
        "create_time": 1760000000,
        "view_count": 15,
        "like_count": 2,
        "comment_count": 1,
        "share_count": 0,
    }


def interroger(requete, rapport, **options):
    """Exécuter une recherche dans une fenêtre fixe pour rendre les tests reproductibles."""
    return collecter_videos_presse_research(
        None, None, rapport, hashtag="17octobre", requete=requete,
        jeton="jeton_simule", debut="2026-10-01", fin="2026-10-25",
        aujourd_hui=DATE_FIXE, pause=lambda _: None, **options,
    )


class TestsSequencesHashtagsResearch(unittest.TestCase):
    def test_deux_sequences_reprennent_exactement_la_page_suivante(self):
        """Le second lot ne doit pas reconsommer les pages du premier."""
        appels = []

        def api(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            curseur = corps.get("cursor")
            if curseur is None:
                return {"data": {"videos": [video(1), video(2)],
                                 "has_more": True, "cursor": 2,
                                 "search_id": "recherche_stable"}}
            if curseur == 2:
                return {"data": {"videos": [video(3)], "has_more": True,
                                 "cursor": 3, "search_id": "recherche_stable"}}
            self.assertEqual(curseur, 3)
            self.assertEqual(corps["search_id"], "recherche_stable")
            return {"data": {"videos": [video(4)], "has_more": False}}

        premier = {}
        urls_premier = interroger(
            api, premier, maximum_candidats=1000, maximum_requetes=2)
        self.assertEqual(len(urls_premier), 3)
        self.assertEqual(premier["discovery_stop"], "lot_termine")
        self.assertEqual(premier["requetes_tentees"], 2)
        position = premier["reprise_pagination_research"]
        self.assertEqual(position["cursor"], 3)
        self.assertEqual(position["search_id"], "recherche_stable")
        journal = [{"source": "#17octobre", "statut_source": "partielle",
                    "rapport": premier}]
        restauree = positions_pagination_research(journal, ["17octobre"])
        second = {}
        urls_second = interroger(
            api, second, maximum_candidats=1000,
            maximum_requetes=2, position_reprise=restauree["#17octobre"])
        self.assertEqual(len(urls_second), 1)
        self.assertEqual(len(set(urls_premier + urls_second)), 4)
        self.assertEqual(len(appels), 3)
        self.assertEqual(appels[2]["cursor"], 3)
        self.assertEqual(appels[2]["start_date"], appels[0]["start_date"])
        self.assertEqual(appels[2]["end_date"], appels[0]["end_date"])
        self.assertIsNone(second["reprise_pagination_research"])
        self.assertFalse(second["collecte_partielle"])

    def test_interruption_pendant_la_lecture_rejoue_seulement_la_page_inachevee(self):
        """La position validée n'avance qu'après la fin du callback."""
        appels = []

        def api(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            if corps.get("cursor") is None:
                return {"data": {"videos": [video(1)], "has_more": True,
                                 "cursor": 1, "search_id": "id1"}}
            self.assertEqual(corps["cursor"], 1)
            return {"data": {"videos": [video(2)], "has_more": False}}

        visites = []

        def progression(nombre):
            visites.append(nombre)
            if len(visites) == 2:
                raise RuntimeError("arrêt simulé au milieu de la page")

        premier = {}
        with self.assertRaisesRegex(RuntimeError, "arrêt simulé"):
            interroger(api, premier, progress=progression)
        self.assertEqual(premier["reprise_pagination_research"]["cursor"], 1)
        second = {}
        interroger(api, second,
                   position_reprise=premier["reprise_pagination_research"])
        self.assertEqual([corps.get("cursor") for corps in appels], [None, 1, 1])
        self.assertEqual(len(second["discovered_urls"]), 1)

    def test_pagination_invalide_ne_redemarre_ni_ne_saute_de_periode(self):
        """Signaler explicitement un curseur absent malgré has_more=True."""
        appels = []

        def api(url, *, data, headers):
            appels.append(json.loads(data))
            return {"data": {"videos": [video(1)], "has_more": True,
                             "search_id": "id_sans_curseur"}}

        resultat = {}
        collecter_videos_presse_research(
            None, None, resultat, hashtag="17octobre", requete=api,
            jeton="test", debut="2026-08-01", fin="2026-10-25",
            aujourd_hui=DATE_FIXE, pause=lambda _: None,
            maximum_candidats=1000, maximum_requetes=10,
        )
        self.assertEqual(len(appels), 1)
        self.assertEqual(resultat["discovery_stop"], "pagination_research_invalide")
        self.assertTrue(resultat["collecte_partielle"])
        self.assertTrue(resultat["reprise_pagination_research"]["pagination_invalide"])
        journal = [{"source": "#17octobre", "statut_source": "partielle",
                    "rapport": resultat}]
        position = positions_pagination_research(journal, ["17octobre"])
        self.assertTrue(position["#17octobre"]["pagination_invalide"])

    def test_dix_requetes_arretent_le_lot_meme_si_aucun_candidat_n_est_retenu(self):
        """Une recherche peu productive ne peut parcourir un nombre illimité de pages."""
        appels = []

        def api(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            suite = len(appels)
            return {"data": {"videos": [], "has_more": True,
                             "cursor": suite, "search_id": "vide"}}

        resultat = {}
        interroger(api, resultat, maximum_candidats=1000, maximum_requetes=10)
        self.assertEqual(len(appels), 10)
        self.assertEqual(resultat["candidats_examines"], 0)
        self.assertEqual(resultat["requetes_tentees"], 10)
        self.assertEqual(resultat["discovery_stop"], "lot_termine")
        self.assertEqual(resultat["reprise_pagination_research"]["cursor"], 10)

    def test_enchainement_automatique_avec_budget_disponible(self):
        """Plusieurs séquences progressent sans clic ni retour au curseur initial."""
        appels = []

        def api(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            numero = len(appels)
            attendu = None if numero == 1 else numero - 1
            self.assertEqual(corps.get("cursor"), attendu)
            if numero > 1:
                self.assertEqual(corps["search_id"], "suite")
            return {
                "data": {
                    "videos": [video(numero)],
                    "has_more": numero < 5,
                    "cursor": numero,
                    "search_id": "suite",
                }
            }

        rapport = {}
        liens = interroger(
            api, rapport, maximum_candidats=1000,
            maximum_requetes=2, enchainement_automatique=True)
        self.assertEqual(len(appels), 5)
        self.assertEqual(len(liens), 5)
        self.assertEqual(len(set(liens)), 5)
        self.assertEqual(rapport["requetes_tentees"], 5)
        self.assertEqual(rapport["sequences_terminees"], 2)
        self.assertEqual(rapport["discovery_stop"], "fin_des_periodes")
        self.assertFalse(rapport["collecte_partielle"])
        self.assertIsNone(rapport["reprise_pagination_research"])

    def test_enchainement_conserve_le_curseur_si_le_budget_refuse(self):
        """Le quota peut arrêter une exécution sans supprimer les pages acquises."""
        from collecte.researchapi import ResearchAccesRefuse
        appels = []

        def api(url, *, data, headers):
            corps = json.loads(data)
            appels.append(corps)
            numero = len(appels)
            if numero == 4:
                raise ResearchAccesRefuse("Quota local quotidien atteint")
            return {
                "data": {
                    "videos": [video(numero)],
                    "has_more": True,
                    "cursor": numero,
                    "search_id": "suite",
                }
            }

        rapport = {}
        with self.assertRaises(ResearchAccesRefuse):
            interroger(api, rapport, maximum_requetes=2,
                       maximum_candidats=1000,
                       enchainement_automatique=True)
        self.assertEqual(len(rapport["discovered_urls"]), 3)
        self.assertEqual(rapport["sequences_terminees"], 1)
        self.assertEqual(rapport["reprise_pagination_research"]["cursor"], 3)
        self.assertEqual(rapport["reprise_pagination_research"]["search_id"], "suite")

    def test_conservation_interface_et_limites_fixes(self):
        """Le contrôle intermédiaire n'est plus configurable ni affiché."""
        racine = Path(__file__).resolve().parents[1]
        serveur = (racine / "webapp.py").read_text(encoding="utf-8")
        interface = (racine / "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("LIMITE_CANDIDATS_SEQUENCE_RESEARCH = 1000", serveur)
        self.assertIn("LIMITE_REQUETES_SEQUENCE_RESEARCH = 10", serveur)
        self.assertNotIn("lot_candidats_research", serveur)
        self.assertNotIn("lot_candidats_research", interface)
        self.assertIn('"Poursuivre la collecte"', interface)
        self.assertIn('"/reprendre-hashtags"', interface)


if __name__ == "__main__":
    unittest.main()
