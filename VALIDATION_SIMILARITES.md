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

## Correctif du 20 octobre 2026

- Présélection temporelle sans rejet prématuré des empreintes globales stables ; la diversité des zones confirmées par ORB reste obligatoire.
- Budget de 400 candidats réparti sur toute la vidéo ; répartition des voisins entre publications. Migration des recherches existantes sans supprimer les vignettes et caches ORB.
- Diagnostic des candidats, vérifications ORB, rejets et erreurs disponible dans l'interface et le ZIP. Options désactivées exportées avec la modalité `no`. Colonne URL TikTok copiable dans le tableau de collecte.
- 37 tests ciblés réussis (diagnostic, index, codage, exports, extraction, temporalité, disponibilité et onglet Multimodale).
- Essai réel : vidéos TikTok 7697829530844663072 et 7697724586003057953 téléchargées et examinées. Scènes différentes, aucun candidat détecté. Cela ne valide pas les huit autres vidéos du lot utilisateur.
- Contrôle positif dérivé de la vidéo Brut : extrait 10–16 s, recadrage central à 85 %, redimensionnement 360 px, réencodage H.264 CRF 30 sans audio. Correspondance retrouvée avec 0–6 s de l'extrait, six images confirmées par ORB, score interne 0,799 (non calibré comme probabilité).
- Docker/Coolify non exécuté lors de cette validation locale.
