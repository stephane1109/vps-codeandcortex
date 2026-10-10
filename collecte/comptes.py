"""Recherche de publications avec contrôle strict du compte auteur."""
from copy import copy
from urllib.parse import quote
from .verification_comptes import normaliser_compte


def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Réutiliser les pages de hashtags, ou la recherche vidéo sans hashtag."""
    from scraptiktok import collect_links, normalize_hashtag, canonical_post, manual_step, WebDriverException
    compte = normaliser_compte(compte)
    rapport = rapport if rapport is not None else {}
    hashtags = list(dict.fromkeys(normalize_hashtag(h) for h in hashtags))
    recherches = (["https://www.tiktok.com/tag/" + quote(h) for h in hashtags]
                  if hashtags else ["https://www.tiktok.com/search?q=" + quote("@" + compte)])
    rapport.update(compte_attendu=compte, mode_decouverte="hashtags" if hashtags else "recherche_compte",
                   recherches=[], exhaustif=False)
    liens = {}
    erreurs = []
    validation = options.pop("validation_initiale", True)
    interaction = options.pop("interact", manual_step)

    def intervenir(message):
        nonlocal validation
        interaction(message)
        validation = False

    for url in recherches:
        if len(liens) >= arguments.limit:
            break
        recherche = {"hashtag_url": url, "compte_attendu": compte}
        rapport["recherches"].append(recherche)
        # La borne vaut pour le compte entier, même avec deux hashtags.
        bornes = copy(arguments)
        bornes.limit = arguments.limit
        try:
            trouves = collect_links(navigateur, bornes, recherche, interact=intervenir,
                                    validation_initiale=validation, **options)
        except (RuntimeError, WebDriverException) as erreur:
            recherche["erreur"] = str(erreur)
            erreurs.append(erreur)
            continue
        rapport.update({k: recherche[k] for k in ("hashtag_url", "discovery_stop") if k in recherche})
        for lien in trouves:
            identite = canonical_post(lien)
            if identite and identite[2].lower() == compte and len(liens) < arguments.limit:
                liens.setdefault(identite[0], identite[1])
    rapport["recherches_en_echec"] = len(erreurs)
    rapport["discovered_urls"] = list(liens.values())
    if erreurs and len(erreurs) == len(rapport["recherches"]):
        rapport.update({k: recherche[k] for k in ("hashtag_url", "diagnostic", "discovery_stop") if k in recherche})
        raise erreurs[-1]
    # Une page de recherche ne permet pas de certifier le profil ou son badge.
    rapport["verification"] = {"compte": compte, "concordant": None,
                               "raison": "recherche_avec_filtrage_auteur"}
    return list(liens.values())
