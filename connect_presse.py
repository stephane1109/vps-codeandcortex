"""Parcours Selenium anonyme propre aux médias cochés dans Presse/médias."""
from collecte.presse import selectionner_medias
from collecte.session_navigateur import SessionNavigateur
from collecte.verification_comptes import normaliser_compte


class ConnexionPresse(SessionNavigateur):
    mode = "presse"

    def preparer_sources(self, parametres):
        """Résoudre uniquement les médias cochés dans l’inventaire de presse."""
        medias = selectionner_medias(parametres.medias)
        if not medias:
            raise ValueError("Sélectionnez au moins un média.")
        self.medias_selectionnes = {media["id"]: dict(media) for media in medias}
        self.moteur_collecte = parametres.presse_moteur
        self.commentaires_tikwm = bool(parametres.collecter_commentaires)
        return [dict(media) for media in medias]

    def ouvrir(self):
        """Ouvrir Chrome pour TikWM uniquement si les commentaires sont demandés."""
        if self.moteur_collecte == "tikwm" and not self.commentaires_tikwm:
            if self.verifier:
                self.verifier()
            return None
        return super().ouvrir()

    def options_decouverte(self, rapport, contexte="", progression=None):
        """Découvrir par TikWM sans utiliser le navigateur Selenium."""
        if self.moteur_collecte != "tikwm":
            return super().options_decouverte(rapport, contexte, progression)
        if self.verifier:
            self.verifier()
        rapport["connexion"] = {"mode": "presse", "module": type(self).__module__,
                               "tiers": "TikWM", "navigateur_decouverte": False}
        return {"check": self.verifier, "progress": progression}

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Parcourir uniquement les comptes de médias, sans filtre de hashtag."""
        from collecte.comptes import collecter_compte

        media = getattr(self, "medias_selectionnes", {}).get(source.get("id"))
        if media is None or normaliser_compte(source["compte"]) != media["compte"]:
            raise ValueError("Ce compte ne correspond pas à un média sélectionné.")
        from collecte.presse_api import VERSION_PRESSE
        from collecte.presse_tikwm import VERSION_TIKWM
        version = VERSION_TIKWM if self.moteur_collecte == "tikwm" else VERSION_PRESSE
        rapport.update(media_id=media["id"], compte_selectionne=media["compte"],
                       version_collecteur=version,
                       presse_moteur=self.moteur_collecte)
        navigateur = (self.obtenir_navigateur()
                      if self.moteur_collecte != "tikwm" or self.commentaires_tikwm
                      else None)
        return collecter_compte(navigateur, self.arguments, media["compte"],
            rapport=rapport, hashtags=(),
            presse_videos_uniquement=True,
            presse_moteur=self.moteur_collecte,
            **self.options_decouverte(rapport, contexte, progression))
