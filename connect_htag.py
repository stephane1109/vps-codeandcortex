"""Parcours Selenium anonyme propre au mode Hashtags."""
from urllib.parse import quote

from collecte.session_navigateur import SessionNavigateur
from scraptiktok import normalize_hashtag


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
        for hashtag in demandes:
            for variante in variantes_hashtag(
                    hashtag, avec_accents=parametres.variantes_accents):
                if variante.casefold() not in vus:
                    vus.add(variante.casefold())
                    sources.append({"hashtag": variante, "hashtag_demande": hashtag})
        self.hashtags = tuple(s["hashtag"] for s in sources)
        return sources

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Ouvrir la page du hashtag et employer son défilement existant."""
        from collecte.hashtags import collecter_hashtag

        hashtag = normalize_hashtag(source["hashtag"])
        if hashtag not in getattr(self, "hashtags", ()):
            raise ValueError("Ce hashtag ne fait pas partie de la recherche.")
        rapport["hashtag_url"] = "https://www.tiktok.com/tag/" + quote(hashtag)
        return collecter_hashtag(self.obtenir_navigateur(), self.arguments, rapport,
            **self.options_decouverte(rapport, contexte, progression))
