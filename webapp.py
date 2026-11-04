"""Interface web : un navigateur isolé par collecte, piloté uniquement par son worker."""
from __future__ import annotations

import json
import hashlib
import signal
import sqlite3
import subprocess
import sys
import argparse
import base64
import hmac
import logging
import os
import queue
import re
import unicodedata
import secrets
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator, model_validator
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import scraptiktok as scraper
from language_filter import classify_description
from collecte.dates import normaliser_date, evaluer_periode
from collecte.selection_hashtags import normaliser_liste_hashtags
from collecte.suivi_sources import etablir_bilan_medias, exporter_bilan_medias_csv
from collecte.suivi_hashtags import (
    etablir_bilan_hashtags, exporter_bilan_hashtags_csv,
    preparer_reprise_hashtags)

LOG = logging.getLogger("scraptiktok.web")
TERMINAL = {"completed", "partial", "failed", "stopped"}
COOKIE = "scraptiktok_session"
HISTORIQUE_COOKIE = "scraptiktok_historique"


def session_terminee_inactive(job, maintenant, retention):
    """Ne supprimer qu'une session terminée, non consultée depuis le délai."""
    return (
        not job.busy and not job.video_busy
        and job.finished is not None
        and maintenant - max(job.finished, job.last_seen) > retention
    )


def nom_fichier_telechargement(nom_collecte, type_export, extension):
    """Nommer chaque export avec la collecte et son contenu, sans chemin local."""
    def nettoyer(texte, maximum):
        return re.sub(r"[^\w-]+", "_", str(texte or ""), flags=re.UNICODE).strip("_")[:maximum]
    nom = nettoyer(nom_collecte, 80) or "collecte"
    nature = nettoyer(type_export, 50) or "resultats"
    ext = nettoyer(str(extension).lstrip("."), 12) or "csv"
    return f"{nom}_{nature}.{ext}"


def entete_telechargement(nom):
    """Respecter les accents dans le nom proposé au navigateur."""
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"}



def texte_commentaires_collectes(job):
    """Restituer les commentaires dans le ZIP et dans le TXT individuel."""
    with job.lock:
        retenues = {str(p["id"]) for p in job.records}
        blocs = [
            f"*id_{c['publication_id']}\n@{c.get('auteur') or 'inconnu'}\n{c['texte']}"
            for c in job.commentaires
            if str(c["publication_id"]) in retenues
        ]
    return "\n\n".join(blocs) + ("\n" if blocs else "")


class SupprimerCollectePostgresPayload(BaseModel):
    """Confirmation explicite du nom exact avant une suppression définitive."""
    nom_confirmation: str = Field(min_length=1, max_length=160)


class ReprendreCollectePayload(BaseModel):
    """Paramètres de reprise sans modification des critères scientifiques."""
    medias: list[str] = Field(default_factory=list)
    research_client_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    research_client_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)


class ReprendreHashtagsPayload(BaseModel):
    """Hashtags inachevés à compléter dans le corpus PostgreSQL original."""
    hashtags: list[str] = Field(min_length=1, max_length=10)
    research_client_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    research_client_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)


class StartRequest(BaseModel):
    hashtag: str = Field(default="", max_length=100)
    source_collecte: Literal["hashtags", "comptes", "presse"] = "hashtags"
    nom_sauvegarde: str = Field(default="", max_length=120)
    comptes: list[str] = Field(default_factory=list, max_length=10)
    # Aucun plafond arbitraire de médias : l'inventaire valide les identifiants.
    # Les limites de requêtes et de pagination sont celles de la Research API.
    medias: list[str] = Field(default_factory=list)
    presse_moteur: Literal["api", "navigateur", "research", "gallerydl", "tikhub", "apify"] = "api"
    hashtag_moteur: Literal["api", "navigateur", "research", "gallerydl", "tikhub"] = "navigateur"
    profil_moteur: Literal["api", "navigateur", "research", "gallerydl", "tikhub"] = "navigateur"
    croiser_hashtag_presse: bool = False
    hashtag_presse: str = Field(default="", max_length=100)
    hashtags_presse: list[str] = Field(default_factory=list, max_length=10)
    operator_presse: Literal["AND", "OR"] = "AND"
    collecter_republications_research: bool = False
    maximum_republications_par_compte: int = Field(default=100, ge=1, le=1000)
    # Secrets fournis à chaque collecte, jamais sérialisés dans SQLite / ZIP
    # ni exposés par snapshot(), model_dump() ou les diagnostics.
    research_client_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    research_client_secret: SecretStr | None = Field(default=None, exclude=True, repr=False)
    tikhub_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    apify_api_token: SecretStr | None = Field(default=None, exclude=True, repr=False)
    cookies_tiktok: SecretStr | None = Field(default=None, exclude=True, repr=False, max_length=1_048_576)
    enrichir: bool = False
    telecharger_mp4: bool = False
    sauvegarde_progressive: bool = False
    collecter_commentaires: bool = False
    # Par défaut historique, les API existantes conservent leurs exports TXT.
    # L'interface transmet explicitement False pour les nouvelles collectes.
    inclure_commentaires_txt: bool = True
    collecter_reponses: bool = False
    collecter_follower_count: bool = False
    collecter_is_verified: bool = False
    # Indicateurs agrégés des médias : distincts des métriques par vidéo.
    profils_medias_variables: list[Literal[
        "following_count", "follower_count", "likes_count", "video_count"
    ]] = Field(default_factory=list, max_length=4)
    profils_medias_classes: list[Literal[
        "following_count", "follower_count", "likes_count", "video_count"
    ]] = Field(default_factory=list, max_length=4)
    follower_count_illustratif: bool = False
    abonnes_classe_illustratif: bool = False
    variables_classes_txt: list[Literal["vues", "likes", "commentaires", "partages", "favoris", "duree"]] = Field(default_factory=list, max_length=6)
    taux_engagement_txt: Literal["aucun", "brut", "classes", "brut_et_classes"] = "aucun"
    limite_commentaires: int = Field(default=50, ge=1, le=500)
    second_hashtag: str = Field(default="", max_length=100)
    hashtags_saisis: list[str] = Field(default_factory=list)
    hashtags_exclus: list[str] = Field(default_factory=list)
    operator: Literal["AND", "OR"] = "AND"
    rechercher_dans_texte: bool = False
    variantes_accents: bool = False
    region_fr_research: bool = False
    # None signifie une recherche Research paginée sans plafond local.
    # Les moteurs non Research conservent leur limite numérique.
    limit: int | None = Field(default=50, ge=1, le=1000)
    collecte_research_complete: bool = False
    test_research_10_publications: bool = False
    # Taille des lots de candidats API avant contrôle humain.
    # Le max_count officiel reste fixé à 100 par requête.
    lot_candidats_research: int = Field(default=1000, ge=100, le=5000)
    include_sources: bool = True
    inclure_metadonnees_txt: bool = False
    inclure_texte_genere_ia: bool = False
    filtrer_texte_ia_tiktok: bool = False
    inclure_hashtags_csv: bool = False
    supprimer_arobase_profil: bool = False
    # None conserve les anciennes requêtes ; une liste vide demande le texte seul.
    variables_txt: list[Literal["date", "profil", "id", "vues", "likes", "partages", "commentaires", "favoris", "duree", "region_code", "is_verified", "hashtags"]] | None = Field(default=None, max_length=12)
    french_only: bool = False
    date_debut: str | None = Field(default=None, max_length=10)
    date_fin: str | None = Field(default=None, max_length=10)

    @field_validator("nom_sauvegarde")
    @classmethod
    def valider_nom_sauvegarde(cls, valeur):
        """Nettoyer le nom affiché sans accepter de caractères de contrôle."""
        nom = valeur.strip()
        if not nom:
            # Les sessions antérieures n'avaient pas de nom de sauvegarde.
            # Seules les nouvelles requêtes HTTP exigent un nom explicite.
            return ""
        if any(ord(caractere) < 32 or ord(caractere) == 127 for caractere in nom):
            raise ValueError("Le nom de la sauvegarde contient un caractère interdit.")
        return nom

    @field_validator("variables_txt", mode="before")
    @classmethod
    def valider_variables_txt(cls, valeurs):
        # Garder les anciennes sélections, en lisant désormais le vrai compteur de partages.
        if isinstance(valeurs, (list, tuple)) and all(isinstance(v, str) for v in valeurs):
            return normaliser_variables_txt(valeurs)
        return valeurs

    @field_validator("date_debut", "date_fin")
    @classmethod
    def valider_date(cls, valeur):
        return normaliser_date(valeur)

    @field_validator("hashtag")
    @classmethod
    def valid_hashtag(cls, value):
        if not value.strip(): return ""
        try:
            return scraper.normalize_hashtag(value)
        except argparse.ArgumentTypeError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("hashtag_presse")
    @classmethod
    def valider_hashtag_presse(cls, valeur):
        # Le croisement s'appuie sur le même validateur que la collecte hashtags.
        return cls.valid_hashtag(valeur) if valeur.strip() else ""

    @field_validator("second_hashtag")
    @classmethod
    def valid_second_hashtag(cls, value):
        return cls.valid_hashtag(value) if value.strip() else ""

    @field_validator("hashtags_saisis", "hashtags_exclus", "hashtags_presse")
    @classmethod
    def valider_hashtags_saisis(cls, valeurs):
        return normaliser_liste_hashtags(valeurs)

    @field_validator("comptes")
    @classmethod
    def valider_comptes(cls, valeurs):
        from collecte.verification_comptes import normaliser_compte
        return list(dict.fromkeys(normaliser_compte(v) for v in valeurs))

    @model_validator(mode="after")
    def valider_sources(self, info: ValidationInfo):
        if self.date_debut and self.date_fin and self.date_debut > self.date_fin:
            raise ValueError("La date de début doit précéder ou égaler la date de fin.")
        # Le filtrage implique la lecture effective du résumé natif de TikTok.
        # L'indicateur de contenu IA fourni par l'API ne constitue pas ce texte.
        if self.filtrer_texte_ia_tiktok:
            self.inclure_texte_genere_ia = True
        # Les métriques de comptes ne sont pas un export de vidéos et ne
        # peuvent être collectées sur un moteur non officiel.
        self.profils_medias_variables = list(dict.fromkeys(
            self.profils_medias_variables))
        self.profils_medias_classes = list(dict.fromkeys(
            self.profils_medias_classes))
        if self.profils_medias_classes and not set(
                self.profils_medias_classes).issubset(self.profils_medias_variables):
            raise ValueError(
                "Une segmentation de profil nécessite la collecte du compteur correspondant.")
        if (self.profils_medias_variables and
                (self.source_collecte not in {"presse", "hashtags"}
                 or self.moteur_actif != "research")):
            raise ValueError(
                "Les métriques des profils sont disponibles en modes Presse et "
                "Hashtags avec la Research API officielle.")
        if (self.collecter_republications_research and
                (self.source_collecte != "presse" or self.presse_moteur != "research")):
            raise ValueError(
                "La récupération des republications est réservée au mode "
                "Presse et médias avec Research API officielle.")
        if self.source_collecte == "presse" and self.presse_moteur == "apify":
            from collecte.presse_apify import cle_disponible
            jeton = self.apify_api_token.get_secret_value().strip() if self.apify_api_token else ""
            if not cle_disponible(jeton):
                raise ValueError("Apify : saisir le jeton API ou renseigner APIFY_API_TOKEN dans Coolify.")
        if self.moteur_actif == "tikhub":
            from collecte.presse_tikhub import cle_disponible
            cle = self.tikhub_api_key.get_secret_value().strip() if self.tikhub_api_key else ""
            if not cle_disponible(cle):
                raise ValueError("TikHub : saisir une clé API ou renseigner TIKHUB_API_KEY dans Coolify.")
        if self.moteur_actif == "research":
            cle = self.research_client_key.get_secret_value().strip() if self.research_client_key else ""
            secret = (self.research_client_secret.get_secret_value().strip()
                      if self.research_client_secret else "")
            if bool(cle) != bool(secret):
                raise ValueError("Research API : saisir les deux identifiants ensemble.")
            from collecte.presse_research import identifiants_disponibles
            # Une archive peut être consultée sans fournir de nouveau
            # les secrets ; tout nouveau lancement conserve la règle stricte.
            consultation = bool((info.context or {}).get("consultation_historique"))
            if not (cle and secret) and not identifiants_disponibles() and not consultation:
                raise ValueError("Research API : renseigner Client key et Client secret dans l'application.")
        if self.source_collecte == "presse":
            # Les anciens champs de recherche ne s'appliquent pas aux médias.
            # Le croisement est une option indépendante, explicite et facultative.
            self.hashtag = ""
            self.second_hashtag = ""
            self.hashtags_saisis = []
            self.rechercher_dans_texte = False
            self.variantes_accents = False
            if self.croiser_hashtag_presse:
                # La liste prévaut ; le champ unique assure la compatibilité historique.
                if not self.hashtags_presse and self.hashtag_presse:
                    self.hashtags_presse = [self.hashtag_presse]
                if not self.hashtags_presse:
                    raise ValueError("Saisissez au moins un hashtag à croiser avec les médias.")
                self.hashtag_presse = self.hashtags_presse[0]
            else:
                self.hashtag_presse = ""
                self.hashtags_presse = []
        else:
            self.croiser_hashtag_presse = False
            self.hashtag_presse = ""
            self.hashtags_presse = []
            # Préserver les anciens clients utilisant hashtag et second_hashtag.
            # Lorsqu'une liste est fournie, elle constitue la sélection de référence.
            if not self.hashtags_saisis:
                self.hashtags_saisis = normaliser_liste_hashtags(
                    [valeur for valeur in (self.hashtag, self.second_hashtag) if valeur])
            if not self.hashtags_saisis:
                if self.source_collecte == "comptes":
                    raise ValueError("Renseignez au moins un hashtag pour une collecte par profil.")
                raise ValueError("Renseignez au moins un hashtag.")
            self.hashtag = self.hashtags_saisis[0]
            self.second_hashtag = (
                self.hashtags_saisis[1] if len(self.hashtags_saisis) > 1 else "")
        if self.source_collecte == "comptes" and not self.comptes:
            raise ValueError("Renseignez au moins un compte TikTok.")
        inclus = ({nom.casefold() for nom in self.hashtags_saisis}
                  if self.source_collecte != "presse" else
                  ({nom.casefold() for nom in self.hashtags_presse}
                   if self.croiser_hashtag_presse else set()))
        conflits = inclus.intersection(nom.casefold() for nom in self.hashtags_exclus)
        if conflits:
            raise ValueError("Un hashtag ne peut pas être recherché et exclu : "
                             + ", ".join("#" + nom for nom in sorted(conflits)))
        if self.source_collecte == "presse":
            from collecte.presse import selectionner_medias
            if not self.medias: raise ValueError("Sélectionnez au moins un média.")
            selectionner_medias(self.medias)
        if not self.collecter_commentaires:
            self.collecter_reponses = False
            self.inclure_commentaires_txt = False
        # Le code FR concerne l'enregistrement du compte, pas la langue
        # du texte ni nécessairement le lieu de prise de vue.
        if self.source_collecte != "hashtags" or self.moteur_actif != "research":
            self.region_fr_research = False
        # Research API : pagination sans plafond local de publications.
        # Le mode test explicite reste limité à dix vidéos au total.
        if self.moteur_actif == "research":
            self.collecte_research_complete = True
            self.limit = 10 if self.test_research_10_publications else None
        elif self.limit is None:
            raise ValueError(
                "Une limite numérique est nécessaire avec un moteur non Research.")
        # Les compteurs de profils ne sont demandés que sur le moteur officiel.
        if self.moteur_actif != "research":
            self.test_research_10_publications = False
            self.collecte_research_complete = False
            self.collecter_follower_count = False
            self.collecter_is_verified = False
        elif self.variables_txt is not None and "is_verified" in self.variables_txt:
            # L'export illustratif demande aussi la récupération du profil.
            self.collecter_is_verified = True
        if not self.collecter_follower_count:
            self.follower_count_illustratif = False
            self.abonnes_classe_illustratif = False
        # Éviter deux fois la même modalité dans un seul en-tête.
        self.variables_classes_txt = list(dict.fromkeys(self.variables_classes_txt))
        if (self.source_collecte == "hashtags"
                and self.moteur_actif == "research"
                and not (info.context or {}).get("consultation_historique")
                and not (info.context or {}).get("reprise_historique")):
            # Figer la fenêtre UTC lors du premier lancement : une reprise
            # le lendemain ne doit pas déplacer le corpus de 24 heures.
            aujourd_hui = datetime.now(timezone.utc).date()
            borne_fin = (date.fromisoformat(self.date_fin)
                         if self.date_fin else aujourd_hui)
            borne_debut = (date.fromisoformat(self.date_debut)
                           if self.date_debut else borne_fin - timedelta(days=29))
            self.date_debut = borne_debut.isoformat()
            self.date_fin = borne_fin.isoformat()
        return self

    @property
    def moteur_actif(self):
        """Conserver le moteur propre à chacun des trois modes."""
        return (self.presse_moteur if self.source_collecte == "presse" else
                self.profil_moteur if self.source_collecte == "comptes" else
                self.hashtag_moteur)

    @property
    def enrichie(self):
        return (self.enrichir or self.source_collecte != "hashtags"
                or self.moteur_actif == "research"
                or self.collecter_commentaires or self.telecharger_mp4
                or self.filtrer_texte_ia_tiktok)

    @property
    def libelle(self):
        if self.source_collecte == "hashtags":
            return (" OU " if self.operator == "OR" else " ET ").join("#" + h for h in self.hashtags)
        libelle = ", ".join("@" + s["compte"] for s in self.sources)
        if self.source_collecte == "presse" and self.croiser_hashtag_presse:
            libelle += " × (" + (" OU " if self.operator_presse == "OR" else " ET ").join("#" + h for h in self.hashtags_presse) + ")"
        return libelle

    @property
    def sources(self):
        from collecte.presse import selectionner_medias
        if self.source_collecte == "presse": return selectionner_medias(self.medias)
        return [{"compte": c, "id": None, "categorie": None} for c in self.comptes]

    @property
    def hashtags(self):
        return list(self.hashtags_saisis)

    @property
    def filename(self):
        # Les noms de sauvegarde deviennent des noms de fichiers sûrs.
        if self.nom_sauvegarde:
            nom_fichier = re.sub(r"[^\w-]+", "_", self.nom_sauvegarde, flags=re.UNICODE).strip("_")[:100]
            if nom_fichier:
                return nom_fichier + ".txt"
        joiner = "_ET_" if self.operator == "AND" else "_OU_"
        nom = (joiner.join(self.hashtags) if self.source_collecte == "hashtags"
               else "comptes_" + "_".join(s["compte"] for s in self.sources)[:100])
        if self.source_collecte == "presse" and self.croiser_hashtag_presse:
            nom += "_hashtag_" + ("_OU_" if self.operator_presse == "OR" else "_ET_").join(self.hashtags_presse)
        # Dix hashtags longs peuvent dépasser la limite de nom du système de fichiers.
        if len(nom.encode("utf-8")) > 160:
            empreinte = hashlib.sha256(nom.encode("utf-8")).hexdigest()[:12]
            nom = nom.encode("utf-8")[:140].decode("utf-8", "ignore").rstrip("_")
            nom = f"{nom}_{empreinte}"
        return "tiktok_" + nom + ("_fr" if self.french_only else "") + ".txt"


def tag_key(value):
    return unicodedata.normalize("NFC", value).casefold()


def normaliser_terme_texte(texte):
    """Comparaison facultative des mots, sans différence entre é et e."""
    return "".join(caractere for caractere in unicodedata.normalize("NFD", tag_key(texte))
                   if not unicodedata.combining(caractere))


def correspondance_hashtag(description, hashtag, *, rechercher_dans_texte=False,
                           variantes_accents=False):
    """Comparer un hashtag entier ; lire les mots de la légende seulement sur demande."""
    texte = tag_key(description or "")
    terme = tag_key(hashtag).removeprefix("#")
    presents = set(re.findall(r"#(\w+)", texte))
    if terme in presents:
        return True
    if variantes_accents and normaliser_terme_texte(terme) in {
            normaliser_terme_texte(present) for present in presents}:
        return True
    if not rechercher_dans_texte:
        return False

    texte = normaliser_terme_texte(texte)
    terme = normaliser_terme_texte(terme)
    # L'option texte accepte les accents et des expressions telles que
    # #17octobre -> "17 octobre" ou #lyceens_en_colere -> "lycéens en colère".
    parties = re.findall(r"\d+|[^\W\d_]+", terme)
    separateur = bool("_" in terme or (len(parties) > 1 and any(p.isdecimal() for p in parties)))
    motif = re.escape(terme)
    if separateur and len(parties) > 1:
        # Accepter également la graphie compacte (« 17octobre »).
        motif = "(?:" + motif + "|" + r"[\s_]+".join(map(re.escape, parties)) + ")"
    return re.search(r"(?<!\w)" + motif + r"(?!\w)", texte) is not None


def hashtags_correspondants_presse(description, settings, hashtags_observes=None):
    """Identifier précisément les hashtags recherchés présents dans une publication."""
    if not settings.croiser_hashtag_presse:
        return []
    # Le tableau issu de Research contient les hashtags officiels.
    # La légende sert de repli pour les moteurs qui ne les fournissent pas.
    observations = (
        {str(tag).lstrip("#").casefold() for tag in hashtags_observes
         if isinstance(tag, str)}
        if isinstance(hashtags_observes, (list, tuple)) and hashtags_observes else None
    )
    return [
        hashtag for hashtag in settings.hashtags_presse
        if (hashtag.casefold() in observations if observations is not None
            else correspondance_hashtag(description, hashtag))
    ]


def hashtags_correspondants_publication(description, settings, hashtags_observes=None):
    """Confronter les hashtags recherchés aux métadonnées puis à la légende.

    La Research API fournit les hashtags dans un champ distinct du texte.
    Le moteur Presse exploite déjà ce champ : le mode Hashtags doit lui aussi
    conserver les légendes correspondantes même si elles ne répètent pas le #tag.
    L'option de recherche dans le texte reste facultative et additive.
    """
    observations = (
        {tag.lstrip("#").casefold() for tag in hashtags_observes
         if isinstance(tag, str)}
        if isinstance(hashtags_observes, (list, tuple)) else set()
    )
    observations_normalisees = (
        {normaliser_terme_texte(tag) for tag in observations}
        if settings.variantes_accents else set()
    )
    correspondants = []
    for hashtag in settings.hashtags:
        cle = hashtag.casefold()
        trouve_api = (
            cle in observations
            or (settings.variantes_accents
                and normaliser_terme_texte(cle) in observations_normalisees)
        )
        # Un #hashtag explicitement écrit dans la légende reste une
        # correspondance exacte, même si hashtag_names est incomplet.
        # Seuls les mots sans # nécessitent l'option complémentaire.
        trouve_texte = correspondance_hashtag(
            description, hashtag,
            rechercher_dans_texte=settings.rechercher_dans_texte,
            variantes_accents=settings.variantes_accents)
        if trouve_api or trouve_texte:
            correspondants.append(hashtag)
    return correspondants


def matches_hashtags(description, settings, *, hashtags_observes=None):
    if settings.source_collecte == "presse":
        if not settings.croiser_hashtag_presse:
            return True
        concordances = hashtags_correspondants_presse(
            description, settings, hashtags_observes)
        return (len(concordances) == len(settings.hashtags_presse)
                if settings.operator_presse == "AND" else bool(concordances))
    correspondants = hashtags_correspondants_publication(
        description, settings, hashtags_observes)
    if not settings.hashtags:
        return False
    return (len(correspondants) == len(settings.hashtags)
            if settings.operator == "AND" else bool(correspondants))


def verifier_criteres_hashtags_research(fiche, parametres):
    """Vérifier les hashtags et, sur demande, le pays du compte créateur."""
    if not isinstance(fiche, dict):
        return False
    if (parametres.region_fr_research
            and str(fiche.get("region_code") or "").upper() != "FR"):
        return False
    return matches_hashtags(
        fiche.get("description") or "", parametres,
        hashtags_observes=fiche.get("hashtags"))


def filtrer_decouverte_hashtags_research(liens, metadonnees, parametres):
    """Écarter avant lecture les vidéos Research ne correspondant pas aux hashtags.

    La découverte par hashtag peut retourner une vidéo portant uniquement le
    premier hashtag, y compris lorsque ET est sélectionné. Les métadonnées de
    la Research API permettent de vérifier immédiatement tous les critères,
    avec les mêmes règles que l'export TXT, sans ouvrir la vidéo.
    """
    conserves = []
    ecartes = 0
    indetermines = 0
    for url in liens:
        identite = scraper.canonical_post(url)
        fiche = (metadonnees.get(str(identite[0]))
                 if identite and isinstance(metadonnees, dict) else None)
        if not isinstance(fiche, dict):
            # Une vidéo non vérifiable ne peut pas être déclarée conforme.
            indetermines += 1
            continue
        if not verifier_criteres_hashtags_research(fiche, parametres):
            ecartes += 1
            continue
        conserves.append(url)
    return conserves, ecartes, indetermines


class CodageViolence(BaseModel):
    publication_id: str = Field(min_length=1, max_length=32, pattern=r"^[0-9]+$")
    violence_visible: Literal[0, 1] | None


class AnnotationsViolence(BaseModel):
    annotations: list[CodageViolence] = Field(min_length=1, max_length=1000)


class NomVariableCodage(BaseModel):
    nom: str = Field(min_length=2, max_length=70)


class ModificationCodage(BaseModel):
    variable_id: str = Field(pattern=r"^codage_[a-f0-9]{12}$")
    publication_id: str = Field(min_length=1,max_length=32,pattern=r"^[0-9]+$")
    valeur: Literal[0, 1] | None


class ModificationsCodages(BaseModel):
    annotations: list[ModificationCodage] = Field(min_length=1, max_length=2000)


class Point(BaseModel):
    x: float = Field(ge=0, le=1, allow_inf_nan=False)
    y: float = Field(ge=0, le=1, allow_inf_nan=False)
    

class BrowserAction(BaseModel):
    kind: Literal["click", "drag", "pointer_down", "pointer_move", "pointer_up", "pointer_cancel", "text", "key", "scroll"]
    points: list[Point] = Field(default_factory=list, max_length=80)
    text: str = Field(default="", max_length=2000)
    key: Literal["Enter", "Tab", "Backspace", "Escape", "select_all"] = "Enter"
    delta: int = Field(default=0, ge=-1200, le=1200)


class Stopped(Exception):
    pass


class LiveAction:
    def __init__(self, action):
        self.action = action
        self.done = threading.Event()
        self.error = ""


def normaliser_variables_txt(variables):
    """Migrer les sélections anciennes et retirer l’indicateur IA abandonné."""
    if variables is None:
        return None
    return list(dict.fromkeys({"republications": "partages", "url": "id"}.get(v, v)
                             for v in variables if v != "contenu_genere_ia"))


def texte_ia_tiktok_exploitable(publication):
    """Ne retenir qu'un résumé TikTok effectivement lu et distinct de la légende."""
    resume = publication.get("resume_ia_tiktok")
    if not isinstance(resume, str) or not resume.strip():
        return False
    if publication.get("statut_resume_ia") in ("erreur_lecture", "non_trouve", "desactive", "absent"):
        return False
    nettoyer = lambda texte: re.sub(r"\s+", " ", str(texte or "")).strip().casefold()
    return nettoyer(resume) != nettoyer(publication.get("description"))


def entete_publication(publication: dict, variables=None, supprimer_arobase_profil=False,
                       follower_count_illustratif=False,
                       abonnes_classe_illustratif=False,
                       variables_classes_txt=None, taux_engagement_txt="aucun") -> str:
    """Écrire les variables choisies au format *nom_valeur sur une seule ligne."""
    from datetime import datetime

    def modalite(valeur):
        return ("_".join(str(valeur).split()) or "indetermine") if valeur is not None else "indetermine"

    try:
        date_publication = datetime.fromisoformat(str(publication.get("created_at") or "").replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        date_publication = "indetermine"
    profil = modalite(publication.get("author"))
    if publication.get("author"):
        profil = ("" if supprimer_arobase_profil else "@") + profil.lstrip("@")

    def compteur(nom):
        mesure = (publication.get("engagement") or {}).get(nom) or {}
        # Zéro est une observation valide. Les détails des mesures restent dans le JSON.
        return modalite(mesure.get("valeur"))

    from collecte.variables_profil import normaliser_region, modalite_verification
    region = normaliser_region(publication.get("region_code"))
    valeurs = {"date": f"*date_{date_publication}",
               "profil": f"*profil_{profil}", "id": f"*id_{modalite(publication.get('id'))}",
               "vues": f"*vues_{compteur('vues')}", "likes": f"*likes_{compteur('likes')}",
               "partages": f"*partages_{compteur('partages')}",
               "commentaires": f"*comment_{compteur('commentaires')}",
               "favoris": f"*favoris_{compteur('favoris')}",
               "duree": f"*duree_{modalite(publication.get('video_duration'))}",
               "region_code": f"*region_{region if region else 'indetermine'}",
               "is_verified": f"*is_verified_{modalite_verification(publication.get('is_verified'))}"}
    # Les anciens appels sans sélection gardent leur en-tête à trois variables.
    selection = set(normaliser_variables_txt(variables) if variables is not None else ("date", "profil", "id"))
    entete = " ".join(texte for cle, texte in valeurs.items() if cle in selection)
    if follower_count_illustratif:
        compteur_abonnes = publication.get("follower_count")
        # Une donnée absente ne doit jamais être interprétée comme zéro.
        valeur = (str(compteur_abonnes) if isinstance(compteur_abonnes, int)
                  and not isinstance(compteur_abonnes, bool) and compteur_abonnes >= 0
                  else "indetermine")
        entete = f"*follower_count_{valeur}" + (" " + entete if entete else "")
    if abonnes_classe_illustratif:
        from collecte.classes_abonnes import classer_nombre_abonnes
        classe = classer_nombre_abonnes(publication.get("follower_count"))
        # Une modalité partagée remplace les valeurs rares propres à chaque auteur.
        entete = f"*{classe}" + (" " + entete if entete else "")
    if variables_classes_txt or taux_engagement_txt != "aucun":
        from collecte.variables_numeriques import (
            classer_compteur, valeur_variable, calculer_taux_engagement,
            classer_taux_engagement, modalite_taux_brut)
        classes = [
            "*" + classer_compteur(nom, valeur_variable(publication, nom))
            for nom in (variables_classes_txt or [])
        ]
        if taux_engagement_txt != "aucun":
            taux = calculer_taux_engagement(publication)
            # Le recodage complète la valeur numérique au lieu de la remplacer.
            if taux_engagement_txt in ("brut", "brut_et_classes"):
                classes.append("*" + modalite_taux_brut(taux))
            if taux_engagement_txt in ("classes", "brut_et_classes"):
                classes.append("*" + classer_taux_engagement(taux))
        if classes:
            entete = " ".join(classes) + (" " + entete if entete else "")
    # La catégorie du média s'ajoute au profil sans dépendre des autres cases.
    from collecte.presse import code_presse_publication
    code_presse = code_presse_publication(publication)
    if code_presse:
        entete = (entete + " " if entete else "") + "*" + code_presse
    return entete + "\n" if entete else ""


def texte_et_hashtags(publication):
    """Déplacer les hashtags sous la légende pour le TXT sans modifier les données."""
    description = publication.get("description") or ""
    hashtags = publication.get("hashtags")
    if not isinstance(hashtags, list):
        hashtags = []
    # Inclure aussi les tags présents dans le texte si la liste structurée est incomplète.
    # Les fragments d’URL ne doivent pas être supprimés du texte comme des hashtags.
    motif = re.compile(r"https?://\S+|#(\w+)")
    hashtags = [*hashtags, *(m.group(1) for m in motif.finditer(description) if m.group(1))]
    uniques = {}
    for hashtag in hashtags:
        hashtag = str(hashtag).strip().lstrip("#")
        if re.fullmatch(r"\w+", hashtag):
            uniques.setdefault(hashtag.casefold(), "#" + hashtag)
    if not uniques:
        return description
    texte = motif.sub(lambda m: "" if m.group(1) else m.group(0), description)
    # Conserver les retours à la ligne du texte ; nettoyer les espaces laissés par les tags.
    texte = "\n".join(re.sub(r"[ \t]{2,}", " ", ligne).strip() for ligne in texte.split("\n")).strip()
    return (texte + "\n" if texte else "") + " ".join(uniques.values())


def entete_sources_ia(publication, source, themes=None, variables=""):
    """Identifier la provenance du texte dans un corpus IRaMuTeQ."""
    def modalite(valeur):
        texte = re.sub(r"[^\w-]+", "_", str(valeur or "").casefold().lstrip("@#")).strip("_")
        return texte or "indetermine"

    theme = next(iter(publication.get("hashtags_correspondants") or []), None)
    if not theme:
        theme = next((mot for mot in (themes or []) if mot), None)
    if not theme:
        theme = next(iter(publication.get("hashtags") or []), None)
    return (f"**** *source_{source} *theme_{modalite(theme)}"
            + (" " + variables.strip() if variables.strip() else "") + "\n")


def text_export(records: list[dict], include_sources: bool, inclure_metadonnees_txt: bool = False,
                variables_txt=None, commentaires=None, supprimer_arobase_profil=False,
                inclure_texte_genere_ia=False, themes=None,
                follower_count_illustratif=False,
                abonnes_classe_illustratif=False,
                variables_classes_txt=None, taux_engagement_txt="aucun") -> str:
    blocks = []
    par_publication = {}
    selection = normaliser_variables_txt(variables_txt)
    for commentaire in commentaires or []:
        if commentaire.get("texte"):
            par_publication.setdefault(str(commentaire.get("publication_id")), []).append(commentaire)
    for record in records:
        if not record.get("description"):
            continue
        options_classes = {
            "follower_count_illustratif": follower_count_illustratif,
            "abonnes_classe_illustratif": abonnes_classe_illustratif,
            "variables_classes_txt": variables_classes_txt,
            "taux_engagement_txt": taux_engagement_txt,
        }
        if selection is not None:
            prefix = entete_publication(
                record, selection, supprimer_arobase_profil, **options_classes)
        elif inclure_metadonnees_txt:
            prefix = entete_publication(
                record, supprimer_arobase_profil=supprimer_arobase_profil,
                **options_classes)
        elif include_sources:
            prefix = entete_publication(
                record, ("profil", "id"), supprimer_arobase_profil,
                **options_classes)
        elif (follower_count_illustratif or abonnes_classe_illustratif
              or variables_classes_txt or taux_engagement_txt != "aucun"):
            prefix = entete_publication(
                record, (), supprimer_arobase_profil, **options_classes)
        else:
            # Même sans métadonnées sélectionnées, le code du média est conservé.
            from collecte.presse import code_presse_publication
            prefix = (entete_publication(record, (), supprimer_arobase_profil)
                      if code_presse_publication(record) else "")
        # Le lien texte/MP4 reste présent même si la case ID vidéo était décochée.
        if record.get("video_id") and not re.search(r"(?:^| )\*id_", prefix):
            prefix = prefix.rstrip("\n") + (" " if prefix else "") + f"*id_{record['video_id']}\n"
        texte = texte_et_hashtags(record) if selection and "hashtags" in selection else record["description"]
        if inclure_texte_genere_ia:
            bloc = entete_sources_ia(record, "original", themes, prefix) + texte
        else:
            bloc = prefix + texte
        for numero, commentaire in enumerate(par_publication.get(str(record["id"]), []), 1):
            etiquette = "Réponse" if commentaire.get("est_reponse") else "Commentaire"
            bloc += f"\n\n{etiquette} {numero} :\n{commentaire['texte']}"
        blocks.append(bloc)
        if inclure_texte_genere_ia:
            resume_ia = (record.get("resume_ia_tiktok") or "").strip()
            if resume_ia and resume_ia != (record.get("description") or "").strip():
                blocks.append(entete_sources_ia(record, "ia", themes, prefix) + resume_ia)
    return "\n\n".join(blocks) + ("\n" if blocks else "")


CAUSES_ARRET = {
    'utilisateur': 'Bouton Arrêter la collecte utilisé.',
    'acces_inactif': 'Accès libéré, expiré ou devenu inactif.',
    'inactivite': 'Délai sans contact avec l’interface dépassé.',
    'duree_maximale': 'Durée maximale autorisée pour la collecte atteinte.',
    'arret_serveur': 'Arrêt ou redémarrage du serveur.',
}


class Job:
    def __init__(self, owner: str, settings: StartRequest, data_dir: Path, *,
                 identifiant=None, archive_directory=None, owner_historique="", reprise=False):
        self.id = identifiant or uuid.uuid4().hex
        self.owner = owner
        self.owner_historique = owner_historique
        self.historique = archive_directory is not None
        self.reprise = bool(reprise)
        self.medias_reprise = []
        self.hashtags_reprise = []
        self.sources_reprise_hashtags = []
        self.reprise_decalage = 0
        self.publications_avant_reprise = 0
        self.settings = settings
        self.racine = data_dir
        if archive_directory is not None:
            self.directory = Path(archive_directory)
        elif settings.enrichie:
            from stockage.sessions import creer_dossier_session
            self.directory = creer_dossier_session(data_dir, self.id)
        else:
            self.directory = data_dir / self.id
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "textes.txt"
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.diagnostics = []
        self.requetes_research_lot = 0
        self.candidats_research_lot = 0
        self.ecartes_hashtags_research_lot = 0
        self.quota_research_local = None
        self.attente_validation_research = False
        self.continuer_research = threading.Event()
        self.apercu_ecartes_research = []
        self.exclus_hashtags = 0
        self.cause_arret = None
        self.evenements_debug = []
        self.publication_en_cours = None
        self.limites_debug = {}
        self.commands = queue.Queue(maxsize=8)
        self.created = self.last_seen = time.monotonic()
        self.finished = None
        self.busy = True
        self.status = "starting"
        self.message = "Ouverture du navigateur…"
        self.discovered = 0
        self.decouvertes_ids = set()
        self.retenues_sources = {}
        self.exportees = 0
        self.processed = 0
        self.errors = 0
        self.filtered = 0
        self.exclus_sans_texte_ia = 0
        hashtags_a_compter = (settings.hashtags if settings.source_collecte != "presse"
            else settings.hashtags_presse if settings.croiser_hashtag_presse else [])
        self.bilan_hashtags = {h: 0 for h in hashtags_a_compter}
        self.correspondances_hashtags = 0
        self.legendes_vides = 0
        self.non_french = 0
        self.language_unknown = 0
        self.hors_periode = 0
        self.dates_indeterminees = 0
        self.search_errors = 0
        self.records = []
        self.dernier_point_sauvegarde = None
        self.erreur_sauvegarde = None
        self.sauvegarde_postgres = "en_attente"
        self.erreur_postgres = ""
        self.sauvegarde_postgres_publications = 0
        self.sauvegarde_postgres_commentaires = 0
        self._pg_publications = 0
        self._pg_commentaires = 0
        self._pg_traitees = -1
        self._pg_initialise = False
        self.frame = b""
        self.action_error = ""
        self.type_intervention = ""
        self.thread = None
        self.publications = []
        self.commentaires = []
        self.republications = []
        self.profils_medias = []
        self.bilan_republications = {}
        self.journal = []
        self.source_en_cours_id = None
        self.archive_prete = False
        self.video_busy = False
        self.video_stop = threading.Event()
        self.video_process = None
        self.video_thread = None
        self.video_debut = None
        self.base = None
        self.plan_research_id = None
        if settings.enrichie and (not self.historique or self.reprise):
            from stockage.base_donnees import BaseDonnees
            self.base = BaseDonnees(data_dir / "scraptiktok.sqlite")
            self.base.creer_session(self.id, owner, scraper.utc_now(), settings.model_dump())

    def demander_arret(self, cause):
        """Conserver la première cause, même si plusieurs contrôles demandent l’arrêt."""
        with self.lock:
            if not self.stop.is_set():
                self.cause_arret = {'code':cause,'explication':CAUSES_ARRET[cause],
                    'date':scraper.utc_now(),'traitees':self.processed,
                    'publication':self.publication_en_cours}
            self.stop.set()

    def diagnostic_collecte(self):
        """Exporter des champs techniques choisis, sans cookies ni réponses du navigateur."""
        with self.lock:
            return {'date':scraper.utc_now(),'statut':self.status,
                'cause_arret':self.cause_arret,
                'arret_demande':self.stop.is_set(),
                'publication_en_cours_ou_derniere':self.publication_en_cours,
                'duree_ecoulee_s':round((self.finished or time.monotonic())-self.created),
                'limites':dict(self.limites_debug),
                'compteurs':{'decouvertes':len(self.decouvertes_ids),'retenues_lecture':self.discovered,
                    'traitees':self.processed + self.reprise_decalage,'restantes':max(0,self.discovered-self.processed),
                    'publications_enregistrees':len(self.publications),'exportees_txt':self.exportees,
                    'hors_hashtags':self.filtered,'exclus_hashtags':self.exclus_hashtags,
                    'autre_langue':self.non_french,
                    'langue_indeterminee':self.language_unknown,
                    'hors_periode':self.hors_periode,'date_inconnue':self.dates_indeterminees,
                    'sans_legende':self.legendes_vides,'erreurs_lecture':self.errors},
                'evenements_recents':list(self.evenements_debug)}

    def update(self, **values):
        with self.lock:
            if any(cle in values and values[cle]!=getattr(self,cle,None) for cle in ('status','processed','publication_en_cours')):
                self.evenements_debug.append({'date':scraper.utc_now(),
                    'statut':values.get('status',self.status),
                    'traitees':values.get('processed',self.processed),
                    'publication':values.get('publication_en_cours',self.publication_en_cours)})
                self.evenements_debug=self.evenements_debug[-100:]
            for key, value in values.items():
                setattr(self, key, value)

    def snapshot(self):
        with self.lock:
            return {"debug_collecte": self.diagnostic_collecte(), "id": self.id, "hashtag": self.settings.hashtag,
                    "second_hashtag": self.settings.second_hashtag,
                    "hashtags_saisis": list(self.settings.hashtags_saisis),
                    "hashtags_exclus": list(self.settings.hashtags_exclus),
                    "exclus_hashtags": self.exclus_hashtags,
                    "operator": self.settings.operator,
                    "croiser_hashtag_presse": self.settings.croiser_hashtag_presse,
                    "hashtag_presse": self.settings.hashtag_presse,
                    "hashtags_presse": list(self.settings.hashtags_presse),
                    "operator_presse": self.settings.operator_presse,
                    "collecter_republications_research": self.settings.collecter_republications_research,
                    "profils_medias_variables": self.settings.profils_medias_variables,
                    "profils_medias_classes": self.settings.profils_medias_classes,
                    "nombre_profils_medias": len(self.profils_medias),
                    "bilan_profils_medias": [
                        {"compte": p["compte"], "statut": p["statut_profil"]}
                        for p in self.profils_medias],
                    "maximum_republications_par_compte": self.settings.maximum_republications_par_compte,
                    "nombre_republications": len(self.republications),
                    "bilan_republications": dict(self.bilan_republications),
                    "rechercher_dans_texte": self.settings.rechercher_dans_texte,
                    "variantes_accents": self.settings.variantes_accents,
                    "region_fr_research": self.settings.region_fr_research,
                    "hashtags": self.settings.hashtags, "filename": self.settings.filename,
                    "nom_sauvegarde": self.settings.nom_sauvegarde,
                    "sauvegarde_postgres": self.sauvegarde_postgres,
                    "erreur_postgres": self.erreur_postgres,
                    "sauvegarde_postgres_publications": self.sauvegarde_postgres_publications,
                    "sauvegarde_postgres_commentaires": self.sauvegarde_postgres_commentaires,
                    "filtered": self.filtered, "search_errors": self.search_errors,
                    "bilan_hashtags": dict(self.bilan_hashtags),
                    "correspondances_hashtags": self.correspondances_hashtags,
                    "legendes_vides": self.legendes_vides,
                    "bilan_medias": (etablir_bilan_medias(
                        self.settings.sources, self.journal,
                        source_en_cours=self.source_en_cours_id,
                        termine=not self.busy)
                        if self.settings.source_collecte == "presse" else []),
                    "bilan_sources": [{"source": entree["source"],
                        "liens": len(entree.get("rapport", {}).get("discovered_urls", [])),
                        "version_collecteur": entree.get("rapport", {}).get("version_collecteur"),
                        "presse_moteur": entree.get("rapport", {}).get("presse_moteur"),
                        "message": entree.get("message", "Recherche terminée."),
                        "candidats_examines": entree.get("rapport", {}).get(
                            "candidats_examines", 0),
                        "pages_research": entree.get("rapport", {}).get(
                            "pages_research", 0),
                        "requetes_tentees": entree.get("rapport", {}).get(
                            "requetes_tentees", 0),
                        "ecartes_hashtags_api": entree.get("rapport", {}).get(
                            "ecartes_hashtags_api", 0),
                        "ecartes_combinaison_hashtags": entree.get("rapport", {}).get(
                            "ecartes_combinaison_hashtags", 0),
                        "ecartes_metadonnees_absentes": entree.get("rapport", {}).get(
                            "ecartes_metadonnees_absentes", 0),
                        "retenues_par_compte": entree.get("rapport", {}).get("retenues_par_compte", {}),
                        "navigation_videos": entree.get("rapport", {}).get("navigation_videos", {}),
                        "navigation_videos_observee": entree.get("rapport", {}).get("navigation_videos_observee", {}),
                        "statut_http_profil": entree.get("rapport", {}).get("statut_http_profil"),
                        "etat_page": {cle: entree.get("rapport", {}).get("etat_page", {}).get(cle)
                            for cle in ("titre", "etat", "liens", "erreur_tiktok")
                            if cle in entree.get("rapport", {}).get("etat_page", {})},
                        "reseau_profil": {cle: entree.get("rapport", {}).get("reseau_profil", {}).get(cle)
                            for cle in ("statut_http", "reponses", "refus_http", "reponses_vides", "liste_refusee")
                            if cle in entree.get("rapport", {}).get("reseau_profil", {})},
                        "recherches": [{"requete": r.get("requete_recherche"),
                            "compte": r.get("compte_attendu"),
                            "candidats_examines": r.get("candidats_examines", 0),
                            "auteurs_dans_liens": r.get("auteurs_dans_liens", {}),
                            "defilements": r.get("defilements_effectues", 0),
                            "arret": r.get("discovery_stop", ""),
                            "pagination_bilan": r.get("pagination_bilan", {}),
                            "pages_api": r.get("pages_api", 0),
                            "pages_research": r.get("pages_research", 0),
                            "plage_research": r.get("plage_research"),
                            "fournisseur_donnees": r.get("fournisseur_donnees"),
                            "requetes_tentees": r.get("requetes_tentees", 0),
                            "secuid_resolu": bool(r.get("secuid_resolu", False)),
                            "source_secuid": r.get("source_secuid"),
                            "tentatives_embed_video": r.get("tentatives_embed_video", 0),
                            "videos_amorcage_disponibles": r.get("videos_amorcage_disponibles", 0),
                            "urls_embed_non_verifiees": r.get("urls_embed_non_verifiees", 0),
                            "message_erreur": r.get("message_erreur"),
                            "navigation_publications": r.get("navigation_publications"),
                            "navigation_videos": r.get("navigation_videos", {}),
                            "navigation_videos_observee": r.get("navigation_videos_observee", {}),
                            "url_rubrique_publications": r.get("url_rubrique_publications"),
                            "observation_reseau": {
                                "actif": bool(r.get("observation_reseau", {}).get("actif")),
                                "pages": len(r.get("observation_reseau", {}).get("pages", [])),
                                "indisponibilite": r.get("observation_reseau", {}).get("indisponibilite"),
                            },
                            "liens": len(r.get("discovered_urls", [])),
                            "auteurs_ecartes": r.get("auteurs_ecartes", 0),
                            "diagnostic": r.get("diagnostic", {})}
                            for r in (entree.get("rapport", {}).get("recherches_compte")
                                      or entree.get("rapport", {}).get("recherches_hashtags", []))],
                        "diagnostic": entree.get("rapport", {}).get("diagnostic", {})}
                        for entree in self.journal if "source" in entree],
                    "french_only": self.settings.french_only, "include_sources": self.settings.include_sources,
                    "inclure_metadonnees_txt": self.settings.inclure_metadonnees_txt,
                    "variables_txt": self.settings.variables_txt,
                    "inclure_texte_genere_ia": self.settings.inclure_texte_genere_ia,
                    "inclure_hashtags_csv": self.settings.inclure_hashtags_csv,
                    "filtrer_texte_ia_tiktok": self.settings.filtrer_texte_ia_tiktok,
                    "exclus_sans_texte_ia": self.exclus_sans_texte_ia,
                    "supprimer_arobase_profil": self.settings.supprimer_arobase_profil,
                    "bilan_textes_ia": {
                        "publications": len(self.records),
                        "recuperes": sum(bool(r.get("resume_ia_tiktok")) for r in self.records),
                        "details": [{"URL TikTok": r["url"],
                                     "État": ("Récupéré" if r.get("resume_ia_tiktok") else
                                              "Erreur de lecture" if r.get("statut_resume_ia") == "erreur_lecture" else
                                              "Résumé non trouvé dans la page")}
                                    for r in self.records]
                    } if self.settings.inclure_texte_genere_ia else None,
                    "non_french": self.non_french, "language_unknown": self.language_unknown,
                    "date_debut": self.settings.date_debut, "date_fin": self.settings.date_fin,
                    "hors_periode": self.hors_periode, "dates_indeterminees": self.dates_indeterminees,
                    "source_collecte": self.settings.source_collecte,
                    "presse_moteur": self.settings.presse_moteur,
                    "hashtag_moteur": self.settings.hashtag_moteur,
                    "profil_moteur": self.settings.profil_moteur,
                    "moteur_actif": self.settings.moteur_actif,
                    "comptes": self.settings.comptes,
                    "comptes_filtres": ([source["compte"] for source in self.settings.sources]
                                        if self.settings.source_collecte != "hashtags" else []),
                    "medias": self.settings.medias, "libelle": self.settings.libelle,
                    "reprise": self.reprise, "medias_reprise": list(self.medias_reprise),
                    "hashtags_reprise": list(self.hashtags_reprise),
                    "bilan_hashtags_sources": (
                        etablir_bilan_hashtags(
                            self.settings.hashtags, self.settings.variantes_accents,
                            self.journal, source_en_cours=self.source_en_cours_id,
                            termine=not self.busy, collecte_id=self.id)
                        if self.settings.source_collecte == "hashtags" else []),
                    "publications_avant_reprise": self.publications_avant_reprise,
                    "publications_ajoutees": max(0, len(self.publications) - self.publications_avant_reprise) if self.reprise else 0,
                    "diagnostics": list(self.diagnostics),
                    "telecharger_mp4": self.settings.telecharger_mp4,
                    "sauvegarde_progressive": self.settings.sauvegarde_progressive,
                    "dernier_point_sauvegarde": self.dernier_point_sauvegarde,
                    "erreur_sauvegarde": self.erreur_sauvegarde,
                    "bilan_mp4": [{"video_id": r.get("video_id"), "video_statut": r.get("video_statut", "en_attente"),
                        "video_message": r.get("video_message", "En attente du téléchargement."),
                        "video_fichier": r.get("video_fichier")} for r in self.records if r.get("video_id")],
                    "enrichir": self.settings.enrichie, "commentaires_collectes": len(self.commentaires),
                    "collecter_commentaires":self.settings.collecter_commentaires,
                    "inclure_commentaires_txt":self.settings.inclure_commentaires_txt,
                    "collecter_reponses":self.settings.collecter_reponses,
                    "collecter_follower_count":self.settings.collecter_follower_count,
                    "follower_count_illustratif":self.settings.follower_count_illustratif,
                    "abonnes_classe_illustratif":self.settings.abonnes_classe_illustratif,
                    "collecter_is_verified": self.settings.collecter_is_verified,
                    "variables_classes_txt": self.settings.variables_classes_txt,
                    "taux_engagement_txt": self.settings.taux_engagement_txt,
                    "commentaires_indisponibles": sum(r.get("collecte_commentaires", {}).get("statut") in {
                        "inaccessible", "page_differente", "indisponible_ou_vide", "panneau_introuvable",
                        "extraction_impossible", "chargement_incomplet", "erreur_chargement", "verification_tiktok",
                        "connexion_requise", "desactives"} for r in self.records),
                    "bilan_commentaires": [{"publication_id": r["id"], **r["collecte_commentaires"]}
                        for r in self.records if "collecte_commentaires" in r],
                    "limite_commentaires":self.settings.limite_commentaires,
                    "collecte_research_complete":self.settings.collecte_research_complete,
                    "test_research_10_publications":self.settings.test_research_10_publications,
                    "requetes_research_lot": self.requetes_research_lot,
                    "candidats_research_lot": self.candidats_research_lot,
                    "ecartes_hashtags_research_lot": self.ecartes_hashtags_research_lot,
                    "quota_research_local": self.quota_research_local,
                    "lot_candidats_research": self.settings.lot_candidats_research,
                    "attente_validation_research": self.attente_validation_research,
                    "apercu_ecartes_research": list(self.apercu_ecartes_research[-20:]),
                    "apercu_texte_research": [{
                        "url": p.get("url", ""), "auteur": p.get("author", ""),
                        "legende": str(p.get("description") or "")[:450],
                        "hashtags": list(p.get("hashtags") or [])[:25],
                        "hashtags_correspondants": list(
                            p.get("hashtags_correspondants") or []),
                        "langue": p.get("langue_detection") or "non_evaluee",
                        "region": p.get("region_code") or "indeterminee"}
                        for p in self.records[-20:]]
                        if self.settings.source_collecte == "hashtags"
                        and self.settings.moteur_actif == "research" else [],
                    "archive_prete": self.archive_prete, "video_busy": self.video_busy,
                    "limit": self.settings.limit, "status": self.status, "busy": self.busy,
                    "message": self.message, "discovered": self.discovered,
                    "processed": self.processed + self.reprise_decalage, "captions": len(self.records),
                    "compteurs_collecte": {"decouvertes": len(self.decouvertes_ids), "retenues": self.discovered,
                        "traitees": self.processed + self.reprise_decalage, "exportees": self.exportees},
                    "errors": self.errors, "has_frame": bool(self.frame), "type_intervention": self.type_intervention,
                    "action_error": self.action_error, "can_download": bool(
                        self.records or self.republications or self.profils_medias),
                    "apercu_filtrage": [{
                        "auteur": r.get("author", ""),
                        "url": r.get("url", ""),
                        "legende": str(r.get("description") or "")[:200],
                        "langue": r.get("langue_detection") or "non_evaluee",
                        "motif": r.get("motif_non_retenue") or
                                 ("retenue" if r.get("retenue") else "non_determine")
                    } for r in self.publications[:30]]
                    if self.settings.test_research_10_publications else [],
                    "apercu_engagement": [{"id": r["id"], "author": r["author"], "url": r["url"],
                        "engagement": r.get("engagement", {}), "langue_detection": r.get("langue_detection"),
                        "motif_non_retenue": r.get("motif_non_retenue"),
                        "retenue_txt": bool(r.get("retenue", r in self.records))}
                        for r in (self.publications or self.records)],
                    "preview": [{"author": r["author"], "description": r["description"],
                        "texte_export": self.texte_a_exporter(publications=[r]),
                        "texte_export_sans_arobase": self.texte_a_exporter(True, publications=[r]),
                        "texte_export_avec_arobase": self.texte_a_exporter(False, publications=[r])}
                                for r in self.records[:5]]}

    def check(self):
        if self.stop.is_set():
            raise Stopped()

    def pause(self, seconds):
        if self.stop.wait(seconds):
            raise Stopped()

    def actualiser_decouverte(self, rapport):
        """Compter les IDs distincts, y compris les résultats d'autres auteurs."""
        retenues = {identite[0] for url in rapport.get("discovered_urls", [])
                    if (identite := scraper.canonical_post(url))}
        source = rapport.get("compte_attendu") or rapport.get("hashtag_url", "")
        with self.lock:
            self.decouvertes_ids.update(rapport.get("candidats_ids", retenues))
            self.retenues_sources[source] = retenues
            self.discovered = len(set().union(*self.retenues_sources.values()))

    def texte_a_exporter(self, supprimer_arobase_profil=None, *, publications=None):
        """Appliquer le choix de téléchargement sans modifier les données collectées."""
        with self.lock:
            if supprimer_arobase_profil is None:
                supprimer_arobase_profil = self.settings.supprimer_arobase_profil
            return text_export(self.records if publications is None else publications, self.settings.include_sources,
                self.settings.inclure_metadonnees_txt, self.settings.variables_txt,
                self.commentaires if (self.settings.collecter_commentaires
                                     and self.settings.inclure_commentaires_txt) else None,
                supprimer_arobase_profil=supprimer_arobase_profil,
                inclure_texte_genere_ia=self.settings.inclure_texte_genere_ia,
                follower_count_illustratif=self.settings.follower_count_illustratif,
                abonnes_classe_illustratif=self.settings.abonnes_classe_illustratif,
                variables_classes_txt=self.settings.variables_classes_txt,
                taux_engagement_txt=self.settings.taux_engagement_txt,
                themes=(self.settings.hashtags_presse if self.settings.croiser_hashtag_presse
                        else self.settings.hashtags))

    def sauvegarder_postgres(self, *, progressif=False):
        """Archiver automatiquement les nouvelles données sans réécrire le corpus."""
        if self.historique and not self.reprise:
            return False
        if self.plan_research_id:
            # Les lots programmés utilisent leur propre stockage SQLite/PostgreSQL.
            return True
        if not self.owner_historique:
            self.sauvegarde_postgres = "identite_absente"
            self.erreur_postgres = "Cookie d'historique absent : sauvegarde impossible."
            return False
        with self.lock:
            total_publications = len(self.publications or self.records)
            total_commentaires = len(self.commentaires)
            traitees = self.processed
            if (progressif and self._pg_initialise
                    and self.sauvegarde_postgres == "synchronise"
                    and total_publications == self._pg_publications
                    and total_commentaires == self._pg_commentaires
                    and traitees == self._pg_traitees):
                return True
            indice_publications = self._pg_publications if progressif else 0
            indice_commentaires = self._pg_commentaires if progressif else 0
        try:
            from stockage.postgres_consultation import archiver_collecte
            if progressif:
                archiver_collecte(
                    self, a_partir_publications=indice_publications,
                    a_partir_commentaires=indice_commentaires)
            else:
                archiver_collecte(self)
        except Exception as erreur:
            # Ne pas inscrire le DSN ni les identifiants dans les journaux.
            LOG.warning("Archivage PostgreSQL impossible pour %s : %s (SQLSTATE %s)",
                        self.id, type(erreur).__name__,
                        getattr(erreur, "sqlstate", None) or "indisponible")
            self.sauvegarde_postgres = "erreur"
            self.erreur_postgres = (
                "Sauvegarde PostgreSQL impossible : vérifiez les journaux "
                "ScrapTikTok et les droits PostgreSQL dans Coolify. "
                "Les fichiers SQLite et ZIP restent accessibles.")
            return False
        with self.lock:
            self._pg_publications = total_publications
            self._pg_commentaires = total_commentaires
            self._pg_traitees = traitees
            self._pg_initialise = True
            self.sauvegarde_postgres_publications = total_publications
            self.sauvegarde_postgres_commentaires = total_commentaires
            self.sauvegarde_postgres = "synchronise"
            self.erreur_postgres = ""
        return True

    def sauvegarder_historique(self):
        """Synchroniser les résultats et codages dans l'historique privé de 30 jours."""
        if self.historique and not self.reprise:
            # Les analyses rouvertes pointent déjà sur leur dossier d'archive.
            return True
        if not self.owner_historique:
            return False
        # Même si le ZIP n'a pas été finalisé, les fichiers JSON déjà écrits
        # doivent rester disponibles dans l'historique privé.
        fichiers_minimaux = (
            self.publications
            and (self.directory / "publications.json").is_file()
            and (self.directory / "journal.json").is_file()
        )
        if not self.archive_prete and not fichiers_minimaux:
            return False
        try:
            # L'historique contient directement un tableau prêt à être réimporté,
            # avec toutes les mesures et annotations regroupées par publication.
            from analyse_desordre.corpus_fusion import sauvegarder_tableau_complet
            sauvegarder_tableau_complet(self.directory)
            from stockage.historique_analyses import enregistrer
            enregistrer(self, self.owner_historique)
            return True
        except Exception:
            LOG.exception("Archivage historique impossible pour %s", self.id)
            return False

    def sauvegarder_point(self, statut="en_cours"):
        """Point de récupération indépendant du TTL des dossiers de session."""
        if not self.settings.sauvegarde_progressive:
            return None
        # Pas de ZIP de récupération contenant seulement un rapport d'échec.
        if self.settings.source_collecte == "presse" and not self.publications:
            return None
        from stockage.sauvegarde_progressive import enregistrer_point
        with self.lock:
            etat={"traitees":self.processed, "statut":statut,
                  "source":self.settings.libelle}
            try:
                point=enregistrer_point(
                    self.racine, self.id, self.owner, etat,
                    self.texte_a_exporter(), self.publications, self.records,
                    self.commentaires, self.settings.model_dump())
            except (OSError, ValueError, TypeError) as erreur:
                LOG.exception("Échec de la sauvegarde progressive %s", self.id)
                self.erreur_sauvegarde="Impossible d’écrire la sauvegarde sur le VPS : "+str(erreur)[:250]
                return None
            self.erreur_sauvegarde=None
            self.dernier_point_sauvegarde=point
            return point

    def save(self):
        # Les profils et captures ne sont jamais écrits dans les exports.
        with self.lock:
            content = self.texte_a_exporter()
            nombre_exporte = sum(bool(r.get("description")) for r in self.records)
        if (self.settings.source_collecte == "presse" and not self.publications
                and not self.profils_medias and not self.republications):
            # Ne pas produire un TXT vide après un refus avant toute donnée.
            # Un export profils/republications seul conserve néanmoins une source
            # TXT vide pour l'assemblage cohérent de l'archive ZIP.
            self.path.unlink(missing_ok=True)
        else:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(content, encoding="utf-8")
            temp.replace(self.path)
        self.update(exportees=nombre_exporte)


def release_pointer(driver):
    point = getattr(driver, "_scraptiktok_pointer", None)
    if isinstance(point, dict):
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased", **point, "button": "left", "buttons": 0, "clickCount": 1})
        driver._scraptiktok_pointer = None
    ActionChains(driver).reset_actions()


def perform_action(driver, action: BrowserAction):
    """Rejoue les gestes humains reçus ; aucun solveur de CAPTCHA ni JS utilisateur."""
    width, height = driver.execute_script("return [window.innerWidth, window.innerHeight];")
    chain = ActionChains(driver, duration=60)

    def move(point):
        chain.w3c_actions.pointer_action.move_to_location(
            min(width - 1, round(point.x * width)), min(height - 1, round(point.y * height)))

    if action.kind.startswith("pointer_"):
        if action.kind == "pointer_cancel":
            release_pointer(driver)
            return
        point = action.points[0]
        coords = {"x": min(width - 1, round(point.x * width)),
                  "y": min(height - 1, round(point.y * height))}
        # Chromium : conserver le bouton et la capture DOM entre deux requêtes.
        # Des séquences W3C séparées peuvent perdre la capture du curseur natif.
        event_type = {"pointer_down": "mousePressed", "pointer_move": "mouseMoved",
                      "pointer_up": "mouseReleased"}[action.kind]
        driver._scraptiktok_pointer = coords
        driver.execute_cdp_cmd("Input.dispatchMouseEvent", {
            "type": event_type, **coords, "button": "left",
            "buttons": 0 if action.kind == "pointer_up" else 1, "clickCount": 1})
        if action.kind == "pointer_up":
            driver._scraptiktok_pointer = None
    elif action.kind in {"click", "drag"}:
        if not action.points:
            raise ValueError("Le geste ne contient aucune position.")
        move(action.points[0])
        if action.kind == "click":
            chain.click()
        else:
            chain.click_and_hold()
            for point in action.points[1:]:
                move(point)
            chain.release()
        chain.perform()
    elif action.kind == "text":
        chain.send_keys(action.text).perform()
    elif action.kind == "key":
        if action.key == "select_all":
            modifier = Keys.COMMAND if driver.capabilities.get("platformName") == "mac" else Keys.CONTROL
            chain.key_down(modifier).send_keys("a").key_up(modifier).perform()
        else:
            mapping = {"Enter": Keys.ENTER, "Tab": Keys.TAB,
                       "Backspace": Keys.BACKSPACE, "Escape": Keys.ESCAPE}
            chain.send_keys(mapping[action.key]).perform()
    else:
        driver.execute_script("window.scrollBy(0, arguments[0]);", action.delta)


def wait_for_user(driver, job: Job, message: str):
    def nature_intervention():
        return scraper.type_intervention_tiktok(driver)

    with job.lock:
        previous, message_precedent = job.status, job.message
        job.update(status="attention", message=message, action_error="")
    next_frame = 0
    held_since = None
    prochaine_detection = 0
    try:
        while True:
            job.check()
            if held_since is not None and time.monotonic() - held_since > 15:
                release_pointer(driver)
                held_since = None
            # Ne pas parcourir les cadres pendant un glisser-déposer du puzzle.
            if held_since is None and time.monotonic() >= prochaine_detection:
                nature = nature_intervention()
                job.update(type_intervention=nature)
                prochaine_detection = time.monotonic() + 1
            if time.monotonic() >= next_frame:
                job.update(frame=driver.get_screenshot_as_png())
                next_frame = time.monotonic() + 0.25
            try:
                command = job.commands.get(timeout=0.15)
            except queue.Empty:
                continue
            if command == "continue":
                scraper.fermer_invitation_connexion(driver)
                if nature_intervention() == "captcha":
                    job.update(type_intervention="captcha", action_error="TikTok affiche encore un CAPTCHA. Terminez-le dans la fenêtre avant de continuer.")
                    continue
                break
            live = command if isinstance(command, LiveAction) else None
            if live:
                command = live.action
            try:
                if command.kind == "text" and nature_intervention() == "connexion":
                    command.text = ""
                    raise ValueError("La collecte est anonyme ; aucune saisie d’identifiants n’est proposée.")
                perform_action(driver, command)
                if command.kind in {"pointer_down", "pointer_move"}:
                    held_since = time.monotonic()
                elif command.kind in {"pointer_up", "pointer_cancel"}:
                    held_since = None
                job.update(action_error="")
                next_frame = 0
            except Exception:
                message = "Ce geste n’a pas abouti. Attendez l’actualisation de l’image et réessayez."
                job.update(action_error=message)
                if live:
                    live.error = message
            finally:
                if live:
                    live.done.set()
    finally:
        try:
            release_pointer(driver)
        except Exception:
            pass
        job.update(status=previous, message=message_precedent, frame=b"", type_intervention="")
        while not job.commands.empty():
            try:
                pending = job.commands.get_nowait()
                if isinstance(pending, LiveAction):
                    pending.error = "L’interaction avec le navigateur est terminée."
                    pending.done.set()
            except queue.Empty:
                break


def expliquer_echec_source(rapport, erreur):
    """Donner la cause observée sans attribuer une panne du navigateur au média."""
    from collecte.presse_api import PresseApiError, PresseRateLimitError, PresseCooldownError
    from collecte.presse_research import ResearchErreur
    from collecte.quotas_exploitation import QuotaScrapingAtteint
    if isinstance(erreur, ResearchErreur):
        return "Research API officielle : " + str(erreur)
    if isinstance(erreur, PresseRateLimitError):
        conservees = len(rapport.get("discovered_urls", []))
        return ("Accès API Presse refusé par TikTok (HTTP 429) : collecte arrêtée. "
                + (f"{conservees} URL déjà reçue(s) conservée(s), sans vérification de vidéo ou de métriques. "
                   if conservees else "Aucune URL de vidéo utilisable n'a pu être conservée. ")
                + "Aucun nouvel appel n'est lancé par cette collecte.")
    if isinstance(erreur, PresseCooldownError):
        return "Pause TikTok Retry-After encore active : aucune requête API Presse envoyée."
    if isinstance(erreur, QuotaScrapingAtteint):
        return "Quota de sécurité ScrapTikTok atteint : arrêt avant la requête TikTok suivante."
    if isinstance(erreur, PresseApiError):
        return "API web TikTok (secUid) : " + str(erreur)
    diagnostic = rapport.get("diagnostic", {})
    if not diagnostic.get("code"):
        # Les moteurs Selenium/API placent leurs observations dans l'étape
        # du compte ; préserver cette cause dans le message principal.
        diagnostic = next((etape["diagnostic"] for etape in
            reversed(rapport.get("recherches_compte", []))
            if (etape.get("diagnostic") or {}).get("code")), diagnostic)
    code = diagnostic.get("code")
    if isinstance(code, str) and code.startswith("tikhub_"):
        descriptions = {
            "tikhub_sans_videos": "TikHub n'a fourni aucune vidéo pour ce média.",
            "tikhub_secuid_absent": "TikHub n'a pas fourni l'identifiant secUid du compte.",
            "tikhub_compte_incorrect": "TikHub a renvoyé les données d'un autre compte.",
            "tikhub_itemlist_absente": "La réponse TikHub ne contient pas de liste de publications exploitable.",
            "tikhub_limite": "TikHub limite actuellement les requêtes (HTTP 429).",
            "tikhub_acces_refuse": "TikHub a refusé l'accès : vérifier la clé ou le crédit disponible.",
        }
        return descriptions.get(code, "TikHub : la collecte a échoué ; consultez le diagnostic.")
    if isinstance(code, str) and code.startswith("apify_"):
        descriptions = {
            "apify_cle_absente": "Apify : jeton API absent.",
            "apify_acces_refuse": "Apify refuse l'accès : vérifier le jeton et les droits de l'Actor.",
            "apify_credit": "Apify refuse la collecte : crédits ou moyens de paiement insuffisants.",
            "apify_limite": "Apify limite les appels (HTTP 429).",
            "apify_delai": "Apify : exécution distante interrompue après dépassement du délai.",
            "apify_execution_echec": "L'Actor Apify n'a pas terminé avec succès.",
            "apify_dataset_absent": "L'Actor Apify n'a pas fourni de dataset.",
            "apify_sans_videos": "Apify n'a fourni aucune vidéo vérifiée pour ce compte.",
            "apify_reseau": "Apify est inaccessible depuis le VPS.",
            "apify_configuration": "Apify : plafond de coût invalide dans Coolify.",
        }
        return descriptions.get(code, "Apify : la collecte a échoué ; consulter le diagnostic.")
    if code == "gallerydl_sans_videos":
        categorie = diagnostic.get("categorie")
        detail = (" (HTTP 429)" if categorie == "http_429" else
                  " (HTTP 403)" if categorie == "http_403" else "")
        return ("Méthode gallery-dl : TikTok n'a pas fourni de publications"
                + detail + ". Cela ne signifie pas que le compte est vide.")
    if code == "gallerydl_delai_depasse":
        return ("Méthode gallery-dl : délai dépassé pendant l'étape "
                + str(diagnostic.get("etape", "non_identifiee"))
                + ". La collecte est arrêtée, sans prétendre que le compte est vide.")
    if code == "gallerydl_extraction_echec":
        return ("Méthode gallery-dl : échec pendant l'étape "
                + str(diagnostic.get("etape", "non_identifiee"))
                + " (type " + str(diagnostic.get("erreur_type", "inconnue"))
                + "). Aucun résultat inventé.")
    if code == "gallerydl_json_invalide":
        return "Méthode gallery-dl : réponse non exploitable, aucune publication inventée."
    if code == "gallerydl_indisponible":
        return "Méthode gallery-dl : dépendance absente du conteneur."
    if code == "profil_sans_liens_playwright":
        return ("Le profil n’a fourni aucun lien vidéo après "
                + str(diagnostic.get("delai_secondes", "?"))
                + " seconde(s) d’attente du contenu. Cela ne signifie pas que le compte n’a pas de vidéos.")
    if code == "refus_http_playwright":
        return f"TikTok refuse le chargement du profil Playwright (HTTP {diagnostic.get('statut_http')})."
    if code == "redirection_hors_profil":
        return "TikTok a redirigé Playwright hors du profil demandé ; les liens de cette autre page sont ignorés."
    if code == "erreur_tiktok_playwright":
        return "TikTok affiche une erreur à la place des vidéos dans la session Playwright."
    if code == "erreur_session":
        return "La session Selenium a été fermée ou perdue. Relancez une collecte pour ouvrir un nouveau navigateur anonyme."
    if code == "recherche_redirigee":
        return "TikTok a redirigé la recherche compte + hashtag vers une autre page. Les publications de cette autre page ne sont pas collectées."
    if code == "resultats_incomplets":
        return "La recherche TikTok reste incomplète après plusieurs chargements."
    if code == "connexion_sans_publications_publiques":
        return "TikTok n’a fourni aucun lien public lisible et affiche une fenêtre de connexion. La collecte n’impose pas de connexion ; cette source est inaccessible sans compte dans cette session."
    if rapport.get("discovery_stop") == "blocked" or code == "verification_tiktok":
        return "Vérification TikTok non terminée."
    if code == "erreur_tiktok":
        return "TikTok affiche « Something went wrong / Une erreur est survenue » à la place des publications. Le rechargement automatique n’a pas résolu cette erreur ; aucune publication n’a pu être consultée."
    if code == "delai_navigation" or isinstance(erreur, scraper.TimeoutException):
        return "Le chargement de la page a dépassé le délai du navigateur."
    if code == "erreur_reseau":
        return "Erreur réseau du navigateur : " + diagnostic.get("erreur_reseau", "indéterminée") + "."
    if code == "erreur_navigateur" or isinstance(erreur, scraper.WebDriverException):
        return "Le navigateur n’a pas pu ouvrir ou lire cette page. Voir le diagnostic de la source."
    return "Aucun lien de publication lisible dans la page reçue de TikTok après vérification."


def attendre_intervalle_lecture(debut_precedent, intervalle, pause):
    """Espacer les débuts de lecture sans ajouter une pause à une page déjà lente."""
    if debut_precedent is not None:
        restant = intervalle - (time.monotonic() - debut_precedent)
        if restant > 0:
            pause(restant)
    return time.monotonic()


def execute_job(job: Job, driver_factory=scraper.create_driver):
    from collecte.quotas_exploitation import max_defilements
    args = argparse.Namespace(
        hashtag=job.settings.hashtag,
        limit=job.settings.limit,
        inclure_texte_genere_ia=job.settings.inclure_texte_genere_ia,
        max_scrolls=max_defilements(),
        idle_rounds=3, delay=3.0, timeout=20.0, interactive=True,
        headless=os.getenv("SCRAPTIKTOK_HEADLESS", "1") == "1",
        chrome_binary=Path(os.environ["CHROME_BINARY"]) if os.getenv("CHROME_BINARY") else None,
        driver=Path(os.environ["CHROMEDRIVER"]) if os.getenv("CHROMEDRIVER") else None,
    )
    driver = None
    connexion = None
    moteur_actif = job.settings.moteur_actif
    unique_links = {}
    if job.reprise:
        # Les vidéos existantes sont connues : aucune nouvelle lecture TikTok.
        for publication in job.publications:
            url_ancienne = publication.get("url")
            if not url_ancienne:
                continue
            identite = scraper.canonical_post(url_ancienne)
            if identite:
                unique_links.setdefault(str(identite[0]), identite[1])
    metadonnees_api = {}
    dernier_debut_lecture = None
    final_status, final_message = "failed", "La collecte n’a pas pu aboutir."
    limitation_tiktok = False
    limitation_research = False
    echecs_serveur_research_consecutifs = 0
    limitation_commentaires_research = False
    limitation_abonnes_research = False
    cache_abonnes_research = {}
    limitation_budget = False
    try:
        job.check()
        # Chaque mode possède son point d’entrée ; aucun repli implicite vers un autre mode.
        if job.settings.source_collecte == "hashtags":
            from connect_htag import ConnexionHashtag
            parcours = ConnexionHashtag
        elif job.settings.source_collecte == "presse":
            from connect_presse import ConnexionPresse
            parcours = ConnexionPresse
        elif job.settings.source_collecte == "comptes":
            from connect_profil import ConnexionProfil
            parcours = ConnexionProfil
        else:
            raise ValueError("Mode de collecte inconnu.")
        connexion = parcours(args, fabrique=driver_factory, verifier=job.check,
            interaction=lambda navigateur, message: wait_for_user(navigateur, job, message))
        if job.settings.source_collecte == "hashtags" and moteur_actif == "research":
            # Le connecteur utilise exactement la même correspondance que
            # le TXT, avant de réserver les identifiants de vidéos.
            connexion.valider_fiche_hashtags_research = (
                lambda fiche: verifier_criteres_hashtags_research(
                    fiche, job.settings))
        sources = connexion.preparer_sources(job.settings)
        if job.reprise:
            if job.settings.source_collecte == "presse":
                index_sources = {source.get("id"): source for source in sources}
                sources = [
                    index_sources[media_id] for media_id in job.medias_reprise
                    if media_id in index_sources
                ]
            elif job.settings.source_collecte == "hashtags":
                autorisees = set(job.sources_reprise_hashtags)
                sources = [
                    source for source in sources
                    if source.get("hashtag") in autorisees
                ]
            if not sources:
                raise ValueError("Aucune source inachevée à reprendre.")
        driver = connexion.ouvrir()
        if (job.settings.profils_medias_variables and moteur_actif == "research"
                and job.settings.source_collecte == "presse"):
            # Une ligne par média choisi, même s'il n'a aucune vidéo retenue.
            # La collecte est indépendante du nombre de publications et du
            # filtre de hashtags appliqué à leur description.
            from collecte.profils_medias import ligne_profil_media
            from collecte.researchapi import (
                collecter_metriques_profil_media_research,
                ResearchErreur, ResearchAccesRefuse)
            quota_profils_refuse = False
            profils_anterieurs = {
                p["compte"]: p for p in job.profils_medias if p.get("compte")
            } if job.reprise else {}
            for media in sources:
                job.check()
                compte = media["compte"]
                if profils_anterieurs.get(compte, {}).get("statut_profil") == "ok":
                    # La métrique du compte était déjà acquise : quota épargné.
                    continue
                donnees, statut = {}, "indisponible"
                job.update(status="collecting",
                           message="Lecture des métriques du profil @" + compte + "…")
                if quota_profils_refuse:
                    statut = "acces_refuse"
                else:
                    try:
                        donnees = collecter_metriques_profil_media_research(
                            compte, job.settings.profils_medias_variables,
                            verifier=job.check,
                            credentiels=connexion.research_credentiels)
                        statut = ("ok" if any(v is not None for v in donnees.values())
                                  else "indisponible")
                    except ResearchAccesRefuse:
                        quota_profils_refuse = True
                        statut = "acces_refuse"
                    except ResearchErreur:
                        statut = "indisponible"
                if job.reprise:
                    # Une seule ligne par compte après actualisation du profil.
                    job.profils_medias = [
                        p for p in job.profils_medias if p.get("compte") != compte
                    ]
                job.profils_medias.append(ligne_profil_media(
                    media, job.settings.profils_medias_variables,
                    job.settings.profils_medias_classes, donnees=donnees,
                    statut=statut, date_collecte=scraper.utc_now()))
        hors_selection = 0
        medias_par_compte = {s["compte"]: s for s in sources if "compte" in s}
        links = []
        # La limite demandée concerne les résultats conservés, non les candidats
        # explorés lorsque l’utilisateur filtre les dates de publication.
        filtre_dates_hashtags = (job.settings.source_collecte == "hashtags" and
                                 bool(job.settings.date_debut or job.settings.date_fin))
        plafond_decouverte = (
            10 if job.settings.test_research_10_publications else
            None if args.limit is None else
            min(args.limit * 5, 500) if filtre_dates_hashtags else args.limit
        )
        def lire_decouvertes():
            """Lire et exporter les nouvelles publications dès qu'un compte est découvert."""
            nonlocal links, hors_selection, dernier_debut_lecture, limitation_commentaires_research, limitation_abonnes_research
            links = list(unique_links.values())
            job.update(status="collecting", discovered=len(links))
            for index in range(job.processed + 1, len(links) + 1):
                if job.settings.test_research_10_publications and job.processed >= 10:
                    break
                if filtre_dates_hashtags and args.limit is not None and len(job.records) >= args.limit:
                    break
                url = links[index - 1]
                job.update(message=f"Lecture de la publication {index} sur {len(links)}…", publication_en_cours=scraper.canonical_post(url)[0])
                try:
                    identifiant_publication = scraper.canonical_post(url)[0]
                    record_api = metadonnees_api.get(identifiant_publication)
                    if record_api and job.settings.hashtags_exclus:
                        from collecte.exclusion_hashtags import hashtags_a_exclure
                        correspondances_api = hashtags_a_exclure(
                            record_api, job.settings.hashtags_exclus)
                        if correspondances_api:
                            # Ignorer immédiatement les vidéos déjà identifiées, sans
                            # ouvrir Selenium ni payer un enrichissement supplémentaire.
                            with job.lock:
                                job.exclus_hashtags += 1
                            job.journal.append({
                                "publication_id": identifiant_publication,
                                "filtre": "not_hashtag",
                                "hashtags": correspondances_api})
                            job.update(processed=index)
                            if job.settings.sauvegarde_progressive and index % 10 == 0:
                                job.sauvegarder_point()
                            continue
                    if (record_api and (
                            (job.settings.source_collecte == "hashtags" and moteur_actif == "research")
                            or (job.settings.source_collecte == "comptes"
                                and (moteur_actif in {"research", "gallerydl", "tikhub"}
                                     or (moteur_actif == "api"
                                         and not job.settings.collecter_commentaires
                                         and record_api.get("description"))))
                            or (job.settings.source_collecte == "presse"
                                and (moteur_actif in {"research", "gallerydl", "tikhub", "apify"}
                                     or (moteur_actif == "api"
                                         and not job.settings.collecter_commentaires
                                         and record_api.get("description")))))):
                        # TikTok a déjà fourni une légende et éventuellement les
                        # compteurs dans itemList : ne pas faire une nouvelle
                        # visite Selenium pour la même vidéo.
                        record = dict(record_api)
                        if (job.settings.inclure_texte_genere_ia
                                and not (job.settings.source_collecte == "presse"
                                         and moteur_actif == "tikhub"
                                         and job.settings.croiser_hashtag_presse
                                         and not matches_hashtags(
                                             record.get("description", ""), job.settings,
                                             hashtags_observes=record.get("hashtags")))):
                            # La case IA demande une lecture du résumé affiché ; les API
                            # de métadonnées ne le fournissent pas. Garder leurs données.
                            job.pause(args.delay)
                            try:
                                lecture_ia = connexion.lire_publication(url)
                                for cle in ("resume_ia_tiktok", "statut_resume_ia",
                                            "source_resume_ia", "titre_ia_tiktok",
                                            "article_ia_tiktok", "mots_cles_ia_tiktok"):
                                    if cle in lecture_ia:
                                        record[cle] = lecture_ia[cle]
                            except scraper.WebDriverException:
                                record["statut_resume_ia"] = "erreur_lecture"
                            except RuntimeError as erreur:
                                # Refus d'authentification ou limitation : stopper pour
                                # éviter une série de requêtes TikHub payantes.
                                if getattr(erreur, "code", None) in {
                                    "tikhub_limite", "tikhub_acces_refuse", "tikhub_code",
                                }:
                                    raise
                                record["statut_resume_ia"] = "erreur_lecture"
                    else:
                        if job.settings.source_collecte == "hashtags":
                            dernier_debut_lecture = attendre_intervalle_lecture(
                                dernier_debut_lecture, args.delay, job.pause)
                        else:
                            job.pause(args.delay)
                        record = connexion.lire_publication(url)
                    record["retenue"] = False
                    # La case Htag dans le csv concerne uniquement les exports :
                    # garder intactes les données brutes et le corpus TXT.
                    record["inclure_hashtags_csv"] = job.settings.inclure_hashtags_csv
                    if job.settings.hashtags_exclus:
                        from collecte.exclusion_hashtags import hashtags_a_exclure
                        correspondances = hashtags_a_exclure(
                            record, job.settings.hashtags_exclus)
                        if correspondances:
                            # Écarter avant les commentaires, les analyses et les exports.
                            with job.lock:
                                job.exclus_hashtags += 1
                            job.journal.append({
                                "publication_id": record.get("id"),
                                "filtre": "not_hashtag",
                                "hashtags": correspondances})
                            job.update(processed=index)
                            if job.settings.sauvegarde_progressive and index % 10 == 0:
                                job.sauvegarder_point()
                            continue
                    if moteur_actif == "research" and (
                            job.settings.collecter_follower_count
                            or job.settings.collecter_is_verified):
                        # Les deux propriétés sont regroupées en une requête par
                        # auteur distinct ; les valeurs manquantes restent inconnues.
                        from collecte.researchapi import (
                            ResearchErreur, ResearchAccesRefuse,
                            collecter_abonnes_research, collecter_verification_research,
                            collecter_profil_research)
                        compte_auteur = str(record.get("author") or "").casefold()
                        if compte_auteur not in cache_abonnes_research:
                            if limitation_abonnes_research:
                                cache_abonnes_research[compte_auteur] = {
                                    "follower_count": None, "is_verified": None,
                                    "statut": "acces_refuse"}
                            else:
                                try:
                                    if (job.settings.collecter_follower_count
                                            and job.settings.collecter_is_verified):
                                        profil = collecter_profil_research(
                                            compte_auteur, verifier=job.check,
                                            credentiels=connexion.research_credentiels)
                                    elif job.settings.collecter_follower_count:
                                        profil = {"follower_count": collecter_abonnes_research(
                                            compte_auteur, verifier=job.check,
                                            credentiels=connexion.research_credentiels),
                                            "is_verified": None}
                                    else:
                                        profil = {"follower_count": None,
                                                  "is_verified": collecter_verification_research(
                                            compte_auteur, verifier=job.check,
                                            credentiels=connexion.research_credentiels)}
                                    cache_abonnes_research[compte_auteur] = {
                                        **profil, "statut": "ok"}
                                except ResearchAccesRefuse:
                                    limitation_abonnes_research = True
                                    cache_abonnes_research[compte_auteur] = {
                                        "follower_count": None, "is_verified": None,
                                        "statut": "acces_refuse"}
                                except ResearchErreur:
                                    cache_abonnes_research[compte_auteur] = {
                                        "follower_count": None, "is_verified": None,
                                        "statut": "indisponible"}
                        profil = cache_abonnes_research[compte_auteur]
                        if job.settings.collecter_follower_count:
                            nombre = profil.get("follower_count")
                            record["follower_count"] = nombre
                            record["follower_count_statut"] = (
                                profil["statut"] if nombre is not None
                                else ("indisponible" if profil["statut"] == "ok"
                                      else profil["statut"]))
                            from collecte.classes_abonnes import classer_nombre_abonnes
                            record["classe_abonnes"] = classer_nombre_abonnes(nombre)
                        if job.settings.collecter_is_verified:
                            verifie = profil.get("is_verified")
                            record["is_verified"] = verifie
                            record["is_verified_statut"] = (
                                profil["statut"] if verifie is not None
                                else ("indisponible" if profil["statut"] == "ok"
                                      else profil["statut"]))
                    # Les classes et le taux sont calculés même si le TXT n'en a pas besoin.
                    # Catégorie déterminée par l'auteur lu, y compris depuis un hashtag.
                    # Conserver les quatre indicatrices dans les données archivées.
                    from collecte.presse import (categorie_presse_publication,
                                                 colonnes_categories_presse)
                    categorie_compte = categorie_presse_publication(record)
                    if categorie_compte and not record.get("categorie_media"):
                        record["categorie_media"] = categorie_compte
                    record.update(colonnes_categories_presse(record))
                    from collecte.variables_numeriques import indicateurs_numeriques
                    record.update(indicateurs_numeriques(record))
                    if job.settings.source_collecte != "presse":
                        # Requête par hashtags ou profils : mémoriser les
                        # critères de collecte, et les correspondances réelles
                        # issues des métadonnées API ou du texte de la légende.
                        record["hashtags_recherches"] = list(job.settings.hashtags)
                        record["hashtags_correspondants"] = (
                            hashtags_correspondants_publication(
                                record.get("description", ""), job.settings,
                                record.get("hashtags")))
                    if job.settings.source_collecte == "presse":
                        # Conserver le filtre demandé et les hashtags réellement rencontrés.
                        recherches = (job.settings.hashtags_presse
                                      if job.settings.croiser_hashtag_presse else [])
                        presents = [
                            nom for nom in recherches if correspondance_hashtag(
                                record.get("description", ""), nom)
                        ]
                        if recherches:
                            presents = hashtags_correspondants_presse(
                                record.get("description", ""), job.settings,
                                record.get("hashtags"))
                        record["hashtags_recherches"] = list(recherches)
                        record["hashtags_correspondants"] = presents
                        record["operateur_hashtags"] = (
                            job.settings.operator_presse if recherches else None)
                    if job.settings.telecharger_mp4:
                        from telechargement_videos import correspondance_video
                        record.update(correspondance_video(record))
                    # Même découverte et lecture que le mode hashtag ; filtrer ensuite
                    # l’auteur effectivement lu, et non une grille de profil différente.
                    if (job.settings.source_collecte != "hashtags"
                            and str(record.get("author", "")).lower() not in medias_par_compte):
                        hors_selection += 1
                        job.journal.append({"publication_id": record.get("id"),
                            "auteur": record.get("author"), "filtre_auteur": "hors_selection"})
                        job.update(processed=index)
                        if job.settings.sauvegarde_progressive and index % 10 == 0:
                            job.sauvegarder_point()
                        continue
                    periode = evaluer_periode(record.get("created_at"), job.settings.date_debut, job.settings.date_fin)
                    if periode in {"hors_periode", "date_indeterminee"}:
                        record["motif_non_retenue"] = periode
                        with job.lock:
                            if periode == "hors_periode": job.hors_periode += 1
                            else: job.dates_indeterminees += 1
                        job.journal.append({"publication_id":record["id"], "created_at":record.get("created_at"), "filtre_date":periode})
                    else:
                        # Filtre positif appliqué après lecture du contenu IA :
                        # ne jamais confondre une étiquette IA avec un résumé.
                        if (job.settings.filtrer_texte_ia_tiktok
                                and not texte_ia_tiktok_exploitable(record)):
                            record["motif_non_retenue"] = "sans_texte_ia_tiktok"
                            with job.lock:
                                job.exclus_sans_texte_ia += 1
                            job.journal.append({
                                "publication_id": record.get("id"),
                                "filtre": "sans_texte_ia_tiktok",
                                "statut_resume_ia": record.get("statut_resume_ia") or "non_renseigne",
                            })
                            job.update(processed=index)
                            if job.settings.sauvegarde_progressive and index % 10 == 0:
                                job.sauvegarder_point()
                            continue
                        if job.settings.enrichie:
                            media = medias_par_compte.get(record["author"].lower(), {})
                            record.update(
                                media_id=media.get("id") or record.get("media_id"),
                                categorie_media=(
                                    media.get("categorie")
                                    or record.get("categorie_media")),
                                retenue=False)
                            if not job.settings.filtrer_texte_ia_tiktok:
                                job.publications.append(record)
                        if str(record.get("description") or "").strip():
                            matches = matches_hashtags(
                                record["description"], job.settings,
                                hashtags_observes=record.get("hashtags"))
                            # Compter sur la même légende et dans la même période que le filtre.
                            with job.lock:
                                for hashtag in job.bilan_hashtags:
                                    # Un même critère sert au filtrage et au bilan,
                                    # pour éviter un texte retenu mais non comptabilisé.
                                    correspondance = (
                                        hashtag in record.get("hashtags_correspondants", []))
                                    if correspondance:
                                        job.bilan_hashtags[hashtag] += 1
                                if matches:
                                    job.correspondances_hashtags += 1
                            # Évaluer la langue indépendamment du filtre des hashtags.
                            language = (
                                classify_description(record["description"])
                                if job.settings.french_only else None
                            )
                            record["langue_detection"] = language
                            
                            with job.lock:
                                if not matches:
                                    record["motif_non_retenue"] = "filtre_hashtags"
                                    job.filtered += 1
                                elif language == "other":
                                    record["motif_non_retenue"] = "autre_langue"
                                    job.non_french += 1
                                elif language == "unknown":
                                    # L'incertitude statistique n'est pas une preuve
                                    # de langue étrangère : conserver la légende
                                    # originale et signaler sa langue indéterminée.
                                    record["retenue"] = True
                                    record["motif_non_retenue"] = "retenue_langue_indeterminee"
                                    job.language_unknown += 1
                                    job.records.append(record)
                                else:
                                    record["retenue"] = True
                                    record["motif_non_retenue"] = "retenue"
                                    job.records.append(record)
                            # Avec le filtre positif IA, tous les exports doivent
                            # contenir uniquement les publications réellement retenues.
                            if (record.get("retenue") and job.settings.filtrer_texte_ia_tiktok
                                    and job.settings.enrichie):
                                job.publications.append(record)
                            # Les commentaires sont demandés uniquement pour les publications retenues.
                            if record.get("retenue") and job.settings.collecter_commentaires:
                                try:
                                    if moteur_actif == "research":
                                        from collecte.researchapi import collecter_commentaires_research
                                        if limitation_commentaires_research:
                                            record["collecte_commentaires"] = {
                                                "statut": "acces_refuse",
                                                "source": "research_api_officielle",
                                                "exhaustif": False,
                                                "message": "Collecte des commentaires suspendue après un refus Research."
                                            }
                                            resultat = None
                                        else:
                                            resultat = collecter_commentaires_research(
                                                record, reponses=job.settings.collecter_reponses,
                                                verifier=job.check, pause=job.pause,
                                                credentiels=connexion.research_credentiels)
                                            if resultat.get("bloquer_requetes"):
                                                limitation_commentaires_research = True
                                    else:
                                        from collecte.commentaires import collecter_commentaires
                                        if moteur_actif in {"gallerydl", "tikhub", "apify"}:
                                            driver.get(url)
                                        resultat = collecter_commentaires(
                                            driver, record, job.settings.limite_commentaires,
                                            job.settings.collecter_reponses, verifier=job.check,
                                            pause=job.pause, interact=connexion.intervenir)
                                    if resultat is not None:
                                        with job.lock:
                                            recuperes = resultat.pop("commentaires")
                                            resultat.setdefault("recuperes", len(recuperes))
                                            resultat.setdefault(
                                                "annonces",
                                                (record.get("engagement") or {}).get("commentaires", {}).get("valeur"))
                                            job.commentaires.extend(recuperes)
                                            record["collecte_commentaires"] = resultat
                                except scraper.WebDriverException as erreur:
                                    if scraper.est_erreur_session(erreur): raise
                                    record["collecte_commentaires"] = {"statut": "inaccessible", "exhaustif": False}
                        else:
                            record["motif_non_retenue"] = "legende_vide"
                            with job.lock:
                                job.legendes_vides += 1
                except scraper.WebDriverException as erreur:
                    code = "erreur_session" if scraper.est_erreur_session(erreur) else "erreur_extraction_video"
                    job.diagnostics.append({"code": code, "publication_id": scraper.canonical_post(url)[0],
                                            "exception": type(erreur).__name__})
                    with job.lock:
                        job.errors += 1
                    if scraper.est_erreur_session(erreur):
                        job.update(processed=index)
                        raise
                job.update(processed=index)
                if (job.settings.source_collecte != "hashtags"
                        or moteur_actif != "research"
                        or index % 20 == 0 or index == len(links)):
                    # Les écritures complètes du TXT à chaque publication
                    # deviennent quadratiques sur plusieurs milliers de vidéos.
                    # En Research Hashtags, sauvegarder par lot et en fin de
                    # page ; le finally effectue toujours l'écriture finale.
                    job.save()
                if job.base and (not job.settings.filtrer_texte_ia_tiktok
                                 or record.get("retenue")):
                    job.base.enregistrer(job.id, job.publications[-1:], job.commentaires)
                if (job.plan_research_id and job.publications
                        and (not job.settings.filtrer_texte_ia_tiktok
                             or record.get("retenue"))):
                    # Écriture permanente au fil de l'eau, indépendante de
                    # l'expiration des fichiers temporaires de collecte.
                    from stockage.collectes_research import enregistrer_partiel
                    enregistrer_partiel(job.racine, job.plan_research_id,
                        job.publications[-1], job.commentaires)
                if index % 10 == 0 and not job.plan_research_id:
                    # PostgreSQL conserve un point automatique toutes les dix vidéos.
                    job.sauvegarder_postgres(progressif=True)
                if job.settings.sauvegarde_progressive and index % 10 == 0:
                    job.sauvegarder_point()

        # Les compteurs sont cumulés entre sources sans confondre une
        # vidéo trouvée par l'API et une publication valide pour le TXT.
        requetes_sources_terminees = 0
        candidats_sources_termines = 0
        ecartes_sources_termines = 0
        # Premier contrôle après la première page, puis séquences de
        # 1 000 candidats par défaut. Conserver le curseur Research en mémoire
        # durant la pause évite de recommencer la recherche.
        prochain_controle_research = 100
        for numero_source, source in enumerate(sources, 1):
            job.check()
            if job.settings.test_research_10_publications and len(unique_links) >= 10:
                break
            # Double garde-fou : même si un connecteur de hashtags renvoie
            # trop d'URL, ne jamais retenir plus que la limite globale saisie.
            if (job.settings.source_collecte == "hashtags" and plafond_decouverte is not None
                    and len(unique_links) >= plafond_decouverte):
                break
            job.source_en_cours_id = (
                source.get("id") if job.settings.source_collecte == "presse"
                else "#" + source["hashtag"]
                if job.settings.source_collecte == "hashtags" else None)
            etiquette = "#" + source["hashtag"] if "hashtag" in source else "@" + source["compte"]
            entree_source = None
            job.update(status="discovering", message=f"Source {numero_source}/{len(sources)} : recherche des publications de {etiquette}…")
            rapport = {}
            if job.settings.source_collecte == "hashtags" and moteur_actif == "research":
                # Inscrire la source avant la première page. Une interruption
                # manuelle ou une erreur 5xx préserve ainsi son état partiel
                # pour une reprise sans perdre les textes déjà enregistrés.
                entree_source = {
                    "source": etiquette, "date": scraper.utc_now(),
                    "rapport": rapport, "statut_source": "en_cours",
                    "message": "Recherche Research en cours : données partielles."}
                job.journal.append(entree_source)
            # Limiter chaque source à la quantité restante du test global.
            limite_initiale = args.limit
            if job.settings.test_research_10_publications:
                # Répartir le budget de dix vidéos entre toutes les sources.
                # Deux médias donnent cinq publications par média.
                restant = max(0, 10 - len(unique_links))
                nombre_sources_restantes = len(sources) - numero_source + 1
                args.limit = (restant + nombre_sources_restantes - 1) // nombre_sources_restantes
            # Les URL sélectionnées au cours des pages successives de cette
            # source sont ajoutées immédiatement au corpus et non après
            # plusieurs milliers de résultats accumulés dans la pagination.
            liens_verifies_source = {}
            def suivre_decouverte(nombre):
                nonlocal prochain_controle_research
                requete = rapport.get("requete_recherche") or etiquette
                if (job.settings.source_collecte == "hashtags"
                        and moteur_actif == "research"
                        and "liens_page_research" in rapport):
                    fiches_page = rapport.get("metadonnees_api") or {}
                    for adresse in rapport.get("liens_page_research") or []:
                        identite = scraper.canonical_post(adresse)
                        fiche = (fiches_page.get(str(identite[0]))
                                 if identite else None)
                        if not isinstance(fiche, dict):
                            continue
                        if not verifier_criteres_hashtags_research(
                                fiche, job.settings):
                            continue
                        identifiant = str(identite[0])
                        liens_verifies_source.setdefault(identifiant, identite[1])
                        unique_links.setdefault(identifiant, identite[1])
                        metadonnees_api.setdefault(identifiant, fiche)
                    # Le bilan par source reflète seulement les vidéos
                    # conformes aux critères ; les candidats restent comptés
                    # séparément par la Research API.
                    rapport["discovered_urls"] = list(liens_verifies_source.values())
                    job.actualiser_decouverte(rapport)
                    requetes_lot = (
                        requetes_sources_terminees
                        + int(rapport.get("requetes_tentees") or 0))
                    candidats_lot = (
                        candidats_sources_termines
                        + int(rapport.get("candidats_examines") or 0))
                    ecartes_lot = (
                        ecartes_sources_termines
                        + int(rapport.get("ecartes_hashtags_api") or 0))
                    quota_local = None
                    try:
                        from stockage.collectes_research import etat_quota
                        quota_local = etat_quota(
                            Path(os.getenv("DATA_DIR", "data")))
                    except (OSError, RuntimeError, ValueError, sqlite3.Error):
                        # Une panne du diagnostic de quota n'interrompt
                        # jamais les vidéos déjà accessibles.
                        pass
                    job.update(
                        requetes_research_lot=requetes_lot,
                        candidats_research_lot=candidats_lot,
                        ecartes_hashtags_research_lot=ecartes_lot,
                        quota_research_local=quota_local,
                        message=(
                            f"{etiquette} : {candidats_lot} vidéo(s) reçue(s) "
                            f"de TikTok, {len(unique_links)} conforme(s) "
                            f"aux hashtags, {job.processed} traitée(s), "
                            f"{len(job.records)} texte(s) retenu(s) ; "
                            f"{requetes_lot} requête(s) Research."))
                    if len(unique_links) > job.processed:
                        lire_decouvertes()
                    if rapport.get("apercu_ecartes_research"):
                        with job.lock:
                            for element in rapport["apercu_ecartes_research"]:
                                if len(job.apercu_ecartes_research) >= 20:
                                    break
                                if element not in job.apercu_ecartes_research:
                                    job.apercu_ecartes_research.append(element)
                    # Une première page peut contenir moins de 100 vidéos.
                    # Le contrôle initial doit intervenir dès sa réception.
                    premier_controle = (
                        prochain_controle_research == 100
                        and int(rapport.get("pages_research") or 0) == 1)
                    if (not job.settings.test_research_10_publications
                            and (premier_controle
                                 or candidats_lot >= prochain_controle_research)):
                        if prochain_controle_research == 100:
                            prochain_controle_research = (
                                job.settings.lot_candidats_research)
                        else:
                            prochain_controle_research += (
                                job.settings.lot_candidats_research)
                        job.continuer_research.clear()
                        job.update(
                            status="validation_research",
                            attente_validation_research=True,
                            message=(
                                "Collecte suspendue pour contrôle : examinez "
                                "les légendes, hashtags et régions dans le tableau "
                                "ci-dessous, puis choisissez Poursuivre ou Arrêter. "
                                f"{candidats_lot} candidat(s) API examinés."))
                        # L'arrêt reste immédiatement utilisable pendant
                        # l'attente de décision de l'utilisateur.
                        while not job.continuer_research.wait(0.5):
                            job.check()
                        job.check()
                        job.update(
                            status="discovering",
                            attente_validation_research=False,
                            message="Pagination Research reprise après contrôle.")
                    return
                job.actualiser_decouverte(rapport)
                objectif = (f"{nombre}/{args.limit}" if args.limit is not None
                            and job.settings.source_collecte != "hashtags" else str(nombre))
                message_progression = (
                    f"{objectif} candidat(s) trouvés pour vérification ET/OU…"
                    if job.settings.source_collecte == "hashtags"
                    else f"{objectif} retenue(s) pour ce compte…")
                job.update(message=f"Source {numero_source}/{len(sources)} — recherche {requete} : "
                    f"{rapport.get('candidats_examines', nombre)} publication(s) découverte(s), "
                    + message_progression)
            try:
                found = connexion.decouvrir(source, rapport,
                    contexte=f"Source {numero_source}/{len(sources)} — {etiquette}",
                    progression=suivre_decouverte)
                if (job.settings.source_collecte == "hashtags"
                        and moteur_actif == "research"):
                    # Contrôler ET/OU dès la découverte, et non seulement
                    # après avoir ouvert des vidéos hors sujet.
                    found, ecartes, indetermines = filtrer_decouverte_hashtags_research(
                        found, rapport.get("metadonnees_api") or {},
                        job.settings)
                    rapport["ecartes_combinaison_hashtags"] = (
                        rapport.get("ecartes_combinaison_hashtags", 0) + ecartes)
                    rapport["ecartes_metadonnees_absentes"] = (
                        rapport.get("ecartes_metadonnees_absentes", 0) + indetermines)
                    if ecartes or indetermines:
                        job.diagnostics.append({
                            "code": "preselection_hashtags_research",
                            "source": etiquette,
                            "hors_criteres": ecartes,
                            "sans_metadonnees": indetermines,
                            "retenues_pour_lecture": len(found),
                            "operateur": job.settings.operator,
                        })
                rapport["discovered_urls"] = found
                # Une découverte réussie réinitialise le compteur de pannes 5xx.
                echecs_serveur_research_consecutifs = 0
                if (job.settings.source_collecte in {"presse", "comptes", "hashtags"}
                        and moteur_actif in {"api", "research", "gallerydl", "tikhub", "apify"}):
                    for identifiant, donnees in (rapport.get("metadonnees_api") or {}).items():
                        if isinstance(donnees, dict):
                            metadonnees_api.setdefault(str(identifiant), donnees)
                if rapport.get("recherches_en_echec"):
                    job.update(search_errors=job.search_errors + 1)
                message_source = rapport.get("bilan_recherche") or ("Recherche partielle : une recherche TikTok a échoué."
                                  if rapport.get("recherches_en_echec") else "Recherche terminée.")
                message_rapport = (
                    message_source if found or rapport.get("bilan_recherche") else
                    "Collecte partielle : aucune publication du compte trouvée "
                    "dans les résultats accessibles. Cela ne signifie pas que "
                    "le compte est vide."
                    if job.settings.source_collecte != "hashtags" else
                    "Aucune publication correspondant à cette recherche n’a "
                    "été trouvée. Cela ne signifie pas que le compte est vide.")
                if entree_source is None:
                    entree_source = {
                        "source": etiquette, "date": scraper.utc_now(),
                        "rapport": rapport, "statut_source": "en_cours",
                        "message": message_rapport}
                    job.journal.append(entree_source)
                else:
                    entree_source["message"] = message_rapport
                for url in found:
                    identity = scraper.canonical_post(url)
                    if identity and (job.settings.source_collecte == "hashtags"
                                     or identity[2].casefold() in medias_par_compte):
                        if (job.settings.test_research_10_publications
                                and len(unique_links) >= 10):
                            break
                        if (job.settings.source_collecte == "hashtags"
                                and plafond_decouverte is not None
                                and len(unique_links) >= plafond_decouverte):
                            break
                        unique_links.setdefault(identity[0], identity[1])
            except (RuntimeError, scraper.WebDriverException) as erreur:
                LOG.warning("Source %s : %s", etiquette, type(erreur).__name__)
                if "diagnostic" not in rapport:
                    rapport["diagnostic"] = {"exception": type(erreur).__name__}
                from collecte.presse_research import ResearchErreur
                from collecte.presse_api import PresseRateLimitError, PresseCooldownError
                from collecte.quotas_exploitation import QuotaScrapingAtteint
                statut_echec = ("partielle" if rapport.get("discovered_urls") else "interrompue") if isinstance(
                    erreur, (ResearchErreur, PresseRateLimitError, PresseCooldownError, QuotaScrapingAtteint)) else "echec"
                message_echec = expliquer_echec_source(rapport, erreur)
                if entree_source is not None:
                    entree_source.update(
                        statut="inaccessible", statut_source=statut_echec,
                        date=scraper.utc_now(), message=message_echec)
                else:
                    job.journal.append({
                        "source": etiquette, "statut": "inaccessible",
                        "statut_source": statut_echec, "date": scraper.utc_now(),
                        "rapport": rapport, "message": message_echec})
                from collecte.presse_api import PresseRateLimitError, PresseCooldownError
                from collecte.presse_research import ResearchErreur
                from collecte.quotas_exploitation import QuotaScrapingAtteint
                if isinstance(erreur, ResearchErreur):
                    from collecte.researchapi import (
                        ResearchErreurServeur, poursuivre_apres_erreur_serveur)
                    if (job.settings.source_collecte == "hashtags"
                            and moteur_actif == "research"):
                        # Une erreur 500 ou un refus de quota peut survenir
                        # après plusieurs pages. Ne jamais intégrer les liens
                        # partiels avant leur vérification ET/OU.
                        partiels, ecartes, indetermines = (
                            filtrer_decouverte_hashtags_research(
                                rapport.get("discovered_urls") or [],
                                rapport.get("metadonnees_api") or {},
                                job.settings))
                        rapport["discovered_urls"] = partiels
                        rapport["ecartes_combinaison_hashtags"] = (
                            rapport.get("ecartes_combinaison_hashtags", 0) + ecartes)
                        rapport["ecartes_metadonnees_absentes"] = (
                            rapport.get("ecartes_metadonnees_absentes", 0)
                            + indetermines)
                    for identifiant, fiche in (rapport.get("metadonnees_api") or {}).items():
                        if isinstance(fiche, dict):
                            metadonnees_api.setdefault(str(identifiant), fiche)
                    for url in rapport.get("discovered_urls", []):
                        identite = scraper.canonical_post(url)
                        if identite and (
                                job.settings.source_collecte == "hashtags"
                                or identite[2].casefold() in medias_par_compte):
                            if (job.settings.test_research_10_publications
                                    and len(unique_links) >= 10):
                                break
                            unique_links.setdefault(identite[0], identite[1])
                    job.update(search_errors=job.search_errors + 1)
                    if isinstance(erreur, ResearchErreurServeur):
                        echecs_serveur_research_consecutifs += 1
                        poursuivre = poursuivre_apres_erreur_serveur(
                            erreur,
                            source_collecte=job.settings.source_collecte,
                            moteur_actif=moteur_actif,
                            echecs_consecutifs=echecs_serveur_research_consecutifs)
                        job.diagnostics.append({
                            "code": "research_erreur_serveur",
                            "source": etiquette,
                            "http_status": erreur.statut_http,
                            "echecs_consecutifs": echecs_serveur_research_consecutifs,
                            "poursuite_autorisee": poursuivre,
                        })
                        if poursuivre:
                            # Le média reste en erreur dans le bilan, mais la
                            # recherche peut continuer sur les autres comptes.
                            job.update(
                                status="discovering",
                                message=(
                                    f"{etiquette} : HTTP {erreur.statut_http} côté TikTok. "
                                    "Source à reprendre ultérieurement ; "
                                    "poursuite des autres médias."
                                ),
                            )
                            job.pause(2.0)
                            continue
                        limitation_research = True
                        job.update(
                            status="finalizing",
                            message=(
                                "Research API : trois erreurs HTTP 5xx consécutives "
                                "ou erreur serveur hors collecte Presse ; "
                                "arrêt de précaution du lot."
                            ),
                        )
                        break
                    limitation_research = True
                    job.update(
                        status="finalizing",
                        message="Research API : refus d'accès, quota ou erreur non transitoire ; lot interrompu.",
                    )
                    break
                if isinstance(erreur, QuotaScrapingAtteint):
                    limitation_budget = True
                    job.update(search_errors=job.search_errors + 1)
                    break
                if isinstance(erreur, (PresseRateLimitError, PresseCooldownError)):
                    # Le média interrompu n'a pas été intégralement collecté :
                    # exclure ses liens/mesures incomplets de tous les exports,
                    # sans perdre les publications des médias précédents.
                    rapport["discovered_urls"] = []
                    rapport["metadonnees_api"] = {}
                    rapport["retenues_par_compte"] = {}
                    for etape in rapport.get("recherches_compte", []):
                        etape["discovered_urls"] = []
                        etape["metadonnees_api"] = {}
                    links = list(unique_links.values())
                    limitation_tiktok = True
                    job.update(
                        search_errors=job.search_errors + 1,
                        status="finalizing",
                        message="TikTok HTTP 429 : collecte interrompue ; seules les données entièrement récupérées sont conservées.",
                    )
                    break
                if len(sources) == 1 or scraper.est_erreur_session(erreur): raise
                job.update(search_errors=job.search_errors + 1)
            finally:
                args.limit = limite_initiale
                if (job.settings.source_collecte == "hashtags"
                        and moteur_actif == "research"):
                    requetes_sources_terminees += int(
                        rapport.get("requetes_tentees") or 0)
                    candidats_sources_termines += int(
                        rapport.get("candidats_examines") or 0)
                    ecartes_sources_termines += int(
                        rapport.get("ecartes_hashtags_api") or 0)
                    job.update(
                        requetes_research_lot=requetes_sources_terminees,
                        candidats_research_lot=candidats_sources_termines,
                        ecartes_hashtags_research_lot=ecartes_sources_termines)
                job.actualiser_decouverte(rapport)
            job.update(discovered=len(unique_links))
            # Exporter chaque compte aussitôt sa découverte terminée.
            if ((job.settings.source_collecte != "hashtags" or filtre_dates_hashtags)
                    and len(unique_links) > job.processed):
                lire_decouvertes()
            if not job.plan_research_id:
                # Chaque média terminé devient consultable sans attendre le lot complet.
                job.sauvegarder_postgres(progressif=True)
            if filtre_dates_hashtags and args.limit is not None and len(job.records) >= args.limit:
                break
            if entree_source is not None and entree_source.get("statut") != "inaccessible":
                incomplete = bool(rapport.get("collecte_partielle") or rapport.get("recherches_en_echec")
                    or any(r.get("collecte_partielle") or r.get("recherches_en_echec")
                        for r in rapport.get("recherches_compte", [])))
                entree_source["statut_source"] = "partielle" if incomplete else "traitee"
            if (job.settings.test_research_10_publications
                    and (job.processed >= 10 or len(unique_links) >= 10)):
                break
        if job.settings.collecter_republications_research and moteur_actif == "research":
            from collecte.researchapi import ResearchErreur, ResearchAccesRefuse
        # Les republications sont une population distincte : le créateur de la
        # vidéo n'est pas nécessairement l'un des médias choisis. Les conserver
        # dans une table séparée, sans contourner le contrôle des auteurs
        # du corpus principal ni inventer des résultats négatifs.
        if (job.settings.collecter_republications_research
                and moteur_actif == "research" and not limitation_research
                and not job.stop.is_set()):
            from collecte.republications_research import (
                collecter_republications_research, rapprocher_republications)
            from collecte.exclusion_hashtags import hashtags_a_exclure
            for media in sources:
                job.check()
                compte = media["compte"]
                diagnostic = {}
                job.update(status="collecting",
                    message="Recherche des republications de @" + compte + "…")
                def accepter_republication(fiche):
                    if hashtags_a_exclure(fiche, job.settings.hashtags_exclus):
                        return False
                    if (job.settings.croiser_hashtag_presse
                            and not matches_hashtags(
                                fiche.get("description") or "", job.settings,
                                hashtags_observes=fiche.get("hashtags"))):
                        return False
                    if (job.settings.french_only
                            and classify_description(fiche.get("description") or "") == "other"):
                        return False
                    return True
                try:
                    lignes = collecter_republications_research(
                        compte, job.settings.maximum_republications_par_compte,
                        debut=job.settings.date_debut, fin=job.settings.date_fin,
                        verifier=job.check, pause=job.pause,
                        credentiels=connexion.research_credentiels,
                        accepter=accepter_republication, rapport=diagnostic)
                    for ligne in lignes:
                        ligne["media_id"] = media["id"]
                        # Même choix de colonnes que dans publications.csv.
                        ligne["inclure_hashtags_csv"] = job.settings.inclure_hashtags_csv
                    job.republications.extend(lignes)
                except (ResearchErreur, ValueError) as erreur:
                    diagnostic.update(statut="erreur_research",
                                      exception=type(erreur).__name__)
                    job.bilan_republications[compte] = diagnostic
                    job.update(search_errors=job.search_errors + 1)
                    job.diagnostics.append({
                        "code": "republications_research",
                        "compte": compte, "exception": type(erreur).__name__})
                    # Un refus de droits ou de quota n'est pas un résultat négatif.
                    if isinstance(erreur, ResearchAccesRefuse):
                        break
                    continue
                job.bilan_republications[compte] = diagnostic
            rapprocher_republications(job.publications, job.republications)
            rapprocher_republications(job.records, job.republications)
        # Un 429 interdit aussi la lecture différée des vidéos déjà découvertes.
        if limitation_research and len(unique_links) > job.processed:
            lire_decouvertes()
        if (job.settings.source_collecte == "hashtags" and not filtre_dates_hashtags
                and not limitation_tiktok and not limitation_budget and not job.stop.is_set()):
            lire_decouvertes()
        if (job.settings.source_collecte == "hashtags" and moteur_actif == "research"
                and job.settings.profils_medias_variables):
            # Même tableau de métriques que Presse, mais une ligne par auteur
            # distinct effectivement présent dans le corpus hashtags.
            from collecte.profils_medias import ligne_profil_media
            from collecte.researchapi import (
                collecter_metriques_profil_media_research,
                ResearchErreur, ResearchAccesRefuse)
            deja_recuperes = {
                str(fiche.get("compte") or "").casefold(): fiche
                for fiche in job.profils_medias if isinstance(fiche, dict)
            }
            auteurs = dict.fromkeys(
                str(publication.get("author") or "").strip().lstrip("@").casefold()
                for publication in job.publications
                if isinstance(publication, dict) and publication.get("author")
            )
            quota_profils_refuse = limitation_research or limitation_abonnes_research
            for auteur in auteurs:
                if deja_recuperes.get(auteur, {}).get("statut_profil") == "ok":
                    continue
                job.check()
                donnees, etat = {}, "indisponible"
                job.update(status="collecting",
                           message="Lecture des métriques du compte @" + auteur + "…")
                if quota_profils_refuse:
                    etat = "acces_refuse"
                else:
                    try:
                        donnees = collecter_metriques_profil_media_research(
                            auteur, job.settings.profils_medias_variables,
                            verifier=job.check,
                            credentiels=connexion.research_credentiels)
                        etat = ("ok" if any(valeur is not None
                                         for valeur in donnees.values())
                                else "indisponible")
                    except ResearchAccesRefuse:
                        quota_profils_refuse = True
                        limitation_abonnes_research = True
                        etat = "acces_refuse"
                    except ResearchErreur:
                        etat = "indisponible"
                from collecte.presse import categorie_presse_publication
                fiche_auteur = {
                    "compte": auteur, "nom": auteur,
                    "categorie": categorie_presse_publication({"author": auteur}),
                    "url": "https://www.tiktok.com/@" + auteur,
                }
                ligne = ligne_profil_media(
                    fiche_auteur, job.settings.profils_medias_variables,
                    job.settings.profils_medias_classes,
                    donnees=donnees, statut=etat)
                if auteur in deja_recuperes:
                    position = next(
                        (i for i, valeur in enumerate(job.profils_medias)
                         if valeur.get("compte") == auteur), None)
                    if position is not None:
                        job.profils_medias[position] = ligne
                else:
                    job.profils_medias.append(ligne)
                deja_recuperes[auteur] = ligne
        exclus_decouverte = set().union(*(set(e.get("rapport", {}).get("auteurs_ecartes_ids", [])) for e in job.journal))
        recherche_partielle = any(e.get("rapport", {}).get("collecte_partielle") for e in job.journal)
        if job.settings.test_research_10_publications:
            # L'arrêt voulu après dix lectures ne constitue pas une collecte partielle.
            recherche_partielle = False
        if job.settings.source_collecte != "hashtags":
            retenues_par_compte = {compte: 0 for compte in medias_par_compte}
            for url in links:
                identite = scraper.canonical_post(url)
                if identite and identite[2].casefold() in retenues_par_compte:
                    retenues_par_compte[identite[2].casefold()] += 1
            # Chaque profil contribue indépendamment à la limite demandée.
            if args.limit is not None and not job.settings.test_research_10_publications:
                recherche_partielle = any(nombre < args.limit for nombre in retenues_par_compte.values())
        final_status = "partial" if job.errors or job.search_errors or recherche_partielle else "completed"
        final_message = f"{len(job.records)} texte(s) collecté(s) sur {job.processed + job.reprise_decalage} publication(s) consultée(s)."
        if job.settings.filtrer_texte_ia_tiktok:
            final_message += (
                f" Filtre texte IA TikTok : {job.exclus_sans_texte_ia} publication(s) "
                "écartée(s), car aucun résumé natif exploitable n'a été récupéré."
            )
        if job.settings.collecter_republications_research:
            final_message += (
                f" Republications Research : {len(job.republications)} "
                "relation(s) compte–vidéo identifiée(s) dans la collecte séparée. "
                "Une absence n'est pas une preuve de non-republication."
            )
        if (job.settings.source_collecte == "hashtags" and moteur_actif == "research"):
            final_message += (
                f" Research Hashtags : {job.candidats_research_lot} candidat(s) "
                f"renvoyé(s) par TikTok, {len(unique_links)} vidéo(s) "
                f"conforme(s) retenue(s) pour lecture, "
                f"{job.requetes_research_lot} requête(s) de recherche. "
                f"{job.ecartes_hashtags_research_lot} candidat(s) "
                "sans correspondance exacte dans les métadonnées.")
        if job.settings.test_research_10_publications:
            final_message += (
                f" Mode test Research : {job.processed}/10 publication(s) "
                "conforme(s) consultée(s) au maximum. Les vidéos écartées "
                "dès la découverte ne sont pas comptées comme traitées. "
                "Décochez « Faire un test sur 10 publications » pour lancer "
                "la collecte complète."
            )
        if not job.records:
            final_message = ("Aucune publication accessible : consultez le détail des sources."
                             if not links else "Aucune légende exploitable retenue parmi les publications consultées.")
            if not links and job.settings.source_collecte != "hashtags":
                final_message = ("Aucune publication publique accessible pour les comptes sélectionnés. "
                                 "Consultez les diagnostics de chaque source ; les filtres de langue et de légende n’ont pas été appliqués.")
            elif job.settings.test_research_10_publications:
                final_message += (
                    " Consultez le diagnostic du test pour connaître les légendes "
                    "absentes et les motifs d'exclusion.")
            if job.settings.filtrer_texte_ia_tiktok and job.exclus_sans_texte_ia:
                final_message = (
                    "Aucun texte IA TikTok exploitable parmi les publications consultées. "
                    f"{job.exclus_sans_texte_ia} publication(s) écartée(s) : "
                    "résumé non trouvé ou lecture inaccessible."
                )
            elif job.filtered and job.processed:
                final_message = "Aucun texte ne correspond à cette combinaison dans les publications consultées."
        if not job.records and job.republications:
            final_message = (
                "Aucune vidéo originale des médias retenue, mais "
                f"{len(job.republications)} relation(s) de republication "
                "sont accessibles dans republications.csv et republications.json."
            )
        if job.settings.french_only and job.processed:
            if not job.records and job.non_french:
                final_message = ("Aucun texte retenu par le filtre français parmi "
                                 "les légendes consultées.")
            final_message += (
                f" Filtre français : {job.non_french} texte(s) identifié(s) "
                f"dans une autre langue écartés ; {job.language_unknown} "
                "légende(s) de langue indéterminée conservée(s) et signalée(s)."
            )
        if job.settings.hashtags_exclus:
            final_message += (
                f" Exclusion NOT : {job.exclus_hashtags} publication(s) écartée(s) "
                "après lecture. La Research API applique aussi NOT à la recherche.")
        if job.settings.hashtags and job.processed:
            nom_filtre = "hashtags et texte" if job.settings.rechercher_dans_texte else "hashtags"
            final_message += f" {job.filtered} texte(s) écarté(s) par le filtre {nom_filtre}."
            if job.settings.source_collecte != "hashtags":
                final_message += " Combinaison ET/OU vérifiée sur les légendes des comptes sélectionnés."
        if job.settings.source_collecte != "hashtags":
            final_message += (f" {len(exclus_decouverte)} publication(s) d’autres auteurs écartée(s) à la découverte ; "
                              f"{hors_selection} écartée(s) après contrôle de l’auteur à la lecture.")
        if job.settings.date_debut or job.settings.date_fin:
            if not job.records and (job.hors_periode or job.dates_indeterminees):
                final_message = "Aucun texte retenu avec la période et les autres filtres choisis."
            final_message += f" Période : {job.hors_periode} publication(s) hors période et {job.dates_indeterminees} publication(s) sans date exploitable écartées."
        if job.search_errors:
            final_message += f" {job.search_errors} source(s) partiellement ou totalement inaccessible(s) ; les résultats sont incomplets."
        if job.errors:
            final_message += f" {job.errors} publication(s) dont la légende n’a pas pu être lue."
        if job.settings.source_collecte != "hashtags":
            if job.settings.test_research_10_publications:
                pass  # Le résumé du mode test a déjà été ajouté.
            elif args.limit is None:
                final_message += (" Research API : pagination automatique des résultats accessibles ; "
                                  "l’exhaustivité du corpus n’est pas garantie.")
            else:
                final_message += (" Collecte partielle : la recherche TikTok n’a pas fourni la limite demandée ; résultats non exhaustifs."
                                  if recherche_partielle else " Collecte limitée au nombre demandé par compte ; historique complet non garanti.")
        if limitation_budget:
            final_message += (" Plafond interne de requêtes API Presse atteint : "
                              "collecte arrêtée sans demander davantage de données à TikTok.")
            final_status = "partial" if links else "failed"
        if limitation_abonnes_research:
            final_message += (" Research API : accès au nombre d\u0027abonnés refusé ; "
                              "les valeurs indisponibles sont notées indéterminées.")
            if final_status == "completed":
                final_status = "partial"
        if limitation_commentaires_research:
            final_message += (" Commentaires Research API : refus ou quota détecté ; "
                              "nouvelles requêtes de commentaires suspendues.")
            if final_status == "completed":
                final_status = "partial"
        if limitation_research:
            final_message += (
                " Research API : lot arrêté après un refus, une erreur non "
                "transitoire ou plusieurs erreurs HTTP 5xx consécutives. "
                "Données déjà reçues conservées ; consulter le diagnostic.")
            final_status = "partial" if links else "failed"
        if limitation_tiktok:
            final_message += (" TikTok HTTP 429 : découverte arrêtée immédiatement. "
                              "Les autres médias de cette collecte n'ont pas été sollicités ; "
                              "consultez l'éventuel délai Retry-After dans le diagnostic.")
            final_status = "partial" if job.publications else "failed"
        if not links and job.search_errors:
            final_status = "failed"
        elif args.limit is not None and len(links) < args.limit and not job.settings.second_hashtag:
            final_message += f" La recherche a fourni {len(links)} lien(s), pour un objectif de {args.limit}."
        if job.reprise:
            if job.settings.source_collecte == "presse":
                from collecte.suivi_sources import (
                    etablir_bilan_medias, medias_a_reprendre)
                bilan_actuel = etablir_bilan_medias(
                    job.settings.sources, job.journal,
                    source_en_cours=job.source_en_cours_id, termine=True)
                encore_a_traiter = medias_a_reprendre(bilan_actuel)
                nom_source = "média(s)"
            else:
                from collecte.suivi_hashtags import (
                    etablir_bilan_hashtags, hashtags_a_reprendre)
                bilan_actuel = etablir_bilan_hashtags(
                    job.settings.hashtags, job.settings.variantes_accents,
                    job.journal, source_en_cours=job.source_en_cours_id,
                    termine=True, collecte_id=job.id)
                encore_a_traiter = hashtags_a_reprendre(bilan_actuel)
                nom_source = "hashtag(s)"
            if encore_a_traiter:
                final_message += (
                    f" Reprise du même corpus : {len(encore_a_traiter)} "
                    f"{nom_source} restent à parcourir ou sont en erreur.")
                if final_status == "completed":
                    final_status = "partial"
            elif (final_status == "partial" and not (
                    job.errors or job.search_errors or limitation_research
                    or limitation_tiktok or limitation_budget
                    or limitation_commentaires_research or limitation_abonnes_research)):
                # Les diagnostics de l'ancienne exécution ne doivent pas
                # maintenir le lot comme partiel après leur résolution.
                final_status = "completed"
                final_message += " Toutes les sources prévues ont été parcourues."
    except Stopped:
        job.attente_validation_research = False
        final_status, final_message = "stopped", "Collecte arrêtée. " + ((job.cause_arret or {}).get("explication") or "Cause de l’arrêt non renseignée.") + " Les textes déjà obtenus restent téléchargeables."
    except scraper.WebDriverException as erreur:
        code = "erreur_session" if scraper.est_erreur_session(erreur) else "erreur_navigateur"
        job.diagnostics.append({"code": code, "exception": type(erreur).__name__})
        final_message = ("La session Selenium a été perdue. Relancez la collecte pour ouvrir une nouvelle session."
                         if code == "erreur_session" else "Le navigateur TikTok n’a pas pu poursuivre. Les résultats déjà collectés sont conservés.")
    except RuntimeError:
        final_message = "Aucune publication accessible pour la source choisie. Consultez le détail des sources et vérifiez que les publications sont visibles dans TikTok avant de continuer."
        if len(job.journal) == 1 and job.journal[0].get("rapport", {}).get("diagnostic", {}).get("code") == "erreur_tiktok":
            final_message = job.journal[0]["source"] + " : " + job.journal[0]["message"]
    except Exception:
        # Ne pas journaliser les réponses brutes du navigateur.
        LOG.error("Échec de la collecte %s", job.id)
        final_message = "La connexion au navigateur a échoué. Les textes déjà obtenus sont conservés. Réessayez ou contactez l’administrateur."
    finally:
        contexte_mp4 = {}
        if (job.settings.telecharger_mp4 and job.records and connexion is not None
                and not limitation_tiktok and not limitation_budget and not job.stop.is_set()):
            try:
                from telechargement_videos import capturer_contexte_anonyme
                contexte_mp4 = capturer_contexte_anonyme(connexion.obtenir_navigateur())
            except Exception:
                pass
        if connexion is not None:
            # Ne pas conserver les identifiants d'un utilisateur après la collecte.
            if getattr(connexion, "moteur_collecte", None) == "research":
                connexion.research_credentiels = None
            if getattr(connexion, "moteur_collecte", None) == "tikhub":
                connexion.tikhub_cle = None
            if getattr(connexion, "moteur_collecte", None) == "apify":
                connexion.apify_cle = None
            try:
                connexion.fermer()
            except scraper.WebDriverException:
                LOG.warning("Fermeture du navigateur impossible pour %s", job.id)
        # Les valeurs restent en mémoire uniquement durant le job actif.
        job.settings.research_client_key = None
        job.settings.research_client_secret = None
        job.settings.tikhub_api_key = None
        job.settings.apify_api_token = None
        job.settings.cookies_tiktok = None
        try:
            job.save()
        except OSError:
            LOG.exception("Écriture de l’export impossible")
            final_status, final_message = "failed", "Le serveur n’a pas pu enregistrer le fichier texte."
        if (job.settings.telecharger_mp4 and job.records
                and not limitation_tiktok and not limitation_budget and not job.stop.is_set()):
            try:
                final_message += " " + telecharger_mp4_collecte(job, contexte_mp4)
                if job.stop.is_set():
                    final_status = "stopped"
            except Exception:
                # Garder les textes et finaliser l’archive même si ce module échoue.
                LOG.error("Téléchargement MP4 interrompu pour %s", job.id)
                final_message += " Téléchargement MP4 interrompu ; les textes sont conservés."
            finally:
                contexte_mp4.clear()
        if job.base and (job.settings.source_collecte != "presse"
                         or job.publications or job.settings.collecter_republications_research
                         or job.settings.profils_medias_variables):
            try:
                from corpus.construction import construire_exports
                from corpus.export_zip import exporter_zip
                job.base.enregistrer(job.id, job.publications, job.commentaires)
                job.base.terminer_session(job.id, final_status)
                from stockage.historique import ajouter_evenement
                for evenement in job.journal: ajouter_evenement(job.base,job.id,evenement)
                construire_exports(job.directory, job.publications, job.commentaires,
                    {"session": job.id, "statut": final_status, "parametres": job.settings.model_dump(),
                     "compteurs_collecte": job.snapshot()["compteurs_collecte"], "evenements": job.journal,
                     "diagnostics": job.diagnostics}, texte_source=job.path,
                     republications=(job.republications
                                     if job.settings.collecter_republications_research
                                     else None),
                     inclure_commentaires_txt=job.settings.inclure_commentaires_txt,
                     profils_medias=(job.profils_medias if
                                     job.settings.profils_medias_variables else None),
                     profils_medias_variables=job.settings.profils_medias_variables,
                     profils_medias_classes=job.settings.profils_medias_classes)
                if job.settings.source_collecte == "presse":
                    bilan = etablir_bilan_medias(
                        job.settings.sources, job.journal,
                        source_en_cours=job.source_en_cours_id, termine=True)
                    (job.directory / "bilan_medias.csv").write_bytes(
                        exporter_bilan_medias_csv(bilan))
                elif job.settings.source_collecte == "hashtags":
                    bilan = etablir_bilan_hashtags(
                        job.settings.hashtags, job.settings.variantes_accents,
                        job.journal, source_en_cours=job.source_en_cours_id,
                        termine=True, collecte_id=job.id)
                    (job.directory / "bilan_hashtags.csv").write_bytes(
                        exporter_bilan_hashtags_csv(bilan))
                # Le mode Profils conserve les vidéos découvertes sans légende.
                # Le mode Presse n'archive QUE des publications réellement lues
                # et jamais une référence brute issue d'un embed ou d'une API 429.
                if job.settings.source_collecte == "comptes":
                    from analyse_desordre.sources import construire_sources_visuelles
                    complement = construire_sources_visuelles(
                        unique_links.values(), job.publications
                    )
                    (job.directory / "sources_visuelles.json").write_text(
                        json.dumps(complement, ensure_ascii=False), encoding="utf-8"
                    )
                exporter_zip(
                    job.directory, job.directory / "archive.zip",
                    inclure_mp4=job.settings.telecharger_mp4,
                    commentaires_csv_uniquement=(
                        job.settings.collecter_commentaires
                        and not job.settings.inclure_commentaires_txt))
                job.archive_prete = True
            except Exception:
                LOG.exception("Export enrichi impossible")
                final_message += " L’archive enrichie n’a pas pu être finalisée ; le TXT reste disponible."
        if job.profils_medias:
            reussis = sum(
                fiche["statut_profil"] == "ok" for fiche in job.profils_medias)
            libelle_profils = (
                "Profils médias" if job.settings.source_collecte == "presse"
                else "Profils auteurs")
            final_message += (
                f" {libelle_profils} : {reussis}/{len(job.profils_medias)} "
                "compte(s) renseigné(s) ; consultez profils_medias.csv "
                "pour les valeurs exactes et les absences.")
            if final_status == "failed" and reussis and job.archive_prete:
                # La collecte des vidéos est vide, mais les profils constituent
                # des résultats scientifiques réels à conserver.
                final_status = "partial"
        # Ne signaler la fin au navigateur qu'une fois les tentatives
        # d'archivage PostgreSQL et historique local effectuées.
        job.update(status=final_status, message=final_message)
        try:
            # Archiver aussi les vidéos dont les légendes ont été écartées.
            job.sauvegarder_postgres()
            job.sauvegarder_historique()
        finally:
            job.update(busy=False, finished=time.monotonic(), frame=b"")
        if job.settings.sauvegarde_progressive:
            try:
                job.sauvegarder_point(final_status)
            except (OSError, ValueError, TypeError):
                LOG.exception("Sauvegarde de récupération finale impossible pour %s",job.id)


def telecharger_mp4_collecte(job, contexte_anonyme=None):
    """Traiter les publications retenues une par une, après la fermeture de Selenium."""
    from telechargement_videos import telecharger_video, resultat_video
    debut = time.monotonic()
    volume = 0
    resultats = {}
    with job.lock:
        publications = list(job.records)
    for numero, publication in enumerate(publications, 1):
        identifiant = str(publication["id"])
        job.update(status="downloading", message=f"Téléchargement MP4 {numero}/{len(publications)} — textes déjà disponibles…")
        if identifiant in resultats:
            resultat = resultats[identifiant]
        elif job.stop.is_set():
            resultat = resultat_video(publication, "arrete")
        elif time.monotonic() - debut >= 900 or volume >= 2 * 1024**3:
            resultat = resultat_video(publication, "limite_lot")
        else:
            maximum_mo = min(256, (2 * 1024**3 - volume) // 1024**2)
            if maximum_mo < 1:
                resultat = resultat_video(publication, "limite_lot")
            else:
                try:
                    resultat = telecharger_video(publication, job.directory / "videos", arreter=job.stop.is_set,
                        taille_max_mo=maximum_mo, delai_max_s=min(120, max(1, 900-(time.monotonic()-debut))),
                        reserve_mo=512 + 2 * (volume // 1024**2 + maximum_mo), contexte_anonyme=contexte_anonyme)
                    if resultat.get("video_fichier"):
                        volume += (job.directory / resultat["video_fichier"]).stat().st_size
                except Exception:
                    resultat = resultat_video(publication, "erreur")
        resultats[identifiant] = resultat
        with job.lock:
            publication.update(resultat)
    recuperes = sum(bool(r.get("video_fichier")) for r in resultats.values())
    return f"MP4 : {recuperes}/{len(resultats)} vidéo(s) disponible(s) dans l’archive. Voir le bilan MP4."


class ProgrammerResearch(BaseModel):
    """Programmation Research ; le corps des paramètres conserve son modèle existant."""
    parametres: StartRequest
    debut_execution: str
    fin_execution: str

    @field_validator("debut_execution", "fin_execution")
    @classmethod
    def verifier_date_programme(cls, valeur):
        try:
            date.fromisoformat(valeur)
        except ValueError as erreur:
            raise ValueError("Date au format AAAA-MM-JJ attendue.") from erreur
        return valeur


class Manager:
    def __init__(self, data_dir=None, runner=execute_job, max_jobs=None):
        self.data_dir = Path(data_dir or os.getenv("DATA_DIR", str(scraper.BASE_DIR / "data")))
        self.max_jobs = max_jobs or max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
        self.retention = max(60, int(os.getenv("RESULT_TTL_SECONDS", "3600")))
        self.retention_points = max(3600, int(os.getenv("CHECKPOINT_TTL_SECONDS", "604800")))
        self.idle_timeout = max(60, int(os.getenv("IDLE_TIMEOUT_SECONDS", "300")))
        self.max_duration = max(60, int(os.getenv("JOB_TIMEOUT_SECONDS", "1800")))
        self.runner = runner
        self.jobs = {}
        # Un identifiant éphémère permet de détecter une autre instance
        # Coolify derrière le proxy, ou le redémarrage du moteur.
        self.instance_id = secrets.token_hex(12)
        self.lock = threading.RLock()
        self.closed = threading.Event()
        self.reaper = None
        from stockage.collectes_research import reprendre_apres_redemarrage
        reprendre_apres_redemarrage(self.data_dir)

    def _executer_lot_research(self, job, plan_id):
        """Exécuter un lot journalier, puis archiver ses résultats sans secrets."""
        from stockage.collectes_research import enregistrer_lot
        try:
            self.runner(job)
        except Exception:
            LOG.exception("Lot Research programmé interrompu : %s", plan_id)
            job.update(status="failed", message="Échec du lot Research ; reprise planifiée.",
                       busy=False, finished=time.monotonic())
        finally:
            try:
                enregistrer_lot(self.data_dir, plan_id, job,
                               abouti=job.status == "completed" and not job.stop.is_set())
                # Archiver dans PostgreSQL après la validation du lot SQLite.
                from stockage.postgres_research import synchroniser_plan
                synchroniser_plan(self.data_dir, plan_id)
            except Exception:
                LOG.exception("Persistance du lot Research impossible : %s", plan_id)

    def programmer_research(self, proprietaire_historique, parametres, debut_execution, fin_execution):
        """Enregistrer la programmation, sans jamais stocker les Client secrets."""
        from collecte.researchapi import identifiants_disponibles
        from stockage.collectes_research import creer_plan, detail_plan, lister_plans
        if not parametres.nom_sauvegarde:
            raise HTTPException(422, "Le nom de la sauvegarde est obligatoire.")
        if not identifiants_disponibles():
            raise HTTPException(422, "Pour les reprises automatiques, configurez "
                "TIKTOK_RESEARCH_CLIENT_KEY et TIKTOK_RESEARCH_CLIENT_SECRET "
                "dans les variables d'environnement Coolify.")
        if parametres.moteur_actif != "research":
            raise HTTPException(422, "La programmation utilise uniquement Research API.")
        if not parametres.date_debut or not parametres.date_fin:
            raise HTTPException(422, "Précisez les dates des publications à rechercher.")
        if parametres.test_research_10_publications:
            raise HTTPException(422, "Désactivez le test sur 10 publications pour programmer une collecte.")
        if parametres.collecter_republications_research:
            raise HTTPException(422,
                "Les republications Research sont disponibles dans les collectes "
                "ponctuelles, pas encore dans les collectes programmées.")
        if parametres.profils_medias_variables:
            raise HTTPException(422,
                "Les métriques des comptes médias sont réservées aux collectes "
                "ponctuelles Research, pas aux collectes programmées.")
        if (parametres.telecharger_mp4 or parametres.inclure_texte_genere_ia
                or parametres.filtrer_texte_ia_tiktok):
            raise HTTPException(422, "La collecte Research programmée ne lance "
                "ni téléchargement MP4 ni navigation Selenium.")
        if len([p for p in lister_plans(self.data_dir, proprietaire_historique)
                if p["statut"] in ("programme", "en_cours", "suspendu")]) >= 3:
            raise HTTPException(409, "Trois collectes Research programmées sont déjà actives.")
        valeurs = parametres.model_dump()
        valeurs["collecte_research_complete"] = True
        try:
            identifiant = creer_plan(self.data_dir, proprietaire_historique,
                valeurs, debut_execution, fin_execution)
        except ValueError as erreur:
            raise HTTPException(422, str(erreur)) from erreur
        return detail_plan(self.data_dir, identifiant, proprietaire_historique)

    def traiter_plans_research(self):
        """Un seul lot actif à la fois, avec contrôle du quota UTC en SQLite."""
        from stockage.collectes_research import (
            clore_dates, candidats, reserver_lot, etat_quota)
        for plan_expire in clore_dates(self.data_dir):
            self.arreter_plan_research(plan_expire)
        if self.closed.is_set() or etat_quota(self.data_dir)["reste_local"] == 0:
            return
        with self.lock:
            if any(job.busy or job.video_busy for job in self.jobs.values()):
                return
            for plan in candidats(self.data_dir):
                # Respecter aussi la limite de concurrence existante.
                lot = reserver_lot(self.data_dir, plan["id"])
                if lot is None:
                    continue
                valeurs = lot["parametres"]
                valeurs.update(date_debut=lot["jour"], date_fin=lot["jour"],
                               collecte_research_complete=True,
                               test_research_10_publications=False,
                               collecter_commentaires=valeurs.get("collecter_commentaires", False))
                if lot["source_collecte"] == "presse":
                    valeurs["medias"] = [lot["source"]]
                elif lot["source_collecte"] == "comptes":
                    valeurs["comptes"] = [lot["source"]]
                try:
                    parametres = StartRequest.model_validate(valeurs)
                    job = Job(secrets.token_hex(32), parametres, self.data_dir)
                    job.plan_research_id = plan["id"]
                    job.limites_debug = {"duree_max_s": self.max_duration,
                                        "collecte_programmee": True}
                    self.jobs[job.id] = job
                    job.thread = threading.Thread(
                        target=self._executer_lot_research,
                        args=(job, plan["id"]), daemon=True)
                    job.thread.start()
                except Exception:
                    LOG.exception("Impossible de démarrer le lot Research %s", plan["id"])
                    from stockage.collectes_research import remettre_en_attente
                    remettre_en_attente(self.data_dir, plan["id"])
                break

    def arreter_plan_research(self, identifiant):
        """Interrompre le lot courant d'un programme suspendu ou arrêté."""
        with self.lock:
            for job in self.jobs.values():
                if job.plan_research_id == identifiant and job.busy:
                    job.demander_arret("utilisateur")

    def start(self, owner, settings, owner_historique=""):
        from collecte.quotas_exploitation import (
            max_publications, max_sources, max_commentaires
        )
        if settings.collecter_commentaires and settings.limite_commentaires > max_commentaires():
            raise HTTPException(422, f"Borne technique du moteur : "
                f"{max_commentaires()} commentaires par publication.")
        if (settings.limit is not None and settings.limit > max_publications()
                and settings.moteur_actif != "research"):
            raise HTTPException(422,
                f"Borne technique du moteur : {max_publications()} publications par source.")
        nombre_sources = (len(settings.medias) if settings.source_collecte=="presse"
                          else len(settings.comptes) if settings.source_collecte=="comptes"
                          else len(settings.hashtags))
        if settings.moteur_actif != "research" and nombre_sources > max_sources():
            # Pour les autres moteurs, conserver la garde technique existante.
            # En Research, seul l'inventaire valide la sélection : aucun
            # plafond local additionnel sur le nombre de comptes sélectionnés.
            raise HTTPException(422,
                f"Borne technique du moteur : {max_sources()} sources par collecte.")
        # Une base configurée doit être joignable avant de consommer le quota TikTok.
        # L'archivage sera ensuite automatiquement tenté en fin de collecte.
        from stockage.postgres_consultation import (
            adresse_configuree, verifier_disponibilite)
        if adresse_configuree():
            try:
                verifier_disponibilite()
            except RuntimeError as erreur:
                raise HTTPException(
                    503, "La base PostgreSQL n'est pas accessible. "
                    "Collecte non lancée pour éviter une sauvegarde perdue. "
                    "Vérifiez la ressource PostgreSQL dans Coolify.") from None
        with self.lock:
            if any(j.video_busy for j in self.jobs.values()):
                raise HTTPException(409, "Un traitement vidéo est en cours. Patientez avant une nouvelle collecte.")
            active = [job for job in self.jobs.values() if job.busy]
            if any(job.owner == owner for job in active):
                raise HTTPException(409, "Une collecte est déjà en cours dans votre session.")
            if len(active) >= self.max_jobs:
                raise HTTPException(409, "Le navigateur est occupé par une autre collecte. Réessayez dans quelques minutes.")
            job = Job(owner, settings, self.data_dir, owner_historique=owner_historique)
            job.limites_debug={"inactivite_max_s":self.idle_timeout,"duree_max_s":self.max_duration}
            if adresse_configuree() and not job.sauvegarder_postgres():
                raise HTTPException(
                    503, "La sauvegarde PostgreSQL initiale a échoué. "
                    "Collecte non lancée pour préserver votre corpus. "
                    + job.erreur_postgres)
            self.jobs[job.id] = job
            job.thread = threading.Thread(target=self.runner, args=(job,), daemon=True)
            job.thread.start()
            return job

    def reprendre_historique(self, owner, identifiant, cookie, payload):
        """Compléter la collecte et son identifiant PostgreSQL, sans nouveau corpus."""
        from collecte.reprise_collecte import (
            initialiser_donnees_reprise, lire_archive_json, preparer_reprise_medias)
        from stockage.historique_analyses import retrouver
        from stockage.postgres_consultation import (
            adresse_configuree, compter_publications_collecte,
            obtenir_nom_collecte, verifier_disponibilite)
        if not cookie:
            raise HTTPException(403, "Historique privé indisponible.")
        archive = retrouver(self.data_dir, identifiant, cookie)
        if archive is None:
            raise HTTPException(404, "Collecte absente de l'historique privé.")
        ligne, dossier, manifeste = archive
        from collecte.presse import filtrer_medias_archives
        parametres = filtrer_medias_archives(
            manifeste.get("parametres") or {})
        if parametres.get("source_collecte") != "presse":
            raise HTTPException(422, "La reprise par sources concerne les collectes Presse et médias.")
        if parametres.get("presse_moteur") != "research":
            raise HTTPException(422, "La reprise dans le même corpus est actuellement réservée à Research API.")
        if parametres.get("test_research_10_publications"):
            raise HTTPException(422, "Une collecte de test ne peut pas être prolongée.")
        if not adresse_configuree():
            raise HTTPException(503, "PostgreSQL doit être configuré pour reprendre le même corpus.")
        try:
            verifier_disponibilite()
            nom_pg = obtenir_nom_collecte(cookie, "collecte", identifiant)
        except ValueError:
            raise HTTPException(404,
                "La collecte d'origine est absente de PostgreSQL : aucune nouvelle collecte ne sera créée.") from None
        except RuntimeError:
            raise HTTPException(503, "PostgreSQL indisponible : reprise non lancée.") from None
        if nom_pg != (parametres.get("nom_sauvegarde") or nom_pg):
            raise HTTPException(409, "Le nom de la collecte PostgreSQL ne correspond plus à l'archive.")
        try:
            publications_archivees = lire_archive_json(
                dossier, "publications.json", obligatoire=True)
            if not isinstance(publications_archivees, list):
                raise ValueError("Format de publications.json invalide.")
            publications_sql = compter_publications_collecte(cookie, identifiant)
        except ValueError:
            raise HTTPException(409,
                "Archive et base d'origine inaccessibles : reprise bloquée pour protéger les données.") from None
        except RuntimeError:
            raise HTTPException(503,
                "Vérification PostgreSQL impossible : reprise non lancée.") from None
        if publications_sql > len(publications_archivees):
            raise HTTPException(409,
                "Reprise bloquée : PostgreSQL conserve "
                f"{publications_sql} publications, mais l'archive locale n'en contient "
                f"que {len(publications_archivees)}. "
                "Le corpus original est protégé. Exportez d'abord les données "
                "PostgreSQL pour reconstituer l'archive avant toute reprise.")
        try:
            journal = lire_archive_json(dossier, "journal.json", obligatoire=True)
        except ValueError:
            raise HTTPException(409, "Le journal d'origine est illisible ou absent.") from None
        if not isinstance(journal, dict) or not isinstance(journal.get("evenements"), list):
            raise HTTPException(409, "Le journal d'origine est absent : impossible de reprendre les sources.")
        credentials = {}
        for cle in ("research_client_key", "research_client_secret"):
            valeur = getattr(payload, cle, None)
            if valeur:
                credentials[cle] = valeur.get_secret_value()
        try:
            settings = StartRequest.model_validate({**parametres, **credentials})
        except ValueError:
            # Ne jamais inclure les secrets envoyés dans une erreur de validation.
            raise HTTPException(422,
                "Paramètres historiques invalides ou identifiants Research manquants.") from None
        try:
            selection, _ = preparer_reprise_medias(
                settings.sources, journal["evenements"], payload.medias,
                source_en_cours=manifeste.get("source_en_cours_id"))
        except ValueError as erreur:
            raise HTTPException(422, str(erreur)) from None
        with self.lock:
            if any(tache.busy or tache.video_busy for tache in self.jobs.values()):
                raise HTTPException(409, "Un traitement est déjà en cours sur le serveur.")
            existant = self.jobs.get(identifiant)
            if existant is not None and existant.owner != owner:
                raise HTTPException(403, "Collecte détenue par une autre session.")
            job = Job(owner, settings, self.data_dir,
                      identifiant=identifiant, archive_directory=dossier,
                      owner_historique=cookie, reprise=True)
            try:
                initialiser_donnees_reprise(job, dossier, manifeste, selection)
            except (ValueError, TypeError, OSError) as erreur:
                raise HTTPException(409, str(erreur)) from None
            job.journal.append({
                "reprise_collecte": True,
                "date": scraper.utc_now(),
                "medias_a_reprendre": list(selection),
                "publications_anterieures": len(job.publications),
                "traitees_anterieures": job.processed + job.reprise_decalage,
            })
            job.limites_debug = {
                "inactivite_max_s": self.idle_timeout,
                "duree_max_s": self.max_duration}
            self.jobs[identifiant] = job
            job.thread = threading.Thread(
                target=self.runner, args=(job,), daemon=True)
            job.thread.start()
            return job

    def reprendre_hashtags_historique(self, owner, identifiant, cookie, payload):
        """Reprendre les hashtags inachevés dans le même corpus PostgreSQL."""
        from collecte.reprise_collecte import (
            initialiser_donnees_reprise, lire_archive_json)
        from stockage.historique_analyses import retrouver
        from stockage.postgres_consultation import (
            adresse_configuree, compter_publications_collecte,
            obtenir_nom_collecte, verifier_disponibilite)
        if not cookie:
            raise HTTPException(403, "Historique privé indisponible.")
        archive = retrouver(self.data_dir, identifiant, cookie)
        if archive is None:
            raise HTTPException(404, "Collecte absente de l'historique privé.")
        _, dossier, manifeste = archive
        parametres = dict(manifeste.get("parametres") or {})
        if (parametres.get("source_collecte") != "hashtags"
                or parametres.get("hashtag_moteur") != "research"):
            raise HTTPException(
                422, "La reprise des hashtags exige une collecte Research API.")
        if parametres.get("test_research_10_publications"):
            raise HTTPException(422, "Le mode test de dix publications ne peut pas être repris.")
        if not adresse_configuree():
            raise HTTPException(503, "PostgreSQL doit être configuré pour reprendre le corpus.")
        try:
            verifier_disponibilite()
            nom_pg = obtenir_nom_collecte(cookie, "collecte", identifiant)
            nombre_pg = compter_publications_collecte(cookie, identifiant)
        except ValueError:
            raise HTTPException(
                404, "Collecte d'origine absente de PostgreSQL : reprise refusée.") from None
        except RuntimeError:
            raise HTTPException(503, "PostgreSQL indisponible : reprise non lancée.") from None
        if nom_pg != (parametres.get("nom_sauvegarde") or nom_pg):
            raise HTTPException(409, "Le nom de la collecte PostgreSQL ne correspond plus.")
        try:
            publications = lire_archive_json(
                dossier, "publications.json", obligatoire=True)
            journal = lire_archive_json(
                dossier, "journal.json", obligatoire=True)
        except ValueError:
            raise HTTPException(
                409, "Archive locale incomplète : reprise bloquée pour protéger le corpus.") from None
        if not isinstance(publications, list) or not isinstance(journal, dict):
            raise HTTPException(409, "Archive scientifique invalide.")
        if not isinstance(journal.get("evenements"), list):
            raise HTTPException(409, "Journal des hashtags absent.")
        if nombre_pg > len(publications):
            raise HTTPException(
                409, f"PostgreSQL contient {nombre_pg} publications, "
                f"mais l'archive locale n'en contient que {len(publications)}. "
                "Reprise bloquée pour protéger le corpus original.")
        credentials = {}
        for cle in ("research_client_key", "research_client_secret"):
            secret = getattr(payload, cle, None)
            if secret:
                credentials[cle] = secret.get_secret_value()
        # Les anciennes archives pouvaient omettre la fenêtre implicite
        # des 30 jours UTC. Retrouver la date initiale dans le journal pour
        # ne pas déplacer le corpus vers la date de la reprise.
        if not parametres.get("date_fin"):
            date_archive = ""
            for evenement in journal["evenements"]:
                if not isinstance(evenement, dict):
                    continue
                plage = (evenement.get("rapport") or {}).get("plage_research") or {}
                borne_fin = str(plage.get("fin") or "")
                if len(borne_fin) == 8 and borne_fin.isdigit():
                    date_archive = (borne_fin[:4] + "-" + borne_fin[4:6]
                                    + "-" + borne_fin[6:])
                    break
                date_evenement = str(evenement.get("date") or "")[:10]
                try:
                    date.fromisoformat(date_evenement)
                except ValueError:
                    continue
                date_archive = date_evenement
                break
            if not date_archive:
                raise HTTPException(
                    409, "Période de l'ancienne collecte inconnue : reprise "
                    "bloquée pour éviter un changement de corpus.")
            parametres["date_fin"] = date_archive
            if not parametres.get("date_debut"):
                parametres["date_debut"] = (
                    date.fromisoformat(date_archive)
                    - timedelta(days=29)).isoformat()
        try:
            settings = StartRequest.model_validate(
                {**parametres, **credentials},
                context={"reprise_historique": True})
        except ValueError:
            raise HTTPException(
                422, "Paramètres historiques invalides ou identifiants Research manquants.") from None
        try:
            selection, variantes, _ = preparer_reprise_hashtags(
                settings.hashtags, settings.variantes_accents,
                journal["evenements"], payload.hashtags,
                source_en_cours=manifeste.get("source_en_cours_id"))
        except ValueError as erreur:
            raise HTTPException(422, str(erreur)) from None
        with self.lock:
            if any(tache.busy or tache.video_busy for tache in self.jobs.values()):
                raise HTTPException(409, "Un traitement est déjà en cours sur le serveur.")
            ancien = self.jobs.get(identifiant)
            if ancien is not None and ancien.owner != owner:
                raise HTTPException(403, "Cette collecte appartient à une autre session.")
            job = Job(
                owner, settings, self.data_dir, identifiant=identifiant,
                archive_directory=dossier, owner_historique=cookie, reprise=True)
            try:
                initialiser_donnees_reprise(job, dossier, manifeste, [])
            except (ValueError, TypeError, OSError) as erreur:
                raise HTTPException(409, str(erreur)) from None
            job.hashtags_reprise = list(selection)
            job.sources_reprise_hashtags = list(variantes)
            job.journal.append({
                "reprise_hashtags": True,
                "date": scraper.utc_now(),
                "hashtags_a_reprendre": list(selection),
                "variantes_a_interroger": list(variantes),
                "publications_anterieures": len(job.publications),
            })
            job.limites_debug = {
                "inactivite_max_s": self.idle_timeout,
                "duree_max_s": self.max_duration}
            self.jobs[identifiant] = job
            job.thread = threading.Thread(
                target=self.runner, args=(job,), daemon=True)
            job.thread.start()
            return job

    def reouvrir_historique(self, owner, identifiant, cookie):
        from stockage.historique_analyses import retrouver
        recupere = retrouver(self.data_dir, identifiant, cookie)
        if recupere is None:
            raise HTTPException(404, "Analyse introuvable ou expirée.")
        ligne, dossier, manifeste = recupere
        with self.lock:
            job = self.jobs.get(identifiant)
            if job is not None and (job.busy or job.video_busy) and job.owner != owner:
                raise HTTPException(409, "Cette collecte est active dans une autre session.")
            if job is not None and job.owner == owner and (not job.historique or job.busy or job.reprise):
                return job
            from collecte.presse import filtrer_medias_archives
            params = StartRequest.model_validate(
                filtrer_medias_archives(manifeste["parametres"]),
                context={"consultation_historique": True})
            job = Job(owner, params, self.data_dir, identifiant=identifiant,
                      archive_directory=dossier, owner_historique=cookie)
            def charger(nom):
                chemin = dossier / nom
                return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else []
            job.publications=charger("publications.json")
            job.records=[p for p in job.publications if p.get("retenue")]
            job.commentaires=charger("commentaires.json")
            job.republications=charger("republications.json")
            job.profils_medias=charger("profils_medias.json")
            journal_archive = charger("journal.json")
            if isinstance(journal_archive, dict):
                job.journal = list(journal_archive.get("evenements") or [])
                anciens_compteurs = journal_archive.get("compteurs_collecte") or {}
                if isinstance(anciens_compteurs, dict):
                    # Restaurer les indicateurs observés, sans les confondre avec
                    # les nouvelles requêtes effectuées par une reprise.
                    job.discovered = int(anciens_compteurs.get("retenues") or 0)
                    job.exportees = int(
                        anciens_compteurs.get("exportees")
                        or sum(bool(p.get("description")) for p in job.records))
            job.processed=int(manifeste.get("traites",0))
            job.source_en_cours_id = manifeste.get("source_en_cours_id")
            job.busy=False
            job.status=ligne["statut"]
            job.archive_prete=True
            job.finished=time.monotonic()
            self.jobs[identifiant]=job
            return job

    def get(self, owner, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None or job.owner != owner:
                raise HTTPException(404, "Cette collecte est introuvable ou a expiré.")
            job.last_seen = time.monotonic()
            return job

    def latest(self, owner):
        with self.lock:
            jobs = [j for j in self.jobs.values() if j.owner == owner]
            if not jobs:
                return None
            job = max(jobs, key=lambda j: j.created)
            job.last_seen = time.monotonic()
            return job

    def cleanup(self):
        now = time.monotonic()
        with self.lock:
            for job in list(self.jobs.values()):
                if (job.busy or job.video_busy) and not job.plan_research_id:
                    from ticket_gate import verifier_session_active
                    if not verifier_session_active(job.owner):
                        job.demander_arret("acces_inactif")
                        job.video_stop.set()
                if job.busy:
                    job.limites_debug={'inactivite_max_s':self.idle_timeout,'duree_max_s':self.max_duration}
                    if now-job.created > self.max_duration:
                        job.demander_arret('duree_maximale')
                    elif not job.plan_research_id and now-job.last_seen > self.idle_timeout:
                        job.demander_arret('inactivite')
                if job.video_busy and (now-job.last_seen>self.idle_timeout or now-job.video_debut>7200):
                    job.video_stop.set()
                if session_terminee_inactive(job, now, self.retention):
                    # Une collecte terminée et encore consultée reste ouverte.
                    # Le nettoyage ne concerne que les sessions réellement inactives.
                    self.jobs.pop(job.id)
                    if not job.historique:
                        shutil.rmtree(job.directory, ignore_errors=True)
                    if job.base: job.base.supprimer_session(job.id)
            if (self.data_dir / "scraptiktok.sqlite").exists():
                from stockage.nettoyage import nettoyer_sessions
                from stockage.base_donnees import BaseDonnees
                base = BaseDonnees(self.data_dir / "scraptiktok.sqlite")
                nettoyer_sessions(self.data_dir, base, self.retention, self.jobs)
            # Les sauvegardes optionnelles ont une durée de vie indépendante
            # des sessions temporaires, y compris après redémarrage.
            from stockage.sauvegarde_progressive import purger_points
            purger_points(self.data_dir, self.retention_points)
            from stockage.historique_analyses import purger as purger_historique
            purger_historique(self.data_dir)
            # Retire également les exports orphelins après un redémarrage.
            if self.data_dir.exists():
                for directory in self.data_dir.iterdir():
                    if (directory.is_dir() and len(directory.name) == 32
                            and directory.name not in self.jobs
                            and time.time() - directory.stat().st_mtime > self.retention):
                        shutil.rmtree(directory, ignore_errors=True)

    def maintain(self):
        while not self.closed.wait(15):
            self.cleanup()
            try:
                self.traiter_plans_research()
            except Exception:
                LOG.exception("Planificateur Research temporairement indisponible.")

    def shutdown(self):
        self.closed.set()
        with self.lock:
            jobs = list(self.jobs.values())
            for job in jobs:
                job.demander_arret("arret_serveur")
                job.video_stop.set()
        deadline = time.monotonic() + 25
        for job in jobs:
            if job.video_thread:
                job.video_thread.join(timeout=5)
            if job.thread:
                job.thread.join(timeout=max(0, deadline - time.monotonic()))


class OptionsDesordre(BaseModel):
    telecharger_manquants: bool = False
    frequence: float = Field(default=10., ge=1, le=60)
    dimension: int = Field(default=320, ge=64, le=1280)
    duree_max: float = Field(default=10., gt=0, le=3600)


def executer_desordre(job, options, dossier):
    """Partager la réservation CPU et l'arrêt des analyses sans changer leurs algorithmes."""
    from analyse_desordre.service import ecrire_etat, lire_etat
    processus = None
    try:
        with (job.directory/'desordre.log').open('w') as journal:
            processus = subprocess.Popen([sys.executable, '-m', 'analyse_desordre.service',
                '--session', str(job.directory), '--dossier', dossier,
                '--frequence', str(options.frequence), '--dimension', str(options.dimension),
                '--duree-max', str(options.duree_max)]+(['--telecharger-manquants'] if options.telecharger_manquants else []), cwd=scraper.BASE_DIR,
                stdout=journal, stderr=subprocess.STDOUT, start_new_session=True)
            job.video_process = processus
            limite = time.monotonic()+7200
            while processus.poll() is None:
                if job.video_stop.wait(.5) or time.monotonic()>limite:
                    os.killpg(processus.pid,signal.SIGTERM)
                    try: processus.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(processus.pid,signal.SIGKILL); processus.wait()
                    try: os.killpg(processus.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    ecrire_etat(job.directory,{**lire_etat(job.directory),'statut':'interrompu','etape':'Analyse arrêtée'})
                    break
            else:
                if processus.returncode:
                    ecrire_etat(job.directory,{**lire_etat(job.directory),'statut':'echec',
                        'erreur':'Le processus a échoué. Consultez desordre.log sur le serveur.'})
    except Exception:
        LOG.exception('Analyse du désordre interrompue')
        ecrire_etat(job.directory,{'statut':'echec','erreur':'Impossible de démarrer le calcul sur le serveur.'})
    finally:
        if processus is not None and processus.poll() is None:
            os.killpg(processus.pid,signal.SIGKILL); processus.wait()
        # Un arrêt forcé ne doit pas laisser les liens MP4 de préparation dans les exports.
        for temporaire in job.directory.glob('desordre_sources_*'):
            if temporaire.is_dir() and not temporaire.is_symlink(): shutil.rmtree(temporaire,ignore_errors=True)
        job.update(video_busy=False,video_process=None,finished=time.monotonic())
        job.sauvegarder_historique()


def create_app(manager=None):
    manager = manager or Manager()

    @asynccontextmanager
    async def lifespan(app):
        manager.reaper = threading.Thread(target=manager.maintain, daemon=True)
        manager.reaper.start()

        # Appliquer la migration additive dès le démarrage, sans bloquer
        # le service HTTP ni exiger le lancement d'une nouvelle collecte.
        from stockage.postgres_consultation import adresse_configuree
        if adresse_configuree():
            def initialiser_schema_postgres():
                """Préparer les colonnes exploitables sans exposer le DSN."""
                try:
                    from stockage.postgres_consultation import verifier_disponibilite
                    verifier_disponibilite()
                except Exception as erreur:
                    LOG.warning(
                        "Initialisation du schéma PostgreSQL impossible : %s",
                        type(erreur).__name__)
            threading.Thread(
                target=initialiser_schema_postgres,
                name="scraptiktok-schema-postgres",
                daemon=True,
            ).start()
        yield
        manager.shutdown()

    app = FastAPI(title="ScrapTikTok", lifespan=lifespan, docs_url=None, redoc_url=None)
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(RequestValidationError)
    async def erreur_validation_sans_secrets(request, erreur):
        """Ne jamais renvoyer le corps d'une requête contenant des cookies."""
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": e["loc"], "msg": e["msg"], "type": e["type"]}
            for e in erreur.errors()]})
    from interface.passerelle import CompressionInterface, ressource_interface_versionnee
    app.add_middleware(CompressionInterface)
    app.state.manager = manager

    @app.middleware("http")
    async def security(request, call_next):
        password = os.getenv("APP_ACCESS_PASSWORD", "")
        if password and request.url.path != "/healthz":
            expected_user = os.getenv("APP_ACCESS_USER", "scraptiktok")
            try:
                scheme, encoded = request.headers.get("authorization", "").split(" ", 1)
                user, secret = base64.b64decode(encoded, validate=True).decode().split(":", 1)
                accepted = scheme.lower() == "basic" and hmac.compare_digest(user.encode(), expected_user.encode()) and hmac.compare_digest(secret.encode(), password.encode())
            except (ValueError, UnicodeError):
                accepted = False
            if not accepted:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="ScrapTikTok"'})
        if request.method == "POST" and not request.url.path.startswith("/_stcore/"):
            # Les requêtes de mutation viennent uniquement de notre propre page.
            if request.headers.get("x-scraptiktok") != "1":
                return JSONResponse({"detail": "Requête non autorisée."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        # Les scripts/styles portent une empreinte qui change avec leur contenu.
        # Le HTML, les sessions, les exports et les captures restent sans cache.
        if (request.method in {"GET", "HEAD"} and response.status_code in {200, 304}
                and ressource_interface_versionnee(request.url.path)):
            response.headers["Cache-Control"] = "private, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-store"
        if not request.url.path.startswith(("/api/", "/controle", "/healthz", "/static/controle.css", "/static/navigateur.js", "/static/controle.js")):
            response.headers["Content-Security-Policy"] = "frame-ancestors 'self'; base-uri 'self'"
            return response
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'self'"
        return response

    def owner(request):
        session = request.cookies.get(COOKIE, "")
        if len(session) != 64 or any(c not in "0123456789abcdef" for c in session):
            raise HTTPException(401, "Rechargez la page pour ouvrir une session.")
        return session

    def owner_historique(request):
        cookie=request.cookies.get(HISTORIQUE_COOKIE,"")
        if not re.fullmatch(r"[a-f0-9]{64}",cookie):
            raise HTTPException(401,"Historique inaccessible : rechargez la page d’accueil.")
        return cookie

    @app.get("/api/collecte/limites")
    def lire_limites_exploitation(request: Request):
        owner(request)
        from collecte.quotas_exploitation import (
            max_publications, max_sources, max_commentaires,
            max_defilements, max_pages_api, etat_budget
        )
        return {
            "maximum_publications_par_source": max_publications(),
            "maximum_sources_par_collecte": max_sources(),
            "maximum_commentaires_par_video": max_commentaires(),
            "maximum_defilements": max_defilements(),
            "maximum_pages_api_par_source": max_pages_api(),
            "budget_api_presse": etat_budget(),
        }

    @app.get("/api/base-donnees")
    def lister_postgres(request: Request, filtre: str = ""):
        """Lister toutes les sauvegardes appartenant au cookie privé."""
        from stockage.postgres_consultation import lister_sauvegardes, adresse_configuree
        propriete = owner_historique(request)
        if not adresse_configuree():
            return {"configure": False, "sauvegardes": []}
        try:
            return {"configure": True, "sauvegardes": lister_sauvegardes(propriete, filtre)}
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None

    @app.post("/api/base-donnees/importer-historique")
    def importer_historique_postgres(request: Request):
        """Importer uniquement les archives possédées par le navigateur courant."""
        exiger_ticket(request)
        from stockage.postgres_consultation import importer_historique
        try:
            return importer_historique(manager.data_dir, owner_historique(request))
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None

    @app.post("/api/base-donnees/{type_sauvegarde}/{identifiant}/supprimer")
    def supprimer_archive_postgres(
            type_sauvegarde: str, identifiant: str,
            payload: SupprimerCollectePostgresPayload, request: Request):
        """Supprimer uniquement l'enregistrement d'une collecte autorisée."""
        exiger_ticket(request)
        utilisateur = owner_historique(request)
        # Ne pas supprimer une archive susceptible d'être réécrite par
        # une collecte encore active ou un programme Research en cours.
        if type_sauvegarde == "collecte":
            try:
                tache = manager.get(owner(request), identifiant)
            except HTTPException:
                tache = None
            if tache is not None and (tache.busy or tache.video_busy):
                raise HTTPException(
                    409, "Arrêtez la collecte avant de supprimer son archive.")
        elif type_sauvegarde == "research":
            # Une copie PostgreSQL peut subsister alors que SQLite a expiré :
            # ne jamais créer une nouvelle base SQLite en contrôlant son état.
            programme = None
            if (manager.data_dir / "collectes_research.sqlite3").is_file():
                from stockage.collectes_research import detail_plan
                programme = detail_plan(manager.data_dir, identifiant, utilisateur)
            if programme and programme.get("statut") in ("programme", "en_cours"):
                raise HTTPException(
                    409, "Arrêtez le programme Research avant de supprimer "
                         "sa copie PostgreSQL, sinon elle sera recréée.")
        from stockage.postgres_consultation import supprimer_collecte_postgres
        try:
            return supprimer_collecte_postgres(
                utilisateur, type_sauvegarde, identifiant,
                payload.nom_confirmation)
        except ValueError as erreur:
            raise HTTPException(400, str(erreur)) from None
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None

    @app.get("/api/base-donnees/{type_sauvegarde}/{identifiant}/archive.zip")
    def telecharger_archive_postgres(
            type_sauvegarde: str, identifiant: str, request: Request):
        """Télécharger les publications et commentaires PostgreSQL en un ZIP."""
        from stockage.export_zip_postgres import construire_archive_postgres
        # Pour une collecte encore active en mémoire, récupérer aussi
        # son archive ZIP d'origine et les éventuels MP4 disponibles.
        archive_active = None
        try:
            tache = manager.get(owner(request), identifiant)
        except HTTPException:
            tache = None
        if (tache is not None and not tache.busy and not tache.video_busy
                and tache.archive_prete
                and tache.owner_historique == owner_historique(request)):
            chemin = tache.directory / "archive.zip"
            if chemin.is_file() and not chemin.is_symlink():
                archive_active = chemin
        try:
            fichier, nom = construire_archive_postgres(
                owner_historique(request), type_sauvegarde, identifiant,
                dossier_local=manager.data_dir,
                archive_active=archive_active)
        except ValueError:
            raise HTTPException(404, "Collecte PostgreSQL introuvable.") from None
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None
        return StreamingResponse(
            iter(lambda: fichier.read(65536), b""),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"
            },
            background=BackgroundTask(fichier.close),
        )

    @app.get("/api/base-donnees/{type_sauvegarde}/{identifiant}/{categorie}")
    def consulter_postgres(type_sauvegarde: str, identifiant: str, categorie: str,
                          request: Request, filtre: str = "", limite: int = 100,
                          decalage: int = 0):
        """Consulter une page de publications ou de commentaires privés."""
        from stockage.postgres_consultation import donnees_sauvegarde
        try:
            return donnees_sauvegarde(owner_historique(request), type_sauvegarde,
                                      identifiant, categorie, filtre, limite, decalage)
        except ValueError:
            raise HTTPException(404, "Sauvegarde ou catégorie introuvable.") from None
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None

    @app.get("/api/base-donnees/{type_sauvegarde}/{identifiant}/export/{nom}")
    def exporter_postgres(type_sauvegarde: str, identifiant: str, nom: str,
                         request: Request):
        """Exporter un corpus PostgreSQL complet en CSV ou JSON."""
        from stockage.postgres_consultation import (
            exporter_sauvegarde, obtenir_nom_collecte)
        if nom not in ("publications.csv", "commentaires.csv",
                       "publications.json", "commentaires.json"):
            raise HTTPException(404, "Format inconnu.")
        categorie, format_ = nom.rsplit(".", 1)
        propriete = owner_historique(request)
        try:
            nom_collecte = obtenir_nom_collecte(
                propriete, type_sauvegarde, identifiant)
            morceaux = exporter_sauvegarde(
                propriete, type_sauvegarde, identifiant,
                categorie, format_)
        except ValueError:
            raise HTTPException(404, "Sauvegarde introuvable.") from None
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None
        nom_fichier = nom_fichier_telechargement(
            nom_collecte, categorie, format_)
        return StreamingResponse(morceaux,
            media_type=("text/csv; charset=utf-8" if format_ == "csv"
                        else "application/json; charset=utf-8"),
            headers=entete_telechargement(nom_fichier))

    @app.post("/api/base-donnees/{identifiant}/synchroniser")
    def synchroniser_collecte_postgres(identifiant: str, request: Request):
        """Rejouer l'archivage d'une collecte terminée."""
        exiger_ticket(request)
        job = manager.get(owner(request), identifiant)
        if job.busy or job.video_busy:
            raise HTTPException(409, "La collecte doit être terminée.")
        if job.owner_historique != owner_historique(request):
            raise HTTPException(403, "Cette sauvegarde ne vous appartient pas.")
        if not job.sauvegarder_postgres():
            raise HTTPException(503, job.erreur_postgres)
        return {"statut": "synchronise",
                "publications": len(job.publications),
                "commentaires": len(job.commentaires)}

    @app.get("/api/research/plans")
    def lister_programmes_research(request: Request):
        """Programmes privés et compteurs du budget local."""
        from stockage.collectes_research import lister_plans, etat_quota
        return {"plans": lister_plans(manager.data_dir, owner_historique(request)),
                "quota": etat_quota(manager.data_dir)}

    @app.post("/api/research/plans", status_code=202)
    def programmer_research(payload: ProgrammerResearch, request: Request):
        exiger_ticket(request)
        return manager.programmer_research(
            owner_historique(request), payload.parametres,
            payload.debut_execution, payload.fin_execution)

    @app.post("/api/research/plans/{identifiant}/{action}")
    def agir_programme_research(identifiant: str, action: str, request: Request):
        from stockage.collectes_research import changer_etat, detail_plan
        if action not in ("suspendre", "reprendre", "arreter"):
            raise HTTPException(404, "Action inconnue.")
        propriete = owner_historique(request)
        try:
            statut = changer_etat(manager.data_dir, identifiant, propriete, action)
        except ValueError:
            raise HTTPException(404, "Programme introuvable.")
        if statut in ("suspendu", "arrete"):
            manager.arreter_plan_research(identifiant)
        return detail_plan(manager.data_dir, identifiant, propriete)

    @app.post("/api/research/plans/{identifiant}/synchroniser-postgres")
    def synchroniser_programme_postgres(identifiant: str, request: Request):
        """Rejouer l'archivage PostgreSQL d'un programme autorisé."""
        exiger_ticket(request)
        from stockage.collectes_research import detail_plan
        from stockage.postgres_research import synchroniser_plan
        if detail_plan(manager.data_dir, identifiant, owner_historique(request)) is None:
            raise HTTPException(404, "Programme introuvable.")
        try:
            return synchroniser_plan(manager.data_dir, identifiant, exiger_configuration=True)
        except RuntimeError as erreur:
            raise HTTPException(503, str(erreur)) from None

    @app.get("/api/research/plans/{identifiant}/journal")
    def lire_journal_research(identifiant: str, request: Request):
        from stockage.collectes_research import journal_plan
        valeurs = journal_plan(manager.data_dir, identifiant, owner_historique(request))
        if valeurs is None:
            raise HTTPException(404, "Programme introuvable.")
        return {"journal": valeurs}

    @app.get("/api/research/plans/{identifiant}/export/{format_}")
    def exporter_programme_research(identifiant: str, format_: str, request: Request):
        from stockage.collectes_research import exporter
        if format_ not in ("json", "csv", "commentaires.csv", "txt", "zip", "sqlite3"):
            raise HTTPException(404, "Format inconnu.")
        contenu = exporter(manager.data_dir, identifiant, owner_historique(request), format_)
        if contenu is None:
            raise HTTPException(404, "Programme introuvable.")
        media = {
            "json": "application/json", "csv": "text/csv",
            "commentaires.csv": "text/csv", "txt": "text/plain",
            "zip": "application/zip", "sqlite3": "application/vnd.sqlite3",
        }[format_]
        # Associer chaque fichier à son nom de sauvegarde, même lors d'un export ultérieur.
        from stockage.collectes_research import detail_plan
        plan = detail_plan(manager.data_dir, identifiant, owner_historique(request))
        libelle = (plan or {}).get("nom_sauvegarde") or "research"
        nom_nettoye = re.sub(r"[^\w-]+", "_", libelle, flags=re.UNICODE).strip("_")[:80] or "research"
        nom_fichier = (
            f"{nom_nettoye}.zip" if format_ == "zip"
            else f"{nom_nettoye}_{identifiant[:8]}.{format_}"
        )
        return Response(contenu, media_type=media, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom_fichier)}"})

    @app.get("/api/presse/limitation")
    def statut_limitation_presse(request: Request):
        """État partagé de la pause 429, sans cookie TikTok ni identifiant."""
        owner(request)
        from collecte.tiktok_limitation import consulter_limitation
        return consulter_limitation()

    @app.get("/healthz")
    def health():
        import urllib.request
        try:
            with urllib.request.urlopen("http://127.0.0.1:" + os.getenv("STREAMLIT_PORT", "8502") + "/_stcore/health",timeout=2): pass
        except OSError: raise HTTPException(503,"Interface Streamlit indisponible.")
        from collecte.presse_api import VERSION_PRESSE
        from collecte.presse_research import VERSION_RESEARCH, identifiants_disponibles
        return {"status": "ok", "version_presse": VERSION_PRESSE,
                "version_research": VERSION_RESEARCH,
                "research_configuree": identifiants_disponibles()}

    @app.get("/")
    @app.get("/controle")
    async def home(request: Request):
        if request.url.path == "/controle":
            response = FileResponse(scraper.BASE_DIR / "static" / "controle.html")
        else:
            response = await app.state.relayer_streamlit(request, "")
        if not request.cookies.get(COOKIE):
            response.set_cookie(COOKIE, secrets.token_hex(32), httponly=True, samesite="strict",
                                secure=os.getenv("COOKIE_SECURE", "0") == "1", max_age=86400)
        if not re.fullmatch(r"[a-f0-9]{64}",request.cookies.get(HISTORIQUE_COOKIE,"")):
            response.set_cookie(HISTORIQUE_COOKIE, secrets.token_hex(32), httponly=True,
                                samesite="strict", secure=os.getenv("COOKIE_SECURE","0")=="1",
                                max_age=400*86400)
        return response

    @app.post("/api/jobs/{job_id}/desordre", status_code=202)
    def lancer_desordre(job_id: str, options: OptionsDesordre, request: Request):
        """Lancement explicite réservé au propriétaire et au détenteur de l'accès actif."""
        exiger_ticket(request)
        job = manager.get(owner(request), job_id)
        from analyse_desordre.service import dependances_disponibles, ecrire_etat
        if not dependances_disponibles():
            raise HTTPException(409, "Dépendances OpenCV absentes : vérifiez les dépendances de Désordre visuel.")
        with manager.lock:
            if any(j.busy or j.video_busy for j in manager.jobs.values()):
                raise HTTPException(409, 'Une collecte ou une analyse est déjà en cours.')
            if not job.archive_prete or not (
                (job.directory/'publications.json').is_file()
                or (job.directory/'sources_visuelles.json').is_file()
            ):
                raise HTTPException(409, 'Effectuez d’abord une collecte enrichie.')
            from analyse_desordre.sources import inventaire_sources
            sources=inventaire_sources(job.directory)
            if not sources['mp4_locaux'] and not (options.telecharger_manquants and sources['mp4_telechargeables']):
                raise HTTPException(409, 'Aucun MP4 associé à la collecte. Activez le téléchargement des MP4 manquants si des URL TikTok sont disponibles.')
            dossier = 'desordre_'+secrets.token_hex(8)
            ecrire_etat(job.directory,{'statut':'en_cours','dossier':dossier,'terminees':0,'total':0,'etape':'Démarrage'})
            job.video_stop.clear()
            job.update(video_busy=True,video_debut=time.monotonic())
            job.video_thread=threading.Thread(target=executer_desordre,args=(job,options,dossier),daemon=True)
            job.video_thread.start()
        return job.snapshot()

    def dossier_desordre(job, etat):
        nom = etat.get('dossier','')
        if not re.fullmatch(r'desordre_[a-f0-9]{16}',nom): return None
        dossier=job.directory/nom
        return dossier if dossier.is_dir() and not dossier.is_symlink() else None

    @app.get("/api/jobs/{job_id}/desordre")
    def resultats_desordre(job_id: str, request: Request):
        job=manager.get(owner(request),job_id)
        from analyse_desordre.service import lire_etat, lire_tableau, dependances_disponibles
        etat=lire_etat(job.directory);dossier=dossier_desordre(job,etat)
        disponibles=dossier is not None
        from analyse_desordre.sources import inventaire_sources, publications_sans_resultat
        lignes=lire_tableau(dossier/'indicateurs_engagement.csv') if disponibles else []
        from analyse_desordre.annotation import (
            lire_annotations, fusionner, statistiques_codage, correlations_violence,
            publications_annotables
        )
        with job.lock:
            codages=lire_annotations(job.directory)
        # L'identité de l'éditeur change après sauvegarde pour éliminer ses
        # anciennes modifications locales (et ne pas les réappliquer au nouveau CSV).
        revision=hashlib.sha256(
            json.dumps(codages,sort_keys=True).encode('utf-8')).hexdigest()[:12]
        sans_resultat=publications_sans_resultat(job.directory,lignes,etat)
        base=lire_tableau(dossier/'correlations_spearman.csv') if disponibles else []
        annotations_corr=(correlations_violence(
            dossier/'indicateurs_engagement.csv',codages)
            if disponibles and etat.get('statut') in ('termine','partiel') else [])
        inventaire=inventaire_sources(job.directory)
        from analyse_desordre.sources import lire_publications
        publications_analyse = lire_publications(job.directory)
        anotables=publications_annotables(
            publications_analyse, [*lignes,*sans_resultat])
        indicateurs_ia = {
            str(publication.get("id") or publication.get("publication_id")):
                publication.get("contenu_genere_ia")
            for publication in publications_analyse if isinstance(publication, dict)
        }
        from analyse_desordre.codages_personnalises import lire as lire_codages_personnalises
        with job.lock:
            personnalises=lire_codages_personnalises(job.directory)
        revision=hashlib.sha256((revision+json.dumps(personnalises,ensure_ascii=False,sort_keys=True)).encode('utf-8')).hexdigest()[:12]
        return {'etat':etat,'disponible':dependances_disponibles(),
            **inventaire,
            'indicateurs':fusionner(lignes,codages),
            'sans_resultat':fusionner(sans_resultat,codages),
            'annotations_violence':statistiques_codage(codages,len(anotables)),
            'annotation_version':revision,
            'publications_annotables':anotables,
            'indicateurs_ia':indicateurs_ia,
            'codages_personnalises':personnalises,
            'correlations':base+annotations_corr}

    @app.get("/api/jobs/{job_id}/desordre/tableau-complet.csv")
    def exporter_tableau_complet_desordre(job_id: str, request: Request):
        """Exporter toutes les mesures et codages, sans MP4 ni recalcul vidéo."""
        job=manager.get(owner(request),job_id)
        from analyse_desordre.corpus_fusion import sauvegarder_tableau_complet
        with job.lock:
            try:
                fichier=sauvegarder_tableau_complet(job.directory)
            except (ValueError, OSError, KeyError, TypeError) as erreur:
                raise HTTPException(422, str(erreur)) from erreur
            if fichier is None:
                raise HTTPException(404, "Aucun tableau d'analyse disponible pour cette collecte.")
            texte=fichier.read_text(encoding="utf-8")
        return Response(texte,media_type="text/csv; charset=utf-8",
            headers=entete_telechargement(nom_fichier_telechargement(
                job.settings.nom_sauvegarde, "tableau_complet", "csv")))

    @app.post("/api/jobs/{job_id}/desordre/sauvegarder")
    def enregistrer_analyse_desordre(job_id: str, request: Request):
        """Sauvegarder explicitement les mesures et les codages sur 30 jours."""
        exiger_ticket(request)
        job=manager.get(owner(request), job_id)
        cookie=owner_historique(request)
        if job.busy or job.video_busy or not job.archive_prete:
            raise HTTPException(409, "Attendez la fin des traitements pour enregistrer l'analyse.")
        if job.owner_historique and job.owner_historique != cookie:
            raise HTTPException(403, "Cette analyse est liée à un autre historique privé.")
        from stockage.historique_analyses import retention_jours
        with job.lock:
            if not job.historique:
                job.owner_historique=cookie
            if not job.sauvegarder_historique():
                raise HTTPException(500, "L'historique n'a pas pu être enregistré.")
        return {"ok":True,"id":job.id,"retention_jours":retention_jours()}

    @app.post("/api/jobs/{job_id}/desordre/annotations")
    def sauver_annotations_desordre(job_id: str, modifications: AnnotationsViolence, request: Request):
        """Sauvegarder les codages explicites de l'utilisateur, pas de classification automatique."""
        exiger_ticket(request)
        job=manager.get(owner(request),job_id)
        from analyse_desordre.service import lire_etat
        from analyse_desordre.sources import lire_publications
        from analyse_desordre.annotation import enregistrer_annotations, statistiques_codage
        etat=lire_etat(job.directory)
        dossier=dossier_desordre(job,etat)
        if job.busy or job.video_busy:
            raise HTTPException(409, "Terminez d’abord la collecte ou le calcul en cours.")
        from analyse_desordre.service import lire_tableau
        from analyse_desordre.annotation import publications_annotables
        publications=publications_annotables(
            lire_publications(job.directory),
            lire_tableau(dossier/'indicateurs_engagement.csv'))
        identifiants={p['id'] for p in publications}
        changements=[p.model_dump() for p in modifications.annotations]
        with job.lock:
            try:
                codes=enregistrer_annotations(job.directory,changements,identifiants)
            except (ValueError, OSError) as erreur:
                raise HTTPException(422, str(erreur)) from erreur
            historique_ok=job.sauvegarder_historique()
        return {'ok':True,'annotations_violence':statistiques_codage(codes,len(identifiants)),
                'historique_synchronise':historique_ok}

    @app.post("/api/jobs/{job_id}/desordre/variables")
    def ajouter_variable_desordre(job_id: str, payload: NomVariableCodage, request: Request):
        exiger_ticket(request)
        job=manager.get(owner(request),job_id)
        if job.busy or job.video_busy:
            raise HTTPException(409, "Traitement en cours.")
        from analyse_desordre.codages_personnalises import creer_variable
        with job.lock:
            try:
                variable=creer_variable(job.directory,payload.nom)
            except (ValueError,OSError) as erreur:
                raise HTTPException(422,str(erreur)) from erreur
            historique_ok=job.sauvegarder_historique()
        return {'ok':True,'variable':variable,'historique_synchronise':historique_ok}

    @app.post("/api/jobs/{job_id}/desordre/variables/{variable_id}/renommer")
    def renommer_variable_desordre(
        job_id: str, variable_id: str, payload: NomVariableCodage, request: Request
    ):
        exiger_ticket(request)
        job=manager.get(owner(request),job_id)
        if job.busy or job.video_busy:
            raise HTTPException(409, "Terminez d'abord la collecte ou le calcul en cours.")
        from analyse_desordre.codages_personnalises import renommer_variable
        with job.lock:
            try:
                variable=renommer_variable(job.directory,variable_id,payload.nom)
            except (ValueError,OSError) as erreur:
                raise HTTPException(422,str(erreur)) from erreur
            historique_ok=job.sauvegarder_historique()
        return {'ok':True,'variable':variable,'historique_synchronise':historique_ok}

    @app.post("/api/jobs/{job_id}/desordre/codages")
    def sauver_codages_personnalises(job_id: str, payload: ModificationsCodages, request: Request):
        exiger_ticket(request)
        job=manager.get(owner(request),job_id)
        if job.busy or job.video_busy:
            raise HTTPException(409, "Traitement en cours.")
        from analyse_desordre.sources import lire_publications
        from analyse_desordre.codages_personnalises import enregistrer
        ids={str(p.get('id')) for p in lire_publications(job.directory)}
        with job.lock:
            try:
                valeurs=enregistrer(job.directory,[p.model_dump() for p in payload.annotations],ids)
            except (ValueError,OSError) as erreur:
                raise HTTPException(422,str(erreur)) from erreur
            historique_ok=job.sauvegarder_historique()
        return {'ok':True,'nombre_variables':len(valeurs['variables']),
                'historique_synchronise':historique_ok}

    @app.get("/api/jobs/{job_id}/desordre/codages.csv")
    def exporter_codages_personnalises(job_id: str, request: Request):
        job=manager.get(owner(request),job_id)
        from analyse_desordre.sources import lire_publications
        from analyse_desordre.annotation import lire_annotations, publications_annotables
        from analyse_desordre.codages_personnalises import lire, export_csv
        with job.lock:
            publications=publications_annotables(lire_publications(job.directory),[])
            texte=export_csv(publications,lire(job.directory),lire_annotations(job.directory))
        return Response(texte,media_type="text/csv; charset=utf-8",
            headers=entete_telechargement(nom_fichier_telechargement(
                job.settings.nom_sauvegarde, "codages_videos", "csv")))

    @app.get("/api/jobs/{job_id}/desordre/annotations.csv")
    def export_annotations_desordre(job_id: str, request: Request):
        job=manager.get(owner(request),job_id)
        from analyse_desordre.sources import lire_publications
        from analyse_desordre.service import lire_etat, lire_tableau
        from analyse_desordre.annotation import (
            lire_annotations, exporter_annotations_csv, publications_annotables
        )
        etat=lire_etat(job.directory)
        dossier=dossier_desordre(job,etat)
        lignes=lire_tableau(dossier/'indicateurs_engagement.csv') if dossier else []
        with job.lock:
            codes=lire_annotations(job.directory)
        publications=publications_annotables(lire_publications(job.directory),lignes)
        texte=exporter_annotations_csv(publications,codes)
        return Response(texte,media_type="text/csv; charset=utf-8",
            headers=entete_telechargement(nom_fichier_telechargement(
                job.settings.nom_sauvegarde, "annotations", "csv")))

    @app.get("/api/jobs/{job_id}/desordre/correlations_violence.csv")
    def export_correlations_violence(job_id: str, request: Request):
        job=manager.get(owner(request),job_id)
        from analyse_desordre.service import lire_etat
        from analyse_desordre.annotation import (
            lire_annotations, correlations_violence, exporter_correlations_csv
        )
        etat=lire_etat(job.directory)
        dossier=dossier_desordre(job,etat)
        if dossier is None or etat.get('statut') not in ('termine','partiel'):
            raise HTTPException(404, "Analyse indisponible.")
        with job.lock:
            codes=lire_annotations(job.directory)
        correlations=correlations_violence(dossier/'indicateurs_engagement.csv',codes)
        return Response(exporter_correlations_csv(correlations),
            media_type="text/csv; charset=utf-8",
            headers=entete_telechargement(nom_fichier_telechargement(
                job.settings.nom_sauvegarde, "correlations", "csv")))

    @app.get("/api/jobs/{job_id}/desordre/export/{nom}")
    def exporter_desordre(job_id: str, nom: str, request: Request):
        job=manager.get(owner(request),job_id)
        from analyse_desordre.service import lire_etat, FICHIERS_EXPORTABLES
        etat=lire_etat(job.directory);dossier=dossier_desordre(job,etat)
        if dossier is None or nom not in FICHIERS_EXPORTABLES or (etat['statut'] not in ('termine','partiel') and nom != 'indicateurs_engagement.csv'):
            raise HTTPException(404, 'Export indisponible')
        chemin=dossier/nom
        if not chemin.is_file() or chemin.is_symlink(): raise HTTPException(404, 'Export indisponible')
        return FileResponse(
            chemin,
            filename=nom_fichier_telechargement(
                job.settings.nom_sauvegarde, Path(nom).stem, Path(nom).suffix))

    @app.post("/api/jobs/{job_id}/video/stop")
    def arreter_analyse_video(job_id: str, request: Request):
        manager.get(owner(request), job_id).video_stop.set()
        return {"ok": True}

    @app.get("/api/presse")
    def inventaire_presse(request: Request):
        owner(request)
        from collecte.presse import charger_inventaire
        return {"medias": charger_inventaire()}

    @app.get("/api/jobs/{job_id}/archive")
    def telecharger_archive(job_id: str, request: Request, supprimer_arobase_profil: bool | None = None):
        job = manager.get(owner(request), job_id)
        if job.busy or job.video_busy or not job.archive_prete:
            raise HTTPException(409, "L’archive enrichie n’est pas encore disponible.")
        from corpus.export_zip import archive_avec_texte
        contenu = job.texte_a_exporter(supprimer_arobase_profil).encode("utf-8")
        # Inclure les fichiers auparavant disponibles via des boutons séparés.
        ajouts = {}
        if job.commentaires and job.settings.inclure_commentaires_txt:
            ajouts["commentaires.txt"] = texte_commentaires_collectes(job).encode("utf-8")
        diagnostic = job.snapshot().get("debug_collecte")
        if diagnostic:
            ajouts["diagnostic_collecte.json"] = json.dumps(
                diagnostic, ensure_ascii=False, indent=2).encode("utf-8")
        if job.historique:
            from stockage.historique_analyses import exporter_zip
            # Le téléchargement de l'historique respecte le même choix que le TXT.
            with exporter_zip(job.directory) as source:
                flux = archive_avec_texte(
                    source, contenu, ajouts,
                    commentaires_csv_uniquement=(
                        job.settings.collecter_commentaires
                        and not job.settings.inclure_commentaires_txt))
        else:
            flux = archive_avec_texte(
                job.directory / "archive.zip", contenu, ajouts,
                commentaires_csv_uniquement=(
                    job.settings.collecter_commentaires
                    and not job.settings.inclure_commentaires_txt))
        # Le nom existant de la collecte sert aussi de nom de ZIP.
        nom = Path(job.settings.filename).stem + ".zip"
        return StreamingResponse(iter(lambda: flux.read(65536), b""), media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"},
            background=BackgroundTask(flux.close))

    @app.get("/api/jobs/{job_id}/engagement.csv")
    def telecharger_engagement(job_id: str, request: Request):
        from corpus.construction import lignes_engagement, COLONNES_ENGAGEMENT
        from corpus.export_csv import serialiser_csv
        job = manager.get(owner(request), job_id)
        with job.lock:
            publications=job.records
            fichier=job.directory / 'publications.json'
            if fichier.is_file():
                visuelles={str(p['id']):p for p in json.loads(fichier.read_text())}
                publications=[{
                    **p,
                    **{
                        k: visuelles.get(str(p['id']), {}).get(k)
                        if visuelles.get(str(p['id']), {}).get(k) is not None else p.get(k)
                        for k in ('groupe_visuel', 'reemploi_visuel')
                    },
                } for p in publications]
            contenu = serialiser_csv(lignes_engagement(publications), COLONNES_ENGAGEMENT)
        return Response(contenu.encode("utf-8-sig"), media_type="text/csv",
            headers=entete_telechargement(nom_fichier_telechargement(
                job.settings.nom_sauvegarde, "engagement", "csv")))

    @app.get("/api/jobs/{job_id}/sociometrie")
    def consulter_sociometrie(job_id: str, request: Request,
                             mode: str = "auteurs_videos", seuil: int = 1):
        """Construire les réseaux à partir des commentaires autorisés de la session."""
        job = manager.get(owner(request), job_id)
        from analyse_sociometrique.reseaux import construire_reseau, apercu, construire_dot
        with job.lock:
            commentaires, publications = list(job.commentaires), list(job.records)
        try:
            graphe = construire_reseau(commentaires, publications, mode, job.id, seuil)
        except ValueError as erreur:
            raise HTTPException(422, str(erreur)) from erreur
        visible = apercu(graphe)
        return {
            "statistiques": graphe["statistiques"],
            "diagnostics": graphe["diagnostics"],
            "dot": construire_dot(visible),
            "apercu_liens": visible["liens"],
            "apercu_partiel": visible["partiel"],
            "matrice_disponible": len(graphe["noeuds"]) <= 250,
            "analyse_en_cours": job.busy,
        }

    @app.get("/api/jobs/{job_id}/sociometrie/export/{format_}")
    def exporter_sociometrie(job_id: str, format_: str, request: Request,
                             mode: str = "auteurs_videos", seuil: int = 1):
        """Exporter les liens et matrices privés en CSV, GraphML ou GEXF."""
        job = manager.get(owner(request), job_id)
        from analyse_sociometrique.reseaux import construire_reseau, exporter
        with job.lock:
            commentaires, publications = list(job.commentaires), list(job.records)
        try:
            reseau = construire_reseau(commentaires, publications, mode, job.id, seuil)
            contenu = exporter(reseau, format_)
        except ValueError as erreur:
            raise HTTPException(422, str(erreur)) from erreur
        media = "text/csv; charset=utf-8" if format_.endswith(".csv") else "application/xml"
        extension_reseau = (
            format_.rsplit(".", 1)[1] if "." in format_ else format_)
        nature_reseau = (
            Path(format_).stem if "." in format_ else format_)
        nom = nom_fichier_telechargement(
            job.settings.nom_sauvegarde,
            f"sociometrie_{mode}_{nature_reseau}", extension_reseau)
        return Response(contenu, media_type=media,
                        headers=entete_telechargement(nom))

    @app.get("/api/jobs/{job_id}/commentaires.txt")
    def telecharger_commentaires(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        if not job.settings.inclure_commentaires_txt:
            raise HTTPException(409,
                "Les commentaires ont été enregistrés uniquement dans le CSV. "
                "L'export TXT n'était pas activé pour cette collecte.")
        return Response(texte_commentaires_collectes(job), media_type="text/plain",
            headers=entete_telechargement(nom_fichier_telechargement(
                job.settings.nom_sauvegarde, "commentaires", "txt")))

    @app.get("/api/historique")
    def historique_analyses(request: Request):
        from stockage.historique_analyses import lister, retention_jours
        return {"analyses":lister(manager.data_dir, owner_historique(request)),
                "retention_jours":retention_jours()}

    @app.post("/api/historique/{identifiant}/reprendre", status_code=202)
    def reprendre_collecte_existante(
            identifiant: str, payload: ReprendreCollectePayload, request: Request):
        """Reprendre exclusivement les médias manquants dans le même corpus PostgreSQL."""
        exiger_ticket(request)
        travail = manager.reprendre_historique(
            owner(request), identifiant, owner_historique(request), payload)
        return travail.snapshot()

    @app.post("/api/historique/{identifiant}/reprendre-hashtags", status_code=202)
    def reprendre_hashtags_existants(
            identifiant: str, payload: ReprendreHashtagsPayload, request: Request):
        """Continuer une collecte hashtags Research sans nouveau corpus."""
        exiger_ticket(request)
        travail = manager.reprendre_hashtags_historique(
            owner(request), identifiant, owner_historique(request), payload)
        return travail.snapshot()

    @app.post("/api/historique/{identifiant}/ouvrir")
    def ouvrir_historique(identifiant: str, request: Request):
        exiger_ticket(request)
        return manager.reouvrir_historique(owner(request), identifiant,
                                          owner_historique(request)).snapshot()

    @app.get("/api/historique/{identifiant}/archive")
    def exporter_historique(identifiant: str, request: Request):
        from stockage.historique_analyses import retrouver, exporter_zip
        archive=retrouver(manager.data_dir, identifiant, owner_historique(request))
        if archive is None:
            raise HTTPException(404, "Analyse introuvable.")
        flux=exporter_zip(archive[1])
        return StreamingResponse(iter(lambda: flux.read(65536), b""), media_type="application/zip",
            headers=entete_telechargement(nom_fichier_telechargement(
                archive[0].get("titre") or identifiant, "analyse_complete", "zip")),
            background=BackgroundTask(flux.close))

    @app.get("/api/historique/{identifiant}/sauvegarde/{categorie}")
    def telecharger_sauvegarde_distincte(identifiant: str, categorie: str, request: Request):
        from stockage.historique_analyses import retrouver, exporter_sauvegarde_distincte
        if categorie not in {"collecte", "analyse"}:
            raise HTTPException(404, "Type de sauvegarde inconnu.")
        archive = retrouver(manager.data_dir, identifiant, owner_historique(request))
        if archive is None:
            raise HTTPException(404, "Sauvegarde introuvable.")
        flux = exporter_sauvegarde_distincte(archive[1], categorie)
        return StreamingResponse(iter(lambda: flux.read(65536), b""), media_type="application/zip",
            headers=entete_telechargement(nom_fichier_telechargement(
                archive[0].get("titre") or identifiant, categorie, "zip")),
            background=BackgroundTask(flux.close))

    @app.get("/api/sauvegardes")
    def sauvegardes_disponibles(request: Request):
        from stockage.sauvegarde_progressive import lister_points
        return {"sauvegardes": lister_points(manager.data_dir, owner(request))}

    @app.get("/api/sauvegardes/{identifiant}/telecharger")
    def telecharger_sauvegarde(identifiant: str, request: Request):
        from stockage.sauvegarde_progressive import fichier_point
        try:
            chemin=fichier_point(manager.data_dir, identifiant, owner(request))
        except ValueError:
            raise HTTPException(404, "Sauvegarde introuvable.")
        if chemin is None:
            raise HTTPException(404, "Sauvegarde introuvable.")
        # L'ancienne sauvegarde progressive conserve aussi son nom initial
        # lorsqu'il figure dans les paramètres archivés.
        nom_collecte = identifiant[:8]
        from zipfile import ZipFile
        try:
            with ZipFile(chemin) as archive:
                parametres = json.loads(archive.read("parametres.json"))
                nom_collecte = (
                    parametres.get("nom_sauvegarde") or nom_collecte)
        except (OSError, KeyError, ValueError, TypeError):
            pass
        return FileResponse(
            chemin, media_type="application/zip",
            filename=nom_fichier_telechargement(
                nom_collecte, "sauvegarde_intermediaire", "zip"))

    @app.get("/api/session")
    def session(request: Request):
        proprietaire = owner(request)
        job = manager.latest(proprietaire)
        return {
            "job": job.snapshot() if job else None,
            # Empreinte non authentifiante : jamais le cookie ou son contenu.
            "empreinte_session": hashlib.sha256(proprietaire.encode()).hexdigest()[:16],
            "instance": manager.instance_id,
        }

    def exiger_ticket(request):
        from ticket_gate import verifier_session_active
        if not verifier_session_active(owner(request)):
            raise HTTPException(403, "Accès non actif. Reprenez un ticket dans la barre latérale.")

    @app.post("/api/jobs", status_code=202)
    def start(payload: StartRequest, request: Request):
        exiger_ticket(request)
        if not payload.nom_sauvegarde:
            raise HTTPException(422, "Le nom de la sauvegarde est obligatoire.")
        if payload.cookies_tiktok is not None:
            if payload.source_collecte != "presse" or payload.presse_moteur != "navigateur":
                raise HTTPException(422, "L'import de cookies est disponible avec la méthode Presse Selenium.")
            try:
                from collecte.cookies_presse import charger_cookies_presse
                charger_cookies_presse(payload.cookies_tiktok.get_secret_value())
            except RuntimeError as erreur:
                raise HTTPException(422, str(erreur)) from None
        cookie = request.cookies.get(HISTORIQUE_COOKIE,"")
        return manager.start(owner(request), payload,
            cookie if re.fullmatch(r"[a-f0-9]{64}",cookie) else "").snapshot()

    @app.get("/api/jobs/{job_id}")
    def status(job_id: str, request: Request):
        return manager.get(owner(request), job_id).snapshot()

    @app.post("/api/jobs/{job_id}/stop")
    def stop(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        if job.busy:
            job.demander_arret("utilisateur")
        return {"ok": True, "arret_demande": job.stop.is_set(), "busy": job.busy}

    @app.post("/api/jobs/{job_id}/research/continuer")
    def poursuivre_research(job_id: str, request: Request):
        """Autoriser explicitement le lot de pagination suivant."""
        job = manager.get(owner(request), job_id)
        if not (job.busy and job.attente_validation_research
                and job.settings.source_collecte == "hashtags"
                and job.settings.moteur_actif == "research"):
            raise HTTPException(409, "La collecte Research n'attend pas de validation.")
        job.continuer_research.set()
        return {"ok": True, "statut": "reprise_demandee"}

    def enqueue(job, command):
        with job.lock:
            if job.status != "attention":
                raise HTTPException(409, "Le navigateur n’attend pas d’intervention.")
            try:
                job.commands.put_nowait(command)
            except queue.Full:
                raise HTTPException(409, "Patientez un instant avant le prochain geste.")

    @app.post("/api/jobs/{job_id}/continue")
    def resume(job_id: str, request: Request):
        enqueue(manager.get(owner(request), job_id), "continue")
        return {"ok": True}

    @app.post("/api/jobs/{job_id}/action", status_code=202)
    def action(job_id: str, payload: BrowserAction, request: Request):
        if payload.kind in {"click", "drag", "pointer_down", "pointer_move", "pointer_up"} and not payload.points:
            raise HTTPException(422, "Une position est requise.")
        job = manager.get(owner(request), job_id)
        if job.type_intervention == "connexion" and (payload.kind == "text" or payload.text):
            payload.text = ""
            raise HTTPException(422, "La collecte est anonyme ; aucune saisie d’identifiants ou de codes de connexion n’est proposée.")
        if payload.kind.startswith("pointer_"):
            command = LiveAction(payload)
            enqueue(job, command)
            # Accusé de réception après exécution : le client ne sature pas la file.
            if not command.done.wait(10):
                raise HTTPException(504, "Le navigateur ne répond pas. Attendez puis réessayez.")
            if command.error:
                raise HTTPException(409, command.error)
        else:
            enqueue(job, payload)
        return {"ok": True}

    @app.get("/api/jobs/{job_id}/frame")
    def frame(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        with job.lock:
            return Response(job.frame, media_type="image/png", status_code=200 if job.frame else 204)

    @app.get("/api/jobs/{job_id}/download")
    def download(job_id: str, request: Request, supprimer_arobase_profil: bool | None = None):
        job = manager.get(owner(request), job_id)
        if not job.path.exists() or not job.records:
            raise HTTPException(409, "Aucun texte n’est encore disponible.")
        filename = job.settings.filename
        # Régénérer aussi les anciens exports pour appliquer les corrections de codage.
        contenu = job.texte_a_exporter(supprimer_arobase_profil).encode("utf-8")
        return Response(contenu, media_type="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})

    @app.get("/interface")
    @app.get("/interface/")
    def ancienne_adresse():
        return RedirectResponse("/", status_code=302)

    # Seules les ressources du navigateur intégré sont servies par FastAPI.
    @app.get("/static/controle.css")
    def style_controle():
        return FileResponse(scraper.BASE_DIR / "static" / "controle.css")

    @app.get("/static/navigateur.js")
    def gestes_navigateur():
        return FileResponse(scraper.BASE_DIR / "static" / "navigateur.js")

    @app.get("/static/controle.js")
    def script_controle():
        return FileResponse(scraper.BASE_DIR / "static" / "controle.js")

    from interface.passerelle import installer_passerelle
    installer_passerelle(app)
    return app


app = create_app()
