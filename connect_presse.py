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
        return [dict(media) for media in medias]

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Parcourir uniquement les comptes de médias, sans filtre de hashtag."""
        from collecte.comptes import collecter_compte

        media = getattr(self, "medias_selectionnes", {}).get(source.get("id"))
        if media is None or normaliser_compte(source["compte"]) != media["compte"]:
            raise ValueError("Ce compte ne correspond pas à un média sélectionné.")
        rapport.update(media_id=media["id"], compte_selectionne=media["compte"])
        return collecter_compte(self.obtenir_navigateur(), self.arguments, media["compte"],
            rapport=rapport, hashtags=(),
            presse_videos_uniquement=True,
            **self.options_decouverte(rapport, contexte, progression))
