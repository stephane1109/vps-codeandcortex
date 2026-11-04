"""Annotation manuelle autonome de tableaux engagement.csv.

Les données restent dans un espace privé lié au cookie d'historique.
Aucune collecte TikTok, analyse vidéo ou modification du corpus original.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

LIMITE_OCTETS = 12_000_000
LIMITE_LIGNES = 100_000
LIMITE_VARIABLES = 60
NOM_VARIABLE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")
ID_PROJET = re.compile(r"^[a-f0-9]{32}$")
CHOIX_BINAIRES = ("Non évaluée", "Non (0)", "Oui (1)")


def dossier_prive(racine, proprietaire):
    """Créer un répertoire isolé sans écrire le cookie en clair."""
    if not re.fullmatch(r"[a-f0-9]{64}", proprietaire or ""):
        raise ValueError("Historique privé indisponible.")
    empreinte = hashlib.sha256(proprietaire.encode("ascii")).hexdigest()
    dossier = Path(racine) / "annotations_csv" / empreinte
    dossier.mkdir(parents=True, exist_ok=True, mode=0o700)
    return dossier


def chemin_projet(racine, proprietaire, identifiant):
    """Limiter la lecture aux projets autorisés et à leurs noms validés."""
    if not ID_PROJET.fullmatch(str(identifiant)):
        raise ValueError("Identifiant de projet invalide.")
    return dossier_prive(racine, proprietaire) / (identifiant + ".json")


def ecrire_atomiquement(chemin, donnees):
    """Enregistrer sans laisser un fichier JSON partiellement écrit."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=chemin.parent,
        prefix=".annotation_", suffix=".tmp", delete=False
    ) as temporaire:
        temporaire_name = temporaire.name
        json.dump(donnees, temporaire, ensure_ascii=False)
    try:
        os.replace(temporaire_name, chemin)
    finally:
        Path(temporaire_name).unlink(missing_ok=True)


def lire_projet(racine, proprietaire, identifiant):
    """Charger un projet existant sans possibilité de sortie de répertoire."""
    chemin = chemin_projet(racine, proprietaire, identifiant)
    if not chemin.is_file():
        raise ValueError("Projet d'annotation introuvable.")
    projet = json.loads(chemin.read_text(encoding="utf-8"))
    if projet.get("id") != identifiant:
        raise ValueError("Projet d'annotation incohérent.")
    return projet


def importer_tableau(racine, proprietaire, nom, contenu):
    """Importer le CSV en préservant les colonnes et les identifiants textuels."""
    if not isinstance(contenu, bytes) or len(contenu) > LIMITE_OCTETS:
        raise ValueError("CSV invalide ou supérieur à 12 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeError as erreur:
        raise ValueError("Le CSV doit être encodé en UTF-8.") from erreur
    try:
        dialecte = csv.Sniffer().sniff(texte[:8192], delimiters=";,\t")
        separateur = dialecte.delimiter
    except csv.Error:
        separateur = ";" if ";" in texte.splitlines()[0] else ","
    lecteur = csv.DictReader(io.StringIO(texte, newline=""), delimiter=separateur)
    colonnes = list(lecteur.fieldnames or [])
    if not colonnes or len(colonnes) != len(set(colonnes)) or len(colonnes) > 250:
        raise ValueError("Le CSV possède des colonnes absentes, dupliquées ou trop nombreuses.")
    colonne_id = next((c for c in ("publication_id", "id", "id_", "video_id")
                       if c in colonnes), None)
    if not colonne_id:
        raise ValueError("Le CSV doit contenir publication_id, id, id_ ou video_id.")
    lignes = []
    identifiants = set()
    for numero, ligne in enumerate(lecteur, start=1):
        if numero > LIMITE_LIGNES:
            raise ValueError("Maximum de 100 000 publications par projet.")
        if None in ligne:
            raise ValueError(f"Ligne {numero} : nombre de cellules incohérent.")
        identifiant = (ligne.get(colonne_id) or "").strip()
        if not identifiant:
            raise ValueError(f"Ligne {numero} : identifiant TikTok absent.")
        if identifiant in identifiants:
            raise ValueError(f"Identifiant TikTok dupliqué : {identifiant}.")
        identifiants.add(identifiant)
        lignes.append({c: ligne.get(c) or "" for c in colonnes})
    if not lignes:
        raise ValueError("Le CSV ne contient aucune publication.")
    identifiant = uuid.uuid4().hex
    maintenant = datetime.now(timezone.utc).isoformat()
    projet = {
        "id": identifiant, "nom": (nom or "Annotation").strip()[:120],
        "cree_le": maintenant, "modifie_le": maintenant,
        "colonne_id": colonne_id, "colonnes": colonnes,
        "lignes": lignes, "variables": [], "annotations": {},
        "revision": 0,
    }
    ecrire_atomiquement(chemin_projet(racine, proprietaire, identifiant), projet)
    return resumer_projet(projet)


def resumer_projet(projet):
    """Ne pas renvoyer le tableau intégral dans les listes de projets."""
    return {
        "id": projet["id"], "nom": projet["nom"],
        "nombre": len(projet["lignes"]),
        "variables": projet["variables"],
        "colonne_id": projet["colonne_id"],
        "revision": projet["revision"],
        "modifie_le": projet["modifie_le"],
    }


def lister_projets(racine, proprietaire):
    """Lister les projets du seul propriétaire courant."""
    dossier = dossier_prive(racine, proprietaire)
    resultats = []
    for chemin in dossier.glob("*.json"):
        try:
            projet = json.loads(chemin.read_text(encoding="utf-8"))
            if projet.get("id") == chemin.stem:
                resultats.append(resumer_projet(projet))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(resultats, key=lambda p: p["modifie_le"], reverse=True)


def lire_page(racine, proprietaire, identifiant, page=0, taille=50):
    """Envoyer seulement une page pour éviter un tableau Streamlit volumineux."""
    projet = lire_projet(racine, proprietaire, identifiant)
    if not 0 <= page <= 100000 or not 1 <= taille <= 200:
        raise ValueError("Pagination invalide.")
    debut = page * taille
    annotations = projet["annotations"]
    rows = []
    for ligne in projet["lignes"][debut:debut + taille]:
        identifiant_video = ligne[projet["colonne_id"]]
        codages = annotations.get(identifiant_video) or {}
        rows.append({
            **ligne, **{
                v["id"]: codages.get(v["id"], "Non évaluée")
                for v in projet["variables"]
            }
        })
    return {**resumer_projet(projet), "colonnes": projet["colonnes"],
            "page": page, "taille": taille, "lignes": rows}


def ajouter_variable(racine, proprietaire, identifiant, nom, type_variable="binaire",
                     modalites=None):
    """Ajouter une variable sans altérer les observations existantes."""
    projet = lire_projet(racine, proprietaire, identifiant)
    cle = re.sub(r"\s+", "_", (nom or "").strip().lower())
    if (not NOM_VARIABLE.fullmatch(cle)
            or cle in projet["colonnes"]
            or cle in {v["id"] for v in projet["variables"]}):
        raise ValueError("Nom de variable invalide ou déjà utilisé (lettres, chiffres, _).")
    if len(projet["variables"]) >= LIMITE_VARIABLES:
        raise ValueError("Maximum de 60 variables d'annotation.")
    if type_variable == "binaire":
        choix = list(CHOIX_BINAIRES)
    elif type_variable == "categorielle":
        choix = ["Non évaluée", *[
            v.strip() for v in (modalites or [])
            if isinstance(v, str) and v.strip() and v.strip() != "Non évaluée"]]
        if not 2 <= len(choix) <= 21 or len(set(choix)) != len(choix):
            raise ValueError("Saisissez entre une et vingt modalités distinctes.")
    else:
        raise ValueError("Type de variable inconnu.")
    projet["variables"].append({
        "id": cle, "nom": nom.strip()[:120],
        "type": type_variable, "modalites": choix,
    })
    projet["revision"] += 1
    projet["modifie_le"] = datetime.now(timezone.utc).isoformat()
    ecrire_atomiquement(chemin_projet(racine, proprietaire, identifiant), projet)
    return resumer_projet(projet)


def enregistrer_annotations(racine, proprietaire, identifiant, modifications, revision):
    """Valider puis enregistrer atomiquement toutes les cellules modifiées."""
    projet = lire_projet(racine, proprietaire, identifiant)
    if projet["revision"] != revision:
        raise ValueError("Les annotations ont changé : rechargez le projet avant d'enregistrer.")
    if len(modifications) > 200:
        raise ValueError("Maximum de 200 lignes par enregistrement.")
    valides = {ligne[projet["colonne_id"]] for ligne in projet["lignes"]}
    variables = {v["id"]: set(v["modalites"]) for v in projet["variables"]}
    for item in modifications:
        identifiant_video = str(item.get("publication_id") or "")
        codages = item.get("codages")
        if identifiant_video not in valides or not isinstance(codages, dict):
            raise ValueError("Ligne d'annotation invalide.")
        if set(codages) - set(variables):
            raise ValueError("Variable d'annotation inconnue.")
        for variable, valeur in codages.items():
            if valeur not in variables[variable]:
                raise ValueError("Modalité d'annotation non autorisée.")
    for item in modifications:
        identifiant_video = str(item["publication_id"])
        projet["annotations"].setdefault(identifiant_video, {}).update(item["codages"])
    projet["revision"] += 1
    projet["modifie_le"] = datetime.now(timezone.utc).isoformat()
    ecrire_atomiquement(chemin_projet(racine, proprietaire, identifiant), projet)
    return resumer_projet(projet)


def exporter_tableau(racine, proprietaire, identifiant):
    """Restituer le CSV complet enrichi de ses variables de codage."""
    projet = lire_projet(racine, proprietaire, identifiant)
    from corpus.export_csv import serialiser_csv
    colonnes = [*projet["colonnes"], *(v["id"] for v in projet["variables"])]
    lignes = []
    for ligne in projet["lignes"]:
        code = projet["annotations"].get(ligne[projet["colonne_id"]]) or {}
        lignes.append({
            **ligne, **{
                variable["id"]: code.get(variable["id"], "Non évaluée")
                for variable in projet["variables"]
            }
        })
    return "\ufeff" + serialiser_csv(lignes, colonnes)
