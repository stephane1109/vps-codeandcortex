"""Sauvegarde persistante des corpus, paramètres et annotations Qwen.

Les résultats sont enregistrés dans SQLite après chaque unité textuelle.
La base se trouve dans un volume Docker distinct du conteneur Streamlit.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


class FichierRestaure:
    """Reproduire l'interface minimale des fichiers téléversés dans Streamlit."""

    def __init__(self, nom: str, contenu: bytes) -> None:
        self.name = nom
        self._contenu = contenu

    def getvalue(self) -> bytes:
        """Restituer les octets originaux, sans changer leur encodage."""
        return self._contenu


def chemin_base() -> Path:
    """Localiser le volume persistant du VPS."""
    repertoire = Path(
        os.getenv("QWEN_DATA_DIR", "/data/analyses_qwen")
    )
    repertoire.mkdir(parents=True, exist_ok=True, mode=0o700)
    return repertoire / "analyses.sqlite3"


@contextmanager
def ouvrir_base():
    """Fermer la connexion après chaque transaction, succès comme erreur."""
    chemin = chemin_base()
    connexion = sqlite3.connect(str(chemin), timeout=30)
    try:
        connexion.execute("PRAGMA busy_timeout = 30000")
        connexion.execute("PRAGMA journal_mode = WAL")
        connexion.execute("PRAGMA synchronous = FULL")
        connexion.execute("PRAGMA foreign_keys = ON")
        connexion.executescript(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                cle TEXT PRIMARY KEY,
                cree_le TEXT NOT NULL,
                modifie_le TEXT NOT NULL,
                parametres_json TEXT NOT NULL,
                widgets_json TEXT NOT NULL,
                nombre_textes INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS fichiers (
                cle TEXT NOT NULL,
                position INTEGER NOT NULL,
                nom TEXT NOT NULL,
                contenu_compresse BLOB NOT NULL,
                PRIMARY KEY (cle, position),
                FOREIGN KEY (cle) REFERENCES analyses(cle) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS resultats (
                cle TEXT NOT NULL,
                numero_document INTEGER NOT NULL,
                informations_json TEXT NOT NULL,
                modifie_le TEXT NOT NULL,
                PRIMARY KEY (cle, numero_document),
                FOREIGN KEY (cle) REFERENCES analyses(cle) ON DELETE CASCADE
            );
            """
        )
        if chemin.exists():
            try:
                chemin.chmod(0o600)
            except OSError:
                pass
        yield connexion
        connexion.commit()
    except BaseException:
        connexion.rollback()
        raise
    finally:
        connexion.close()


def horodatage() -> str:
    """Produire un horodatage UTC explicite."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normaliser_valeur(valeur: Any) -> Any:
    """Convertir les valeurs pandas en JSON sans perdre les absences."""
    if valeur is None:
        return None
    if isinstance(valeur, (str, bytes)):
        return valeur.decode("utf-8", errors="replace") if isinstance(
            valeur, bytes
        ) else valeur
    try:
        if pd.isna(valeur):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(valeur, "item"):
        valeur = valeur.item()
    if isinstance(valeur, (bool, int)):
        return valeur
    if isinstance(valeur, float):
        return valeur if math.isfinite(valeur) else None
    if isinstance(valeur, (list, tuple)):
        return [normaliser_valeur(v) for v in valeur]
    if isinstance(valeur, dict):
        return {str(cle): normaliser_valeur(v) for cle, v in valeur.items()}
    return str(valeur)


def enregistrer_analyse(
    cle: str,
    parametres: dict[str, Any],
    widgets: dict[str, Any],
    fichiers: list[Any],
    nombre_textes: int,
) -> None:
    """Conserver une analyse et les fichiers source avant la première inférence."""
    if not cle or not fichiers:
        raise ValueError("Une analyse persistante nécessite une clé et des fichiers.")
    maintenant = horodatage()
    with ouvrir_base() as connexion:
        existante = connexion.execute(
            "SELECT 1 FROM analyses WHERE cle = ?", (cle,)
        ).fetchone()
        if existante:
            connexion.execute(
                """
                UPDATE analyses SET modifie_le = ?, parametres_json = ?,
                    widgets_json = ?, nombre_textes = ?
                WHERE cle = ?
                """,
                (
                    maintenant,
                    json.dumps(normaliser_valeur(parametres), ensure_ascii=False),
                    json.dumps(normaliser_valeur(widgets), ensure_ascii=False),
                    int(nombre_textes), cle,
                ),
            )
        else:
            connexion.execute(
                """
                INSERT INTO analyses (
                    cle, cree_le, modifie_le, parametres_json,
                    widgets_json, nombre_textes
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cle, maintenant, maintenant,
                    json.dumps(normaliser_valeur(parametres), ensure_ascii=False),
                    json.dumps(normaliser_valeur(widgets), ensure_ascii=False),
                    int(nombre_textes),
                ),
            )
        for position, fichier in enumerate(fichiers):
            # Les sources ne sont réécrites que lors de la première sauvegarde.
            deja_present = connexion.execute(
                "SELECT 1 FROM fichiers WHERE cle = ? AND position = ?",
                (cle, position),
            ).fetchone()
            if not deja_present:
                connexion.execute(
                    """
                    INSERT INTO fichiers (
                        cle, position, nom, contenu_compresse
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        cle, position, str(fichier.name),
                        sqlite3.Binary(zlib.compress(fichier.getvalue(), level=3)),
                    ),
                )


CHAMPS_RESULTATS = frozenset({
    "statut_codage", "erreur_codage", "reponse_qwen", "mode_analyse",
    "texte_tronque", "contexte_tronque",
    "nombre_segments", "segments_traites", "justification",
    "incertitude_interpretation", "probabilite_incertitude",
    "validation_humaine", "note_humaine",
})
PREFIXES_RESULTATS = (
    "theme_", "manuel_theme_", "final_theme_", "indice_theme_",
    "probabilite_theme_", "similarite_theme_", "nli_",
)


def extraire_resultat(ligne: pd.Series) -> dict[str, Any]:
    """Extraire uniquement les calculs, sans recopier toutes les métadonnées."""
    return {
        str(champ): normaliser_valeur(valeur)
        for champ, valeur in ligne.items()
        if champ in CHAMPS_RESULTATS
        or str(champ).startswith(PREFIXES_RESULTATS)
    }


def enregistrer_resultat(
    cle: str, numero_document: int, ligne: pd.Series
) -> None:
    """Valider sur disque chaque annotation avant de passer à la suivante."""
    if not cle:
        return
    maintenant = horodatage()
    informations = extraire_resultat(ligne)
    with ouvrir_base() as connexion:
        connexion.execute(
            """
            INSERT INTO resultats (
                cle, numero_document, informations_json, modifie_le
            ) VALUES (?, ?, ?, ?)
            ON CONFLICT(cle, numero_document) DO UPDATE SET
                informations_json = excluded.informations_json,
                modifie_le = excluded.modifie_le
            """,
            (
                cle, int(numero_document),
                json.dumps(informations, ensure_ascii=False),
                maintenant,
            ),
        )
        connexion.execute(
            "UPDATE analyses SET modifie_le = ? WHERE cle = ?",
            (maintenant, cle),
        )


def lister_analyses() -> list[dict[str, Any]]:
    """Lister les travaux récupérables sans charger les corpus en mémoire."""
    chemin = chemin_base()
    if not chemin.exists():
        return []
    with ouvrir_base() as connexion:
        lignes = connexion.execute(
            """
            SELECT a.cle, a.modifie_le, a.parametres_json, a.nombre_textes,
                COUNT(r.numero_document)
            FROM analyses a
            LEFT JOIN resultats r ON r.cle = a.cle
            GROUP BY a.cle
            ORDER BY a.modifie_le DESC
            """
        ).fetchall()
    return [
        {
            "cle": cle,
            "modifie_le": modifie,
            "modele": json.loads(parametres).get("modele", ""),
            "nombre_textes": nombre,
            "nombre_sauvegardes": compte,
        }
        for cle, modifie, parametres, nombre, compte in lignes
    ]


def charger_analyse(cle: str) -> dict[str, Any]:
    """Restituer fichiers et choix de l'utilisateur, sans désérialiser du pickle."""
    with ouvrir_base() as connexion:
        ligne = connexion.execute(
            """
            SELECT parametres_json, widgets_json, nombre_textes
            FROM analyses WHERE cle = ?
            """,
            (cle,),
        ).fetchone()
        if ligne is None:
            raise ValueError("La sauvegarde demandée est introuvable.")
        fichiers = connexion.execute(
            """
            SELECT nom, contenu_compresse FROM fichiers
            WHERE cle = ? ORDER BY position
            """,
            (cle,),
        ).fetchall()
    if not fichiers:
        raise ValueError("La sauvegarde ne contient pas les fichiers source.")
    return {
        "cle": cle,
        "parametres": json.loads(ligne[0]),
        "widgets": json.loads(ligne[1]),
        "nombre_textes": ligne[2],
        "fichiers": [
            FichierRestaure(nom, zlib.decompress(contenu))
            for nom, contenu in fichiers
        ],
    }


def restaurer_resultats(
    donnees: pd.DataFrame, cle: str
) -> tuple[pd.DataFrame, int]:
    """Réappliquer les seuls résultats de la clé, en conservant le corpus source."""
    with ouvrir_base() as connexion:
        lignes = connexion.execute(
            """
            SELECT numero_document, informations_json
            FROM resultats WHERE cle = ?
            """,
            (cle,),
        ).fetchall()
    if not lignes:
        return donnees, 0
    restauration = donnees.copy()
    correspondances = {
        int(numero): indice
        for indice, numero in restauration["numero_document"].items()
    }
    nombre = 0
    for numero, informations_json in lignes:
        indice = correspondances.get(int(numero))
        if indice is None:
            continue
        informations = json.loads(informations_json)
        for champ, valeur in informations.items():
            if champ not in restauration.columns:
                restauration[champ] = pd.Series(
                    [None] * len(restauration),
                    index=restauration.index, dtype="object",
                )
            restauration.at[indice, champ] = pd.NA if valeur is None else valeur
        nombre += 1
    return restauration, nombre
