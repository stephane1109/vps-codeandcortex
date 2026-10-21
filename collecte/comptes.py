"""Recherches ciblées compte + hashtag, avec contrôle des auteurs."""
from urllib.parse import quote

from .verification_comptes import normaliser_compte


def collecter_comptes_par_hashtag(navigateur, arguments, comptes, hashtag, rapport=None,
                                  liens_precedents=(), **options):
    """Parcourir un hashtag une seule fois pour tous les comptes sélectionnés."""
    from scraptiktok import normalize_hashtag
    from .hashtags import collecter_hashtag

    comptes = list(dict.fromkeys(normaliser_compte(compte) for compte in comptes))
    if not comptes:
        raise ValueError("Renseignez au moins un compte TikTok.")
    hashtag = normalize_hashtag(hashtag)
    rapport = rapport if rapport is not None else {}
    # Un ancien marqueur de compte ne doit pas rediriger vers /search/video.
    rapport.pop("compte_attendu", None)
    rapport.update(hashtag_url=f"https://www.tiktok.com/tag/{quote(hashtag)}",
                   comptes_attendus=comptes, mode_decouverte="hashtags_comptes",
                   exhaustif=False, recherches_en_echec=0)
    options["sans_connexion"] = True
    try:
        return collecter_hashtag(navigateur, arguments, rapport,
            comptes_attendus=comptes, liens_precedents=liens_precedents, **options)
    except Exception:
        rapport["recherches_en_echec"] = 1
        raise


def collecter_requete_compte(navigateur, arguments, compte, hashtag, rapport=None,
                             liens_precedents=(), **options):
    """Ouvrir une recherche compte + hashtag avec le moteur de collecte commun."""
    from scraptiktok import collect_links, normalize_hashtag
    from .recherche_comptes import adresse_recherche, construire_requete_compte

    compte, hashtag = normaliser_compte(compte), normalize_hashtag(hashtag)
    rapport = rapport if rapport is not None else {}
    rapport.update(compte_attendu=compte, comptes_attendus=[compte],
                   hashtag_url=adresse_recherche(compte, hashtag),
                   requete_recherche=construire_requete_compte(compte, hashtag), hashtag_recherche=hashtag,
                   mode_decouverte="recherche_compte_hashtag", exhaustif=False,
                   recherches_en_echec=0)
    options["sans_connexion"] = True
    try:
        # La sélection explicite garde le moteur commun : même attente et même
        # CAPTCHA que les hashtags, mais l'URL vise ce compte et ce hashtag.
        return collect_links(navigateur, arguments, rapport, comptes_attendus=[compte],
                             liens_precedents=liens_precedents, **options)
    except Exception:
        rapport["recherches_en_echec"] = 1
        raise
