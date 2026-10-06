"""Interface web : un navigateur isolé par collecte, piloté uniquement par son worker."""
from __future__ import annotations

import argparse
import base64
import hmac
import logging
import os
import queue
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
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import scraptiktok as scraper

LOG = logging.getLogger("scraptiktok.web")
TERMINAL = {"completed", "partial", "failed", "stopped"}
COOKIE = "scraptiktok_session"


class StartRequest(BaseModel):
    hashtag: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=50, ge=1, le=300)
    include_sources: bool = True

    @field_validator("hashtag")
    @classmethod
    def valid_hashtag(cls, value):
        try:
            return scraper.normalize_hashtag(value)
        except argparse.ArgumentTypeError as exc:
            raise ValueError(str(exc)) from exc


class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)


class BrowserAction(BaseModel):
    kind: Literal["click", "drag", "text", "key", "scroll"]
    points: list[Point] = Field(default_factory=list, max_length=80)
    text: str = Field(default="", max_length=2000)
    key: Literal["Enter", "Tab", "Backspace", "Escape", "select_all"] = "Enter"
    delta: int = Field(default=0, ge=-1200, le=1200)


class Stopped(Exception):
    pass


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
        self.directory = data_dir / self.id
        self.directory.mkdir(parents=True)
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
        self.records = []
        self.frame = b""
        self.action_error = ""
        self.thread = None

    def update(self, **values):
        with self.lock:
            for key, value in values.items():
                setattr(self, key, value)

    def snapshot(self):
        with self.lock:
            return {"id": self.id, "hashtag": self.settings.hashtag,
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


def perform_action(driver, action: BrowserAction):
    """Rejoue les gestes humains reçus ; aucun solveur de CAPTCHA ni JS utilisateur."""
    width, height = driver.execute_script("return [window.innerWidth, window.innerHeight];")
    chain = ActionChains(driver, duration=60)

    def move(point):
        chain.w3c_actions.pointer_action.move_to_location(
            min(width - 1, round(point.x * width)), min(height - 1, round(point.y * height)))

    if action.kind in {"click", "drag"}:
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
    try:
        while True:
            job.check()
            if time.monotonic() >= next_frame:
                job.update(frame=driver.get_screenshot_as_png())
                next_frame = time.monotonic() + 0.8
            try:
                command = job.commands.get(timeout=0.15)
            except queue.Empty:
                continue
            if command == "continue":
                if driver.execute_script(scraper.BLOCKED_JS):
                    job.update(action_error="TikTok affiche encore une vérification ou une connexion. Terminez-la dans l’image avant de continuer.")
                    continue
                break
            try:
                perform_action(driver, command)
                job.update(action_error="")
                next_frame = 0
            except (scraper.WebDriverException, ValueError):
                job.update(action_error="Ce geste n’a pas abouti. Attendez l’actualisation de l’image et réessayez.")
    finally:
        job.update(status=previous, frame=b"")
        while not job.commands.empty():
            try:
                job.commands.get_nowait()
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
    report = {"hashtag_url": f"https://www.tiktok.com/tag/{quote(args.hashtag)}"}
    driver = None
    final_status, final_message = "failed", "La collecte n’a pas pu aboutir."
    try:
        job.check()
        driver = driver_factory(args)
        job.update(status="discovering", message="Recherche des publications du hashtag…")
        interact = lambda message: wait_for_user(driver, job, message)
        links = scraper.collect_links(driver, args, report, interact=interact,
                                      progress=lambda count: job.update(discovered=count), check=job.check)
        job.update(status="collecting", discovered=len(links))
        for index, url in enumerate(links, 1):
            job.pause(args.delay)
            job.update(message=f"Lecture de la publication {index} sur {len(links)}…")
            try:
                record = scraper.read_post(driver, url, args, interact=interact, check=job.check)
                with job.lock:
                    if record["description"]:
                        job.records.append(record)
            except scraper.WebDriverException:
                with job.lock:
                    job.errors += 1
            job.update(processed=index)
            job.save()
        final_status = "partial" if job.errors else "completed"
        final_message = f"{len(job.records)} texte(s) collecté(s) sur {job.processed} publication(s) consultée(s)."
        if not job.records:
            final_message = "Aucun texte récupéré. TikTok peut limiter l’accès ou les publications peuvent être sans légende."
        elif len(links) < args.limit:
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
                if not job.busy and job.finished is not None and now - job.finished > self.retention:
                    self.jobs.pop(job.id)
                    shutil.rmtree(job.directory, ignore_errors=True)
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
        deadline = time.monotonic() + 25
        for job in jobs:
            if job.thread:
                job.thread.join(timeout=max(0, deadline - time.monotonic()))


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
        if request.method == "POST":
            # Les requêtes de mutation viennent uniquement de notre propre page.
            if request.headers.get("x-scraptiktok") != "1":
                return JSONResponse({"detail": "Requête non autorisée."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
        return response

    def owner(request):
        session = request.cookies.get(COOKIE, "")
        if len(session) != 64 or any(c not in "0123456789abcdef" for c in session):
            raise HTTPException(401, "Rechargez la page pour ouvrir une session.")
        return session

    @app.get("/healthz")
    def health():
        return {"status": "ok"}

    @app.get("/")
    def home(request: Request):
        response = FileResponse(scraper.BASE_DIR / "static" / "index.html")
        if not request.cookies.get(COOKIE):
            response.set_cookie(COOKIE, secrets.token_hex(32), httponly=True, samesite="strict",
                                secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=86400)
        return response

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
        if payload.kind in {"click", "drag"} and not payload.points:
            raise HTTPException(422, "Une position est requise.")
        enqueue(manager.get(owner(request), job_id), payload)
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
        filename = f"tiktok_{job.settings.hashtag}.txt"
        return Response(job.path.read_bytes(), media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})

    app.mount("/static", StaticFiles(directory=scraper.BASE_DIR / "static"), name="static")
    return app


app = create_app()
