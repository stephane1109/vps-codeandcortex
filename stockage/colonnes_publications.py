"""Colonnes réelles de la table PostgreSQL des publications TikTok.

Les colonnes calculées et stockées sont automatiquement renseignées à partir
du JSONB pour les anciennes et nouvelles publications. La migration est
additive : elle conserve les colonnes, données et clés préexistantes.
"""


def _texte(nom):
    """Lire une variable textuelle dans les métadonnées de la publication."""
    return f"donnees->>'{nom}'"


def _entier(expression):
    """Convertir uniquement les entiers positifs compatibles avec BIGINT."""
    return (
        f"CASE WHEN ({expression}) ~ '^[0-9]{{1,18}}$' "
        f"THEN ({expression})::BIGINT END"
    )


def _nombre(expression):
    """Conserver NULL en cas de valeur numérique absente ou invalide."""
    return (
        f"CASE WHEN ({expression}) ~ '^-?[0-9]{{1,16}}([.][0-9]{{1,16}})?$' "
        f"THEN ({expression})::NUMERIC END"
    )


def _booleen(expression):
    """Distinguer explicitement vrai, faux et donnée indisponible."""
    return (
        f"CASE WHEN LOWER({expression}) IN ('true', 'false') "
        f"THEN ({expression})::BOOLEAN END"
    )


def colonnes_publications():
    """Définir les variables de collecte sous forme de vraies colonnes."""
    colonnes = {
        "url": ("TEXT", _texte("url")),
        "profil": ("TEXT", _texte("author")),
        "date_publication": ("TEXT", _texte("created_at")),
        "date_collecte": ("TEXT", _texte("collected_at")),
        "description": ("TEXT", _texte("description")),
        "region_code": ("TEXT", _texte("region_code")),
        "is_verified": ("BOOLEAN", _booleen(_texte("is_verified"))),
        "is_verified_statut": ("TEXT", _texte("is_verified_statut")),
        "follower_count": ("BIGINT", _entier(_texte("follower_count"))),
        "follower_count_statut": ("TEXT", _texte("follower_count_statut")),
        "classe_abonnes": ("TEXT", _texte("classe_abonnes")),
        "duree_secondes": ("NUMERIC", _nombre(_texte("video_duration"))),
        "duree_classe": ("TEXT", _texte("duree_classe")),
        "taux_engagement": ("NUMERIC", _nombre(_texte("taux_engagement"))),
        "classe_taux_engagement": ("TEXT", _texte("classe_taux_engagement")),
        "hashtags": ("TEXT", _texte("hashtags")),
        "langue_detection": ("TEXT", _texte("langue_detection")),
        "motif_non_retenue": ("TEXT", _texte("motif_non_retenue")),
        "source_video": ("TEXT", _texte("source")),
        "statut_video": ("TEXT", _texte("status")),
        "erreur_video": ("TEXT", _texte("error")),
        "media_id": ("TEXT", _texte("media_id")),
        "categorie_media": ("TEXT", _texte("categorie_media")),
        "groupe_visuel": ("TEXT", _texte("groupe_visuel")),
        "reemploi_visuel": ("TEXT", _texte("reemploi_visuel")),
        "video_id_mp4": ("TEXT", _texte("video_id")),
        "video_url_mp4": ("TEXT", _texte("video_url")),
        "video_fichier_mp4": ("TEXT", _texte("video_fichier")),
        "contenu_genere_ia": ("BOOLEAN", _booleen(_texte("contenu_genere_ia"))),
        "statut_resume_ia": ("TEXT", _texte("statut_resume_ia")),
        "resume_ia_tiktok": ("TEXT", _texte("resume_ia_tiktok")),
        "source_resume_ia": ("TEXT", _texte("source_resume_ia")),
        "titre_ia_tiktok": ("TEXT", _texte("titre_ia_tiktok")),
        "article_ia_tiktok": ("TEXT", _texte("article_ia_tiktok")),
        "mots_cles_ia_tiktok": ("TEXT", _texte("mots_cles_ia_tiktok")),
        "video_statut": ("TEXT", _texte("video_statut")),
        "video_message": ("TEXT", _texte("video_message")),
        "video_diagnostic": ("TEXT", _texte("video_diagnostic")),
        "collecte_commentaires_statut": (
            "TEXT", "donnees#>>'{collecte_commentaires,statut}'"),
        "collecte_commentaires_recuperes": (
            "BIGINT", _entier("donnees#>>'{collecte_commentaires,recuperes}'")),
        "collecte_commentaires_annonces": (
            "BIGINT", _entier("donnees#>>'{collecte_commentaires,annonces}'")),
        "collecte_commentaires_exhaustive": (
            "BOOLEAN", _booleen("donnees#>>'{collecte_commentaires,exhaustif}'")),
    }
    for compteur in ("vues", "likes", "commentaires", "partages", "favoris"):
        expression = f"donnees#>>'{{engagement,{compteur},valeur}}'"
        colonnes[compteur] = ("BIGINT", _entier(expression))
        colonnes[compteur + "_brut"] = (
            "TEXT", f"donnees#>>'{{engagement,{compteur},brut}}'")
        colonnes[compteur + "_classe"] = (
            "TEXT", _texte(compteur + "_classe"))
    return colonnes


def preparer_colonnes_publications(curseur):
    """Migrer uniquement les colonnes manquantes, en une seule opération.

    Une seule commande ALTER TABLE limite les réécritures sur une table ayant
    déjà des publications. Aucune migration n'est lancée si le schéma est à jour.
    """
    curseur.execute("""
        SELECT attname
        FROM pg_attribute
        WHERE attrelid = 'scraptiktok_publications'::regclass
          AND attnum > 0 AND NOT attisdropped
    """)
    presentes = {ligne[0] for ligne in curseur.fetchall()}
    manquantes = [
        (nom, type_sql, expression)
        for nom, (type_sql, expression) in colonnes_publications().items()
        if nom not in presentes
    ]
    if not manquantes:
        return 0
    ajouts = [
        f"ADD COLUMN IF NOT EXISTS {nom} {type_sql} "
        f"GENERATED ALWAYS AS ({expression}) STORED"
        for nom, type_sql, expression in manquantes
    ]
    curseur.execute("ALTER TABLE scraptiktok_publications\n    "
                    + ",\n    ".join(ajouts))
    return len(manquantes)
