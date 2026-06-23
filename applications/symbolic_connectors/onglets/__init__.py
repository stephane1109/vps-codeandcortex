"""# Interface des onglets

Ce module centralise l'import des fonctions de rendu de chaque onglet
Streamlit (densité, connecteurs, TF-IDF, etc.) afin de simplifier leur
exposition dans l'application principale.

## Dépendances
- Modules locaux `onglet_*.py` : chaque onglet spécialisé est importé et
  réexporté via `__all__`.
- Bibliothèque Streamlit : les fonctions importées reposent sur Streamlit
  pour afficher les interfaces utilisateur.
"""
from .onglet_connecteurs import rendu_connecteurs
from .onglet_anova import rendu_anova
from .onglet_densite import rendu_densite
from .onglet_donnees_brutes import rendu_donnees_brutes
from .onglet_hash import rendu_hash
from .onglet_import import parse_upload, rendu_donnees_importees
from .onglet_chi2 import rendu_chi2
from .onglet_lisibilite import rendu_lisibilite
from .onglet_ngram import rendu_ngram
from .onglet_openlexicon import rendu_openlexicon
from .onglet_patterns import rendu_patterns
from .onglet_regex_motifs import rendu_regex_motifs
from .onglet_simi_cosinus import rendu_simi_cosinus
from .onglet_sous_corpus import rendu_sous_corpus
from .onglet_tfidf import rendu_tfidf

__all__ = [
    "parse_upload",
    "rendu_anova",
    "rendu_connecteurs",
    "rendu_densite",
    "rendu_donnees_brutes",
    "rendu_donnees_importees",
    "rendu_hash",
    "rendu_chi2",
    "rendu_lisibilite",
    "rendu_ngram",
    "rendu_openlexicon",
    "rendu_patterns",
    "rendu_regex_motifs",
    "rendu_simi_cosinus",
    "rendu_sous_corpus",
    "rendu_tfidf",
]
