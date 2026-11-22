"""Vérifier que la collecte de profils accepte une sélection complète."""

import unittest

from webapp import StartRequest


class TestTransfertComptesIntegral(unittest.TestCase):
    def test_plus_de_dix_comptes_sont_conserves(self):
        """Le modèle ne doit ni limiter ni tronquer les comptes sélectionnés."""
        comptes = [f"compte_{indice:03d}" for indice in range(35)]
        parametres = StartRequest.model_validate({
            "source_collecte": "comptes",
            "nom_sauvegarde": "selection_complete",
            "comptes": comptes,
            "hashtags_saisis": ["manifestation"],
            "profil_moteur": "navigateur",
            "limit": 50,
        })
        self.assertEqual(parametres.comptes, comptes)
        self.assertEqual(
            [source["compte"] for source in parametres.sources], comptes)

    def test_doublons_ne_creent_pas_de_profils_supplementaires(self):
        """La suppression des doublons n'efface pas les autres profils."""
        comptes = [f"compte_{indice:03d}" for indice in range(20)]
        parametres = StartRequest.model_validate({
            "source_collecte": "comptes",
            "nom_sauvegarde": "selection_sans_doublons",
            "comptes": comptes + comptes[:3],
            "hashtags_saisis": ["lyceen"],
            "profil_moteur": "navigateur",
            "limit": 50,
        })
        self.assertEqual(parametres.comptes, comptes)


if __name__ == "__main__":
    unittest.main()
