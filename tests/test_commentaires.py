import unittest
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
