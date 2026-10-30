"""Parcours Selenium dédié aux publications publiques d'un profil TikTok."""
import time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.support.ui import WebDriverWait

from .pagination_profils import defiler_grille_profil, etat_grille_profil
from .reseau_profils import ObservationProfil


ONGLET_PUBLICATIONS_JS = """
// Chercher d'abord l'accès à la liste de TOUTES les vidéos, quand TikTok
// présente un aperçu du profil limité à quelques vignettes. Ne jamais
// construire une URL supposée : ne suivre que les éléments du DOM observé.
const compte = '@' + arguments[0].toLowerCase();
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
const libelles = e => [e.innerText, e.getAttribute('aria-label'), e.getAttribute('title')]
    .filter(Boolean).map(t => t.trim().replace(/\\s+/g, ' '));
const memeProfil = e => {
    if (e.tagName !== 'A' || !e.href) return true;
    try {
        const url = new URL(e.href, location.href);
        return (url.hostname === 'www.tiktok.com' || url.hostname === 'tiktok.com')
            && decodeURIComponent(url.pathname.split('/')[1] || '').toLowerCase() === compte;
    } catch (_) { return false; }
};
const candidats = Array.from(document.querySelectorAll(
    'a, button, [role="button"], [role="tab"], [data-e2e="user-post-tab"], [data-e2e="videos-tab"]'
)).filter(e => visible(e) && memeProfil(e));
const tout = /(?:voir|afficher|voir toutes?|see|view|show)\\s+(?:toutes?\\s+les\\s+|all\\s+)?(?:vidéos|videos|publications|posts)|(?:all\\s+(?:videos|posts)|toutes?\\s+les\\s+(?:vidéos|publications))/i;
const lienComplet = candidats.find(e => libelles(e).some(texte => tout.test(texte)) &&
    (e.tagName !== 'A' || new URL(e.href, location.href).href !== location.href));
if (lienComplet) return lienComplet;
const onglets = candidats.filter(e => (
    ['videos-tab','user-post-tab'].includes(e.getAttribute('data-e2e')) ||
    e.getAttribute('role') === 'tab'
));
return onglets.find(e =>
    (libelles(e).some(texte => /^(vidéos|videos|publications|posts)(?:\\s*\\(\\d+\\))?$/i.test(texte)) ||
    ['videos-tab','user-post-tab'].includes(e.getAttribute('data-e2e'))) &&
    e.getAttribute('aria-selected') !== 'true'
) || null;
"""

ETAT_ONGLET_VIDEOS_JS = """
// Cibler les publications du profil, pas les recommandations ni les onglets
// Favoris / Republis. L'onglet Vidéos peut déjà être sélectionné par défaut.
const visible = e => !!e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
const titre = e => [
    e.innerText || '', e.getAttribute('aria-label') || '',
    e.getAttribute('title') || ''
].map(v => v.trim()).filter(Boolean);
const onglets = Array.from(document.querySelectorAll(
    '[data-e2e="user-post-tab"],[data-e2e="videos-tab"],[role="tab"]'
)).filter(visible);
const onglet = onglets.find(e =>
    ['user-post-tab', 'videos-tab'].includes(e.getAttribute('data-e2e')) ||
    titre(e).some(t => /^(vidéos|videos|publications|posts)(?:\\s*\\(\\d+\\))?$/i.test(t))
);
const grille = Array.from(document.querySelectorAll(
    '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"]'
)).find(visible);
if (onglet) {
    const selection = onglet.getAttribute('aria-selected');
    if (selection === 'true') return {etat:'selectionne',element:null,grille:!!grille};
    if (selection !== 'false' && grille) return {etat:'selectionne',element:null,grille:true};
    return {etat:'a_ouvrir',element:onglet,grille:!!grille};
}
if (grille) return {etat:'grille_videos',element:null,grille:true};
return {etat:'indisponible',element:null,grille:false};
"""

LIENS_ONGLET_VIDEOS_JS = """
// En mode Presse, ne compter QUE les vidéos de la grille du média. Les
// recommandations, photos et résultats de recherche ne sont pas des sources.
const auteur = '@' + arguments[0].toLowerCase();
const conteneurs = document.querySelectorAll(
    '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"]'
);
const liens = [];
for (const conteneur of conteneurs) {
    for (const e of conteneur.querySelectorAll('a[href*="/video/"]')) {
        try {
            const url = new URL(e.href);
            if ((url.hostname === 'www.tiktok.com' || url.hostname === 'tiktok.com')
                && decodeURIComponent(url.pathname.split('/')[1]).toLowerCase() === auteur
                && /\\/video\\/\\d+\\/?$/.test(url.pathname)) liens.push(e.href);
        } catch (_) {}
    }
}
return Array.from(new Set(liens));
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


def collecter_grille_profil(navigateur, arguments, rapport, *, interact, check=None,
                          progress=None, cibler_onglet_videos=False):
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
    clic_videos_tente = False

    def afficher_page(motif, message):
        """Ouvrir automatiquement la fenêtre existante, sans nouvelle session."""
        rapport.setdefault("interventions_automatiques", []).append(motif)
        interact(message)
        check()

    def activer_publications():
        """Sélectionner explicitement la vue Vidéos en mode Presse.

        Retourne True juste après un clic : il faut attendre un nouveau rendu
        avant de scanner la grille, sinon on compte l'aperçu d'accueil.
        """
        nonlocal onglet_active, clic_videos_tente
        if onglet_active or moteur.type_intervention_tiktok(navigateur) == "connexion":
            return False
        if cibler_onglet_videos:
            situation = navigateur.execute_script(ETAT_ONGLET_VIDEOS_JS) or {}
            etat = situation.get("etat", "indisponible")
            if etat in ("selectionne", "grille_videos") and situation.get("grille"):
                onglet_active = True
                rapport["navigation_publications"] = (
                    "onglet_videos_selectionne" if etat == "selectionne"
                    else "grille_videos_sans_onglet_distinct"
                )
                rapport["onglet_publications_active"] = True
                return False
            # TikTok peut afficher des vidéos de l'auteur sans monter
            # user-post-item-list : accepter cette vue seulement sur le
            # véritable profil et avec des URL vidéo de cet auteur.
            if etat != "a_ouvrir" and not situation.get("grille"):
                from urllib.parse import urlsplit
                page_url = urlsplit(getattr(navigateur, "current_url", ""))
                meme_page = (page_url.hostname in {"www.tiktok.com", "tiktok.com"}
                             and page_url.path.rstrip("/").casefold() ==
                             ("/@" + compte).casefold())
                if meme_page:
                    visibles = navigateur.execute_script(LIENS_PROFIL_JS, compte) or []
                    from scraptiktok import canonical_post
                    valides = [url for url in visibles if
                               (identite := canonical_post(url))
                               and identite[2].casefold() == compte.casefold()
                               and "/video/" in identite[1]]
                    if valides:
                        onglet_active = True
                        rapport["navigation_publications"] = "profil_videos_sans_grille_e2e"
                        rapport["onglet_publications_active"] = True
                        return False
            if etat == "a_ouvrir":
                if clic_videos_tente:
                    # Le DOM n'a pas encore confirmé la nouvelle vue.
                    return False
                try:
                    situation["element"].click()
                    clic_videos_tente = True
                    rapport["navigation_publications"] = "ouverture_onglet_videos_en_cours"
                    return True
                except WebDriverException:
                    rapport["navigation_publications"] = "clic_onglet_videos_impossible"
            else:
                rapport["navigation_publications"] = "onglet_videos_indisponible"
            return False

        onglet = navigateur.execute_script(ONGLET_PUBLICATIONS_JS, compte)
        if onglet:
            try:
                onglet.click()
                onglet_active = True
                rapport["onglet_publications_active"] = True
                rapport["navigation_publications"] = "rubrique_selectionnee"
            except WebDriverException:
                rapport["onglet_publications_active"] = False
                rapport["navigation_publications"] = "clic_impossible"
        else:
            rapport.setdefault("navigation_publications", "pas_de_rubrique_distincte_detectee")
        return False

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
        transition = activer_publications()
        if transition or (cibler_onglet_videos and not onglet_active):
            # Aucun lien de l'aperçu n'est compté tant que l'onglet Vidéos
            # et sa grille n'ont pas été confirmés.
            return False
        avant = len(liens)
        if cibler_onglet_videos:
            candidats = list(navigateur.execute_script(LIENS_ONGLET_VIDEOS_JS, compte) or [])
            if onglet_active and rapport.get("navigation_publications") == "profil_videos_sans_grille_e2e":
                candidats.extend(
                    url for url in (navigateur.execute_script(LIENS_PROFIL_JS, compte) or [])
                    if "/video/" in url
                )
            # Uniquement les liens vidéo de l'auteur sur le profil chargé,
            # jamais les résultats d'une recherche générale.
            if onglet_active:
                candidats.extend(
                    url for url in observation.lire() if "/video/" in url
                )
            rapport["ciblage_videos"] = (
                "grille_du_profil" if onglet_active else "onglet_indisponible"
            )
        else:
            candidats = list(navigateur.execute_script(LIENS_PROFIL_JS, compte) or [])
            candidats.extend(moteur.liens_donnees_publications(navigateur.execute_script(moteur.DONNEES_PUBLICATIONS_JS)))
            candidats.extend(observation.lire())
        for url in candidats:
            identite = moteur.canonical_post(url)
            if (identite and identite[2].casefold() == compte.casefold()
                    and (not cibler_onglet_videos or "/video/" in identite[1])
                    and (not cibler_onglet_videos or onglet_active)
                    and len(liens) < arguments.limit):
                liens.setdefault(identite[0], identite[1])
        rapport["discovered_urls"] = list(liens.values())
        adresse = getattr(navigateur, "current_url", "")
        if isinstance(adresse, str) and adresse.startswith("https://www.tiktok.com/@"):
            rapport["url_rubrique_publications"] = adresse.split("?")[0]
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
                    clic_videos_tente = False
                    continue
                if diagnostic["code"] == "erreur_tiktok" and not recharge_effectuee:
                    recharge_effectuee = True
                    rapport["rechargements"] = 1
                    check()
                    moteur.open_page(navigateur, rapport["hashtag_url"])
                    onglet_active = False
                    clic_videos_tente = False
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
