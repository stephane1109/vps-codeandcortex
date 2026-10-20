# Vérification du 20 octobre 2026

- 63 tests ciblés réussis sur la branche de déploiement : index, extraction,
  ORB/RANSAC, temporalité, groupes, exports, API et nouvel onglet Streamlit.
- 40 tests ciblés réussis sur l’intégration `main`, qui conserve ses propres
  fonctionnalités et ses formats préexistants.
- 1 000 publications à empreintes synthétiques : index persistant interrogé
  sans calcul ORB et sans création des 499 500 paires possibles. Ce test ne
  chronomètre pas 1 000 vidéos réelles sur le VPS.
- Réencodage MP4 réel, compression JPEG, copie binaire, texte incrusté,
  recadrage à 36 % de la surface, extrait décalé, bandeau commun sur contenus
  différents, image fixe, cache, reprise inter-sessions, nettoyage MP4,
  séparation des propriétaires, invalidation et poursuite après erreur testés.
- Les tests complets rencontrent encore 12 échecs/erreurs préexistants sur le
  déploiement : collecteur anonyme, recherche de comptes, dates et deux tests
  de navigateur Streamlit. Reproduits sur `2906598` sans nos changements.
  Un autre test historique de validation entre sources échoue aussi sur
  `main`, reproduit avec son `webapp.py` original.
- Environnement local : Python 3.11, OpenCV 4.11, NumPy 1.26.4,
  Streamlit 1.57 (différent de la version exigée par le Dockerfile).
- Compilation Python et contrôle des différences effectués. Pas de Docker
  local : construction de l’image et performance réelle du VPS non vérifiées.
  Le profil `INSTALL_VIDEO=base` existant fournit les dépendances nécessaires ;
  SQLite est fourni par Python. Aucun paquet CUDA ou service externe ajouté.

Pour Coolify : déployer `deploy-scraptiktok`, profil `base`, avec `/app/data`
sur un volume persistant local. Les options de téléchargement et de collecte
restent inchangées ; le nettoyage MP4 n’est actif que sur demande explicite.
