"""Importer des CSV de commentaires et de vidéos pour la sociométrie.

Les identifiants restent textuels, les doublons sont repérés par (vidéo, commentaire)
et aucune relation d'auteur n'est inférée à partir des commentaires Research.
"""
import csv
import hashlib
import io
import re

from .reseaux import construire_reseau

MAX_FICHIER = 12_000_000
MAX_COMMENTAIRES = 100_000
MAX_VIDEOS = 100_000


def lire_csv(octets, nom):
    """Lire un CSV UTF-8 avec séparateur ;, virgule ou tabulation."""
    if not isinstance(octets, bytes) or len(octets) > MAX_FICHIER:
        raise ValueError(f"{nom} : fichier invalide ou supérieur à 12 Mo.")
    try:
        contenu = octets.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        raise ValueError(f"{nom} : encodage UTF-8 attendu.") from erreur
    if not contenu.strip():
        raise ValueError(f"{nom} : fichier vide.")
    try:
        dialecte = csv.Sniffer().sniff(contenu[:8192], delimiters=";,\t")
        separateur = dialecte.delimiter
    except csv.Error:
        separateur = ";" if ";" in contenu.splitlines()[0] else ","
    lecteur = csv.DictReader(io.StringIO(contenu), delimiter=separateur)
    colonnes = lecteur.fieldnames or []
    if not colonnes or len(colonnes) != len(set(colonnes)) or len(colonnes) > 200:
        raise ValueError(f"{nom} : entêtes absents, dupliqués ou trop nombreux.")
    resultats = []
    for numero, ligne in enumerate(lecteur, 2):
        if None in ligne:
            raise ValueError(f"{nom} : colonnes supplémentaires à la ligne {numero}.")
        resultats.append({cle: valeur or "" for cle, valeur in ligne.items()})
    return colonnes, resultats


def premier(donnees, *noms):
    """Retourner une cellule non vide sans transformer les identifiants."""
    for nom in noms:
        valeur = str(donnees.get(nom) or "").strip()
        if valeur:
            return valeur
    return ""


def preparer_import(fichiers_commentaires, fichiers_videos=()):
    """Fusionner les CSV, conserver les commentaires sans doublon et diagnostiquer."""
    if not fichiers_commentaires:
        raise ValueError("Importez au moins un fichier commentaires.csv.")
    commentaires = {}
    videos = {}
    diagnostics = []
    doublons = 0
    sans_id = 0
    lignes_lues = 0
    lignes_par_fichier = []
    parents_absents = 0
    conflits = 0
    for nom, contenu in fichiers_commentaires:
        colonnes, lignes = lire_csv(contenu, nom)
        if "publication_id" not in colonnes or "id" not in colonnes:
            raise ValueError(f"{nom} : colonnes id et publication_id nécessaires.")
        lignes_lues += len(lignes)
        lignes_par_fichier.append((nom, len(lignes)))
        for ligne in lignes:
            vid, cid = premier(ligne, "publication_id"), premier(ligne, "id")
            if not vid or not cid:
                sans_id += 1
                continue
            cle = (vid, cid)
            if cle in commentaires:
                doublons += 1
                if commentaires[cle] != ligne:
                    conflits += 1
                continue
            if len(commentaires) >= MAX_COMMENTAIRES:
                raise ValueError("Maximum de 100 000 commentaires distincts.")
            commentaires[cle] = {
                "id": cid,
                "publication_id": vid,
                "parent_id": premier(ligne, "parent_id", "parent_comment_id"),
                "source": premier(ligne, "source"),
                "auteur": premier(ligne, "auteur"),
                "texte": premier(ligne, "texte"),
            }
            videos.setdefault(vid, {"id": vid})
    for nom, contenu in fichiers_videos:
        colonnes, lignes = lire_csv(contenu, nom)
        identifiant = next((c for c in ("publication_id", "id", "id_", "video_id")
                            if c in colonnes), None)
        if not identifiant:
            raise ValueError(f"{nom} : colonne publication_id ou id nécessaire.")
        for ligne in lignes:
            vid = premier(ligne, identifiant)
            if not vid:
                continue
            if len(videos) >= MAX_VIDEOS and vid not in videos:
                raise ValueError("Maximum de 100 000 vidéos.")
            fiche = videos.setdefault(vid, {"id": vid})
            for cle in ("url", "legende", "vues", "likes", "commentaires",
                        "partages", "favoris", "taux_engagement",
                        "statut_resume_ia"):
                if ligne.get(cle) and not fiche.get(cle):
                    fiche[cle] = ligne[cle]
    for (vid, _), commentaire in commentaires.items():
        parent = commentaire["parent_id"]
        if parent and parent != "0" and (vid, parent) not in commentaires:
            parents_absents += 1
    sources_fiables = sum(
        1 for c in commentaires.values()
        if c["source"] == "page_visible" and re.fullmatch(
            r"[A-Za-z0-9_.]{2,30}", c["auteur"].lstrip("@") or "")
    )
    if doublons:
        diagnostics.append(f"{doublons} commentaire(s) en doublon ignoré(s).")
    if conflits:
        diagnostics.append(
            f"{conflits} doublon(s) comportent des valeurs divergentes : première occurrence conservée.")
    if sans_id:
        diagnostics.append(f"{sans_id} ligne(s) sans identifiants exclue(s).")
    if parents_absents:
        diagnostics.append(
            f"{parents_absents} réponse(s) pointent vers un commentaire parent non présent.")
    if not sources_fiables:
        diagnostics.append(
            "Aucun identifiant d'auteur issu d'une page visible : seuls les réseaux de réponses sont interprétables.")
    if not commentaires:
        details = "; ".join(
            f"{nom} : {nombre} ligne(s)" for nom, nombre in lignes_par_fichier)
        if lignes_lues == 0:
            raise ValueError(
                "Le ou les fichiers commentaires.csv contiennent uniquement "
                "les en-têtes : aucun commentaire n'a été exporté. "
                "Vérifiez dans les résultats de collecte que l'option "
                "Collecter les commentaires était activée et que TikTok "
                "a réellement renvoyé des commentaires. "
                f"Fichiers examinés : {details}. "
                "engagement.csv contient des publications et des métriques, "
                "mais ne permet pas de reconstruire les réponses entre commentaires.")
        raise ValueError(
            f"{lignes_lues} ligne(s) lue(s), mais aucune avec à la fois "
            "id (commentaire) et publication_id (vidéo). "
            f"{sans_id} ligne(s) sans ces identifiants. "
            f"Fichiers : {details}. "
            "Les identifiants manquants ne peuvent pas être inventés "
            "pour construire un réseau de réponses.")
    return {
        "commentaires": list(commentaires.values()),
        "publications": list(videos.values()),
        "diagnostics": diagnostics,
        "auteurs_candidats": sources_fiables,
        "doublons": doublons,
        "sans_id": sans_id,
        "parents_absents": parents_absents,
        "graine": hashlib.sha256(
            "\n".join(sorted(f"{v}:{c}" for v, c in commentaires)).encode()).hexdigest(),
    }


def analyser_import(donnees, mode, seuil=1):
    """Réutiliser exactement l'algorithme sociométrique existant."""
    reseau = construire_reseau(
        donnees["commentaires"], donnees["publications"],
        mode, donnees["graine"], seuil)
    reseau["diagnostics"] = [*donnees["diagnostics"], *reseau["diagnostics"]]
    metriques = {p["id"]: p for p in donnees["publications"]}
    for noeud in reseau["noeuds"]:
        if noeud["type"] == "video" and noeud["id"].startswith("video:"):
            video = metriques.get(noeud["id"][6:], {})
            for cle in ("url", "vues", "likes", "commentaires",
                        "partages", "favoris", "taux_engagement"):
                if video.get(cle):
                    noeud[cle] = video[cle]
    return reseau
