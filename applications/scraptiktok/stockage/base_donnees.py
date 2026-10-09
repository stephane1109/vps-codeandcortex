"""SQLite : instantanés cloisonnés par session, transactions et clés étrangères."""
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path

class BaseDonnees:
    def __init__(self, chemin):
        self.chemin = Path(chemin); self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self.connexion() as base:
            base.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, proprietaire TEXT NOT NULL, cree_le TEXT NOT NULL, statut TEXT NOT NULL, parametres TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS publications(session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE, id TEXT, donnees TEXT NOT NULL, PRIMARY KEY(session_id,id));
            CREATE TABLE IF NOT EXISTS commentaires(session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE, id TEXT, publication_id TEXT, donnees TEXT NOT NULL, PRIMARY KEY(session_id,id));
            CREATE TABLE IF NOT EXISTS evenements(numero INTEGER PRIMARY KEY, session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE, date TEXT, donnees TEXT);
            CREATE TABLE IF NOT EXISTS cache_video(cle TEXT PRIMARY KEY, donnees TEXT NOT NULL, cree_le TEXT NOT NULL);
            PRAGMA user_version=1;
            """)

    @contextmanager
    def connexion(self):
        base = sqlite3.connect(self.chemin, timeout=15)
        base.execute("PRAGMA foreign_keys=ON")
        try:
            with base: yield base
        finally:
            base.close()

    def creer_session(self, identifiant, proprietaire, date, parametres):
        with self.connexion() as base:
            base.execute("INSERT OR IGNORE INTO sessions VALUES(?,?,?,?,?)", (identifiant, proprietaire, date, "en_cours", json.dumps(parametres, ensure_ascii=False)))

    def enregistrer(self, session, publications, commentaires):
        with self.connexion() as base:
            base.executemany("INSERT OR REPLACE INTO publications VALUES(?,?,?)", [(session,p["id"],json.dumps(p,ensure_ascii=False,allow_nan=False)) for p in publications])
            base.executemany("INSERT OR REPLACE INTO commentaires VALUES(?,?,?,?)", [(session,c["id"],c["publication_id"],json.dumps(c,ensure_ascii=False,allow_nan=False)) for c in commentaires])

    def contient_publication(self, session, identifiant):
        with self.connexion() as base:
            return base.execute("SELECT 1 FROM publications WHERE session_id=? AND id=?", (session,identifiant)).fetchone() is not None

    def terminer_session(self, session, statut):
        with self.connexion() as base: base.execute("UPDATE sessions SET statut=? WHERE id=?", (statut,session))

    def supprimer_session(self, session):
        with self.connexion() as base: base.execute("DELETE FROM sessions WHERE id=?", (session,))
