"""Parcours Selenium anonyme propre au mode Hashtags."""
from urllib.parse import quote

from collecte.session_navigateur import SessionNavigateur
from scraptiktok import normalize_hashtag


class ConnexionHashtag(SessionNavigateur):
    mode = "hashtags"

    def preparer_sources(self, parametres):
        """Conserver les hashtags saisis, sans restriction de compte."""
        self.hashtags = tuple(dict.fromkeys(normalize_hashtag(h) for h in parametres.hashtags))
        if not self.hashtags:
            raise ValueError("Renseignez au moins un hashtag.")
        return [{"hashtag": hashtag} for hashtag in self.hashtags]

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Ouvrir la page du hashtag et employer son défilement existant."""
        from collecte.hashtags import collecter_hashtag

        hashtag = normalize_hashtag(source["hashtag"])
        if hashtag not in getattr(self, "hashtags", ()):
            raise ValueError("Ce hashtag ne fait pas partie de la recherche.")
        rapport["hashtag_url"] = "https://www.tiktok.com/tag/" + quote(hashtag)
        return collecter_hashtag(self.obtenir_navigateur(), self.arguments, rapport,
            **self.options_decouverte(rapport, contexte, progression))
