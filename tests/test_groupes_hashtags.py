"""Vérifications des groupes OU reliés par ET sans changer le mode classique."""
import unittest

from webapp import StartRequest, matches_hashtags


GROUPES = [
    ["manifestation", "manifestations"],
    ["lyceen", "lyceens", "lycéen", "lycéens"],
]


class TestGroupesHashtags(unittest.TestCase):
    def parametres(self, **options):
        return StartRequest.model_validate({
            "source_collecte": "hashtags",
            "hashtag_moteur": "navigateur",
            "nom_sauvegarde": "test_groupes",
            "groupes_hashtags": GROUPES,
            **options,
        })

    def test_normalisation_et_conservation(self):
        parametres = self.parametres()
        self.assertEqual(parametres.groupes_hashtags, GROUPES)
        self.assertEqual(parametres.operator, "AND")
        self.assertEqual(len(parametres.hashtags), 6)
        self.assertIn(" OU ", parametres.libelle)
        self.assertIn(" ET ", parametres.libelle)
        self.assertEqual(
            StartRequest.model_validate(parametres.model_dump()).groupes_hashtags,
            GROUPES,
        )

    def test_condition_et_entre_deux_groupes(self):
        parametres = self.parametres()
        self.assertTrue(matches_hashtags("", parametres,
            hashtags_observes=["manifestations", "lycéens"]))
        self.assertTrue(matches_hashtags("", parametres,
            hashtags_observes=["manifestation", "lyceen"]))
        self.assertFalse(matches_hashtags("", parametres,
            hashtags_observes=["manifestations"]))
        self.assertFalse(matches_hashtags("", parametres,
            hashtags_observes=["lycéens"]))
        self.assertFalse(matches_hashtags("", parametres,
            hashtags_observes=["manifestation", "manifestations"]))
        self.assertTrue(matches_hashtags(
            "#manifestations #lyceens", parametres))

    def test_mode_classique_inchange(self):
        parametres = StartRequest.model_validate({
            "source_collecte": "hashtags",
            "hashtag_moteur": "navigateur",
            "nom_sauvegarde": "test_historique",
            "hashtags_saisis": ["manifestation", "lyceens"],
            "operator": "OR",
        })
        self.assertEqual(parametres.groupes_hashtags, [])
        self.assertTrue(matches_hashtags("", parametres,
            hashtags_observes=["manifestation"]))
        parametres.operator = "AND"
        self.assertFalse(matches_hashtags("", parametres,
            hashtags_observes=["manifestation"]))

    def test_refus_groupe_vide_ou_redondant(self):
        with self.assertRaises(ValueError):
            self.parametres(groupes_hashtags=[["manifestation"], []])
        with self.assertRaises(ValueError):
            self.parametres(groupes_hashtags=[
                ["manifestation"], ["manifestation"]])


if __name__ == "__main__":
    unittest.main()
