"""Gestes humains et captures Playwright pour la fenêtre existante de ScrapTikTok."""
import scraptiktok as moteur


class ControlePlaywright:
    """Adapter l'interface de contrôle, sans lancer un deuxième navigateur."""

    def __init__(self, client):
        self.client = client
        self.pointeur_enfonce = False

    def nature_intervention(self):
        """Examiner la page et les cadres visibles ; donner priorité au CAPTCHA."""
        from .presse_playwright import _script
        from playwright.sync_api import Error
        nature = ""
        for cadre in self.client.page.frames[:13]:
            try:
                if cadre != self.client.page.main_frame and not cadre.frame_element().is_visible():
                    continue
                resultat = _script(cadre, moteur.TYPE_INTERVENTION_JS)
            except Error:
                continue  # Un cadre détaché sera réexaminé à la prochaine capture.
            if resultat == "captcha":
                return resultat
            if resultat == "connexion":
                nature = resultat
        return nature

    def fermer_invitation(self):
        """Utiliser uniquement le bouton de fermeture proposé par TikTok."""
        from .presse_playwright import _script
        if self.nature_intervention() == "connexion":
            _script(self.client.page, "const bouton = (function() {" +
                    moteur.FERMETURE_CONNEXION_JS + "})(); if (bouton) bouton.click();")

    def get_screenshot_as_png(self):
        """Capture en mémoire, jamais sauvegardée dans les exports."""
        return self.client.page.screenshot(type="png", timeout=5000)

    def liberer_pointeur(self):
        """Relâcher aussi lors d'un arrêt, d'une erreur ou d'un geste interrompu."""
        if self.pointeur_enfonce:
            self.client.page.mouse.up()
            self.pointeur_enfonce = False

    def effectuer_geste(self, action):
        """Rejouer exclusivement les coordonnées et touches envoyées par l'utilisateur."""
        page = self.client.page
        largeur, hauteur = page.evaluate("() => [innerWidth, innerHeight]")

        def deplacer(point):
            page.mouse.move(max(0, min(largeur - 1, round(point.x * largeur))),
                            max(0, min(hauteur - 1, round(point.y * hauteur))))

        if action.kind == "pointer_cancel":
            self.liberer_pointeur()
        elif action.kind in {"click", "drag", "pointer_down", "pointer_move", "pointer_up"}:
            if not action.points:
                raise ValueError("Le geste ne contient aucune position.")
            deplacer(action.points[0])
            if action.kind in {"click", "drag", "pointer_down"}:
                page.mouse.down()
                self.pointeur_enfonce = True
            if action.kind == "drag":
                for point in action.points[1:]:
                    deplacer(point)
            if action.kind in {"click", "drag", "pointer_up"}:
                self.liberer_pointeur()
        elif action.kind == "text":
            page.keyboard.insert_text(action.text)
        elif action.kind == "key":
            page.keyboard.press("ControlOrMeta+a" if action.key == "select_all" else action.key)
        else:
            page.mouse.wheel(0, action.delta)
