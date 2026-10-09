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
from urllib.parse import quote, unquote, urlsplit

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
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
BLOCKED_JS = """
return Array.from(document.querySelectorAll(
    'iframe[src*="captcha"], [id*="captcha"], [class*="captcha-verify"], ' +
    '[data-e2e="login-modal"]'
)).some(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
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
            if isinstance(item.get("author"), dict):
                record["author"] = item["author"].get("uniqueId") or author
            # Une légende vide est un résultat valide quand l'ID est confirmé.
            break
    else:
        # Vérifier l'identité de la page avant le repli sur son texte affiché.
        current = canonical_post(snapshot.get("url", ""))
        canonical = canonical_post(snapshot.get("canonical", ""))
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
        writer = csv.DictWriter(stream, fieldnames=FIELDS, delimiter=";")
        writer.writeheader()
        for record in records:
            row = dict(record, hashtags=" ".join("#" + tag for tag in record["hashtags"]))
            writer.writerow({key: csv_safe(row.get(key, "")) for key in FIELDS})
    temp.replace(target)
    target = prefix.with_suffix(".txt")
    temp = target.with_suffix(".txt.tmp")
    temp.write_text("\n\n".join(
        f"{record['url']}\n{record['description']}" for record in records if record["description"]
    ) + "\n", encoding="utf-8")
    temp.replace(target)


def create_driver(args: argparse.Namespace) -> webdriver.Chrome:
    if not args.driver:
        # Un ancien ChromeDriver dans PATH ne doit pas empêcher Manager de choisir
        # la version correspondant au Chrome installé. --driver reste prioritaire.
        os.environ.setdefault("SE_SKIP_DRIVER_IN_PATH", "true")
    os.environ.setdefault("SE_CACHE_PATH", str(BASE_DIR / ".selenium-cache"))
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--lang=fr-FR")
    options.add_argument("--mute-audio")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--disable-dev-shm-usage")
    if os.getenv("CHROME_NO_SANDBOX") == "1":
        options.add_argument("--no-sandbox")
    if args.headless:
        options.add_argument("--headless=new")
    if args.profile_dir:
        options.add_argument(f"--user-data-dir={args.profile_dir.expanduser().resolve()}")
    if args.chrome_binary:
        options.binary_location = str(args.chrome_binary.expanduser().resolve())
    service = Service(executable_path=str(args.driver.expanduser().resolve())) if args.driver else Service()
    driver = webdriver.Chrome(options=options, service=service)
    driver.set_page_load_timeout(args.timeout)
    return driver


def manual_step(message: str) -> None:
    print(f"\n{message}\nIntervenez dans Chrome, puis appuyez sur Entrée ici (Ctrl+C pour arrêter).")
    try:
        input()
    except EOFError as exc:
        raise RuntimeError("Le mode interactif nécessite un terminal ouvert.") from exc


def open_page(driver: webdriver.Chrome, url: str) -> None:
    try:
        driver.get(url)
    except TimeoutException:
        # Une navigation incomplète ne doit pas faire lire la page précédente.
        driver.execute_script("window.stop();")
        raise


def collect_links(driver: webdriver.Chrome, args: argparse.Namespace, report: dict,
                  *, interact=manual_step, progress=None, check=None, validation_initiale=True) -> list[str]:
    check = check or (lambda: None)
    check()
    open_page(driver, report["hashtag_url"])
    if args.interactive and validation_initiale:
        interact("Vérifiez que les publications sont visibles. Traitez les cookies, une connexion ou un CAPTCHA si nécessaire.")
    links: dict[str, str] = {}

    def scan(browser: webdriver.Chrome) -> bool:
        check()
        # Une autre source réutilise la session ; seules les vérifications visibles
        # de TikTok interrompent alors la collecte, même si des liens restent derrière.
        if args.interactive and browser.execute_script(BLOCKED_JS):
            interact("TikTok affiche une connexion ou une vérification. Terminez-la pour poursuivre.")
            check()
        previous = len(links)
        for href in browser.execute_script(DISCOVER_JS):
            identity = canonical_post(href)
            if identity and report.get("compte_attendu") and identity[2].lower() != report["compte_attendu"]:
                continue
            if identity and len(links) < args.limit:
                links.setdefault(identity[0], identity[1])
        report["discovered_urls"] = list(links.values())
        if progress:
            progress(len(links))
        return len(links) > previous

    try:
        WebDriverWait(driver, args.timeout).until(scan)
    except TimeoutException as exc:
        if driver.execute_script(BLOCKED_JS):
            report["discovery_stop"] = "blocked"
            raise RuntimeError(
                "TikTok affiche une connexion ou un CAPTCHA. Relancez avec --interactive, "
                "terminez la vérification dans Chrome, puis appuyez sur Entrée dans le terminal."
            ) from exc
        raise RuntimeError(
            "Aucune publication accessible pour ce hashtag. La page peut être vide, bloquée, "
            "ou avoir changé. Relancez avec --interactive et vérifiez Chrome."
        ) from exc
    idle = 0
    for _ in range(args.max_scrolls):
        check()
        if len(links) >= args.limit:
            report["discovery_stop"] = "limit"
            break
        if driver.execute_script(BLOCKED_JS):
            if args.interactive:
                interact("TikTok affiche une connexion ou une vérification.")
            else:
                report["discovery_stop"] = "blocked"
                break
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(args.delay)
        try:
            WebDriverWait(driver, args.timeout).until(scan)
            idle = 0
        except TimeoutException:
            idle += 1
        LOG.info("%d publication(s) repérée(s)", len(links))
        if idle >= args.idle_rounds:
            report["discovery_stop"] = "no_new_links"
            break
    else:
        report["discovery_stop"] = "max_scrolls"
    if len(links) >= args.limit:
        report["discovery_stop"] = "limit"
    return list(links.values())


def read_post(driver: webdriver.Chrome, url: str, args: argparse.Namespace,
              *, interact=manual_step, check=None) -> dict:
    check = check or (lambda: None)
    check()
    open_page(driver, url)

    def read(browser: webdriver.Chrome) -> dict | bool:
        check()
        return extract_record(browser.execute_script(PAGE_JS), url) or False

    try:
        return WebDriverWait(driver, args.timeout).until(read)
    except TimeoutException:
        if not args.interactive:
            raise
        interact("Légende non accessible. Vérifiez la publication, la connexion et un éventuel CAPTCHA.")
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
    parser.add_argument("--interactive", action="store_true", help="Pause pour se connecter ou traiter les blocages dans Chrome")
    parser.add_argument("--headless", action="store_true", help="Chrome sans fenêtre, notamment sur VPS")
    parser.add_argument("--profile-dir", type=Path, help="Profil Chrome dédié pour conserver la session")
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
