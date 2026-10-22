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

LIENS_PROFIL_JS = """
// La grille peut être montée hors de <main> après le chargement initial.
const auteur = '@' + arguments[0].toLowerCase();
return Array.from(document.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]'))
    .filter(e => {
        try { return decodeURIComponent(new URL(e.href).pathname.split('/')[1]).toLowerCase() === auteur; }
        catch (_) { return false; }
    }).map(e => e.href);
"""


def collecter_grille_profil(navigateur, arguments, rapport, *, interact, check=None, progress=None):
    """Suivre la grille et ses réponses de pagination dans une seule session Chrome."""
    import scraptiktok as moteur
    check = check or (lambda: None)
    compte = rapport["compte_attendu"]
    liens = {}
    rapport.update(technique="selenium_profil_pagination", pagination_profil=[],
                   observation_reseau={}, exhaustif=False, defilements_effectues=0,
                   pagination_sans_progres=0)
    observation = ObservationProfil(navigateur, compte, rapport["observation_reseau"], arguments.timeout)
    onglet_active = False

    def afficher_page(motif, message):
        """Ouvrir automatiquement la fenêtre existante, sans nouvelle session."""
        rapport.setdefault("interventions_automatiques", []).append(motif)
        interact(message)
        check()

    def activer_publications():
        """Attendre que l'onglet existe avant de tenter de le sélectionner."""
        nonlocal onglet_active
        if onglet_active or moteur.type_intervention_tiktok(navigateur) == "connexion":
            return
        onglet = navigateur.execute_script(ONGLET_PUBLICATIONS_JS)
        if onglet:
            try:
                onglet.click()
                onglet_active = True
                rapport["onglet_publications_active"] = True
            except WebDriverException:
                rapport["onglet_publications_active"] = False

    def surveiller():
        check()
        nature = moteur.type_intervention_tiktok(navigateur)
        if nature == "captcha":
            if not arguments.interactive:
                rapport["discovery_stop"] = "blocked"
                moteur.diagnostiquer_page(navigateur, rapport, code="verification_tiktok")
                raise RuntimeError("TikTok demande un CAPTCHA avant de poursuivre le profil.")
            afficher_page("captcha", "TikTok demande un CAPTCHA sur ce profil. Terminez-le dans la fenêtre, puis cliquez sur Continuer.")
        moteur.fermer_invitation_connexion(navigateur)

    def scanner(_):
        surveiller()
        # Les données initiales peuvent déjà contenir des liens alors que
        # l'onglet et la grille ne sont pas encore montés dans la page.
        activer_publications()
        avant = len(liens)
        candidats = list(navigateur.execute_script(LIENS_PROFIL_JS, compte) or [])
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
        aide_vide = False
        recharge_effectuee = False
        while True:
            try:
                WebDriverWait(navigateur, arguments.timeout).until(scanner)
                # Le diagnostic final ne doit pas garder l'erreur d'une page
                # désormais lisible ; conserver les indices précédents à part.
                if "diagnostic" in rapport:
                    rapport["diagnostic_avant_reprise"] = rapport.pop("diagnostic")
                break
            except TimeoutException:
                diagnostic = moteur.diagnostiquer_page(navigateur, rapport)
                if moteur.type_intervention_tiktok(navigateur) == "connexion":
                    diagnostic["code"] = "connexion_sans_publications_publiques"
                # Une détection manquée ne doit pas terminer une source en silence.
                # Montrer la page avant toute recharge, pour préserver la vérification.
                if arguments.interactive and not aide_vide:
                    aide_vide = True
                    afficher_page("profil_sans_liens",
                        f"Aucune publication lisible de @{compte} pour le moment. La fenêtre TikTok s’ouvre automatiquement. "
                        "Terminez une éventuelle vérification ou fermez l’invitation à vous connecter si possible, "
                        "puis cliquez sur Continuer pour relire cette même page. Aucune connexion n’est imposée.")
                    onglet_active = False
                    continue
                if diagnostic["code"] == "erreur_tiktok" and not recharge_effectuee:
                    recharge_effectuee = True
                    rapport["rechargements"] = 1
                    check()
                    moteur.open_page(navigateur, rapport["hashtag_url"])
                    onglet_active = False
                    continue
                rapport["discovery_stop"] = "no_accessible_links"
                raise RuntimeError("Le profil ne fournit aucune publication publique lisible dans cette session.")

        inactif = 0
        aide_pagination = False
        for tour in range(arguments.max_scrolls):
            if len(liens) >= arguments.limit:
                rapport["discovery_stop"] = "limit"
                break
            surveiller()
            defilement = None
            if moteur.type_intervention_tiktok(navigateur) != "connexion":
                defilement = defiler_grille_profil(navigateur, compte, reprendre=inactif > 0, check=check)
                defilement["liens_avant"] = len(liens)
                rapport["pagination_profil"].append(defilement)
                rapport["defilements_effectues"] += 1
                if ("position" in defilement["avant"] and "position" in defilement["apres"]
                        and "liens_visibles" in defilement["avant"]
                        and "liens_visibles" in defilement["apres"]
                        and defilement["avant"]["position"] == defilement["apres"]["position"]
                        and defilement["avant"]["liens_visibles"] == defilement["apres"]["liens_visibles"]):
                    rapport["pagination_sans_progres"] += 1
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
                # Un CAPTCHA non reconnu peut masquer la suite alors que des liens
                # initiaux restent présents. L'utilisateur doit voir la page réelle.
                suite = (observation.derniere_page or {}).get("suite")
                connexion = moteur.type_intervention_tiktok(navigateur) == "connexion"
                if arguments.interactive and not aide_pagination and (connexion or suite is not False):
                    aide_pagination = True
                    afficher_page("pagination_bloquee",
                        f"Le chargement de @{compte} n’ajoute plus de publications après {len(liens)} lien(s). "
                        "La fenêtre TikTok s’ouvre automatiquement. Traitez une éventuelle vérification, "
                        "puis cliquez sur Continuer pour reprendre. Les liens obtenus restent conservés.")
                    scanner(navigateur)
                    inactif = 0
                    if len(liens) >= arguments.limit:
                        rapport["discovery_stop"] = "limit"
                        break
                    # Réessayer le défilement dans le budget restant, sans navigation.
                    if tour + 1 < arguments.max_scrolls:
                        continue
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
                "pages_reseau_lues": len(rapport["observation_reseau"].get("pages", [])),
                "suite_annoncee": (observation.derniere_page or {}).get("suite")}
        rapport["pagination_bilan"] = {
            "liens": len(liens),
            "objectif": arguments.limit,
            "defilements": rapport["defilements_effectues"],
            "sans_progres": rapport["pagination_sans_progres"],
            "pages_reseau": len(rapport["observation_reseau"].get("pages", [])),
            "reseau_disponible": observation.rapport.get("actif", False),
            "arret": rapport.get("discovery_stop", ""),
            "connexion_exigee": rapport.get("discovery_stop") == "connexion_apres_resultats",
        }
        return list(liens.values())
    except WebDriverException as erreur:
        moteur.diagnostiquer_page(navigateur, rapport, erreur)
        if liens:
            rapport["discovery_stop"] = "erreur_apres_resultats"
            return list(liens.values())
        raise
    finally:
        observation.fermer()
