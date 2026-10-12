"""Découverte des comptes exclusivement depuis la recherche vidéo TikTok."""
from .verification_comptes import normaliser_compte
from .recherche_comptes import adresse_recherche


def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Rechercher @compte ; les hashtags sont filtrés ensuite sur les légendes."""
    from scraptiktok import collect_links, normalize_hashtag
    compte = normaliser_compte(compte)
    rapport = rapport if rapport is not None else {}
    rapport.update(compte_attendu=compte, hashtag_url=adresse_recherche(compte),
                   hashtags_filtres=list(dict.fromkeys(normalize_hashtag(h) for h in hashtags)),
                   mode_decouverte="recherche_video", exhaustif=False, recherches_en_echec=0)
    options["validation_initiale"] = False
    options["intervention_si_vide"] = True
    options["sans_connexion"] = True
    try:
        return collect_links(navigateur, arguments, rapport, **options)
    except Exception:
        rapport["recherches_en_echec"] = 1
        raise
