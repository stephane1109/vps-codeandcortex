"""Isolation des méthodes Presse et preuve de version côté serveur."""
import unittest
import tempfile
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient

from webapp import StartRequest,Manager,create_app
from collecte.presse_api import VERSION_PRESSE
from connect_presse import ConnexionPresse


class TestIsolationPresse(unittest.TestCase):
    def test_version_serveur_est_exposee_sur_healthz(self):
        with tempfile.TemporaryDirectory() as dossier, \
             patch("urllib.request.urlopen") as controle:
            controle.return_value.__enter__.return_value = Mock()
            with TestClient(create_app(Manager(data_dir=dossier))) as client:
                response = client.get("/healthz")
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["version_presse"],VERSION_PRESSE)

    def test_une_seule_methode_est_selectionnee_par_collecte(self):
        for moteur in ("api","navigateur","gallerydl"):
            with self.subTest(moteur=moteur):
                requete=StartRequest(source_collecte="presse",
                                     medias=["lemonde"],presse_moteur=moteur)
                connecteur=ConnexionPresse(Mock())
                connecteur.preparer_sources(requete)
                self.assertEqual(connecteur.moteur_collecte,moteur)
                self.assertEqual(requete.presse_moteur,moteur)
        with self.assertRaises(ValueError):
            StartRequest(source_collecte="presse",medias=["lemonde"],
                         presse_moteur="api_puis_navigateur")

    def test_methode_api_par_defaut_et_numero_version_explicite(self):
        requete=StartRequest(source_collecte="presse",medias=["lemonde"])
        self.assertEqual(requete.presse_moteur,"api")
        self.assertEqual(VERSION_PRESSE,"presse-secuid-depuis-embed-createur-v11")
        from pathlib import Path
        code=Path(__file__).resolve().parents[1].joinpath(
            "collecte/presse_api.py").read_text(encoding="utf-8")
        self.assertNotIn("secUid du média introuvable ou invalide",code)


    def test_choix_moteur_avant_selection_des_medias(self):
        """Le sélecteur et les champs Research précèdent l'inventaire des médias."""
        from pathlib import Path
        texte=Path(__file__).resolve().parents[1].joinpath(
            "streamlit_app.py").read_text(encoding="utf-8")
        choix=texte.index('st.radio("Moteur de découverte Presse')
        cle=texte.index('key="research_client_key"',choix)
        secret=texte.index('key="research_client_secret"',cle)
        medias=texte.index('st.write("Choisir les médias à collecter")',secret)
        cases=texte.index('st.button("Tout cocher"',medias)
        self.assertLess(choix,cle)
        self.assertLess(cle,secret)
        self.assertLess(secret,medias)
        self.assertLess(medias,cases)
        self.assertIn('["api", "research", "navigateur", "gallerydl", "tikhub", "apify"]',texte[choix:medias])


    def test_options_commentaires_sous_case_et_titre_periode(self):
        """Les options commentaires suivent la case, avant le titre Période."""
        from pathlib import Path
        code=Path(__file__).resolve().parents[1].joinpath(
            "streamlit_app.py").read_text(encoding="utf-8")
        case=code.index('st.checkbox("Collecter les textes des commentaires"')
        options=code.index('with st.expander("Options des commentaires")',case)
        titre=code.index('st.subheader("Période")',options)
        dates=code.index('with st.expander("Dates (facultatif)"',titre)
        variables=code.index('st.write("Variables à inclure avant chaque post dans le TXT")',dates)
        self.assertLess(case,options)
        self.assertLess(options,titre)
        self.assertLess(titre,dates)
        self.assertLess(dates,variables)


    def test_diagnostics_sources_compacts_et_nom_methode_selenium(self):
        """Une ligne pour méthode/liens et une ligne pour pagination/arrêt."""
        from pathlib import Path
        interface = Path(__file__).resolve().parents[1].joinpath(
            "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('informations_source.append(', interface)
        self.assertIn('ajouter_detail_source(" · ".join(informations_source))', interface)
        self.assertIn('ligne_pagination = (ligne_pagination + " · " + texte_arret', interface)
        self.assertIn('ajouter_detail_source(ligne_pagination)', interface)
        self.assertIn('"navigateur":"Méthode Selenium"', interface)
        self.assertIn('« Méthode Selenium »', interface)
        self.assertNotIn("Grille du profil (Selenium", interface)


    def test_accueil_date_et_texte_multimodale(self):
        from pathlib import Path
        code = Path(__file__).resolve().parents[1].joinpath(
            "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn('st.caption("Appli en cours de dév - modifiée 27-10-2026")', code)
        self.assertNotIn("Collecter les textes des publications TikTok.", code)
        self.assertNotIn(
            "Les liens de vidéos découverts sont également exploitables lorsque leur légende est inaccessible.",
            code,
        )


    def test_resume_research_api_concis_sans_details_supprimes(self):
        from pathlib import Path
        code = Path(__file__).resolve().parents[1].joinpath(
            "streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn(
            'informations_presse.append("Research API officielle : projet approuvé nécessaire. Les MP4 ne sont pas fournis par cette API.")',
            code,
        )
        self.assertNotIn("Période par défaut : 30 jours UTC", code)
        self.assertNotIn("version_research", code)
        self.assertNotIn("Renseigner Client key et Client secret ci-dessus", code)
        self.assertIn('st.text_input("TIKTOK_RESEARCH_CLIENT_KEY"', code)
        self.assertIn('st.text_input("TIKTOK_RESEARCH_CLIENT_SECRET"', code)



if __name__=="__main__":
    unittest.main()
