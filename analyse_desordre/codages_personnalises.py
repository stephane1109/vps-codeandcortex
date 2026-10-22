"""Codages binaires SHS libres, indépendants des mesures et de la violence historique.

Les valeurs absentes ne sont pas des zéros. Chaque variable a un identifiant stable.
"""
import csv
import io
import json
import os
import re
import tempfile
import unicodedata
import uuid
from pathlib import Path

FICHIER = "codages_personnalises.json"
MAX_VARIABLES = 20


def lire(session):
    chemin = Path(session) / FICHIER
    if chemin.is_symlink():
        raise ValueError("Fichier des codages non autorisé.")
    if not chemin.is_file():
        return {"variables": [], "valeurs": {}}
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    if not isinstance(donnees, dict) or not isinstance(donnees.get("variables"), list) or not isinstance(donnees.get("valeurs"), dict):
        raise ValueError("Fichier des codages invalide.")
    return donnees


def _ecrire(session, donnees):
    rep = Path(session)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=rep,
                                     prefix=".codages_", suffix=".tmp", delete=False) as flux:
        temp = Path(flux.name)
        try:
            json.dump(donnees, flux, ensure_ascii=False, indent=2, sort_keys=True)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, rep / FICHIER)
    finally:
        temp.unlink(missing_ok=True)


def _normaliser_nom(nom):
    nom = " ".join(str(nom).strip().split())
    if not 2 <= len(nom) <= 70 or any(ord(c) < 32 for c in nom):
        raise ValueError("Le nom de la variable doit contenir 2 à 70 caractères.")
    return nom


def _cle_nom(nom):
    return unicodedata.normalize("NFKC", nom).casefold()


def creer_variable(session, nom):
    nom = _normaliser_nom(nom)
    donnees = lire(session)
    if len(donnees["variables"]) >= MAX_VARIABLES:
        raise ValueError("20 variables maximum par corpus.")
    cle = _cle_nom(nom)
    if any(_cle_nom(v["nom"]) == cle for v in donnees["variables"]):
        raise ValueError("Une variable porte déjà ce nom.")
    nouvelle = {"id": "codage_" + uuid.uuid4().hex[:12], "nom": nom}
    donnees["variables"].append(nouvelle)
    donnees["valeurs"][nouvelle["id"]] = {}
    _ecrire(session, donnees)
    return nouvelle


def renommer_variable(session, variable_id, nom):
    """Modifier seulement le libellé : ID stable, annotations intégralement conservées."""
    if not re.fullmatch(r"codage_[a-f0-9]{12}", variable_id):
        raise ValueError("Identifiant de variable invalide.")
    nom = _normaliser_nom(nom)
    donnees = lire(session)
    variable = next((v for v in donnees["variables"] if v["id"] == variable_id), None)
    if variable is None:
        raise ValueError("Variable absente de cette analyse.")
    if any(v["id"] != variable_id and _cle_nom(v["nom"]) == _cle_nom(nom)
           for v in donnees["variables"]):
        raise ValueError("Une autre variable porte déjà ce nom.")
    variable["nom"] = nom
    _ecrire(session, donnees)
    return dict(variable)


MODALITES_ANNOTATION = {"Non évaluée": None, "Non (0)": 0, "Oui (1)": 1}


def modifications_depuis_tableau(original, modifie, variables):
    """Calculer les changements par ID de vidéo, indépendamment du tri des lignes.

    Vérifier aussi l'identité des colonnes : seule une variable créée dans
    cette analyse peut être codée.
    """
    colonnes = [v["id"] for v in variables]
    depart = {}
    for ligne in original.to_dict("records"):
        identifiant = str(ligne["publication_id"])
        if identifiant in depart:
            raise ValueError("Identifiant TikTok dupliqué.")
        depart[identifiant] = ligne
    mutations = []
    presents = set()
    for ligne in modifie.to_dict("records"):
        identifiant = str(ligne["publication_id"])
        if identifiant in presents or identifiant not in depart:
            raise ValueError("L'identité des vidéos du tableau a changé.")
        presents.add(identifiant)
        for variable_id in colonnes:
            if variable_id not in ligne or variable_id not in depart[identifiant]:
                raise ValueError("Une colonne d'annotation a disparu.")
            ancienne = depart[identifiant][variable_id]
            nouvelle = ligne[variable_id]
            if nouvelle not in MODALITES_ANNOTATION:
                raise ValueError("Choisissez Non évaluée, Non (0) ou Oui (1).")
            if nouvelle != ancienne:
                mutations.append({
                    "publication_id": identifiant,
                    "variable_id": variable_id,
                    "valeur": MODALITES_ANNOTATION[nouvelle],
                })
    if presents != set(depart):
        raise ValueError("Certaines vidéos manquent dans le tableau.")
    return mutations


def enregistrer(session, modifications, ids_autorises):
    donnees = lire(session)
    autorises = {str(v) for v in ids_autorises}
    variables = {v["id"] for v in donnees["variables"]}
    for ligne in modifications:
        var = ligne["variable_id"]
        identifiant = str(ligne["publication_id"])
        valeur = ligne["valeur"]
        if var not in variables or identifiant not in autorises or not re.fullmatch(r"[0-9]+", identifiant):
            raise ValueError("Variable ou publication absente de ce corpus.")
        if valeur is not None and (type(valeur) is not int or valeur not in (0, 1)):
            raise ValueError("Le codage doit être 0, 1 ou non évalué.")
    for ligne in modifications:
        donnees["valeurs"].setdefault(ligne["variable_id"], {})
        valeurs = donnees["valeurs"][ligne["variable_id"]]
        identifiant = str(ligne["publication_id"])
        if ligne["valeur"] is None:
            valeurs.pop(identifiant, None)
        else:
            valeurs[identifiant] = ligne["valeur"]
    _ecrire(session, donnees)
    return donnees


def export_csv(publications, donnees, violence):
    sortie = io.StringIO(newline="")
    writer = csv.writer(sortie, delimiter=";")
    vars_ = donnees["variables"]
    writer.writerow(["publication_id", "url", "violence_visible", *[v["nom"] for v in vars_]])
    for publication in publications:
        identifiant = str(publication.get("id") or publication.get("publication_id") or "")
        def code(valeur):
            return "" if valeur is None else valeur
        writer.writerow([identifiant, publication.get("url") or "", code(violence.get(identifiant)),
                         *[code(donnees["valeurs"].get(v["id"], {}).get(identifiant)) for v in vars_]])
    return "\ufeff" + sortie.getvalue()
