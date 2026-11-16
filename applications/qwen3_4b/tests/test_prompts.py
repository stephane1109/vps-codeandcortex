"""Tests de non-régression des modes prompt et grille structurée de Qwen."""
from __future__ import annotations

import unittest
from unittest.mock import Mock

from codage_qwen import (
    CHAMPS_BOOLEENS, PROMPT_LIBRE_DEFAUT, coder_commentaire,
    verifier_resultat,
)


class TestAnalyseQwen(unittest.TestCase):
    def test_prompt_libre_sans_schema(self):
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": "Le commentaire évoque une question éducative."}
        }
        session = Mock()
        session.post.return_value = reponse
        resultat = coder_commentaire(
            "Un commentaire éducatif", consigne="Repère le thème éducatif.",
            mode_analyse="libre", session=session,
        )
        self.assertEqual(resultat["mode_analyse"], "libre")
        self.assertIn("question éducative", resultat["reponse_qwen"])
        charge = session.post.call_args.kwargs["json"]
        self.assertNotIn("format", charge)
        self.assertIn("Repère le thème éducatif.", charge["messages"][0]["content"])

    def test_codage_ancien_schema_preserve(self):
        import json
        valeurs = {champ: False for champ in CHAMPS_BOOLEENS}
        valeurs.update({
            "acteur_cible": "", "indice_textuel": "", "justification": "RAS",
        })
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": json.dumps(valeurs)}
        }
        session = Mock()
        session.post.return_value = reponse
        resultat = coder_commentaire(
            "Pas de violence.", mode_analyse="structure", session=session,
        )
        self.assertFalse(resultat["violence_evoquee"])
        self.assertEqual(resultat["mode_analyse"], "structure")
        charge = session.post.call_args.kwargs["json"]
        self.assertIn("format", charge)

    def test_prompt_vide_refuse(self):
        with self.assertRaisesRegex(ValueError, "prompt"):
            coder_commentaire(
                "Une phrase", consigne="   ", mode_analyse="libre",
            )

    def test_erreur_http_ollama_avec_detail(self):
        import requests
        reponse = Mock()
        reponse.status_code = 500
        reponse.text = "llama runner process has terminated"
        reponse.raise_for_status.side_effect = requests.HTTPError("500")
        session = Mock()
        session.post.return_value = reponse
        with self.assertRaisesRegex(
            requests.HTTPError,
            "Modèle sollicité : .* ; Contexte demandé : .*"
        ) as contexte:
            coder_commentaire(
                "Commentaire d'essai",
                consigne="Analyse ce commentaire.",
                mode_analyse="libre",
                session=session,
            )
        self.assertIn(
            "llama runner process has terminated", str(contexte.exception)
        )

    def test_reponse_ollama_vide_explicitement_signalee(self):
        reponse = Mock()
        reponse.json.return_value = {"message": {"content": ""}}
        session = Mock()
        session.post.return_value = reponse
        with self.assertRaisesRegex(ValueError, "message.content"):
            coder_commentaire(
                "Commentaire d'essai",
                consigne="Analyse ce commentaire.",
                mode_analyse="libre",
                session=session,
            )

    def test_grille_trois_themes_valide(self):
        from codage_qwen import valider_theses, THESES_INITIALES
        resultat = valider_theses(list(THESES_INITIALES))
        self.assertEqual(len(resultat), 3)
        self.assertIn("titre", resultat[0])
        with self.assertRaisesRegex(ValueError, "trois"):
            valider_theses(resultat[:2])
        with self.assertRaisesRegex(ValueError, "distincts"):
            valider_theses([resultat[0], resultat[0], resultat[2]])

    def test_classement_indetermine_et_theme(self):
        from codage_qwen import valider_classement_theses, THESES_INITIALES
        contenu = {
            "these_retenue": "these_3",
            "indice_textuel": "Je préfère me taire",
            "justification": "Le commentaire exprime une retenue de parole.",
        }
        resultat = valider_classement_theses(
            contenu, list(THESES_INITIALES)
        )
        self.assertEqual(resultat["these_retenue"], "these_3")
        self.assertEqual(resultat["theme_retenu"], "theme_3")
        self.assertEqual(resultat["theme_intitule"], THESES_INITIALES[2]["titre"])
        self.assertEqual(
            resultat["these_intitule"], THESES_INITIALES[2]["titre"]
        )
        contenu["these_retenue"] = "indetermine"
        resultat = valider_classement_theses(contenu, list(THESES_INITIALES))
        self.assertEqual(resultat["these_retenue"], "indetermine")
        contenu["these_retenue"] = "autre"
        with self.assertRaisesRegex(ValueError, "trois thèmes"):
            valider_classement_theses(contenu, list(THESES_INITIALES))

    def test_proposition_trois_themes_avec_reponse_fictive(self):
        import json
        from codage_qwen import proposer_trois_theses, THESES_INITIALES
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": json.dumps(
                {"theses": list(THESES_INITIALES)},
                ensure_ascii=False,
            )}
        }
        session = Mock()
        session.post.return_value = reponse
        themes = proposer_trois_theses(
            ["Il y a eu des violences", "J'évite de parler par peur"],
            session=session,
        )
        self.assertEqual(len(themes), 3)
        charge = session.post.call_args.kwargs["json"]
        self.assertEqual(charge["stream"], False)
        self.assertIn("format", charge)
        self.assertIn("échantillon", charge["messages"][1]["content"])

    def test_classification_trois_themes_avec_reponse_fictive(self):
        import json
        from codage_qwen import THESES_INITIALES
        reponse = Mock()
        reponse.json.return_value = {
            "message": {"content": json.dumps({
                "these_retenue": "these_3",
                "indice_textuel": "responsable des violences",
                "justification": "Un acteur est accusé explicitement.",
            }, ensure_ascii=False)}
        }
        session = Mock()
        session.post.return_value = reponse
        resultat = coder_commentaire(
            "Ce groupe est responsable des violences contre nous.",
            consigne="Classe les discours sur la violence.",
            mode_analyse="theses",
            theses=list(THESES_INITIALES),
            session=session,
        )
        self.assertEqual(resultat["mode_analyse"], "theses")
        self.assertEqual(resultat["theme_retenu"], "theme_3")
        self.assertEqual(resultat["these_retenue"], "these_3")
        self.assertIn("persécuteur", resultat["these_intitule"].lower())
        charge = session.post.call_args.kwargs["json"]
        self.assertIn("format", charge)
        self.assertIn("Tâche : CLASSE", charge["messages"][0]["content"])
        self.assertNotIn(
            "Consigne définie par le chercheur",
            charge["messages"][0]["content"],
        )

    def test_trois_themes_demandes(self):
        """Les trois classes imposées distinguent trois opérations discursives."""
        from codage_qwen import THESES_INITIALES, PROMPT_THESES_DEFAUT
        self.assertEqual(
            [theme["titre"] for theme in THESES_INITIALES],
            [
                "Dénonciation de la violence",
                "Indignation face à la violence",
                "Détermination d'un persécuteur face à la violence",
            ],
        )
        self.assertIn("trois thèmes", PROMPT_THESES_DEFAUT)
        self.assertIn("indéterminé", PROMPT_THESES_DEFAUT)

    def test_affinement_ne_remplace_pas_les_titres(self):
        """L'affinement des définitions conserve les intitulés imposés."""
        import json
        from codage_qwen import THESES_INITIALES, proposer_trois_theses
        reponse = Mock()
        reponse.json.return_value = {
            "message": {
                "content": json.dumps({
                    "theses": [
                        {
                            "titre": THESES_INITIALES[0]["titre"],
                            "definition": "Définition Qwen 1.",
                        },
                        {
                            "titre": THESES_INITIALES[1]["titre"],
                            "definition": "Définition Qwen 2.",
                        },
                        {
                            "titre": THESES_INITIALES[2]["titre"],
                            "definition": "Définition Qwen 3.",
                        },
                    ]
                }, ensure_ascii=False)
            }
        }
        session = Mock()
        session.post.return_value = reponse
        resultats = proposer_trois_theses(
            ["Cette violence est inacceptable."],
            session=session,
            themes_imposes=list(THESES_INITIALES),
        )
        self.assertEqual(
            [item["titre"] for item in resultats],
            [item["titre"] for item in THESES_INITIALES],
        )
        self.assertEqual(resultats[2]["definition"], "Définition Qwen 3.")
        message = session.post.call_args.kwargs["json"]["messages"][1]["content"]
        self.assertIn("Intitulés IMPOSÉS", message)
        self.assertIn("persécuteur", message)

    def test_affinement_rejette_substitution_themes(self):
        """Un changement de classe par le modèle ne doit pas être masqué."""
        import json
        from codage_qwen import THESES_INITIALES, proposer_trois_theses
        reponse = Mock()
        reponse.json.return_value = {
            "message": {
                "content": json.dumps({
                    "theses": [
                        {
                            "titre": "Sujet sans rapport",
                            "definition": "Une nouvelle catégorie non autorisée.",
                        },
                        dict(THESES_INITIALES[1]),
                        dict(THESES_INITIALES[2]),
                    ]
                }, ensure_ascii=False)
            }
        }
        session = Mock()
        session.post.return_value = reponse
        with self.assertRaisesRegex(ValueError, "ne respecte pas"):
            proposer_trois_theses(
                ["Cette violence est inacceptable."],
                session=session,
                themes_imposes=list(THESES_INITIALES),
            )

    def test_schema_rejette_les_chaine_boolean(self):
        valeurs = {champ: "false" for champ in CHAMPS_BOOLEENS}
        valeurs.update({
            "acteur_cible": "", "indice_textuel": "", "justification": "",
        })
        with self.assertRaises(ValueError):
            verifier_resultat(valeurs)


if __name__ == "__main__":
    unittest.main()
