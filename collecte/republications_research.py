"""Republications des comptes TikTok publics via la Research API officielle.

La date de création appartient à la vidéo originale, non à sa republication.
L'absence d'un identifiant parmi les résultats ne prouve aucune non-republication.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date

from .researchapi import (
    ResearchAccesRefuse, ResearchErreur, _fiche, _jeton, _requete,
)
from .verification_comptes import normaliser_compte

URL_REPUBLICATIONS = "https://open.tiktokapis.com/v2/research/user/reposted_videos/"
CHAMPS_REPUBLICATIONS = (
    "id,create_time,username,region_code,video_description,"
    "like_count,comment_count,share_count,view_count,"
    "hashtag_names,video_duration,favorites_count"
)
MAX_PAGES_REPUBLICATIONS = 100


def url_republications():
    """Construire l'URL officielle avec les champs explicitement documentés."""
    return URL_REPUBLICATIONS + "?fields=" + CHAMPS_REPUBLICATIONS


def collecter_republications_research(compte, limite=100, *, debut=None, fin=None,
                                     verifier=None, pause=time.sleep,
                                     requete=_requete, jeton=None, credentiels=None,
                                     accepter=None, rapport=None):
    """Parcourir les republications publiques sans inventer les dates ou les absences.

    `accepter` reçoit la fiche de la vidéo originale, pour appliquer
    les filtres de date, de hashtags et de langue de la collecte principale.
    """
    compte = normaliser_compte(compte)
    limite = max(1, min(int(limite), 1000))
    controle = verifier or (lambda: None)
    diagnostic = rapport if rapport is not None else {}
    diagnostic.update(compte=compte, requetes=0, pages=0, candidats=0,
                      retenues=0, doublons=0, statut="en_cours",
                      pagination_terminee=False, exhaustif=False)
    controle()
    acces = jeton if jeton is not None else _jeton(
        requete=requete, credentiels=credentiels)
    if not isinstance(acces, str) or not acces:
        raise ResearchAccesRefuse("Research API : jeton absent pour les republications.")
    resultats = {}
    curseur = None
    curseurs_vus = set()
    limite_atteinte = False
    for page in range(MAX_PAGES_REPUBLICATIONS):
        controle()
        corps = {"username": compte,
                 "max_count": min(100, limite - len(resultats))}
        if curseur is not None:
            corps["cursor"] = curseur
        diagnostic["requetes"] += 1
        reponse = requete(url_republications(), data=json.dumps(corps).encode("utf-8"),
                          headers={"Authorization": "Bearer " + acces,
                                   "Content-Type": "application/json"})
        donnees = reponse.get("data")
        if not isinstance(donnees, dict):
            raise ResearchErreur("Research API : données de republications absentes.")
        # La documentation officielle varie entre l'exemple JSON et le tableau.
        videos = donnees.get("user_reposted_videos")
        if videos is None:
            videos = donnees.get("reposted_videos")
        if not isinstance(videos, list):
            raise ResearchErreur("Research API : liste des vidéos republiées absente.")
        diagnostic["pages"] += 1
        diagnostic["candidats"] += len(videos)
        for video in videos:
            fiche = _fiche(video, None)
            if fiche is None:
                continue
            identifiant = fiche["id"]
            if identifiant in resultats:
                diagnostic["doublons"] += 1
                continue
            # Des doublons d'une page précédente ne doivent pas remplir le budget.
            if accepter is not None and not accepter(fiche):
                continue
            cree = fiche.get("created_at") or ""
            if debut and (not cree or cree[:10] < debut):
                continue
            if fin and (not cree or cree[:10] > fin):
                continue
            fiche.update(
                compte_reposteur=compte,
                auteur_original=fiche["author"],
                id_video_originale=identifiant,
                type_publication="republication_par_compte",
                republication_confirmee=1,
                # Ne pas attribuer une date fictive à l'acte de republication.
                date_republication=None,
            )
            resultats[identifiant] = fiche
            if len(resultats) >= limite:
                limite_atteinte = True
                break
        diagnostic["retenues"] = len(resultats)
        if limite_atteinte:
            diagnostic["statut"] = "limite_atteinte"
            break
        if not donnees.get("has_more"):
            diagnostic["statut"] = "termine"
            diagnostic["pagination_terminee"] = True
            # Une pagination complète ne garantit pas l'exhaustivité :
            # TikTok peut omettre des vidéos supprimées ou privées.
            break
        nouveau = donnees.get("cursor")
        if not isinstance(nouveau, int) or nouveau < 0 or nouveau == curseur or nouveau in curseurs_vus:
            diagnostic["statut"] = "pagination_invalide"
            break
        curseurs_vus.add(nouveau)
        curseur = nouveau
        pause(1.0)
    else:
        diagnostic["statut"] = "plafond_pages"
    return list(resultats.values())


def rapprocher_republications(publications, republications):
    """Associer uniquement les identifiants identiques, sans codage négatif infondé."""
    rapprochements = {}
    for publication in republications:
        identifiant = str(publication.get("id_video_originale") or publication.get("id") or "")
        compte = publication.get("compte_reposteur")
        if identifiant and isinstance(compte, str) and compte:
            rapprochements.setdefault(identifiant, set()).add(compte)
    for publication in publications:
        identifiant = str(publication.get("id") or "")
        comptes = sorted(rapprochements.get(identifiant, ()))
        publication["type_publication"] = "publication_du_createur"
        publication["auteur_original"] = publication.get("author")
        publication["id_video_originale"] = identifiant
        publication["compte_reposteur"] = ", ".join(comptes) if comptes else ""
        publication["comptes_reposteurs"] = comptes
        publication["republication_confirmee"] = 1 if comptes else None
        publication["date_republication"] = None
    return len(rapprochements)
