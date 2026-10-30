"""Extraction bornée de listes TikTok par l'API Python de gallery-dl.

Exécuté dans un processus distinct pour arrêter proprement les requêtes
réseau en cas d'annulation. Ne visite aucune URL de publication : seule
TiktokPostsExtractor.posts() est sollicitée.
"""
from __future__ import annotations

import argparse
import json
import sys


def signaler(etape):
    """Transmettre une étape non sensible au processus parent."""
    print("ETAPE:" + etape, file=sys.stderr, flush=True)


def recuperer_liste(compte, limite, delai):
    """Renvoyer les éléments itemList, sans page HTML de chaque vidéo."""
    from gallery_dl import config, extractor

    # Éviter les configurations héritées de l'hôte et les réessais prolongés.
    config.clear()
    config.set(("extractor",), "timeout", delai)
    config.set(("extractor",), "retries", 0)
    config.set(("extractor", "tiktok"), "order-posts", "desc")
    config.set(("extractor", "tiktok"), "tiktok-range", f"1-{limite}")
    config.set(("extractor", "tiktok"), "ytdl", False)

    url = f"https://www.tiktok.com/@{compte}/posts"
    signaler("initialisation")
    client = extractor.find(url)
    if client is None or client.__class__.__name__ != "TiktokPostsExtractor":
        raise RuntimeError("L'extracteur de profils TikTok est indisponible.")
    client.initialize()
    signaler("resolution_profil")

    # Le traitement des métadonnées est terminé à la sortie de posts().
    # L'appel items() provoquerait en plus une visite de chaque publication.
    def enregistrer_etape_api(fonction):
        def appeler(*args, **kwargs):
            signaler("liste_createur")
            return fonction(*args, **kwargs)
        return appeler
    client._extract_posts_api_legacy = enregistrer_etape_api(
        client._extract_posts_api_legacy)
    publications = client.posts()
    signaler("conversion_metadonnees")
    if not isinstance(publications, dict):
        publications = {}

    messages = []
    for objet in list(publications.values())[:limite]:
        if not isinstance(objet, dict):
            continue
        donnees = {
            cle: objet.get(cle)
            for cle in ("id", "author", "desc", "createTime", "stats",
                        "video", "imagePost", "video_tag", "videoTag",
                        "aigcLabelType", "aigc_label_type")
            if cle in objet
        }
        messages.append([2, "", donnees])
    return messages


def principal():
    """Ne jamais imprimer de cookies, d'URL signée ou de réponse brute."""
    analyseur = argparse.ArgumentParser()
    analyseur.add_argument("--compte", required=True)
    analyseur.add_argument("--limite", required=True, type=int)
    analyseur.add_argument("--delai", required=True, type=float)
    options = analyseur.parse_args()
    try:
        if not options.compte.replace("_", "").replace(".", "").isalnum():
            raise ValueError("Compte TikTok invalide.")
        if not 1 <= options.limite <= 500:
            raise ValueError("Limite de collecte invalide.")
        resultats = recuperer_liste(options.compte, options.limite, options.delai)
        print(json.dumps(resultats, ensure_ascii=False, separators=(",", ":")))
    except Exception as erreur:
        # Le nom de la classe suffit au diagnostic et ne révèle aucun secret.
        print("ERREUR:" + type(erreur).__name__, file=sys.stderr, flush=True)
        raise SystemExit(2) from None


if __name__ == "__main__":
    principal()
