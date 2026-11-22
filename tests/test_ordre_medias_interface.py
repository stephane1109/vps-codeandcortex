"""Tests de concordance entre l'ordre des cases à cocher et la collecte."""
import unittest

from collecte.presse import (
    charger_inventaire, cle_tri_media, ordre_affichage_medias,
    selectionner_medias,
)


class TestsOrdreMediasInterface(unittest.TestCase):
    def test_meme_ordre_que_les_categories_et_les_sous_groupes_visibles(self):
        inventaire = charger_inventaire()
        ordre = ordre_affichage_medias(inventaire)
        attendu = []
        for categorie in ("presse_nationale", "presse_regionale",
                          "presse_independante", "autres_medias"):
            comptes = sorted(
                [m for m in inventaire if m["categorie"] == categorie],
                key=cle_tri_media,
            )
            if categorie == "presse_nationale":
                groupes = (
                    [m for m in comptes if m.get("sous_categorie") == "television_nationale"],
                    [m for m in comptes if m.get("sous_categorie") == "presse_ecrite_nationale"],
                    [m for m in comptes if m.get("sous_categorie") not in (
                        "television_nationale", "presse_ecrite_nationale")],
                )
                for groupe in groupes:
                    attendu.extend(m["id"] for m in groupe)
            else:
                attendu.extend(m["id"] for m in comptes)
        self.assertEqual(len(ordre), len(inventaire))
        self.assertEqual(len(set(ordre)), len(inventaire))
        self.assertEqual(ordre, attendu)

    def test_ordre_selection_transmis_au_collecteur(self):
        inventaire = charger_inventaire()
        ordre = ordre_affichage_medias({m["id"]: m for m in inventaire})
        tous = selectionner_medias(ordre, inventaire)
        self.assertEqual([m["id"] for m in tous], ordre)
        self.assertNotEqual(ordre, [m["id"] for m in inventaire])
        selection = ordre[::3]
        self.assertEqual(
            [m["id"] for m in selectionner_medias(selection, inventaire)],
            selection,
        )


if __name__ == "__main__":
    unittest.main()
