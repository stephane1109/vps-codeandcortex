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
      
def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Parcourir le profil public, puis compléter par les hashtags."""
    from scraptiktok import (
        canonical_post, collect_links, est_erreur_session,
        normalize_hashtag, WebDriverException,
    )

    compte = normaliser_compte(compte)
    hashtags = list(dict.fromkeys(normalize_hashtag(h) for h in hashtags))
    if not hashtags:
        raise ValueError("Renseignez au moins un hashtag.")

    rapport = rapport if rapport is not None else {}
    options = dict(options)
    interaction = options.pop("interact", None)
    progression = options.pop("progress", None)
    validation_initiale = options.pop("validation_initiale", True)
    liens = {}
    recherches = []
    derniere_erreur = None
    session_validee = False

    def intervenir(message):
        nonlocal session_validee
        if interaction is not None:
            interaction(message)
        else:
            from scraptiktok import manual_step
            manual_step(message)
        session_validee = True

    def explorer(adresse, etiquette, mode):
        nonlocal derniere_erreur
        courant = {
            "hashtag_url": adresse,
            "requete_recherche": etiquette,
            "mode_decouverte": mode,
            "compte_attendu": compte,
            "recherches_en_echec": 0,
        }
        recherches.append(courant)

        def publier(_nombre=0):
            visibles = dict(liens)
            for url in courant.get("discovered_urls", []):
                identite = canonical_post(url)
                if identite and identite[2].casefold() == compte and len(visibles) < arguments.limit:
                    visibles.setdefault(identite[0], identite[1])
            rapport.update(
                requete_recherche=etiquette,
                candidats_examines=sum(r.get("candidats_examines", 0) for r in recherches),
                recherches_hashtags=recherches,
                discovered_urls=list(visibles.values()),
                retenues_par_compte={compte: len(visibles)},
                recherches_en_echec=sum(r.get("recherches_en_echec", 0) for r in recherches),
            )
            if progression:
                progression(len(visibles))

        reglages = dict(
            options,
            interact=intervenir,
            progress=publier,
            validation_initiale=validation_initiale and not session_validee,
        )
        try:
            collect_links(
                navigateur, arguments, courant,
                comptes_attendus=[compte],
                liens_precedents=list(liens.values()),
                **reglages,
            )
        except (RuntimeError, WebDriverException) as erreur:
            derniere_erreur = erreur
            courant["recherches_en_echec"] = 1
            courant["erreur"] = str(erreur)
            if est_erreur_session(erreur):
                raise
        finally:
            for url in courant.get("discovered_urls", []):
                identite = canonical_post(url)
                if identite and identite[2].casefold() == compte and len(liens) < arguments.limit:
                    liens.setdefault(identite[0], identite[1])
            publier()

    explorer(f"https://www.tiktok.com/@{compte}", f"@{compte}", "profil_direct")

    if len(liens) < arguments.limit:
        for hashtag in hashtags:
            explorer(
                f"https://www.tiktok.com/tag/{quote(hashtag)}",
                f"#{hashtag}",
                "hashtags_comptes",
            )
            if len(liens) >= arguments.limit:
                break

    rapport.update(
        discovered_urls=list(liens.values()),
        recherches_hashtags=recherches,
        recherches_en_echec=sum(r.get("recherches_en_echec", 0) for r in recherches),
        retenues_par_compte={compte: len(liens)},
        collecte_partielle=len(liens) < arguments.limit,
        exhaustif=False,
        bilan_recherche=(
            f"@{compte} : {len(liens)} publication(s) publique(s) découverte(s). "
            "Profil parcouru en premier ; hashtags utilisés en complément. "
            "Résultats non exhaustifs."
        ),
    )
    if not liens and derniere_erreur is not None:
        raise derniere_erreur
    return list(liens.values())
