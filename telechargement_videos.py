"""MP4 facultatifs via yt-dlp, indépendants de Selenium et des analyses audiovisuelles."""
from importlib.util import find_spec
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from urllib.parse import urlsplit

CHAMPS_VIDEO = ("video_id", "video_url", "video_fichier")
MESSAGES = {
    "telecharge": "MP4 téléchargé.", "existant": "MP4 déjà présent, réutilisé.",
    "indisponible": "Vidéo inaccessible ou aucun format MP4 disponible via yt-dlp.",
    "dependance_absente": "yt-dlp n’est pas installé ; texte conservé.",
    "url_invalide": "L’URL ne correspond pas à l’identifiant TikTok attendu.",
    "pas_une_video": "Cette publication est un diaporama, pas une vidéo MP4.",
    "delai_depasse": "Délai de téléchargement dépassé ; texte conservé.",
    "espace_insuffisant": "Espace disque réservé aux exports textuels atteint.",
    "taille_depassee": "Taille maximale du fichier MP4 dépassée.",
    "arrete": "Téléchargement arrêté ; texte conservé.",
    "erreur": "Téléchargement impossible ; texte conservé.",
    "limite_lot": "Limite de durée ou de volume du lot MP4 atteinte ; texte conservé.",
}


def correspondance_video(publication):
    """Conserver un identifiant exact et une URL publique, jamais une URL CDN temporaire."""
    identifiant = str(publication.get("id") or "")
    return {"video_id": identifiant if re.fullmatch(r"[0-9]+", identifiant) else None,
            "video_url": publication.get("url"), "video_fichier": publication.get("video_fichier")}


def resultat_video(publication, statut, fichier=None):
    return {**correspondance_video(publication), "video_fichier": fichier,
            "video_statut": statut, "video_message": MESSAGES[statut]}


def fichier_mp4_lisible(chemin):
    """Contrôler la signature du conteneur sans charger de bibliothèque audiovisuelle."""
    if chemin.is_symlink() or not chemin.is_file() or chemin.stat().st_size < 16:
        return False
    with chemin.open("rb") as flux:
        return flux.read(12)[4:8] == b"ftyp"


def telecharger_video(publication, dossier, arreter=lambda: False, *,
                       taille_max_mo=256, delai_max_s=120, reserve_mo=512):
    """Télécharger un seul MP4, avec arrêt, limites et renommage atomique après succès."""
    try:
        return _telecharger_video(publication, Path(dossier), arreter,
                                  taille_max_mo, delai_max_s, reserve_mo)
    except Exception:
        # Une erreur de téléchargement ne doit jamais invalider la collecte textuelle.
        # Ne pas exporter les réponses HTTP, cookies ou sorties brutes de yt-dlp.
        return resultat_video(publication, "erreur")


def _telecharger_video(publication, dossier, arreter, taille_max_mo, delai_max_s, reserve_mo):
    identifiant = correspondance_video(publication)["video_id"]
    url = str(publication.get("url") or "")
    adresse = urlsplit(url)
    chemin = re.fullmatch(r"/@[^/]+/(video|photo)/([0-9]+)/?", adresse.path)
    if (not identifiant or adresse.scheme != "https" or adresse.hostname not in {"www.tiktok.com", "tiktok.com"}
            or adresse.username or adresse.password or adresse.port not in {None, 443}
            or not chemin or chemin[2] != identifiant):
        return resultat_video(publication, "url_invalide")
    if chemin[1] != "video":
        return resultat_video(publication, "pas_une_video")
    if arreter():
        return resultat_video(publication, "arrete")
    dossier.mkdir(parents=True, exist_ok=True)
    if dossier.is_symlink():
        return resultat_video(publication, "erreur")
    nom = "id_" + identifiant + ".mp4"
    cible = dossier / nom
    if fichier_mp4_lisible(cible):
        return resultat_video(publication, "existant", "videos/" + nom)
    if cible.is_symlink():
        return resultat_video(publication, "erreur")
    if find_spec("yt_dlp") is None:
        return resultat_video(publication, "dependance_absente")
    if shutil.disk_usage(dossier).free < reserve_mo * 1024**2:
        return resultat_video(publication, "espace_insuffisant")
    with TemporaryDirectory(prefix=".mp4_", dir=dossier) as temporaire:
        sortie = Path(temporaire) / nom
        commande = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
            "--no-cache-dir", "--no-progress", "--no-warnings", "--quiet", "--no-part",
            "--downloader", "native", "--fixup", "never",
            "--socket-timeout", "20", "--retries", "1", "--fragment-retries", "1",
            "--concurrent-fragments", "1", "--max-filesize", str(taille_max_mo) + "M",
            "--match-filters", "id = '" + identifiant + "'", "--format", "best[ext=mp4]",
            "--output", str(sortie), "--", "https://www.tiktok.com" + adresse.path]
        debut = time.monotonic()
        processus = subprocess.Popen(commande, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            while True:
                if arreter():
                    return resultat_video(publication, "arrete")
                if time.monotonic() - debut > delai_max_s:
                    return resultat_video(publication, "delai_depasse")
                if shutil.disk_usage(dossier).free < reserve_mo * 1024**2:
                    return resultat_video(publication, "espace_insuffisant")
                if sortie.exists() and sortie.stat().st_size > taille_max_mo * 1024**2:
                    return resultat_video(publication, "taille_depassee")
                try:
                    code = processus.wait(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if code != 0 or not fichier_mp4_lisible(sortie):
                return resultat_video(publication, "indisponible")
            if sortie.stat().st_size > taille_max_mo * 1024**2:
                return resultat_video(publication, "taille_depassee")
            sortie.replace(cible)
            return resultat_video(publication, "telecharge", "videos/" + nom)
        finally:
            if processus.poll() is None:
                processus.terminate()
                try:
                    processus.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    processus.kill()
                    processus.wait(timeout=2)
