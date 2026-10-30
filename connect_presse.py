"""Collecte Presse : Selenium, Playwright, API web secUid, Research."""
from collecte.presse import selectionner_medias
from collecte.session_navigateur import SessionNavigateur
from collecte.verification_comptes import normaliser_compte


class ConnexionPresse(SessionNavigateur):
    mode = "presse"

    def preparer_sources(self, parametres):
        medias = selectionner_medias(parametres.medias)
        if not medias:
            raise ValueError("Sélectionnez au moins un média.")
        self.medias_selectionnes = {m["id"]: dict(m) for m in medias}
        self.moteur_collecte = parametres.presse_moteur
        self.research_debut = parametres.date_debut
        self.research_fin = parametres.date_fin
        self.commentaires_research = bool(parametres.collecter_commentaires)
        self.resume_research = bool(getattr(parametres, "inclure_texte_genere_ia", False))
        self.research_credentiels = None
        self.playwright_client = None
        if self.moteur_collecte == "research":
            cle = (parametres.research_client_key.get_secret_value().strip()
                   if parametres.research_client_key else "")
            secret = (parametres.research_client_secret.get_secret_value().strip()
                      if parametres.research_client_secret else "")
            if cle and secret:
                self.research_credentiels = (cle, secret)
        return [dict(m) for m in medias]

    def ouvrir(self):
        """Research sans Chrome, sauf demande de commentaires ou de résumés IA."""
        if self.moteur_collecte == "playwright":
            from collecte.presse_playwright import PressePlaywright
            self.playwright_client = PressePlaywright(self.arguments, self.verifier)
            self.playwright_client.ouvrir()
            # Le navigateur Selenium n’est nécessaire qu’aux commentaires.
            return super().ouvrir() if self.commentaires_research else None
        if self.moteur_collecte == "research" and not self.commentaires_research and not self.resume_research:
            if self.verifier:
                self.verifier()
            return None
        return super().ouvrir()

    def options_decouverte(self, rapport, contexte="", progression=None):
        if self.moteur_collecte == "playwright":
            if self.verifier:
                self.verifier()
            rapport["connexion"] = {"mode": "presse", "module": type(self).__module__,
                                   "navigateur_decouverte": "playwright", "anonyme": True}
            return {"check": self.verifier, "progress": progression}
        if self.moteur_collecte != "research":
            return super().options_decouverte(rapport, contexte, progression)
        if self.verifier:
            self.verifier()
        rapport["connexion"] = {"mode": "presse",
                               "module": type(self).__module__,
                               "api": "Research API officielle",
                               "navigateur_decouverte": False}
        return {"check": self.verifier, "progress": progression,
                "research_debut": self.research_debut,
                "research_fin": self.research_fin,
                "research_credentiels": self.research_credentiels}

    def decouvrir(self, source, rapport, *, contexte="", progression=None):
        from collecte.comptes import collecter_compte
        media = getattr(self, "medias_selectionnes", {}).get(source.get("id"))
        if media is None or normaliser_compte(source["compte"]) != media["compte"]:
            raise ValueError("Ce compte ne correspond pas à un média sélectionné.")
        if self.moteur_collecte == "playwright":
            rapport.update(media_id=media["id"], compte_selectionne=media["compte"],
                           version_collecteur="playwright-presse-v2-attente", presse_moteur="playwright")
            self.options_decouverte(rapport, contexte, progression)
            return self.playwright_client.decouvrir(media["compte"], rapport, progression)
        if self.moteur_collecte == "research":
            from collecte.presse_research import VERSION_RESEARCH
            version = VERSION_RESEARCH
        elif self.moteur_collecte == "navigateur":
            version = "selenium-presse-v2-attente"
        else:
            from collecte.presse_api import VERSION_PRESSE
            version = VERSION_PRESSE
        rapport.update(media_id=media["id"], compte_selectionne=media["compte"],
                       version_collecteur=version, presse_moteur=self.moteur_collecte)
        navigateur = (self.obtenir_navigateur()
                      if self.moteur_collecte != "research" or self.commentaires_research
                      else None)
        return collecter_compte(navigateur, self.arguments, media["compte"],
            rapport=rapport, hashtags=(), presse_videos_uniquement=True,
            presse_moteur=self.moteur_collecte,
            **self.options_decouverte(rapport, contexte, progression))


    def lire_publication(self, url):
        if self.moteur_collecte == "playwright":
            return self.playwright_client.lire(url)
        return super().lire_publication(url)

    def fermer(self):
        try:
            client = getattr(self, "playwright_client", None)
            if client is not None:
                client.fermer()
                self.playwright_client = None
        finally:
            super().fermer()
