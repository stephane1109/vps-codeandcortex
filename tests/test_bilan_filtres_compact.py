"""Vérifier que le bilan des filtres n'insère pas de lignes vides."""

import ast
import unittest
from pathlib import Path


RACINE = Path(__file__).resolve().parents[1]


class TestBilanFiltresCompact(unittest.TestCase):
    def test_un_seul_bloc_pour_tous_les_comptages(self):
        """Conserver les chiffres dans un seul élément Streamlit compact."""
        source = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(source)
        bilan = source.split('with st.expander("Bilan des filtres"', 1)[1]
        bilan = bilan.split('if actuel["date_debut"] or actuel["date_fin"]:', 1)[0]
        self.assertIn('lignes_bilan = [introduction_bilan]', bilan)
        self.assertIn('actuel["bilan_hashtags"].items()', bilan)
        self.assertIn("actuel['correspondances_hashtags']", bilan)
        self.assertIn("actuel['non_french']", bilan)
        self.assertIn("actuel['language_unknown']", bilan)
        self.assertIn("actuel['legendes_vides']", bilan)
        self.assertIn("actuel['errors']", bilan)
        self.assertIn('"<br>".join(html.escape(ligne) for ligne in lignes_bilan)', bilan)
        self.assertEqual(bilan.count("st.html("), 1)
        self.assertNotIn("st.write(", bilan)
        self.assertNotIn("st.caption(", bilan)


if __name__ == "__main__":
    unittest.main()
