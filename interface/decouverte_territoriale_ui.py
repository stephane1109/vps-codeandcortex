"""Compatibilité avec les anciens imports de découverte territoriale.

L'interface complète de collecte de compte a été déplacée dans collcompte.py.
"""

from collcompte import afficher_collecte_de_compte as afficher_decouverte_territoriale

__all__ = ["afficher_decouverte_territoriale"]
