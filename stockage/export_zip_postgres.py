"""Exporter une collecte PostgreSQL en archive ZIP portable.

L'archive conserve les fichiers CSV et JSON de toutes les publications
et commentaires. Elle n'est pas une sauvegarde physique de l'instance
PostgreSQL et ne contient pas les secrets de connexion.
"""
import io
import json
import re
from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED

from .postgres_consultation import (
    description_table, donnees_sauvegarde, empreinte, exporter_sauvegarde,
    ouvrir_connexion,
)


def construire_archive_postgres(cookie, type_sauvegarde, identifiant):
    """Produire un ZIP téléchargeable après contrôle du propriétaire."""
    parent, _, cle, _ = description_table(
        type_sauvegarde, "publications")
    # Ne jamais se contenter de la validation du nom reçu par le navigateur.
    with ouvrir_connexion() as connexion:
        with connexion.cursor() as curseur:
            curseur.execute(
                f"SELECT nom_sauvegarde FROM {parent} "
                f"WHERE {cle}=%s AND proprietaire_hash=%s",
                (identifiant, empreinte(cookie)))
            ligne = curseur.fetchone()
    if not ligne:
        raise ValueError("Collecte PostgreSQL introuvable.")

    nom = str(ligne[0] or "collecte")
    nom_fichier = re.sub(r"[^\w-]+", "_", nom).strip("_")[:80] or "collecte"
    archive = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    try:
        with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=5) as cible:
            cible.writestr("informations_export.json", json.dumps({
                "format": "scraptiktok-postgres-export-v1",
                "source": "PostgreSQL",
                "type_collecte": type_sauvegarde,
                "identifiant": identifiant,
                "nom_collecte": nom,
                "description": (
                    "Export logique CSV/JSON des données de la collecte ; "
                    "ce ZIP n'est pas une sauvegarde physique PostgreSQL."
                ),
            }, ensure_ascii=False, indent=2))
            for categorie in ("publications", "commentaires"):
                for format_ in ("csv", "json"):
                    nom_interne = f"{categorie}.{format_}"
                    with cible.open(nom_interne, "w") as sortie:
                        for morceau in exporter_sauvegarde(
                                cookie, type_sauvegarde, identifiant,
                                categorie, format_):
                            sortie.write(morceau.encode("utf-8"))
        archive.seek(0)
        return archive, nom_fichier + ".zip"
    except Exception:
        archive.close()
        raise
