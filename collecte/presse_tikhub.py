"""Collecte Presse via TikHub, indépendante des autres moteurs TikTok.

Endpoints documentés :
- /fetch_user_profile : uniqueId -> secUid
- /fetch_user_post : pages de 15 publications maximum
- /fetch_post_ai_article : itemCustomTDK, uniquement sur demande explicite

Les identifiants restent dans l'en-tête Authorization en mémoire. Les réponses
d'erreur ne sont pas copiées dans le journal afin de ne pas divulguer la clé.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import scraptiktok as moteur
from collecte.presse_api import _metadonnees_publication_api
from collecte.verification_comptes import normaliser_compte

HOTE = "https://api.tikhub.io"
PREFIXE = "/api/v1/tiktok/web"
MAX_REPONSE = 8_000_000
MAX_PAGES = 75
MAX_PUBLICATIONS = 1000
VERSION_TIKHUB = "tikhub-presse-v1"


class ErreurTikHub(RuntimeError):
    """Erreur maîtrisée, sans contenu brut ni secret d'authentification."""

    def __init__(self, message, code="tikhub_erreur", statut_http=None):
        self.code = code
        self.statut_http = statut_http
        super().__init__(message)


def cle_disponible(cle=None):
    """Vérifier une clé individuelle ou celle fournie par Coolify."""
    return bool((cle or os.environ.get("TIKHUB_API_KEY", "")).strip())


def _contenu(donnees):
    """Déplier uniquement les enveloppes connues, sans explorer des objets voisins."""
    resultat = donnees
    for _ in range(3):
        if isinstance(resultat, dict) and isinstance(resultat.get("data"), dict):
            resultat = resultat["data"]
        else:
            break
    return resultat if isinstance(resultat, dict) else {}


def _resume_ia(donnees):
    """Lire les champs IA natifs de TikTok, jamais la légende ou un texte inventé."""
    contenu = _contenu(donnees)
    tdk = contenu.get("itemCustomTDK")
    if not isinstance(tdk, dict):
        # Certains résultats enveloppent le contenu dans itemInfo.
        info = contenu.get("itemInfo")
        tdk = info.get("itemCustomTDK") if isinstance(info, dict) else None
    if not isinstance(tdk, dict):
        return {"resume_ia_tiktok": "", "statut_resume_ia": "absent",
                "source_resume_ia": "tikhub_itemCustomTDK"}
    desc = tdk.get("desc") if isinstance(tdk.get("desc"), str) else ""
    titre = tdk.get("title") if isinstance(tdk.get("title"), str) else ""
    article = tdk.get("article") if isinstance(tdk.get("article"), str) else ""
    mots = tdk.get("keywords")
    if not isinstance(mots, list):
        mots = []
    mots = [m.strip() for m in mots if isinstance(m, str) and m.strip()]
    return {
        "resume_ia_tiktok": desc.strip(),
        "statut_resume_ia": "recupere" if desc.strip() else "absent",
        "source_resume_ia": "tikhub_itemCustomTDK",
        "titre_ia_tiktok": titre.strip(),
        "article_ia_tiktok": article.strip(),
        "mots_cles_ia_tiktok": mots,
    }


def _profil_secuid(donnees, compte):
    """Valider l'identité avant de demander les publications."""
    contenu = _contenu(donnees)
    info = contenu.get("userInfo")
    utilisateur = info.get("user") if isinstance(info, dict) else None
    if not isinstance(utilisateur, dict):
        utilisateur = contenu.get("user")
    if not isinstance(utilisateur, dict):
        utilisateur = contenu
    nom = utilisateur.get("uniqueId") or utilisateur.get("unique_id")
    if isinstance(nom, str) and nom and nom.casefold() != compte.casefold():
        raise ErreurTikHub("TikHub a renvoyé un profil différent du média sélectionné.",
                          "tikhub_compte_incorrect")
    secuid = utilisateur.get("secUid") or utilisateur.get("sec_uid")
    if not isinstance(secuid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{20,250}", secuid):
        raise ErreurTikHub("TikHub ne fournit pas de secUid exploitable pour ce média.",
                          "tikhub_secuid_absent")
    return secuid


def _page_publications(donnees, compte, secuid, limite):
    """Valider chaque auteur et les champs essentiels d'une page de publications."""
    contenu = _contenu(donnees)
    if contenu.get("statusCode", contenu.get("status_code", 0)) not in (0, "0", None):
        raise ErreurTikHub("TikTok a refusé la liste des publications.", "tikhub_liste_refusee")
    elements = contenu.get("itemList")
    if not isinstance(elements, list):
        raise ErreurTikHub("Réponse TikHub sans itemList exploitable.",
                          "tikhub_itemlist_absente")
    publications = {}
    for item in elements:
        if not isinstance(item, dict):
            continue
        auteur = item.get("author")
        if not isinstance(auteur, dict):
            continue
        nom = auteur.get("uniqueId") or auteur.get("unique_id")
        auteur_secuid = auteur.get("secUid") or auteur.get("sec_uid")
        if not isinstance(nom, str) or nom.casefold() != compte.casefold():
            continue
        if auteur_secuid and auteur_secuid != secuid:
            continue
        identifiant = str(item.get("id") or "")
        if (not re.fullmatch(r"\d{5,30}", identifiant)
                or not isinstance(item.get("video"), dict)):
            continue
        publication = _metadonnees_publication_api(item, compte, identifiant)
        publication["source"] = "tikhub_user_post"
        publications.setdefault(identifiant, publication)
        if len(publications) >= limite:
            break
    has_more = contenu.get("hasMore", contenu.get("hasMorePrevious"))
    cursor = contenu.get("cursor", contenu.get("nextCursor"))
    return publications, has_more in (1, True, "1", "true"), cursor


class PresseTikHub:
    """Moteur payant indépendant, sans pagination infinie ni requête implicite."""

    def __init__(self, arguments, cle=None, verifier=None):
        self.arguments = arguments
        self.verifier = verifier or (lambda: None)
        self._cle = (cle or os.environ.get("TIKHUB_API_KEY", "")).strip()
        if not self._cle:
            raise ErreurTikHub("Renseignez la clé TikHub dans l'interface ou TIKHUB_API_KEY dans Coolify.",
                              "tikhub_cle_absente")
        self.nombre_requetes = 0

    def _requete(self, endpoint, parametres):
        """Appeler un seul endpoint documenté, avec arrêt immédiat si refus."""
        self.verifier()
        url = HOTE + PREFIXE + endpoint + "?" + urlencode(parametres)
        req = Request(url, headers={
            "Authorization": "Bearer " + self._cle,
            "Accept": "application/json",
            "User-Agent": "ScrapTikTok/1.0",
        })
        try:
            with urlopen(req, timeout=30) as reponse:
                brut = reponse.read(MAX_REPONSE + 1)
                statut = getattr(reponse, "status", 200)
        except HTTPError as erreur:
            statut = erreur.code
            code = "tikhub_limite" if statut == 429 else "tikhub_acces_refuse"
            raise ErreurTikHub(f"TikHub refuse la requête (HTTP {statut}).",
                              code, statut) from None
        except (URLError, TimeoutError, OSError):
            raise ErreurTikHub("TikHub est inaccessible depuis le serveur.", "tikhub_reseau") from None
        self.nombre_requetes += 1
        if statut != 200:
            raise ErreurTikHub(f"TikHub a répondu HTTP {statut}.",
                              "tikhub_http", statut)
        if len(brut) > MAX_REPONSE:
            raise ErreurTikHub("Réponse TikHub trop volumineuse.", "tikhub_taille")
        try:
            enveloppe = json.loads(brut)
        except (ValueError, UnicodeDecodeError):
            raise ErreurTikHub("TikHub a renvoyé une réponse non JSON.", "tikhub_json") from None
        if not isinstance(enveloppe, dict):
            raise ErreurTikHub("Réponse TikHub inattendue.", "tikhub_json")
        code = enveloppe.get("code")
        if code not in (200, "200", 0, "0"):
            raise ErreurTikHub("TikHub a refusé la demande (code applicatif non valide).",
                              "tikhub_code")
        if not isinstance(enveloppe.get("data"), dict):
            raise ErreurTikHub("TikHub ne fournit aucune donnée exploitable.",
                              "tikhub_donnees_absentes")
        return enveloppe

    def decouvrir(self, compte, rapport, progression=None):
        compte = normaliser_compte(compte)
        limite = min(MAX_PUBLICATIONS, max(1, int(self.arguments.limit)))
        rapport.update(mode_decouverte="tikhub", technique="tikhub_user_post",
                       presse_moteur="tikhub", version_collecteur=VERSION_TIKHUB,
                       compte_attendu=compte, discovered_urls=[],
                       metadonnees_api={}, retenues_par_compte={compte: 0},
                       exhaustif=False)
        try:
            identite = self._requete("/fetch_user_profile", {"uniqueId": compte})
            secuid = _profil_secuid(identite, compte)
            pages = 0
            cursor = 0
            vus = set()
            publications = {}
            while len(publications) < limite and pages < MAX_PAGES:
                self.verifier()
                pages += 1
                donnees = self._requete("/fetch_user_post", {
                    "secUid": secuid, "cursor": cursor,
                    "count": min(15, limite - len(publications)),
                })
                records, continuer, prochain = _page_publications(
                    donnees, compte, secuid, limite - len(publications))
                publications.update(records)
                rapport.update(discovered_urls=[r["url"] for r in publications.values()],
                               metadonnees_api=publications,
                               retenues_par_compte={compte: len(publications)},
                               candidats_examines=len(publications), pages_api=pages,
                               requetes_tentees=self.nombre_requetes)
                if progression:
                    progression(len(publications))
                if not continuer or len(publications) >= limite:
                    break
                if prochain is None or str(prochain) in vus or str(prochain) == str(cursor):
                    rapport["discovery_stop"] = "pagination_incoherente"
                    break
                vus.add(str(prochain))
                cursor = prochain
            rapport["collecte_partielle"] = len(publications) < limite
            rapport.setdefault("discovery_stop",
                               "limit" if len(publications) >= limite else "fin_pages")
            rapport["bilan_recherche"] = (
                f"@{compte} : {len(publications)} vidéo(s) vérifiée(s) via TikHub ; "
                f"{pages} page(s), {self.nombre_requetes} requête(s) facturables potentielles.")
            if not publications:
                raise ErreurTikHub("TikHub n'a fourni aucune vidéo de ce compte.",
                                  "tikhub_sans_videos")
            return list(rapport["discovered_urls"])
        except ErreurTikHub as erreur:
            rapport["diagnostic"] = {"code": erreur.code,
                                      "statut_http": erreur.statut_http}
            raise

    def lire_resume(self, url):
        """Lire uniquement le résumé natif, sur demande explicite de l'utilisateur."""
        identite = moteur.canonical_post(url)
        if identite is None:
            raise ErreurTikHub("URL vidéo TikTok invalide.", "tikhub_url")
        donnees = self._requete("/fetch_post_ai_article", {"itemId": identite[0]})
        return _resume_ia(donnees)

    def fermer(self):
        self._cle = ""
