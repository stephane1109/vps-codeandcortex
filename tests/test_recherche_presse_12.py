"""Régression : la recherche média ne s'arrête pas à sa première page de 12."""
import unittest
from unittest.mock import Mock, patch

from collecte.pagination_recherche import (
    ETAT_RECHERCHE_JS,
    SECOURS_DEFILEMENT_JS,
    defiler_resultats,
)
from collecte.reseau_recherche import extraire_page_recherche


class PaginationRechercheMediaTests(unittest.TestCase):
    def test_grille_immobile_a_douze_declenche_defilement_de_la_derniere_carte(self):
        navigateur = Mock()
        premier = {
            "element": "zone", "x": 160, "y": 250,
            "fenetre": 800, "position": 0, "hauteur": 1600, "fin": False,
        }
        nouveau = {**premier, "position": 300, "hauteur": 2300}
        etats = iter([premier, premier, nouveau])
        navigateur.execute_script.side_effect = lambda code, *args: (
            next(etats) if code == ETAT_RECHERCHE_JS else None
        )
        with patch("collecte.pagination_recherche.ScrollOrigin.from_viewport",
                   return_value=object()), \
             patch("collecte.pagination_recherche.ActionChains") as actions:
            sortie = defiler_resultats(navigateur)
        self.assertTrue(sortie["secours"])
        self.assertEqual(sortie["apres"]["position"], 300)
        navigateur.execute_script.assert_any_call(SECOURS_DEFILEMENT_JS, "zone", 560)
        actions.assert_called_once()

    def test_defilement_normal_ne_declenche_pas_seconde_tentative(self):
        navigateur = Mock()
        premier = {
            "element": "zone", "x": 160, "y": 250,
            "fenetre": 800, "position": 0, "hauteur": 1600, "fin": False,
        }
        nouveau = {**premier, "position": 350}
        etats = iter([premier, nouveau])
        navigateur.execute_script.side_effect = lambda code, *args: (
            next(etats) if code == ETAT_RECHERCHE_JS else None
        )
        with patch("collecte.pagination_recherche.ScrollOrigin.from_viewport",
                   return_value=object()), \
             patch("collecte.pagination_recherche.ActionChains"):
            sortie = defiler_resultats(navigateur)
        self.assertFalse(sortie["secours"])
        self.assertEqual(navigateur.execute_script.call_count, 2)

    def test_page_recherche_conserve_video_sans_legende(self):
        numero = "7697829530844663072"
        page = extraire_page_recherche({
            "status_code": 0, "data": {
                "item_list": [
                    {"item": {"id":numero, "author":{"uniqueId":"lemondefr"},
                              "video":{"id":numero}}},
                    {"item": {"id":"123", "author":{"uniqueId":"autremedia"},
                              "desc":"Autre", "video":{"id":"123"}}},
                ],
                "has_more": True, "cursor": 12,
            },
        })
        self.assertTrue(page["liste_valide"])
        self.assertEqual(page["curseur"],"12")
        self.assertTrue(page["suite"])
        self.assertIn(f"https://www.tiktok.com/@lemondefr/video/{numero}",page["liens"])
        self.assertEqual(len(page["liens"]),2)

    def test_format_precedent_de_recherche_reste_compatible(self):
        page = extraire_page_recherche({
            "status_code": 0, "has_more": 0, "cursor": 24,
            "data": [{"item": {"id":"123","author":{"uniqueId":"lemondefr"},
                              "desc":"Légende","video":{"id":"123"}}}],
        })
        self.assertEqual(page["liens"],["https://www.tiktok.com/@lemondefr/video/123"])
        self.assertFalse(page["suite"])

    def test_ancre_choisit_dernier_resultat_visible(self):
        from collecte.pagination_recherche import ETAT_RECHERCHE_JS
        self.assertIn(".at(-1)",ETAT_RECHERCHE_JS)
        self.assertNotIn("liens.find(e =>",ETAT_RECHERCHE_JS)


if __name__=="__main__":
    unittest.main()
