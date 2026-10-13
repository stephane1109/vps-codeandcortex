# Vérifications réalisées le 13 octobre 2026

- Python 3.11, PostgreSQL 16.2 temporaire local.
- **37 tests réussis sur PostgreSQL**, avec un schéma isolé par test. Cela inclut les parcours métier, l'API, quatre parcours d'interface Streamlit, les migrations aller/retour, la double modération et l'utilisation concurrente d'un même défi.
- `alembic check` : aucun écart entre modèles et migrations.
- `ruff check` et compilation Python : réussis.
- Validation syntaxique des scripts shell : réussie.
- Compose : YAML parsé ; services, dépendances, absence de port PostgreSQL public et absence de secrets administrateur dans le service API vérifiés.
- Sauvegarde réelle par `scripts/sauvegarder.sh`, puis restauration par `scripts/restaurer.sh` dans une seconde base PostgreSQL temporaire. Effectifs de neuf tables et valeurs documentaires comparés, version Alembic vérifiée. Une seconde restauration vers la base non vide est correctement refusée. Bases temporaires de ce contrôle supprimées après vérification.
- Contrôle visuel du navigateur : accueil sur ordinateur et recherche sur un écran de 390 × 844 pixels ; navigation mobile repliable et filtres empilés. La sélection multiple est fournie par le composant Streamlit ; son interaction native n'est pas pilotée par les tests AppTest.

Docker Engine n'est pas disponible sur ce poste : **aucune construction d'image ou exécution du Compose n'a été réalisée**. Le déploiement Coolify et le routage HTTPS devront être vérifiés sur le VPS avec les secrets d'exploitation. Ces vérifications locales ne constituent pas une validation du déploiement sur le VPS.

La suite produit un avertissement de dépréciation du client de test Starlette lié à httpx ; il n'affecte pas les résultats ni les routes de production.

## Gestion administrative des plateformes

- 48 tests réussis sur PostgreSQL 16.2, dont création, renommage, suppression, audit, contrôle administrateur, doublons et protection des plateformes utilisées.
- Parcours Streamlit AppTest : création, sélection, renommage, confirmation puis suppression sans erreur.
- 15 tests ciblés réussis sur SQLite. `ruff check` et `git diff --check` réussis.
- Aucun changement de schéma : `alembic check` ne détecte aucune migration nécessaire.
