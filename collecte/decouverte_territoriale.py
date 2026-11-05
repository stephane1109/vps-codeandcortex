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
import time
from urllib.parse import unquote, urlparse

from collecte.researchapi import (
    _dates, _jeton, _requete, _url_videos,
    ResearchErreur, ResearchJetonInvalide, ResearchErreurServeur,
)
from collecte.verification_comptes import normaliser_compte

MAX_COMPTES = 30000
VERSION_REQUETE = 4
_VERROU = threading.RLock()
_TRAVAUX = {}


def _normaliser_texte(texte):
    """Uniformiser accents et casse sans effacer les séparateurs de mots."""
    valeur = unicodedata.normalize("NFKD", str(texte or ""))
    return "".join(c for c in valeur if not unicodedata.combining(c)).casefold()


def extraire_reference_lieu(valeur, ville=""):
    """Accepter une URL TikTok Place ou un ID, sans vérifier l'association vidéo-lieu."""
    entree = str(valeur or "").strip()
    nom = str(ville or "").strip()
    if re.fullmatch(r"\d{12,25}", entree):
        identifiant = entree
        if not nom:
            raise ValueError("Indiquez le nom de la ville en plus du Place ID.")
    else:
        adresse = urlparse(entree)
        if (adresse.scheme not in ("https", "http")
                or (adresse.hostname or "").lower()
                not in ("tiktok.com", "www.tiktok.com", "m.tiktok.com")):
            raise ValueError("Indiquez une URL TikTok /place/ ou un Place ID.")
        chemin = unquote(adresse.path).strip("/")
        correspondance = re.fullmatch(
            r"place/(?P<nom>.+)-(?P<identifiant>\d{12,25})", chemin)
        if not correspondance:
            raise ValueError("URL de lieu TikTok sans identifiant Place valide.")
        identifiant = correspondance.group("identifiant")
        if not nom:
            nom = correspondance.group("nom").replace("-", " ")
    if not 2 <= len(nom) <= 80:
        raise ValueError("Le nom du lieu doit comporter 2 à 80 caractères.")
    nettoyer_terme(nom)
    return {"place_id": identifiant, "nom_lieu": nom}


def correspond_territoire(video, termes):
    """Vérifier que la ville apparaît réellement dans la légende ou les hashtags."""
    if not isinstance(video, dict):
        return False
    hashtags = video.get("hashtag_names") or []
    if not isinstance(hashtags, list):
        hashtags = []
    formes = set()
    for tag in hashtags:
        if not isinstance(tag, str):
            continue
        try:
            formes.add(nettoyer_terme(tag))
        except ValueError:
            continue
    if formes.intersection(termes):
        return True
    description = _normaliser_texte(video.get("video_description") or "")
    return any(re.search(r"(?<![a-z0-9_])" + re.escape(mot)
                         + r"(?![a-z0-9_])", description) for mot in termes)


def correspond_hashtags(video, hashtags, operateur="OR"):
    """Contrôler les hashtags présents, indépendamment de la ville."""
    if not hashtags:
        return True
    trouves = set()
    for nom in (video.get("hashtag_names") or []):
        if not isinstance(nom, str):
            continue
        try:
            trouves.add(nettoyer_terme(nom))
        except ValueError:
            continue
    # Certaines réponses Research ne fournissent que la description.
    description = _normaliser_texte(video.get("video_description") or "")
    for nom in re.findall(r"#([\w]+)", description):
        try:
            trouves.add(nettoyer_terme(nom))
        except ValueError:
            continue
    attendus = set(hashtags)
    return attendus.issubset(trouves) if operateur == "AND" else bool(attendus & trouves)


def requete_territoriale(termes, debut, fin, curseur=None, search_id=None,
                        hashtags_croises=None, operateur="OR",
                        mode_territoire="texte", region_code=None):
    """Croiser le pays d'enregistrement ou une ville textuelle avec les hashtags."""
    conditions = []
    if mode_territoire == "region_code":
        if not region_code or not re.fullmatch(r"[A-Z]{2}", region_code):
            raise ValueError("Code pays ISO invalide.")
        conditions.append({"field_name": "region_code", "operation": "EQ",
                           "field_values": [region_code]})
    elif mode_territoire in ("texte", "place_reference"):
        conditions.append({"field_name": "keyword", "operation": "IN",
                           "field_values": list(termes)})
    else:
        raise ValueError("Mode territorial inconnu.")
    if hashtags_croises:
        if operateur == "AND":
            conditions.extend({
                "field_name": "hashtag_name", "operation": "EQ",
                "field_values": [nom]} for nom in hashtags_croises)
        else:
            conditions.append({
                "field_name": "hashtag_name", "operation": "IN",
                "field_values": list(hashtags_croises)})
        query = {"and": conditions}
    elif mode_territoire in ("texte", "place_reference"):
        # Compatibilité des inventaires anciens sans hashtags thématiques.
        query = {"or": [
            {"field_name": "hashtag_name", "operation": "IN",
             "field_values": list(termes)},
            {"field_name": "keyword", "operation": "IN",
             "field_values": list(termes)}]}
    else:
        raise ValueError("Renseignez au moins un hashtag à croiser avec le pays.")
    corps = {"query": query, "start_date": debut, "end_date": fin,
             "max_count": 100, "is_random": False}
    if curseur is not None:
        corps["cursor"] = curseur
        corps["search_id"] = search_id
    return corps


def recherche_active(identifiant):
    """Indiquer si un travail de fond est actuellement vivant."""
    with _VERROU:
        entree = _TRAVAUX.get(identifiant)
        return bool(entree and entree["thread"].is_alive())


def recherche_arret_demande(identifiant):
    """Indiquer si un arrêt a été demandé au travail en cours."""
    with _VERROU:
        entree = _TRAVAUX.get(identifiant)
        return bool(entree and entree["thread"].is_alive()
                    and entree["arret"].is_set())


def recherche_en_cours():
    """Empêcher une deuxième recherche sur le même processus."""
    with _VERROU:
        return any(
            entree["thread"].is_alive() for entree in _TRAVAUX.values())


def lancer_recherche(racine, proprietaire, identifiant, *, credentiels=None):
    """Exécuter toutes les pages disponibles sans bloquer la requête HTTP."""
    charger(racine, proprietaire, identifiant)
    with _VERROU:
        if recherche_active(identifiant):
            return True
        if recherche_en_cours():
            raise ValueError(
                "Une collecte de comptes est déjà active. Sélectionnez-la "
                "dans les collectes enregistrées puis cliquez sur "
                "'Arrêter la collecte' avant d'en démarrer une autre.")
        arret = threading.Event()

        def travailler():
            try:
                poursuivre_inventaire(
                    racine, proprietaire, identifiant, nombre_pages=None,
                    arret=arret, credentiels=credentiels)
            except Exception as erreur:
                # Ne pas exposer les réponses brutes de l'API ni les jetons.
                chemin = chemin_inventaire(racine, proprietaire, identifiant)
                try:
                    etat = charger(racine, proprietaire, identifiant)
                    etat["etat"] = "interrompue"
                    etat["erreur"] = (
                        "Erreur interne pendant la découverte : "
                        + type(erreur).__name__)
                    sauvegarder(chemin, etat)
                except (OSError, ValueError):
                    pass
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


def interroger_page_avec_reprises(
        requete, corps, token, *, credentiels=None, pause=time.sleep,
        arret=None, compteurs=None):
    """Réessayer la même page sur HTTP 5xx, sans perdre cursor/search_id.

    Les erreurs 401 hors jeton expiré, 403 et 429 sont propagées sans
    répétition. Les relances 5xx comptent dans les requêtes Research.
    """
    compteurs = compteurs if compteurs is not None else {}
    donnees = json.dumps(corps).encode("utf-8")
    for tentative in range(4):
        if arret is not None and arret.is_set():
            return None, token
        try:
            try:
                resultat = requete(
                    _url_videos(), data=donnees,
                    headers={"Authorization": "Bearer " + token,
                             "Content-Type": "application/json"})
            except ResearchJetonInvalide:
                # Un seul renouvellement lors d'une invalidation avérée.
                token = _jeton(
                    requete=requete, credentiels=credentiels,
                    renouveler=True)
                resultat = requete(
                    _url_videos(), data=donnees,
                    headers={"Authorization": "Bearer " + token,
                             "Content-Type": "application/json"})
            return resultat, token
        except ResearchErreurServeur:
            compteurs["echecs_serveur"] = compteurs.get("echecs_serveur", 0) + 1
            if tentative == 3:
                raise
            compteurs["relances_serveur"] = compteurs.get("relances_serveur", 0) + 1
            # Attente progressive de 2, 4 puis 8 secondes.
            for _ in range(2 ** (tentative + 1)):
                if arret is not None and arret.is_set():
                    return None, token
                pause(1)
    raise ResearchErreur("Nombre de tentatives Research inattendu.")


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


def creer_inventaire(racine, proprietaire, ville, variantes, debut, fin, *, operateur="OR", mode_territoire="texte", region_code=None, reference_lieu=None):
    """Initialiser les périodes et les mots-clés de découverte."""
    ville = str(ville or "").strip()
    if mode_territoire == "region_code":
        region_code = str(region_code or "").strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", region_code):
            raise ValueError("Indiquez un code de pays ISO à deux lettres, par exemple FR.")
        ville = region_code
        termes = []
    elif mode_territoire == "place_reference":
        reference = extraire_reference_lieu(reference_lieu, ville)
        ville = reference["nom_lieu"]
        termes = [nettoyer_terme(ville)]
        region_code = None
    elif mode_territoire == "texte":
        if not 2 <= len(ville) <= 80:
            raise ValueError("Précisez une ville entre 2 et 80 caractères.")
        termes = [nettoyer_terme(ville)]
        region_code = None
    else:
        raise ValueError("Mode de recherche territorial inconnu.")
    hashtags_croises = []
    for valeur in variantes or []:
        hashtag = nettoyer_terme(valeur)
        if hashtag not in hashtags_croises:
            hashtags_croises.append(hashtag)
    if not hashtags_croises:
        raise ValueError("Renseignez au moins un hashtag à croiser avec la ville.")
    if len(hashtags_croises) > 10:
        raise ValueError("10 hashtags au maximum.")
    if operateur not in ("OR", "AND"):
        raise ValueError("Opérateur de croisement invalide.")
    if not debut or not fin:
        raise ValueError("Choisissez une période de recherche.")
    periodes = list(_dates(debut, fin))
    if not periodes:
        raise ValueError("Période de recherche vide.")
    identifiant = uuid.uuid4().hex
    inventaire = {
        "id": identifiant, "ville": ville, "hashtags": termes,
        "hashtags_croises": hashtags_croises, "operateur": operateur,
        "mode_territoire": mode_territoire, "region_code": region_code,
        "place_id": (reference["place_id"] if mode_territoire == "place_reference" else None),
        "statut_localisation": ("non_verifiee_recherche_textuelle"
                                if mode_territoire == "place_reference"
                                else "non_verifiee"),
        "date_debut": debut, "date_fin": fin,
        "periodes": periodes, "indice_periode": 0,
        "cursor": None, "search_id": None,
        "comptes": {}, "pages": 0, "candidats": 0,
        "terminee": False, "erreur": "", "version_requete": VERSION_REQUETE,
        "videos_ecartees": 0, "etat": "en_attente",
        "echecs_serveur": 0, "relances_serveur": 0,
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
        "hashtags": inventaire["hashtags"],
        "hashtags_croises": inventaire.get("hashtags_croises", []),
        "operateur": inventaire.get("operateur", "OR"),
        "mode_territoire": inventaire.get("mode_territoire", "texte"),
        "region_code": inventaire.get("region_code"),
        "place_id": inventaire.get("place_id"),
        "statut_localisation": inventaire.get("statut_localisation", "non_verifiee"),
        "date_debut": inventaire["date_debut"],
        "date_fin": inventaire["date_fin"], "pages": inventaire["pages"],
        "candidats": inventaire["candidats"],
        "terminee": (inventaire["terminee"] and inventaire.get("version_requete", 1) >= 2),
        "erreur": inventaire.get("erreur", ""),
        "ancienne_recherche": inventaire.get("version_requete", 1) < 2,
        "comptes": comptes, "nombre_comptes": len(comptes),
        "videos_ecartees": inventaire.get("videos_ecartees", 0),
        "echecs_serveur": inventaire.get("echecs_serveur", 0),
        "relances_serveur": inventaire.get("relances_serveur", 0),
        "etat": ("en_cours" if recherche_active(inventaire["id"])
                 else inventaire.get("etat", "en_attente")
                 if inventaire.get("etat") != "en_cours" else "interrompue"),
        "arret_demande": recherche_arret_demande(inventaire["id"]),
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
                "terminee": (objet.get("terminee", False)
                             and objet.get("version_requete", 1) >= 2),
                "etat": ("en_cours" if recherche_active(objet["id"])
                         else "interrompue"
                         if objet.get("etat") == "en_cours"
                         else objet.get("etat", "en_attente")),
                "arret_demande": recherche_arret_demande(objet["id"]),
            })
        except (KeyError, ValueError, OSError):
            continue
    return resultats


def poursuivre_inventaire(racine, proprietaire, identifiant, *, requete=_requete,
                         nombre_pages=None, arret=None, credentiels=None):
    """Parcourir les pages jusqu'à la fin ou à l'arrêt, avec checkpoint."""
    if nombre_pages is not None and not 1 <= nombre_pages <= 100000:
        raise ValueError("Nombre de pages invalide.")
    chemin = chemin_inventaire(racine, proprietaire, identifiant)
    inventaire = charger(racine, proprietaire, identifiant)
    # Les anciens inventaires utilisaient une requête limitée aux hashtags.
    # Leur curseur n'est pas réutilisable avec la requête keyword élargie.
    # Même les inventaires anciens marqués « terminés » doivent pouvoir repartir.
    if inventaire.get("version_requete", 1) < 2:
        inventaire["indice_periode"] = 0
        inventaire["cursor"] = None
        inventaire["search_id"] = None
        inventaire["terminee"] = False
        inventaire["erreur"] = ""
        inventaire["version_requete"] = VERSION_REQUETE
        inventaire["etat"] = "en_attente"
        sauvegarder(chemin, inventaire)
    if inventaire["terminee"]:
        return presenter(inventaire)
    inventaire["etat"] = "en_cours"
    sauvegarder(chemin, inventaire)
    # Le jeton provient des variables Coolify ; il n'est jamais persisté.
    try:
        token = _jeton(requete=requete, credentiels=credentiels)
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
            inventaire["cursor"], inventaire["search_id"],
            inventaire.get("hashtags_croises"), inventaire.get("operateur", "OR"),
            inventaire.get("mode_territoire", "texte"),
            inventaire.get("region_code"))
        try:
            resultat, token = interroger_page_avec_reprises(
                requete, corps, token, credentiels=credentiels,
                arret=arret, compteurs=inventaire)
            if resultat is None:
                inventaire["etat"] = "interrompue"
                break
            donnees = resultat.get("data") or {}
            videos = donnees.get("videos")
            if not isinstance(videos, list):
                raise ResearchErreur("TikTok n'a pas renvoyé de liste de vidéos.")
            compteurs = inventaire["comptes"]
            for video in videos:
                if not isinstance(video, dict):
                    continue
                # Une vidéo doit satisfaire les DEUX dimensions.
                mode = inventaire.get("mode_territoire", "texte")
                localisation_valide = (
                    str(video.get("region_code") or "").upper()
                    == inventaire.get("region_code")
                    if mode == "region_code"
                    else correspond_territoire(video, inventaire["hashtags"]))
                if (not localisation_valide
                        or not correspond_hashtags(
                            video, inventaire.get("hashtags_croises", []),
                            inventaire.get("operateur", "OR"))):
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
            inventaire["erreur"] = (
                str(erreur) + (
                    " Après quatre tentatives sur la même page. "
                    "La position de reprise a été conservée."
                    if isinstance(erreur, ResearchErreurServeur) else ""
                )
            )
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
    avec_reference = inventaire.get("mode_territoire") == "place_reference"
    entetes = ["territoire", "username", "url_compte", "videos_trouvees"]
    if avec_reference:
        entetes += ["place_id_reference", "statut_localisation"]
    writer.writerow(entetes)
    for compte in presenter(inventaire)["comptes"]:
        valeurs = [
            inventaire["ville"], compte["username"],
            "https://www.tiktok.com/" + compte["username"],
            compte["videos_trouvees"]]
        if avec_reference:
            valeurs += [inventaire.get("place_id", ""),
                        "non_verifiee_recherche_textuelle"]
        writer.writerow(valeurs)
    return sortie.getvalue().encode("utf-8-sig")


def exporter_txt(inventaire):
    """Produire un @compte par ligne pour le champ Profils."""
    return ("\n".join(
        ligne["username"] for ligne in presenter(inventaire)["comptes"]
    ) + "\n").encode("utf-8") if inventaire["comptes"] else b""
