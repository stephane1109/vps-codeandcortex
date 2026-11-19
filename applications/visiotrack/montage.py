"""Montage comparatif de quatre vidéos, sans modifier les analyses CSV existantes."""

from __future__ import annotations

import math
import csv
import subprocess
import tempfile
from pathlib import Path

from detection import (
    CATEGORIES,
    SourceVideo,
    analyser_video,
    charger_modele,
    colonnes_resultats,
    creer_video_annotee,
    lire_metadonnees,
    preparer_video,
    verifier_url,
)


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


def reutiliser_apercu_analyse(chemin_apercu, chemin_chronologie, identifiant,
                            categorie, destination, progression=lambda valeur: None):
    """Compléter un aperçu YOLO déjà calculé avec le compteur de sa chronologie."""
    import cv2

    if not Path(chemin_apercu).is_file() or not Path(chemin_chronologie).is_file():
        raise ValueError("L'aperçu ou sa chronologie est indisponible.")

    effectifs = []
    with Path(chemin_chronologie).open("r", encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier):
            if ligne.get("video_id") == identifiant and ligne.get("categorie") == CATEGORIES[categorie]:
                effectifs.append((float(ligne["horodatage_s"]), int(ligne["nombre_visible"])))
    if not effectifs:
        raise ValueError("Aucune chronologie pour la catégorie sélectionnée.")
    effectifs.sort(key=lambda valeur: valeur[0])

    capture = cv2.VideoCapture(str(chemin_apercu))
    encodeur = None
    reussi = False
    try:
        if not capture.isOpened():
            raise ValueError("Impossible de lire l'aperçu YOLO existant.")
        largeur = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        hauteur = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cadence = float(capture.get(cv2.CAP_PROP_FPS))
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if largeur <= 0 or hauteur <= 0 or not math.isfinite(cadence) or cadence <= 0:
            raise ValueError("Métadonnées vidéo invalides.")
        commande = [
            "ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "bgr24",
            "-video_size", f"{largeur}x{hauteur}", "-framerate", f"{cadence:.6f}",
            "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(destination),
        ]
        encodeur = subprocess.Popen(
            commande, stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        numero = 0
        position = -1
        while True:
            lu, image = capture.read()
            if not lu:
                break
            temps = numero / cadence
            while position + 1 < len(effectifs) and effectifs[position + 1][0] <= temps + 1e-7:
                position += 1
            nombre = effectifs[position][1] if position >= 0 else 0
            libelle = f"{CATEGORIES[categorie].capitalize()} : {nombre}"
            largeur_texte = cv2.getTextSize(
                libelle, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2
            )[0][0]
            cv2.rectangle(
                image, (8, 7), (min(largeur - 1, largeur_texte + 25), 44),
                (0, 0, 0), -1
            )
            cv2.putText(
                image, libelle, (16, 33), cv2.FONT_HERSHEY_SIMPLEX,
                0.65, (255, 255, 255), 2, cv2.LINE_AA
            )
            encodeur.stdin.write(image.tobytes())
            numero += 1
            if total > 0 and numero % max(1, int(cadence)) == 0:
                progression(min(numero / total, 0.999))
        if not numero:
            raise ValueError("Aucune image dans l'aperçu existant.")
        encodeur.stdin.close()
        if encodeur.wait() != 0:
            raise ValueError("Échec de l'encodage de l'aperçu réutilisé.")
        if not Path(destination).is_file() or Path(destination).stat().st_size == 0:
            raise ValueError("L'aperçu avec compteur n'a pas été généré.")
        reussi = True
        progression(1.0)
    finally:
        capture.release()
        if encodeur is not None:
            if encodeur.stdin is not None and not encodeur.stdin.closed:
                encodeur.stdin.close()
            if encodeur.poll() is None:
                encodeur.terminate()
            encodeur.wait()
        if not reussi:
            Path(destination).unlink(missing_ok=True)


def assembler_quatre_videos(chemins, sortie):
    """Réunir les quatre vidéos annotées en un seul lecteur 1920 × 1080."""
    if len(chemins) != 4:
        raise ValueError("Le montage requiert exactement quatre vidéos.")
    durees = [lire_metadonnees(chemin)[0] for chemin in chemins]
    duree_max = max(durees)
    commande = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for chemin in chemins:
        commande.extend(["-i", str(chemin)])
    filtres = []
    for indice, duree in enumerate(durees):
        # Préserver le cadrage de chaque vidéo (verticale ou horizontale).
        # Prolonger la dernière image jusqu'à la fin de la piste la plus longue.
        prolongation = max(0.0, duree_max - duree) + 1.0 / CADENCE_SORTIE
        filtres.append(
            f"[{indice}:v]fps={CADENCE_SORTIE},"
            f"scale={LARGEUR_CASE}:{HAUTEUR_CASE}:force_original_aspect_ratio=decrease,"
            f"pad={LARGEUR_CASE}:{HAUTEUR_CASE}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"setsar=1,setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={prolongation:.6f}[v{indice}]"
        )
    filtres.append(
        "[v0][v1][v2][v3]xstack=inputs=4:"
        f"layout=0_0|{LARGEUR_CASE}_0|0_{HAUTEUR_CASE}|"
        f"{LARGEUR_CASE}_{HAUTEUR_CASE},format=yuv420p[montage]"
    )
    commande.extend([
        "-filter_complex", ";".join(filtres), "-map", "[montage]", "-an",
        "-t", f"{duree_max:.6f}", "-r", str(CADENCE_SORTIE),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(sortie),
    ])
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        raise ValueError(f"Échec de l'assemblage FFmpeg : {resultat.stderr[-1500:]}")
    if not Path(sortie).is_file() or Path(sortie).stat().st_size == 0:
        raise ValueError("Le montage MP4 est absent.")
    return duree_max


def creer_montage(urls, dossier, frequence=5.0, progression=lambda *args: None,
                 categorie=67, reutilisations=None):
    """Analyser réellement les quatre vidéos avec VisioTrack puis assembler leurs annotations.

    Chaque URL utilise le même moteur YOLO, ByteTrack, la détection des
    changements de plan et la quantification que l'analyse individuelle.
    """
    if len(urls) != 4 or any(not url.strip() for url in urls):
        raise ValueError("Renseignez les quatre URL vidéo.")
    if categorie not in CATEGORIES:
        raise ValueError("Sélectionnez une catégorie YOLO valide.")
    if not math.isfinite(frequence) or not 0 < frequence <= 30:
        raise ValueError("La fréquence d'analyse doit être comprise entre 0 et 30 images/s.")
    for url in urls:
        verifier_url(url.strip())

    racine = Path(dossier)
    racine.mkdir(parents=True, exist_ok=True)
    reutilisations = reutilisations or {}
    modele = None
    chemins_annotes = []
    resultats = []

    for indice, url in enumerate(urls, 1):
        adresse = url.strip()
        destination = racine / f"case_{indice}.mp4"
        reprise = reutilisations.get(adresse)
        if reprise is not None:
            try:
                progression(indice, 5, f"Réutilisation de l'analyse URL {indice}", 0.0)
                reutiliser_apercu_analyse(
                    reprise["apercu"], reprise["chronologie"], reprise["video_id"],
                    categorie, destination,
                    lambda valeur: progression(
                        indice, 5, f"Annotation du compteur URL {indice}", valeur
                    ),
                )
                ligne = dict(reprise["resultat"])
                ligne.update(video_id=f"v{indice:06d}", source=adresse)
                resultats.append(ligne)
                chemins_annotes.append(destination)
                continue
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                # Le téléchargement reste possible lorsque l'aperçu n'est plus lisible.
                destination.unlink(missing_ok=True)

        progression(indice, 5, f"Téléchargement URL {indice}", 0.0)
        try:
            if modele is None:
                modele = charger_modele()
            with tempfile.TemporaryDirectory(prefix=f"source-{indice}-", dir=racine) as temporaire:
                source = SourceVideo(adresse, "url", adresse)
                chemin = preparer_video(source, temporaire)
                video_id = f"v{indice:06d}"
                lignes = analyser_video(
                    chemin, video_id, url.strip(), [categorie], frequence, modele,
                    temporaire,
                    lambda valeur: progression(indice, 5, f"Analyse YOLO URL {indice}", 0.7 * valeur),
                    quantifier_temps=True, compter_distincts=True,
                )
                creer_video_annotee(
                    chemin, Path(temporaire) / "observations.jsonl", destination,
                    lignes[0]["duree_totale_s"],
                    lambda valeur: progression(
                        indice, 5, f"Vidéo annotée URL {indice}", 0.7 + valeur * 0.3
                    ),
                    categories_compteur=[categorie],
                )
                chemins_annotes.append(destination)
                resultats.extend(lignes)
        except Exception as erreur:
            raise ValueError(f"Échec de l'analyse de l'URL {indice} : {erreur}") from erreur

    # Les résultats numériques et les vidéos proviennent des mêmes observations YOLO.
    chemin_csv = racine / "visiotrack_montage_resultats.csv"
    with chemin_csv.open("w", encoding="utf-8-sig", newline="") as fichier:
        redacteur = csv.DictWriter(
            fichier, fieldnames=colonnes_resultats(True, True), extrasaction="ignore"
        )
        redacteur.writeheader()
        redacteur.writerows(resultats)

    progression(5, 5, "Assemblage des quatre vidéos analysées", 0.0)
    sortie = racine / "visiotrack_montage_4_fenetres.mp4"
    duree = assembler_quatre_videos(chemins_annotes, sortie)
    # Le fichier final et le CSV restent accessibles durant la session Streamlit.
    for chemin in chemins_annotes:
        chemin.unlink(missing_ok=True)
    progression(5, 5, "Vidéo comparative terminée", 1.0)
    return sortie, duree
