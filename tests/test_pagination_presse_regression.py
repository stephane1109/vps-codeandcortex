"""Tests du chargement des médias au-delà de leur première grille publique."""
import unittest
from unittest.mock import Mock, patch

from collecte.pagination_profils import (
    ETAT_GRILLE_JS,
    RECUPERATION_DEFILEMENT_JS,
    defiler_grille_profil,
)


def etat(position, hauteur, visibles):
    return {
        "element": "conteneur-grille", "x": 220, "y": 600, "fenetre": 650,
        "position": position, "hauteur": hauteur, "liens_visibles": visibles,
        "fin": position + 650 >= hauteur - 4,
    }


class PaginationPresseRegression(unittest.TestCase):
    def test_grille_figee_a_six_videos_declenche_defilement_fin_de_grille(self):
        """Si la molette n'avance pas, activer le scroll du dernier élément."""
        navigateur = Mock()
        successifs = iter([
            etat(0, 900, 6),   # avant molette
            etat(0, 900, 6),   # molette inefficace
            etat(400, 1500, 12),  # chargement après le défilement alternatif
        ])
        navigateur.execute_script.side_effect = (
            lambda code, *args: next(successifs)
            if code == ETAT_GRILLE_JS else {"liens": 6, "ancre_presente": True}
        )
        with patch("collecte.pagination_profils.ScrollOrigin.from_viewport", return_value=object()), \
             patch("collecte.pagination_profils.ActionChains") as gestes:
            resultat = defiler_grille_profil(navigateur, "lemondefr")
        self.assertTrue(resultat["recours"])
        self.assertEqual(resultat["avant"]["liens_visibles"], 6)
        self.assertEqual(resultat["apres"]["liens_visibles"], 12)
        navigateur.execute_script.assert_any_call(
            RECUPERATION_DEFILEMENT_JS, "lemondefr", "conteneur-grille", int(650 * 0.7)
        )
        gestes.assert_called_once()

    def test_scroll_efficace_ne_declenche_pas_recours(self):
        navigateur = Mock()
        successifs = iter([etat(0, 1600, 6), etat(400, 1600, 6)])
        navigateur.execute_script.side_effect = (
            lambda code, *args: next(successifs) if code == ETAT_GRILLE_JS else None
        )
        with patch("collecte.pagination_profils.ScrollOrigin.from_viewport", return_value=object()), \
             patch("collecte.pagination_profils.ActionChains"):
            resultat = defiler_grille_profil(navigateur, "lemondefr")
        self.assertFalse(resultat["recours"])
        self.assertEqual(navigateur.execute_script.call_count, 2)

    def test_bordure_apparente_ne_prouve_pas_une_limite_a_six(self):
        """Sans progrès ni nouvelles réponses, le résultat doit rester partiel."""
        navigateur = Mock()
        navigateur.execute_script.side_effect = (
            lambda code, *args: etat(0, 650, 6)
            if code == ETAT_GRILLE_JS else {"liens": 6, "ancre_presente": True}
        )
        with patch("collecte.pagination_profils.ScrollOrigin.from_viewport", return_value=object()), \
             patch("collecte.pagination_profils.ActionChains"):
            resultat = defiler_grille_profil(navigateur, "lemondefr")
        self.assertTrue(resultat["recours"])
        self.assertEqual(resultat["apres"]["liens_visibles"], 6)
        self.assertTrue(resultat["apres"]["fin"])


if __name__ == "__main__":
    unittest.main()
