"""Non-régression des options individuelles de variables textométriques."""
import unittest

from webapp import StartRequest, text_export


class TestsOptionsVariablesTXT(unittest.TestCase):
    def test_duree_brute_et_intervalles_coexistent(self):
        publication = {
            "id": "987654321", "author": "pressefr",
            "description": "Manifestation",
            "video_duration": 74,
            "engagement": {
                "vues": {"valeur": 12345},
                "likes": {"valeur": 150},
                "commentaires": {"valeur": 17},
                "partages": {"valeur": 3},
                "favoris": {"valeur": 5},
            },
        }
        texte = text_export(
            [publication], False,
            variables_txt=["duree", "profil", "likes"],
            variables_classes_txt=["vues", "likes", "duree"],
            taux_engagement_txt="classes",
            supprimer_arobase_profil=True)
        self.assertIn("*duree_74", texte)
        self.assertIn("*duree_classe_60_179s", texte)
        self.assertIn("*vues_classe_10k_100k", texte)
        self.assertIn("*likes_classe_100_999", texte)
        self.assertIn("*engagement_1_3pct", texte)
        self.assertIn("*profil_pressefr", texte)
        self.assertNotIn("*profil_@pressefr", texte)

    def test_duree_absente_distinguee_de_zero(self):
        publication = {
            "id": "123", "description": "Texte", "video_duration": None}
        texte = text_export(
            [publication], False,
            variables_txt=["duree"], variables_classes_txt=["duree"])
        self.assertIn("*duree_indetermine", texte)
        self.assertIn("*duree_classe_indetermine", texte)
        publication["video_duration"] = 0
        texte = text_export(
            [publication], False,
            variables_txt=["duree"], variables_classes_txt=["duree"])
        self.assertIn("*duree_0", texte)
        self.assertIn("*duree_classe_moins_15s", texte)

    def test_ancienne_selection_et_nouveaux_champs(self):
        config = StartRequest(
            hashtag="lyceens",
            variables_txt=["date", "profil", "vues", "duree"],
            variables_classes_txt=["vues", "commentaires", "duree"],
            taux_engagement_txt="brut",
        )
        self.assertEqual(config.variables_txt,
                         ["date", "profil", "vues", "duree"])
        self.assertEqual(config.variables_classes_txt,
                         ["vues", "commentaires", "duree"])
        self.assertEqual(config.taux_engagement_txt, "brut")
        ancienne = StartRequest(
            hashtag="lyceens", variables_txt=["date", "profil", "id"])
        self.assertEqual(ancienne.variables_txt, ["date", "profil", "id"])


if __name__ == "__main__":
    unittest.main()
