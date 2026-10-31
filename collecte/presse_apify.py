"""Collecte des publications Presse par l'API d'Apify.

La collecte tourne dans l'infrastructure Apify ; ScrapTikTok n'emploie que
l'API REST pour démarrer un Actor, contrôler son exécution et lire son dataset.
La clé reste en mémoire et passe exclusivement dans l'en-tête Authorization.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from collecte.presse_api import _metadonnees_publication_api
from collecte.verification_comptes import normaliser_compte

HOTE = "https://api.apify.com/v2"
ACTOR = "clockworks~tiktok-profile-scraper"
VERSION_APIFY = "apify-presse-v1"
MAX_REPONSE = 24_000_000
ETATS_TERMINAUX = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


class ErreurApify(RuntimeError):
    """Erreur identifiable sans divulguer le jeton ou les réponses brutes."""

    def __init__(self, message, code="apify_erreur", statut_http=None):
        self.code = code
        self.statut_http = statut_http
        super().__init__(message)


def cle_disponible(cle=None):
    """Accepter le jeton individuel ou le jeton déclaré dans Coolify."""
    return bool((cle or os.environ.get("APIFY_API_TOKEN", "")).strip())


def construire_entree(compte, limite):
    """Limiter l'Actor aux vidéos propres au profil, sans téléchargement MP4."""
    return {
        "profiles": [normaliser_compte(compte)],
        "profileScrapeSections": ["videos"],
        "profileSorting": "latest",
        "resultsPerPage": min(1000, max(1, int(limite))),
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
        "shouldDownloadSlideshowImages": False,
    }


def _nombre(valeur):
    """Lire uniquement un compteur entier connu, y compris zéro."""
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, int):
        return valeur if valeur >= 0 else None
    if isinstance(valeur, str) and valeur.isdecimal():
        return int(valeur)
    return None


def normaliser_publications(donnees, compte, limite):
    """Valider l'auteur réel et harmoniser avec les exports ScrapTikTok."""
    compte = normaliser_compte(compte)
    sorties = {}
    if not isinstance(donnees, list):
        raise ErreurApify("Le dataset Apify n'est pas une liste de publications.",
                         "apify_dataset_invalide")
    for objet in donnees:
        if not isinstance(objet, dict) or objet.get("isSlideshow") is True:
            continue
        auteur = objet.get("authorMeta")
        if not isinstance(auteur, dict):
            auteur = objet.get("author")
        if not isinstance(auteur, dict):
            continue
        nom = auteur.get("name") or auteur.get("uniqueId") or auteur.get("unique_id")
        if not isinstance(nom, str):
            continue
        try:
            if normaliser_compte(nom) != compte:
                continue
        except ValueError:
            continue
        identifiant = str(objet.get("id") or "")
        if not re.fullmatch(r"\d{5,30}", identifiant):
            continue
        url = objet.get("webVideoUrl")
        if url is not None:
            if not isinstance(url, str):
                continue
            correspondance = re.fullmatch(
                r"https://(?:www\.)?tiktok\.com/@([A-Za-z0-9._]+)/video/(\d+)(?:\?.*)?",
                url)
            if not correspondance:
                continue
            if (correspondance.group(1).casefold() != compte.casefold()
                    or correspondance.group(2) != identifiant):
                continue
        description = objet.get("text", objet.get("desc", ""))
        if not isinstance(description, str):
            description = ""
        horodatage = _nombre(objet.get("createTime"))
        if horodatage is None:
            date_iso = objet.get("createTimeISO")
            try:
                horodatage = int(datetime.fromisoformat(
                    date_iso.replace("Z", "+00:00")).timestamp())
            except (TypeError, ValueError, AttributeError, OverflowError):
                horodatage = None
        # L'extracteur Apify utilise des compteurs plats, contrairement
        # à itemList qui les regroupe sous "stats".
        cles = ("playCount", "diggCount", "commentCount",
                "shareCount", "collectCount")
        stats = {cle: _nombre(objet.get(cle)) for cle in cles}
        stats = {cle: valeur for cle, valeur in stats.items() if valeur is not None}
        item = {
            "id": identifiant,
            "author": {"uniqueId": compte},
            "video": {},
            "desc": description,
            "stats": stats,
        }
        if horodatage is not None:
            item["createTime"] = horodatage
        if objet.get("aigcLabelType") is not None:
            item["aigcLabelType"] = objet["aigcLabelType"]
        fiche = _metadonnees_publication_api(item, compte, identifiant)
        fiche["source"] = "apify_profile_scraper"
        hashtags = objet.get("hashtags")
        if isinstance(hashtags, list):
            noms = [
                elt.get("name") if isinstance(elt, dict) else elt
                for elt in hashtags
            ]
            fiche["hashtags"] = list(dict.fromkeys(
                str(nom).lstrip("#") for nom in noms
                if isinstance(nom, str) and nom.strip("# ")
            ))
        sorties.setdefault(identifiant, fiche)
        if len(sorties) >= limite:
            break
    return sorties


class PresseApify:
    """Client HTTP borné et sans relance facturable automatique."""

    def __init__(self, arguments, cle=None, verifier=None,
                 ouvrir_url=None, horloge=None, pause=None):
        self.arguments = arguments
        self.verifier = verifier or (lambda: None)
        self._cle = (cle or os.environ.get("APIFY_API_TOKEN", "")).strip()
        if not self._cle:
            raise ErreurApify(
                "Renseignez un jeton Apify ou APIFY_API_TOKEN dans Coolify.",
                "apify_cle_absente")
        self.ouvrir_url = ouvrir_url or urlopen
        self.horloge = horloge or time.monotonic
        self.pause = pause or time.sleep
        self.execution_id = None
        self.requetes = 0

    def _requete(self, methode, chemin, parametres=None, entree=None):
        """Appel REST avec résultat borné et erreurs sans secrets."""
        self.verifier()
        url = HOTE + chemin
        if parametres:
            url += "?" + urlencode(parametres)
        donnees = json.dumps(entree).encode("utf-8") if entree is not None else (
            b"" if methode == "POST" else None)
        requete = Request(
            url, data=donnees, method=methode, headers={
                "Authorization": "Bearer " + self._cle,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "ScrapTikTok/1.0",
            })
        try:
            with self.ouvrir_url(requete, timeout=22) as reponse:
                corps = reponse.read(MAX_REPONSE + 1)
                statut = getattr(reponse, "status", 200)
        except HTTPError as erreur:
            statut = erreur.code
            code = (
                "apify_limite" if statut == 429
                else "apify_acces_refuse" if statut in {401, 403}
                else "apify_credit" if statut == 402
                else "apify_http"
            )
            raise ErreurApify("Apify a refusé la requête (HTTP %s)." % statut,
                             code, statut) from None
        except (URLError, TimeoutError, OSError):
            raise ErreurApify("Apify est inaccessible depuis le serveur.",
                             "apify_reseau") from None
        self.requetes += 1
        if statut < 200 or statut >= 300:
            raise ErreurApify("Apify a répondu HTTP %s." % statut,
                             "apify_http", statut)
        if len(corps) > MAX_REPONSE:
            raise ErreurApify("Réponse Apify trop volumineuse.", "apify_taille")
        try:
            resultat = json.loads(corps)
        except (ValueError, UnicodeDecodeError):
            raise ErreurApify("Apify n'a pas renvoyé un JSON exploitable.",
                             "apify_json") from None
        return resultat

    def _abandonner(self):
        """Arrêter un Actor encore actif : éviter de laisser courir les coûts."""
        if self.execution_id:
            try:
                # Un arrêt distant peut lui-même échouer ; ne jamais masquer
                # l'erreur ou l'annulation initiale.
                self._requete("POST",
                              "/actor-runs/" + self.execution_id + "/abort")
            except Exception:
                pass
            self.execution_id = None

    def decouvrir(self, compte, rapport, progression=None):
        """Démarrer une fois, attendre de façon bornée, récupérer les vidéos."""
        compte = normaliser_compte(compte)
        limite = min(1000, max(1, int(self.arguments.limit)))
        try:
            plafond_usd = float(os.environ.get("APIFY_MAX_CHARGE_USD", "1.0"))
        except ValueError:
            raise ErreurApify("APIFY_MAX_CHARGE_USD doit être un nombre.",
                             "apify_configuration") from None
        if not 0.01 <= plafond_usd <= 25.0:
            raise ErreurApify("Le plafond Apify doit être entre 0,01 et 25 USD.",
                             "apify_configuration")
        rapport.update(
            mode_decouverte="apify", technique="apify_actor_profile",
            version_collecteur=VERSION_APIFY, presse_moteur="apify",
            compte_attendu=compte, discovered_urls=[], metadonnees_api={},
            retenues_par_compte={compte: 0}, collecte_partielle=True,
            exhaustif=False, diagnostic={},
            limite_facturation_usd=plafond_usd,
            acteur_apify=ACTOR,
            requetes_tentees=0,
        )
        entree = construire_entree(compte, limite)
        try:
            execution = self._requete(
                "POST", "/acts/" + ACTOR + "/runs",
                {"maxItems": limite, "maxTotalChargeUsd": plafond_usd,
                 "timeout": 180, "restartOnError": "false"},
                entree)
            donnees_run = execution.get("data") if isinstance(execution, dict) else None
            if not isinstance(donnees_run, dict):
                raise ErreurApify("Apify n'a pas confirmé le lancement.", "apify_run_invalide")
            identifiant = donnees_run.get("id")
            if not isinstance(identifiant, str) or not re.fullmatch(
                    r"[A-Za-z0-9]{5,100}", identifiant):
                raise ErreurApify("Identifiant d'exécution Apify invalide.",
                                 "apify_run_invalide")
            self.execution_id = identifiant
            limite_temps = self.horloge() + 185
            statut = donnees_run.get("status")
            while statut not in ETATS_TERMINAUX:
                self.verifier()
                if self.horloge() >= limite_temps:
                    raise ErreurApify("L'exécution Apify a dépassé 185 secondes.",
                                     "apify_delai")
                self.pause(min(3.0, max(0.0, limite_temps - self.horloge())))
                reponse = self._requete("GET", "/actor-runs/" + identifiant)
                donnees_run = reponse.get("data") if isinstance(reponse, dict) else None
                if not isinstance(donnees_run, dict):
                    raise ErreurApify("Statut Apify illisible.", "apify_run_invalide")
                statut = donnees_run.get("status")
            if statut != "SUCCEEDED":
                raise ErreurApify(
                    "L'exécution Apify s'est terminée avec le statut " + str(statut) + ".",
                    "apify_execution_echec")
            dataset = donnees_run.get("defaultDatasetId")
            if not isinstance(dataset, str) or not re.fullmatch(
                    r"[A-Za-z0-9]{5,100}", dataset):
                raise ErreurApify("Apify n'a pas fourni de dataset.", "apify_dataset_absent")
            # Une exécution réussie n'a plus besoin d'être interrompue.
            self.execution_id = None
            resultats = self._requete(
                "GET", "/datasets/" + dataset + "/items",
                {"limit": limite, "format": "json", "clean": "true"})
            videos = normaliser_publications(resultats, compte, limite)
            rapport.update(
                metadonnees_api=videos,
                discovered_urls=[fiche["url"] for fiche in videos.values()],
                retenues_par_compte={compte: len(videos)},
                candidats_examines=len(resultats),
                collecte_partielle=len(videos) < limite,
                requetes_tentees=self.requetes,
                discovery_stop="limit" if len(videos) >= limite else "fin_dataset",
                bilan_recherche=(
                    f"@{compte} : {len(videos)} publication(s) vérifiée(s) via "
                    f"Apify ; {self.requetes} appels à son API."
                ),
            )
            if progression:
                progression(len(videos))
            if not videos:
                raise ErreurApify(
                    "Apify n'a fourni aucune vidéo vérifiée pour ce média.",
                    "apify_sans_videos")
            return list(rapport["discovered_urls"])
        except Exception as erreur:
            self._abandonner()
            if isinstance(erreur, ErreurApify):
                rapport["diagnostic"] = {
                    "code": erreur.code,
                    "statut_http": erreur.statut_http,
                    "requetes_apify": self.requetes,
                }
            raise

    def fermer(self):
        """Ne conserver ni jeton ni exécution distante après la collecte."""
        self._abandonner()
        self._cle = ""
