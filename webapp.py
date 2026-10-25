"""Interface web : un navigateur isolé par collecte, piloté uniquement par son worker."""
from __future__ import annotations

import json
import hashlib
import signal
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
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field, field_validator, model_validator
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

import scraptiktok as scraper
from language_filter import classify_description
from collecte.dates import normaliser_date, evaluer_periode

LOG = logging.getLogger("scraptiktok.web")
TERMINAL = {"completed", "partial", "failed", "stopped"}
COOKIE = "scraptiktok_session"
HISTORIQUE_COOKIE = "scraptiktok_historique"


class StartRequest(BaseModel):
    hashtag: str = Field(default="", max_length=100)
    source_collecte: Literal["hashtags", "comptes", "presse"] = "hashtags"
    comptes: list[str] = Field(default_factory=list, max_length=10)
    medias: list[str] = Field(default_factory=list, max_length=29)
    presse_moteur: Literal["api", "navigateur", "tikwm"] = "api"
    enrichir: bool = False
    telecharger_mp4: bool = False
    sauvegarde_progressive: bool = False
    collecter_commentaires: bool = False
    collecter_reponses: bool = False
    limite_commentaires: int = Field(default=50, ge=1, le=500)
    second_hashtag: str = Field(default="", max_length=100)
    operator: Literal["AND", "OR"] = "AND"
    rechercher_dans_texte: bool = False
    variantes_accents: bool = False
    limit: int = Field(default=50, ge=1, le=1000)
    include_sources: bool = True
    inclure_metadonnees_txt: bool = False
    # None conserve les anciennes requêtes ; une liste vide demande le texte seul.
    variables_txt: list[Literal["date", "profil", "id", "vues", "likes", "partages", "commentaires", "favoris", "hashtags"]] | None = Field(default=None, max_length=9)
    french_only: bool = False
    date_debut: str | None = Field(default=None, max_length=10)
    date_fin: str | None = Field(default=None, max_length=10)

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

    @field_validator("second_hashtag")
    @classmethod
    def valid_second_hashtag(cls, value):
        return cls.valid_hashtag(value) if value.strip() else ""

    @field_validator("comptes")
    @classmethod
    def valider_comptes(cls, valeurs):
        from collecte.verification_comptes import normaliser_compte
        return list(dict.fromkeys(normaliser_compte(v) for v in valeurs))

    @model_validator(mode="after")
    def valider_sources(self):
        if self.date_debut and self.date_fin and self.date_debut > self.date_fin:
            raise ValueError("La date de début doit précéder ou égaler la date de fin.")
        if self.source_collecte == "presse":
            # La collecte média dépend uniquement des comptes choisis ; ignorer
            # aussi les anciens hashtags présents dans une requête sauvegardée.
            self.hashtag = ""
            self.second_hashtag = ""
            self.rechercher_dans_texte = False
            self.variantes_accents = False
        else:
            if not self.hashtag:
                if self.source_collecte == "comptes":
                    raise ValueError("Renseignez au moins un hashtag pour une collecte par profil.")
                raise ValueError("Le premier hashtag est obligatoire.")
            if self.second_hashtag and not self.hashtag:
                raise ValueError("Renseignez le premier hashtag avant le deuxième.")
        if self.source_collecte == "comptes" and not self.comptes:
            raise ValueError("Renseignez au moins un compte TikTok.")
        if self.source_collecte == "presse":
            from collecte.presse import selectionner_medias
            if not self.medias: raise ValueError("Sélectionnez au moins un média.")
            selectionner_medias(self.medias)
        if not self.collecter_commentaires: self.collecter_reponses = False
        return self

    @property
    def enrichie(self):
        return self.enrichir or self.source_collecte != "hashtags" or self.collecter_commentaires or self.telecharger_mp4

    @property
    def libelle(self):
        if self.source_collecte == "hashtags":
            return (" OU " if self.operator == "OR" else " ET ").join("#" + h for h in self.hashtags)
        return ", ".join("@" + s["compte"] for s in self.sources)

    @property
    def sources(self):
        from collecte.presse import selectionner_medias
        if self.source_collecte == "presse": return selectionner_medias(self.medias)
        return [{"compte": c, "id": None, "categorie": None} for c in self.comptes]

    @property
    def hashtags(self):
        return list({tag_key(tag): tag for tag in [self.hashtag, self.second_hashtag] if tag}.values())

    @property
    def filename(self):
        joiner = "_ET_" if self.operator == "AND" else "_OU_"
        return "tiktok_" + (joiner.join(self.hashtags) if self.source_collecte == "hashtags" else "comptes_" + "_".join(s["compte"] for s in self.sources)[:100]) + ("_fr" if self.french_only else "") + ".txt"


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


def matches_hashtags(description, settings):
    resultats = [
        correspondance_hashtag(description, tag,
            rechercher_dans_texte=settings.rechercher_dans_texte,
            variantes_accents=settings.variantes_accents)
        for tag in settings.hashtags
    ]

    if not resultats:
        # La collecte presse ne filtre pas les légendes sur les hashtags.
        return settings.source_collecte == "presse"

    return all(resultats) if settings.operator == "AND" else any(resultats)


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
    """Reprendre les anciennes sélections : republications vers partages, URL vers ID."""
    if variables is None:
        return None
    return list(dict.fromkeys({"republications": "partages", "url": "id"}.get(v, v) for v in variables))


def entete_publication(publication: dict, variables=None, supprimer_arobase_profil=False) -> str:
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

    valeurs = {"date": f"*date_{date_publication}",
               "profil": f"*profil_{profil}", "id": f"*id_{modalite(publication.get('id'))}",
               "vues": f"*vues_{compteur('vues')}", "likes": f"*likes_{compteur('likes')}",
               "partages": f"*partages_{compteur('partages')}",
               "commentaires": f"*comment_{compteur('commentaires')}",
               "favoris": f"*favoris_{compteur('favoris')}"}
    # Les anciens appels sans sélection gardent leur en-tête à trois variables.
    selection = set(normaliser_variables_txt(variables) if variables is not None else ("date", "profil", "id"))
    entete = " ".join(texte for cle, texte in valeurs.items() if cle in selection)
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


def text_export(records: list[dict], include_sources: bool, inclure_metadonnees_txt: bool = False,
                variables_txt=None, commentaires=None, supprimer_arobase_profil=False) -> str:
    blocks = []
    par_publication = {}
    selection = normaliser_variables_txt(variables_txt)
    for commentaire in commentaires or []:
        if commentaire.get("texte"):
            par_publication.setdefault(str(commentaire.get("publication_id")), []).append(commentaire)
    for record in records:
        if not record.get("description"):
            continue
        prefix = (entete_publication(record, selection, supprimer_arobase_profil) if selection is not None
                  else entete_publication(record, supprimer_arobase_profil=supprimer_arobase_profil) if inclure_metadonnees_txt
                  else entete_publication(record, ("profil", "id"), supprimer_arobase_profil) if include_sources else "")
        # Le lien texte/MP4 reste présent même si la case ID vidéo était décochée.
        if record.get("video_id") and not re.search(r"(?:^| )\*id_", prefix):
            prefix = prefix.rstrip("\n") + (" " if prefix else "") + f"*id_{record['video_id']}\n"
        texte = texte_et_hashtags(record) if selection and "hashtags" in selection else record["description"]
        bloc = prefix + texte
        for numero, commentaire in enumerate(par_publication.get(str(record["id"]), []), 1):
            etiquette = "Réponse" if commentaire.get("est_reponse") else "Commentaire"
            bloc += f"\n\n{etiquette} {numero} :\n{commentaire['texte']}"
        blocks.append(bloc)
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
                 identifiant=None, archive_directory=None, owner_historique=""):
        self.id = identifiant or uuid.uuid4().hex
        self.owner = owner
        self.owner_historique = owner_historique
        self.historique = archive_directory is not None
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
        self.bilan_hashtags = {h: 0 for h in settings.hashtags}
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
        self.frame = b""
        self.action_error = ""
        self.type_intervention = ""
        self.thread = None
        self.publications = []
        self.commentaires = []
        self.journal = []
        self.archive_prete = False
        self.video_busy = False
        self.video_stop = threading.Event()
        self.video_process = None
        self.video_thread = None
        self.video_debut = None
        self.base = None
        if settings.enrichie and not self.historique:
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
                    'traitees':self.processed,'restantes':max(0,self.discovered-self.processed),
                    'publications_enregistrees':len(self.publications),'exportees_txt':self.exportees,
                    'hors_hashtags':self.filtered,'autre_langue':self.non_french,
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
                    "second_hashtag": self.settings.second_hashtag, "operator": self.settings.operator,
                    "rechercher_dans_texte": self.settings.rechercher_dans_texte,
                    "variantes_accents": self.settings.variantes_accents,
                    "hashtags": self.settings.hashtags, "filename": self.settings.filename,
                    "filtered": self.filtered, "search_errors": self.search_errors,
                    "bilan_hashtags": dict(self.bilan_hashtags),
                    "correspondances_hashtags": self.correspondances_hashtags,
                    "legendes_vides": self.legendes_vides,
                    "bilan_sources": [{"source": entree["source"],
                        "liens": len(entree.get("rapport", {}).get("discovered_urls", [])),
                        "version_collecteur": entree.get("rapport", {}).get("version_collecteur"),
                        "presse_moteur": entree.get("rapport", {}).get("presse_moteur"),
                        "message": entree.get("message", "Recherche terminée."),
                        "retenues_par_compte": entree.get("rapport", {}).get("retenues_par_compte", {}),
                        "recherches": [{"requete": r.get("requete_recherche"),
                            "compte": r.get("compte_attendu"),
                            "candidats_examines": r.get("candidats_examines", 0),
                            "auteurs_dans_liens": r.get("auteurs_dans_liens", {}),
                            "defilements": r.get("defilements_effectues", 0),
                            "arret": r.get("discovery_stop", ""),
                            "pagination_bilan": r.get("pagination_bilan", {}),
                            "pages_api": r.get("pages_api", 0),
                            "requetes_tentees": r.get("requetes_tentees", 0),
                            "secuid_resolu": bool(r.get("secuid_resolu", False)),
                            "source_secuid": r.get("source_secuid"),
                            "tentatives_embed_video": r.get("tentatives_embed_video", 0),
                            "pages_tikwm": r.get("pages_tikwm", 0),
                            "fournisseur_donnees": r.get("fournisseur_donnees"),
                            "videos_amorcage_disponibles": r.get("videos_amorcage_disponibles", 0),
                            "urls_embed_non_verifiees": r.get("urls_embed_non_verifiees", 0),
                            # Liens déjà présents dans la réponse reçue AVANT le 429.
                            # Exposés au seul propriétaire de la collecte pour export
                            # et référencement, sans les compter comme textes lus.
                            "urls_embed_references": (
                                list(r.get("discovered_urls", []))
                                if r.get("urls_embed_non_verifiees") else []
                            ),
                            "message_erreur": r.get("message_erreur"),
                            "navigation_publications": r.get("navigation_publications"),
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
                    "non_french": self.non_french, "language_unknown": self.language_unknown,
                    "date_debut": self.settings.date_debut, "date_fin": self.settings.date_fin,
                    "hors_periode": self.hors_periode, "dates_indeterminees": self.dates_indeterminees,
                    "source_collecte": self.settings.source_collecte,
                    "presse_moteur": self.settings.presse_moteur, "comptes": self.settings.comptes,
                    "comptes_filtres": ([source["compte"] for source in self.settings.sources]
                                        if self.settings.source_collecte != "hashtags" else []),
                    "medias": self.settings.medias, "libelle": self.settings.libelle,
                    "diagnostics": list(self.diagnostics),
                    "telecharger_mp4": self.settings.telecharger_mp4,
                    "sauvegarde_progressive": self.settings.sauvegarde_progressive,
                    "dernier_point_sauvegarde": self.dernier_point_sauvegarde,
                    "erreur_sauvegarde": self.erreur_sauvegarde,
                    "bilan_mp4": [{"video_id": r.get("video_id"), "video_statut": r.get("video_statut", "en_attente"),
                        "video_message": r.get("video_message", "En attente du téléchargement."),
                        "video_fichier": r.get("video_fichier")} for r in self.records if r.get("video_id")],
                    "enrichir": self.settings.enrichie, "commentaires_collectes": len(self.commentaires),
                    "collecter_commentaires":self.settings.collecter_commentaires, "collecter_reponses":self.settings.collecter_reponses,
                    "commentaires_indisponibles": sum(r.get("collecte_commentaires", {}).get("statut") in {
                        "inaccessible", "page_differente", "indisponible_ou_vide", "panneau_introuvable",
                        "extraction_impossible", "chargement_incomplet", "erreur_chargement", "verification_tiktok",
                        "connexion_requise", "desactives"} for r in self.records),
                    "bilan_commentaires": [{"publication_id": r["id"], **r["collecte_commentaires"]}
                        for r in self.records if "collecte_commentaires" in r],
                    "limite_commentaires":self.settings.limite_commentaires,
                    "archive_prete": self.archive_prete, "video_busy": self.video_busy,
                    "limit": self.settings.limit, "status": self.status, "busy": self.busy,
                    "message": self.message, "discovered": self.discovered,
                    "processed": self.processed, "captions": len(self.records),
                    "compteurs_collecte": {"decouvertes": len(self.decouvertes_ids), "retenues": self.discovered,
                        "traitees": self.processed, "exportees": self.exportees},
                    "errors": self.errors, "has_frame": bool(self.frame), "type_intervention": self.type_intervention,
                    "action_error": self.action_error, "can_download": bool(self.records),
                    "apercu_engagement": [{"id": r["id"], "author": r["author"], "url": r["url"],
                        "engagement": r.get("engagement", {}), "langue_detection": r.get("langue_detection"),
                        "retenue_txt": bool(r.get("retenue", r in self.records))}
                        for r in (self.publications or self.records)],
                    "preview": [{"author": r["author"], "description": r["description"]}
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

    def texte_a_exporter(self, supprimer_arobase_profil=False):
        """Appliquer le choix de téléchargement sans modifier les données collectées."""
        with self.lock:
            return text_export(self.records, self.settings.include_sources,
                self.settings.inclure_metadonnees_txt, self.settings.variables_txt,
                self.commentaires if self.settings.collecter_commentaires else None,
                supprimer_arobase_profil=supprimer_arobase_profil)

    def sauvegarder_historique(self):
        """Synchroniser les résultats et codages dans l'historique privé de 30 jours."""
        if self.historique:
            # Les analyses rouvertes pointent déjà sur leur dossier d'archive.
            return True
        if not self.owner_historique or not self.archive_prete:
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
            content = text_export(self.records, self.settings.include_sources, self.settings.inclure_metadonnees_txt,
                                  self.settings.variables_txt, self.commentaires if self.settings.collecter_commentaires else None)
            nombre_exporte = sum(bool(r.get("description")) for r in self.records)
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
                nature = scraper.type_intervention_tiktok(driver)
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
                if scraper.captcha_present(driver):
                    job.update(type_intervention="captcha", action_error="TikTok affiche encore un CAPTCHA. Terminez-le dans la fenêtre avant de continuer.")
                    continue
                break
            live = command if isinstance(command, LiveAction) else None
            if live:
                command = live.action
            try:
                if command.kind == "text" and scraper.type_intervention_tiktok(driver) == "connexion":
                    command.text = ""
                    raise ValueError("La collecte est anonyme ; aucune saisie d’identifiants n’est proposée.")
                perform_action(driver, command)
                if command.kind in {"pointer_down", "pointer_move"}:
                    held_since = time.monotonic()
                elif command.kind in {"pointer_up", "pointer_cancel"}:
                    held_since = None
                job.update(action_error="")
                next_frame = 0
            except (scraper.WebDriverException, ValueError):
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
        except scraper.WebDriverException:
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
    from collecte.presse_api import PresseRateLimitError, PresseCooldownError
    from collecte.quotas_exploitation import QuotaScrapingAtteint
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
    diagnostic = rapport.get("diagnostic", {})
    code = diagnostic.get("code")
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


def execute_job(job: Job, driver_factory=scraper.create_driver):
    from collecte.quotas_exploitation import max_defilements
    args = argparse.Namespace(
        hashtag=job.settings.hashtag, limit=job.settings.limit,
        max_scrolls=max_defilements(),
        idle_rounds=3, delay=3.0, timeout=20.0, interactive=True,
        headless=os.getenv("SCRAPTIKTOK_HEADLESS", "1") == "1",
        chrome_binary=Path(os.environ["CHROME_BINARY"]) if os.getenv("CHROME_BINARY") else None,
        driver=Path(os.environ["CHROMEDRIVER"]) if os.getenv("CHROMEDRIVER") else None,
    )
    driver = None
    connexion = None
    unique_links = {}
    metadonnees_api = {}
    final_status, final_message = "failed", "La collecte n’a pas pu aboutir."
    limitation_tiktok = False
    limitation_tikwm = False
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
        sources = connexion.preparer_sources(job.settings)
        driver = connexion.ouvrir()
        hors_selection = 0
        medias_par_compte = {s["compte"]: s for s in sources if "compte" in s}
        links = []
        def lire_decouvertes():
            """Lire et exporter les nouvelles publications dès qu'un compte est découvert."""
            nonlocal links, hors_selection
            links = list(unique_links.values())
            job.update(status="collecting", discovered=len(links))
            for index in range(job.processed + 1, len(links) + 1):
                url = links[index - 1]
                job.update(message=f"Lecture de la publication {index} sur {len(links)}…", publication_en_cours=scraper.canonical_post(url)[0])
                try:
                    identifiant_publication = scraper.canonical_post(url)[0]
                    record_api = metadonnees_api.get(identifiant_publication)
                    if (job.settings.source_collecte == "presse"
                            and record_api is not None
                            and (job.settings.presse_moteur == "tikwm"
                                 or (job.settings.presse_moteur == "api"
                                     and not job.settings.collecter_commentaires
                                     and record_api.get("description")))):
                        # TikTok a déjà fourni une légende et éventuellement les
                        # compteurs dans itemList : ne pas faire une nouvelle
                        # visite Selenium pour la même vidéo.
                        record = dict(record_api)
                    else:
                        # La pause entre publications n'est utile que lorsqu'une
                        # consultation TikTok / Selenium est réellement nécessaire.
                        job.pause(args.delay)
                        record = connexion.lire_publication(url)
                    record["retenue"] = False
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
                        with job.lock:
                            if periode == "hors_periode": job.hors_periode += 1
                            else: job.dates_indeterminees += 1
                        job.journal.append({"publication_id":record["id"], "created_at":record.get("created_at"), "filtre_date":periode})
                    else:
                        if job.settings.enrichie:
                            media = medias_par_compte.get(record["author"].lower(), {})
                            record.update(media_id=media.get("id"), categorie_media=media.get("categorie"), retenue=False)
                            job.publications.append(record)
                        if record["description"]:
                            matches = matches_hashtags(record["description"], job.settings)
                            # Compter sur la même légende et dans la même période que le filtre.
                            with job.lock:
                                for hashtag in job.bilan_hashtags:
                                    if correspondance_hashtag(
                                            record["description"], hashtag,
                                            rechercher_dans_texte=job.settings.rechercher_dans_texte,
                                            variantes_accents=job.settings.variantes_accents):
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
                                    job.filtered += 1
                                elif language == "other":
                                    job.non_french += 1
                                else:
                                    if language == "unknown":
                                        job.language_unknown += 1
                                    record["retenue"] = True
                                    job.records.append(record)
                            # Les commentaires sont demandés uniquement pour les publications retenues.
                            if record.get("retenue") and job.settings.collecter_commentaires:
                                from collecte.commentaires import collecter_commentaires
                                try:
                                    resultat = collecter_commentaires(driver, record, job.settings.limite_commentaires,
                                        job.settings.collecter_reponses, verifier=job.check, pause=job.pause,
                                        interact=connexion.intervenir)
                                    with job.lock:
                                        recuperes = resultat.pop("commentaires")
                                        resultat.setdefault("recuperes", len(recuperes))
                                        resultat.setdefault("annonces", (record.get("engagement") or {}).get("commentaires", {}).get("valeur"))
                                        job.commentaires.extend(recuperes)
                                        record["collecte_commentaires"] = resultat
                                except scraper.WebDriverException as erreur:
                                    if scraper.est_erreur_session(erreur): raise
                                    record["collecte_commentaires"] = {"statut": "inaccessible", "exhaustif": False}
                        else:
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
                job.save()
                if job.base:
                    job.base.enregistrer(job.id, job.publications[-1:], job.commentaires)
                if job.settings.sauvegarde_progressive and index % 10 == 0:
                    job.sauvegarder_point()

        for numero_source, source in enumerate(sources, 1):
            job.check()
            # Double garde-fou : même si un connecteur de hashtags renvoie
            # trop d'URL, ne jamais retenir plus que la limite globale saisie.
            if job.settings.source_collecte == "hashtags" and len(unique_links) >= args.limit:
                break
            etiquette = "#" + source["hashtag"] if "hashtag" in source else "@" + source["compte"]
            job.update(status="discovering", message=f"Source {numero_source}/{len(sources)} : recherche des publications de {etiquette}…")
            rapport = {}
            def suivre_decouverte(nombre):
                job.actualiser_decouverte(rapport)
                requete = rapport.get("requete_recherche") or etiquette
                objectif = f"{nombre}/{args.limit}" if job.settings.source_collecte != "hashtags" else str(nombre)
                job.update(message=f"Source {numero_source}/{len(sources)} — recherche {requete} : "
                    f"{rapport.get('candidats_examines', nombre)} publication(s) découverte(s), "
                    f"{objectif} retenue(s) pour ce compte…")
            try:
                found = connexion.decouvrir(source, rapport,
                    contexte=f"Source {numero_source}/{len(sources)} — {etiquette}",
                    progression=suivre_decouverte)
                rapport["discovered_urls"] = found
                if job.settings.source_collecte == "presse" and job.settings.presse_moteur in {"api", "tikwm"}:
                    for identifiant, donnees in (rapport.get("metadonnees_api") or {}).items():
                        if isinstance(donnees, dict):
                            metadonnees_api.setdefault(str(identifiant), donnees)
                if rapport.get("recherches_en_echec"):
                    job.update(search_errors=job.search_errors + 1)
                message_source = rapport.get("bilan_recherche") or ("Recherche partielle : une recherche TikTok a échoué."
                                  if rapport.get("recherches_en_echec") else "Recherche terminée.")
                job.journal.append({"source":etiquette,"date":scraper.utc_now(),"rapport":rapport,
                    "message": message_source if found or rapport.get("bilan_recherche") else ("Collecte partielle : aucune publication du compte trouvée dans les résultats accessibles. Cela ne signifie pas que le compte est vide."
                        if job.settings.source_collecte != "hashtags" else "Aucune publication correspondant à cette recherche n’a été trouvée. Cela ne signifie pas que le compte est vide.")})
                for url in found:
                    identity = scraper.canonical_post(url)
                    if identity and (job.settings.source_collecte == "hashtags"
                                     or identity[2].casefold() in medias_par_compte):
                        if (job.settings.source_collecte == "hashtags"
                                and len(unique_links) >= args.limit):
                            break
                        unique_links.setdefault(identity[0], identity[1])
            except (RuntimeError, scraper.WebDriverException) as erreur:
                LOG.warning("Source %s : %s", etiquette, type(erreur).__name__)
                if "diagnostic" not in rapport:
                    rapport["diagnostic"] = {"exception": type(erreur).__name__}
                job.journal.append({"source": etiquette, "statut": "inaccessible", "date": scraper.utc_now(), "rapport": rapport,
                    "message": expliquer_echec_source(rapport, erreur)})
                from collecte.presse_api import PresseRateLimitError, PresseCooldownError
                from collecte.presse_tikwm import TikwmRefus429
                from collecte.quotas_exploitation import QuotaScrapingAtteint
                if isinstance(erreur, QuotaScrapingAtteint):
                    limitation_budget = True
                    job.update(search_errors=job.search_errors + 1)
                    break
                if isinstance(erreur, TikwmRefus429):
                    # Garder les vidéos dont les données ont été vérifiées avant le refus.
                    for identifiant, fiche in (rapport.get("metadonnees_api") or {}).items():
                        if isinstance(fiche, dict):
                            metadonnees_api.setdefault(str(identifiant), fiche)
                    for adresse in rapport.get("discovered_urls", []):
                        identite = scraper.canonical_post(adresse)
                        if identite and identite[2].casefold() in medias_par_compte:
                            unique_links.setdefault(identite[0], identite[1])
                    limitation_tikwm = True
                    job.update(search_errors=job.search_errors + 1,
                        status="finalizing",
                        message="TikWM HTTP 429 : arrêt du prestataire externe ; données reçues conservées.")
                    break
                if isinstance(erreur, (PresseRateLimitError, PresseCooldownError)):
                    # Conserver les URL déjà découvertes avant le HTTP 429,
                    # sans nouvelle lecture de page, embed ou téléchargement.
                    for url in rapport.get("discovered_urls", []):
                        identite = scraper.canonical_post(url)
                        if identite and (
                            job.settings.source_collecte == "hashtags"
                            or identite[2].casefold() in medias_par_compte
                        ):
                            unique_links.setdefault(identite[0], identite[1])
                    links = list(unique_links.values())
                    limitation_tiktok = True
                    job.update(
                        search_errors=job.search_errors + 1,
                        status="finalizing",
                        message="TikTok HTTP 429 : collecte interrompue, sauvegarde des résultats sans nouveau téléchargement.",
                    )
                    break
                if len(sources) == 1 or scraper.est_erreur_session(erreur): raise
                job.update(search_errors=job.search_errors + 1)
            finally:
                job.actualiser_decouverte(rapport)
            job.update(discovered=len(unique_links))
            # Exporter chaque compte aussitôt sa découverte terminée.
            if job.settings.source_collecte != "hashtags" and len(unique_links) > job.processed:
                lire_decouvertes()
        # Exporter les métadonnées TikWM reçues avant le refus, sans nouvelle requête.
        if limitation_tikwm and len(unique_links) > job.processed:
            lire_decouvertes()
        # Un 429 TikTok interdit la lecture différée des vidéos déjà découvertes.
        if (job.settings.source_collecte == "hashtags" and not limitation_tiktok
                and not limitation_budget and not job.stop.is_set()):
            lire_decouvertes()
        exclus_decouverte = set().union(*(set(e.get("rapport", {}).get("auteurs_ecartes_ids", [])) for e in job.journal))
        recherche_partielle = any(e.get("rapport", {}).get("collecte_partielle") for e in job.journal)
        if job.settings.source_collecte != "hashtags":
            retenues_par_compte = {compte: 0 for compte in medias_par_compte}
            for url in links:
                identite = scraper.canonical_post(url)
                if identite and identite[2].casefold() in retenues_par_compte:
                    retenues_par_compte[identite[2].casefold()] += 1
            # Chaque profil contribue indépendamment à la limite demandée.
            recherche_partielle = any(nombre < args.limit for nombre in retenues_par_compte.values())
        final_status = "partial" if job.errors or job.search_errors or recherche_partielle else "completed"
        final_message = f"{len(job.records)} texte(s) collecté(s) sur {job.processed} publication(s) consultée(s)."
        if not job.records:
            final_message = ("Aucune publication accessible : consultez le détail des sources."
                             if not links else "Aucune légende exploitable retenue parmi les publications consultées.")
            if not links and job.settings.source_collecte != "hashtags":
                final_message = ("Aucune publication publique accessible pour les comptes sélectionnés. "
                                 "Consultez les diagnostics de chaque source ; les filtres de langue et de légende n’ont pas été appliqués.")
            if job.filtered and job.processed:
                final_message = "Aucun texte ne correspond à cette combinaison dans les publications consultées."
        if job.settings.french_only and job.processed:
            if not job.records and job.non_french:
                final_message = "Aucun texte retenu par le filtre français parmi les légendes consultées."
            final_message += f" Filtre français : {job.non_french} texte(s) identifié(s) dans une autre langue écartés ; {job.language_unknown} texte(s) de langue indéterminée conservés."
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
            final_message += (" Collecte partielle : la recherche TikTok n’a pas fourni la limite demandée ; résultats non exhaustifs."
                              if recherche_partielle else " Collecte limitée au nombre demandé par compte ; historique complet non garanti.")
        if limitation_budget:
            final_message += (" Plafond interne de requêtes API Presse atteint : "
                              "collecte arrêtée sans demander davantage de données à TikTok.")
            final_status = "partial" if links else "failed"
        if limitation_tikwm:
            final_message += (" TikWM HTTP 429 : le prestataire externe a arrêté la pagination. "
                              "Les autres médias du lot ne sont pas sollicités.")
            final_status = "partial" if links else "failed"
        if limitation_tiktok:
            final_message += (" TikTok HTTP 429 : découverte arrêtée immédiatement. "
                              "Les autres médias de cette collecte n'ont pas été sollicités ; "
                              "consultez l'éventuel délai Retry-After dans le diagnostic.")
            final_status = "partial" if links else "failed"
        if not links and job.search_errors:
            final_status = "failed"
        elif len(links) < args.limit and not job.settings.second_hashtag:
            final_message += f" La recherche a fourni {len(links)} lien(s), pour un objectif de {args.limit}."
    except Stopped:
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
                and not limitation_tiktok and not limitation_tikwm
                and not limitation_budget and not job.stop.is_set()):
            try:
                from telechargement_videos import capturer_contexte_anonyme
                contexte_mp4 = capturer_contexte_anonyme(connexion.obtenir_navigateur())
            except Exception:
                pass
        if connexion is not None:
            try:
                connexion.fermer()
            except scraper.WebDriverException:
                LOG.warning("Fermeture du navigateur impossible pour %s", job.id)
        try:
            job.save()
        except OSError:
            LOG.exception("Écriture de l’export impossible")
            final_status, final_message = "failed", "Le serveur n’a pas pu enregistrer le fichier texte."
        if (job.settings.telecharger_mp4 and job.records
                and not limitation_tiktok and not limitation_tikwm
                and not limitation_budget and not job.stop.is_set()):
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
        if job.base:
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
                     "diagnostics": job.diagnostics}, texte_source=job.path)
                # Les collectes comptes/presse peuvent découvrir un lien vidéo
                # sans pouvoir en lire la légende. Le conserver pour l'analyse
                # visuelle, sans le transformer en texte ou en mesure d'engagement.
                if job.settings.source_collecte in {"comptes", "presse"}:
                    from analyse_desordre.sources import construire_sources_visuelles
                    complement = construire_sources_visuelles(
                        unique_links.values(), job.publications
                    )
                    (job.directory / "sources_visuelles.json").write_text(
                        json.dumps(complement, ensure_ascii=False), encoding="utf-8"
                    )
                exporter_zip(job.directory, job.directory / "archive.zip", inclure_mp4=job.settings.telecharger_mp4)
                job.archive_prete = True
            except Exception:
                LOG.exception("Export enrichi impossible")
                final_message += " L’archive enrichie n’a pas pu être finalisée ; le TXT reste disponible."
        job.update(status=final_status, message=final_message, busy=False,
                   finished=time.monotonic(), frame=b"")
        job.sauvegarder_historique()
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

    def start(self, owner, settings, owner_historique=""):
        from collecte.quotas_exploitation import (
            max_publications, max_sources, max_commentaires
        )
        if settings.collecter_commentaires and settings.limite_commentaires > max_commentaires():
            raise HTTPException(422, f"Borne technique du moteur : "
                f"{max_commentaires()} commentaires par publication.")
        if settings.limit > max_publications():
            raise HTTPException(422,
                f"Borne technique du moteur : {max_publications()} publications par source.")
        nombre_sources = (len(settings.medias) if settings.source_collecte=="presse"
                          else len(settings.comptes) if settings.source_collecte=="comptes"
                          else len(settings.hashtags))
        if nombre_sources > max_sources():
            raise HTTPException(422,
                f"Borne technique du moteur : {max_sources()} sources par collecte.")
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
            self.jobs[job.id] = job
            job.thread = threading.Thread(target=self.runner, args=(job,), daemon=True)
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
            if job is not None and job.owner == owner and not job.historique:
                return job
            params = StartRequest.model_validate(manifeste["parametres"])
            job = Job(owner, params, self.data_dir, identifiant=identifiant,
                      archive_directory=dossier, owner_historique=cookie)
            def charger(nom):
                chemin = dossier / nom
                return json.loads(chemin.read_text(encoding="utf-8")) if chemin.is_file() else []
            job.publications=charger("publications.json")
            job.records=[p for p in job.publications if p.get("retenue")]
            job.commentaires=charger("commentaires.json")
            job.processed=int(manifeste.get("traites",0))
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
                if job.busy or job.video_busy:
                    from ticket_gate import verifier_session_active
                    if not verifier_session_active(job.owner):
                        job.demander_arret("acces_inactif")
                        job.video_stop.set()
                if job.busy:
                    job.limites_debug={'inactivite_max_s':self.idle_timeout,'duree_max_s':self.max_duration}
                    if now-job.created > self.max_duration:
                        job.demander_arret('duree_maximale')
                    elif now-job.last_seen > self.idle_timeout:
                        job.demander_arret('inactivite')
                if job.video_busy and (now-job.last_seen>self.idle_timeout or now-job.video_debut>7200):
                    job.video_stop.set()
                if not job.busy and not job.video_busy and job.finished is not None and now - job.finished > self.retention:
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
        yield
        manager.shutdown()

    app = FastAPI(title="ScrapTikTok", lifespan=lifespan, docs_url=None, redoc_url=None)
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
        return {"status": "ok", "version_presse": VERSION_PRESSE}

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
                                max_age=90*86400)
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
        anotables=publications_annotables(
            lire_publications(job.directory), [*lignes,*sans_resultat])
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
            headers={"Content-Disposition":
                     f'attachment; filename="scraptiktok_tableau_complet_{job.id}.csv"'})

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
            headers={"Content-Disposition":'attachment; filename="codages_videos.csv"'})

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
            headers={"Content-Disposition":'attachment; filename="annotations_violence.csv"'})

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
            headers={"Content-Disposition":'attachment; filename="correlations_violence.csv"'})

    @app.get("/api/jobs/{job_id}/desordre/export/{nom}")
    def exporter_desordre(job_id: str, nom: str, request: Request):
        job=manager.get(owner(request),job_id)
        from analyse_desordre.service import lire_etat, FICHIERS_EXPORTABLES
        etat=lire_etat(job.directory);dossier=dossier_desordre(job,etat)
        if dossier is None or nom not in FICHIERS_EXPORTABLES or (etat['statut'] not in ('termine','partiel') and nom != 'indicateurs_engagement.csv'):
            raise HTTPException(404, 'Export indisponible')
        chemin=dossier/nom
        if not chemin.is_file() or chemin.is_symlink(): raise HTTPException(404, 'Export indisponible')
        return FileResponse(chemin,filename=nom)

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
    def telecharger_archive(job_id: str, request: Request, supprimer_arobase_profil: bool = False):
        job = manager.get(owner(request), job_id)
        if job.busy or job.video_busy or not job.archive_prete:
            raise HTTPException(409, "L’archive enrichie n’est pas encore disponible.")
        if job.historique:
            from stockage.historique_analyses import exporter_zip
            flux=exporter_zip(job.directory)
            return StreamingResponse(iter(lambda: flux.read(65536), b""), media_type="application/zip",
                headers={"Content-Disposition":f'attachment; filename="scraptiktok_{job.id}_historique.zip"'},
                background=BackgroundTask(flux.close))
        if supprimer_arobase_profil:
            from corpus.export_zip import archive_avec_texte
            contenu = job.texte_a_exporter(supprimer_arobase_profil=True).encode("utf-8")
            flux = archive_avec_texte(job.directory / "archive.zip", contenu)
            return StreamingResponse(iter(lambda: flux.read(65536), b""), media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="scraptiktok_{job.id}.zip"'},
                background=BackgroundTask(flux.close))
        return FileResponse(job.directory / "archive.zip", filename=f"scraptiktok_{job.id}.zip", media_type="application/zip")

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
                publications=[{**p,**{k:visuelles.get(str(p['id']),{}).get(k)
                                      for k in ('groupe_visuel','reemploi_visuel')}} for p in publications]
            contenu = serialiser_csv(lignes_engagement(publications), COLONNES_ENGAGEMENT)
        return Response(contenu.encode("utf-8-sig"), media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="engagement.csv"'})

    @app.get("/api/jobs/{job_id}/commentaires.txt")
    def telecharger_commentaires(job_id: str, request: Request):
        job = manager.get(owner(request), job_id)
        with job.lock:
            retenues = {p["id"]: p for p in job.records}
            blocs = [f"*id_{c['publication_id']}\n@{c.get('auteur') or 'inconnu'}\n{c['texte']}"
                for c in job.commentaires if c["publication_id"] in retenues]
        return Response("\n\n".join(blocs) + ("\n" if blocs else ""), media_type="text/plain",
            headers={"Content-Disposition": 'attachment; filename="commentaires.txt"'})

    @app.get("/api/historique")
    def historique_analyses(request: Request):
        from stockage.historique_analyses import lister, retention_jours
        return {"analyses":lister(manager.data_dir, owner_historique(request)),
                "retention_jours":retention_jours()}

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
            headers={"Content-Disposition":f'attachment; filename="scraptiktok_analyse_{identifiant}.zip"'},
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
        return FileResponse(chemin, media_type="application/zip",
            filename=f"scraptiktok_sauvegarde_{identifiant}.zip")

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
    def download(job_id: str, request: Request, supprimer_arobase_profil: bool = False):
        job = manager.get(owner(request), job_id)
        if not job.path.exists() or not job.records:
            raise HTTPException(409, "Aucun texte n’est encore disponible.")
        filename = job.settings.filename
        contenu = (job.texte_a_exporter(supprimer_arobase_profil=True).encode("utf-8")
                   if supprimer_arobase_profil else job.path.read_bytes())
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


