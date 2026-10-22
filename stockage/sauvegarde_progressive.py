"""Points de récupération optionnels, consultables après redémarrage de l'application.

Un seul ZIP par collecte est remplacé atomiquement, indépendamment des sessions
éphémères nettoyées par le Manager. La propriété est vérifiée via le hash du
cookie privé ; le cookie lui-même n'est jamais enregistré.
"""
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import hmac
import json
import os
import re
import tempfile
import time
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

DOSSIER = "sauvegardes_collectes"
IDENTIFIANT = re.compile(r"[0-9a-f]{32}\Z")


def _racine(dossier_donnees):
    return Path(dossier_donnees) / DOSSIER


def _nom_fichier(dossier_donnees, identifiant):
    if not IDENTIFIANT.fullmatch(str(identifiant)):
        raise ValueError("Identifiant de collecte invalide.")
    return _racine(dossier_donnees) / f"{identifiant}.zip"


def enregistrer_point(dossier_donnees, identifiant, proprietaire, etat, textes,
                     publications, retenues, commentaires):
    """Sauvegarder TXT, données enrichies et métadonnées en un ZIP atomique.

    Les MP4 ne sont pas copiés ; la sauvegarde ne constitue pas une reprise
    automatique du navigateur Selenium et n'allonge pas la vie de la session.
    """
    cible = _nom_fichier(dossier_donnees, identifiant)
    cible.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifeste = {
        "id": identifiant,
        "proprietaire_empreinte": sha256(proprietaire.encode("utf-8")).hexdigest(),
        "sauvegarde_le": datetime.now(timezone.utc).isoformat(),
        "traitees": int(etat.get("traitees", 0)),
        "retenues": len(retenues),
        "publications": len(publications),
        "commentaires": len(commentaires),
        "statut": str(etat.get("statut") or "en_cours"),
        "source": str(etat.get("source") or ""),
    }
    descripteurs = {
        "textes.txt": textes,
        "publications.json": json.dumps(publications, ensure_ascii=False, allow_nan=False),
        "retenues.json": json.dumps(retenues, ensure_ascii=False, allow_nan=False),
        "commentaires.json": json.dumps(commentaires, ensure_ascii=False, allow_nan=False),
        "etat.json": json.dumps({k:v for k,v in manifeste.items() if k!="proprietaire_empreinte"},
                              ensure_ascii=False),
    }
    # La création se déroule dans le même dossier, évitant tout ZIP tronqué visible.
    with tempfile.NamedTemporaryFile(dir=cible.parent, prefix=".sauvegarde_",
                                     suffix=".tmp", delete=False) as flux:
        temporaire = Path(flux.name)
    try:
        with ZipFile(temporaire, "w", compression=ZIP_DEFLATED, compresslevel=5) as archive:
            archive.writestr("manifest.json", json.dumps(manifeste, ensure_ascii=False))
            for nom, contenu in descripteurs.items():
                archive.writestr(nom, contenu)
        os.replace(temporaire, cible)
    finally:
        temporaire.unlink(missing_ok=True)
    return {cle:valeur for cle,valeur in manifeste.items() if cle!="proprietaire_empreinte"}


def _lire_manifeste(chemin, proprietaire):
    if chemin.is_symlink() or not chemin.is_file():
        return None
    try:
        with ZipFile(chemin) as archive:
            manifeste = json.loads(archive.read("manifest.json"))
        empreinte = sha256(proprietaire.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(manifeste.get("proprietaire_empreinte", ""), empreinte):
            return None
        if manifeste.get("id") != chemin.stem:
            return None
        return {cle:valeur for cle,valeur in manifeste.items() if cle!="proprietaire_empreinte"}
    except (BadZipFile, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def lister_points(dossier_donnees, proprietaire):
    racine = _racine(dossier_donnees)
    if not racine.is_dir():
        return []
    resultat = []
    for chemin in racine.glob("*.zip"):
        if not IDENTIFIANT.fullmatch(chemin.stem):
            continue
        manifeste = _lire_manifeste(chemin, proprietaire)
        if manifeste is not None:
            resultat.append(manifeste)
    return sorted(resultat, key=lambda d:d["sauvegarde_le"], reverse=True)


def fichier_point(dossier_donnees, identifiant, proprietaire):
    chemin = _nom_fichier(dossier_donnees, identifiant)
    return chemin if _lire_manifeste(chemin, proprietaire) is not None else None


def purger_points(dossier_donnees, duree_retention):
    racine = _racine(dossier_donnees)
    if not racine.is_dir():
        return
    maintenant = time.time()
    for chemin in racine.glob("*.zip"):
        if chemin.is_symlink() or not IDENTIFIANT.fullmatch(chemin.stem):
            continue
        try:
            if maintenant - chemin.stat().st_mtime > duree_retention:
                chemin.unlink()
        except OSError:
            continue
