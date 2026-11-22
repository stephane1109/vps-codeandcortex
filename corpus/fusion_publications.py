"""Concaténer les métriques TikTok de plusieurs CSV sans accès à la base.

Ce module n'écrit jamais dans SQLite ou PostgreSQL. L'identifiant TikTok
est une chaîne afin de préserver les grands entiers de publications.
"""
import csv
import io
import re

from corpus.export_csv import serialiser_csv

MAX_FICHIERS = 20
MAX_OCTETS = 10 * 1024 * 1024
MAX_LIGNES = 100000
IDENTIFIANT = re.compile(r"[0-9]{5,30}\Z")
URL_VIDEO = re.compile(r"/video/([0-9]{5,30})(?:[/?#]|$)")


def _lire_lignes(nom, contenu):
    """Vérifier le CSV et restituer ses lignes sans conversion destructive."""
    if not str(nom).lower().endswith(".csv"):
        raise ValueError("La fusion accepte uniquement des fichiers CSV.")
    if not isinstance(contenu, bytes) or not contenu or len(contenu) > MAX_OCTETS:
        raise ValueError(f"{nom} : fichier vide ou supérieur à 10 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeError as erreur:
        raise ValueError(f"{nom} : encodage UTF-8 requis.") from erreur
    entete = texte.splitlines()[0] if texte.splitlines() else ""
    try:
        dialecte = csv.Sniffer().sniff(entete, delimiters=";,\t")
        separateur = dialecte.delimiter
    except csv.Error:
        separateur = ";" if entete.count(";") >= entete.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(texte, newline=""), delimiter=separateur)
    champs = lecteur.fieldnames or []
    if not champs or len(champs) != len(set(champs)) or any(not c for c in champs):
        raise ValueError(f"{nom} : noms de colonnes absents ou dupliqués.")
    if not any(c in champs for c in ("publication_id", "id", "url")):
        raise ValueError(f"{nom} : colonne d'identification de la vidéo absente.")
    # Refuser les fichiers commentaires lorsque « id » désigne le commentaire.
    if {"parent_id", "texte"}.issubset(champs) and "publication_id" in champs:
        raise ValueError(f"{nom} : sélectionnez un CSV de publications, pas de commentaires.")
    lignes = []
    for ligne in lecteur:
        if None in ligne:
            raise ValueError(f"{nom} : une ligne possède trop de cellules.")
        if all(valeur in (None, "") for valeur in ligne.values()):
            continue
        lignes.append(ligne)
    return champs, lignes


def _identifiant(ligne):
    """Repérer la vidéo TikTok sans convertir ses identifiants en flottants."""
    for cle in ("publication_id", "id"):
        valeur = str(ligne.get(cle) or "").strip()
        if IDENTIFIANT.fullmatch(valeur):
            return valeur
    trouve = URL_VIDEO.search(str(ligne.get("url") or ""))
    return trouve.group(1) if trouve else ""


def fusionner_publications_csv(fichiers, priorite="premier"):
    """Assembler les lignes par ID, conserver toutes les colonnes et provenances."""
    if priorite not in ("premier", "dernier"):
        raise ValueError("Priorité de dédoublonnage inconnue.")
    if not 1 <= len(fichiers) <= MAX_FICHIERS:
        raise ValueError("Importez entre 1 et 20 fichiers CSV.")
    colonnes = ["publication_id", "fichiers_sources"]
    lignes = {}
    provenances = {}
    total = doublons = divergents = 0
    for nom, contenu in fichiers:
        champs, observations = _lire_lignes(nom, contenu)
        colonnes = list(dict.fromkeys([*colonnes, *champs]))
        for ligne in observations:
            total += 1
            if total > MAX_LIGNES:
                raise ValueError("La fusion est limitée à 100 000 lignes.")
            code = _identifiant(ligne)
            if not code:
                raise ValueError(f"{nom} : identifiant TikTok manquant ou invalide.")
            ligne["publication_id"] = code
            if code not in provenances:
                provenances[code] = []
            if nom not in provenances[code]:
                provenances[code].append(nom)
            ancienne = lignes.get(code)
            if ancienne is not None:
                doublons += 1
                if any(ancienne.get(champ) not in ("", None)
                       and ligne.get(champ) not in ("", None)
                       and str(ancienne[champ]) != str(ligne[champ])
                       for champ in set(ancienne) & set(ligne)
                       if champ != "fichiers_sources"):
                    divergents += 1
                if priorite == "premier":
                    # Les nouveaux champs non vides complètent l'ancienne ligne.
                    for champ, valeur in ligne.items():
                        if ancienne.get(champ) in (None, "") and valeur not in (None, ""):
                            ancienne[champ] = valeur
                    continue
                # Dernier fichier prioritaire, sans supprimer les champs
                # uniquement présents dans les précédents.
                fusion = dict(ancienne)
                fusion.update({champ: valeur for champ, valeur in ligne.items()
                               if valeur not in (None, "")})
                lignes[code] = fusion
            else:
                lignes[code] = ligne
    for code, ligne in lignes.items():
        ligne["fichiers_sources"] = " | ".join(provenances[code])
    contenu = serialiser_csv(lignes.values(), colonnes)
    return {
        "lignes": list(lignes.values()),
        "colonnes": colonnes,
        "total_initial": total,
        "nombre_unique": len(lignes),
        "doublons": doublons,
        "doublons_divergents": divergents,
        "csv": contenu.encode("utf-8-sig"),
    }
