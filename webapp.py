"""Interface web : un navigateur isolé par collecte, piloté uniquement par son worker."""
from __future__ import annotations

import json
import signal
import subprocess
import sys
import argparse
import base64
import hmac
import logging
import os
import queue
import re
import unicodedata
import secrets
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import scraptiktok as scraper
from language_filter import classify_description
from video.disponibilite import video_disponible
from collecte.dates import normaliser_date, evaluer_periode

LOG = logging.getLogger("scraptiktok.web")
TERMINAL = {"completed", "partial", "failed", "stopped"}
COOKIE = "scraptiktok_session"


class StartRequest(BaseModel):
    hashtag: str = Field(default="", max_length=100)
    source_collecte: Literal["hashtags", "comptes", "presse"] = "hashtags"
    comptes: list[str] = Field(default_factory=list, max_length=10)
    medias: list[str] = Field(default_factory=list, max_length=20)
    enrichir: bool = False
    collecter_commentaires: bool = False
    collecter_reponses: bool = False
    limite_commentaires: int = Field(default=50, ge=1, le=500)
    second_hashtag: str = Field(default="", max_length=100)
    operator: Literal["AND", "OR"] = "AND"
    limit: int = Field(default=50, ge=1, le=300)
    include_sources: bool = True
    french_only: bool = False
    date_debut: str | None = Field(default=None, max_length=10)
    date_fin: str | None = Field(default=None, max_length=10)

    @field_validator("date_debut", "date_fin")
    @classmethod
    def valider_date(cls, valeur):
        return normaliser_date(valeur)

    @field_validator("hashtag")
    @classmethod
    def valid_hashtag(cls, value):
        if not value.strip(): return ""
        try:
            return scraper.normalize_hashtag(value)
        except argparse.ArgumentTypeError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("second_hashtag")
    @classmethod
    def valid_second_hashtag(cls, value):
        return cls.valid_hashtag(value) if value.strip() else ""

    @field_validator("comptes")
    @classmethod
    def valider_comptes(cls, valeurs):
        from collecte.verification_comptes import normaliser_compte
        return list(dict.fromkeys(normaliser_compte(v) for v in valeurs))

    @model_validator(mode="after")
    def valider_sources(self):
        if self.date_debut and self.date_fin and self.date_debut > self.date_fin:
            raise ValueError("La date de début doit précéder ou égaler la date de fin.")
        if self.source_collecte == "hashtags" and not self.hashtag:
            raise ValueError("Le premier hashtag est obligatoire.")
        if self.second_hashtag and not self.hashtag:
            raise ValueError("Renseignez le premier hashtag avant le deuxième.")
        if self.source_collecte == "comptes" and not self.comptes:
            raise ValueError("Renseignez au moins un compte TikTok.")
        if self.source_collecte == "presse":
            from collecte.presse import selectionner_medias
            if not self.medias: raise ValueError("Sélectionnez au moins un média.")
            selectionner_medias(self.medias)
        if self.collecter_reponses: self.collecter_commentaires = True
        return self

    @property
    def enrichie(self):
        return self.enrichir or self.source_collecte != "hashtags" or self.collecter_commentaires

    @property
    def libelle(self):
        if self.source_collecte == "hashtags":
            return (" OU " if self.operator == "OR" else " ET ").join("#" + h for h in self.hashtags)
        return ", ".join("@" + s["compte"] for s in self.sources)

    @property
    def sources(self):
        from collecte.presse import selectionner_medias
        if self.source_collecte == "presse": return selectionner_medias(self.medias)
        return [{"compte": c, "id": None, "categorie": None} for c in self.comptes]

    @property
    def hashtags(self):
        return list({tag_key(tag): tag for tag in [self.hashtag, self.second_hashtag] if tag}.values())

    @property
    def filename(self):
        joiner = "_ET_" if self.operator == "AND" else "_OU_"
        return "tiktok_" + (joiner.join(self.hashtags) if self.source_collecte == "hashtags" else "comptes_" + "_".join(s["compte"] for s in self.sources)[:100]) + ("_fr" if self.french_only else "") + ".txt"


def tag_key(value):
    return unicodedata.normalize("NFC", value).casefold()


def matches_hashtags(description, settings):
    if not settings.second_hashtag and (settings.source_collecte == "hashtags" or not settings.hashtag):
        return True  # Conserver le comportement historique de la recherche simple.
    present = set(re.findall(r"#(\w+)", tag_key(description)))
    matches = [tag_key(tag) in present for tag in settings.hashtags]
    return all(matches) if settings.operator == "AND" else any(matches)


class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class BrowserAction(BaseModel):
    kind: Literal["click", "drag", "pointer_down", "pointer_move", "pointer_up", "pointer_cancel", "text", "key", "scroll"]
    points: list[Point] = Field(default_factory=list, max_length=80)
    text: str = Field(default="", max_length=2000)
    key: Literal["Enter", "Tab", "Backspace", "Escape", "select_all"] = "Enter"
    delta: int = Field(default=0, ge=-1200, le=1200)


class Stopped(Exception):
    pass


class LiveAction:
    def __init__(self, action):
        self.action = action
        self.done = threading.Event()
        self.error = ""


def text_export(records: list[dict], include_sources: bool) -> str:
    blocks = []
    for record in records:
        if not record.get("description"):
            continue
        prefix = f"@{record['author']}\n{record['url']}\n" if include_sources else ""
        blocks.append(prefix + record["description"])
    return "\n\n".join(blocks) + ("\n" if blocks else "")


class Job:
    def __init__(self, owner: str, settings: StartRequest, data_dir: Path):
        self.id = uuid.uuid4().hex
        self.owner = owner
        self.settings = settings
        self.racine = data_dir
        if settings.enrichie:
            from stockage.sessions import creer_dossier_session
            self.directory = creer_dossier_session(data_dir, self.id)
        else:
            self.directory = data_dir / self.id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "textes.txt"
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.commands = queue.Queue(maxsize=8)
        self.created = self.last_seen = time.monotonic()
        self.finished = None
        self.busy = True
        self.status = "starting"
        self.message = "Ouverture du navigateur…"
        self.discovered = 0
        self.processed = 0
        self.errors = 0
        self.filtered = 0
        self.non_french = 0
        self.language_unknown = 0
        self.hors_periode = 0
        self.dates_indeterminees = 0
        self.search_errors = 0
        self.records = []
        self.frame = b""
        self.action_error = ""
        self.thread = None
        self.publications = []
        self.commentaires = []
        self.journal = []
        self.archive_prete = False
        self.video_busy = False
        self.video_statut = "non_lance"
        self.video_stop = threading.Event()
        self.video_process = None
        self.video_thread = None
        self.video_debut = None
        self.base = None
        if settings.enrichie:
            from stockage.base_donnees import BaseDonnees
            self.base = BaseDonnees(data_dir / "scraptiktok.sqlite")
            self.base.creer_session(self.id, owner, scraper.utc_now(), settings.model_dump())

    def update(self, **values):
        with self.lock:
            for key, value in values.items():
                setattr(self, key, value)

    def snapshot(self):
        with self.lock:
            progression = None
            if self.video_busy:
                try:
                    etat = json.loads((self.directory / "traitement_video.json").read_text())
                    progression = {cle:etat.get(cle) for cle in ("etape","videos_analysees","comparaisons")}
                except (OSError, ValueError): pass
            return {"id": self.id, "hashtag": self.settings.hashtag,
                    "second_hashtag": self.settings.second_hashtag, "operator": self.settings.operator,
                    "hashtags": self.settings.hashtags, "filename": self.settings.filename,
                    "filtered": self.filtered, "search_errors": self.search_errors,
                    "french_only": self.settings.french_only, "include_sources": self.settings.include_sources,
                    "non_french": self.non_french, "language_unknown": self.language_unknown,
                    "date_debut": self.settings.date_debut, "date_fin": self.settings.date_fin,
                    "hors_periode": self.hors_periode, "dates_indeterminees": self.dates_indeterminees,
                    "source_collecte": self.settings.source_collecte, "comptes": self.settings.comptes,
                    "medias": self.settings.medias, "libelle": self.settings.libelle,
                    "enrichir": self.settings.enrichie, "commentaires_collectes": len(self.commentaires),
                    "collecter_commentaires":self.settings.collecter_commentaires, "collecter_reponses":self.settings.collecter_reponses,
                    "limite_commentaires":self.settings.limite_commentaires,
                    "archive_prete": self.archive_prete, "video_progression":progression, "video_busy": self.video_busy, "video_statut": self.video_statut, "video_disponible": video_disponible(),
                    "limit": self.settings.limit, "status": self.status, "busy": self.busy,
                    "message": self.message, "discovered": self.discovered,
                    "processed": self.processed, "captions": len(self.records),
                    "errors": self.errors, "has_frame": bool(self.frame),
                    "action_error": self.action_error, "can_download": bool(self.records),
                    "preview": [{"author": r["author"], "description": r["description"]}
                                for r in self.records[:5]]}

    def check(self):
        if self.stop.is_set():
            raise Stopped()

    def pause(self, seconds):
        if self.stop.wait(seconds):
            raise Stopped()

    def save(self):
        # Les profils et captures ne sont jamais écrits dans les exports.
        with self.lock:
            content = text_export(self.records, self.settings.include_sources)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(self.path)


def release_pointer(driver):
    point = getattr(driver, "_scraptiktok_pointer", None)
    if isinstance(point, dict):
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased", **point, "button": "left", "buttons": 0, "clickCount": 1})
        driver._scraptiktok_pointer = None
    ActionChains(driver).reset_actions()


def perform_action(driver, action: BrowserAction):
    """Rejoue les gestes humains reçus ; aucun solveur de CAPTCHA ni JS utilisateur."""
    width, height = driver.execute_script("return [window.innerWidth, window.innerHeight];")
    chain = ActionChains(driver, duration=60)

    def move(point):
        chain.w3c_actions.pointer_action.move_to_location(
            min(width - 1, round(point.x * width)), min(height - 1, round(point.y * height)))

    if action.kind.startswith("pointer_"):
        if action.kind == "pointer_cancel":
            release_pointer(driver)
            return
        point = action.points[0]
        coords = {"x": min(width - 1, round(point.x * width)),
                  "y": min(height - 1, round(point.y * height))}
        # Chromium : conserver le bouton et la capture DOM entre deux requêtes.
        # Des séquences W3C séparées peuvent perdre la capture du curseur natif.
        event_type = {"pointer_down": "mousePressed", "pointer_move": "mouseMoved",
                      "pointer_up": "mouseReleased"}[action.kind]
        driver._scraptiktok_pointer = coords
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
            "type": event_type, **coords, "button": "left",
            "buttons": 0 if action.kind == "pointer_up" else 1, "clickCount": 1})
        if action.kind == "pointer_up":
            driver._scraptiktok_pointer = None
    elif action.kind in {"click", "drag"}:
        if not action.points:
            raise ValueError("Le geste ne contient aucune position.")
        move(action.points[0])
        if action.kind == "click":
            chain.click()
        else:
            chain.click_and_hold()
            for point in action.points[1:]:
                move(point)
            chain.release()
        chain.perform()
    elif action.kind == "text":
        chain.send_keys(action.text).perform()
    elif action.kind == "key":
        if action.key == "select_all":
            modifier = Keys.COMMAND if driver.capabilities.get("platformName") == "mac" else Keys.CONTROL
            chain.key_down(modifier).send_keys("a").key_up(modifier).perform()
        else:
            mapping = {"Enter": Keys.ENTER, "Tab": Keys.TAB,
                       "Backspace": Keys.BACKSPACE, "Escape": Keys.ESCAPE}
            chain.send_keys(mapping[action.key]).perform()
    else:
        driver.execute_script("window.scrollBy(0, arguments[0]);", action.delta)


def wait_for_user(driver, job: Job, message: str):
    previous = job.status
    job.update(status="attention", message=message, action_error="")
    next_frame = 0
    held_since = None
    try:
        while True:
            job.check()
            if held_since is not None and time.monotonic() - held_since > 15:
                release_pointer(driver)
                held_since = None
            if time.monotonic() >= next_frame:
                job.update(frame=driver.get_screenshot_as_png())
                next_frame = time.monotonic() + 0.25
            try:
                command = job.commands.get(timeout=0.15)
            except queue.Empty:
                continue
            if command == "continue":
                if driver.execute_script(scraper.BLOCKED_JS):
                    job.update(action_error="TikTok affiche encore une vérification ou une connexion. Terminez-la dans l’image avant de continuer.")
                    continue
                break
            live = command if isinstance(command, LiveAction) else None
            if live:
                command = live.action
            try:
                perform_action(driver, command)
                if command.kind in {"pointer_down", "pointer_move"}:
                    held_since = time.monotonic()
                elif command.kind in {"pointer_up", "pointer_cancel"}:
                    held_since = None
                job.update(action_error="")
                next_frame = 0
            except (scraper.WebDriverException, ValueError):
                message = "Ce geste n’a pas abouti. Attendez l’actualisation de l’image et réessayez."
                job.update(action_error=message)
                if live:
                    live.error = message
            finally:
                if live:
                    live.done.set()
    finally:
        try:
            release_pointer(driver)
        except scraper.WebDriverException:
            pass
        job.update(status=previous, frame=b"")
        while not job.commands.empty():
            try:
                pending = job.commands.get_nowait()
                if isinstance(pending, LiveAction):
                    pending.error = "L’interaction avec le navigateur est terminée."
                    pending.done.set()
            except queue.Empty:
                break


def execute_job(job: Job, driver_factory=scraper.create_driver):
    args = argparse.Namespace(
        hashtag=job.settings.hashtag, limit=job.settings.limit, max_scrolls=40,
        idle_rounds=3, delay=3.0, timeout=20.0, interactive=True,
        headless=os.getenv("SCRAPTIKTOK_HEADLESS", "1") == "1", profile_dir=None,
        chrome_binary=Path(os.environ["CHROME_BINARY"]) if os.getenv("CHROME_BINARY") else None,
        driver=Path(os.environ["CHROMEDRIVER"]) if os.getenv("CHROMEDRIVER") else None,
    )
    driver = None
    final_status, final_message = "failed", "La collecte n’a pas pu aboutir."
    try:
        job.check()
        driver = driver_factory(args)
        interact = lambda message: wait_for_user(driver, job, message)
        unique_links = {}
        sources = ([{"hashtag": h} for h in job.settings.hashtags]
                   if job.settings.source_collecte == "hashtags" else job.settings.sources)
        medias_par_compte = {s["compte"]: s for s in job.settings.sources}
        session_validee = False
        def intervenir(message):
            nonlocal session_validee
            interact(message)
            session_validee = True
        for source in sources:
            etiquette = "#" + source["hashtag"] if "hashtag" in source else "@" + source["compte"]
            job.update(status="discovering", message=f"Recherche des publications de {etiquette}…")
            try:
                if "hashtag" in source:
                    rapport = {"hashtag_url": f"https://www.tiktok.com/tag/{quote(source['hashtag'])}"}
                    found = scraper.collect_links(driver, args, rapport,
                        interact=lambda message: intervenir(f"{etiquette} : {message}"), check=job.check,
                        validation_initiale=not session_validee)
                else:
                    from collecte.comptes import collecter_compte
                    rapport = {}
                    found = collecter_compte(driver, args, source["compte"], rapport=rapport,
                        interact=lambda message: intervenir(f"{etiquette} : {message}"), check=job.check,
                        validation_initiale=not session_validee)
                job.journal.append({"source":etiquette,"date":scraper.utc_now(),"rapport":rapport})
                for url in found:
                    identity = scraper.canonical_post(url)
                    if identity: unique_links.setdefault(identity[0], identity[1])
            except (RuntimeError, scraper.WebDriverException):
                job.journal.append({"source": etiquette, "statut": "inaccessible", "date": scraper.utc_now()})
                if len(sources) == 1: raise
                job.update(search_errors=job.search_errors + 1)
            job.update(discovered=len(unique_links))
        links = list(unique_links.values())
        job.update(status="collecting", discovered=len(links))
        for index, url in enumerate(links, 1):
            job.pause(args.delay)
            job.update(message=f"Lecture de la publication {index} sur {len(links)}…")
            try:
                record = scraper.read_post(driver, url, args, interact=interact, check=job.check)
                periode = evaluer_periode(record.get("created_at"), job.settings.date_debut, job.settings.date_fin)
                if periode in {"hors_periode", "date_indeterminee"}:
                    with job.lock:
                        if periode == "hors_periode": job.hors_periode += 1
                        else: job.dates_indeterminees += 1
                    job.journal.append({"publication_id":record["id"], "created_at":record.get("created_at"), "filtre_date":periode})
                else:
                    if job.settings.enrichie:
                        media = medias_par_compte.get(record["author"].lower(), {})
                        record.update(media_id=media.get("id"), categorie_media=media.get("categorie"), retenue=False)
                        job.publications.append(record)
                        if job.settings.collecter_commentaires:
                            from collecte.commentaires import collecter_commentaires
                            try:
                                resultat = collecter_commentaires(driver, record, job.settings.limite_commentaires,
                                    job.settings.collecter_reponses, verifier=job.check, pause=job.pause)
                                job.commentaires.extend(resultat.pop("commentaires"))
                                record["collecte_commentaires"] = resultat
                            except scraper.WebDriverException:
                                record["collecte_commentaires"] = {"statut": "inaccessible", "exhaustif": False}
                    if record["description"]:
                        matches = matches_hashtags(record["description"], job.settings)
                        language = (classify_description(record["description"])
                                    if matches and job.settings.french_only else "fr")
                        with job.lock:
                            if not matches:
                                job.filtered += 1
                            elif language == "other":
                                job.non_french += 1
                            elif language == "unknown":
                                job.language_unknown += 1
                            else:
                                record["retenue"] = True
                                job.records.append(record)
            except scraper.WebDriverException:
                with job.lock:
                    job.errors += 1
            job.update(processed=index)
            job.save()
            if job.base:
                job.base.enregistrer(job.id, job.publications[-1:], job.commentaires)
        final_status = "partial" if job.errors or job.search_errors else "completed"
        final_message = f"{len(job.records)} texte(s) collecté(s) sur {job.processed} publication(s) consultée(s)."
        if not job.records:
            final_message = "Aucun texte récupéré. TikTok peut limiter l’accès ou les publications peuvent être sans légende."
            if job.settings.second_hashtag and job.processed:
                final_message = "Aucun texte ne correspond à cette combinaison dans les publications consultées."
        if job.settings.french_only:
            if not job.records and (job.non_french or job.language_unknown):
                final_message = "Aucun texte retenu par le filtre français parmi les descriptions correspondant aux hashtags."
            final_message += f" Filtre français : {job.non_french} texte(s) dans une autre langue, {job.language_unknown} texte(s) trop court(s) ou de langue incertaine écartés."
        if job.settings.second_hashtag:
            final_message += f" {job.filtered} texte(s) écarté(s) par le filtre ET/OU."
        if job.settings.date_debut or job.settings.date_fin:
            if not job.records and (job.hors_periode or job.dates_indeterminees):
                final_message = "Aucun texte retenu avec la période et les autres filtres choisis."
            final_message += f" Période : {job.hors_periode} publication(s) hors période et {job.dates_indeterminees} publication(s) sans date exploitable écartées."
        if job.search_errors:
            final_message += f" {job.search_errors} recherche(s) de hashtag inaccessible(s) ; les résultats sont incomplets."
        if not links and job.search_errors:
            final_status = "failed"
        elif len(links) < args.limit and not job.settings.second_hashtag:
            final_message += f" La recherche a fourni {len(links)} lien(s), pour un objectif de {args.limit}."
    except Stopped:
        final_status, final_message = "stopped", "Collecte arrêtée. Les textes déjà obtenus restent téléchargeables."
    except RuntimeError:
        final_message = "Aucune publication accessible. Vérifiez le hashtag et réessayez après avoir terminé la vérification TikTok."
    except Exception:
        LOG.exception("Échec de la collecte %s", job.id)
        final_message = "La connexion au navigateur a échoué. Les textes déjà obtenus sont conservés. Réessayez ou contactez l’administrateur."
    finally:
        try:
            job.save()
        except OSError:
            LOG.exception("Écriture de l’export impossible")
            final_status, final_message = "failed", "Le serveur n’a pas pu enregistrer le fichier texte."
        if driver is not None:
            try:
                driver.quit()
            except scraper.WebDriverException:
                LOG.warning("Fermeture du navigateur impossible pour %s", job.id)
        if job.base:
            try:
                from corpus.construction import construire_exports
                from corpus.export_zip import exporter_zip
                job.base.enregistrer(job.id, job.publications, job.commentaires)
                job.base.terminer_session(job.id, final_status)
                from stockage.historique import ajouter_evenement
                for evenement in job.journal: ajouter_evenement(job.base,job.id,evenement)
                construire_exports(job.directory, job.publications, job.commentaires,
                    {"session": job.id, "statut": final_status, "parametres": job.settings.model_dump(), "evenements": job.journal})
                exporter_zip(job.directory, job.directory / "archive.zip")
                job.archive_prete = True
            except Exception:
                LOG.exception("Export enrichi impossible")
                final_message += " L’archive enrichie n’a pas pu être finalisée ; le TXT reste disponible."
        job.update(status=final_status, message=final_message, busy=False,
                   finished=time.monotonic(), frame=b"")


class Manager:
    def __init__(self, data_dir=None, runner=execute_job, max_jobs=None):
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", str(scraper.BASE_DIR / "data")))
        self.max_jobs = max_jobs or max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
        self.retention = max(60, int(os.getenv("RESULT_TTL_SECONDS", "3600")))
        self.idle_timeout = max(60, int(os.getenv("IDLE_TIMEOUT_SECONDS", "300")))
        self.max_duration = max(60, int(os.getenv("JOB_TIMEOUT_SECONDS", "1800")))
        self.runner = runner
        self.jobs = {}
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.reaper = None

    def start(self, owner, settings):
        with self.lock:
            if any(j.video_busy for j in self.jobs.values()):
                raise HTTPException(429, "Un traitement vidéo est en cours. Patientez avant une nouvelle collecte.")
            active = [job for job in self.jobs.values() if job.busy]
            if any(job.owner == owner for job in active):
                raise HTTPException(409, "Une collecte est déjà en cours dans votre session.")
            if len(active) >= self.max_jobs:
                raise HTTPException(429, "Le navigateur est occupé par une autre collecte. Réessayez dans quelques minutes.")
            job = Job(owner, settings, self.data_dir)
            self.jobs[job.id] = job
            job.thread = threading.Thread(target=self.runner, args=(job,), daemon=True)
            job.thread.start()
            return job

    def get(self, owner, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None or job.owner != owner:
                raise HTTPException(404, "Cette collecte est introuvable ou a expiré.")
            job.last_seen = time.monotonic()
            return job

    def latest(self, owner):
        with self.lock:
            jobs = [j for j in self.jobs.values() if j.owner == owner]
            if not jobs:
                return None
            job = max(jobs, key=lambda j: j.created)
            job.last_seen = time.monotonic()
            return job

    def cleanup(self):
        now = time.monotonic()
        with self.lock:
            for job in list(self.jobs.values()):
                if job.busy and (now - job.last_seen > self.idle_timeout or now - job.created > self.max_duration):
                    job.stop.set()
                if job.video_busy and (now-job.last_seen>self.idle_timeout or now-job.video_debut>7200):
                    job.video_stop.set()
                if not job.busy and not job.video_busy and job.finished is not None and now - job.finished > self.retention:
                    self.jobs.pop(job.id)
                    shutil.rmtree(job.directory, ignore_errors=True)
                    if job.base: job.base.supprimer_session(job.id)
            if (self.data_dir / "scraptiktok.sqlite").exists():
                from stockage.nettoyage import nettoyer_sessions
                from stockage.base_donnees import BaseDonnees
                base = BaseDonnees(self.data_dir / "scraptiktok.sqlite")
                nettoyer_sessions(self.data_dir, base, self.retention, self.jobs)
                from stockage.cache_video import purger_cache
                purger_cache(base,self.retention)
            # Retire également les exports orphelins après un redémarrage.
            if self.data_dir.exists():
                for directory in self.data_dir.iterdir():
                    if (directory.is_dir() and len(directory.name) == 32
                            and directory.name not in self.jobs
                            and time.time() - directory.stat().st_mtime > self.retention):
                        shutil.rmtree(directory, ignore_errors=True)

    def maintain(self):
        while not self.closed.wait(15):
            self.cleanup()

    def shutdown(self):
        self.closed.set()
        with self.lock:
            jobs = list(self.jobs.values())
            for job in jobs:
                job.stop.set()
                job.video_stop.set()
        deadline = time.monotonic() + 25
        for job in jobs:
            if job.video_thread:
                job.video_thread.join(timeout=5)
            if job.thread:
                job.thread.join(timeout=max(0, deadline - time.monotonic()))


class OptionsVideo(BaseModel):
    comparer_sha256: bool = True
    comparer_sequences: bool = True
    audio: bool = False
    ocr: bool = False
    transcription: bool = False
    embeddings: bool = False
    telecharger_modeles: bool = False


def executer_video(job, options):
    from video.parametres import charger_parametres
    from corpus.export_json import exporter_json
    try:
        parametres = charger_parametres()
        parametres.update(options.model_dump(), telecharger_videos=True, audio=options.audio or options.transcription)
        chemin = job.directory / "parametres_traitement.json"
        exporter_json(chemin, parametres)
        with (job.directory / "traitement.log").open("w") as journal:
            processus = subprocess.Popen([sys.executable, "-m", "video.lots", "--session", str(job.directory), "--parametres", str(chemin)],
                cwd=scraper.BASE_DIR, stdout=journal, stderr=subprocess.STDOUT, start_new_session=True)
            job.video_process = processus
            limite = time.monotonic() + parametres["duree_lot_max_s"] + 60
            while processus.poll() is None:
                if job.video_stop.wait(0.5) or time.monotonic() > limite:
                    os.killpg(processus.pid, signal.SIGTERM)
                    try: processus.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(processus.pid, signal.SIGKILL); processus.wait()
                    # Le téléchargement et ffmpeg appartiennent au même groupe.
                    try: os.killpg(processus.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    job.update(video_statut="interrompu")
                    break
            else:
                job.update(video_statut="termine" if processus.returncode == 0 else "partiel" if processus.returncode == 2 else "echec")
    except Exception:
        LOG.exception("Traitement vidéo interrompu")
        job.update(video_statut="echec")
    finally:
        job.update(video_busy=False, video_process=None, finished=time.monotonic())


def create_app(manager=None):
    manager = manager or Manager()

    @asynccontextmanager
    async def lifespan(app):
        manager.reaper = threading.Thread(target=manager.maintain, daemon=True)
        manager.reaper.start()
        yield
        manager.shutdown()

    app = FastAPI(title="ScrapTikTok", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.manager = manager

    @app.middleware("http")
    async def security(request, call_next):
        password = os.getenv("APP_ACCESS_PASSWORD", "")
        if password and request.url.path != "/healthz":
            expected_user = os.getenv("APP_ACCESS_USER", "scraptiktok")
            try:
                scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
                user, secret = base64.b64decode(encoded, validate=True).decode().split(":", 1)
                accepted = scheme.lower() == "basic" and hmac.compare_digest(user.encode(), expected_user.encode()) and hmac.compare_digest(secret.encode(), password.encode())
            except (ValueError, UnicodeError):
                accepted = False
            if not accepted:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="ScrapTikTok"'})
        if request.method == "POST" and not (os.getenv("UI_STREAMLIT", "0") == "1" and request.url.path.startswith("/_stcore/")):
            # Les requêtes de mutation viennent uniquement de notre propre page.
            if request.headers.get("x-scraptiktok") != "1":
                return JSONResponse({"detail": "Requête non autorisée."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if os.getenv("UI_STREAMLIT", "0") == "1" and not request.url.path.startswith(("/api/", "/classique", "/healthz", "/static/app.js", "/static/style.css")):
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self'; base-uri 'self'"
            return response
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
        return response

    def owner(request):
        session = request.cookies.get(COOKIE, "")
        if len(session) != 64 or any(c not in "0123456789abcdef" for c in session):
            raise HTTPException(401, "Rechargez la page pour ouvrir une session.")
        return session

    @app.get("/healthz")
    def health():
        if os.getenv("UI_STREAMLIT", "0") == "1":
            import urllib.request
            try:
                with urllib.request.urlopen("http://127.0.0.1:" + os.getenv("STREAMLIT_PORT", "8502") + "/_stcore/health",timeout=2): pass
            except OSError: raise HTTPException(503,"Interface Streamlit indisponible.")
        return {"status": "ok"}

    @app.get("/")
    @app.get("/classique")
    async def home(request: Request):
        response = (await app.state.relayer_streamlit(request, "") if request.url.path == "/" and os.getenv("UI_STREAMLIT", "0") == "1" else FileResponse(scraper.BASE_DIR / "static" / "index.html"))
        if not request.cookies.get(COOKIE):
            response.set_cookie(COOKIE, secrets.token_hex(32), httponly=True, samesite="strict",
                                secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=86400)
        return response

    @app.post("/api/jobs/{job_id}/video", status_code=202)
    def lancer_analyse_video(job_id: str, options: OptionsVideo, request: Request):
        job = manager.get(owner(request), job_id)
        if not video_disponible():
            raise HTTPException(409, "Le traitement vidéo n’est pas activé sur ce serveur.")
        with manager.lock:
            if any(j.busy or j.video_busy for j in manager.jobs.values()):
                raise HTTPException(409, "Une collecte ou analyse est déjà en cours.")
            if not job.archive_prete or not job.publications:
                raise HTTPException(409, "Effectuez d’abord une collecte enrichie.")
            job.video_stop.clear()
            job.update(video_busy=True, video_statut="en_cours", video_debut=time.monotonic())
            job.video_thread = threading.Thread(target=executer_video, args=(job, options), daemon=True)
            job.video_thread.start()
        return job.snapshot()

    @app.post("/api/jobs/{job_id}/video/stop")
    def arreter_analyse_video(job_id: str, request: Request):
        manager.get(owner(request), job_id).video_stop.set()
        return {"ok": True}

    @app.get("/api/presse")
    def inventaire_presse(request: Request):
        owner(request)
        from collecte.presse import charger_inventaire
        return {"medias": charger_inventaire()}

    @app.get("/api/jobs/{job_id}/archive")
    def telecharger_archive(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        if job.busy or job.video_busy or not job.archive_prete:
            raise HTTPException(409, "L’archive enrichie n’est pas encore disponible.")
        return FileResponse(job.directory / "archive.zip", filename=f"scraptiktok_{job.id}.zip", media_type="application/zip")

    @app.get("/api/configuration")
    def configuration_interface(request: Request):
        owner(request)
        return {"video_disponible":video_disponible()}

    @app.get("/api/session")
    def session(request: Request):
        job = manager.latest(owner(request))
        return {"job": job.snapshot() if job else None}

    @app.post("/api/jobs", status_code=202)
    def start(payload: StartRequest, request: Request):
        return manager.start(owner(request), payload).snapshot()

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str, request: Request):
        return manager.get(owner(request), job_id).snapshot()

    @app.post("/api/jobs/{job_id}/stop")
    def stop(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        job.stop.set()
        return {"ok": True}

    def enqueue(job, command):
        with job.lock:
            if job.status != "attention":
                raise HTTPException(409, "Le navigateur n’attend pas d’intervention.")
            try:
                job.commands.put_nowait(command)
            except queue.Full:
                raise HTTPException(429, "Patientez un instant avant le prochain geste.")

    @app.post("/api/jobs/{job_id}/continue")
    def resume(job_id: str, request: Request):
        enqueue(manager.get(owner(request), job_id), "continue")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/action", status_code=202)
    def action(job_id: str, payload: BrowserAction, request: Request):
        if payload.kind in {"click", "drag", "pointer_down", "pointer_move", "pointer_up"} and not payload.points:
            raise HTTPException(422, "Une position est requise.")
        job = manager.get(owner(request), job_id)
        if payload.kind.startswith("pointer_"):
            command = LiveAction(payload)
            enqueue(job, command)
            # Accusé de réception après exécution : le client ne sature pas la file.
            if not command.done.wait(10):
                raise HTTPException(504, "Le navigateur ne répond pas. Attendez puis réessayez.")
            if command.error:
                raise HTTPException(409, command.error)
        else:
            enqueue(job, payload)
        return {"ok": True}

    @app.get("/api/jobs/{job_id}/frame")
    def frame(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        with job.lock:
            return Response(job.frame, media_type="image/png", status_code=200 if job.frame else 204)

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        if not job.path.exists() or not job.records:
            raise HTTPException(409, "Aucun texte n’est encore disponible.")
        filename = job.settings.filename
        return Response(job.path.read_bytes(), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})

    if os.getenv("UI_STREAMLIT", "0") == "1":
        @app.get("/interface")
        @app.get("/interface/")
        def ancienne_adresse():
            return RedirectResponse("/", status_code=302)

        # Les deux ressources historiques restent disponibles pour le contrôleur intégré.
        @app.get("/static/app.js")
        def script_classique():
            return FileResponse(scraper.BASE_DIR / "static" / "app.js")

        @app.get("/static/style.css")
        def style_classique():
            return FileResponse(scraper.BASE_DIR / "static" / "style.css")

        from interface.passerelle import installer_passerelle
        installer_passerelle(app)
    else:
        app.mount("/static", StaticFiles(directory=scraper.BASE_DIR / "static"), name="static")
    return app


app = create_app()
