"""Connexion manuelle éphémère ; aucun identifiant ni cookie n'est lu ou exporté."""
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException, WebDriverException


CONNEXION_OUVERTE_JS = """
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
// Examiner uniquement la présence des contrôles, jamais leur valeur.
return location.pathname === '/login' || location.pathname.startsWith('/login/') ||
    Array.from(document.querySelectorAll('[data-e2e="login-modal"], input[type="password"], iframe[src*="/login"]')).some(visible);
"""


def connexion_ouverte(navigateur):
    """Inclure les pages de connexion complètes, pas seulement la modale TikTok."""
    return navigateur.execute_script(CONNEXION_OUVERTE_JS) is True


def est_erreur_session(erreur):
    """Classer sans conserver le message Selenium, qui peut contenir des données privées."""
    return isinstance(erreur, (InvalidSessionIdException, NoSuchWindowException))


def ouvrir_connexion(navigateur, intervenir, verifier):
    """L'utilisateur valide sur son téléphone ; l'application n'a aucun champ secret."""
    import scraptiktok as moteur
    verifier()
    moteur.open_page(navigateur, "https://www.tiktok.com/login")
    intervenir("Se connecter à TikTok : choisissez le QR code s’il est proposé, scannez-le avec "
               "TikTok sur votre téléphone et confirmez-y la connexion. Cliquez ensuite sur Continuer. "
               "Aucun identifiant, mot de passe ou code ne doit être saisi dans cette application. "
               "Si le QR code est indisponible, arrêtez cette collecte et relancez en mode anonyme.")
    verifier()


def detruire_session(navigateur, profil):
    """Fermer tous les onglets et supprimer le profil temporaire, même après une erreur."""
    ferme = True
    if navigateur is not None:
        try:
            # Suppression globale dans ce navigateur uniquement, sans lecture des cookies.
            navigateur.execute_cdp_cmd("Network.clearBrowserCookies", {})
        except WebDriverException:
            try:
                navigateur.delete_all_cookies()
            except WebDriverException:
                pass
        try:
            navigateur.quit()
        except WebDriverException:
            ferme = False
    if profil is not None:
        try:
            profil.cleanup()
        except OSError:
            ferme = False
    return ferme
