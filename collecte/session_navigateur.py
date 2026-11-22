"""Cycle de vie commun du navigateur anonyme, sans sélection de source.

Les parcours hashtag, presse et profil sont définis dans les modules connect_*.
Cette classe ne crée ni serveur, ni navigateur au moment de son import.
"""
import scraptiktok as moteur


class SessionNavigateur:
    """Conserver un seul pilote et une validation initiale pour toute la collecte."""

    def __init__(self, arguments, *, fabrique=None, interaction=None, verifier=None):
        self.arguments = arguments
        self.fabrique = fabrique if fabrique is not None else moteur.create_driver
        self.interaction = interaction
        self.verifier = verifier
        self.navigateur = None
        self.validation_effectuee = False
        self.fermee = False

    def ouvrir(self):
        """Créer le navigateur une seule fois, quel que soit le nombre de sources."""
        if self.fermee:
            raise RuntimeError("Cette session de collecte est terminée.")
        if self.verifier:
            self.verifier()
        if self.navigateur is None:
            self.navigateur = self.fabrique(self.arguments)
        return self.navigateur

    def obtenir_navigateur(self):
        """Ne jamais relancer un navigateur pendant une découverte ou une lecture."""
        if self.navigateur is None or self.fermee:
            raise RuntimeError("Le navigateur de cette collecte n’est pas ouvert.")
        return self.navigateur

    def intervenir(self, message, contexte=""):
        """Transmettre la vérification manuelle au contrôle du même navigateur."""
        navigateur = self.obtenir_navigateur()
        if self.verifier:
            self.verifier()
        message = f"{contexte} : {message}" if contexte else message
        if self.interaction is None:
            moteur.manual_step(message)
        else:
            self.interaction(navigateur, message)
        # Une intervention interrompue ne valide pas la session.
        self.validation_effectuee = True

    def options_decouverte(self, rapport, contexte="", progression=None):
        """Partager l’état du CAPTCHA, sans introduire de connexion à un compte."""
        self.obtenir_navigateur()
        if self.verifier:
            self.verifier()
        rapport["connexion"] = {"mode": self.mode, "module": type(self).__module__, "anonyme": True}
        return {
            "interact": lambda message: self.intervenir(message, contexte),
            "check": self.verifier,
            "validation_initiale": not self.validation_effectuee,
            "progress": progression,
            "sans_connexion": True,
        }

    def lire_publication(self, url):
        """Lire chaque publication avec le pilote utilisé pour sa découverte."""
        navigateur = self.obtenir_navigateur()
        if self.verifier:
            self.verifier()
        return moteur.read_post(navigateur, url, self.arguments,
            interact=self.intervenir, check=self.verifier, sans_connexion=True)

    def fermer(self):
        """Détruire le navigateur, sans sauvegarde de cookies ou de profil Chrome."""
        navigateur, self.navigateur = self.navigateur, None
        self.fermee = True
        if navigateur is not None:
            navigateur.quit()
