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
    from .recherche_comptes import adresse_recherche

    compte, hashtag = normaliser_compte(compte), normalize_hashtag(hashtag)
    rapport = rapport if rapport is not None else {}
    rapport.update(compte_attendu=compte, comptes_attendus=[compte],
                   hashtag_url=adresse_recherche(compte, hashtag),
                   requete_recherche=f"@{compte} #{hashtag}", hashtag_recherche=hashtag,
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


def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Rechercher chaque hashtag pour ce compte, dans la même session Selenium."""
    from scraptiktok import canonical_post, est_erreur_session, normalize_hashtag, WebDriverException

    compte = normaliser_compte(compte)
    hashtags = list(dict.fromkeys(normalize_hashtag(h) for h in hashtags))
    if not hashtags:
        raise ValueError("Renseignez au moins un hashtag pour une collecte par profil ou média.")
    rapport = rapport if rapport is not None else {}
    liens, candidats, exclus, recherches = {}, set(), set(), []
    options = dict(options)
    interaction = options.get("interact")
    progression = options.pop("progress", None)
    session_validee = False
    derniere_erreur = None

    def intervenir(message):
        nonlocal session_validee
        if interaction:
            interaction(message)
        else:
            from scraptiktok import manual_step
            manual_step(message)
        session_validee = True

    for hashtag in hashtags:
        courant = {"requete_recherche": f"@{compte} #{hashtag}"}
        recherches.append(courant)

        def publier(_nombre=0):
            retenus = dict(liens)
            for url in courant.get("discovered_urls", []):
                identite = canonical_post(url)
                if identite and identite[2].casefold() == compte and len(retenus) < arguments.limit:
                    retenus.setdefault(identite[0], identite[1])
            tous_candidats = candidats | set(courant.get("candidats_ids", []))
            tous_exclus = exclus | set(courant.get("auteurs_ecartes_ids", []))
            echecs = sum(r.get("recherches_en_echec", 0) for r in recherches)
            rapport.pop("diagnostic", None)
            rapport.update(courant, compte_attendu=compte, recherches_hashtags=recherches,
                candidats_ids=sorted(tous_candidats), candidats_examines=len(tous_candidats),
                auteurs_ecartes_ids=sorted(tous_exclus), auteurs_ecartes=len(tous_exclus),
                discovered_urls=list(retenus.values()), hashtags_filtres=hashtags,
                retenues_par_compte={compte: len(retenus)}, recherches_en_echec=echecs,
                objectif_liens=arguments.limit, objectif_atteint=len(retenus) >= arguments.limit,
                collecte_partielle=len(retenus) < arguments.limit or bool(echecs), exhaustif=False)
            if progression:
                progression(len(retenus))

        reglages = dict(options, interact=intervenir, progress=publier,
                        validation_initiale=options.get("validation_initiale", True) and not session_validee)
        publier()
        try:
            resultat = collecter_requete_compte(navigateur, arguments, compte, hashtag,
                courant, liens_precedents=list(liens.values()), **reglages)
            for url in resultat:
                identite = canonical_post(url)
                if identite and identite[2].casefold() == compte and len(liens) < arguments.limit:
                    liens.setdefault(identite[0], identite[1])
        except (RuntimeError, WebDriverException) as erreur:
            derniere_erreur = erreur
            if est_erreur_session(erreur):
                raise
        finally:
            # Une erreur tardive ne doit pas perdre les liens déjà découverts.
            for url in courant.get("discovered_urls", []):
                identite = canonical_post(url)
                if identite and identite[2].casefold() == compte and len(liens) < arguments.limit:
                    liens.setdefault(identite[0], identite[1])
            candidats.update(courant.get("candidats_ids", []))
            exclus.update(courant.get("auteurs_ecartes_ids", []))
            publier()
        if len(liens) >= arguments.limit:
            break

    rapport["bilan_recherche"] = (
        f"@{compte} : {len(liens)} lien(s) retenu(s) dans les recherches ciblées compte + hashtag. "
        "L'historique complet du compte n'est pas garanti.")
    if rapport["recherches_en_echec"]:
        rapport["bilan_recherche"] += " Une ou plusieurs recherches ciblées ont échoué ; voir leur diagnostic."
    if not liens and derniere_erreur is not None and rapport["recherches_en_echec"] == len(recherches):
        raise derniere_erreur
    if not liens and not rapport["recherches_en_echec"]:
        rapport["diagnostic"] = {"code": "compte_absent_des_resultats"}
        rapport["bilan_recherche"] += " TikTok n'a fourni aucune publication de cet auteur dans ces résultats ; cela ne signifie pas que le compte est vide."
    return list(liens.values())
