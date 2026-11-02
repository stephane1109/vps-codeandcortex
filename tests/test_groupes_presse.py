"""Contrôler l'inventaire des médias et les regroupements éditoriaux."""
import json
import tempfile
import unittest
from pathlib import Path

from collecte.presse import charger_inventaire, selectionner_medias
from collecte.quotas_exploitation import max_sources


COMPTES_NOUVEAUX = {
    "mediapartfr": "presse_independante",
    "actutoulouse": "presse_regionale",
    "lefigaro": "presse_nationale",
    "valeursactuelles": "presse_nationale",
    "liberation.fr": "presse_nationale",
    "loopsider": "autres_medias",
    "lejournaldefrance": "autres_medias",
    "actu.paris": "presse_regionale",
    "ledauphinelibere": "presse_regionale",
    "letelegramme": "presse_regionale",
    "franceinfo": "presse_nationale",
}

COMPTES_REGIONAUX = {
    "ouestfrance", "leparisien", "journalsudouest", "letelegramme",
    "lavoixdunord", "ledauphinelibere", "lanouvellerepublique",
    "le_progres_", "lamontagne_fr", "midilibre", "lindependant_officiel",
    "nice_matin", "parisnormandieofficiel", "corsematin",
    "lestrepublicain", "lalsacefr",
}


class TestsGroupesPresse(unittest.TestCase):
    def test_onze_comptes_de_la_premiere_demande(self):
        """Conserver les anciens comptes et ne pas dupliquer franceinfo."""
        inventaire = charger_inventaire()
        comptes = [m["compte"] for m in inventaire]
        self.assertEqual(len(comptes), len(set(comptes)))
        self.assertEqual(len(comptes), len({m["id"] for m in inventaire}))
        self.assertEqual(comptes.count("franceinfo"), 1)
        for compte, categorie in COMPTES_NOUVEAUX.items():
            with self.subTest(compte=compte):
                media = next(m for m in inventaire if m["compte"] == compte)
                self.assertEqual(media["categorie"], categorie)

    def test_seize_comptes_regionaux_demandes(self):
        """Chaque compte fourni relève du groupe régional une seule fois."""
        inventaire = charger_inventaire()
        regionaux = [m["compte"] for m in inventaire
                    if m["categorie"] == "presse_regionale"]
        for compte in COMPTES_REGIONAUX:
            with self.subTest(compte=compte):
                self.assertEqual(regionaux.count(compte), 1)
        self.assertEqual(len(regionaux), 21)
        self.assertEqual(len(inventaire), 49)

    def test_comptes_sans_profil_distinct_non_ajoutes(self):
        """Ne pas inventer de profil pour les cas particuliers."""
        comptes = {m["compte"] for m in charger_inventaire()}
        self.assertNotIn("lecourrierdelouest", comptes)
        self.assertNotIn("lamarseillaise", comptes)
        alsace = next(m for m in charger_inventaire()
                      if m["compte"] == "lalsacefr")
        self.assertEqual(alsace["nom"], "L'Alsace")
        self.assertIn("DNA", alsace["note"])

    def test_identifiants_anciens_et_selection_conserves(self):
        """La sélection actuelle se fait toujours par ID interne."""
        media = selectionner_medias([
            "lemonde", "franceinfo", "politis_fr",
            "ouestfrance", "journalsudouest",
        ])
        self.assertEqual([m["compte"] for m in media], [
            "lemondefr", "franceinfo", "politis_fr",
            "ouestfrance", "journalsudouest",
        ])

    def test_limite_technique_suit_l_inventaire(self):
        self.assertEqual(max_sources(), len(charger_inventaire()))

    def test_doublon_de_compte_refuse(self):
        """Deux IDs distincts ne doivent pas renvoyer au même TikTok."""
        source = {"comptes": [
            {"id": "a", "compte": "ouestfrance",
             "categorie": "presse_regionale"},
            {"id": "b", "compte": "@ouestfrance",
             "categorie": "presse_regionale"},
        ]}
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "test_presse.json"
            chemin.write_text(json.dumps(source), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dupliqué"):
                charger_inventaire(chemin)

    def test_categories_et_boutons_de_selection_dans_streamlit(self):
        """Les nouvelles catégories n'effacent ni les cases ni Tout cocher."""
        interface = (Path(__file__).resolve().parents[1] /
                     "streamlit_app.py").read_text(encoding="utf-8")
        for categorie, libelle in (
            ("presse_nationale", "Presse nationale"),
            ("presse_regionale", "Presse régionale"),
            ("presse_independante", "Presse indépendante"),
            ("autres_medias", "Autres médias ou statut à confirmer"),
        ):
            self.assertIn(f'("{categorie}", "{libelle}")', interface)
        self.assertIn('key="tous_medias"', interface)
        self.assertIn('"cocher_categorie_" + categorie', interface)
        self.assertIn('"decocher_categorie_" + categorie', interface)
        self.assertIn('key=cle, disabled=occupe, on_change=memoriser_medias', interface)


if __name__ == "__main__":
    unittest.main()
