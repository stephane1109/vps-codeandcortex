"""Découverte Presse par gallery-dl (endpoint créateur, sans Playwright).

Le CLI gallery-dl est exécuté sans fichier de configuration utilisateur, sans
cookies et sans téléchargement. Ses messages Directory apportent les
métadonnées de la publication, qui sont validées par compte et identifiant.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time

import scraptiktok as moteur
from collecte.presse_api import _metadonnees_publication_api
from collecte.verification_comptes import normaliser_compte


def extraire_publications(messages, compte, limite):
    """Utiliser seulement les métadonnées de vidéos du compte ciblé."""
    videos = {}
    if not isinstance(messages, list):
        raise ValueError("La réponse JSON de gallery-dl doit être une liste.")
    for ligne in messages:
        if not isinstance(ligne, list) or not ligne:
            continue
        if ligne[0] == -1:
            continue
        if len(ligne) < 3 or ligne[0] != 2 or not isinstance(ligne[2], dict):
            continue
        objet = ligne[2]
        auteur = objet.get("author")
        identite = (auteur.get("uniqueId") or auteur.get("unique_id")
                    if isinstance(auteur, dict) else objet.get("user"))
        identifiant = str(objet.get("id") or "")
        if (not isinstance(identite, str) or identite.casefold() != compte.casefold()
                or not re.fullmatch(r"\d{5,30}", identifiant)
                or not isinstance(objet.get("video"), dict)
                or objet.get("imagePost") or objet.get("post_type") == "image"):
            continue
        fiche = _metadonnees_publication_api(objet, compte, identifiant)
        fiche["source"] = "gallerydl_createur"
        videos.setdefault(identifiant, fiche)
        if len(videos) >= limite:
            break
    return videos


class PresseGalleryDL:
    """Appel borné du CLI officiel. Aucune signature TikTok n'est fabriquée."""

    def __init__(self, arguments, verifier=None):
        self.arguments = arguments
        self.verifier = verifier or (lambda: None)
        self.processus = None

    def decouvrir(self, compte, rapport, progression=None):
        compte = normaliser_compte(compte)
        limite = min(max(1, int(self.arguments.limit)), 500)
        rapport.update(
            mode_decouverte="gallerydl_createur", technique="gallerydl_cli",
            presse_moteur="gallerydl", compte_attendu=compte,
            hashtag_url=f"https://www.tiktok.com/@{compte}/posts",
            discovered_urls=[], metadonnees_api={},
            retenues_par_compte={compte: 0}, exhaustif=False,
            diagnostic={},
        )
        commande = [
            sys.executable, "-m", "gallery_dl", "--config-ignore",
            "--dump-json", "--post-range", f"1-{limite}",
            "-o", "tiktok.order-posts=desc",
            "-o", "tiktok.videos=false",
            "-o", "tiktok.photos=false",
            "-o", "tiktok.covers=false",
            f"https://www.tiktok.com/@{compte}/posts",
        ]
        self.verifier()
        borne = min(180.0, max(45.0, float(self.arguments.timeout) * 5))
        debut = time.monotonic()
        try:
            self.processus = subprocess.Popen(
                commande, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace"
            )
            while True:
                self.verifier()
                restant = borne - (time.monotonic() - debut)
                if restant <= 0:
                    rapport["diagnostic"] = {"code": "gallerydl_delai_depasse",
                                            "delai_secondes": int(borne)}
                    raise RuntimeError("gallery-dl a dépassé le délai de collecte.")
                try:
                    sortie, erreurs = self.processus.communicate(timeout=min(1.0, restant))
                    break
                except subprocess.TimeoutExpired:
                    continue
            try:
                messages = json.loads(sortie)
            except (TypeError, ValueError) as erreur:
                rapport["diagnostic"] = {"code": "gallerydl_json_invalide"}
                raise RuntimeError("gallery-dl n'a pas fourni une liste JSON exploitable.") from erreur
            videos = extraire_publications(messages, compte, limite)
            rapport["metadonnees_api"] = videos
            rapport["discovered_urls"] = [fiche["url"] for fiche in videos.values()]
            rapport["retenues_par_compte"] = {compte: len(videos)}
            rapport["candidats_examines"] = len(videos)
            rapport["collecte_partielle"] = len(videos) < limite
            rapport["discovery_stop"] = "limit" if len(videos) >= limite else "fin_gallerydl"
            rapport["bilan_recherche"] = (
                f"@{compte} : {len(videos)} vidéo(s) fournies par gallery-dl "
                "(creator/item_list, ordre décroissant)."
            )
            if progression:
                progression(len(videos))
            if not videos:
                # Ne pas exposer stderr : il peut contenir des données de session.
                erreurs_min = (erreurs or "").lower()
                categorie = ("http_429" if "429" in erreurs_min else
                             "http_403" if "403" in erreurs_min else
                             "aucun_resultat")
                rapport["diagnostic"] = {
                    "code": "gallerydl_sans_videos",
                    "categorie": categorie, "code_retour": self.processus.returncode
                }
                raise RuntimeError(
                    "gallery-dl ne fournit aucune vidéo pour ce compte. "
                    "Cela ne signifie pas que le compte est vide."
                )
            return list(rapport["discovered_urls"])
        except FileNotFoundError as erreur:
            rapport["diagnostic"] = {"code": "gallerydl_indisponible"}
            raise RuntimeError("gallery-dl n'est pas installé dans le conteneur.") from erreur
        finally:
            processus = self.processus
            self.processus = None
            if processus is not None and processus.poll() is None:
                processus.terminate()
                try:
                    processus.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    processus.kill()
                    processus.communicate()

    def fermer(self):
        processus = self.processus
        if processus is not None and processus.poll() is None:
            processus.terminate()
