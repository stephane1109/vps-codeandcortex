"""Archivage PostgreSQL facultatif des programmes Research.

Le corpus SQLite demeure la source de vérité pour la reprise, les exports
et le quota local. PostgreSQL stocke les publications et commentaires
dédoublonnés, sans identifiants de l'API TikTok.
"""
import json
import logging
import os
from .collectes_research import connexion, maintenant

JOURNAL = logging.getLogger(__name__)


def synchroniser_plan(dossier, identifiant, *, exiger_configuration=False):
    """Répliquer les données d'un programme avec une opération rejouable."""
    adresse = os.getenv("RESEARCH_POSTGRES_DSN", "").strip()
    if not adresse:
        if exiger_configuration:
            raise RuntimeError("Renseignez RESEARCH_POSTGRES_DSN dans Coolify.")
        return {"statut": "desactive", "publications": 0, "commentaires": 0}
    try:
        import psycopg
        from psycopg.types.json import Jsonb
        with connexion(dossier) as source:
            plan = source.execute(
                "SELECT id,proprietaire,nom_sauvegarde,statut,debut_corpus,fin_corpus,"
                "debut_execution,fin_execution FROM plans WHERE id=?",
                (identifiant,)).fetchone()
            if plan is None:
                raise RuntimeError("Programme Research introuvable.")
            publications = source.execute(
                "SELECT id,retenue,donnees,premiere_collecte,derniere_collecte "
                "FROM publications WHERE plan_id=?", (identifiant,)).fetchall()
            commentaires = source.execute(
                "SELECT id,publication_id,donnees,collecte_le "
                "FROM commentaires WHERE plan_id=?", (identifiant,)).fetchall()
            with psycopg.connect(adresse, connect_timeout=10) as destination:
                with destination.cursor() as curseur:
                    curseur.execute("""
                        CREATE TABLE IF NOT EXISTS research_plans (
                            plan_id TEXT PRIMARY KEY,
                            proprietaire_hash TEXT NOT NULL,
                            nom_sauvegarde TEXT NOT NULL DEFAULT '',
                            statut TEXT NOT NULL,
                            debut_corpus DATE NOT NULL,
                            fin_corpus DATE NOT NULL,
                            debut_execution DATE NOT NULL,
                            fin_execution DATE NOT NULL,
                            synchronise_le TIMESTAMPTZ NOT NULL
                        )""")
                    curseur.execute(
                        "ALTER TABLE research_plans ADD COLUMN IF NOT EXISTS "
                        "nom_sauvegarde TEXT NOT NULL DEFAULT ''")
                    curseur.execute("""
                        CREATE TABLE IF NOT EXISTS research_publications (
                            plan_id TEXT NOT NULL REFERENCES research_plans(plan_id)
                                ON DELETE CASCADE,
                            publication_id TEXT NOT NULL,
                            retenue BOOLEAN NOT NULL,
                            donnees JSONB NOT NULL,
                            premiere_collecte TIMESTAMPTZ NOT NULL,
                            derniere_collecte TIMESTAMPTZ NOT NULL,
                            PRIMARY KEY(plan_id,publication_id)
                        )""")
                    curseur.execute("""
                        CREATE TABLE IF NOT EXISTS research_commentaires (
                            plan_id TEXT NOT NULL REFERENCES research_plans(plan_id)
                                ON DELETE CASCADE,
                            commentaire_id TEXT NOT NULL,
                            publication_id TEXT NOT NULL,
                            donnees JSONB NOT NULL,
                            collecte_le TIMESTAMPTZ NOT NULL,
                            PRIMARY KEY(plan_id,commentaire_id)
                        )""")
                    curseur.execute(
                        "CREATE INDEX IF NOT EXISTS idx_research_commentaires_video "
                        "ON research_commentaires(plan_id,publication_id)")
                    curseur.execute("""
                        INSERT INTO research_plans (
                            plan_id,proprietaire_hash,nom_sauvegarde,statut,debut_corpus,fin_corpus,
                            debut_execution,fin_execution,synchronise_le)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT(plan_id) DO UPDATE SET
                            nom_sauvegarde=EXCLUDED.nom_sauvegarde,
                            statut=EXCLUDED.statut,
                            synchronise_le=EXCLUDED.synchronise_le
                    """, (plan["id"], plan["proprietaire"], plan["nom_sauvegarde"],
                          plan["statut"], plan["debut_corpus"], plan["fin_corpus"],
                          plan["debut_execution"], plan["fin_execution"], maintenant()))
                    for item in publications:
                        curseur.execute("""
                            INSERT INTO research_publications (
                                plan_id,publication_id,retenue,donnees,
                                premiere_collecte,derniere_collecte)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT(plan_id,publication_id) DO UPDATE SET
                                retenue=EXCLUDED.retenue,
                                donnees=EXCLUDED.donnees,
                                premiere_collecte=LEAST(
                                    research_publications.premiere_collecte,
                                    EXCLUDED.premiere_collecte),
                                derniere_collecte=GREATEST(
                                    research_publications.derniere_collecte,
                                    EXCLUDED.derniere_collecte)
                        """, (identifiant, item["id"], bool(item["retenue"]),
                              Jsonb(json.loads(item["donnees"])),
                              item["premiere_collecte"], item["derniere_collecte"]))
                    for item in commentaires:
                        curseur.execute("""
                            INSERT INTO research_commentaires (
                                plan_id,commentaire_id,publication_id,donnees,collecte_le)
                            VALUES (%s,%s,%s,%s,%s)
                            ON CONFLICT(plan_id,commentaire_id) DO UPDATE SET
                                publication_id=EXCLUDED.publication_id,
                                donnees=EXCLUDED.donnees,
                                collecte_le=GREATEST(
                                    research_commentaires.collecte_le,
                                    EXCLUDED.collecte_le)
                        """, (identifiant, item["id"], item["publication_id"],
                              Jsonb(json.loads(item["donnees"])), item["collecte_le"]))
        return {"statut": "synchronise", "publications": len(publications),
                "commentaires": len(commentaires)}
    except Exception as erreur:
        # L'URL PostgreSQL et le contenu des données ne doivent jamais
        # apparaître dans les diagnostics exposés à l'utilisateur.
        JOURNAL.warning("Archivage PostgreSQL Research : %s", type(erreur).__name__)
        if exiger_configuration:
            raise RuntimeError(
                "Synchronisation PostgreSQL impossible : vérifiez "
                "la connexion et les droits de la base dans Coolify.") from None
        return {"statut": "erreur", "publications": 0, "commentaires": 0}
