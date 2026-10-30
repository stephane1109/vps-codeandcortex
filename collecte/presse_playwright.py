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


# On privilégie la grille du profil ; l'aperçu sans data-e2e garde un repli
# borné au profil et à l'auteur, pour ne pas perdre les vidéos visibles.
LIENS_VIDEOS_JS = """() => {
  const grilles = Array.from(document.querySelectorAll(
    '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"]'
  ));
  const racines = grilles.length ? grilles :
    Array.from(document.querySelectorAll('main,[data-e2e="user-post-list"],[data-e2e="user-post"]'));
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

    def ouvrir(self):
        from playwright.sync_api import sync_playwright

        self.check()
        try:
            self.playwright = sync_playwright().start()
            binary = os.getenv("CHROME_BINARY", "/usr/bin/chromium")
            options = {"headless": True, "args": ["--disable-dev-shm-usage", "--no-sandbox"]}
            if binary and os.path.isfile(binary):
                options["executable_path"] = binary
            self.browser = self.playwright.chromium.launch(**options)
            self.context = self.browser.new_context(
                locale="fr-FR", viewport={"width": 1280, "height": 900}
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
            self.page.goto(url, wait_until="domcontentloaded",
                           timeout=max(5000, int(self.args.timeout * 1000)))
            self.page.wait_for_timeout(750)
        except PlaywrightError as erreur:
            raise moteur.WebDriverException("Navigation TikTok inaccessible avec Playwright.") from erreur
        self.check()

    def decouvrir(self, compte, rapport, progress=None):
        compte = normaliser_compte(compte)
        url = f"https://www.tiktok.com/@{compte}"
        rapport.update(mode_decouverte="profil_playwright", technique="playwright_profil",
                       presse_moteur="playwright", hashtag_url=url,
                       compte_attendu=compte, exhaustif=False, pagination_profil=[],
                       discovered_urls=[], metadonnees_api={})
        self._visiter(url)
        if not _profil_correct(self.page.url, compte):
            rapport["diagnostic"] = {"code": "redirection_hors_profil"}
            rapport["discovery_stop"] = "redirection"
            raise RuntimeError("TikTok n'a pas affiché le profil public demandé.")
        # Même principe que Rezepte : laisser le temps à React d'attacher les actions.
        self.page.wait_for_timeout(1500)
        self.page.evaluate(SELECT_ONGLET_JS)
        self.page.wait_for_timeout(500)
        uniques = {}
        tours = max(1, int(self.args.max_scrolls))
        for tour in range(tours + 1):
            self.check()
            try:
                extraits = self.page.evaluate(LIENS_VIDEOS_JS)
            except Exception:
                extraits = []
            for adresse in _liens_compte(extraits, compte, self.args.limit):
                identite = moteur.canonical_post(adresse)
                uniques.setdefault(identite[0], adresse)
                if len(uniques) >= self.args.limit:
                    break
            rapport["discovered_urls"] = list(uniques.values())
            rapport["candidats_examines"] = len(uniques)
            if progress:
                progress(len(uniques))
            if len(uniques) >= self.args.limit:
                rapport["discovery_stop"] = "limit"
                break
            if tour == tours:
                rapport["discovery_stop"] = "max_scrolls"
                break
            avant = len(uniques)
            position = self.page.evaluate(SCROLL_JS)
            self.page.mouse.wheel(0, 1600)
            self.page.wait_for_timeout(max(300, int(float(self.args.delay) * 1000)))
            rapport["pagination_profil"].append(
                {"tour": tour + 1, "liens": avant, "defilement": position}
            )
            # L'observation suivante validera la progression, sans boucle infinie.
            if len(rapport["pagination_profil"]) > 2:
                nombres = [v["liens"] for v in rapport["pagination_profil"][-3:]]
                if nombres[0] == nombres[1] == nombres[2]:
                    rapport["discovery_stop"] = "pagination_stagnante"
                    break
        else:
            rapport["discovery_stop"] = "max_scrolls"

        rapport.update(retenues_par_compte={compte: len(uniques)},
                       collecte_partielle=len(uniques) < self.args.limit,
                       bilan_recherche=f"@{compte} : {len(uniques)}/{self.args.limit} vidéo(s) "
                                      "découverte(s) par Playwright (grille publique).")
        if not uniques:
            rapport["diagnostic"] = {
                "code": "profil_sans_liens_playwright",
                "detail": "Aucun lien vidéo public vérifié dans la grille du compte.",
            }
            raise RuntimeError("Aucune vidéo publique accessible par Playwright.")
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
