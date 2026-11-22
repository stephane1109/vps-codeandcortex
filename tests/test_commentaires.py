import unittest
from unittest.mock import patch
from collecte import commentaires as module
from collecte.commentaires import normaliser_commentaire
from collecte.reponses import rattacher_reponses
class TestsCommentaires(unittest.TestCase):
    def test_parent_et_publication(self):
        self.assertIsNone(normaliser_commentaire({"text":"bonjour", "aweme_id":"2"}, "1", "date"))
        parent = normaliser_commentaire({"cid":"10", "text":"bonjour"}, "1", "date")
        enfant = normaliser_commentaire({"cid":"11","reply_id":"10", "text":"réponse"}, "1", "date")
        self.assertTrue(rattacher_reponses([parent,enfant])[1]["parent_collecte"])
    def test_identifiant_local_est_explicitement_signale(self):
        a = normaliser_commentaire({"texte":"bonjour", "auteur":"user"}, "1", "date")
        self.assertFalse(a["id_observe"])
        self.assertIsNone(a["likes"]["valeur"])

    def test_champs_recuperes_et_zero_distinct_d_une_valeur_absente(self):
        brut = {"cid": "9001", "aweme_id": "123", "text": "Un commentaire",
                "user": {"unique_id": "lecteur"}, "digg_count": 0, "create_time": 123456}
        resultat = normaliser_commentaire(brut, "123", "date-observation")
        self.assertEqual(resultat["id"], "9001")
        self.assertEqual(resultat["publication_id"], "123")
        self.assertEqual(resultat["auteur"], "lecteur")
        self.assertEqual(resultat["date_brute"], 123456)
        self.assertEqual(resultat["observe_le"], "date-observation")
        self.assertEqual(resultat["likes"]["valeur"], 0)
        self.assertTrue(resultat["id_observe"])
        self.assertEqual(resultat["brut"], brut)
        self.assertIsNone(normaliser_commentaire({"texte": "Autre vidéo", "publication_id": "999"}, "123", "date"))


class NavigateurCommentaires:
    """Doubles Selenium : chaque pause rend disponible le chargement suivant."""
    def __init__(self, chargements, etat=None):
        self.chargements = chargements
        self.etat = etat or {}
        self.tour = 0
        self.scripts = []
        self.current_url = "https://www.tiktok.com/@media/video/123"

    def execute_script(self, script):
        self.scripts.append(script)
        if script == module.SCRIPT_COMMENTAIRES:
            return self.chargements[min(self.tour, len(self.chargements) - 1)]
        if script == module.SCRIPT_ETAT:
            return self.etat
        if script == module.SCRIPT_OUVERTURE:
            return {"statut": "ouverture_demandee"}
        if script == module.SCRIPT_DEFILEMENT:
            return {"conteneur": True, "deplace": True}
        if script == module.SCRIPT_REPONSES:
            return True
        raise AssertionError("Script inattendu")

    def pause(self, secondes):
        self.tour += 1


class TestsChargementCommentaires(unittest.TestCase):
    def setUp(self):
        self.publication = {"id": "123", "engagement": {"commentaires": {"valeur": 90}}}
        intervention = patch("scraptiktok.type_intervention_tiktok", return_value="")
        self.intervention = intervention.start()
        self.addCleanup(intervention.stop)
        fermeture = patch("scraptiktok.fermer_invitation_connexion")
        self.fermeture = fermeture.start()
        self.addCleanup(fermeture.stop)

    def collecter(self, navigateur, **options):
        return module.collecter_commentaires(navigateur, self.publication, pause=navigateur.pause, **options)

    def test_ouvre_le_panneau_et_attend_plus_de_trois_chargements_vides(self):
        navigateur = NavigateurCommentaires([[], [], [], [], [{"id": "1", "texte": "Enfin chargé"}]])
        resultat = self.collecter(navigateur, limite=1)
        self.assertEqual(resultat["statut"], "limite")
        self.assertEqual(resultat["recuperes"], 1)
        self.assertEqual(resultat["annonces"], 90)
        self.assertGreaterEqual(navigateur.tour, 4)
        self.assertIn(module.SCRIPT_OUVERTURE, navigateur.scripts)
        self.assertIn(module.SCRIPT_DEFILEMENT, navigateur.scripts)
        self.assertFalse(resultat["exhaustif"])

    def test_chargement_progressif_dedoublonnage_et_limite(self):
        commentaires = [{"id": str(i), "texte": "Texte " + str(i)} for i in range(1, 13)]
        navigateur = NavigateurCommentaires([commentaires[:6], commentaires[:6], commentaires[:9], commentaires], {"panneau_visible": True})
        resultat = self.collecter(navigateur, limite=10)
        self.assertEqual([c["id"] for c in resultat["commentaires"]], [str(i) for i in range(1, 11)])
        self.assertEqual(resultat["recuperes"], 10)
        self.assertGreaterEqual(resultat["diagnostic"]["defilements"], 3)

    def test_reponses_facultatives_et_autre_publication_exclue(self):
        donnees = [{"id": "1", "texte": "Parent"}, {"id": "2", "texte": "Réponse", "parent_id": "1"},
                   {"id": "3", "texte": "À exclure", "aweme_id": "999"}]
        sans = self.collecter(NavigateurCommentaires([donnees]))
        avec_navigateur = NavigateurCommentaires([donnees])
        avec = self.collecter(avec_navigateur, reponses=True)
        self.assertEqual([c["id"] for c in sans["commentaires"]], ["1"])
        self.assertEqual([c["id"] for c in avec["commentaires"]], ["1", "2"])
        self.assertTrue(avec["commentaires"][1]["parent_collecte"])
        self.assertIn(module.SCRIPT_REPONSES, avec_navigateur.scripts)

    def test_captcha_repris_dans_le_meme_navigateur(self):
        navigateur = NavigateurCommentaires([[{"id": "1", "texte": "Chargé"}]])
        self.intervention.return_value = "captcha"
        invitations = []
        def continuer(message):
            invitations.append(message)
            self.intervention.return_value = ""
        resultat = self.collecter(navigateur, limite=1, interact=continuer)
        self.assertEqual(resultat["statut"], "limite")
        self.assertEqual(len(invitations), 1)
        self.assertTrue(all(appel.args == (navigateur,) for appel in self.intervention.call_args_list))
        self.fermeture.assert_not_called()

    def test_captcha_sans_controle_manuel_est_signale(self):
        self.intervention.return_value = "captcha"
        resultat = self.collecter(NavigateurCommentaires([[]]))
        self.assertEqual(resultat["statut"], "verification_tiktok")
        self.assertEqual(resultat["recuperes"], 0)

    def test_redirection_conserve_les_commentaires_deja_lus(self):
        navigateur = NavigateurCommentaires([[{"id": "1", "texte": "Chargé"}]])
        def rediriger(secondes):
            navigateur.current_url = "https://www.tiktok.com/@autre/video/999"
        navigateur.pause = rediriger
        resultat = self.collecter(navigateur)
        self.assertEqual(resultat["statut"], "page_differente")
        self.assertEqual(resultat["recuperes"], 1)

    def test_diagnostics_sans_inventer_un_compteur_nul(self):
        for etat, attendu in [({}, "panneau_introuvable"),
                              ({"panneau_visible": True}, "chargement_incomplet"),
                              ({"elements_detectes": 2}, "extraction_impossible"),
                              ({"erreur": True}, "erreur_chargement"),
                              ({"desactives": True}, "desactives")]:
            with self.subTest(statut=attendu):
                resultat = self.collecter(NavigateurCommentaires([[]], etat))
                self.assertEqual(resultat["statut"], attendu)
                self.assertEqual(resultat["annonces"], 90)
                self.assertEqual(self.publication["engagement"]["commentaires"]["valeur"], 90)
                self.assertEqual(resultat["recuperes"], 0)

    def test_message_vide_en_conflit_avec_le_compteur_reste_indetermine(self):
        navigateur = NavigateurCommentaires([[]], {"vide": True, "panneau_visible": True})
        self.assertEqual(self.collecter(navigateur)["statut"], "chargement_incomplet")
        self.publication["engagement"]["commentaires"]["valeur"] = 0
        self.assertEqual(self.collecter(navigateur)["statut"], "vide_confirme")

    def test_connexion_bloquante_signalee_sans_authentification(self):
        self.intervention.return_value = "connexion"
        resultat = self.collecter(NavigateurCommentaires([[]]))
        self.assertEqual(resultat["statut"], "connexion_requise")
        self.fermeture.assert_called()

    def test_annulation_propagee(self):
        def annuler():
            raise RuntimeError("Collecte arrêtée")
        with self.assertRaisesRegex(RuntimeError, "Collecte arrêtée"):
            self.collecter(NavigateurCommentaires([[]]), verifier=annuler)

    def test_commentaires_recuperes_transmis_aux_exports(self):
        import csv
        import json
        import tempfile
        from pathlib import Path
        from corpus.construction import construire_exports
        navigateur = NavigateurCommentaires([[{"id": "9001", "texte": "Un avis public",
                                              "auteur": "lecteur", "likes": "0", "date_brute": "il y a 2 h"}]])
        resultat = self.collecter(navigateur, limite=1)
        publication = {**self.publication, "url": navigateur.current_url,
                       "author": "media", "description": "Une vidéo"}
        with tempfile.TemporaryDirectory() as dossier:
            construire_exports(dossier, [publication], resultat["commentaires"], {})
            with (Path(dossier) / "commentaires.csv").open(encoding="utf-8-sig", newline="") as flux:
                lignes = list(csv.DictReader(flux, delimiter=";"))
            self.assertEqual(len(lignes), 1)
            self.assertEqual(lignes[0]["id"], "9001")
            self.assertEqual(lignes[0]["id_"], "123")
            self.assertEqual(lignes[0]["url"], navigateur.current_url)
            self.assertEqual(lignes[0]["texte"], "Un avis public")
            self.assertEqual(lignes[0]["auteur"], "lecteur")
            self.assertEqual(lignes[0]["date_brute"], "il y a 2 h")
            self.assertEqual(json.loads(lignes[0]["likes"])["valeur"], 0)
            self.assertIn("Un avis public", (Path(dossier) / "corpus_commentaires_iramuteq.txt").read_text())
