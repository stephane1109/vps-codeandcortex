"""Vues PostgreSQL tabulaires, sans duplication des données JSONB."""

def preparer_vues_tabulaire(curseur):
    """Déplier les variables pour la consultation directe dans pgAdmin."""
    curseur.execute("""
        CREATE OR REPLACE VIEW scraptiktok_publications_tableau AS
        SELECT
            p.collecte_id,
            c.nom_sauvegarde,
            c.source_collecte,
            c.moteur,
            c.statut AS statut_collecte,
            p.publication_id,
            p.retenue,
            p.donnees->>'url' AS url,
            p.donnees->>'author' AS profil,
            p.donnees->>'created_at' AS date_publication,
            p.donnees->>'collected_at' AS date_collecte,
            p.donnees->>'description' AS description,
            p.donnees->>'region_code' AS region_code,
            CASE WHEN p.donnees->>'is_verified' IN ('true', 'false')
                THEN (p.donnees->>'is_verified')::boolean END AS is_verified,
            p.donnees->>'is_verified_statut' AS is_verified_statut,
            CASE WHEN (p.donnees->>'follower_count') ~ '^[0-9]+$'
                THEN (p.donnees->>'follower_count')::bigint END AS follower_count,
            p.donnees->>'follower_count_statut' AS follower_count_statut,
            p.donnees->>'classe_abonnes' AS classe_abonnes,
            CASE WHEN (p.donnees->>'video_duration') ~ '^[0-9]+([.][0-9]+)?$'
                THEN (p.donnees->>'video_duration')::numeric END AS duree_video,
            p.donnees->>'duree_classe' AS duree_classe,
            CASE WHEN (p.donnees#>>'{engagement,vues,valeur}') ~ '^[0-9]+$'
                THEN (p.donnees#>>'{engagement,vues,valeur}')::bigint END AS vues,
            CASE WHEN (p.donnees#>>'{engagement,likes,valeur}') ~ '^[0-9]+$'
                THEN (p.donnees#>>'{engagement,likes,valeur}')::bigint END AS likes,
            CASE WHEN (p.donnees#>>'{engagement,commentaires,valeur}') ~ '^[0-9]+$'
                THEN (p.donnees#>>'{engagement,commentaires,valeur}')::bigint END AS commentaires,
            CASE WHEN (p.donnees#>>'{engagement,partages,valeur}') ~ '^[0-9]+$'
                THEN (p.donnees#>>'{engagement,partages,valeur}')::bigint END AS partages,
            CASE WHEN (p.donnees#>>'{engagement,favoris,valeur}') ~ '^[0-9]+$'
                THEN (p.donnees#>>'{engagement,favoris,valeur}')::bigint END AS favoris,
            p.donnees#>>'{engagement,vues,brut}' AS vues_brut,
            p.donnees#>>'{engagement,likes,brut}' AS likes_brut,
            p.donnees#>>'{engagement,commentaires,brut}' AS commentaires_brut,
            p.donnees#>>'{engagement,partages,brut}' AS partages_brut,
            p.donnees#>>'{engagement,favoris,brut}' AS favoris_brut,
            CASE WHEN (p.donnees->>'taux_engagement') ~ '^-?[0-9]+([.][0-9]+)?$'
                THEN (p.donnees->>'taux_engagement')::numeric END AS taux_engagement,
            p.donnees->>'classe_taux_engagement' AS classe_taux_engagement,
            p.donnees->>'vues_classe' AS vues_classe,
            p.donnees->>'likes_classe' AS likes_classe,
            p.donnees->>'commentaires_classe' AS commentaires_classe,
            p.donnees->>'partages_classe' AS partages_classe,
            p.donnees->>'favoris_classe' AS favoris_classe,
            p.donnees->>'hashtags' AS hashtags,
            p.donnees->>'langue_detection' AS langue_detection,
            p.donnees->>'motif_non_retenue' AS motif_non_retenue,
            p.donnees->>'source' AS source_video,
            p.donnees->>'status' AS statut_video,
            p.donnees->>'error' AS erreur_video,
            p.donnees->>'media_id' AS media_id,
            p.donnees->>'categorie_media' AS categorie_media,
            p.donnees->>'groupe_visuel' AS groupe_visuel,
            p.donnees->>'reemploi_visuel' AS reemploi_visuel,
            p.donnees->>'video_id' AS video_id_mp4,
            p.donnees->>'video_url' AS video_url_mp4,
            p.donnees->>'video_fichier' AS video_fichier_mp4,
            CASE WHEN p.donnees->>'contenu_genere_ia' IN ('true', 'false')
                THEN (p.donnees->>'contenu_genere_ia')::boolean END AS contenu_genere_ia,
            p.donnees->>'statut_resume_ia' AS statut_resume_ia,
            p.donnees->>'resume_ia_tiktok' AS resume_ia_tiktok,
            (SELECT count(*)
             FROM scraptiktok_commentaires AS m
             WHERE m.collecte_id = p.collecte_id
               AND m.publication_id = p.publication_id) AS commentaires_collectes
        FROM scraptiktok_publications AS p
        JOIN scraptiktok_collectes AS c ON c.collecte_id = p.collecte_id
    """)
    curseur.execute("""
        CREATE OR REPLACE VIEW scraptiktok_commentaires_tableau AS
        SELECT
            m.collecte_id,
            c.nom_sauvegarde,
            c.moteur,
            m.publication_id,
            p.donnees->>'url' AS url_video,
            m.commentaire_id,
            COALESCE(m.donnees->>'auteur', m.donnees->>'author') AS auteur,
            COALESCE(m.donnees->>'texte', m.donnees->>'text') AS texte,
            m.donnees->>'parent_id' AS parent_id,
            CASE WHEN m.donnees->>'est_reponse' IN ('true', 'false')
                THEN (m.donnees->>'est_reponse')::boolean END AS est_reponse,
            m.donnees->>'date_brute' AS date_commentaire,
            CASE WHEN (m.donnees->>'likes') ~ '^[0-9]+$'
                THEN (m.donnees->>'likes')::bigint END AS likes,
            m.donnees->>'source' AS source_commentaire,
            m.donnees->>'observe_le' AS date_collecte
        FROM scraptiktok_commentaires AS m
        JOIN scraptiktok_collectes AS c ON c.collecte_id = m.collecte_id
        LEFT JOIN scraptiktok_publications AS p
            ON p.collecte_id = m.collecte_id
           AND p.publication_id = m.publication_id
    """)
