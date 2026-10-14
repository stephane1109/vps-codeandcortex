"""MP4 facultatifs via yt-dlp, indépendants de Selenium et des analyses audiovisuelles."""
from importlib.util import find_spec
from importlib.metadata import version, PackageNotFoundError
from collections import deque
import threading
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
    "indisponible": "yt-dlp n’a pas pu récupérer cette vidéo ; cause non identifiée.",
    "connexion_requise": "TikTok demande une connexion pour ce téléchargement. La collecte reste anonyme.",
    "verification_requise": "TikTok renvoie une vérification à yt-dlp malgré la collecte dans le navigateur.",
    "acces_refuse": "TikTok ou son serveur vidéo refuse la requête (HTTP 403).",
    "requetes_limitees": "TikTok limite les requêtes du serveur (HTTP 429).",
    "format_absent": "yt-dlp ne propose aucun format MP4 compatible pour cette publication.",
    "extraction_impossible": "yt-dlp ne parvient pas à lire les données de cette page TikTok.",
    "reseau_indisponible": "Échec réseau, TLS ou résolution DNS pendant le téléchargement.",
    "configuration_invalide": "L’appel à yt-dlp utilise une option incompatible avec sa version installée.",
    "support_navigateur_absent": "Le support réseau de navigateur curl-cffi manque ou ne peut pas être utilisé.",
    "identifiant_rejete": "yt-dlp a reçu un identifiant différent de la vidéo attendue.",
    "aucun_fichier": "yt-dlp s’est terminé sans produire de fichier vidéo.",
    "format_invalide": "Le fichier reçu ne présente pas la signature attendue d’un MP4.",
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


# Liste fermée : aucun sessionid, sid_tt, jeton de connexion ou cookie de compte.
COOKIES_TECHNIQUES = frozenset({"ttwid", "tt_chain_token", "msToken", "s_v_web_id",
    "verifyFp", "tt_webid", "tt_webid_v2", "_ttp", "_wafchallengeid", "waforiginalreid"})


def filtrer_cookies_techniques(cookies):
    """Limiter le transfert aux cookies techniques TikTok et au format Netscape sûr."""
    conserves = []
    for cookie in cookies:
        nom, valeur = cookie.get("name"), cookie.get("value")
        domaine, chemin = cookie.get("domain", ""), cookie.get("path", "/")
        if nom not in COOKIES_TECHNIQUES:
            continue
        if not all(isinstance(v, str) and not re.search(r"[\x00-\x20\x7f]", v)
                   for v in (nom, valeur, domaine, chemin)):
            continue
        hote = domaine.lstrip(".").lower()
        if not (hote == "tiktok.com" or hote.endswith(".tiktok.com")) or not chemin.startswith("/"):
            continue
        if len(valeur) > 8192:
            continue
        try:
            expiration = int(cookie.get("expiry") or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        if expiration and expiration <= time.time():
            continue
        conserves.append({"name": nom, "value": valeur, "domain": domaine, "path": chemin,
                          "secure": bool(cookie.get("secure")), "expiry": expiration})
    return conserves


def capturer_contexte_anonyme(navigateur):
    """Lire le contexte avant fermeture, sans changer de page ni ouvrir de connexion."""
    try:
        adresse = urlsplit(navigateur.current_url)
        if adresse.scheme != "https" or adresse.hostname not in {"www.tiktok.com", "tiktok.com"}:
            return {}
        cookies = filtrer_cookies_techniques(navigateur.get_cookies())
        agent = navigateur.execute_script("return navigator.userAgent;")
        if not isinstance(agent, str) or not 1 <= len(agent) <= 1024 or re.search(r"[\r\n\x00]", agent):
            agent = None
        return {"cookies": cookies, "agent": agent}
    except Exception:
        # Un contexte indisponible ne doit pas empêcher la fermeture du navigateur.
        return {}


def ecrire_cookies_temporaires(chemin, cookies):
    """Fichier privé de courte durée, hors du dossier des exports."""
    lignes = ["# Netscape HTTP Cookie File"]
    for cookie in filtrer_cookies_techniques(cookies):
        lignes.append("\t".join((cookie["domain"], "TRUE" if cookie["domain"].startswith(".") else "FALSE",
            cookie["path"], "TRUE" if cookie["secure"] else "FALSE", str(cookie["expiry"]),
            cookie["name"], cookie["value"])))
    if len(lignes) == 1:
        return False
    chemin.touch(mode=0o600, exist_ok=False)
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return True


def diagnostiquer_echec(texte, code):
    """Classer la sortie en mémoire ; ne jamais renvoyer le texte brut de yt-dlp."""
    texte = texte.casefold()
    regles = [
        ("configuration_invalide", r"no such option|unrecognized arguments|invalid filter|unsupported downloader"),
        ("support_navigateur_absent", r"impersonat[^\n]*(?:not available|not found|not supported|unavailable)|curl_cffi[^\n]*(?:not|missing|unavailable)"),
        ("requetes_limitees", r"http error 429|http[^\n]*429|too many requests"),
        ("connexion_requise", r"login required|log.?in is required|requiring login|log in to|sign in to|only available for registered"),
        ("verification_requise", r"captcha|verify (?:that )?you|challenge|verify your browser"),
        ("acces_refuse", r"http error 403|http[^\n]*403|403 forbidden"),
        ("format_absent", r"requested format is not available|no video formats found|no formats found"),
        ("taille_depassee", r"larger than max|larger than.*max.filesize|exceeds.*max.filesize"),
        ("identifiant_rejete", r"does not pass filter"),
        ("reseau_indisponible", r"timed out|certificate.verify|name or service not known|temporary failure in name resolution|connection refused|unable to connect"),
        ("extraction_impossible", r"unable to extract|unexpected response|invalid json|expecting value"),
    ]
    for statut, motif in regles:
        if re.search(motif, texte):
            return statut
    return "aucun_fichier" if code == 0 else "indisponible"


def lire_sortie_bornee(flux, morceaux):
    """Vider le tube pour éviter un blocage ; ne garder que 32 Kio en mémoire."""
    try:
        while morceau := flux.read(4096):
            morceaux.append(morceau)
    except (OSError, ValueError):
        pass


def version_ytdlp():
    try:
        return version("yt-dlp")
    except PackageNotFoundError:
        return None


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
                       taille_max_mo=256, delai_max_s=120, reserve_mo=512, contexte_anonyme=None):
    """Télécharger un seul MP4, avec arrêt, limites et renommage atomique après succès."""
    try:
        return _telecharger_video(publication, Path(dossier), arreter,
                                  taille_max_mo, delai_max_s, reserve_mo, contexte_anonyme or {})
    except Exception:
        # Une erreur de téléchargement ne doit jamais invalider la collecte textuelle.
        # Ne pas exporter les réponses HTTP, cookies ou sorties brutes de yt-dlp.
        return resultat_video(publication, "erreur")


def _telecharger_video(publication, dossier, arreter, taille_max_mo, delai_max_s, reserve_mo, contexte):
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
    with TemporaryDirectory(prefix=".mp4_", dir=dossier) as temporaire, TemporaryDirectory(prefix="scraptiktok-cookies-") as prive:
        sortie = Path(temporaire) / nom
        commande = [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
            "--no-cache-dir", "--no-progress", "--no-part",
            "--downloader", "native", "--fixup", "never",
            "--socket-timeout", "20", "--retries", "1", "--fragment-retries", "1",
            "--concurrent-fragments", "1", "--max-filesize", str(taille_max_mo) + "M",
            "--match-filters", "id = '" + identifiant + "'", "--format", "best[ext=mp4]",
            "--output", str(sortie), "--", "https://www.tiktok.com" + adresse.path]
        cookies = filtrer_cookies_techniques(contexte.get("cookies", []))
        options_contexte = []
        fichier_cookies = Path(prive) / "cookies.txt"
        if ecrire_cookies_temporaires(fichier_cookies, cookies):
            options_contexte += ["--cookies", str(fichier_cookies)]
        agent = contexte.get("agent")
        if isinstance(agent, str) and 1 <= len(agent) <= 1024 and not re.search(r"[\r\n\x00]", agent):
            options_contexte += ["--user-agent", agent]
        # Ne pas ajouter Cookie en en-tête global : yt-dlp applique les domaines du fichier.
        commande[commande.index("--"):commande.index("--")] = options_contexte
        diagnostic = {"yt_dlp_version": version_ytdlp(), "cookies_techniques": len(cookies),
                      "contexte_navigateur": bool(contexte), "curl_cffi_disponible": find_spec("curl_cffi") is not None}
        morceaux = deque(maxlen=8)
        debut = time.monotonic()
        processus = subprocess.Popen(commande, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lecteur = threading.Thread(target=lire_sortie_bornee, args=(processus.stdout, morceaux), daemon=True)
        lecteur.start()
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
            lecteur.join(timeout=2)
            diagnostic["code_sortie"] = code
            if code != 0 or not fichier_mp4_lisible(sortie):
                sortie_brute = b"".join(morceaux).decode("utf-8", errors="replace")
                statut = ("format_invalide" if code == 0 and sortie.exists()
                          else diagnostiquer_echec(sortie_brute, code))
                return {**resultat_video(publication, statut), "video_diagnostic": diagnostic}
            if sortie.stat().st_size > taille_max_mo * 1024**2:
                return resultat_video(publication, "taille_depassee")
            sortie.replace(cible)
            return {**resultat_video(publication, "telecharge", "videos/" + nom), "video_diagnostic": diagnostic}
        finally:
            if processus.poll() is None:
                processus.terminate()
                try:
                    processus.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    processus.kill()
                    processus.wait(timeout=2)
            lecteur.join(timeout=2)
            if processus.stdout is not None:
                processus.stdout.close()
            morceaux.clear()
