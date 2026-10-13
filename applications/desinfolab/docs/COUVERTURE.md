# Couverture du cahier des charges et garde de non-régression

| Exigence | Implémentation | Vérification |
| --- | --- | --- |
| Python 3.11, Streamlit, PostgreSQL | Dockerfile, versions figées, modèles SQLAlchemy | Tests PostgreSQL et AppTest |
| Sources, comptes, contenus et relations | Tables distinctes, clés étrangères, fiches liées | Parcours source → compte → contenu |
| 14 plateformes et extensions | Migration 0002, ajout administratif | Test nouvelle plateforme |
| Contributions sans compte | Formulaires et propositions privées | Test absence de publication avant validation |
| Anonymat applicatif | Aucun champ contributeur/IP/email, quotas globaux | Test structure et données enregistrées |
| Validation des URL et doublons | HTTP(S), ports publics, clé canonique, unicité | Tests URL dangereuses, YouTube, doublons |
| Anti-automatisation | Défi unique, délai, expiration, leurre, quotas | Tests erreurs, réutilisation et concurrence |
| Gestion des tags | Cinq familles, création, modification et suppression administratives ; aucun champ parent dans le formulaire | Tests droits, usages, historique, compatibilité des anciennes relations et parcours Streamlit |
| Qualifications documentées | Référence explicite par tag appliqué | Test refus de qualification injustifiée |
| Recherche multicritère ET/OU | Requêtes SQL partagées API/Streamlit | Tests croisés tags/dates/pays/langue/média/URL |
| Pagination et fiches liées | Tableaux interactifs et liens de fiches | Tests pagination et navigation AppTest |
| URL originales et sélection multiple | Liens, copie, corpus en session | Exports testés ; sélection à vérifier visuellement |
| TXT/CSV/JSON avec métadonnées | Export complet et flux API | Tests formats, tags et protection CSV |
| Administration sécurisée | scrypt, expiration, quota persistant | Tests accès refusé, jeton et quota |
| Révision, refus, validation, fusion | Transactions et contrôle de versions | Tests métier et parcours administratif AppTest |
| Historique des états et références | Table historique avant/après, motifs | Tests révision et modération atomique |
| API sources/comptes/contenus/tags/URL | FastAPI, OpenAPI, routes GET | TestClient, refus des routes privées et POST |
| Python/R et collecteurs | Exemples README, export d'URL | Test originalité et filtrage des URL |
| Aucun téléchargement automatique | Aucune requête HTTP sur les URL soumises | Lecture du code de validation |
| Six pages françaises et responsive | Navigation Streamlit, colonnes, tableaux | AppTest et contrôle navigateur |
| Schéma, migrations et configuration | schema.sql, Alembic, Compose, .env.example | Aller-retour migrations, alembic check |
| Persistance et sauvegardes | Volumes, pg_dump, restauration sur base vide | Sauvegarde/restauration réelle, 9 tables comparées, cible non vide refusée |
| Journaux minimisés et limites documentées | Configuration Streamlit/Uvicorn/PostgreSQL, README | Revue de configuration |

Aucune évolution ne doit retirer silencieusement une capacité décrite ici. Ajouter un test de régression lors d'une correction et maintenir la compatibilité des routes `/v1` ou prévoir une migration explicite. Les contrôles humains de pertinence scientifique et les limites d'anonymat réseau restent documentés dans le README.
