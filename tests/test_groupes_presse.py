"""Contrôler l'inventaire des médias et les regroupements éditoriaux."""
import json
import tempfile
import unittest
from pathlib import Path

from collecte.presse import charger_inventaire, selectionner_medias
from collecte.quotas_exploitation import max_sources


COMPTES_NOUVEAUX = {
    "mediapartfr": "presse_nationale",
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

COMPTES_NATIONAUX_TELEVISION = {
    "tf1info", "bfmtv", "francetvpolitique", "france.tv",
    "m6info", "lci", "cnewsofficiel", "artefr",
}

COMPTES_NATIONAUX_ECRITS = {
    "lemondefr", "lefigaro", "liberation.fr", "lequipe", "lhumanitefr",
    "mediapartfr",
    "lesechos", "lobs", "lepoint.fr", "marianne.lemag",
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
        # Seul @liberationfr a été supprimé à la demande de l'utilisateur.
        self.assertEqual(len(inventaire), 62)

    def test_nationaux_tv_et_presse_ecrite_conserves(self):
        """Compléter les deux listes sans supprimer les anciens médias."""
        inventaire = charger_inventaire()
        handles = {media["compte"]: media for media in inventaire}
        for compte in COMPTES_NATIONAUX_TELEVISION:
            with self.subTest(compte=compte):
                self.assertEqual(
                    handles[compte]["categorie"], "presse_nationale")
                self.assertEqual(
                    handles[compte]["sous_categorie"], "television_nationale")
        for compte in COMPTES_NATIONAUX_ECRITS:
            with self.subTest(compte=compte):
                self.assertEqual(
                    handles[compte]["categorie"], "presse_nationale")
                self.assertEqual(
                    handles[compte]["sous_categorie"], "presse_ecrite_nationale")
        self.assertEqual(len(handles), 62)
        self.assertEqual(
            len([m for m in inventaire
                 if m["categorie"] == "presse_nationale"]), 25)

    def test_lhumanite_dans_presse_ecrite_nationale(self):
        """Ajouter L'Humanité sans créer de doublon ni modifier ses voisins."""
        inventaire = charger_inventaire()
        humanite = [media for media in inventaire
                    if media["compte"] == "lhumanitefr"]
        self.assertEqual(len(humanite), 1)
        self.assertEqual(humanite[0]["nom"], "L'Humanité")
        self.assertEqual(humanite[0]["categorie"], "presse_nationale")
        self.assertEqual(
            humanite[0]["sous_categorie"], "presse_ecrite_nationale")
        self.assertEqual(
            humanite[0]["url"], "https://www.tiktok.com/@lhumanitefr")

    def test_linfo_60_secondes_et_deplacement_mediapart(self):
        """Ajouter un compte indépendant et reclasser Mediapart sans suppression."""
        inventaire = charger_inventaire()
        handles = {m["compte"]: m for m in inventaire}
        self.assertEqual(len(inventaire), 62)
        info = handles["iuzdrmqevnu"]
        self.assertEqual(info["nom"], "L’info en 60 secondes")
        self.assertEqual(info["categorie"], "presse_independante")
        self.assertEqual(
            info["url"], "https://www.tiktok.com/@iuzdrmqevnu")
        mediapart = handles["mediapartfr"]
        self.assertEqual(mediapart["categorie"], "presse_nationale")
        self.assertEqual(
            mediapart["sous_categorie"], "presse_ecrite_nationale")
        self.assertEqual(
            sum(m["categorie"] == "presse_independante" for m in inventaire),
            8)
        self.assertEqual(
            sum(m["categorie"] == "presse_nationale" for m in inventaire),
            25)

    def test_liberation_variante_supprimee_compte_original_conserve(self):
        """Ne supprimer que @liberationfr sans toucher aux autres comptes."""
        inventaire = charger_inventaire()
        handles = {m["compte"] for m in inventaire}
        self.assertIn("liberation.fr", handles)
        self.assertNotIn("liberationfr", handles)
        self.assertTrue({"m6info", "m6info_"}.issubset(handles))
        self.assertEqual(
            next(m["statut"] for m in inventaire
                 if m["compte"] == "m6info"),
            "declare_utilisateur")

    def test_quatre_medias_reclasses_independants(self):
        """Les quatre comptes changent de groupe sans changer d'identifiant."""
        inventaire = charger_inventaire()
        groupes = {media["compte"]: media for media in inventaire}
        for compte in (
            "lehuffpostfr", "cquoilinfo", "hugodecrypte", "brutofficiel",
        ):
            with self.subTest(compte=compte):
                self.assertIn(compte, groupes)
                self.assertEqual(
                    groupes[compte]["categorie"], "presse_independante")
                self.assertNotIn("sous_categorie", groupes[compte])
        self.assertEqual(len(inventaire), 62)
        self.assertEqual(
            sum(m["categorie"] == "presse_independante" for m in inventaire),
            8)
        self.assertEqual(
            sum(m["categorie"] == "presse_regionale" for m in inventaire),
            21)

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
        self.assertIn('with st.container(gap=None):', interface)
        self.assertIn('if indice % 2 != numero_colonne:', interface)
        self.assertIn('on_change=memoriser_medias,', interface)
        self.assertIn('"Chaînes de télévision nationales"', interface)
        self.assertIn('("presse_ecrite_nationale", "Presse nationale")', interface)
        self.assertNotIn('"Presse écrite nationale"', interface)
        self.assertIn('"Autres médias nationaux"', interface)


if __name__ == "__main__":
    unittest.main()
