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
                           validation_initiale=True):
    """Découvrir les publications d'un profil, sans recherche par hashtag."""
    import time
    from selenium.common.exceptions import TimeoutException, WebDriverException
    from selenium.webdriver.support.ui import WebDriverWait
    import scraptiktok as moteur
    from .pagination_profils import defiler_grille_profil
    from .reseau_profils import ObservationProfil

    compte = normaliser_compte(compte)
    check = check or (lambda: None)
    url_profil = f"https://www.tiktok.com/@{compte}"
    rapport.update(mode_decouverte="profil_direct", hashtag_url=url_profil,
                   requete_recherche=f"@{compte} (profil public)",
                   compte_attendu=compte, discovered_urls=[],
                   candidats_ids=[], candidats_examines=0,
                   auteurs_ecartes=0, defilements_effectues=0,
                   pagination_profil=[], observation_reseau={},
                   exhaustif=False)
    observation = ObservationProfil(navigateur, compte, rapport["observation_reseau"], arguments.timeout)
    liens, candidats, exclus = {}, set(), set()
    tentatives_vides = max(2, arguments.idle_rounds)

    def publier():
        rapport.update(discovered_urls=list(liens.values()),
                       candidats_ids=sorted(candidats),
                       candidats_examines=len(candidats),
                       auteurs_ecartes_ids=sorted(exclus),
                       auteurs_ecartes=len(exclus),
                       retenues_par_compte={compte: len(liens)})
        if progress:
            progress(len(liens))

    def scanner():
        check()
        if not moteur.meme_page_tiktok(navigateur.current_url, url_profil):
            rapport["redirection_profil"] = True
            return False
        adresses = list(navigateur.execute_script(moteur.DISCOVER_JS) or [])
        adresses.extend(moteur.liens_donnees_publications(
            navigateur.execute_script(moteur.DONNEES_PUBLICATIONS_JS)))
        adresses.extend(observation.lire())
        avant = len(liens)
        for adresse in adresses:
            identite = moteur.canonical_post(adresse)
            if not identite:
                continue
            identifiant, canonique, auteur = identite
            candidats.add(identifiant)
            if auteur.casefold() != compte:
                exclus.add(identifiant)
            elif len(liens) < arguments.limit:
                liens.setdefault(identifiant, canonique)
        publier()
        return len(liens) > avant

    check()
    observation.demarrer()
    try:
        moteur.open_page(navigateur, url_profil)
        if moteur.diagnostiquer_page(navigateur, rapport)["code"] == "erreur_tiktok":
            rapport["discovery_stop"] = "erreur_profil"
            raise RuntimeError("TikTok affiche une erreur sur le profil public.")
        if moteur.type_intervention_tiktok(navigateur) == "captcha":
            if not arguments.interactive:
                moteur.diagnostiquer_page(navigateur, rapport, code="verification_tiktok")
                raise RuntimeError("Vérification TikTok nécessaire.")
            interact("Terminez le CAPTCHA du profil, puis cliquez sur Continuer.")
        if moteur.type_intervention_tiktok(navigateur) == "connexion":
            rapport["discovery_stop"] = "connexion_profil"
            raise RuntimeError("TikTok demande une connexion pour afficher le profil.")
        try:
            WebDriverWait(navigateur, arguments.timeout).until(lambda _: scanner())
        except TimeoutException:
            if arguments.interactive and validation_initiale:
                interact("Aucune publication visible sur le profil. Vérifiez la page ou un CAPTCHA, puis cliquez sur Continuer.")
                scanner()
        if not liens:
            moteur.diagnostiquer_page(navigateur, rapport)
            rapport["discovery_stop"] = "grille_profil_vide"
            raise RuntimeError("Le profil public ne fournit aucun lien de publication lisible.")

        inactif = 0
        for _ in range(arguments.max_scrolls):
            check()
            if len(liens) >= arguments.limit:
                rapport["discovery_stop"] = "limit"
                break
            nature = moteur.type_intervention_tiktok(navigateur)
            if nature == "captcha":
                if not arguments.interactive:
                    rapport["discovery_stop"] = "verification_tiktok"
                    break
                interact("Terminez le CAPTCHA pour charger la suite des vidéos du profil.")
            elif nature == "connexion":
                rapport["discovery_stop"] = "connexion_apres_resultats"
                break
            if not moteur.meme_page_tiktok(navigateur.current_url, url_profil):
                rapport["discovery_stop"] = "profil_redirige"
                break
            try:
                etape = defiler_grille_profil(navigateur, compte, reprendre=inactif > 0, check=check)
                rapport["pagination_profil"].append(etape)
                rapport["defilements_effectues"] += 1
                time.sleep(arguments.delay)
                WebDriverWait(navigateur, arguments.timeout).until(lambda _: scanner())
                inactif = 0
            except TimeoutException:
                inactif += 1
                if inactif >= tentatives_vides:
                    rapport["discovery_stop"] = "aucune_nouvelle_publication"
                    break
        else:
            rapport["discovery_stop"] = "max_scrolls"
        if len(liens) >= arguments.limit:
            rapport["discovery_stop"] = "limit"
        return list(liens.values())
    except WebDriverException as erreur:
        moteur.diagnostiquer_page(navigateur, rapport, erreur)
        if moteur.est_erreur_session(erreur):
            raise
        if liens:
            rapport["discovery_stop"] = "erreur_navigation_apres_resultats"
            return list(liens.values())
        raise
    finally:
        observation.fermer()
        publier()
        rapport["collecte_partielle"] = len(liens) < arguments.limit


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
        validation_initiale=options.get("validation_initiale", True)))

    if not liens:
        def recherche_ciblee(etat, suivi):
            etat["compte_attendu"] = compte
            return collecter_recherche_compte(
                navigateur, arguments, etat,
                interact=intervenir, progress=suivi, check=verifier)

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
                   bilan_recherche=(f"@{compte} : {len(liens)} publication(s) du compte retrouvée(s). "
                                    "Grille du profil en priorité ; recherche par @identifiant en secours. "
                                    "Aucun résultat d'autres auteurs n'est conservé. "
                                    "Accès public potentiellement incomplet."))
    if not liens and erreur_finale is not None:
        raise erreur_finale
    return list(liens.values())
