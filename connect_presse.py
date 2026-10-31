"""Collecte Presse : Selenium, gallery-dl, API web, Research, TikHub et Apify."""
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
        self.gallerydl_client = None
        self.tikhub_client = None
        self.tikhub_cle = None
        self.apify_client = None
        self.apify_cle = None
        if self.moteur_collecte == "apify":
            secret = getattr(parametres, "apify_api_token", None)
            self.apify_cle = secret.get_secret_value().strip() if secret else None
        if self.moteur_collecte == "tikhub":
            secret = getattr(parametres, "tikhub_api_key", None)
            self.tikhub_cle = secret.get_secret_value().strip() if secret else None
        self.cookies_fournis = None
        secret_cookies = getattr(parametres, "cookies_tiktok", None)
        if secret_cookies and self.moteur_collecte == "navigateur":
            from collecte.cookies_presse import charger_cookies_presse
            self.cookies_fournis = charger_cookies_presse(secret_cookies.get_secret_value())
        if self.moteur_collecte == "research":
            cle = (parametres.research_client_key.get_secret_value().strip()
                   if parametres.research_client_key else "")
            secret = (parametres.research_client_secret.get_secret_value().strip()
                      if parametres.research_client_secret else "")
            if cle and secret:
                self.research_credentiels = (cle, secret)
        return [dict(m) for m in medias]

    def ouvrir(self):
        """Les moteurs API n'ouvrent Chrome que pour les fonctions nécessaires."""
        if self.moteur_collecte == "apify":
            from collecte.presse_apify import PresseApify
            self.apify_client = PresseApify(self.arguments, self.apify_cle, self.verifier)
            # Les vidéos et métadonnées sont fournies par Apify. Les options
            # de commentaires et de résumés IA restent distinctes via Selenium.
            return super().ouvrir() if (self.commentaires_research or self.resume_research) else None
        if self.moteur_collecte == "tikhub":
            from collecte.presse_tikhub import PresseTikHub
            self.tikhub_client = PresseTikHub(self.arguments, self.tikhub_cle, self.verifier)
            # Le résumé IA TikHub provient de l'API ; Selenium sert uniquement
            # aux commentaires explicitement demandés.
            return super().ouvrir() if self.commentaires_research else None
        if self.moteur_collecte == "gallerydl":
            from collecte.presse_gallerydl import PresseGalleryDL
            self.gallerydl_client = PresseGalleryDL(self.arguments, self.verifier)
            # Un navigateur Selenium n'est nécessaire que pour les commentaires
            # ou les synthèses IA affichées dans la vidéo.
            return super().ouvrir() if (self.commentaires_research or self.resume_research) else None
        if self.moteur_collecte == "research" and not self.commentaires_research and not self.resume_research:
            if self.verifier:
                self.verifier()
            return None
        navigateur = super().ouvrir()
        if self.moteur_collecte != "research":
            from collecte.cookies_presse import appliquer_cookies_selenium
            self.nombre_cookies_importes = appliquer_cookies_selenium(navigateur, self.cookies_fournis)
        return navigateur

    def options_decouverte(self, rapport, contexte="", progression=None):
        if self.moteur_collecte == "apify":
            if self.verifier:
                self.verifier()
            rapport["connexion"] = {"mode": "presse", "module": type(self).__module__,
                                   "navigateur_decouverte": False, "api": "Apify",
                                   "cle_configuree": True}
            return {"check": self.verifier, "progress": progression}
        if self.moteur_collecte == "tikhub":
            if self.verifier:
                self.verifier()
            rapport["connexion"] = {"mode": "presse", "module": type(self).__module__,
                                    "navigateur_decouverte": False,
                                    "api": "TikHub", "cle_configuree": True}
            return {"check": self.verifier, "progress": progression}
        if self.moteur_collecte == "gallerydl":
            if self.verifier:
                self.verifier()
            rapport["connexion"] = {"mode": "presse", "module": type(self).__module__,
                                   "navigateur_decouverte": False, "outil": "gallery-dl"}
            return {"check": self.verifier, "progress": progression}
        if self.moteur_collecte != "research":
            options = super().options_decouverte(rapport, contexte, progression)
            rapport["connexion"].pop("anonyme", None)
            rapport["connexion"]["cookies_configures"] = bool(getattr(self, "nombre_cookies_importes", 0))
            return options
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
        if self.moteur_collecte == "apify":
            from collecte.presse_apify import VERSION_APIFY
            rapport.update(media_id=media["id"], compte_selectionne=media["compte"],
                           version_collecteur=VERSION_APIFY, presse_moteur="apify")
            self.options_decouverte(rapport, contexte, progression)
            return self.apify_client.decouvrir(media["compte"], rapport, progression)
        if self.moteur_collecte == "tikhub":
            rapport.update(media_id=media["id"], compte_selectionne=media["compte"],
                           version_collecteur="tikhub-presse-v1", presse_moteur="tikhub")
            self.options_decouverte(rapport, contexte, progression)
            return self.tikhub_client.decouvrir(media["compte"], rapport, progression)
        if self.moteur_collecte == "gallerydl":
            rapport.update(media_id=media["id"], compte_selectionne=media["compte"],
                           version_collecteur="gallerydl-presse-v2-liste-directe", presse_moteur="gallerydl")
            self.options_decouverte(rapport, contexte, progression)
            return self.gallerydl_client.decouvrir(media["compte"], rapport, progression)
        if self.moteur_collecte == "research":
            from collecte.presse_research import VERSION_RESEARCH
            version = VERSION_RESEARCH
        elif self.moteur_collecte == "navigateur":
            version = "selenium-presse-v3-reseau"
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
        if self.moteur_collecte == "tikhub":
            return self.tikhub_client.lire_resume(url)
        return super().lire_publication(url)

    def fermer(self):
        self.cookies_fournis = None
        self.tikhub_cle = None
        self.apify_cle = None
        try:
            client_apify = getattr(self, "apify_client", None)
            if client_apify is not None:
                client_apify.fermer()
                self.apify_client = None
            client_tikhub = getattr(self, "tikhub_client", None)
            if client_tikhub is not None:
                client_tikhub.fermer()
                self.tikhub_client = None
            client_gallerydl = getattr(self, "gallerydl_client", None)
            if client_gallerydl is not None:
                client_gallerydl.fermer()
                self.gallerydl_client = None
        finally:
            super().fermer()
