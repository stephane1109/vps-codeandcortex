"""Test du GCN/VAE sans téléchargement du modèle multilingue."""
import importlib.util
import sys
import types
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

try:
    import torch
except ImportError:
    torch = None

CHEMIN = Path(__file__).resolve().parents[1] / "applications" / "dartopic" / "modele_dartopic.py"


@unittest.skipIf(torch is None, "PyTorch non disponible")
class TestDARTopic(unittest.TestCase):
    def test_calcul_synthetique(self):
        sauvegarde = sys.modules.get("transformers")
        sys.modules["transformers"] = types.SimpleNamespace(AutoModel=None, AutoTokenizer=None)
        try:
            spec = importlib.util.spec_from_file_location("dartopic_sans_reseau", CHEMIN)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        finally:
            if sauvegarde is None:
                del sys.modules["transformers"]
            else:
                sys.modules["transformers"] = sauvegarde

        def encodeur_factice(textes, parametres, progression):
            hasard = np.random.default_rng(42)
            embeddings = hasard.normal(size=(len(textes), 8, 12)).astype("float16")
            masques = np.ones((len(textes), 8), dtype="float32")
            return embeddings, masques

        module._encoder_tokens = encodeur_factice
        textes = ["police foule charge", "manifestants police intervention",
                  "manifestation calme", "la foule filme", "violence et videos",
                  "discours violence", "police et manifestation"]
        parametres = replace(module.ParametresDARTopic(), nombre_themes=2,
                             nombre_epoques=2, taille_lot=3, frequence_minimale=1)
        resultat = module.entrainer_dartopic(textes, parametres)
        self.assertEqual(resultat["distribution"].shape, (len(textes), 2))
        self.assertTrue(np.allclose(resultat["distribution"].sum(axis=1), 1, atol=0.0001))
        self.assertEqual(len(resultat["themes"]), 2)
        self.assertEqual(len(resultat["historique"]), 2)


if __name__ == "__main__":
    unittest.main()
