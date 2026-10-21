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
        for hashtag in demandes:
            variantes = variantes_hashtag(
                hashtag, avec_accents=parametres.variantes_accents)
            # Supprimer les doublons entre recherches sans perdre le lien vers le tag initial.
            variantes = [v for v in variantes if v.casefold() not in vus
                         and not vus.add(v.casefold())]
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
        restant = max(0, self.arguments.limit - len(retenus))
        if not restant:
            rapport.update(discovered_urls=[], discovery_stop="objectif_hashtag_atteint",
                           bilan_recherche="Objectif déjà atteint pour le hashtag initial.")
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
            if identite and identite[0] not in retenus and len(retenus) < self.arguments.limit:
                retenus.add(identite[0])
                nouveaux.append(identite[1])
        rapport["discovered_urls"] = nouveaux
        rapport["objectif_hashtag_initial"] = self.arguments.limit
        rapport["retenues_hashtag_initial"] = len(retenus)
        return nouveaux
