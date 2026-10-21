"""Téléchargement facultatif depuis une URL validée ; diagnostics sans sortie sensible."""
from pathlib import Path
import re
import subprocess
import sys
import shutil


class ErreurTelechargement(RuntimeError):
    """Conserver une cause exploitable sans exposer la commande ou une URL CDN."""
    def __init__(self, statut, message, code=None):
        super().__init__(message)
        self.statut = statut
        self.code = code


def expliquer_echec(sortie, code):
    """Classer stderr/stdout en mémoire, sans enregistrer leurs contenus bruts."""
    if isinstance(sortie, bytes): sortie = sortie.decode('utf-8', errors='replace')
    texte = sortie.casefold()
    regles = [
        ('dependance_absente', r'no module named.*yt_dlp', 'yt-dlp n’est pas installé sur le serveur.'),
        ('configuration_invalide', r'no such option|unrecognized arguments|invalid filter', 'Configuration yt-dlp invalide.'),
        ('requetes_limitees', r'http error 429|too many requests', 'TikTok limite les requêtes (HTTP 429). Réessayez plus tard.'),
        ('connexion_requise', r'login required|log.?in is required|requiring login|log in to|sign in to', 'TikTok exige une connexion pour cette vidéo.'),
        ('verification_requise', r'captcha|verify (?:that )?you|challenge', 'TikTok demande une vérification anti-robot.'),
        ('acces_refuse', r'http error 403|403 forbidden', 'TikTok refuse le téléchargement (HTTP 403).'),
        ('video_indisponible', r'http error 404|video (?:is )?(?:unavailable|private)|video has been removed', 'Vidéo indisponible, privée ou supprimée.'),
        ('duree_depassee', r'does not pass filter|does not pass.*duration', 'Vidéo exclue par la limite de durée configurée.'),
        ('taille_depassee', r'larger than max|larger than.*max.filesize|exceeds.*max.filesize', 'Vidéo exclue par la taille maximale configurée.'),
        ('format_absent', r'requested format is not available|no video formats|no formats found', 'Aucun format vidéo téléchargeable trouvé.'),
        ('reseau_indisponible', r'timed out|certificate.verify|name or service not known|temporary failure in name resolution|connection refused|unable to connect', 'Échec réseau pendant le téléchargement.'),
        ('extraction_impossible', r'unable to extract|unexpected response|invalid json|expecting value', 'yt-dlp ne parvient pas à extraire la vidéo TikTok.'),
    ]
    for statut, motif, message in regles:
        if re.search(motif, texte): return ErreurTelechargement(statut, message, code)
    return ErreurTelechargement('telechargement_inconnu', f'Téléchargement non abouti (code yt-dlp {code}). Cause non identifiée.', code)


def telecharger_video(publication, dossier, parametres):
    """Nettoyer les téléchargements incomplets et laisser le lot poursuivre les autres vidéos."""
    from scraptiktok import canonical_post
    identite=canonical_post(publication['url'])
    if not identite or identite[0]!=str(publication['id']): raise ValueError('URL ou identifiant vidéo invalide.')
    dossier=Path(dossier); dossier.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(dossier).free < parametres['espace_libre_min_mo']*1024**2: raise OSError('Espace disque insuffisant.')
    cible=dossier/(identite[0]+'.mp4')
    # duree_max_s borne la portion analysee, pas la duree TOTALE de la video.
    # --match-filter rejetait toutes les videos de plus de 60 s avant leur analyse.
    # yt-dlp s'appuie sur ffmpeg (deja present pour l'analyse) pour ne garder
    # que la section initiale. Les limites de taille/temps restent surveillees.
    duree_section = float(parametres['duree_max_s'])
    if not 0 < duree_section <= 3600: raise ValueError('Durée maximale invalide.')
    if shutil.which('ffmpeg') is None:
        raise ErreurTelechargement('dependance_absente',
            'ffmpeg est nécessaire pour extraire les premières secondes des vidéos.')
    commande=[sys.executable,'-m','yt_dlp','--ignore-config','--no-playlist','--no-progress','--no-warnings','--socket-timeout','20','--retries','1',
        '--download-sections',f"*0-{duree_section:g}",
        '-f','best[ext=mp4]/best','--no-part','-o',str(cible),'--',identite[1]]
    try:
        resultat=subprocess.run(commande,capture_output=True,timeout=180,check=False)
        if resultat.returncode or not cible.exists() or not cible.stat().st_size:
            raise expliquer_echec((resultat.stderr or b'')+b'\n'+(resultat.stdout or b''),resultat.returncode)
        if cible.stat().st_size > parametres['taille_max_mo']*1024**2:
            raise ErreurTelechargement('taille_depassee','Vidéo trop volumineuse.')
    except subprocess.TimeoutExpired:
        cible.unlink(missing_ok=True)
        raise ErreurTelechargement('delai_depasse','Téléchargement interrompu après 180 secondes.') from None
    except OSError:
        cible.unlink(missing_ok=True)
        raise ErreurTelechargement('erreur_systeme','Impossible de lancer yt-dlp ou d’écrire la vidéo sur le serveur.') from None
    except ErreurTelechargement:
        cible.unlink(missing_ok=True)
        raise
    return cible
