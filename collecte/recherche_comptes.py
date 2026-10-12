"""Découverte exclusive par la recherche vidéo TikTok d'un identifiant exact."""
import time
from urllib.parse import quote

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

from .pagination_recherche import defiler_resultats, etat_resultats
from .reseau_recherche import ObservationRecherche
from .verification_comptes import normaliser_compte


LIENS_RECHERCHE_JS = """
return Array.from(document.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]')).map(e => e.href);
"""


def adresse_recherche(compte, hashtag=None):
    """Cibler l'identifiant et, s'il est fourni, le hashtag dans la requête."""
    requete = "@" + normaliser_compte(compte)
    if hashtag is not None:
        from scraptiktok import normalize_hashtag
        requete += " #" + normalize_hashtag(hashtag)
    return "https://www.tiktok.com/search/video?q=" + quote(requete, safe="")


def collecter_recherche_compte(navigateur, arguments, rapport, *, interact, progress=None, check=None):
    """Parcourir les résultats successifs et conserver uniquement l'auteur exact."""
    import scraptiktok as moteur
    compte = normaliser_compte(rapport["compte_attendu"])
    check = check or (lambda: None)
    rapport.update(compte_attendu=compte, hashtag_url=adresse_recherche(compte),
                   mode_decouverte="recherche_video", exhaustif=False, collecte_partielle=True,
                   discovered_urls=[], candidats_ids=[], candidats_examines=0,
                   pagination_recherche=[], observation_reseau={})
    observation = ObservationRecherche(navigateur, compte, rapport["observation_reseau"], arguments.timeout)
    candidats, identites, liens = {}, {}, {}
    donnees_confirmees = set()
    tentatives_vides = max(3, arguments.idle_rounds)
    budget = max(arguments.max_scrolls, arguments.limit * 4)
    rapport.update(tentatives_sans_nouveaute=tentatives_vides, budget_defilements=budget)

    def publier_compteurs():
        rapport.update(candidats_ids=list(candidats), candidats_examines=len(candidats),
                       discovered_urls=list(liens.values()),
                       auteurs_ecartes=sum(auteur.casefold() != compte for _, auteur in identites.values()),
                       objectif_liens=arguments.limit, objectif_atteint=len(liens) >= arguments.limit)
        if progress:
            progress(len(liens))

    def afficher(motif, message):
        rapport.setdefault("interventions_automatiques", []).append(motif)
        interact(message)
        check()

    def surveiller():
        check()
        if moteur.type_intervention_tiktok(navigateur) == "captcha":
            if not arguments.interactive:
                rapport["discovery_stop"] = "blocked"
                moteur.diagnostiquer_page(navigateur, rapport, code="verification_tiktok")
                raise RuntimeError("La recherche TikTok demande un CAPTCHA.")
            afficher("captcha", "TikTok demande un CAPTCHA. Terminez-le dans la fenêtre, puis cliquez sur Continuer.")
        moteur.fermer_invitation_connexion(navigateur)

    def sur_la_recherche():
        """Une redirection vers un profil ne devient jamais une source de liens."""
        return moteur.meme_page_tiktok(navigateur.current_url, rapport["hashtag_url"])

    def scanner(_):
        surveiller()
        if not sur_la_recherche():
            rapport["redirection_recherche"] = True
            return False
        avant = (len(candidats), tuple(liens))
        sources = [
            (navigateur.execute_script(LIENS_RECHERCHE_JS) or [], False),
            (moteur.liens_donnees_publications(navigateur.execute_script(moteur.DONNEES_PUBLICATIONS_JS)), True),
            (observation.lire(), True),
        ]
        for urls, donnee_auteur in sources:
            for url in urls:
                identite = moteur.canonical_post(url)
                if not identite:
                    continue
                identifiant, canonique, auteur = identite
                candidats.setdefault(identifiant, None)
                # Les objets vidéo fournissent l'auteur, pas le texte de la requête.
                # Leur identité prime sur un lien HTML contradictoire de même ID.
                if donnee_auteur or identifiant not in donnees_confirmees:
                    identites[identifiant] = (canonique, auteur)
                if donnee_auteur:
                    donnees_confirmees.add(identifiant)
        liens.clear()
        for identifiant in candidats:
            url, auteur = identites[identifiant]
            if auteur.casefold() == compte and len(liens) < arguments.limit:
                liens[identifiant] = url
        publier_compteurs()
        return avant != (len(candidats), tuple(liens))

    aide_vide = aide_blocage = False
    inactif = 0
    check()
    observation.demarrer()
    try:
        moteur.open_page(navigateur, rapport["hashtag_url"])
        # Le premier passage lit la page ; les suivants chargent sa suite.
        for tour in range(budget + 1):
            check()
            if len(liens) >= arguments.limit:
                rapport["discovery_stop"] = "limit"
                break
            surveiller()
            defilement = None
            if tour and sur_la_recherche() and moteur.type_intervention_tiktok(navigateur) != "connexion":
                defilement = defiler_resultats(navigateur, reprendre=inactif > 0, check=check)
                defilement["decouvertes_avant"] = len(candidats)
                defilement["retenues_avant"] = len(liens)
                rapport["pagination_recherche"].append(defilement)
                time.sleep(arguments.delay)

            def attendre_suite(_):
                if scanner(navigateur):
                    return True
                if defilement:
                    etat = etat_resultats(navigateur)
                    defilement["apres"] = {c: etat[c] for c in defilement["apres"]}
                    # Traverser une grille déjà chargée ne constitue pas une panne
                    # de pagination tant que le bas n'a pas encore été atteint.
                    return not etat["fin"] and etat["position"] > defilement["avant"]["position"] + 2
                return False

            try:
                WebDriverWait(navigateur, arguments.timeout).until(attendre_suite)
                inactif = 0
            except TimeoutException:
                inactif += 1
            finally:
                if defilement:
                    defilement.update(decouvertes_apres=len(candidats), retenues_apres=len(liens))
            if len(liens) >= arguments.limit:
                rapport["discovery_stop"] = "limit"
                break
            if not candidats and arguments.interactive and not aide_vide:
                aide_vide = True
                afficher("recherche_sans_liens", f"La recherche vidéo de @{compte} n’affiche pas encore de publication lisible. "
                         "La fenêtre s’ouvre automatiquement. Traitez une éventuelle vérification, puis cliquez sur Continuer.")
                scanner(navigateur)
                inactif = 0
                continue
            if inactif >= tentatives_vides:
                page = observation.derniere_page or {}
                connexion = moteur.type_intervention_tiktok(navigateur) == "connexion"
                if arguments.interactive and not aide_blocage and (connexion or page.get("suite") is not False):
                    aide_blocage = True
                    afficher("recherche_bloquee", "La recherche TikTok ne charge plus de nouvelles publications. "
                             "Traitez une éventuelle vérification dans la fenêtre, puis cliquez sur Continuer pour réessayer. "
                             "Les publications déjà obtenues sont conservées.")
                    scanner(navigateur)
                    inactif = 0
                    continue
                rapport["discovery_stop"] = ("connexion_apres_resultats" if connexion else
                    "fin_recherche_signalee" if page.get("suite") is False else "recherche_stagnante")
                break
        else:
            rapport["discovery_stop"] = "budget_defilements"
        if len(liens) >= arguments.limit:
            rapport["discovery_stop"] = "limit"
        if not candidats:
            moteur.diagnostiquer_page(navigateur, rapport)
            if not sur_la_recherche():
                rapport["diagnostic"]["code"] = "recherche_redirigee"
            raise RuntimeError("La recherche TikTok ne fournit aucune publication accessible après plusieurs chargements.")
        return list(liens.values())
    except WebDriverException as erreur:
        moteur.diagnostiquer_page(navigateur, rapport, erreur)
        if moteur.est_erreur_session(erreur):
            rapport["diagnostic"] = {"code": "erreur_session", "exception": type(erreur).__name__}
            rapport["discovery_stop"] = "erreur_session"
            raise
        rapport["discovery_stop"] = "erreur_recherche"
        if liens:
            return list(liens.values())
        raise
    finally:
        observation.fermer()
        publier_compteurs()
        rapport["collecte_partielle"] = rapport.get("discovery_stop") != "limit"
        rapport["limite_acces_public"] = rapport.get("discovery_stop") == "connexion_apres_resultats"
        if rapport["collecte_partielle"] and "diagnostic" not in rapport:
            rapport["diagnostic"] = {"code": "resultats_incomplets", "motif": rapport.get("discovery_stop")}
        rapport["bilan_recherche"] = ("Limite demandée atteinte ; les résultats de recherche ne garantissent pas l’historique complet du compte."
            if not rapport["collecte_partielle"] else
            "Collecte partielle : seuls les résultats accessibles de la recherche TikTok ont été récupérés. L’historique du compte n’est pas exhaustif.")
