"""Historique SQLite privé, 30 jours, pour les collectes et analyses ScratchTikTok.

Copies de résultats sans fichiers MP4. Le cookie propriétaire (90 jours) est
distinct du cookie d'exécution (24 h) : une session expirée ne rend pas
l'historique inaccessible. Le conteneur exige un volume persistant /app/data.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import time
from zipfile import ZipFile, ZIP_DEFLATED

DOSSIER = "historique_analyses"
COOKIE = "scraptiktok_historique"
IDENTIFIANT = re.compile(r"[a-f0-9]{32}\Z")
SUFFIXES = {".txt", ".json", ".csv", ".png", ".html", ".htm", ".svg", ".log",
            ".gexf", ".graphml", ".pdf", ".md"}
EXCLUS = {"videos", "__pycache__"}
RETENTION_DEFAUT = 30


def retention_jours():
    try:
        return max(1, min(365, int(os.getenv("SCRAPTIKTOK_ANALYSIS_RETENTION_DAYS", "30"))))
    except ValueError:
        return RETENTION_DEFAUT


def empreinte(cookie):
    return hashlib.sha256(cookie.encode("utf-8")).hexdigest()


def racine(data_dir):
    rep = Path(data_dir) / DOSSIER
    rep.mkdir(parents=True, exist_ok=True)
    return rep


def chemin(data_dir, identifiant):
    if not IDENTIFIANT.fullmatch(str(identifiant)):
        raise ValueError("Identifiant d'analyse invalide.")
    return racine(data_dir) / identifiant


def base(data_dir):
    racine(data_dir)
    db = sqlite3.connect(Path(data_dir) / "historique-analyses.sqlite3", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("""CREATE TABLE IF NOT EXISTS analyses (
        id TEXT PRIMARY KEY, proprietaire TEXT NOT NULL,
        titre TEXT NOT NULL, statut TEXT NOT NULL,
        cree_le INTEGER NOT NULL, actualise_le INTEGER NOT NULL,
        expire_le INTEGER NOT NULL)""")
    db.execute("CREATE INDEX IF NOT EXISTS analyses_owner ON analyses(proprietaire, actualise_le DESC)")
    return db


def purger(data_dir):
    maintenant = int(time.time())
    with base(data_dir) as db:
        expirations = db.execute("SELECT id FROM analyses WHERE expire_le<=?", (maintenant,)).fetchall()
        db.executemany("DELETE FROM analyses WHERE id=?", [(v["id"],) for v in expirations])
    for v in expirations:
        destination = chemin(data_dir, v["id"])
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination, ignore_errors=True)


def enregistrer(job, owner_cookie):
    """Copier uniquement des artefacts, en remplaçant les fichiers atomiquement.

    Les vidéos et les archives avec MP4 ne sont jamais dupliquées.
    """
    if not IDENTIFIANT.fullmatch(str(job.id)) or not owner_cookie or getattr(job, "historique", False):
        return
    source = Path(job.directory).resolve()
    destination = chemin(job.racine, job.id)
    destination.mkdir(parents=True, exist_ok=True)
    for dossier, dossiers, fichiers in os.walk(source):
        dossiers[:] = [d for d in dossiers if d not in EXCLUS
                       and not d.startswith("desordre_sources_") and not (Path(dossier) / d).is_symlink()]
        for nom in fichiers:
            original = Path(dossier) / nom
            if original.is_symlink() or original.suffix.lower() not in SUFFIXES:
                continue
            relatif = original.relative_to(source)
            cible = destination / relatif
            cible.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=cible.parent, prefix=".historique_", delete=False) as flux:
                temporaire = Path(flux.name)
            try:
                with original.open("rb") as entree, temporaire.open("wb") as sortie:
                    shutil.copyfileobj(entree, sortie, length=1024*1024)
                os.replace(temporaire, cible)
            finally:
                temporaire.unlink(missing_ok=True)
    maintenant = int(time.time())
    manifeste = {"id": job.id, "parametres": job.settings.model_dump(),
                 "statut": job.status, "traites": job.processed,
                 "legendes": len(job.records), "publications": len(job.publications)}
    (destination / "parametres_historique.json").write_text(
        json.dumps(manifeste, ensure_ascii=False), encoding="utf-8")
    # L'index est mis à jour en dernier, une fois les fichiers copiés.
    with base(job.racine) as db:
        db.execute("""INSERT INTO analyses(id,proprietaire,titre,statut,cree_le,actualise_le,expire_le)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET titre=excluded.titre, statut=excluded.statut,
                actualise_le=excluded.actualise_le, expire_le=excluded.expire_le""",
            (job.id, empreinte(owner_cookie), job.settings.libelle[:160], job.status,
             maintenant, maintenant, maintenant + retention_jours()*86400))


def lister(data_dir, cookie):
    if not cookie:
        return []
    purger(data_dir)
    with base(data_dir) as db:
        rows = db.execute(
            "SELECT id,titre,statut,cree_le,actualise_le,expire_le FROM analyses "
            "WHERE proprietaire=? ORDER BY actualise_le DESC",
            (empreinte(cookie),)).fetchall()
        return [dict(row) for row in rows]


def retrouver(data_dir, identifiant, cookie):
    if not cookie or not IDENTIFIANT.fullmatch(str(identifiant)):
        return None
    purger(data_dir)
    with base(data_dir) as db:
        row = db.execute(
            "SELECT id,titre,statut FROM analyses WHERE id=? AND proprietaire=?",
            (identifiant, empreinte(cookie))).fetchone()
    if row is None:
        return None
    dossier = chemin(data_dir, identifiant)
    manifeste = dossier / "parametres_historique.json"
    if not manifeste.is_file() or manifeste.is_symlink():
        return None
    try:
        params = json.loads(manifeste.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dict(row), dossier, params


def exporter_zip(dossier):
    """Reconstruire une archive des résultats sans MP4, accessible depuis l'historique."""
    from io import BytesIO
    flux = BytesIO()
    with ZipFile(flux, "w", compression=ZIP_DEFLATED, compresslevel=5) as zipf:
        for fichier in Path(dossier).rglob("*"):
            if fichier.is_file() and not fichier.is_symlink() and fichier.suffix.lower() in SUFFIXES:
                zipf.write(fichier, fichier.relative_to(dossier).as_posix())
    flux.seek(0)
    return flux
