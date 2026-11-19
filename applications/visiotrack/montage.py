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
    """Réutiliser les annotations YOLO et ajouter un compteur pour chaque objet choisi."""
    import cv2

    categories = [categorie] if isinstance(categorie, int) else list(categorie)
    if not categories or any(cle not in CATEGORIES for cle in categories):
        raise ValueError("Sélectionnez au moins un objet YOLO valide.")
    if not Path(chemin_apercu).is_file() or not Path(chemin_chronologie).is_file():
        raise ValueError("L'aperçu ou sa chronologie est indisponible.")

    effectifs = {cle: [] for cle in categories}
    noms_classes = {CATEGORIES[cle]: cle for cle in categories}
    with Path(chemin_chronologie).open("r", encoding="utf-8-sig", newline="") as fichier:
        for ligne in csv.DictReader(fichier):
            if ligne.get("video_id") != identifiant:
                continue
            cle = noms_classes.get(ligne.get("categorie"))
            if cle is not None:
                effectifs[cle].append(
                    (float(ligne["horodatage_s"]), int(ligne["nombre_visible"]))
                )
    if any(not valeurs for valeurs in effectifs.values()):
        raise ValueError("La chronologie de certains objets sélectionnés est absente.")
    for valeurs in effectifs.values():
        valeurs.sort(key=lambda element: element[0])

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
            raise ValueError("Métadonnées de l'aperçu invalides.")

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
        positions = {cle: -1 for cle in categories}
        while True:
            lu, image = capture.read()
            if not lu:
                break
            temps = numero / cadence
            for rang, cle in enumerate(categories):
                valeurs = effectifs[cle]
                position = positions[cle]
                while position + 1 < len(valeurs) and valeurs[position + 1][0] <= temps + 1e-7:
                    position += 1
                positions[cle] = position
                nombre = valeurs[position][1] if position >= 0 else 0
                libelle = f"{CATEGORIES[cle].capitalize()} : {nombre}"
                largeur_texte = cv2.getTextSize(
                    libelle, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2
                )[0][0]
                haut = 7 + rang * 38
                bas = haut + 37
                if bas > hauteur:
                    continue
                cv2.rectangle(
                    image, (8, haut),
                    (min(largeur - 1, max(155, largeur_texte + 25)), bas),
                    (0, 0, 0), -1
                )
                cv2.putText(
                    image, libelle, (16, haut + 26), cv2.FONT_HERSHEY_SIMPLEX,
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
            raise ValueError("L'aperçu avec compteurs n'a pas été généré.")
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


def assembler_videos(chemins, sortie):
    """Composer deux, trois ou quatre vidéos YOLO dans une image 1920 × 1080."""
    nombre = len(chemins)
    if nombre not in (2, 3, 4):
        raise ValueError("La vidéo split nécessite deux, trois ou quatre vidéos.")

    largeur_case = LARGEUR_CASE if nombre in (2, 4) else 640
    hauteur_case = HAUTEUR_CASE if nombre == 4 else 1080
    positions = (
        [(0, 0), (largeur_case, 0), (0, hauteur_case), (largeur_case, hauteur_case)]
        if nombre == 4
        else [(indice * largeur_case, 0) for indice in range(nombre)]
    )

    durees = [lire_metadonnees(chemin)[0] for chemin in chemins]
    duree_max = max(durees)
    commande = ["ffmpeg", "-nostdin", "-y", "-hide_banner", "-loglevel", "error"]
    for chemin in chemins:
        commande.extend(["-i", str(chemin)])

    filtres = []
    for indice, duree in enumerate(durees):
        prolongation = max(0.0, duree_max - duree) + 1.0 / CADENCE_SORTIE
        filtres.append(
            f"[{indice}:v]fps={CADENCE_SORTIE},"
            f"scale={largeur_case}:{hauteur_case}:force_original_aspect_ratio=decrease,"
            f"pad={largeur_case}:{hauteur_case}:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,setpts=PTS-STARTPTS,"
            f"tpad=stop_mode=clone:stop_duration={prolongation:.6f}[v{indice}]"
        )

    positionnement = "|".join(f"{x}_{y}" for x, y in positions)
    etiquettes = "".join(f"[v{indice}]" for indice in range(nombre))
    filtres.append(
        f"{etiquettes}xstack=inputs={nombre}:layout={positionnement},"
        "format=yuv420p[montage]"
    )
    commande.extend([
        "-filter_complex", ";".join(filtres), "-map", "[montage]", "-an",
        "-t", f"{duree_max:.6f}", "-r", str(CADENCE_SORTIE),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(sortie),
    ])
    resultat = subprocess.run(commande, capture_output=True, text=True)
    if resultat.returncode != 0:
        raise ValueError(
            f"Échec de l'assemblage FFmpeg : {resultat.stderr[-1500:]}"
        )
    if not Path(sortie).is_file() or Path(sortie).stat().st_size == 0:
        raise ValueError("Le fichier vidéo split n'a pas été produit.")
    return duree_max


def assembler_quatre_videos(chemins, sortie):
    """Conserver la compatibilité avec l'ancien moteur de montage."""
    return assembler_videos(chemins, sortie)


def creer_montage(urls, dossier, frequence=5.0, progression=lambda *args: None,
                 categorie=67, reutilisations=None, generer_split=True, categories=None):
    """Analyser une à quatre URL et produire une vidéo split seulement sur demande.

    Les quatre champs URL sont facultatifs : seuls ceux renseignés sont analysés.
    Les vidéos déjà analysées dans la session réutilisent leurs annotations.
    Chaque URL restante suit le moteur individuel YOLO/ByteTrack de VisioTrack.
    """
    adresses = [str(adresse).strip() for adresse in urls if str(adresse).strip()]
    if not 1 <= len(adresses) <= 4:
        raise ValueError("Renseignez entre une et quatre URL vidéo.")
    if generer_split and len(adresses) < 2:
        raise ValueError("Une vidéo split nécessite au moins deux URL.")
    categories_choisies = [categorie] if categories is None else list(categories)
    if not categories_choisies or any(cle not in CATEGORIES for cle in categories_choisies):
        raise ValueError("Sélectionnez au moins un objet YOLO valide.")
    if len(categories_choisies) != len(set(categories_choisies)):
        raise ValueError("Ne sélectionnez pas plusieurs fois le même objet.")
    if not math.isfinite(frequence) or not 0 < frequence <= 30:
        raise ValueError("La fréquence d'analyse doit être comprise entre 0 et 30 images/s.")
    for adresse in adresses:
        verifier_url(adresse)

    racine = Path(dossier)
    racine.mkdir(parents=True, exist_ok=True)
    reutilisations = reutilisations or {}
    modele = None
    chemins_annotes = []
    resultats = []
    total_etapes = len(adresses) + (1 if generer_split else 0)

    for indice, adresse in enumerate(adresses, 1):
        destination = racine / f"case_{indice}.mp4"
        reprise = reutilisations.get(adresse)
        if reprise is not None:
            try:
                progression(indice, total_etapes, f"Réutilisation de l'analyse URL {indice}", 0.0)
                reutiliser_apercu_analyse(
                    reprise["apercu"], reprise["chronologie"], reprise["video_id"],
                    categories_choisies, destination,
                    lambda valeur: progression(
                        indice, total_etapes, f"Compteur URL {indice}", valeur
                    ),
                )
                anciennes_lignes = reprise["resultat"]
                if isinstance(anciennes_lignes, dict):
                    anciennes_lignes = [anciennes_lignes]
                for ancienne_ligne in anciennes_lignes:
                    if ancienne_ligne.get("categorie") not in [
                        CATEGORIES[cle] for cle in categories_choisies
                    ]:
                        continue
                    ligne = dict(ancienne_ligne)
                    ligne.update(video_id=f"v{indice:06d}", source=adresse)
                    resultats.append(ligne)
                chemins_annotes.append(destination)
                continue
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                # Revenir à l'analyse ordinaire si le résultat antérieur a expiré.
                destination.unlink(missing_ok=True)

        progression(indice, total_etapes, f"Téléchargement URL {indice}", 0.0)
        try:
            if modele is None:
                modele = charger_modele()
            with tempfile.TemporaryDirectory(
                prefix=f"source-{indice}-", dir=racine
            ) as temporaire:
                source = SourceVideo(adresse, "url", adresse)
                chemin = preparer_video(source, temporaire)
                video_id = f"v{indice:06d}"
                lignes = analyser_video(
                    chemin, video_id, adresse, categories_choisies, frequence, modele,
                    temporaire,
                    lambda valeur: progression(
                        indice, total_etapes, f"Analyse YOLO URL {indice}", 0.7 * valeur
                    ),
                    quantifier_temps=True, compter_distincts=True,
                )
                creer_video_annotee(
                    chemin, Path(temporaire) / "observations.jsonl", destination,
                    lignes[0]["duree_totale_s"],
                    lambda valeur: progression(
                        indice, total_etapes, f"Vidéo annotée URL {indice}", 0.7 + valeur * 0.3
                    ),
                    categories_compteur=categories_choisies,
                )
                chemins_annotes.append(destination)
                resultats.extend(lignes)
        except Exception as erreur:
            raise ValueError(f"Échec de l'analyse de l'URL {indice} : {erreur}") from erreur

    chemin_csv = racine / "visiotrack_montage_resultats.csv"
    with chemin_csv.open("w", encoding="utf-8-sig", newline="") as fichier:
        redacteur = csv.DictWriter(
            fichier, fieldnames=colonnes_resultats(True, True), extrasaction="ignore"
        )
        redacteur.writeheader()
        redacteur.writerows(resultats)

    sortie = None
    duree = None
    if generer_split:
        progression(total_etapes, total_etapes, "Assemblage des vidéos analysées", 0.0)
        sortie = racine / f"visiotrack_montage_{len(adresses)}_fenetres.mp4"
        duree = assembler_quatre_videos(chemins_annotes, sortie)
        progression(total_etapes, total_etapes, "Vidéo split terminée", 1.0)

    # Conserver les vidéos annotées individuelles : elles restent consultables
    # et téléchargeables, que la vidéo split ait été demandée ou non.
    return sortie, duree
