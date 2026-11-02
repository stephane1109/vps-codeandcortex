"""Colonnes communes des fichiers publications.csv de ScrapTikTok.

L'export conserve les champs existants et inclut les variables de la section
« Variables à inclure avant chaque post dans le TXT », avec leurs recodages.
Les valeurs indisponibles restent vides : aucune donnée n'est inventée.
"""
import json
import re
from collecte.variables_numeriques import indicateurs_numeriques
from collecte.presse import colonnes_categories_presse


def cellule_csv(valeur):
    """Protéger les cellules CSV sans perdre les listes ni les vrais zéros."""
    texte = (
        json.dumps(valeur, ensure_ascii=False, allow_nan=False)
        if isinstance(valeur, (list, dict)) else
        "" if valeur is None else str(valeur)
    )
    return "'" + texte if texte.lstrip().startswith(("=", "+", "-", "@")) else texte

COMPTEURS = ("vues", "likes", "commentaires", "partages", "favoris")


def hashtags_pour_csv(publication):
    """Produire une colonne de hashtags sans dièse sur demande explicite.

    Les données brutes ne sont pas modifiées ; les anciennes publications,
    sans réglage enregistré, conservent le comportement historique.
    """
    if "inclure_hashtags_csv" not in publication:
        return publication.get("hashtags")
    if not publication.get("inclure_hashtags_csv"):
        return ""
    hashtags = publication.get("hashtags")
    valeurs = list(hashtags) if isinstance(hashtags, (list, tuple)) else []
    # Compléter la liste structurée avec les hashtags visibles dans la légende,
    # sans extraire les fragments d'URL externes.
    description = publication.get("description") or ""
    if isinstance(description, str):
        motif = r"https?://\S+|#(\w+)"
        valeurs.extend(
            occurrence.group(1) for occurrence in re.finditer(motif, description)
            if occurrence.group(1))
    uniques = {}
    for valeur in valeurs:
        if not isinstance(valeur, str):
            continue
        nom = valeur.strip().lstrip("#").strip()
        if re.fullmatch(r"\w+", nom):
            uniques.setdefault(nom.casefold(), nom)
    return ", ".join(uniques.values())

# Une structure stable permet de concaténer les CSV de plusieurs collectes.
# Conserver les noms historiques (id, author, create_time, etc.).
COLONNES_PUBLICATIONS_CSV = (
    "id", "url", "author", "create_time", "description", "region_code",
    "is_verified", "vues", "likes", "commentaires", "partages", "favoris",
    "date_premiere_collecte", "date_derniere_collecte",
    "publication_id", "profil", "date_publication", "created_at",
    "collected_at", "retenue", "motif_non_retenue", "langue_detection",
    "is_verified_statut", "follower_count", "follower_count_statut",
    "classe_abonnes", "video_duration", "duree_classe",
    "taux_engagement", "classe_taux_engagement",
    "vues_classe", "likes_classe", "commentaires_classe",
    "partages_classe", "favoris_classe",
    "vues_brut", "likes_brut", "commentaires_brut",
    "partages_brut", "favoris_brut",
    "hashtags", "hashtags_recherches", "hashtags_correspondants",
    "operateur_hashtags", "media_id", "categorie_media",
    "type_publication", "compte_reposteur", "comptes_reposteurs",
    "auteur_original", "id_video_originale",
    "republication_confirmee", "date_republication",
    "presse_nationale", "presse_regio_dpt", "presse_indep", "presse_autre",
    "source", "status",
    "error", "groupe_visuel", "reemploi_visuel",
    "contenu_genere_ia", "statut_resume_ia", "resume_ia_tiktok",
    "video_id", "video_url", "video_fichier",
    "video_statut", "video_message", "video_diagnostic",
    "commentaires_collecte_statut", "commentaires_collecte_recuperes",
    "commentaires_collecte_annonces", "commentaires_collecte_exhaustif",
)


def _premiere_valeur(publication, *noms):
    """Rechercher le premier champ renseigné sans effacer les vrais zéros."""
    for nom in noms:
        if publication.get(nom) is not None:
            return publication[nom]
    return None


def ligne_publication_csv(publication):
    """Déplier les valeurs brutes, catégorielles et métadonnées d'une vidéo."""
    ligne = {nom: publication.get(nom) for nom in COLONNES_PUBLICATIONS_CSV}
    ligne.update(colonnes_categories_presse(publication))
    ligne["hashtags"] = hashtags_pour_csv(publication)
    ligne["id"] = _premiere_valeur(publication, "id", "publication_id")
    ligne["publication_id"] = ligne["id"]
    ligne["author"] = _premiere_valeur(publication, "author", "profil")
    ligne["profil"] = ligne["author"]
    ligne["create_time"] = _premiere_valeur(
        publication, "create_time", "created_at", "date_publication")
    ligne["created_at"] = _premiere_valeur(
        publication, "created_at", "date_publication", "create_time")
    ligne["date_publication"] = ligne["created_at"]
    ligne["date_premiere_collecte"] = _premiere_valeur(
        publication, "_premiere_collecte", "date_premiere_collecte")
    ligne["date_derniere_collecte"] = _premiere_valeur(
        publication, "_derniere_collecte", "date_derniere_collecte")
    ligne["retenue"] = _premiere_valeur(publication, "retenue", "_retenue")

    engagement = publication.get("engagement") or {}
    for nom in COMPTEURS:
        mesure = engagement.get(nom)
        if isinstance(mesure, dict):
            ligne[nom] = mesure.get("valeur")
            ligne[nom + "_brut"] = mesure.get("brut")
        elif mesure is not None:
            ligne[nom] = mesure
        # La liste de valeurs planes reste utilisable pour les anciens imports.

    # Si des données anciennes n'ont pas encore les variables dérivées,
    # les calculer uniquement à partir des compteurs réellement disponibles.
    calculs = indicateurs_numeriques(publication)
    for nom in ("taux_engagement", "classe_taux_engagement",
                "vues_classe", "likes_classe", "commentaires_classe",
                "partages_classe", "favoris_classe", "duree_classe"):
        if ligne.get(nom) is None:
            ligne[nom] = calculs.get(nom)

    collecte_commentaires = publication.get("collecte_commentaires") or {}
    if isinstance(collecte_commentaires, dict):
        for cible, noms in (
            ("commentaires_collecte_statut", ("statut",)),
            ("commentaires_collecte_recuperes", ("recuperes",)),
            ("commentaires_collecte_annonces", ("annonces",)),
            ("commentaires_collecte_exhaustif", ("exhaustif", "exhaustive")),
        ):
            if ligne.get(cible) is None:
                for nom in noms:
                    if nom in collecte_commentaires:
                        ligne[cible] = collecte_commentaires[nom]
                        break
    return ligne


def lignes_publications_csv(publications):
    """Préparer un tableau d'une ligne par vidéo, sans perte des colonnes."""
    return [ligne_publication_csv(publication) for publication in publications]
