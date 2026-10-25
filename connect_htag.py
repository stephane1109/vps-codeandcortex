"""Parcours Selenium anonyme propre au mode Hashtags."""
from urllib.parse import quote
import copy
import math

from collecte.session_navigateur import SessionNavigateur
from scraptiktok import normalize_hashtag, canonical_post


class ConnexionHashtag(SessionNavigateur):
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
        self._quota_hashtag = {
            demande: parametres.limit // nombre_demandes
                    + int(rang < parametres.limit % nombre_demandes)
            for rang, demande in enumerate(demandes)
        }
        for hashtag in demandes:
            variantes = variantes_hashtag(
                hashtag, avec_accents=parametres.variantes_accents)
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
        return sources

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
                             self.arguments.limit - len(self._ids_globaux)))
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
        trouves = collecter_hashtag(self.obtenir_navigateur(), arguments, rapport,
            **self.options_decouverte(rapport, contexte, progression))
        nouveaux = []
        for adresse in trouves:
            identite = canonical_post(adresse)
            if (identite and identite[0] not in self._ids_globaux
                    and len(retenus) < objectif_tag
                    and len(self._ids_globaux) < self.arguments.limit):
                retenus.add(identite[0])
                self._ids_globaux.add(identite[0])
                nouveaux.append(identite[1])
        rapport["discovered_urls"] = nouveaux
        rapport["objectif_hashtag_initial"] = objectif_tag
        rapport["objectif_total_collecte"] = self.arguments.limit
        rapport["retenues_hashtag_initial"] = len(retenus)
        return nouveaux
