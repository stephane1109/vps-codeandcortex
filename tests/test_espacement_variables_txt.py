"""Vérifier le regroupement compact des options TXT dans Streamlit."""

import ast
import unittest
from pathlib import Path


RACINE = Path(__file__).resolve().parents[1]


class TestEspacementVariablesTXT(unittest.TestCase):
    def test_bloc_compact_sans_changer_les_cles(self):
        """Préserver tous les widgets tout en supprimant leurs espaces verticaux."""
        code = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        ast.parse(code)
        self.assertIn('with st.container(key="bloc_variables_txt"):', code)
        self.assertIn(
            '.st-key-bloc_variables_txt [data-testid="stCheckbox"] label',
            code)
        self.assertIn('padding-block: 0 !important;', code)
        self.assertIn('row-gap: 0 !important;', code)
        for cle in (
            "collecter_follower_count",
            "follower_count_illustratif",
            "abonnes_classe_illustratif",
            "txt_region_code",
            "txt_is_verified",
            "collecter_commentaires",
        ):
            self.assertIn('key="' + cle + '"', code)
        self.assertIn('key="txt_" + nom', code)
        self.assertIn('key="txt_classe_" + nom', code)

    def test_commentaires_inclus_dans_le_meme_bloc(self):
        """La dernière case doit participer au même regroupement compact."""
        code = (RACINE / "streamlit_app.py").read_text(encoding="utf-8")
        section = code.split(
            'with st.container(key="bloc_variables_txt"):', 1)[1]
        entre_fin_et_options = section.split(
            'with st.expander("Options des commentaires"', 1)[0]
        self.assertIn(
            'st.checkbox("Collecter les textes des commentaires"',
            entre_fin_et_options)
        self.assertIn(
            '            st.checkbox("Collecter les textes des commentaires"',
            entre_fin_et_options)


if __name__ == "__main__":
    unittest.main()
