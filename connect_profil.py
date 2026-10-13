"""Parcours Selenium anonyme propre aux profils saisis par l’utilisateur."""
from collecte.session_navigateur import SessionNavigateur
from collecte.verification_comptes import normaliser_compte
from scraptiktok import normalize_hashtag


class ConnexionProfil(SessionNavigateur):
    mode = "comptes"

    def preparer_sources(self, parametres):
        """Accepter les identifiants avec ou sans @, indépendamment de la presse."""
        self.hashtags = tuple(dict.fromkeys(normalize_hashtag(h) for h in parametres.hashtags))
        if not self.hashtags:
            raise ValueError("Renseignez au moins un hashtag pour les profils sélectionnés.")
        self.comptes_selectionnes = tuple(dict.fromkeys(normaliser_compte(c) for c in parametres.comptes))
        if not self.comptes_selectionnes:
            raise ValueError("Renseignez au moins un compte TikTok.")
        return [{"compte": compte, "id": None, "categorie": None} for compte in self.comptes_selectionnes]

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Rechercher les vidéos du compte, avec vérification stricte de l’auteur."""
        from collecte.comptes import collecter_compte

        compte = normaliser_compte(source["compte"])
        if compte not in getattr(self, "comptes_selectionnes", ()):
            raise ValueError("Ce profil ne fait pas partie des comptes sélectionnés.")
        rapport["compte_selectionne"] = compte
        return collecter_compte(self.obtenir_navigateur(), self.arguments, compte,
            rapport=rapport, hashtags=list(self.hashtags),
            **self.options_decouverte(rapport, contexte, progression))
