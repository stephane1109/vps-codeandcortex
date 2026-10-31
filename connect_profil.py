"""Parcours profils : cinq moteurs avec sélection des comptes et filtres des légendes."""
from collecte.verification_comptes import normaliser_compte
from scraptiktok import normalize_hashtag
from connect_presse import ConnexionPresse


class ConnexionProfil(ConnexionPresse):
    mode = "comptes"

    def preparer_sources(self, parametres):
        """Conserver les filtres et les comptes saisis sans utiliser la liste Presse."""
        self.hashtags = tuple(dict.fromkeys(normalize_hashtag(h) for h in parametres.hashtags))
        if not self.hashtags:
            raise ValueError("Renseignez au moins un hashtag pour les profils sélectionnés.")
        self.comptes_selectionnes = tuple(dict.fromkeys(normaliser_compte(c) for c in parametres.comptes))
        if not self.comptes_selectionnes:
            raise ValueError("Renseignez au moins un compte TikTok.")
        self.configurer_moteur(parametres, getattr(parametres, "profil_moteur", "navigateur"))
        return [{"compte": compte, "id": None, "categorie": None}
                for compte in self.comptes_selectionnes]

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        """Vérifier le compte et ne jamais basculer vers un autre moteur."""
        from collecte.comptes import collecter_compte

        compte = normaliser_compte(source["compte"])
        if compte not in getattr(self, "comptes_selectionnes", ()):
            raise ValueError("Ce profil ne fait pas partie des comptes sélectionnés.")
        rapport.update(compte_selectionne=compte, moteur_collecte=self.moteur_collecte)
        if self.moteur_collecte == "tikhub":
            from collecte.presse_tikhub import VERSION_TIKHUB
            rapport["version_collecteur"] = VERSION_TIKHUB
            self.options_decouverte(rapport, contexte, progression)
            return self.tikhub_client.decouvrir(compte, rapport, progression)
        if self.moteur_collecte == "gallerydl":
            rapport["version_collecteur"] = "gallerydl-presse-v2-liste-directe"
            self.options_decouverte(rapport, contexte, progression)
            return self.gallerydl_client.decouvrir(compte, rapport, progression)
        if self.moteur_collecte == "research":
            from collecte.presse_research import VERSION_RESEARCH
            rapport["version_collecteur"] = VERSION_RESEARCH
        elif self.moteur_collecte == "api":
            from collecte.presse_api import VERSION_PRESSE
            rapport["version_collecteur"] = VERSION_PRESSE
        else:
            rapport["version_collecteur"] = "selenium-profil-v3"

        options = self.options_decouverte(rapport, contexte, progression)
        navigateur = (self.obtenir_navigateur() if self.moteur_collecte == "navigateur"
                      or self.commentaires_research or self.resume_research else None)
        supplement = ({"presse_videos_uniquement": True,
                        "presse_moteur": self.moteur_collecte}
                       if self.moteur_collecte != "navigateur" else {})
        return collecter_compte(
            navigateur, self.arguments, compte, rapport=rapport,
            hashtags=list(self.hashtags), **supplement, **options)
