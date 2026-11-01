"""Discrétisation reproductible des indicateurs TikTok pour IRaMuTeQ."""
import math


VARIABLES_CLASSES = ("vues", "likes", "commentaires", "partages", "favoris", "duree")
NOMS_CLASSES = {
    "vues": "vues_classe",
    "likes": "likes_classe",
    "commentaires": "commentaires_classe",
    "partages": "partages_classe",
    "favoris": "favoris_classe",
    "duree": "duree_classe",
}


def normaliser_nombre(valeur):
    """Préserver les vrais zéros, refuser les booléens et les inconnues."""
    if isinstance(valeur, bool) or valeur is None:
        return None
    if isinstance(valeur, str):
        valeur = valeur.strip()
        if not valeur.isdecimal():
            return None
        valeur = int(valeur)
    if isinstance(valeur, (int, float)) and math.isfinite(valeur) and valeur >= 0:
        return valeur
    return None


def lire_compteur(publication, nom):
    """Lire une observation numérique sans supposer un compteur absent égal à zéro."""
    engagement = publication.get("engagement") or {}
    mesure = engagement.get(nom)
    if not isinstance(mesure, dict):
        return None
    return normaliser_nombre(mesure.get("valeur"))


def calculer_taux_engagement(publication):
    """(likes + commentaires + partages + favoris) / vues × 100."""
    vues = lire_compteur(publication, "vues")
    if vues is None or vues <= 0:
        return None
    comptes = [lire_compteur(publication, nom)
               for nom in ("likes", "commentaires", "partages", "favoris")]
    if any(valeur is None for valeur in comptes):
        return None
    return 100.0 * sum(comptes) / vues


def classer_taux_engagement(taux):
    """Classes fixes de pourcentages avec bornes supérieures exclusives."""
    taux = normaliser_nombre(taux)
    if taux is None:
        return "engagement_indetermine"
    if taux < 1:
        return "engagement_moins_1pct"
    if taux < 3:
        return "engagement_1_3pct"
    if taux < 5:
        return "engagement_3_5pct"
    if taux < 10:
        return "engagement_5_10pct"
    return "engagement_plus_10pct"


def classer_compteur(nom, valeur):
    """Créer les modalités de classes sans confusion avec les données brutes."""
    if nom not in VARIABLES_CLASSES:
        raise ValueError("Variable numérique non prise en charge.")
    prefixe = NOMS_CLASSES[nom]
    valeur = normaliser_nombre(valeur)
    if valeur is None:
        return f"{prefixe}_indetermine"
    if nom == "duree":
        if valeur < 15:
            modalite = "moins_15s"
        elif valeur < 60:
            modalite = "15_59s"
        elif valeur < 180:
            modalite = "60_179s"
        else:
            modalite = "plus_180s"
    elif nom == "vues":
        if valeur < 1000:
            modalite = "moins_1k"
        elif valeur < 10000:
            modalite = "1k_10k"
        elif valeur < 100000:
            modalite = "10k_100k"
        elif valeur < 1000000:
            modalite = "100k_1m"
        else:
            modalite = "plus_1m"
    else:
        if valeur == 0:
            modalite = "zero"
        elif valeur < 10:
            modalite = "1_9"
        elif valeur < 100:
            modalite = "10_99"
        elif valeur < 1000:
            modalite = "100_999"
        else:
            modalite = "plus_1k"
    return f"{prefixe}_{modalite}"


def valeur_variable(publication, nom):
    """Lire la durée en secondes ou un compteur d'engagement existant."""
    if nom == "duree":
        return normaliser_nombre(publication.get("video_duration"))
    return lire_compteur(publication, nom)


def indicateurs_numeriques(publication):
    """Construire des indicateurs dérivés sans requêtes supplémentaires à TikTok."""
    taux = calculer_taux_engagement(publication)
    resultat = {
        "taux_engagement": taux,
        "classe_taux_engagement": classer_taux_engagement(taux),
    }
    for nom in VARIABLES_CLASSES:
        resultat[NOMS_CLASSES[nom]] = classer_compteur(
            nom, valeur_variable(publication, nom))
    return resultat


def modalite_taux_brut(taux):
    """Format numérique pour les métadonnées textométriques (deux décimales)."""
    taux = normaliser_nombre(taux)
    if taux is None:
        return "taux_engagement_indetermine"
    return "taux_engagement_" + f"{taux:.2f}".replace(".", "p") + "pct"
