"""Normalisation partagée des listes de hashtags pour l'interface et l'API."""
import argparse
import re

from scraptiktok import normalize_hashtag

MAX_HASHTAGS = 10


def separer_saisie_hashtags(saisie):
    """Accepter les virgules, les points-virgules, les espaces et les retours ligne."""
    return [valeur for valeur in re.split(r"[\s,;]+", saisie.strip()) if valeur]


def normaliser_liste_hashtags(valeurs):
    """Valider, dédoublonner sans distinction de casse et limiter à dix hashtags."""
    hashtags = []
    deja_vus = set()
    for valeur in valeurs:
        try:
            hashtag = normalize_hashtag(valeur)
        except argparse.ArgumentTypeError as erreur:
            raise ValueError(str(erreur)) from erreur
        cle = hashtag.casefold()
        if cle not in deja_vus:
            deja_vus.add(cle)
            hashtags.append(hashtag)
        if len(hashtags) > MAX_HASHTAGS:
            raise ValueError(f"Vous pouvez saisir au maximum {MAX_HASHTAGS} hashtags distincts.")
    return hashtags
