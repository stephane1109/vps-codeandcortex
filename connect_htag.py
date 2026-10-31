"""Parcours Selenium anonyme propre au mode Hashtags."""
from urllib.parse import quote
import copy
import math

from collecte.session_navigateur import SessionNavigateur
from connect_presse import ConnexionPresse
from scraptiktok import normalize_hashtag, canonical_post


class ConnexionHashtag(ConnexionPresse):
    mode = "hashtags"

    def preparer_sources(self, parametres):
        """Conserver les hashtags saisis, sans restriction de compte."""
        from collecte.hashtags import variantes_hashtag
        demandes = tuple(dict.fromkeys(normalize_hashtag(h) for h in parametres.hashtags))
        if not demandes:
            raise ValueError("Renseignez au moins un hashtag.")
        # Les pages proposées par TikTok sont explorées avec un budget borné.
        # Chaque vidéo sera revérifiée à partir de ses hashtags réels.
        sources = []
        vus = set()
        self._ids_par_hashtag = {demande: set() for demande in demandes}
        self._ids_globaux = set()
        # Le nombre demandé concerne l'ensemble du corpus. Deux hashtags
        # se partagent ce budget en ET comme en OU (la règle intervient après
        # lecture des légendes). Les variantes utilisent le quota de leur tag.
        nombre_demandes = len(demandes)
        # Avec un filtre de dates, explorer davantage de candidats que le nombre
        # de résultats demandé ; seules les dates vérifiées seront retenues.
        self._budget_decouverte = (min(parametres.limit * 5, 500)
                                  if (getattr(parametres, "date_debut", None)
                                      or getattr(parametres, "date_fin", None))
                                  else parametres.limit)
        self._quota_hashtag = {
            demande: self._budget_decouverte // nombre_demandes
                    + int(rang < self._budget_decouverte % nombre_demandes)
            for rang, demande in enumerate(demandes)
        }
        for hashtag in demandes:
            variantes = variantes_hashtag(
                hashtag, avec_accents=getattr(parametres, "variantes_accents", False))
            # Supprimer les doublons entre recherches sans perdre le tag initial.
            distinctes = []
            for variante in variantes:
                cle = variante.casefold()
                if cle not in vus:
                    vus.add(cle)
                    distinctes.append(variante)
            variantes = distinctes
            for rang, variante in enumerate(variantes):
                sources.append({
                    "hashtag": variante, "hashtag_demande": hashtag,
                    "variantes_restantes": len(variantes) - rang,
                })
        self.hashtags = tuple(s["hashtag"] for s in sources)
        self.configurer_moteur(parametres, getattr(parametres, "hashtag_moteur", "navigateur"))
        self._cache_profils = set()
        self._metadonnees_profils = {}
        self._limite_profils_api = 10
        return sources

    def ouvrir(self):
        """Seule la Research API recherche directement un hashtag sans navigateur."""
        if self.moteur_collecte in {"tikhub", "gallerydl"}:
            super().ouvrir()
            return SessionNavigateur.ouvrir(self)
        return super().ouvrir()

    def _lire_profil_par_moteur(self, compte):
        """Enrichir via l'API au plus dix comptes distincts par collecte."""
        if compte in self._cache_profils or len(self._cache_profils) >= self._limite_profils_api:
            return
        self._cache_profils.add(compte)
        rapport = {}
        if self.moteur_collecte == "tikhub":
            self.tikhub_client.decouvrir(compte, rapport)
        elif self.moteur_collecte == "gallerydl":
            self.gallerydl_client.decouvrir(compte, rapport)
        else:
            from collecte.presse_api import collecter_videos_presse_api
            collecter_videos_presse_api(
                compte, min(self.arguments.limit, 100), rapport,
                check=self.verifier)
        self._metadonnees_profils.update(rapport.get("metadonnees_api") or {})

    def lire_publication(self, url):
        """Recherche hybride : découverte par hashtag, métadonnées par profil."""
        if self.moteur_collecte not in {"api", "gallerydl", "tikhub"}:
            return SessionNavigateur.lire_publication(self, url)
        identite = canonical_post(url)
        if identite is None:
            raise ValueError("URL de publication invalide.")
        identifiant, _, compte = identite
        self._lire_profil_par_moteur(compte)
        fiche = self._metadonnees_profils.get(identifiant)
        if not isinstance(fiche, dict) or fiche.get("author", "").casefold() != compte.casefold():
            resultat = SessionNavigateur.lire_publication(self, url)
            resultat["source"] = "selenium_secours_hashtag"
            return resultat
        resultat = dict(fiche)
        if self.resume_research:
            if self.moteur_collecte == "tikhub":
                resultat.update(self.tikhub_client.lire_resume(url))
            else:
                lecture = SessionNavigateur.lire_publication(self, url)
                for champ in ("resume_ia_tiktok", "statut_resume_ia",
                              "source_resume_ia", "titre_ia_tiktok",
                              "article_ia_tiktok", "mots_cles_ia_tiktok"):
                    if champ in lecture:
                        resultat[champ] = lecture[champ]
        return resultat


    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Ouvrir la page du hashtag et employer son défilement existant."""
        from collecte.hashtags import collecter_hashtag

        hashtag = normalize_hashtag(source["hashtag"])
        if hashtag not in getattr(self, "hashtags", ()):
            raise ValueError("Ce hashtag ne fait pas partie de la recherche.")
        rapport["hashtag_url"] = "https://www.tiktok.com/tag/" + quote(hashtag)
        demande = source.get("hashtag_demande", hashtag)
        retenus = self._ids_par_hashtag.setdefault(demande, set())
        objectif_tag = self._quota_hashtag.get(demande, self.arguments.limit)
        restant = max(0, min(objectif_tag - len(retenus),
                             self._budget_decouverte - len(self._ids_globaux)))
        if not restant:
            rapport.update(discovered_urls=[], discovery_stop="objectif_hashtag_atteint",
                           objectif_hashtag_initial=objectif_tag,
                           retenues_hashtag_initial=len(retenus),
                           bilan_recherche="Objectif global ou quota du hashtag déjà atteint.")
            return []

        # Partager l'objectif du hashtag saisi entre les variantes ; l'option
        # accents ne multiplie jamais le nombre total de vidéos du corpus.
        nombre_variantes = max(1, source.get("variantes_restantes", 1))
        arguments = copy.copy(self.arguments)
        arguments.limit = min(restant, max(1, math.ceil(restant / nombre_variantes)))
        if self.moteur_collecte == "research":
            from collecte.presse_research import collecter_videos_presse_research
            trouves = collecter_videos_presse_research(
                None, arguments.limit, rapport, hashtag=hashtag,
                debut=self.research_debut, fin=self.research_fin,
                check=self.verifier, progress=progression,
                credentiels=self.research_credentiels)
        else:
            trouves = collecter_hashtag(
                self.obtenir_navigateur(), arguments, rapport,
                **SessionNavigateur.options_decouverte(
                    self, rapport, contexte, progression))
        nouveaux = []
        for adresse in trouves:
            identite = canonical_post(adresse)
            if (identite and identite[0] not in self._ids_globaux
                    and len(retenus) < objectif_tag
                    and len(self._ids_globaux) < self._budget_decouverte):
                retenus.add(identite[0])
                self._ids_globaux.add(identite[0])
                nouveaux.append(identite[1])
        rapport["discovered_urls"] = nouveaux
        rapport["objectif_hashtag_initial"] = objectif_tag
        rapport["objectif_total_collecte"] = self._budget_decouverte
        rapport["retenues_hashtag_initial"] = len(retenus)
        return nouveaux
