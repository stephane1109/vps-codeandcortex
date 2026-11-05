"""Découverte progressive de comptes associés à un territoire par vidéos Research.

Un compte candidat est associé au territoire par ses vidéos publiques, pas
par une adresse ou une résidence vérifiée. Les recherches et curseurs sont
sauvegardés sans token ni Client secret, dans un espace privé par session.
"""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import unicodedata
import uuid
import threading

from collecte.researchapi import (
    _dates, _jeton, _requete, _url_videos,
    ResearchErreur, ResearchJetonInvalide,
)
from collecte.verification_comptes import normaliser_compte

MAX_COMPTES = 30000
VERSION_REQUETE = 2
_VERROU = threading.RLock()
_TRAVAUX = {}


def _normaliser_texte(texte):
    """Uniformiser accents et casse sans effacer les séparateurs de mots."""
    valeur = unicodedata.normalize("NFKD", str(texte or ""))
    return "".join(c for c in valeur if not unicodedata.combining(c)).casefold()


def correspond_territoire(video, termes):
    """Vérifier que la ville apparaît réellement dans la légende ou les hashtags."""
    if not isinstance(video, dict):
        return False
    hashtags = video.get("hashtag_names") or []
    if not isinstance(hashtags, list):
        hashtags = []
    formes = {nettoyer_terme(tag) for tag in hashtags
              if isinstance(tag, str) and 2 <= len(tag.strip().lstrip("#")) <= 45}
    if formes.intersection(termes):
        return True
    description = _normaliser_texte(video.get("video_description") or "")
    return any(re.search(r"(?<![a-z0-9_])" + re.escape(mot)
                         + r"(?![a-z0-9_])", description) for mot in termes)


def requete_territoriale(termes, debut, fin, curseur=None, search_id=None):
    """Chercher dans les hashtags OU les mots de la légende."""
    corps = {
        "query": {"or": [
            {"field_name": "hashtag_name", "operation": "IN",
             "field_values": list(termes)},
            {"field_name": "keyword", "operation": "IN",
             "field_values": list(termes)},
        ]},
        "start_date": debut, "end_date": fin,
        "max_count": 100, "is_random": False,
    }
    if curseur is not None:
        corps["cursor"] = curseur
        corps["search_id"] = search_id
    return corps


def recherche_active(identifiant):
    """Indiquer si un travail de fond est actuellement vivant."""
    with _VERROU:
        entree = _TRAVAUX.get(identifiant)
        return bool(entree and entree["thread"].is_alive())


def lancer_recherche(racine, proprietaire, identifiant):
    """Exécuter toutes les pages disponibles sans bloquer la requête HTTP."""
    charger(racine, proprietaire, identifiant)
    with _VERROU:
        if recherche_active(identifiant):
            return True
        if any(e["thread"].is_alive() for e in _TRAVAUX.values()):
            raise ValueError(
                "Une découverte territoriale est déjà en cours sur ce serveur.")
        arret = threading.Event()

        def travailler():
            try:
                poursuivre_inventaire(
                    racine, proprietaire, identifiant, nombre_pages=None,
                    arret=arret)
            finally:
                with _VERROU:
                    _TRAVAUX.pop(identifiant, None)

        tache = threading.Thread(
            target=travailler, daemon=True,
            name="decouverte-territoriale-" + identifiant[:8])
        _TRAVAUX[identifiant] = {"thread": tache, "arret": arret}
        tache.start()
        return True


def arreter_recherche(identifiant):
    """Arrêter après la page en cours, en sauvegardant le curseur."""
    with _VERROU:
        entree = _TRAVAUX.get(identifiant)
        if not entree or not entree["thread"].is_alive():
            return False
        entree["arret"].set()
        return True


def nettoyer_terme(texte):
    """Normaliser une ville ou une graphie de hashtag sans symbole #."""
    valeur = unicodedata.normalize("NFKD", str(texte or ""))
    valeur = "".join(c for c in valeur if not unicodedata.combining(c))
    valeur = valeur.casefold().strip().lstrip("#")
    valeur = re.sub(r"[^a-z0-9_]+", "", valeur)
    if not 2 <= len(valeur) <= 45:
        raise ValueError("Le territoire doit comporter 2 à 45 caractères utilisables.")
    return valeur


def espace_prive(racine, proprietaire):
    """Isoler les inventaires grâce à l'empreinte du cookie d'historique."""
    if not re.fullmatch(r"[a-f0-9]{64}", str(proprietaire or "")):
        raise ValueError("Historique privé indisponible : rechargez l'application.")
    chemin = Path(racine) / "decouverte_territoriale" / hashlib.sha256(
        proprietaire.encode()).hexdigest()
    chemin.mkdir(mode=0o700, parents=True, exist_ok=True)
    return chemin


def chemin_inventaire(racine, proprietaire, identifiant):
    """Ne jamais accepter de chemin de fichier transmis par le navigateur."""
    if not re.fullmatch(r"[a-f0-9]{32}", str(identifiant or "")):
        raise ValueError("Identifiant de découverte incorrect.")
    return espace_prive(racine, proprietaire) / f"{identifiant}.json"


def sauvegarder(chemin, contenu):
    """Écrire un inventaire de manière atomique."""
    temporaire = chemin.with_suffix(".tmp")
    temporaire.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    os.replace(temporaire, chemin)


def creer_inventaire(racine, proprietaire, ville, variantes, debut, fin):
    """Initialiser les périodes et les mots-clés de découverte."""
    ville = str(ville or "").strip()
    if not 2 <= len(ville) <= 80:
        raise ValueError("Précisez une ville entre 2 et 80 caractères.")
    termes = [nettoyer_terme(ville)]
    for variante in variantes or []:
        mot = nettoyer_terme(variante)
        if mot not in termes:
            termes.append(mot)
    if len(termes) > 8:
        raise ValueError("8 variantes de recherche au maximum.")
    if not debut or not fin:
        raise ValueError("Choisissez une période de recherche.")
    periodes = list(_dates(debut, fin))
    if not periodes:
        raise ValueError("Période de recherche vide.")
    identifiant = uuid.uuid4().hex
    inventaire = {
        "id": identifiant, "ville": ville, "hashtags": termes,
        "date_debut": debut, "date_fin": fin,
        "periodes": periodes, "indice_periode": 0,
        "cursor": None, "search_id": None,
        "comptes": {}, "pages": 0, "candidats": 0,
        "terminee": False, "erreur": "", "version_requete": VERSION_REQUETE,
        "videos_ecartees": 0, "etat": "en_attente",
    }
    sauvegarder(chemin_inventaire(racine, proprietaire, identifiant), inventaire)
    return presenter(inventaire)


def charger(racine, proprietaire, identifiant):
    chemin = chemin_inventaire(racine, proprietaire, identifiant)
    if not chemin.is_file():
        raise ValueError("Cet inventaire n'existe pas dans l'historique privé.")
    return json.loads(chemin.read_text(encoding="utf-8"))


def presenter(inventaire):
    """Renvoyer les comptes uniquement, sans secrets ni paramètres internes."""
    comptes = sorted(
        inventaire["comptes"].values(),
        key=lambda compte: (-compte["videos_trouvees"], compte["username"]))
    return {
        "id": inventaire["id"], "ville": inventaire["ville"],
        "hashtags": inventaire["hashtags"], "date_debut": inventaire["date_debut"],
        "date_fin": inventaire["date_fin"], "pages": inventaire["pages"],
        "candidats": inventaire["candidats"],
        "terminee": inventaire["terminee"], "erreur": inventaire.get("erreur", ""),
        "comptes": comptes, "nombre_comptes": len(comptes),
        "videos_ecartees": inventaire.get("videos_ecartees", 0),
        "etat": ("en_cours" if recherche_active(inventaire["id"])
                 else inventaire.get("etat", "en_attente")
                 if inventaire.get("etat") != "en_cours" else "interrompue"),
    }


def lister_inventaires(racine, proprietaire):
    """Lister les recherches conservées pour une session privée."""
    dossier = espace_prive(racine, proprietaire)
    resultats = []
    for chemin in sorted(dossier.glob("*.json")):
        try:
            objet = json.loads(chemin.read_text(encoding="utf-8"))
            resultats.append({
                "id": objet["id"], "ville": objet["ville"],
                "nombre_comptes": len(objet["comptes"]),
                "terminee": objet.get("terminee", False),
            })
        except (KeyError, ValueError, OSError):
            continue
    return resultats


def poursuivre_inventaire(racine, proprietaire, identifiant, *, requete=_requete,
                         nombre_pages=None, arret=None):
    """Parcourir les pages jusqu'à la fin ou à l'arrêt, avec checkpoint."""
    if nombre_pages is not None and not 1 <= nombre_pages <= 100000:
        raise ValueError("Nombre de pages invalide.")
    chemin = chemin_inventaire(racine, proprietaire, identifiant)
    inventaire = charger(racine, proprietaire, identifiant)
    if inventaire["terminee"]:
        return presenter(inventaire)
    # Les anciens inventaires utilisaient une requête limitée aux hashtags.
    # Leur curseur n'est pas réutilisable avec la requête keyword élargie.
    if inventaire.get("version_requete", 1) < VERSION_REQUETE:
        inventaire["indice_periode"] = 0
        inventaire["cursor"] = None
        inventaire["search_id"] = None
        inventaire["version_requete"] = VERSION_REQUETE
        inventaire["etat"] = "en_attente"
        sauvegarder(chemin, inventaire)
    inventaire["etat"] = "en_cours"
    sauvegarder(chemin, inventaire)
    # Le jeton provient des variables Coolify ; il n'est jamais persisté.
    try:
        token = _jeton(requete=requete)
    except ResearchErreur as erreur:
        inventaire["erreur"] = str(erreur)
        inventaire["etat"] = "interrompue"
        sauvegarder(chemin, inventaire)
        return presenter(inventaire)
    pages_traitees = 0
    while nombre_pages is None or pages_traitees < nombre_pages:
        if arret is not None and arret.is_set():
            inventaire["etat"] = "interrompue"
            break
        indice = inventaire["indice_periode"]
        if indice >= len(inventaire["periodes"]):
            inventaire["terminee"] = True
            break
        debut, fin = inventaire["periodes"][indice]
        corps = requete_territoriale(
            inventaire["hashtags"], debut, fin,
            inventaire["cursor"], inventaire["search_id"])
        try:
            try:
                resultat = requete(
                    _url_videos(), data=json.dumps(corps).encode("utf-8"),
                    headers={"Authorization": "Bearer " + token,
                             "Content-Type": "application/json"})
            except ResearchJetonInvalide:
                token = _jeton(requete=requete, renouveler=True)
                resultat = requete(
                    _url_videos(), data=json.dumps(corps).encode("utf-8"),
                    headers={"Authorization": "Bearer " + token,
                             "Content-Type": "application/json"})
            donnees = resultat.get("data") or {}
            videos = donnees.get("videos")
            if not isinstance(videos, list):
                raise ResearchErreur("TikTok n'a pas renvoyé de liste de vidéos.")
            compteurs = inventaire["comptes"]
            for video in videos:
                if not isinstance(video, dict):
                    continue
                if not correspond_territoire(video, inventaire["hashtags"]):
                    inventaire["videos_ecartees"] = inventaire.get("videos_ecartees", 0) + 1
                    continue
                try:
                    auteur = normaliser_compte(video.get("username") or "")
                except (TypeError, AttributeError, ValueError):
                    continue
                if not auteur:
                    continue
                identifiant_video = str(video.get("id") or "")
                if not re.fullmatch(r"\d{5,30}", identifiant_video):
                    continue
                if auteur not in compteurs:
                    if len(compteurs) >= MAX_COMPTES:
                        raise ValueError("Limite de 30 000 comptes atteinte.")
                    compteurs[auteur] = {
                        "username": "@" + auteur, "videos_trouvees": 0,
                        "identifiants_videos": [],
                    }
                compte = compteurs[auteur]
                if identifiant_video not in compte["identifiants_videos"]:
                    compte["identifiants_videos"].append(identifiant_video)
                    compte["videos_trouvees"] += 1
            inventaire["pages"] += 1
            pages_traitees += 1
            inventaire["candidats"] += len(videos)
            if donnees.get("has_more"):
                suivant = donnees.get("cursor")
                recherche = donnees.get("search_id")
                if (not isinstance(suivant, int) or suivant < 0
                        or not isinstance(recherche, str) or not recherche
                        or suivant == inventaire["cursor"]):
                    raise ResearchErreur(
                        "Pagination TikTok incomplète : curseur absent ou identique. "
                        "La recherche est interrompue sans réinitialisation.")
                inventaire["cursor"] = suivant
                inventaire["search_id"] = recherche
            else:
                inventaire["indice_periode"] += 1
                inventaire["cursor"] = None
                inventaire["search_id"] = None
                inventaire["terminee"] = (
                    inventaire["indice_periode"] >= len(inventaire["periodes"]))
            inventaire["erreur"] = ""
            inventaire["etat"] = "terminee" if inventaire["terminee"] else "en_cours"
            sauvegarder(chemin, inventaire)
            if inventaire["terminee"]:
                break
        except (ResearchErreur, ValueError) as erreur:
            inventaire["erreur"] = str(erreur)
            inventaire["etat"] = "interrompue"
            sauvegarder(chemin, inventaire)
            break
    if inventaire["terminee"]:
        inventaire["etat"] = "terminee"
    elif inventaire["etat"] == "en_cours":
        inventaire["etat"] = "interrompue"
    sauvegarder(chemin, inventaire)
    return presenter(inventaire)


def exporter_csv(inventaire):
    """Exporter uniquement les @comptes et leur fréquence de découverte."""
    sortie = io.StringIO()
    writer = csv.writer(sortie, delimiter=";", lineterminator="\n")
    writer.writerow(["territoire", "username", "videos_trouvees"])
    for compte in presenter(inventaire)["comptes"]:
        writer.writerow([
            inventaire["ville"], compte["username"], compte["videos_trouvees"]])
    return sortie.getvalue().encode("utf-8-sig")


def exporter_txt(inventaire):
    """Produire un @compte par ligne pour le champ Profils."""
    return ("\n".join(
        ligne["username"] for ligne in presenter(inventaire)["comptes"]
    ) + "\n").encode("utf-8") if inventaire["comptes"] else b""
