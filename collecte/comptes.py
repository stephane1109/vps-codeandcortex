"""Collecte des comptes dans les pages de hashtags, avec contrôle des auteurs."""
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


def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Adapter les appels par profil au parcours des hashtags obligatoires."""
    from scraptiktok import canonical_post, est_erreur_session, normalize_hashtag, WebDriverException

    compte = normaliser_compte(compte)
    hashtags = list(dict.fromkeys(normalize_hashtag(h) for h in hashtags))
    if not hashtags:
        raise ValueError("Renseignez au moins un hashtag pour une collecte par profil ou média.")
    rapport = rapport if rapport is not None else {}
    liens, candidats, recherches = {}, set(), []
    options = dict(options)
    interaction = options.get("interact")
    session_validee = False

    def intervenir(message):
        nonlocal session_validee
        if interaction:
            interaction(message)
        else:
            from scraptiktok import manual_step
            manual_step(message)
        session_validee = True

    for hashtag in hashtags:
        courant = {}
        reglages = dict(options, interact=intervenir,
                        validation_initiale=options.get("validation_initiale", True) and not session_validee)
        try:
            resultat = collecter_comptes_par_hashtag(navigateur, arguments, [compte], hashtag,
                courant, liens_precedents=list(liens.values()), **reglages)
            for url in resultat:
                identite = canonical_post(url)
                if identite and identite[2].casefold() == compte and len(liens) < arguments.limit:
                    liens.setdefault(identite[0], identite[1])
        except (RuntimeError, WebDriverException) as erreur:
            if est_erreur_session(erreur) or len(hashtags) == 1:
                raise
            if len(recherches) == len(hashtags) - 1 and not liens:
                raise
        finally:
            candidats.update(courant.get("candidats_ids", []))
            recherches.append(courant)
            rapport.update(courant, recherches_hashtags=recherches,
                candidats_ids=sorted(candidats), candidats_examines=len(candidats),
                discovered_urls=list(liens.values()), hashtags_filtres=hashtags,
                recherches_en_echec=sum(r.get("recherches_en_echec", 0) for r in recherches),
                collecte_partielle=len(liens) < arguments.limit, exhaustif=False)
        if len(liens) >= arguments.limit:
            break
    return list(liens.values())
