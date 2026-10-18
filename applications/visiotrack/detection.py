"""Détection, suivi et mesure de visibilité, indépendants de Streamlit."""

from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import tempfile
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse


# Ordre des 80 classes COCO utilisées par le modèle YOLO fourni.
CATEGORIES = dict(enumerate([
    "personne", "vélo", "voiture", "moto", "avion", "bus", "train", "camion",
    "bateau", "feu de circulation", "borne incendie", "panneau stop", "parcmètre",
    "banc", "oiseau", "chat", "chien", "cheval", "mouton", "vache", "éléphant",
    "ours", "zèbre", "girafe", "sac à dos", "parapluie", "sac à main", "cravate",
    "valise", "frisbee", "skis", "snowboard", "ballon", "cerf-volant",
    "batte de baseball", "gant de baseball", "skateboard", "planche de surf",
    "raquette de tennis", "bouteille", "verre à vin", "tasse", "fourchette",
    "couteau", "cuillère", "bol", "banane", "pomme", "sandwich", "orange",
    "brocoli", "carotte", "hot-dog", "pizza", "donut", "gâteau", "chaise",
    "canapé", "plante en pot", "lit", "table à manger", "toilettes",
    "téléviseur", "ordinateur portable", "souris", "télécommande", "clavier",
    "smartphone", "micro-ondes", "four", "grille-pain", "évier", "réfrigérateur",
    "livre", "horloge", "vase", "ciseaux", "ours en peluche", "sèche-cheveux",
    "brosse à dents",
]))

COLONNES_RESULTATS = [
    "video_id", "source", "statut", "erreur", "duree_totale_s", "categorie",
    "objet_detecte", "duree_visibilite_s", "pourcentage_visible",
    "maximum_simultane", "nombre_objets_distincts_estime",
    "frequence_demandee_ips", "images_analysees",
]
COLONNES_INTERVALLES = [
    "video_id", "categorie", "debut_s", "fin_s", "duree_s", "maximum_simultane",
]
COLONNES_DETECTIONS = [
    "video_id", "image", "horodatage_s", "categorie", "piste_id", "confiance",
    "x1", "y1", "x2", "y2", "plan_id", "objet_id",
]


def colonnes_resultats(quantifier_temps=True, compter_distincts=False):
    """Exporter seulement les mesures demandées, sans remplacer une absence par zéro."""
    exclues = set()
    if not quantifier_temps:
        exclues.update(("duree_visibilite_s", "pourcentage_visible"))
    if not compter_distincts:
        exclues.add("nombre_objets_distincts_estime")
    return [colonne for colonne in COLONNES_RESULTATS if colonne not in exclues]


@dataclass
class SourceVideo:
    """Référence légère : les octets des vidéos ne sont pas dupliqués."""

    nom: str
    type: str
    contenu: object
    membre: object = None
    erreur: str = ""


def texte_csv(valeur):
    """Neutraliser les formules des tableurs dans les noms fournis par l'utilisateur."""
    if isinstance(valeur, str) and valeur.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + valeur
    return valeur


def ouvrir_csv(chemin, colonnes):
    """Créer un CSV UTF-8 avec BOM, compatible avec les tableurs."""
    fichier = Path(chemin).open("w", encoding="utf-8-sig", newline="")
    redacteur = csv.DictWriter(fichier, fieldnames=colonnes)
    redacteur.writeheader()
    return fichier, redacteur


def inventorier_sources(fichiers, texte_urls, dossier=None):
    """Lister les MP4, y compris dans les sous-dossiers ZIP, sans les extraire."""
    sources = []
    for fichier in fichiers:
        if fichier.name.lower().endswith(".zip"):
            try:
                fichier.seek(0)
                with zipfile.ZipFile(fichier) as archive:
                    membres = [m for m in archive.infolist()
                               if not m.is_dir() and m.filename.lower().endswith(".mp4")
                               and not m.filename.startswith("__MACOSX/")]
                    if not membres:
                        raise ValueError("L'archive ne contient aucun fichier MP4.")
                    for membre in membres:
                        sources.append(SourceVideo(
                            f"{fichier.name} / {membre.filename}", "zip", fichier, membre))
            except (OSError, ValueError, zipfile.BadZipFile) as erreur:
                sources.append(SourceVideo(fichier.name, "erreur", None, erreur=str(erreur)))
        else:
            sources.append(SourceVideo(fichier.name, "fichier", fichier))
    # Éviter de télécharger deux fois une URL identique dans le même lot.
    for url in dict.fromkeys(texte_urls.splitlines()):
        if url.strip():
            sources.append(SourceVideo(url.strip(), "url", url.strip()))
    if dossier:
        racine = Path(dossier).resolve()
        if not racine.is_dir():
            sources.append(SourceVideo(str(racine), "erreur", None,
                                       erreur="Le dossier serveur est introuvable."))
        else:
            for chemin in sorted(racine.rglob("*")):
                # Ne pas suivre les liens menant hors du volume configuré.
                if (chemin.suffix.lower() == ".mp4" and chemin.is_file()
                        and chemin.resolve().is_relative_to(racine)):
                    sources.append(SourceVideo(str(chemin.relative_to(racine)), "serveur", chemin))
    return sources


def verifier_url(url):
    """Limiter l'import réseau aux URL publiques des deux plateformes annoncées."""
    adresse = urlparse(url)
    hote = (adresse.hostname or "").lower()
    autorise = any(hote == domaine or hote.endswith("." + domaine)
                   for domaine in ("youtube.com", "youtu.be", "tiktok.com"))
    if (adresse.scheme != "https" or not autorise or adresse.username
            or adresse.password or adresse.port not in (None, 443)):
        raise ValueError("Utilisez une URL HTTPS YouTube ou TikTok.")


def preparer_video(source, dossier):
    """Matérialiser une seule vidéo ; le dossier temporaire sera ensuite supprimé."""
    limite = int(os.getenv("VISIOTRACK_MAX_VIDEO_MB", "4096")) * 1024 * 1024
    if source.erreur:
        raise ValueError(source.erreur)
    if source.type == "serveur":
        if source.contenu.stat().st_size > limite:
            raise ValueError("Vidéo trop volumineuse pour la limite du serveur.")
        return source.contenu
    cible = Path(dossier) / "video.mp4"
    if source.type == "url":
        from yt_dlp import YoutubeDL

        verifier_url(source.contenu)

        def surveiller_telechargement(etat):
            """Arrêter un téléchargement qui dépasse la limite, même sans taille annoncée."""
            if etat.get("downloaded_bytes", 0) > limite:
                raise ValueError("Téléchargement trop volumineux.")

        options = {
            "outtmpl": str(Path(dossier) / "video.%(ext)s"),
            "format": ("bestvideo[ext=mp4][vcodec^=avc1][height<=1080]/"
                       "best[ext=mp4][height<=1080]/bestvideo[height<=1080]/"
                       "best[height<=1080]/best"),
            "noplaylist": True, "playlistend": 1, "quiet": True, "no_warnings": True,
            "socket_timeout": 30, "retries": 2, "max_filesize": limite,
            "progress_hooks": [surveiller_telechargement],
        }
        with YoutubeDL(options) as outil:
            informations = outil.extract_info(source.contenu, download=False)
            if (not informations or informations.get("is_live")
                    or informations.get("_type") in ("playlist", "multi_video")):
                raise ValueError("Fournissez une vidéo disponible, hors direct et hors playlist.")
            informations = outil.process_ie_result(informations, download=True)
            cible = Path(outil.prepare_filename(informations))
        if not cible.is_file() or cible.stat().st_size > limite:
            raise ValueError("Téléchargement incomplet ou trop volumineux.")
        return cible

    def copier_limite(entree):
        """Copier par blocs, sans charger un MP4 ou une archive entière en mémoire."""
        total = 0
        with cible.open("wb") as sortie:
            while bloc := entree.read(1024 * 1024):
                total += len(bloc)
                if total > limite:
                    raise ValueError("Vidéo trop volumineuse pour la limite du serveur.")
                sortie.write(bloc)

    source.contenu.seek(0)
    if source.type == "zip":
        if source.membre.file_size > limite:
            raise ValueError("Vidéo décompressée trop volumineuse.")
        # Le nom du membre n'est jamais utilisé comme chemin d'extraction : même
        # ../../video.mp4 reste contenu dans le répertoire temporaire de ce travail.
        with zipfile.ZipFile(source.contenu) as archive:
            with archive.open(source.membre) as entree:
                copier_limite(entree)
    else:
        copier_limite(source.contenu)
    return cible


def lire_metadonnees(chemin):
    """Lire la durée de la piste vidéo, sans confondre sa durée avec celle du son."""
    try:
        execution = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=duration,nb_frames,avg_frame_rate:format=duration",
            "-of", "json", str(chemin),
        ], capture_output=True, text=True, timeout=60, check=True)
    except FileNotFoundError as erreur:
        raise ValueError("FFmpeg/ffprobe doit être installé sur le serveur.") from erreur
    except subprocess.TimeoutExpired as erreur:
        raise ValueError("La lecture des métadonnées a dépassé 60 secondes.") from erreur
    except subprocess.CalledProcessError as erreur:
        raise ValueError("Fichier vidéo illisible ou corrompu (échec de ffprobe).") from erreur
    donnees = json.loads(execution.stdout)
    if not donnees.get("streams"):
        raise ValueError("Aucune piste vidéo lisible.")
    piste = donnees["streams"][0]
    duree = float(piste.get("duration") or donnees.get("format", {}).get("duration", 0))
    if not math.isfinite(duree) or duree <= 0:
        raise ValueError("La durée de la vidéo est inconnue ou invalide.")
    nombre = piste.get("nb_frames", "")
    return duree, int(nombre) if nombre.isdigit() else None


def charger_modele():
    """Charger une seule fois par lot YOLO11s, exclusivement sur CPU."""
    from ultralytics import YOLO
    import torch

    torch.set_num_threads(max(1, int(os.getenv("VISIOTRACK_CPU_THREADS", "2"))))
    chemin = Path(os.getenv("VISIOTRACK_MODEL", str(Path.home() / ".cache/visiotrack/yolo11s.pt")))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    return YOLO(str(chemin))


class MesureVisibilite:
    """Union temporelle par catégorie : plusieurs pistes ne multiplient pas la durée."""

    def __init__(self, categories, ecrire_intervalle):
        self.categories = categories
        self.ecrire_intervalle = ecrire_intervalle
        self.durees = dict.fromkeys(categories, 0.0)
        self.maximums = dict.fromkeys(categories, 0)
        self.ouverts = {}

    def ajouter(self, debut, fin, effectifs):
        """Ajouter une plage représentée par une image, en fermant toute absence."""
        if fin <= debut:
            return
        for categorie in self.categories:
            nombre = effectifs.get(categorie, 0)
            if nombre:
                self.durees[categorie] += fin - debut
                self.maximums[categorie] = max(self.maximums[categorie], nombre)
                if categorie not in self.ouverts:
                    self.ouverts[categorie] = [debut, fin, nombre]
                else:
                    self.ouverts[categorie][1] = fin
                    self.ouverts[categorie][2] = max(self.ouverts[categorie][2], nombre)
            else:
                self.fermer(categorie)

    def fermer(self, categorie):
        """Écrire immédiatement un intervalle fini, sans accumuler une longue liste."""
        if categorie in self.ouverts:
            debut, fin, maximum = self.ouverts.pop(categorie)
            self.ecrire_intervalle({"categorie": CATEGORIES[categorie], "debut_s": debut,
                                   "fin_s": fin, "duree_s": fin - debut,
                                   "maximum_simultane": maximum})

    def terminer(self):
        """Fermer les catégories encore présentes à la fin de la vidéo."""
        for categorie in list(self.ouverts):
            self.fermer(categorie)


def creer_suivis(categories, frequence):
    """Créer des ByteTrack neufs par vidéo et catégorie pour éviter les mélanges."""
    from ultralytics.trackers.byte_tracker import BYTETracker

    parametres = SimpleNamespace(track_high_thresh=0.25, track_low_thresh=0.1,
                                new_track_thresh=0.25, track_buffer=30,
                                match_thresh=0.8, fuse_score=True)
    # Le tampon conserve environ une seconde de pistes perdues. Ces pistes
    # prédites ne contribuent jamais aux durées ni aux comptages observés.
    return {categorie: BYTETracker(parametres, frame_rate=frequence)
            for categorie in categories}


def iterer_vues_smartphone(image):
    """Examiner les détails puis les deux orientations, une vue à la fois sur CPU."""
    import cv2

    hauteur, largeur = image.shape[:2]
    cote = min(hauteur, largeur)
    # Sur une vidéo verticale, les trois carrés couvrent haut, centre et bas.
    # Sur une vidéo horizontale, ils couvrent gauche, centre et droite.
    if max(hauteur, largeur) > cote * 1.2:
        ecart = max(hauteur, largeur) - cote
        for decalage in sorted({0, ecart // 2, ecart}):
            x, y = (0, decalage) if hauteur > largeur else (decalage, 0)
            yield image[y:y + cote, x:x + cote], (x, y, None)
    for rotation in (cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_90_COUNTERCLOCKWISE):
        yield cv2.rotate(image, rotation), (0, 0, rotation)


def reprojeter_boites(boites, transformation, dimensions):
    """Replacer les coordonnées d'un recadrage ou d'une rotation dans la vidéo."""
    import cv2

    resultat = boites.copy()
    x, y, rotation = transformation
    hauteur, largeur = dimensions[:2]
    if rotation == cv2.ROTATE_90_CLOCKWISE:
        resultat[:, 0], resultat[:, 2] = boites[:, 1], boites[:, 3]
        resultat[:, 1], resultat[:, 3] = hauteur - boites[:, 2], hauteur - boites[:, 0]
    elif rotation == cv2.ROTATE_90_COUNTERCLOCKWISE:
        resultat[:, 0], resultat[:, 2] = largeur - boites[:, 3], largeur - boites[:, 1]
        resultat[:, 1], resultat[:, 3] = boites[:, 0], boites[:, 2]
    else:
        resultat[:, (0, 2)] += x
        resultat[:, (1, 3)] += y
    resultat[:, (0, 2)] = resultat[:, (0, 2)].clip(0, largeur)
    resultat[:, (1, 3)] = resultat[:, (1, 3)].clip(0, hauteur)
    return resultat


def supprimer_cadres_imbriques(boites):
    """Éviter de compter un détail du téléphone comme un deuxième téléphone.

    Compléter la NMS de YOLO pour les boîtes dont plus de 90 % de la plus petite
    sont contenus dans l'autre. Prioriser les détections acceptées, puis leur aire.
    """
    import numpy as np

    if len(boites) < 2:
        return boites
    aires = (boites[:, 2] - boites[:, 0]) * (boites[:, 3] - boites[:, 1])
    ordre = sorted(range(len(boites)), key=lambda i: (boites[i, 4] >= 0.25, aires[i]), reverse=True)
    conserves = []
    for indice in ordre:
        doublon = False
        for precedent in conserves:
            coin1 = np.maximum(boites[indice, :2], boites[precedent, :2])
            coin2 = np.minimum(boites[indice, 2:4], boites[precedent, 2:4])
            intersection = np.maximum(0, coin2 - coin1).prod()
            if intersection / max(1e-8, min(aires[indice], aires[precedent])) > 0.9:
                doublon = True
                break
        if not doublon:
            conserves.append(indice)
    return boites[sorted(conserves)]


def detecter_image(modele, suivis, image, categories):
    """Associer les boîtes observées à ByteTrack sans supprimer les nouvelles pistes."""
    import numpy as np
    from ultralytics.engine.results import Boxes

    resultat = modele.predict(image, classes=categories, conf=0.1, iou=0.5,
                              imgsz=640, max_det=1000, device="cpu", verbose=False)[0]
    boites = resultat.boxes.cpu().numpy()
    if 67 in categories:
        telephones = boites.data[boites.cls == 67]
        if not any(telephones[:, 4] >= 0.25):
            # Un téléphone vu de côté ou petit dans une vidéo verticale peut être
            # manqué sur l'image entière. Arrêter dès qu'une vue le retrouve :
            # aucune somme des vues, aucune présence inventée par interpolation.
            for vue, transformation in iterer_vues_smartphone(image):
                rappel = modele.predict(vue, classes=[67], conf=0.25, iou=0.5,
                                        imgsz=640, max_det=1000, device="cpu", verbose=False)[0]
                candidates = rappel.boxes.cpu().numpy().data
                candidates = candidates[candidates[:, 4] >= 0.25]
                if len(candidates):
                    telephones = reprojeter_boites(candidates, transformation, image.shape)
                    break
        telephones = supprimer_cadres_imbriques(telephones)
        boites = Boxes(np.concatenate((boites.data[boites.cls != 67], telephones)), image.shape[:2])
    detections = []
    for categorie in categories:
        selection = boites[boites.cls == categorie]
        pistes = suivis[categorie].update(selection, image)
        # ByteTrack fournit l'indice de la boîte en dernière colonne. Conserver
        # aussi les nouvelles pistes provisoires : leur confirmation ultérieure
        # ne doit pas faire compter une seconde fois le même objet.
        identifiants = {int(piste[-1]): int(piste[4]) for piste in pistes}
        identifiants.update({int(piste.idx): int(piste.track_id)
                             for piste in suivis[categorie].tracked_stracks
                             if piste.frame_id == suivis[categorie].frame_id})
        for indice, boite in enumerate(selection):
            confiance = float(boite.conf[0])
            if confiance < 0.25:
                continue
            coordonnees = boite.xyxy[0].tolist()
            detections.append({"categorie_id": categorie,
                               "piste_id": identifiants.get(indice, ""),
                               "confiance": confiance,
                               **dict(zip(("x1", "y1", "x2", "y2"), coordonnees))})
    return detections


def dessiner_detections(image, detections):
    """Dessiner les boîtes et libellés sur une copie, sans modifier l'image source."""
    import cv2

    hauteur, largeur = image.shape[:2]
    facteur = min(1.0, 960 / max(largeur, hauteur))
    dimensions = (max(2, int(largeur * facteur) // 2 * 2),
                  max(2, int(hauteur * facteur) // 2 * 2))
    apercu = cv2.resize(image, dimensions)
    for detection in detections:
        x1, x2 = [max(0, min(dimensions[0] - 1, round(detection[cle] * dimensions[0] / largeur)))
                  for cle in ("x1", "x2")]
        y1, y2 = [max(0, min(dimensions[1] - 1, round(detection[cle] * dimensions[1] / hauteur)))
                  for cle in ("y1", "y2")]
        couleur = (70, 220, 70)
        cv2.rectangle(apercu, (x1, y1), (x2, y2), couleur, 2)
        # La police intégrée à OpenCV ne gère pas les accents français.
        categorie = CATEGORIES[detection["categorie_id"]]
        libelle = unicodedata.normalize("NFKD", categorie).encode("ascii", "ignore").decode()
        if detection.get("objet_id"):
            libelle += f" #{detection['objet_id']}"
        # Afficher le score de confiance entre 0 et 1, avec une virgule française.
        confiance_affichee = f"{detection['confiance']:.2f}".replace(".", ",")
        libelle += f" {confiance_affichee}"
        largeur_texte = cv2.getTextSize(libelle, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0][0]
        position = (max(0, min(x1, dimensions[0] - largeur_texte - 3)),
                    min(dimensions[1] - 3, max(16, y1 - 6)))
        cv2.putText(apercu, libelle, position, cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(apercu, libelle, position, cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, couleur, 1, cv2.LINE_AA)
    return apercu


def reduire_image_continuite(image):
    """Préparer une petite image pour vérifier le plan sans nouvelle inférence YOLO."""
    import cv2

    return cv2.GaussianBlur(cv2.resize(image, (160, 90), interpolation=cv2.INTER_AREA), (5, 5), 0)


def plan_a_change(precedente, actuelle):
    """Détecter une rupture visuelle étendue, plutôt que le seul mouvement d'une main.

    Comparer les couleurs et la structure spatiale sur des miniatures lissées.
    Une forte variation d'éclairage peut aussi effacer un cadre, par prudence.
    Ces seuils sont fixes : aucune nouvelle option technique dans l'interface.
    """
    import cv2
    import numpy as np

    if precedente is None:
        return False
    difference = cv2.absdiff(precedente, actuelle).mean(axis=2)
    moyenne = float(difference.mean())
    if moyenne >= 24 and float((difference >= 30).mean()) >= 0.45:
        return True
    # Une coupe dans un décor aux couleurs proches peut surtout changer les formes.
    if moyenne >= 12:
        ancien_gris = cv2.cvtColor(precedente, cv2.COLOR_BGR2GRAY).astype(np.float32)
        nouveau_gris = cv2.cvtColor(actuelle, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ancien_gris -= ancien_gris.mean()
        nouveau_gris -= nouveau_gris.mean()
        norme = float(np.linalg.norm(ancien_gris) * np.linalg.norm(nouveau_gris))
        if norme > 1e-6 and float((ancien_gris * nouveau_gris).sum()) / norme < 0.55:
            return True
    return False


def creer_video_annotee(chemin, observations, destination, duree,
                       progression=lambda valeur: None):
    """Encoder un MP4 H.264 lisible dans le navigateur, sans relancer YOLO.

    Les boîtes ne survivent pas à une rupture de plan détectée. Elles restent
    masquées jusqu'à une nouvelle observation positive, même si l'ancien plan
    revient. Une observation vide les efface aussi. La cadence variable du média est
    convertie à 25 images/s en conservant sa chronologie et sa piste audio éventuelle.
    Seules deux images décodées et une observation sont gardées en mémoire.
    """
    import cv2

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    partiel = destination.with_suffix(".part.mp4")
    capture = cv2.VideoCapture(str(chemin))
    encodeur = None
    try:
        succes, precedente = capture.read()
        if not succes:
            raise ValueError("Impossible de relire la vidéo pour créer l'aperçu.")
        precedent_s = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        hauteur, largeur = dessiner_detections(precedente, []).shape[:2]
        with Path(observations).open(encoding="utf-8") as entree, tempfile.TemporaryFile() as erreurs:
            encodeur = subprocess.Popen([
                "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pixel_format", "bgr24",
                "-video_size", f"{largeur}x{hauteur}", "-framerate", "25", "-i", "pipe:0",
                "-i", str(chemin), "-map", "0:v:0", "-map", "1:a:0?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                "-threads", os.getenv("VISIOTRACK_CPU_THREADS", "2"),
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                "-t", str(duree), "-movflags", "+faststart", str(partiel),
            ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=erreurs)
            prochaine = json.loads(ligne) if (ligne := entree.readline()) else None
            detections = []
            numero_sortie = 0
            miniature_precedente = None
            reference_plan = None
            derniere_rupture_s = -1.0

            def encoder_plage(image, horodatage, fin):
                """Répéter une image jusqu'au prochain horodatage, sans accélérer le média."""
                nonlocal prochaine, detections, numero_sortie
                nonlocal miniature_precedente, reference_plan, derniere_rupture_s
                miniature = reduire_image_continuite(image)
                # Comparer chaque image source, même entre deux analyses à 1 Hz.
                # La référence permet aussi d'effacer le cadre après un déplacement
                # progressif mais important de la caméra depuis la détection.
                if (plan_a_change(miniature_precedente, miniature)
                        or (reference_plan is not None and plan_a_change(reference_plan, miniature))):
                    detections = []
                    reference_plan = None
                    derniere_rupture_s = horodatage
                miniature_precedente = miniature
                while prochaine is not None and prochaine["horodatage_s"] <= horodatage + 1e-8:
                    # Une détection sur l'image exacte de la coupe est valable ;
                    # une ancienne détection ne peut jamais ressusciter son cadre.
                    if prochaine["horodatage_s"] >= derniere_rupture_s - 1e-8:
                        detections = prochaine["detections"]
                        reference_plan = miniature if detections else None
                    prochaine = json.loads(ligne) if (ligne := entree.readline()) else None
                if numero_sortie / 25 < fin - 1e-8:
                    pixels = dessiner_detections(image, detections).tobytes()
                    while numero_sortie / 25 < fin - 1e-8:
                        encodeur.stdin.write(pixels)
                        numero_sortie += 1

            while True:
                succes, image = capture.read()
                if not succes:
                    break
                horodatage = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
                encoder_plage(precedente, precedent_s, min(horodatage, duree))
                precedente, precedent_s = image, horodatage
                progression(min(horodatage / duree, 0.999))
            encoder_plage(precedente, precedent_s, duree)
            encodeur.stdin.close()
            if encodeur.wait(timeout=60) != 0:
                raise ValueError("L'encodage de l'aperçu vidéo a échoué.")
        partiel.replace(destination)
        progression(1.0)
    finally:
        capture.release()
        if encodeur is not None:
            if encodeur.poll() is None:
                encodeur.kill()
            encodeur.wait()
            if encodeur.stdin is not None and not encodeur.stdin.closed:
                try:
                    encodeur.stdin.close()
                except BrokenPipeError:
                    pass
        partiel.unlink(missing_ok=True)


def analyser_video(chemin, video_id, nom, categories, frequence, modele,
                   dossier, progression=lambda valeur: None, *,
                   quantifier_temps=True, compter_distincts=False):
    """Décoder séquentiellement ; échantillonner sur les horodatages réels du MP4."""
    import cv2

    if not categories or not math.isfinite(frequence) or frequence <= 0:
        raise ValueError("Sélectionnez au moins une catégorie et une fréquence positive.")
    if not quantifier_temps and not compter_distincts:
        raise ValueError("Cochez au moins une mesure à quantifier.")
    duree, images_attendues = lire_metadonnees(chemin)
    suivis = creer_suivis(categories, frequence)
    capture = cv2.VideoCapture(str(chemin))
    if not capture.isOpened():
        capture.release()
        raise ValueError("Impossible d'ouvrir cette vidéo.")
    fichier_intervalles, redacteur_intervalles = ouvrir_csv(
        Path(dossier) / "intervalles.csv", COLONNES_INTERVALLES)
    fichier_detections, redacteur_detections = ouvrir_csv(
        Path(dossier) / "detections.csv", COLONNES_DETECTIONS)

    def ecrire_intervalle(ligne):
        """Associer chaque intervalle à la vidéo, avec une précision non arrondie."""
        redacteur_intervalles.writerow({"video_id": video_id, **ligne})

    mesure = MesureVisibilite(categories, ecrire_intervalle)
    maximums = Counter()
    nombres_distincts = Counter()
    identifiants_objets = {}
    plan_id = 1
    miniature_precedente = None
    reinitialiser_suivi = False
    precedent = None
    debut_echantillon = 0.0
    effectifs = Counter()
    prochaine_cible = 0.0
    images_lues = images_analysees = 0
    # Conserver aussi les observations vides : elles font disparaître les cadres
    # dans l'aperçu, contrairement au CSV qui ne contient que les détections.
    observations = (Path(dossier) / "observations.jsonl").open("w", encoding="utf-8")
    try:
        while capture.grab():
            horodatage = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if (not math.isfinite(horodatage) or horodatage < 0
                    or (precedent is not None and horodatage <= precedent)):
                raise ValueError("Horodatages vidéo invalides : réencodez ce fichier en MP4.")
            precedent = horodatage
            images_lues += 1
            if horodatage >= duree:
                raise ValueError("La durée annoncée ne correspond pas aux horodatages vidéo.")
            image = None
            if compter_distincts:
                # Vérifier toutes les images pour voir une coupe entre deux
                # analyses YOLO, sans lancer davantage d'inférences.
                succes, image = capture.retrieve()
                if not succes:
                    raise ValueError("Une image ne peut pas être décodée.")
                miniature = reduire_image_continuite(image)
                if plan_a_change(miniature_precedente, miniature):
                    plan_id += 1
                    reinitialiser_suivi = True
                miniature_precedente = miniature
            if horodatage + 1e-8 < prochaine_cible:
                continue
            if image is None:
                succes, image = capture.retrieve()
                if not succes:
                    raise ValueError("Une image sélectionnée ne peut pas être décodée.")
            if reinitialiser_suivi:
                # Ne pas associer deux appareils à la même position dans des
                # plans différents. La réidentification entre plans n'est pas garantie.
                suivis = creer_suivis(categories, frequence)
                identifiants_objets.clear()
                reinitialiser_suivi = False
            if quantifier_temps and images_analysees:
                mesure.ajouter(debut_echantillon, horodatage, effectifs)
            # Le tout premier échantillon représente le début du média à t=0.
            debut_echantillon = horodatage if images_analysees else 0.0
            detections = detecter_image(modele, suivis, image, categories)
            effectifs = Counter(d["categorie_id"] for d in detections)
            for categorie, nombre in effectifs.items():
                maximums[categorie] = max(maximums[categorie], nombre)
            for detection in detections:
                categorie = detection["categorie_id"]
                if compter_distincts:
                    piste = detection["piste_id"]
                    # Une boîte sans association ne prouve aucune identité : la
                    # compter séparément, sans fusion arbitraire avec un téléphone voisin.
                    cle = (categorie, piste) if piste != "" else object()
                    if cle not in identifiants_objets:
                        nombres_distincts[categorie] += 1
                        identifiants_objets[cle] = f"{categorie}-{nombres_distincts[categorie]}"
                    detection.update(plan_id=plan_id, objet_id=identifiants_objets[cle])
                redacteur_detections.writerow({"video_id": video_id, "image": images_lues - 1,
                                               "horodatage_s": horodatage,
                                               "categorie": CATEGORIES[categorie],
                                               **{cle: valeur for cle, valeur in detection.items()
                                                  if cle != "categorie_id"}})
            observations.write(json.dumps({"horodatage_s": horodatage, "detections": detections}) + "\n")
            images_analysees += 1
            prochaine_cible = (math.floor((horodatage + 1e-8) * frequence) + 1) / frequence
            progression(min(horodatage / duree, 0.999))
        if not images_analysees:
            raise ValueError("Aucune image n'a pu être décodée.")
        if images_attendues and images_lues != images_attendues:
            raise ValueError(f"Vidéo incomplète : {images_lues}/{images_attendues} images lisibles.")
        # Sans nombre d'images fiable, refuser une fin prématurée manifeste.
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not images_attendues and duree - precedent > max(1.0, 2 / fps if fps > 0 else 1.0):
            raise ValueError("Décodage interrompu avant la fin annoncée de la vidéo.")
        if quantifier_temps:
            mesure.ajouter(debut_echantillon, duree, effectifs)
            mesure.terminer()
        progression(1.0)
    finally:
        capture.release()
        fichier_intervalles.close()
        fichier_detections.close()
        observations.close()
    return [{"video_id": video_id, "source": texte_csv(nom), "statut": "ok", "erreur": "",
             "duree_totale_s": duree, "categorie": CATEGORIES[categorie],
             "objet_detecte": maximums[categorie] > 0,
             **({"duree_visibilite_s": min(duree, mesure.durees[categorie]),
                 "pourcentage_visible": min(100.0, mesure.durees[categorie] / duree * 100)}
                if quantifier_temps else {}),
             "maximum_simultane": maximums[categorie],
             **({"nombre_objets_distincts_estime": nombres_distincts[categorie]}
                if compter_distincts else {}),
             "frequence_demandee_ips": frequence, "images_analysees": images_analysees}
            for categorie in categories]


def traiter_lot(sources, categories, frequence, dossier, progression=lambda *args: None, *,
                quantifier_temps=True, compter_distincts=False):
    """Traiter un fichier à la fois et continuer après une erreur individuelle."""
    from contextlib import ExitStack

    if not quantifier_temps and not compter_distincts:
        raise ValueError("Cochez au moins une mesure à quantifier.")
    modele = charger_modele()
    resultats = []
    apercus = {}
    with ExitStack() as pile:
        sorties = {}
        for nom, colonnes in (("resultats", colonnes_resultats(quantifier_temps, compter_distincts)),
                              ("intervalles", COLONNES_INTERVALLES),
                              ("detections", COLONNES_DETECTIONS)):
            fichier, redacteur = ouvrir_csv(Path(dossier) / f"{nom}.csv", colonnes)
            pile.enter_context(fichier)
            sorties[nom] = redacteur
        for numero, source in enumerate(sources, 1):
            video_id = f"v{numero:06d}"
            progression(numero, len(sources), source.nom, 0.0)
            try:
                with tempfile.TemporaryDirectory(prefix="video-", dir=dossier) as temporaire:
                    chemin = preparer_video(source, temporaire)
                    lignes = analyser_video(
                        chemin, video_id, source.nom, categories, frequence, modele, temporaire,
                        lambda valeur: progression(numero, len(sources), source.nom, valeur * 0.7),
                        quantifier_temps=quantifier_temps, compter_distincts=compter_distincts)
                    # Une vidéo en erreur ne laisse jamais d'intervalles partiels
                    # dans les exports communs au lot.
                    for nom in ("intervalles", "detections"):
                        with (Path(temporaire) / f"{nom}.csv").open(encoding="utf-8-sig", newline="") as entree:
                            sorties[nom].writerows(csv.DictReader(entree))
                    try:
                        creer_video_annotee(
                            chemin, Path(temporaire) / "observations.jsonl",
                            Path(dossier) / "apercus" / f"{video_id}.mp4",
                            lignes[0]["duree_totale_s"],
                            lambda valeur: progression(numero, len(sources),
                                                       f"Création de l'aperçu : {source.nom}",
                                                       0.7 + valeur * 0.3))
                        apercus[video_id] = {"fichier": f"apercus/{video_id}.mp4"}
                    except Exception:
                        # Un échec d'encodage ne remet pas en cause les mesures CSV.
                        apercus[video_id] = {"erreur": "L'aperçu vidéo n'a pas pu être créé. Les mesures restent disponibles."}
            except Exception as erreur:
                lignes = [{"video_id": video_id, "source": texte_csv(source.nom),
                           "statut": "erreur", "erreur": texte_csv(str(erreur)),
                           "frequence_demandee_ips": frequence}]
            sorties["resultats"].writerows(lignes)
            resultats.extend(lignes)
            progression(numero, len(sources), source.nom, 1.0)
    (Path(dossier) / "apercus.json").write_text(json.dumps(apercus), encoding="utf-8")
    return resultats
