"""Choix indépendants des variables destinées aux tableaux CSV.

Les colonnes de liaison et de diagnostic restent disponibles afin que les
fichiers puissent être concaténés, réimportés et reliés entre eux. Les
variables descriptives désélectionnées ne sont pas exportées.
"""

# Une option par ligne du formulaire, distincte des clés techniques.
VARIABLES_CSV = (
    "date", "profil", "recuperer_abonnes", "follower_count",
    "abonnes_classe", "id", "categorie_compte",
    "region_code", "is_verified",
    "vues", "vues_classe", "likes", "likes_classe",
    "commentaires", "commentaires_classe",
    "partages", "partages_classe",
    "favoris", "favoris_classe",
    "duree", "duree_classe",
    "taux_engagement", "classe_taux_engagement",
    "ville_etude",
)

COLONNES_PAR_VARIABLE = {
    "date": ("create_time", "created_at", "date_publication"),
    "profil": ("author", "profil", "auteur"),
    "recuperer_abonnes": ("follower_count", "follower_count_statut"),
    "follower_count": ("follower_count", "follower_count_statut"),
    "abonnes_classe": ("classe_abonnes",),
    "id": ("id",),
    "categorie_compte": (
        "categorie_media", "presse_nationale", "presse_regio_dpt",
        "presse_indep", "presse_autre",
    ),
    "region_code": ("region_code",),
    "is_verified": ("is_verified", "is_verified_statut"),
    "vues": ("vues", "vues_brut"),
    "vues_classe": ("vues_classe",),
    "likes": ("likes", "likes_brut"),
    "likes_classe": ("likes_classe",),
    "commentaires": ("commentaires", "commentaires_brut"),
    "commentaires_classe": ("commentaires_classe",),
    "partages": ("partages", "partages_brut"),
    "partages_classe": ("partages_classe",),
    "favoris": ("favoris", "favoris_brut"),
    "favoris_classe": ("favoris_classe",),
    "duree": ("video_duration",),
    "duree_classe": ("duree_classe",),
    "taux_engagement": ("taux_engagement",),
    "classe_taux_engagement": ("classe_taux_engagement",),
    "ville_etude": ("ville_etude",),
}

# Ces champs techniques ne sont pas des variables facultatives :
# publication_id relie les commentaires, vidéos et tableaux de métriques.
COLONNES_TECHNIQUES = {"publication_id"}


def colonnes_csv_selectionnees(colonnes, variables_csv=None):
    """Sélectionner les colonnes sans réordonner ni modifier les données.

    None signifie ancien paramétrage, donc toutes les colonnes historiques.
    Une liste explicite, même vide, constitue un choix utilisateur.
    """
    colonnes = list(colonnes)
    if variables_csv is None:
        return colonnes
    inconnues = set(variables_csv) - set(VARIABLES_CSV)
    if inconnues:
        raise ValueError(
            "Variables CSV inconnues : " + ", ".join(sorted(inconnues)))
    selection = set(variables_csv)
    garder = set(COLONNES_TECHNIQUES)
    for nom in selection:
        garder.update(COLONNES_PAR_VARIABLE[nom])
    variables_facultatives = {
        colonne
        for groupe in COLONNES_PAR_VARIABLE.values()
        for colonne in groupe
    }
    return [
        colonne for colonne in colonnes
        if colonne not in variables_facultatives or colonne in garder
    ]
