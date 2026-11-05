"""Normaliser une ville associée à la sélection des comptes TikTok.

Il s'agit d'une métadonnée déclarée par le chercheur ou issue de
l'inventaire territorial, et non d'une géolocalisation TikTok vérifiée.
"""

import re
import unicodedata


def normaliser_ville_etude(valeur):
    """Produire une modalité IRaMuTeQ sûre : Toulouse -> toulouse."""
    texte = str(valeur or "").strip()
    if not texte:
        return ""
    if len(texte) > 80:
        raise ValueError("La ville associée au corpus ne peut dépasser 80 caractères.")
    # Accepter aussi une notation déjà préparée pour IRaMuTeQ.
    if texte.casefold().startswith("*ville_"):
        texte = texte[7:]
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r"[^a-z0-9]+", "_", texte.casefold()).strip("_")
    if not texte:
        raise ValueError("Renseignez un nom de ville exploitable pour IRaMuTeQ.")
    return texte


def balise_ville_etude(valeur):
    """Formater la modalité du corpus, sans caractère de contrôle ni injection."""
    ville = normaliser_ville_etude(valeur)
    return "*ville_" + ville if ville else ""
