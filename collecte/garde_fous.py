"""Quotas d'utilisation partagés par tous les utilisateurs de ScrapTikTok.

L'API web interne de TikTok n'a pas de quota officiel publié. Ces limites sont
des garde-fous locaux de l'application et non des seuils TikTok connus.
SQLite est sur le volume persistant /app/data, donc partagé entre sessions et
redémarrages. Aucun cookie, compte ou IP n'est enregistré en clair.
"""
import hashlib
import os
from pathlib import Path
import sqlite3
import time


class QuotaLocalDepasse(RuntimeError):
    pass


def entier_env(nom, valeur, minimum=1, maximum=100000):
    try:
        n = int(os.getenv(nom, str(valeur)))
    except (TypeError, ValueError):
        n = valeur
    return max(minimum, min(maximum, n))


def plafond_par_source():
    return entier_env("SCRAPTIKTOK_MAX_POSTS_PER_SOURCE",50,1,1000)


def plafond_sources():
    return entier_env("SCRAPTIKTOK_MAX_SOURCES_PER_JOB",3,1,29)


def plafond_total():
    return entier_env("SCRAPTIKTOK_MAX_POSTS_PER_JOB",150,1,1000)


def plafond_commentaires():
    return entier_env("SCRAPTIKTOK_MAX_COMMENTS_PER_POST",20,1,500)


def duree_job():
    return entier_env("JOB_TIMEOUT_SECONDS",900,60,7200)


def reglages():
    return {
        "max_posts_source":plafond_par_source(),
        "max_sources_job":plafond_sources(),
        "max_posts_job":plafond_total(),
        "max_comments_post":plafond_commentaires(),
        "max_job_seconds":duree_job(),
        "max_jobs_day":entier_env("SCRAPTIKTOK_MAX_JOBS_PER_DAY",8,1,500),
        "api_hour":entier_env("SCRAPTIKTOK_API_REQUESTS_PER_HOUR",30,1,10000),
        "api_day":entier_env("SCRAPTIKTOK_API_REQUESTS_PER_DAY",100,1,100000),
        "api_gap_seconds":entier_env("SCRAPTIKTOK_API_GAP_SECONDS",5,1,120),
        "nature":"plafonds_locaux_non_officiels",
    }


def _connexion(data_dir):
    racine=Path(data_dir)
    racine.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(racine/"scraptiktok_usage.sqlite", timeout=15,
                       isolation_level=None)
    db.execute("PRAGMA busy_timeout=15000")
    db.execute("""CREATE TABLE IF NOT EXISTS usage_jobs (
        job_id TEXT PRIMARY KEY, lance_le INTEGER NOT NULL, session_hash TEXT NOT NULL,
        mode TEXT NOT NULL, nb_sources INTEGER NOT NULL, limite_source INTEGER NOT NULL,
        termine_le INTEGER, statut TEXT, traites INTEGER DEFAULT 0)""")
    db.execute("""CREATE INDEX IF NOT EXISTS idx_usage_jobs_debut
                  ON usage_jobs(lance_le)""")
    db.execute("""CREATE TABLE IF NOT EXISTS usage_http (
        id INTEGER PRIMARY KEY, reserve_pour REAL NOT NULL)""")
    db.execute("""CREATE INDEX IF NOT EXISTS idx_usage_http_time
                  ON usage_http(reserve_pour)""")
    return db


def demarrer_job(data_dir, job_id, owner, mode, nb_sources, limite_source, *, maintenant=None):
    """Bloquer la neuvième collecte quotidienne, tous utilisateurs confondus."""
    maintenant=int(time.time() if maintenant is None else maintenant)
    plafond=reglages()["max_jobs_day"]
    empreinte=hashlib.sha256(owner.encode("utf-8")).hexdigest()[:16]
    db=_connexion(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM usage_jobs WHERE lance_le < ?",(maintenant-30*86400,))
        n=db.execute("SELECT COUNT(*) FROM usage_jobs WHERE lance_le>=?",
                     (maintenant-86400,)).fetchone()[0]
        if n>=plafond:
            db.execute("ROLLBACK")
            raise QuotaLocalDepasse(
                f"Plafond de sécurité ScrapTikTok : {plafond} collectes "
                "maximum sur 24 heures pour l'ensemble de l'application.")
        db.execute("""INSERT INTO usage_jobs
            (job_id,lance_le,session_hash,mode,nb_sources,limite_source)
            VALUES (?,?,?,?,?,?)""",
            (job_id,maintenant,empreinte,mode,nb_sources,limite_source))
        db.execute("COMMIT")
    finally:
        db.close()


def terminer_job(data_dir, job_id, statut, traites, *, maintenant=None):
    maintenant=int(time.time() if maintenant is None else maintenant)
    db=_connexion(data_dir)
    try:
        db.execute("""UPDATE usage_jobs SET termine_le=?,statut=?,traites=?
                      WHERE job_id=?""",(maintenant,statut,int(traites),job_id))
    finally:
        db.close()


def reserver_requete_api(data_dir, *, maintenant=None):
    """Réserver un appel HTTP TikTok avec intervalles/quotas globaux.

    La réservation précède l'appel HTTP et est conservée même si TikTok répond
    429. Le délai est une temporisation client, pas un contournement du serveur.
    """
    maintenant=float(time.time() if maintenant is None else maintenant)
    cfg=reglages()
    db=_connexion(data_dir)
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM usage_http WHERE reserve_pour < ?",(maintenant-86400,))
        heure=db.execute("SELECT COUNT(*) FROM usage_http WHERE reserve_pour>?",
                         (maintenant-3600,)).fetchone()[0]
        jour=db.execute("SELECT COUNT(*) FROM usage_http WHERE reserve_pour>?",
                        (maintenant-86400,)).fetchone()[0]
        if heure>=cfg["api_hour"] or jour>=cfg["api_day"]:
            db.execute("ROLLBACK")
            raise QuotaLocalDepasse(
                f"Quota de précaution API ScrapTikTok atteint : "
                f"{cfg['api_hour']} requêtes/heure ou {cfg['api_day']}/24 h. "
                "Aucune nouvelle requête API n'a été envoyée à TikTok.")
        dernier=db.execute("SELECT MAX(reserve_pour) FROM usage_http").fetchone()[0]
        reservation=max(maintenant, (dernier or 0)+cfg["api_gap_seconds"])
        db.execute("INSERT INTO usage_http(reserve_pour) VALUES (?)",(reservation,))
        db.execute("COMMIT")
        return max(0.0,reservation-maintenant)
    finally:
        db.close()


def utilisation(data_dir, *, maintenant=None):
    maintenant=int(time.time() if maintenant is None else maintenant)
    cfg=reglages()
    db=_connexion(data_dir)
    try:
        return {**cfg,
            "jobs_last_24h":db.execute(
                "SELECT COUNT(*) FROM usage_jobs WHERE lance_le>?",
                (maintenant-86400,)).fetchone()[0],
            "api_last_hour":db.execute(
                "SELECT COUNT(*) FROM usage_http WHERE reserve_pour>?",
                (maintenant-3600,)).fetchone()[0],
            "api_last_24h":db.execute(
                "SELECT COUNT(*) FROM usage_http WHERE reserve_pour>?",
                (maintenant-86400,)).fetchone()[0],
        }
    finally:
        db.close()
