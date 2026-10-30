"""Découverte et lecture TikTok Presse par Playwright, indépendante de Selenium.

Un contexte anonyme par collecte. Aucune reconnexion ni changement automatique
de moteur. Les liens sont limités aux vidéos du compte explicitement choisi.
"""
from __future__ import annotations

import os
import re
import time
from urllib.parse import urlsplit

import scraptiktok as moteur
from collecte.verification_comptes import normaliser_compte
from collecte.navigation_videos import NAVIGUER_VIDEOS_JS, DIAGNOSTIC_VIDEOS_JS


# On privilégie la grille du profil ; l'aperçu sans data-e2e garde un repli
# borné au profil et à l'auteur, pour ne pas perdre les vidéos visibles.
LIENS_VIDEOS_JS = """() => {
  const grilles = Array.from(document.querySelectorAll(
    '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"]'
  ));
  // Les cartes vidéo peuvent être montées hors de <main> après le clic Vidéos.
  // Le filtrage strict par auteur est effectué côté Python.
  const racines = grilles.length ? grilles : [document];
  return Array.from(new Set(racines.flatMap(r =>
    Array.from(r.querySelectorAll('a[href*="/video/"]')).map(a => a.href)
  )));
}"""

SELECT_ONGLET_JS = """() => {
  const candidats = Array.from(document.querySelectorAll(
    '[data-e2e="user-post-tab"],[data-e2e="videos-tab"],[role="tab"]'
  ));
  for (const e of candidats) {
    const texte = (e.innerText || e.getAttribute('aria-label') || '').trim();
    if ((/^(vidéos|videos|publications|posts)(?:\s*\(\d+\))?$/i.test(texte)
        || ['user-post-tab', 'videos-tab'].includes(e.getAttribute('data-e2e')))
        && e.getAttribute('aria-selected') === 'false'
        && e.getClientRects().length) {
      e.click();
      return true;
    }
  }
  return false;
}"""

SCROLL_JS = """() => {
  const grilles = Array.from(document.querySelectorAll(
    '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"]'
  ));
  const grille = grilles.find(e => e.getClientRects().length);
  const cible = grille && Array.from(
    (function*(e) { while(e) { yield e; e=e.parentElement; } })(grille)
  ).find(e => e.scrollHeight > e.clientHeight + 100 && e.clientHeight > 0);
  if (cible) cible.scrollTop = cible.scrollHeight;
  window.scrollTo(0, document.documentElement.scrollHeight);
  return {bas: window.scrollY, hauteur: document.documentElement.scrollHeight};
}"""


def _script(page, script: str, *args):
    """Adapter les petits scripts Selenium (arguments[0]) à Playwright."""
    return page.evaluate(
        "(args) => { const run = function() {" + script + "}; return run(...args); }",
        list(args),
    )


def _liens_compte(adresses, compte, limite):
    """Ne prendre ni publications d'autres comptes, ni photos, ni URL inventées."""
    uniques = {}
    for adresse in adresses or []:
        identite = moteur.canonical_post(adresse)
        if identite and identite[2].casefold() == compte.casefold() and "/video/" in identite[1]:
            uniques.setdefault(identite[0], identite[1])
        if len(uniques) >= limite:
            break
    return list(uniques.values())


def _profil_correct(url, compte):
    morceaux = urlsplit(url)
    return (morceaux.scheme == "https"
            and morceaux.hostname in {"www.tiktok.com", "tiktok.com"}
            and morceaux.path.rstrip("/").casefold() == ("/@" + compte).casefold())


class PressePlaywright:
    """Un navigateur et une page par session, libérés à la fin de la collecte."""

    def __init__(self, args, check=None):
        self.args = args
        self.check = check or (lambda: None)
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.statut_http = None

    def ouvrir(self):
        from playwright.sync_api import sync_playwright

        self.check()
        try:
            self.playwright = sync_playwright().start()
            binary = str(getattr(self.args, "chrome_binary", None)
                         or os.getenv("CHROME_BINARY", "/usr/bin/chromium"))
            # Respecter le même réglage que Selenium ; Docker fournit déjà Xvfb.
            options = {"headless": bool(getattr(self.args, "headless", True)),
                       "args": ["--disable-dev-shm-usage", "--no-sandbox", "--mute-audio"]}
            if binary and os.path.isfile(binary):
                options["executable_path"] = binary
            self.browser = self.playwright.chromium.launch(**options)
            self.context = self.browser.new_context(
                locale="fr-FR", viewport={"width": 1440, "height": 1000}
            )
            self.page = self.context.new_page()
            self.page.set_default_timeout(max(5000, int(self.args.timeout * 1000)))
        except Exception:
            self.fermer()
            raise
        return self

    def _visiter(self, url):
        self.check()
        from playwright.sync_api import Error as PlaywrightError
        try:
            self.statut_http = None
            reponse = self.page.goto(url, wait_until="domcontentloaded",
                                     timeout=max(5000, int(self.args.timeout * 1000)))
            if reponse is not None:
                self.statut_http = reponse.status
            # DOMContentLoaded ne garantit pas que React ait affiché les vidéos.
            # La découverte attend ensuite une condition réelle, dans son budget.
        except PlaywrightError as erreur:
            raise moteur.WebDriverException("Navigation TikTok inaccessible avec Playwright.") from erreur
        self.check()

    def _surveiller_page(self, rapport):
        """Distinguer un refus, un CAPTCHA et une page encore incomplète."""
        nature = _script(self.page, moteur.TYPE_INTERVENTION_JS)
        if nature == "captcha":
            rapport.update(discovery_stop="blocked", diagnostic={"code": "verification_tiktok"})
            raise RuntimeError("TikTok demande une vérification dans la session Playwright.")
        if self.statut_http in (403, 429):
            rapport.update(discovery_stop="refus_http", diagnostic={
                "code": "refus_http_playwright", "statut_http": self.statut_http})
            raise RuntimeError(f"TikTok refuse la page du profil (HTTP {self.statut_http}).")
        # Fermer seulement une invitation facultative avec le bouton proposé.
        # Ne saisir aucun identifiant et ne supprimer aucune modale du DOM.
        if nature == "connexion":
            ferme = _script(self.page,
                "const bouton = (function() {" + moteur.FERMETURE_CONNEXION_JS +
                "})(); if (!bouton) return false; bouton.click(); return true;")
            if not ferme:
                rapport.update(discovery_stop="connexion", diagnostic={
                    "code": "connexion_sans_publications_publiques"})
                raise RuntimeError("TikTok affiche une connexion sans bouton de fermeture accessible.")
            return False
        page = _script(self.page, moteur.DIAGNOSTIC_JS)
        if isinstance(page, dict):
            rapport["etat_page"] = page
            if page.get("erreur_tiktok"):
                rapport.update(discovery_stop="erreur_tiktok", diagnostic={
                    **page, "code": "erreur_tiktok_playwright"})
                raise RuntimeError("TikTok affiche une erreur à la place du profil.")
        return True

    def decouvrir(self, compte, rapport, progress=None):
        compte = normaliser_compte(compte)
        url = f"https://www.tiktok.com/@{compte}"
        rapport.update(mode_decouverte="profil_playwright", technique="playwright_profil",
                       presse_moteur="playwright", hashtag_url=url,
                       compte_attendu=compte, exhaustif=False, pagination_profil=[],
                       discovered_urls=[], metadonnees_api={})
        uniques = {}
        navigation = {"statut": "introuvable"}
        clics = 0
        prochain_clic = 0.0
        delai = max(0.1, float(self.args.timeout))

        def publier():
            rapport.update(discovered_urls=list(uniques.values()),
                           candidats_examines=len(uniques),
                           retenues_par_compte={compte: len(uniques)})
            if progress:
                progress(len(uniques))

        def scanner():
            nonlocal navigation, clics, prochain_clic
            self.check()
            try:
                if not self._surveiller_page(rapport):
                    return False
                actuelle = urlsplit(self.page.url)
                chemin = actuelle.path.rstrip("/").casefold()
                attendu = ("/@" + compte).casefold()
                if (actuelle.hostname not in {"www.tiktok.com", "tiktok.com"}
                        or actuelle.scheme != "https"
                        or not (chemin == attendu or chemin.startswith(attendu + "/"))
                        or moteur.canonical_post(self.page.url)):
                    rapport.update(discovery_stop="redirection", diagnostic={
                        "code": "redirection_hors_profil"})
                    raise RuntimeError("TikTok n'affiche plus le profil demandé.")
                # Une rubrique absente au premier rendu doit être recherchée à nouveau.
                # Un clic trop précoce peut précéder l'attachement des actions React :
                # le retenter au plus trois fois, seulement tant qu'aucun lien n'est lu.
                maintenant = time.monotonic()
                if not uniques and clics < 3 and maintenant >= prochain_clic:
                    resultat = self.page.evaluate(NAVIGUER_VIDEOS_JS, compte)
                    if isinstance(resultat, dict):
                        navigation = resultat
                        rapport["navigation_videos"] = navigation
                        statut = navigation.get("statut")
                        rapport["navigation_publications"] = (
                            "ouverture_rubrique_videos" if statut == "clic" else
                            "videos_deja_actif" if statut == "deja_actif" else
                            "rubrique_videos_introuvable")
                        if statut == "clic":
                            clics += 1
                            prochain_clic = maintenant + 2.0
                            return False
                avant = len(uniques)
                extraits = self.page.evaluate(LIENS_VIDEOS_JS)
                for adresse in _liens_compte(extraits, compte, self.args.limit):
                    identite = moteur.canonical_post(adresse)
                    uniques.setdefault(identite[0], adresse)
                    if len(uniques) >= self.args.limit:
                        break
                rapport["url_rubrique_publications"] = self.page.url.split("?")[0]
                publier()
                return len(uniques) > avant
            except RuntimeError:
                raise
            except Exception as erreur:
                # Une navigation initiée par le clic détruit brièvement l'ancien DOM.
                # Toute autre erreur de script doit rester visible, jamais devenir []
                # et être présentée comme une absence de vidéos.
                if "Execution context was destroyed" in str(erreur):
                    return False
                rapport.update(discovery_stop="erreur_navigateur", diagnostic={
                    "code": "erreur_navigateur", "exception": type(erreur).__name__})
                raise moteur.WebDriverException("Lecture du profil Playwright impossible.") from erreur

        def attendre_nouveaux():
            """Attendre des liens, avec contrôle d'arrêt et dernière lecture à l'échéance."""
            echeance = time.monotonic() + delai
            while True:
                if scanner():
                    return True
                restant = echeance - time.monotonic()
                if restant <= 0:
                    return False
                # Cadence de vérification d'une condition, pas délai de chargement supposé.
                self.page.wait_for_timeout(min(250, restant * 1000))

        try:
            self._visiter(url)
            if not attendre_nouveaux():
                observation = self.page.evaluate(DIAGNOSTIC_VIDEOS_JS, compte)
                rapport["navigation_videos_observee"] = observation
                rapport.update(discovery_stop="delai_sans_publications", diagnostic={
                    "code": "profil_sans_liens_playwright",
                    "delai_secondes": delai,
                    "detail": "Aucun lien du compte après attente du contenu dynamique.",
                    **(rapport.get("etat_page") or {}),
                })
                raise RuntimeError("Le profil ne fournit aucun lien vidéo dans le délai imparti.")
            inactifs = 0
            for tour in range(max(0, int(self.args.max_scrolls))):
                if len(uniques) >= self.args.limit:
                    break
                self.check()
                avant = len(uniques)
                position = self.page.evaluate(SCROLL_JS)
                self.page.mouse.wheel(0, 1600)
                # Espacer les sollicitations de pagination ; la disponibilité des liens
                # est ensuite vérifiée même après le tout dernier défilement autorisé.
                repos = max(0.0, float(self.args.delay))
                while repos > 0:
                    self.check()
                    pause = min(0.25, repos)
                    self.page.wait_for_timeout(pause * 1000)
                    repos -= pause
                nouveaux = attendre_nouveaux()
                rapport["pagination_profil"].append({
                    "tour": tour + 1, "liens_avant": avant,
                    "liens_apres": len(uniques), "defilement": position})
                inactifs = 0 if nouveaux else inactifs + 1
                if inactifs >= max(1, int(getattr(self.args, "idle_rounds", 3))):
                    rapport["discovery_stop"] = "pagination_stagnante"
                    break
            else:
                rapport["discovery_stop"] = "max_scrolls"
            if len(uniques) >= self.args.limit:
                rapport["discovery_stop"] = "limit"
        except (RuntimeError, moteur.WebDriverException):
            publier()
            if not uniques:
                raise
            # Préserver les liens déjà obtenus si la suite devient inaccessible.
            rapport["collecte_interrompue"] = True
            rapport["recherches_en_echec"] = 1
        finally:
            rapport.update(retenues_par_compte={compte: len(uniques)},
                           collecte_partielle=len(uniques) < self.args.limit,
                           bilan_recherche=f"@{compte} : {len(uniques)}/{self.args.limit} vidéo(s) "
                                          "découverte(s) par Playwright (grille publique).")
            if rapport.get("collecte_interrompue"):
                rapport["bilan_recherche"] += " Collecte interrompue ; les liens obtenus sont conservés. Voir le diagnostic."
        return list(uniques.values())

    def lire(self, url):
        self._visiter(url)
        identite = moteur.canonical_post(url)
        if not identite:
            raise moteur.WebDriverException("URL vidéo invalide.")
        for _ in range(8):
            self.check()
            instantane = _script(self.page, moteur.PAGE_JS, identite[0], False)
            resultat = moteur.extract_record(instantane, url)
            if resultat and resultat.get("description"):
                break
            self.page.wait_for_timeout(500)
        else:
            raise moteur.WebDriverException("La légende TikTok est inaccessible dans Playwright.")
        if not getattr(self.args, "inclure_texte_genere_ia", False):
            resultat["statut_resume_ia"] = "desactive"
            return resultat

        meilleur = ""
        for tour in range(12):
            self.check()
            if tour in (4, 8):
                try:
                    _script(self.page, moteur.DEPLIER_LEGENDE_JS, identite[0])
                except Exception:
                    pass
            instantane = _script(self.page, moteur.PAGE_JS, identite[0], True)
            candidat = moteur.extraire_resume_ia_tiktok(instantane, resultat["description"])
            if len(candidat) > len(meilleur):
                meilleur = candidat
            if meilleur and tour >= 5:
                break
            self.page.wait_for_timeout(500)
        resultat["resume_ia_tiktok"] = meilleur
        resultat["statut_resume_ia"] = "recupere" if meilleur else "non_trouve"
        return resultat

    def fermer(self):
        for nom in ("context", "browser", "playwright"):
            objet = getattr(self, nom)
            setattr(self, nom, None)
            if objet:
                try:
                    objet.close() if nom != "playwright" else objet.stop()
                except Exception:
                    pass
        self.page = None
