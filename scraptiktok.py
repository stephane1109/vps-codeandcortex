#!/usr/bin/env python3
"""Collecte des légendes TikTok publiques par hashtag avec Chrome/Selenium."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, parse_qs

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, InvalidSessionIdException, NoSuchWindowException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

LOG = logging.getLogger("scraptiktok")
BASE_DIR = Path(__file__).resolve().parent
POST_PATH = re.compile(r"^/@([^/]+)/(video|photo)/(\d+)/?$")
FIELDS = ("id", "url", "author", "description", "hashtags", "created_at",
          "collected_at", "source", "status", "error")

# Sélecteurs regroupés ici pour faciliter les adaptations de l'interface TikTok.
DISCOVER_JS = """
const root = document.querySelector('main') || document;
return Array.from(root.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]'))
    .map(a => a.href);
"""
DONNEES_PUBLICATIONS_JS = """
return ['__UNIVERSAL_DATA_FOR_REHYDRATION__', 'SIGI_STATE']
    .map(id => document.getElementById(id)?.textContent).filter(Boolean);
"""
DEFILER_PUBLICATIONS_JS = """
// Le mode recherche fournit le conteneur détecté et un pas progressif.
// Sans paramètres, conserver le parcours hashtag existant.
if (arguments[0] === 'progressif') {
    arguments[1].scrollBy(0, arguments[2]);
    return;
}
// TikTok peut placer sa grille dans un conteneur défilant, hors du défilement de window.
const root = document.querySelector('main') || document;
const liens = Array.from(root.querySelectorAll('a[href*="/video/"],a[href*="/photo/"]'));
let cible = liens.filter(e => e.getClientRects().length).pop();
while (cible && cible !== document.body && cible !== document.documentElement) {
    const style = getComputedStyle(cible);
    if (/auto|scroll/.test(style.overflowY) && cible.scrollHeight > cible.clientHeight + 10) {
        cible.scrollTo(0, cible.scrollHeight);
        return;
    }
    cible = cible.parentElement;
}
window.scrollTo(0, document.documentElement.scrollHeight);
"""
PAGE_JS = """
const selectors = ['[data-e2e="browse-video-desc"]', '[data-e2e="video-desc"]'];
const text = selectors.flatMap(s => Array.from(document.querySelectorAll(s)))
    .find(e => e.getClientRects().length && e.innerText.trim());
return {
    payloads: ['__UNIVERSAL_DATA_FOR_REHYDRATION__', 'SIGI_STATE']
        .map(id => document.getElementById(id)?.textContent).filter(Boolean),
    description: text ? text.innerText : '',
    canonical: document.querySelector('link[rel="canonical"]')?.href || '',
    url: location.href,
    engagement: Object.fromEntries(Object.entries({likes:'like-count',partages:'share-count',commentaires:'comment-count',favoris:'collect-count',vues:'video-views'}).map(([nom,selecteur])=>[nom,Array.from(document.querySelectorAll('[data-e2e="'+selecteur+'"]')).find(e=>e.getClientRects().length)?.innerText || null]))
};
"""
# Une seule règle distingue la vérification visuelle de l'invitation à se connecter.
# Elle examine uniquement les éléments affichés, jamais la valeur des champs.
DETECTION_INTERVENTION_JS = r"""
const visible = e => {
    if (!Array.from(e.getClientRects()).some(r => r.width > 0 && r.height > 0)) return false;
    for (let p = e; p; p = p.parentElement) {
        const s = getComputedStyle(p);
        if (s.display === 'none' || s.visibility === 'hidden' || s.visibility === 'collapse' || Number(s.opacity) === 0) return false;
    }
    return true;
};
const elements = selecteur => Array.from(document.querySelectorAll(selecteur)).filter(visible);
const captcha = elements(
    'iframe[src*="captcha" i], iframe[src*="/verify" i], iframe[title*="captcha" i], ' +
    '[id*="captcha" i], [class*="captcha" i], [data-e2e*="captcha" i]'
).length > 0;
// Certains puzzles n'exposent qu'une consigne dans une fenêtre de vérification.
const puzzle = /drag the slider|drag the puzzle|slide to verify|faites glisser.{0,60}(?:puzzle|pi[eè]ce|curseur)|glissez.{0,40}(?:puzzle|pi[eè]ce)/i;
const fenetres = elements('[role="dialog"], [aria-modal="true"], [data-e2e="login-modal"]');
if ((window !== window.top || /\/(?:captcha|verify|verification)(?:\/|$)/i.test(location.pathname)) && document.body) fenetres.push(document.body);
const consignePuzzle = fenetres.some(e => visible(e) && puzzle.test(e.innerText || ''));
const connexion = location.pathname === '/login' || location.pathname.startsWith('/login/') ||
    elements('[data-e2e="login-modal"], input[type="password"], iframe[src*="/login"]').length > 0;
const nature = captcha || consignePuzzle ? 'captcha' : connexion ? 'connexion' : '';
"""
TYPE_INTERVENTION_JS = DETECTION_INTERVENTION_JS + "return nature;"
# Constantes conservées pour les outils existants ; le moteur utilise le détecteur
# Python commun afin de prendre aussi en compte les cadres d'un autre domaine.
CAPTCHA_JS = DETECTION_INTERVENTION_JS + "return nature === 'captcha';"
BLOCKED_JS = DETECTION_INTERVENTION_JS + "return nature !== '';"
CADRES_VISIBLES_JS = DETECTION_INTERVENTION_JS + "return elements('iframe, frame');"
FERMETURE_CONNEXION_JS = """
// Utiliser seulement le bouton de fermeture proposé par TikTok, sans retirer la modale.
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
const fenetre = Array.from(document.querySelectorAll('[data-e2e="login-modal"]')).find(visible);
if (!fenetre) return null;
return Array.from(fenetre.querySelectorAll(
    '[data-e2e="tiktok-modal-close"], [data-e2e="login-modal-close"], ' +
    'button[aria-label="Close"], button[aria-label="Fermer"], [role="button"][aria-label="Close"]'
)).find(visible) || null;
"""


def est_erreur_session(erreur):
    """Identifier une session Selenium perdue sans conserver son message brut."""
    return isinstance(erreur, (InvalidSessionIdException, NoSuchWindowException))


def fermer_invitation_connexion(navigateur):
    """Fermer une invitation facultative avec son bouton, sans saisir d'identifiants."""
    try:
        # Une détection indéterminée ne justifie pas de fermer la fenêtre.
        if type_intervention_tiktok(navigateur) != "connexion":
            return
        bouton = navigateur.execute_script(FERMETURE_CONNEXION_JS)
        if bouton:
            bouton.click()
    except WebDriverException:
        # Une invitation sans bouton utilisable ne doit pas imposer une connexion.
        pass


def type_intervention_tiktok(navigateur):
    """Donner la priorité au CAPTCHA, y compris dans les cadres intégrés visibles."""
    cadres_restants = 12
    cadre_visite = False

    def examiner(profondeur=0):
        nonlocal cadres_restants, cadre_visite
        resultat = navigateur.execute_script(TYPE_INTERVENTION_JS)
        nature = resultat if isinstance(resultat, str) and resultat in {"captcha", "connexion"} else ""
        if nature == "captcha" or profondeur >= 3 or cadres_restants <= 0:
            return nature
        cadres = navigateur.execute_script(CADRES_VISIBLES_JS)
        if not isinstance(cadres, list):
            return nature
        for cadre in cadres:
            if cadres_restants <= 0:
                break
            cadres_restants -= 1
            try:
                navigateur.switch_to.frame(cadre)
            except (InvalidSessionIdException, NoSuchWindowException):
                raise
            except WebDriverException:
                # Un cadre supprimé ou pas encore chargé sera réexaminé au prochain passage.
                continue
            cadre_visite = True
            try:
                enfant = examiner(profondeur + 1)
            finally:
                navigateur.switch_to.parent_frame()
            if enfant == "captcha":
                return "captcha"
            if enfant == "connexion":
                nature = "connexion"
        return nature

    try:
        return examiner()
    except (InvalidSessionIdException, NoSuchWindowException):
        raise
    except WebDriverException:
        return ""
    finally:
        if cadre_visite:
            # La capture et les gestes manuels utilisent toujours la fenêtre complète.
            navigateur.switch_to.default_content()


def captcha_present(navigateur):
    """Partager la même détection pour la collecte, la fermeture et le bouton Continuer."""
    return type_intervention_tiktok(navigateur) == "captcha"


DIAGNOSTIC_JS = """
const liens = document.querySelectorAll('a[href*="/video/"],a[href*="/photo/"]').length;
const texte = (document.body?.innerText || '').toLowerCase().replaceAll('’', "'");
const erreur = liens === 0 && (
    texte.includes('something went wrong') ||
    (texte.includes('une erreur') && (texte.includes('réessaie plus tard') || texte.includes('réessayer plus tard'))) ||
    (texte.includes('problème est survenu avec le serveur') && texte.includes('réessayer'))
);
return {url:location.origin+location.pathname, etat:document.readyState,
    titre:document.title.slice(0,160), liens, erreur_tiktok:erreur};
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_hashtag(value: str) -> str:
    value = unicodedata.normalize("NFC", value.strip().removeprefix("#"))
    if not value or not re.fullmatch(r"\w+", value, flags=re.UNICODE):
        raise argparse.ArgumentTypeError(
            "Indiquez un seul hashtag, sans espace ni URL (ex. : #cuisine)."
        )
    return value


def canonical_post(value: str) -> tuple[str, str, str] | None:
    """Valide le domaine et retire les paramètres de suivi ; dédoublonnage par ID."""
    parts = urlsplit(value)
    if parts.scheme != "https" or parts.hostname not in {"www.tiktok.com", "tiktok.com"}:
        return None
    match = POST_PATH.fullmatch(parts.path)
    if not match:
        return None
    author, kind, post_id = match.groups()
    return post_id, f"https://www.tiktok.com/@{author}/{kind}/{post_id}", unquote(author)


def find_item(payload: object, post_id: str) -> dict | None:
    """Ne prend jamais la légende d'une recommandation présente dans le même JSON."""
    stack = [payload]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if str(item.get("id", "")) == post_id and isinstance(item.get("desc"), str):
                return item
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return None


def liens_donnees_publications(contenus) -> list[str]:
    """Lire les publications identifiées dans les données publiques de la page."""
    if not isinstance(contenus, list):
        return []
    liens = {}
    for contenu in contenus:
        try:
            pile = [json.loads(contenu)]
        except (ValueError, TypeError):
            continue
        while pile:
            element = pile.pop()
            if isinstance(element, dict):
                identifiant = str(element.get("id", ""))
                auteur = element.get("author")
                auteur = auteur.get("uniqueId") if isinstance(auteur, dict) else auteur
                if (identifiant.isdecimal() and isinstance(auteur, str)
                        and re.fullmatch(r"[\w.]+", auteur, flags=re.ASCII)
                        and isinstance(element.get("desc"), str)
                        and (element.get("video") or element.get("imagePost"))):
                    type_post = "photo" if element.get("imagePost") else "video"
                    liens[identifiant] = f"https://www.tiktok.com/@{auteur}/{type_post}/{identifiant}"
                pile.extend(element.values())
            elif isinstance(element, list):
                pile.extend(element)
    return list(liens.values())


def timestamp_iso(value: object) -> str:
    try:
        return datetime.fromtimestamp(int(value), timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def extract_record(snapshot: dict, url: str) -> dict | None:
    identity = canonical_post(url)
    if identity is None:
        raise ValueError(f"URL de publication invalide : {url}")
    post_id, url, author = identity
    current = canonical_post(snapshot.get("url", ""))
    canonical = canonical_post(snapshot.get("canonical", ""))
    # Après une redirection, l'auteur du lien demandé peut être trompeur.
    # Une URL observée n'est utilisable que pour le même identifiant de publication.
    page = next((cible for cible in (canonical, current) if cible and cible[0] == post_id), None)
    author = page[2] if page else author
    record = dict.fromkeys(FIELDS, "")
    record.update(id=post_id, url=url, author=author, collected_at=utc_now())
    for raw in snapshot.get("payloads", []):
        try:
            item = find_item(json.loads(raw), post_id)
        except (json.JSONDecodeError, TypeError):
            continue
        if item is not None:
            record.update(description=item["desc"], source="page_json",
                          created_at=timestamp_iso(item.get("createTime")))
            auteur = item.get("author")
            if isinstance(auteur, dict):
                auteur = auteur.get("uniqueId")
            if isinstance(auteur, str) and auteur.strip():
                record["author"] = auteur.strip().removeprefix("@")
            # Une légende vide est un résultat valide quand l'ID est confirmé.
            break
    else:
        # Vérifier l'identité de la page avant le repli sur son texte affiché.
        if not current or current[0] != post_id or (canonical and canonical[0] != post_id):
            return None
        if not snapshot.get("description", "").strip():
            return None
        record.update(description=snapshot["description"].strip(), source="page_dom")
    record["hashtags"] = list(dict.fromkeys(re.findall(r"#(\w+)", record["description"])))
    record["status"] = "ok" if record["description"] else "empty_caption"
    from collecte.publications import enrichir_publication
    return enrichir_publication(record, snapshot)


def csv_safe(value: object) -> str:
    """Conserve le texte brut dans JSON/TXT ; neutralise les formules dans le CSV."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def save_results(prefix: Path, records: list[dict], report: dict) -> None:
    """Remplacement atomique de chaque export, y compris après Ctrl+C."""
    payload = {**report, "updated_at": utc_now(), "processed": len(records),
               "captions": sum(bool(r["description"]) for r in records), "posts": records}
    target = prefix.with_suffix(".json")
    temp = target.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)
    target = prefix.with_suffix(".csv")
    temp = target.with_suffix(".csv.tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        colonnes = (*FIELDS, "id_")
        writer = csv.DictWriter(stream, fieldnames=colonnes, delimiter=";")
        writer.writeheader()
        for record in records:
            row = dict(record, id_=str(record["id"]), hashtags=" ".join("#" + tag for tag in record["hashtags"]))
            writer.writerow({key: csv_safe(row.get(key, "")) for key in colonnes})
    temp.replace(target)
    target = prefix.with_suffix(".txt")
    temp = target.with_suffix(".txt.tmp")
    temp.write_text("\n\n".join(
        f"*id_{record['id']}\n{record['description']}" for record in records if record["description"]
    ) + "\n", encoding="utf-8")
    temp.replace(target)


def create_driver(args: argparse.Namespace) -> webdriver.Chrome:
    if not args.driver:
        # Un ancien ChromeDriver dans PATH ne doit pas empêcher Manager de choisir
        # la version correspondant au Chrome installé. --driver reste prioritaire.
        os.environ.setdefault("SE_SKIP_DRIVER_IN_PATH", "true")
    os.environ.setdefault("SE_CACHE_PATH", str(BASE_DIR / ".selenium-cache"))
    options = webdriver.ChromeOptions()
    # Attendre le document, puis les publications explicitement ; pas toutes les vidéos.
    options.page_load_strategy = "eager"
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--lang=fr-FR")
    options.add_argument("--mute-audio")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--disable-dev-shm-usage")
    if os.getenv("CHROME_NO_SANDBOX") == "1":
        options.add_argument("--no-sandbox")
    if args.headless:
        options.add_argument("--headless=new")
    if args.chrome_binary:
        options.binary_location = str(args.chrome_binary.expanduser().resolve())
    service = Service(executable_path=str(args.driver.expanduser().resolve())) if args.driver else Service()
    driver = webdriver.Chrome(options=options, service=service)
    try:
        driver.set_page_load_timeout(args.timeout)
    except WebDriverException:
        try:
            driver.quit()
        except WebDriverException:
            pass
        raise
    return driver


def manual_step(message: str) -> None:
    print(f"\n{message}\nIntervenez dans Chrome, puis appuyez sur Entrée ici (Ctrl+C pour arrêter).")
    try:
        input()
    except EOFError as exc:
        raise RuntimeError("Le mode interactif nécessite un terminal ouvert.") from exc


def meme_page_tiktok(observee: str, attendue: str) -> bool:
    """Comparer la page cible sans accepter une ancienne page ou un autre domaine."""
    if not isinstance(observee, str): return False
    observee, attendue = urlsplit(observee), urlsplit(attendue)
    return (observee.scheme == attendue.scheme == "https"
            and observee.hostname in {"www.tiktok.com", "tiktok.com"}
            and attendue.hostname in {"www.tiktok.com", "tiktok.com"}
            and observee.path.rstrip("/") == attendue.path.rstrip("/")
            and (attendue.path.rstrip("/") not in {"/search", "/search/video"}
                 or parse_qs(observee.query).get("q") == parse_qs(attendue.query).get("q")))


def diagnostiquer_page(driver, report, erreur=None, code=None):
    """Conserver des indices bornés, sans cookies, capture ni contenu privé de la page."""
    diagnostic = {"code": code or "page_sans_liens"}
    if erreur is not None:
        diagnostic["exception"] = type(erreur).__name__
        reseau = re.search(r"net::ERR_[A-Z_]+", str(erreur))
        if reseau: diagnostic.update(code="erreur_reseau", erreur_reseau=reseau.group())
        elif isinstance(erreur, TimeoutException): diagnostic["code"] = "delai_navigation"
        elif isinstance(erreur, WebDriverException): diagnostic["code"] = "erreur_navigateur"
    try:
        page = driver.execute_script(DIAGNOSTIC_JS)
        if isinstance(page, dict): diagnostic.update(page)
        if diagnostic.get("erreur_tiktok") is True: diagnostic["code"] = "erreur_tiktok"
        # Une vraie vérification reste prioritaire : ne jamais la recharger automatiquement.
        nature = type_intervention_tiktok(driver)
        if nature == "captcha": diagnostic["code"] = "verification_tiktok"
        elif nature == "connexion" and diagnostic["code"] == "page_sans_liens":
            diagnostic["code"] = "invitation_connexion"
    except WebDriverException: pass
    report["diagnostic"] = diagnostic
    return diagnostic


def open_page(driver: webdriver.Chrome, url: str) -> None:
    try:
        driver.get(url)
    except TimeoutException:
        # Une ressource lente ne doit pas masquer un CAPTCHA déjà affiché sur la cible.
        try:
            page = driver.execute_script("""return {url:location.href, etat:document.readyState,
                contenu:!!document.body && document.body.innerText.trim().length>0};""")
            if (isinstance(page, dict) and meme_page_tiktok(page.get("url"), url)
                    and page.get("etat") in {"interactive", "complete"} and page.get("contenu") is True):
                return
        except WebDriverException: pass
        # Ne jamais lire les publications de la page précédente après une navigation ratée.
        driver.execute_script("window.stop();")
        raise


def collect_links(driver: webdriver.Chrome, args: argparse.Namespace, report: dict,
                  *, interact=manual_step, progress=None, check=None, validation_initiale=True, intervention_si_vide=True,
                  sans_connexion=True, comptes_attendus=(), liens_precedents=()) -> list[str]:
    # Argument historique conservé pour les appels existants ; seule la collecte anonyme existe.
    if report.get("compte_attendu") and not comptes_attendus:
        from collecte.recherche_comptes import collecter_recherche_compte
        return collecter_recherche_compte(driver, args, report, interact=interact,
                                         progress=progress, check=check)
    check = check or (lambda: None)
    comptes = {compte.casefold() for compte in comptes_attendus}
    retenues = {compte: set() for compte in comptes}
    deja_vus = set()
    for url in liens_precedents:
        identite = canonical_post(url)
        if identite and identite[2].casefold() in comptes:
            retenues[identite[2].casefold()].add(identite[0])
            deja_vus.add(identite[0])
    links: dict[str, str] = {}

    def objectif_atteint():
        return (all(len(ids) >= args.limit for ids in retenues.values())
                if comptes else len(links) >= args.limit)

    def publier_bilan_comptes():
        if not comptes:
            return
        report.update(retenues_par_compte={compte: len(ids) for compte, ids in sorted(retenues.items())},
                      objectif_par_compte=args.limit, objectif_atteint=objectif_atteint(),
                      collecte_partielle=not objectif_atteint(), exhaustif=False)
        origine = ("les recherches compte + hashtag" if report.get("mode_decouverte") == "recherche_compte_hashtag"
                   else "les pages de hashtags")
        report["bilan_recherche"] = (
            f"Limite demandée atteinte pour les comptes sélectionnés dans {origine} ; historique complet non garanti."
            if objectif_atteint() else
            f"Collecte partielle : {origine} ne fournissent pas la limite demandée pour chaque compte. Aucun accès exhaustif n’est garanti.")

    check()
    if comptes and objectif_atteint():
        report.update(discovered_urls=[], candidats_ids=[], candidats_examines=0, discovery_stop="limit")
        publier_bilan_comptes()
        return []
    try:
        open_page(driver, report["hashtag_url"])
    except WebDriverException as erreur:
        diagnostic = diagnostiquer_page(driver, report, erreur)
        if type_intervention_tiktok(driver) == "connexion":
            diagnostic["code"] = "connexion_sans_publications_publiques"
        raise
    fermer_invitation_connexion(driver)
    if report.get("mode_decouverte") == "profil_direct":
        diagnostic = diagnostiquer_page(driver, report)
        if diagnostic["code"] == "erreur_tiktok":
            report["discovery_stop"] = "tiktok_error"
            raise RuntimeError(
                "TikTok ne charge pas le profil public."
            )
    if (comptes and report.get("mode_decouverte") == "recherche_compte_hashtag"
            and type_intervention_tiktok(driver) == "connexion"):
        # La recherche peut exiger une connexion alors que le hashtag reste public.
        # Conserver le filtre d'auteur ; ne jamais inviter à saisir des identifiants.
        from collecte.comptes import collecter_comptes_par_hashtag
        requete = report.get("hashtag_url")
        hashtag = report["hashtag_recherche"]
        report["repli_public"] = {"motif": "connexion_recherche", "recherche": requete}
        return collecter_comptes_par_hashtag(driver, args, sorted(comptes), hashtag, report,
            liens_precedents=liens_precedents, interact=interact, progress=progress,
            check=check, validation_initiale=validation_initiale,
            intervention_si_vide=intervention_si_vide)
    if args.interactive and validation_initiale:
        interact("Vérifiez les publications publiques. Traitez les cookies ou un éventuel CAPTCHA, puis cliquez sur Continuer.")
    candidats_vus: set[str] = set()
    auteurs_ecartes_ids: set[str] = set()
    publications_par_auteur: dict[str, set[str]] = {}
    report["defilements_effectues"] = 0
    intervention_effectuee = bool(args.interactive and validation_initiale)

    def scan(browser: webdriver.Chrome) -> bool:
        nonlocal intervention_effectuee
        check()
        # Une autre source réutilise la session ; seules les vérifications visibles
        # de TikTok interrompent alors la collecte, même si des liens restent derrière.
        fermer_invitation_connexion(browser)
        if args.interactive and captcha_present(browser):
            interact("TikTok affiche un CAPTCHA. Terminez cette vérification pour poursuivre.")
            intervention_effectuee = True
            check()
        precedents = len(candidats_vus)
        if (report.get("mode_decouverte") == "recherche_compte_hashtag"
                and not meme_page_tiktok(browser.current_url, report["hashtag_url"])):
            report["redirection_recherche"] = True
            return False
        candidats = list(browser.execute_script(DISCOVER_JS))
        for href in candidats:
            identity = canonical_post(href)
            if identity:
                candidats_vus.add(identity[0])
                publications_par_auteur.setdefault(identity[2].casefold(), set()).add(identity[0])
            if not identity:
                continue
            if comptes:
                auteur = identity[2].casefold()
                if auteur not in comptes:
                    auteurs_ecartes_ids.add(identity[0])
                    continue
                if identity[0] in deja_vus or len(retenues[auteur]) >= args.limit:
                    continue
                retenues[auteur].add(identity[0])
                links.setdefault(identity[0], identity[1])
            elif len(links) < args.limit:
                links.setdefault(identity[0], identity[1])
        report["candidats_examines"] = len(candidats_vus)
        report["candidats_ids"] = sorted(candidats_vus)
        # Compter les auteurs des liens avant tout rejet ; la lecture vérifiera l'auteur réel.
        report["auteurs_dans_liens"] = {auteur: len(ids) for auteur, ids in sorted(publications_par_auteur.items())}
        report["discovered_urls"] = list(links.values())
        if comptes:
            report.update(auteurs_ecartes_ids=sorted(auteurs_ecartes_ids),
                          auteurs_ecartes=len(auteurs_ecartes_ids))
        publier_bilan_comptes()
        if progress:
            progress(len(links))
        # Continuer à défiler même si la première page contient d’autres auteurs.
        return len(candidats_vus) > precedents

    # Une erreur affichée par TikTok exige une nouvelle navigation, pas une
    # deuxième attente sur la même page. Une seule recharge par source est autorisée.
    recharge_effectuee = False
    for tentative in range(3):
        try:
            WebDriverWait(driver, args.timeout).until(scan)
            break
        except TimeoutException as exc:
            diagnostic = diagnostiquer_page(driver, report)
            if type_intervention_tiktok(driver) == "connexion":
                diagnostic["code"] = "connexion_sans_publications_publiques"
                report["discovery_stop"] = "publications_non_accessibles"
                raise RuntimeError("TikTok affiche une connexion et ne fournit aucun lien public lisible sur cette page. Aucune connexion n’a été imposée par la collecte.") from exc
            bloque = diagnostic["code"] == "verification_tiktok"
            if (report.get("mode_decouverte") == "recherche_compte_hashtag"
                    and report.get("redirection_recherche")
                    and not meme_page_tiktok(driver.current_url, report["hashtag_url"])
                    and diagnostic["code"] not in {"verification_tiktok", "erreur_tiktok"}):
                diagnostic["code"] = "recherche_redirigee"
                report["discovery_stop"] = "recherche_redirigee"
                raise RuntimeError("TikTok a redirigé la recherche ciblée vers une autre page ; ses publications ne sont pas retenues.") from exc
            if diagnostic["code"] == "erreur_tiktok":
                if not recharge_effectuee and tentative < 2:
                    check()
                    recharge_effectuee = True
                    report["rechargements"] = 1
                    report["diagnostic_avant_rechargement"] = report.pop("diagnostic")
                    try:
                        open_page(driver, report["hashtag_url"])
                    except WebDriverException as erreur:
                        diagnostic = diagnostiquer_page(driver, report, erreur)
                        if type_intervention_tiktok(driver) == "connexion":
                            diagnostic["code"] = "connexion_sans_publications_publiques"
                        raise
                    continue
                report["discovery_stop"] = "tiktok_error"
                raise RuntimeError("TikTok affiche une erreur de chargement des publications, même après rechargement.") from exc
            if args.interactive and intervention_si_vide and not intervention_effectuee and tentative < 2:
                interact("Aucune publication n’a pu être lue dans cette recherche. Examinez la page TikTok ci-dessous, "
                         "terminez une éventuelle vérification, puis cliquez sur Continuer pour réessayer.")
                intervention_effectuee = True
                check()
                continue
            report["discovery_stop"] = "blocked" if bloque else "no_accessible_links"
            if bloque:
                raise RuntimeError("TikTok bloque l’accès public. Seul un éventuel CAPTCHA peut être traité dans la fenêtre intégrée.") from exc
            raise RuntimeError("La page TikTok ne fournit aucun lien de publication lisible après vérification.") from exc
    idle = 0
    for _ in range(args.max_scrolls):
        check()
        if objectif_atteint():
            report["discovery_stop"] = "limit"
            break
        fermer_invitation_connexion(driver)
        if captcha_present(driver):
            if args.interactive:
                interact("TikTok affiche un CAPTCHA. Terminez cette vérification pour poursuivre.")
            else:
                report["discovery_stop"] = "blocked"
                break
        driver.execute_script(DEFILER_PUBLICATIONS_JS)
        report["defilements_effectues"] += 1
        time.sleep(args.delay)

        try:
            WebDriverWait(driver, args.timeout).until(scan)
            idle = 0
        except TimeoutException:
            idle += 1
            if (report.get("mode_decouverte") == "recherche_compte_hashtag"
                    and not meme_page_tiktok(driver.current_url, report["hashtag_url"])):
                diagnostic = diagnostiquer_page(driver, report, code="recherche_redirigee")
                if diagnostic["code"] == "recherche_redirigee":
                    report.update(discovery_stop="recherche_redirigee", recherches_en_echec=1)
                    break
            if (idle >= args.idle_rounds
                    and type_intervention_tiktok(driver) == "connexion"):
                # La fenêtre empêche éventuellement le chargement suivant. Garder
                # les liens déjà lus, sans exiger une authentification ni les perdre.
                diagnostiquer_page(driver, report)
                report["diagnostic"]["code"] = "connexion_apres_resultats"
                report["discovery_stop"] = "connexion_apres_resultats"
                break
        LOG.info("%d publication(s) repérée(s)", len(links))
        if idle >= args.idle_rounds:
            report["discovery_stop"] = "no_new_links"
            break
    else:
        report["discovery_stop"] = "max_scrolls"
    if objectif_atteint():
        report["discovery_stop"] = "limit"
    publier_bilan_comptes()
    return list(links.values())


def read_post(driver: webdriver.Chrome, url: str, args: argparse.Namespace,
              *, interact=manual_step, check=None, sans_connexion=True) -> dict:
    """Lire une publication publique ; ne jamais demander une identification."""
    check = check or (lambda: None)
    check()
    open_page(driver, url)

    def read(browser: webdriver.Chrome) -> dict | bool:
        check()
        fermer_invitation_connexion(browser)
        if captcha_present(browser):
            if not args.interactive:
                return False
            interact("TikTok affiche un CAPTCHA. Terminez cette vérification pour poursuivre.")
            check()
        return extract_record(browser.execute_script(PAGE_JS), url) or False

    # Une légende inaccessible reste une erreur d'extraction, sans pause de connexion.
    return WebDriverWait(driver, args.timeout).until(read)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("La valeur doit être un entier positif.")
    return number


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("La valeur doit être un nombre fini strictement positif.")
    return number


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hashtag", type=normalize_hashtag, help="Hashtag, avec ou sans #")
    parser.add_argument("--limit", type=positive_int, default=50, help="Maximum de publications (50)")
    parser.add_argument("--max-scrolls", type=positive_int, default=30, help="Défilements maximum (30)")
    parser.add_argument("--idle-rounds", type=positive_int, default=3, help="Arrêt après N défilements sans nouveauté (3)")
    parser.add_argument("--delay", type=positive_float, default=3.0, help="Pause entre pages/défilements, en secondes (3)")
    parser.add_argument("--timeout", type=positive_float, default=20.0, help="Délai de chargement, en secondes (20)")
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "exports")
    parser.add_argument("--interactive", action="store_true", help="Pause pour traiter les cookies ou un CAPTCHA dans Chrome")
    parser.add_argument("--headless", action="store_true", help="Chrome sans fenêtre, notamment sur VPS")
    parser.add_argument("--chrome-binary", type=Path, help="Chemin de Chrome/Chromium si non détecté")
    parser.add_argument("--driver", type=Path, help="ChromeDriver installé manuellement (sinon Selenium Manager)")
    args = parser.parse_args(argv)
    if args.headless and args.interactive:
        parser.error("--headless et --interactive sont incompatibles.")
    if args.interactive and not sys.stdin.isatty():
        parser.error("--interactive nécessite un terminal ouvert.")
    return args


def run(args: argparse.Namespace) -> int:
    args.output_dir.expanduser().mkdir(parents=True, exist_ok=True)
    # Nom horodaté : les collectes précédentes sont conservées.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    prefix = args.output_dir.expanduser().resolve() / f"tiktok_{args.hashtag[:60]}_{stamp}"
    report = {"hashtag": args.hashtag, "hashtag_url": f"https://www.tiktok.com/tag/{quote(args.hashtag)}",
              "started_at": utc_now(), "requested_limit": args.limit, "run_status": "running",
              "discovered_urls": [], "discovery_stop": "", "error": ""}
    records: list[dict] = []
    driver = None
    exit_code = 0
    try:
        save_results(prefix, records, report)
        driver = create_driver(args)
        links = collect_links(driver, args, report)
        save_results(prefix, records, report)
        for index, url in enumerate(links, 1):
            time.sleep(args.delay)
            LOG.info("Lecture %d/%d : %s", index, len(links), url)
            try:
                record = read_post(driver, url, args)
            except WebDriverException as exc:
                post_id, _, author = canonical_post(url)
                record = dict.fromkeys(FIELDS, "")
                record.update(id=post_id, url=url, author=author, hashtags=[],
                              collected_at=utc_now(), status="error",
                              error=f"{type(exc).__name__} : publication inaccessible ou structure non reconnue")
                LOG.warning("Publication inaccessible : %s", url)
            records.append(record)
            save_results(prefix, records, report)
        failures = any(r["status"] == "error" for r in records)
        report["run_status"] = "partial" if failures or report["discovery_stop"] == "blocked" else "completed"
        exit_code = 2 if report["run_status"] == "partial" else 0
    except KeyboardInterrupt:
        report["run_status"] = "interrupted"
        exit_code = 130
        LOG.warning("Arrêt demandé ; conservation des résultats déjà collectés.")
    except (RuntimeError, WebDriverException) as exc:
        report.update(run_status="failed", error=str(exc))
        exit_code = 1
        LOG.error("%s", exc)
    finally:
        try:
            save_results(prefix, records, report)
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except WebDriverException:
                    LOG.warning("Chrome était déjà fermé.")
        LOG.info("%d légende(s) sauvegardée(s). Exports : %s.{csv,json,txt}",
                 sum(bool(r["description"]) for r in records), prefix)
    return exit_code


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    args = parse_args(argv)
    try:
        return run(args)
    except OSError as exc:
        LOG.error("Impossible d'écrire les exports : %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
