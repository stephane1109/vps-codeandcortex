"""Montage comparatif de quatre vidéos, sans modifier les analyses CSV existantes."""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path

from detection import SourceVideo, charger_modele, lire_metadonnees, preparer_video, verifier_url


LARGEUR_CASE = 960
HAUTEUR_CASE = 540
CADENCE_SORTIE = 15


def extraire_telephones(modele, image):
    """Localiser les téléphones visibles avec le modèle YOLO de la branche déployée."""
    resultat = modele.predict(image, classes=[67], conf=0.25, iou=0.5,
                              imgsz=640, max_det=1000, device="cpu", verbose=False)[0]
    return [tuple(int(round(float(valeur))) for valeur in boite.xyxy[0])
            for boite in resultat.boxes]


def annoter_video(chemin_source, chemin_sortie, modele, frequence=5.0,
                   progression=lambda valeur: None):
    """Produire une case 960 × 540 sans audio, avec boîtes et compteur actualisés."""
    import cv2
    import numpy as np

    if not math.isfinite(frequence) or frequence <= 0 or frequence > CADENCE_SORTIE:
        raise ValueError("La fréquence doit être comprise entre 0 et 15 images/s.")
    duree, _ = lire_metadonnees(chemin_source)
    filtre = (f"fps={CADENCE_SORTIE},"
              f"scale={LARGEUR_CASE}:{HAUTEUR_CASE}:force_original_aspect_ratio=decrease,"
              f"pad={LARGEUR_CASE}:{HAUTEUR_CASE}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1")
    commande_lecture = [
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i", str(chemin_source),
        "-map", "0:v:0", "-vf", filtre, "-f", "rawvideo", "-pix_fmt", "bgr24", "pipe:1",
    ]
    commande_ecriture = [
        "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo",
        "-pix_fmt", "bgr24", "-video_size", f"{LARGEUR_CASE}x{HAUTEUR_CASE}",
        "-framerate", str(CADENCE_SORTIE), "-i", "pipe:0", "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(chemin_sortie),
    ]
    octets_image = LARGEUR_CASE * HAUTEUR_CASE * 3
    pas_detection = max(1, round(CADENCE_SORTIE / frequence))
    lecteur = subprocess.Popen(commande_lecture, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    encodeur = None
    succes = False
    try:
        encodeur = subprocess.Popen(commande_ecriture, stdin=subprocess.PIPE,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        numero_image = 0
        boites = []
        while True:
            contenu = lecteur.stdout.read(octets_image)
            if not contenu:
                break
            if len(contenu) != octets_image:
                raise ValueError("Une image n'a pas pu être décodée intégralement.")
            image = np.frombuffer(contenu, dtype=np.uint8).reshape(
                (HAUTEUR_CASE, LARGEUR_CASE, 3)).copy()
            if numero_image % pas_detection == 0:
                boites = extraire_telephones(modele, image)
            for x1, y1, x2, y2 in boites:
                cv2.rectangle(image, (x1, y1), (x2, y2), (0, 230, 255), 2)
            # Afficher le compteur uniquement, sans titre de scène.
            libelle = f"Smartphones : {len(boites)}"
            cv2.rectangle(image, (10, 10), (214, 47), (0, 0, 0), -1)
            cv2.putText(image, libelle, (19, 36), cv2.FONT_HERSHEY_SIMPLEX,
                        0.68, (255, 255, 255), 2, cv2.LINE_AA)
            encodeur.stdin.write(image.tobytes())
            numero_image += 1
            if numero_image % CADENCE_SORTIE == 0:
                progression(min(numero_image / (duree * CADENCE_SORTIE), 0.99))
        if numero_image == 0:
            raise ValueError("Aucune image vidéo exploitable.")
        encodeur.stdin.close()
        if lecteur.wait() != 0 or encodeur.wait() != 0:
            raise ValueError("FFmpeg n'a pas pu décoder ou encoder cette vidéo.")
        if not Path(chemin_sortie).is_file() or Path(chemin_sortie).stat().st_size == 0:
            raise ValueError("La vidéo annotée n'a pas été produite.")
        progression(1.0)
        succes = True
    finally:
        lecteur.stdout.close()
        if lecteur.poll() is None:
            lecteur.terminate()
            lecteur.wait()
        if encodeur is not None:
            if encodeur.stdin is not None and not encodeur.stdin.closed:
                encodeur.stdin.close()
            if encodeur.poll() is None:
                encodeur.terminate()
            encodeur.wait()
        if not succes:
            Path(chemin_sortie).unlink(missing_ok=True)


def assembler_quatre_videos(chemins, sortie):
    """Composer quatre cases en 2 × 2 et figer les cases terminées."""
    if len(chemins) != 4:
        raise ValueError("Le montage requiert exactement quatre vidéos.")
    durees = [lire_metadonnees(chemin)[0] for chemin in chemins]
    duree_max = max(durees)
    commandes = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for chemin in chemins:
        commandes.extend(["-i", str(chemin)])
    filtres = []
    for indice, duree in enumerate(durees):
        # Prolonger la dernière image jusqu'à la fin de la vidéo la plus longue.
        prolongation = max(0.0, duree_max - duree) + 1.0 / CADENCE_SORTIE
        filtres.append(f"[{indice}:v]setpts=PTS-STARTPTS,"
                       f"tpad=stop_mode=clone:stop_duration={prolongation:.6f}[v{indice}]")
    filtres.append("[v0][v1][v2][v3]xstack=inputs=4:"
                   f"layout=0_0|{LARGEUR_CASE}_0|0_{HAUTEUR_CASE}|"
                   f"{LARGEUR_CASE}_{HAUTEUR_CASE},format=yuv420p[montage]")
    commandes.extend([
        "-filter_complex", ";".join(filtres), "-map", "[montage]", "-an",
        "-t", f"{duree_max:.6f}", "-r", str(CADENCE_SORTIE),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(sortie),
    ])
    resultat = subprocess.run(commandes, capture_output=True, text=True, timeout=None)
    if resultat.returncode != 0:
        raise ValueError(f"Échec de l'assemblage FFmpeg : {resultat.stderr[-1500:]}")
    if not Path(sortie).is_file() or Path(sortie).stat().st_size == 0:
        raise ValueError("Le montage MP4 est absent.")
    return duree_max


def creer_montage(urls, dossier, frequence=5.0, progression=lambda *args: None):
    """Charger, annoter puis assembler quatre URL publiques YouTube ou TikTok."""
    if len(urls) != 4 or any(not url.strip() for url in urls):
        raise ValueError("Renseignez les quatre URL vidéo.")
    for url in urls:
        verifier_url(url.strip())
    racine = Path(dossier)
    racine.mkdir(parents=True, exist_ok=True)
    modele = charger_modele()
    chemins = []
    for indice, url in enumerate(urls, 1):
        progression(indice, 5, "Téléchargement de la vidéo", 0.0)
        with tempfile.TemporaryDirectory(prefix=f"source-{indice}-", dir=racine) as temporaire:
            source = SourceVideo(url.strip(), "url", url.strip())
            chemin = preparer_video(source, temporaire)
            destination = racine / f"case_{indice}.mp4"
            annoter_video(chemin, destination, modele, frequence,
                          lambda valeur: progression(indice, 5, "Analyse de la vidéo", valeur))
            chemins.append(destination)
    progression(5, 5, "Assemblage des quatre fenêtres", 0.0)
    sortie = racine / "visiotrack_montage_4_fenetres.mp4"
    duree = assembler_quatre_videos(chemins, sortie)
    # Les fichiers intermédiaires ne sont plus utiles après assemblage.
    for chemin in chemins:
        chemin.unlink(missing_ok=True)
    progression(5, 5, "Montage terminé", 1.0)
    return sortie, duree
