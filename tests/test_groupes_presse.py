"""Contrôler l'inventaire des médias et les regroupements éditoriaux."""
import json
import tempfile
import unittest
from pathlib import Path

from collecte.presse import charger_inventaire, selectionner_medias, cle_tri_media
from collecte.quotas_exploitation import max_sources


COMPTES_NOUVEAUX = {
    "mediapartfr": "presse_nationale",
    "actutoulouse": "presse_regionale",
    "actu.fr.officiel": "presse_regionale",
    "lefigaro": "presse_nationale",
    "valeursactuelles": "presse_nationale",
    "liberation.fr": "presse_nationale",
    "loopsider": "presse_independante",
    "lejournaldefrance": "autres_medias",
    "actu.paris": "presse_regionale",
    "ledauphinelibere": "presse_regionale",
    "letelegramme": "presse_regionale",
    "franceinfo": "presse_nationale",
}

COMPTES_NATIONAUX_TELEVISION = {
    "tf1info", "bfmtv", "francetvpolitique", "france.tv",
    "m6info_", "lci", "cnews", "artefr", "france24",
}

COMPTES_NATIONAUX_ECRITS = {
    "lemondefr", "lefigaro", "liberation.fr", "lequipe", "lhumanitefr",
    "mediapartfr", "politis_fr",
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
        self.assertEqual(len(regionaux), 36)
        # Les variantes @liberationfr et @m6info ont été retirées séparément.
        self.assertEqual(len(inventaire), 80)

    def test_onze_nouveaux_comptes_france3_regionaux(self):
        """Les comptes régionaux France 3 sont tous présents et uniques."""
        comptes_attendus = {
            "france3nouvelleaquitaine": "France 3 Nouvelle-Aquitaine",
            "france3grandest": "France 3 Grand Est",
            "france3bretagne": "France 3 Bretagne",
            "france3bfc": "France 3 Bourgogne-Franche-Comté",
            "france3normandie": "France 3 Normandie",
            "f3cvdl": "France 3 Centre-Val de Loire",
            "france3hautsdefrance": "France 3 Hauts-de-France",
            "france3paris_idf": "France 3 Paris Île-de-France",
            "france3pdl": "France 3 Pays de la Loire",
            "france3paca": "France 3 Provence-Alpes-Côte d’Azur",
            "france_3_aura": "France 3 Auvergne-Rhône-Alpes",
        }
        inventaire = charger_inventaire()
        for compte, nom in comptes_attendus.items():
            with self.subTest(compte=compte):
                correspondances = [
                    media for media in inventaire if media["compte"] == compte
                ]
                self.assertEqual(len(correspondances), 1)
                self.assertEqual(correspondances[0]["nom"], nom)
                self.assertEqual(
                    correspondances[0]["categorie"], "presse_regionale")
                self.assertEqual(
                    correspondances[0]["url"],
                    f"https://www.tiktok.com/@{compte}")
        # Le compte France 3 Occitanie déjà présent est conservé.
        self.assertEqual(
            sum(media["compte"] == "france3occitanie" for media in inventaire),
            1)
        self.assertEqual(len(inventaire), 80)
        self.assertEqual(
            sum(media["categorie"] == "presse_regionale"
                for media in inventaire), 36)

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
        self.assertEqual(len(handles), 80)
        self.assertEqual(
            len([m for m in inventaire
                 if m["categorie"] == "presse_nationale"]), 26)

    def test_france24_dans_les_chaines_nationales(self):
        """Vérifier le nouveau compte France 24 et son sous-groupe."""
        inventaire = charger_inventaire()
        france24 = [m for m in inventaire if m["compte"] == "france24"]
        self.assertEqual(len(france24), 1)
        self.assertEqual(france24[0]["id"], "france24")
        self.assertEqual(france24[0]["nom"], "France 24")
        self.assertEqual(france24[0]["categorie"], "presse_nationale")
        self.assertEqual(
            france24[0]["sous_categorie"], "television_nationale")
        self.assertEqual(
            france24[0]["url"], "https://www.tiktok.com/@france24")
        self.assertEqual(len(inventaire), 80)

    def test_cnews_avec_le_compte_corrige(self):
        """Conserver l'ID de sélection CNews et corriger le compte TikTok."""
        inventaire = charger_inventaire()
        cnews = [m for m in inventaire if m["compte"] == "cnews"]
        self.assertEqual(len(cnews), 1)
        self.assertEqual(cnews[0]["id"], "cnewsofficiel")
        self.assertEqual(cnews[0]["nom"], "CNews")
        self.assertEqual(cnews[0]["categorie"], "presse_nationale")
        self.assertEqual(cnews[0]["sous_categorie"], "television_nationale")
        self.assertEqual(cnews[0]["url"], "https://www.tiktok.com/@cnews")
        self.assertNotIn(
            "cnewsofficiel", {m["compte"] for m in inventaire})
        self.assertEqual(len(inventaire), 80)

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
        self.assertEqual(len(inventaire), 80)
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
            9)
        self.assertEqual(
            sum(m["categorie"] == "presse_nationale" for m in inventaire),
            26)

    def test_politis_deplace_en_presse_nationale(self):
        """Conserver le compte Politis et le ranger parmi les titres nationaux."""
        inventaire = charger_inventaire()
        politis = [m for m in inventaire if m["compte"] == "politis_fr"]
        self.assertEqual(len(politis), 1)
        self.assertEqual(politis[0]["id"], "politis_fr")
        self.assertEqual(politis[0]["categorie"], "presse_nationale")
        self.assertEqual(
            politis[0]["sous_categorie"], "presse_ecrite_nationale")
        self.assertEqual(len(inventaire), 80)

    def test_marc_verdenet_dans_autres_medias(self):
        """Ajouter ce profil sans altérer les autres comptes de l'inventaire."""
        inventaire = charger_inventaire()
        profils = [m for m in inventaire if m["compte"] == "marc.verdenet"]
        self.assertEqual(len(profils), 1)
        self.assertEqual(profils[0]["id"], "marc_verdenet")
        self.assertEqual(profils[0]["nom"], "Marc Verdenet")
        self.assertEqual(profils[0]["categorie"], "autres_medias")
        self.assertEqual(
            profils[0]["url"], "https://www.tiktok.com/@marc.verdenet")
        self.assertEqual(len(inventaire), 80)
        self.assertEqual(
            sum(m["categorie"] == "autres_medias" for m in inventaire), 9)

    def test_noahdecrypte_dans_autres_medias(self):
        """Ajouter Noah Décrypte sans supprimer ni renommer d'autres médias."""
        inventaire = charger_inventaire()
        comptes = [m for m in inventaire if m["compte"] == "noahdecrypte"]
        self.assertEqual(len(comptes), 1)
        self.assertEqual(comptes[0]["nom"], "Noah Décrypte")
        self.assertEqual(comptes[0]["categorie"], "autres_medias")
        self.assertEqual(
            comptes[0]["url"], "https://www.tiktok.com/@noahdecrypte")
        self.assertEqual(
            sum(m["categorie"] == "autres_medias" for m in inventaire), 9)
        self.assertEqual(len(inventaire), 80)

    def test_liberation_variante_supprimee_compte_original_conserve(self):
        """Ne supprimer que @liberationfr sans toucher aux autres comptes."""
        inventaire = charger_inventaire()
        handles = {m["compte"] for m in inventaire}
        self.assertIn("liberation.fr", handles)
        self.assertNotIn("liberationfr", handles)
        self.assertIn("m6info_", handles)
        self.assertNotIn("m6info", handles)
        original_m6 = next(m for m in inventaire
                           if m["compte"] == "m6info_")
        self.assertEqual(original_m6["id"], "m6info_")
        self.assertEqual(original_m6["url"], "https://www.tiktok.com/@m6info_")
        self.assertEqual(original_m6["categorie"], "presse_nationale")
        self.assertEqual(
            original_m6["sous_categorie"], "television_nationale")

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
        self.assertEqual(len(inventaire), 80)
        self.assertEqual(
            sum(m["categorie"] == "presse_independante" for m in inventaire),
            9)
        self.assertEqual(
            sum(m["categorie"] == "presse_regionale" for m in inventaire),
            36)

    def test_comptes_sans_profil_distinct_non_ajoutes(self):
        """Ne pas inventer de profil pour les cas particuliers."""
        comptes = {m["compte"] for m in charger_inventaire()}
        self.assertNotIn("lecourrierdelouest", comptes)
        self.assertNotIn("lamarseillaise", comptes)
        alsace = next(m for m in charger_inventaire()
                      if m["compte"] == "lalsacefr")
        self.assertEqual(alsace["nom"], "L'Alsace")
        self.assertIn("DNA", alsace["note"])

    def test_camdiafr_et_angersinfo_dans_leurs_groupes(self):
        """Deux nouveaux comptes sont sélectionnables et recodés selon leur groupe."""
        from collecte.presse import colonnes_categories_presse, code_presse_publication

        inventaire = charger_inventaire()
        par_compte = {media["compte"]: media for media in inventaire}
        cas = (
            ("camdiafr", "autres_medias", "presse_autre"),
            ("angersinfo", "presse_regionale", "presse_regio_dpt"),
        )
        for compte, categorie, variable in cas:
            with self.subTest(compte=compte):
                media = par_compte[compte]
                self.assertEqual(media["id"], compte)
                self.assertEqual(media["categorie"], categorie)
                self.assertEqual(media["url"], f"https://www.tiktok.com/@{compte}")
                self.assertEqual(selectionner_medias([compte])[0]["compte"], compte)
                fiche = {"author": compte, "description": "#manifestation"}
                self.assertEqual(code_presse_publication(fiche), variable)
                colonnes = colonnes_categories_presse(fiche)
                self.assertEqual(colonnes[variable], 1)
                self.assertEqual(sum(colonnes.values()), 1)
        self.assertIn("confirmer", par_compte["camdiafr"]["note"])
        self.assertEqual(len(inventaire), 80)

    def test_actu_locaux_reclasses_regionaux_et_loopsider_independant(self):
        """Vérifier les reclassements, les comptes uniques et l'absence du groupe local."""
        from collecte.presse import code_presse_publication, colonnes_categories_presse

        inventaire = charger_inventaire()
        comptes = {media["compte"]: media for media in inventaire}
        for compte in ("actucaen", "actubordeaux", "actutoulouse"):
            with self.subTest(compte=compte):
                self.assertIn(compte, comptes)
                self.assertEqual(comptes[compte]["categorie"], "presse_regionale")
                self.assertEqual(
                    selectionner_medias([comptes[compte]["id"]])[0]["compte"],
                    compte)
                publication = {"author": compte}
                self.assertEqual(
                    code_presse_publication(publication), "presse_regio_dpt")
                self.assertEqual(
                    colonnes_categories_presse(publication)["presse_regio_dpt"], 1)
        self.assertEqual(comptes["loopsider"]["categorie"], "presse_independante")
        self.assertEqual(
            code_presse_publication({"author": "loopsider"}), "presse_indep")
        self.assertFalse(any(
            media["categorie"] == "presse_locale" for media in inventaire))
        self.assertEqual(
            sum(media["categorie"] == "presse_regionale" for media in inventaire),
            36)
        self.assertEqual(
            sum(media["categorie"] == "presse_independante" for media in inventaire),
            9)
        self.assertEqual(len(inventaire), 80)

    def test_compte_actufr_officiel_et_tri_alphabetique(self):
        """Le compte officiel est sélectionnable et l'affichage reste alphabétique."""
        from collecte.presse import code_presse_publication
        from unicodedata import normalize

        inventaire = charger_inventaire()
        comptes = {media["compte"]: media for media in inventaire}
        media = comptes["actu.fr.officiel"]
        self.assertEqual(media["nom"], "Actu.fr")
        self.assertEqual(media["categorie"], "presse_regionale")
        self.assertEqual(
            media["url"], "https://www.tiktok.com/@actu.fr.officiel")
        self.assertEqual(
            selectionner_medias([media["id"]])[0]["compte"],
            "actu.fr.officiel")
        self.assertEqual(
            code_presse_publication({"author": "actu.fr.officiel"}),
            "presse_regio_dpt")
        self.assertEqual(len(inventaire), 80)

        def cle_attendue(nom):
            texte = normalize("NFKD", nom)
            return "".join(
                caractere for caractere in texte
                if not __import__("unicodedata").combining(caractere)
            ).casefold().strip()

        for categorie in (
            "presse_nationale", "presse_regionale",
            "presse_independante", "autres_medias",
        ):
            with self.subTest(categorie=categorie):
                comptes_categorie = [
                    media for media in inventaire
                    if media["categorie"] == categorie
                ]
                tries = sorted(comptes_categorie, key=cle_tri_media)
                noms = [media["nom"] for media in tries]
                self.assertEqual(
                    [cle_attendue(nom) for nom in noms],
                    sorted(cle_attendue(nom) for nom in noms))
                if categorie == "presse_regionale":
                    indices_france3 = [
                        position for position, media in enumerate(tries)
                        if media["nom"].startswith("France 3 ")
                    ]
                    self.assertEqual(len(indices_france3), 12)
                    self.assertEqual(
                        indices_france3,
                        list(range(indices_france3[0],
                                   indices_france3[0] + 12)))

        interface = (Path(__file__).resolve().parents[1] /
                     "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("comptes_categorie = sorted(", interface)
        self.assertIn("key=lambda element: cle_tri_media(element[1])", interface)
        self.assertIn("from collecte.presse import cle_tri_media", interface)

    def test_clpress_et_france3_regroupes(self):
        """CLPRESS est indépendant et les douze France 3 restent consécutifs."""
        inventaire = charger_inventaire()
        clpress = next(media for media in inventaire if media["compte"] == "clpress")
        self.assertEqual(clpress["categorie"], "presse_independante")
        regionaux = [m for m in inventaire if m["categorie"] == "presse_regionale"]
        indices = [rang for rang, media in enumerate(regionaux)
                   if media["nom"].startswith("France 3 ")]
        self.assertEqual(len(indices), 12)
        self.assertEqual(indices, list(range(indices[0], indices[0] + 12)))

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
            ("presse_regionale", "Presse Régionale/départementale"),
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
