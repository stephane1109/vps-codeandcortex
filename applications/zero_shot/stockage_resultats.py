"""Sauvegarde progressive des classifications dans un volume SQLite persistant."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def chemin_base() -> str:
    """Déterminer le chemin de stockage persistant hors du répertoire Git."""
    return os.getenv("ZERO_SHOT_BASE", "/data/resultats_zero_shot.sqlite3")


def initialiser_base(chemin: str | None = None) -> str:
    """Préparer la base sans effacer les analyses déjà présentes."""
    chemin = chemin or chemin_base()
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(chemin, timeout=30) as connexion:
        connexion.execute("""
            CREATE TABLE IF NOT EXISTS resultats (
                cle_analyse TEXT NOT NULL,
                numero_document INTEGER NOT NULL,
                statut TEXT NOT NULL,
                contenu_json TEXT NOT NULL,
                maj_utc TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (cle_analyse, numero_document)
            )
        """)
        connexion.commit()
    return chemin


def enregistrer_resultat(
    cle_analyse: str,
    numero_document: int,
    statut: str,
    resultat: dict[str, Any],
    chemin: str | None = None,
) -> None:
    """Enregistrer une unité après chaque inférence afin de permettre la reprise."""
    chemin = initialiser_base(chemin)
    with sqlite3.connect(chemin, timeout=30) as connexion:
        connexion.execute("""
            INSERT INTO resultats (cle_analyse, numero_document, statut, contenu_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(cle_analyse, numero_document) DO UPDATE SET
                statut = excluded.statut,
                contenu_json = excluded.contenu_json,
                maj_utc = CURRENT_TIMESTAMP
        """, (
            cle_analyse,
            int(numero_document),
            statut,
            json.dumps(resultat, ensure_ascii=False),
        ))
        connexion.commit()


def recuperer_resultats(
    cle_analyse: str, chemin: str | None = None,
) -> dict[int, dict[str, Any]]:
    """Recharger les résultats d'une précédente exécution du même paramétrage."""
    chemin = initialiser_base(chemin)
    with sqlite3.connect(chemin, timeout=30) as connexion:
        lignes = connexion.execute("""
            SELECT numero_document, statut, contenu_json FROM resultats
            WHERE cle_analyse = ? ORDER BY numero_document
        """, (cle_analyse,)).fetchall()
    return {
        int(numero): {"statut_analyse": statut, **json.loads(contenu)}
        for numero, statut, contenu in lignes
    }
