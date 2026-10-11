"""Parcours Selenium dédié aux publications publiques d'un profil TikTok."""
import time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

from .pagination_profils import defiler_grille_profil, etat_grille_profil
from .reseau_profils import ObservationProfil


ONGLET_PUBLICATIONS_JS = """
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
const candidats = Array.from(document.querySelectorAll(
    '[data-e2e="videos-tab"], [data-e2e="user-post-tab"], [role="tab"]'));
return candidats.find(e => visible(e) &&
    (/^(vidéos|videos|publications|posts)$/i.test(e.innerText.trim()) ||
    ['videos-tab','user-post-tab'].includes(e.getAttribute('data-e2e'))) &&
    e.getAttribute('aria-selected') !== 'true') || null;
"""


def collecter_grille_profil(navigateur, arguments, rapport, *, interact, check=None, progress=None):
    """Suivre la grille et ses réponses de pagination dans une seule session Chrome."""
    import scraptiktok as moteur
    check = check or (lambda: None)
    compte = rapport["compte_attendu"]
    liens = {}
    rapport.update(technique="selenium_profil_pagination", pagination_profil=[],
                   observation_reseau={}, exhaustif=False)
    observation = ObservationProfil(navigateur, compte, rapport["observation_reseau"], arguments.timeout)

    def surveiller():
        check()
        nature = moteur.type_intervention_tiktok(navigateur)
        if nature == "captcha":
            if not arguments.interactive:
                rapport["discovery_stop"] = "blocked"
                moteur.diagnostiquer_page(navigateur, rapport, code="verification_tiktok")
                raise RuntimeError("TikTok demande un CAPTCHA avant de poursuivre le profil.")
            interact("TikTok demande un CAPTCHA sur ce profil. Terminez-le dans la fenêtre, puis cliquez sur Continuer.")
            check()
        moteur.fermer_invitation_connexion(navigateur)

    def scanner(_):
        surveiller()
        avant = len(liens)
        candidats = list(navigateur.execute_script(moteur.DISCOVER_JS) or [])
        candidats.extend(moteur.liens_donnees_publications(navigateur.execute_script(moteur.DONNEES_PUBLICATIONS_JS)))
        candidats.extend(observation.lire())
        for url in candidats:
            identite = moteur.canonical_post(url)
            if identite and identite[2].casefold() == compte.casefold() and len(liens) < arguments.limit:
                liens.setdefault(identite[0], identite[1])
        rapport["discovered_urls"] = list(liens.values())
        if progress:
            progress(len(liens))
        return len(liens) > avant

    check()
    observation.demarrer()
    try:
        moteur.open_page(navigateur, rapport["hashtag_url"])
        surveiller()
        # Activer uniquement l'onglet des publications, jamais les favoris/reposts.
        if moteur.type_intervention_tiktok(navigateur) != "connexion":
            onglet = navigateur.execute_script(ONGLET_PUBLICATIONS_JS)
            if onglet:
                try:
                    onglet.click()
                    rapport["onglet_publications_active"] = True
                except WebDriverException:
                    rapport["onglet_publications_active"] = False
        for tentative in range(2):
            try:
                WebDriverWait(navigateur, arguments.timeout).until(scanner)
                break
            except TimeoutException:
                diagnostic = moteur.diagnostiquer_page(navigateur, rapport)
                if moteur.type_intervention_tiktok(navigateur) == "connexion":
                    diagnostic["code"] = "connexion_sans_publications_publiques"
                if diagnostic["code"] == "erreur_tiktok" and tentative == 0:
                    rapport["rechargements"] = 1
                    check()
                    moteur.open_page(navigateur, rapport["hashtag_url"])
                    continue
                rapport["discovery_stop"] = "no_accessible_links"
                raise RuntimeError("Le profil ne fournit aucune publication publique lisible dans cette session.")

        inactif = 0
        for _ in range(arguments.max_scrolls):
            if len(liens) >= arguments.limit:
                rapport["discovery_stop"] = "limit"
                break
            surveiller()
            defilement = None
            if moteur.type_intervention_tiktok(navigateur) != "connexion":
                defilement = defiler_grille_profil(navigateur, compte, reprendre=inactif > 0, check=check)
                defilement["liens_avant"] = len(liens)
                rapport["pagination_profil"].append(defilement)
            time.sleep(arguments.delay)

            def attendre_suite(_):
                if scanner(navigateur):
                    return True
                if defilement:
                    etat = etat_grille_profil(navigateur, compte)
                    defilement["apres"] = {cle: etat[cle] for cle in defilement["apres"]}
                    return not etat["fin"] and etat["position"] > defilement["avant"]["position"] + 2
                return False

            try:
                WebDriverWait(navigateur, arguments.timeout).until(attendre_suite)
                inactif = 0
            except TimeoutException:
                inactif += 1
            finally:
                if defilement:
                    defilement["liens_apres"] = len(liens)
            if inactif >= arguments.idle_rounds:
                if moteur.type_intervention_tiktok(navigateur) == "connexion":
                    moteur.diagnostiquer_page(navigateur, rapport, code="connexion_apres_resultats")
                    rapport["diagnostic"]["code"] = "connexion_apres_resultats"
                    rapport["discovery_stop"] = "connexion_apres_resultats"
                else:
                    page = observation.derniere_page or {}
                    rapport["discovery_stop"] = ("fin_signalee_par_tiktok" if page.get("suite") is False else
                                                 "pagination_stagnante" if page.get("suite") is True else
                                                 "pagination_non_observee")
                break
        else:
            rapport["discovery_stop"] = "max_scrolls"
        if len(liens) >= arguments.limit:
            rapport["discovery_stop"] = "limit"
        elif rapport.get("discovery_stop") != "connexion_apres_resultats":
            rapport["diagnostic"] = {"code": rapport["discovery_stop"],
                "pages_reseau_lues": len(rapport["observation_reseau"]["pages"]),
                "suite_annoncee": (observation.derniere_page or {}).get("suite")}
        return list(liens.values())
    except WebDriverException as erreur:
        moteur.diagnostiquer_page(navigateur, rapport, erreur)
        if liens:
            rapport["discovery_stop"] = "erreur_apres_resultats"
            return list(liens.values())
        raise
    finally:
        observation.fermer()
