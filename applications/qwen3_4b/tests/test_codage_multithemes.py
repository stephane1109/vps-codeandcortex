"""Tests de l'annotation commune aux commentaires et aux textes longs."""
from __future__ import annotations
import json
import unittest
from unittest.mock import Mock
from codage_multithemes import coder_multithemes, segmenter_texte, valider_annotation


class TestCodageMultithemes(unittest.TestCase):
    def creer_annotation(self, **valeurs):
        resultat = {
            "theme_denonciation": False,
            "theme_indignation": False,
            "theme_persecuteur": False,
            "indice_denonciation": "",
            "indice_indignation": "",
            "indice_persecuteur": "",
            "acteur_designe": "",
            "incertitude_interpretation": False,
            "justification": "Aucune prise de position explicite.",
        }
        resultat.update(valeurs)
        return resultat

    def creer_session(self, annotation):
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": json.dumps(annotation, ensure_ascii=False)}
        }
        session = Mock()
        session.post.return_value = reponse
        return session

    def test_commentaire_sms_deux_themes(self):
        commentaire = "C honteux, cette violence est inacceptable."
        session = self.creer_session(self.creer_annotation(
            theme_denonciation=True,
            theme_indignation=True,
            indice_denonciation="violence est inacceptable",
            indice_indignation="C honteux",
        ))
        resultat = coder_multithemes(commentaire, session=session)
        self.assertTrue(resultat["theme_denonciation"])
        self.assertTrue(resultat["theme_indignation"])
        self.assertFalse(resultat["theme_persecuteur"])
        self.assertEqual(resultat["nombre_segments"], 1)

    def test_texte_long_conserve_integralement(self):
        texte = "Description descriptive sans prise de position. " * 80
        morceaux = segmenter_texte(texte, longueur_max=850)
        self.assertGreater(len(morceaux), 1)
        self.assertTrue(all(len(morceau) <= 850 for morceau in morceaux))
        self.assertEqual(morceaux[-1][-20:], texte[-20:])
        session = self.creer_session(self.creer_annotation())
        resultat = coder_multithemes(texte, session=session)
        self.assertEqual(resultat["nombre_segments"], session.post.call_count)
        self.assertFalse(resultat["texte_tronque"])

    def test_citation_absente_signalee(self):
        annote = valider_annotation(
            self.creer_annotation(
                theme_persecuteur=True, indice_persecuteur="texte inventé",
                acteur_designe="acteur",
            ),
            "Un texte sans persécuteur.",
        )
        self.assertTrue(annote["incertitude_interpretation"])
        self.assertEqual(annote["indice_persecuteur"], "")


if __name__ == "__main__":
    unittest.main()
