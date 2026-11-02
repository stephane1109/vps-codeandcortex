"""Variables et recodages des profils de médias publics TikTok.

Les classes sont proposées pour une analyse comparative et ne constituent
pas des catégories officielles TikTok. Une absence n'est jamais un zéro.
"""
from datetime import datetime, timezone

VARIABLES_PROFILS_MEDIAS = (
    "following_count", "follower_count", "likes_count", "video_count",
)
SEGMENTATIONS_PROFILS_MEDIAS = {
    "following_count": (
        (0, "0"), (9, "1_9"), (99, "10_99"),
        (999, "100_999"), (None, "plus_1000")),
    "follower_count": (
        (999, "moins_1k"), (9999, "1k_10k"),
        (99999, "10k_100k"), (999999, "100k_1m"),
        (None, "plus_1m")),
    "likes_count": (
        (0, "0"), (9999, "1_9999"), (99999, "10k_100k"),
        (999999, "100k_1m"), (9999999, "1m_10m"),
        (None, "plus_10m")),
    "video_count": (
        (0, "0"), (9, "1_9"), (99, "10_99"),
        (999, "100_999"), (None, "plus_1000")),
}
LIBELLES_PROFILS_MEDIAS = {
    "following_count": (
        "Suivis (following_count)",
        "0 ; 1–9 ; 10–99 ; 100–999 ; ≥ 1 000"),
    "follower_count": (
        "Abonnés (follower_count)",
        "0–999 ; 1 000–9 999 ; 10 000–99 999 ; 100 000–999 999 ; ≥ 1 M"),
    "likes_count": (
        "J'aime reçus par le compte (likes_count)",
        "0 ; 1–9 999 ; 10 000–99 999 ; 100 000–999 999 ; "
        "1 M–9 999 999 ; ≥ 10 M"),
    "video_count": (
        "Vidéos publiées (video_count)",
        "0 ; 1–9 ; 10–99 ; 100–999 ; ≥ 1 000"),
}


def segmenter_profil_media(variable, valeur):
    """Recoder un compteur entier observé, sans assimiler un manque à zéro."""
    if variable not in SEGMENTATIONS_PROFILS_MEDIAS:
        raise ValueError("Métrique de profil inconnue.")
    if valeur is None or isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
        return "indetermine"
    for borne, modalite in SEGMENTATIONS_PROFILS_MEDIAS[variable]:
        if borne is None or valeur <= borne:
            return modalite
    raise ValueError("Segmentation de profil impossible.")


def colonnes_profils_medias(variables, classes):
    """Créer des colonnes stables, dans l'ordre défini par l'interface."""
    colonnes = ["compte", "nom", "categorie_media", "url", "date_collecte",
                "statut_profil"]
    for variable in VARIABLES_PROFILS_MEDIAS:
        if variable in variables:
            colonnes.append(variable)
            if variable in classes:
                colonnes.append("classe_" + variable)
    return colonnes


def ligne_profil_media(media, variables, classes, *, donnees=None,
                       statut="indisponible", date_collecte=None):
    """Conserver une ligne par compte même quand l'API refuse de répondre."""
    resultat = {
        "compte": media["compte"],
        "nom": media["nom"],
        "categorie_media": media["categorie"],
        "url": media.get("url") or "https://www.tiktok.com/@" + media["compte"],
        "date_collecte": date_collecte or datetime.now(timezone.utc).isoformat(),
        "statut_profil": statut,
    }
    donnees = donnees or {}
    for variable in VARIABLES_PROFILS_MEDIAS:
        if variable in variables:
            valeur = donnees.get(variable)
            resultat[variable] = (
                valeur if isinstance(valeur, int) and
                not isinstance(valeur, bool) and valeur >= 0 else None)
            if variable in classes:
                resultat["classe_" + variable] = segmenter_profil_media(
                    variable, resultat[variable])
    return resultat
