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
      
def collecter_profil_public(navigateur, arguments, compte, rapport, *,
                           interact, progress=None, check=None,
                           validation_initiale=True, cibler_onglet_videos=False):
    """Découvrir les vidéos d'un compte par sa grille réellement paginée.

    L'ancien parcours cessait parfois après la première grille (environ six
    vignettes). Le module dédié sélectionne l'onglet Publications lorsqu'il
    existe, observe les réponses publiques successives et signale les limites
    d'accès sans contourner la connexion ou un CAPTCHA.
    """
    from .profil_selenium import collecter_grille_profil

    compte = normaliser_compte(compte)
    rapport.update(
        mode_decouverte="profil_direct",
        hashtag_url=f"https://www.tiktok.com/@{compte}",
        requete_recherche=f"@{compte} (profil public)",
        compte_attendu=compte,
        exhaustif=False,
    )
    liens = collecter_grille_profil(
        navigateur, arguments, rapport,
        interact=interact, progress=progress, check=check,
        cibler_onglet_videos=cibler_onglet_videos,
    )
    rapport.update(
        candidats_examines=len(liens),
        retenues_par_compte={compte: len(liens)},
        collecte_partielle=len(liens) < arguments.limit,
    )
    return liens

def collecter_compte(navigateur, arguments, compte, rapport=None, hashtags=(), **options):
    """Collecter exclusivement l'auteur sélectionné, sans pages générales de hashtags.

    Ordre : grille publique du profil, puis recherche vidéo par @identifiant seul
    si la grille ne fournit aucune publication. Les hashtags sont filtrés plus tard
    sur les légendes effectivement lues, jamais pendant la découverte.
    """
    from scraptiktok import canonical_post, est_erreur_session, WebDriverException
    from .recherche_comptes import collecter_recherche_compte

    compte = normaliser_compte(compte)
    rapport = rapport if rapport is not None else {}
    verifier = options.get("check")
    progression = options.get("progress")
    intervenir = options.get("interact")
    presse_videos_uniquement = bool(options.get("presse_videos_uniquement"))
    etapes, liens = [], {}
    erreur_finale = None

    def executer(etape, fonction):
        nonlocal erreur_finale
        etat = {"requete_recherche": etape, "discovered_urls": []}
        etapes.append(etat)

        def suivre(_nombre):
            for adresse in etat.get("discovered_urls", []):
                identite = canonical_post(adresse)
                if identite and identite[2].casefold() == compte and len(liens) < arguments.limit:
                    liens.setdefault(identite[0], identite[1])
            rapport.update(requete_recherche=etape,
                           recherches_compte=etapes,
                           candidats_examines=sum(r.get("candidats_examines", 0) for r in etapes),
                           discovered_urls=list(liens.values()),
                           retenues_par_compte={compte: len(liens)})
            if progression:
                progression(len(liens))

        try:
            trouves = fonction(etat, suivre)
            for adresse in trouves:
                identite = canonical_post(adresse)
                if identite and identite[2].casefold() == compte and len(liens) < arguments.limit:
                    liens.setdefault(identite[0], identite[1])
        except (RuntimeError, WebDriverException) as erreur:
            erreur_finale = erreur
            etat["echec"] = type(erreur).__name__
            etat["message_erreur"] = str(erreur)
            if est_erreur_session(erreur):
                raise
        finally:
            suivre(len(liens))

    executer(f"@{compte} : profil", lambda etat, suivi: collecter_profil_public(
        navigateur, arguments, compte, etat,
        interact=intervenir, progress=suivi, check=verifier,
        validation_initiale=options.get("validation_initiale", True),
        cibler_onglet_videos=presse_videos_uniquement))

    # Compléter jusqu'au nombre demandé pour CHAQUE compte, même si la
    # grille a déjà fourni quelques vidéos (ex. 6/50 ou 8/50).
    if len(liens) < arguments.limit and not presse_videos_uniquement:
        def recherche_ciblee(etat, suivi):
            etat["compte_attendu"] = compte
            return collecter_recherche_compte(
                navigateur, arguments, etat,
                interact=intervenir, progress=suivi, check=verifier,
                liens_precedents=list(liens.values()),
                intervention_si_vide=False)

        executer(f"@{compte} : recherche vidéo", recherche_ciblee)
        # collecter_recherche_compte fournit des liens filtrés par auteur exact.
        # Un résultat d'autres comptes ne doit jamais entrer dans le corpus.

    rapport.update(recherches_compte=etapes,
                   discovered_urls=list(liens.values()),
                   retenues_par_compte={compte: len(liens)},
                   recherches_en_echec=sum(bool(e.get("echec")) for e in etapes),
                   candidats_examines=sum(e.get("candidats_examines", 0) for e in etapes),
                   collecte_partielle=len(liens) < arguments.limit or any(e.get("echec") for e in etapes),
                   exhaustif=False,
                   bilan_recherche=(
                       f"@{compte} : {len(liens)}/{arguments.limit} vidéo(s) découvertes "
                       "dans l'onglet Vidéos du profil. Aucune recherche @compte "
                       "n'est utilisée en mode Presse ; résultats partiels "
                       "si TikTok ne charge pas les pages suivantes."
                       if presse_videos_uniquement else
                       f"@{compte} : {len(liens)}/{arguments.limit} publication(s) "
                       "publiques accessibles. Grille du profil, puis recherche par "
                       "@identifiant pour compléter les résultats manquants. "
                       "Seul l'auteur sélectionné est conservé ; le nombre demandé "
                       "est un objectif, non une garantie d'accès."
                   ))
    if not liens and erreur_finale is not None:
        raise erreur_finale
    return list(liens.values())
