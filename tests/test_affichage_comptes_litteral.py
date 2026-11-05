"""Vérifier que les identifiants TikTok restent littéraux dans l'interface."""

import ast
import unittest
from pathlib import Path


RACINE = Path(__file__).resolve().parents[1]


class TestAffichageComptesLitteral(unittest.TestCase):
    def test_comptes_et_medias_ne_sont_pas_interpretes_en_markdown(self):
        """Les tirets bas ne doivent jamais produire une mise en italique."""
        code = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(code)
        self.assertIn('st.text("Filtre des profils : " + ", ".join(', code)
        self.assertNotIn('st.write("Filtre des profils : " + ", ".join(', code)
        self.assertIn(
            'st.text(f"{media[\'nom\']} (@{media[\'compte\']})" '
            'if media else identifiant)',
            code,
        )


if __name__ == "__main__":
    unittest.main()
