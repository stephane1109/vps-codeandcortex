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

## Comparaison de contenu CLIP — 20 octobre 2026

Deux résultats séparés : séquences réutilisées et scènes/contenus similaires.
La seconde recherche utilise CLIP CPU existant, son index de projections persistant,
un modèle réutilisé en mémoire, un seuil cosinus réglable (0,75 par défaut),
et des exports CSV/JSON distincts. Les proximités sémantiques ne créent pas de
groupes de réemploi. Modèles indisponibles explicités dans le diagnostic.

Validation : 33 tests ciblés réussis sur deploy-scraptiktok, 29 sur main, dont
une paire sémantique simulée exportée sans ORB ni réemploi et le cas des poids
absents. Inférence réelle CLIP ViT-B-32/laion2b_s34b_b79k sur CPU : score
0,524 entre les deux liens TikTok fournis ; 0,777 entre Brut et son extrait
recadré. Cette dernière paire est retrouvée par l'index et retenue à 0,75.
Un seul chargement du modèle pour trois vidéos (deux réutilisations du cache).
Ces essais ne constituent pas une calibration sur des événements similaires
filmés indépendamment, ni une validation de charge sur 1 000 vidéos.
Docker non disponible localement : construction et déploiement Coolify non validés.
Le profil semantique est le nouveau défaut ; un argument Coolify explicite
INSTALL_VIDEO=base doit être remplacé par semantique (ou 1).

## Moteur principal DINOv2 — 20 octobre 2026

`facebook/dinov2-small` produit un vecteur CLS normalisé de 384 composantes pour
chaque image (3 secondes par défaut, intervalle configurable). Aucune moyenne
vidéo n'est calculée par DINOv2. CLIP reste facultatif, dans sa section distincte.
Le téléchargement du modèle est proposé par défaut dans l'interface ; le cache
local fonctionne sans réseau lorsque l'autorisation est désactivée.

L'index FAISS HNSW à produit scalaire est persistant et privé par propriétaire et
profil d'échantillonnage. SQLite conserve les vecteurs, horodatages et JPEG ;
FAISS est reconstruit par blocs après modification et réutilisé sinon. Un verrou
empêche deux écrivains concurrents. Les MP4 peuvent être nettoyés après succès.
Une analyse incomplète conserve ses fichiers pour permettre une reprise.
Les images d'une même publication sont exclues des voisins ; chaque vidéo
a au plus dix autres publications, classées par le meilleur score d'une paire
d'images. Les voisins affichés ne sont jamais filtrés par seuil. HNSW est une
recherche approchée, pas une comparaison exhaustive de toutes les vidéos.

Le regroupement est désactivé par défaut : choisir un seuil après inspection des
scores. Les groupes sont des composantes de liens directs, pas une preuve que
tous leurs membres sont identiques. La progression monotone des horodatages
et la diversité des images distinguent une ressemblance ponctuelle d'une
séquence temporellement cohérente. Cette cohérence seule ne prouve pas un
réemploi. SHA-256, pHash/ORB et RANSAC restent des contrôles complémentaires ;
aucun résultat DINOv2 ne dépend de leur validation.

Le tableau « Vidéos similaires » permet de sélectionner une publication puis
de consulter ses dix voisins, les miniatures, les positions et les URL TikTok.
Exports : `similarites_dino.json`, `similarites_dino.csv`, `groupes_dino.json`,
`miniatures_dino/`, `audit_video.json` et `diagnostic_visuel.json` dans le ZIP.
Le diagnostic distingue MP4 présents, téléchargements effectués, vidéos
décodées, images décodées, embeddings calculés, traitements désactivés et
modèles indisponibles. Les fichiers déjà présents ne sont pas comptés comme de
nouveaux téléchargements. Les compteurs historiques survivent au nettoyage.

### Référence mesurée sur CPU

Le test `tests/reference_dinov2.py` crée six vidéos depuis deux MP4 locaux :
source Brut 7697829530844663072 (24–42 s), réencodage H.264 CRF32, extrait
30–39 s, recadrage central à 70 %, autre magasin filmé entre 70 et 88 s,
et vidéo de rue 7697724586003057953 (0–6 s). Les médias ne sont pas redistribués.

| Rang | Comparaison avec la référence | Cosinus maximal | Temporalité |
|---|---|---|---|
| 1 | Extrait raccourci | 0,9963 | Cohérente |
| 2 | Copie réencodée | 0,9916 | Cohérente |
| 3 | Recadrage | 0,8669 | Cohérente |
| 4 | Autre magasin, type de scène comparable | 0,4735 | Ponctuelle |
| 5 | Rue sans rapport avec le magasin | 0,1326 | Ponctuelle |

Les trois copies connues sont les trois premiers résultats. Les cinq voisins
sont affichés, y compris le score faible. Ce petit jeu ne calibre pas un seuil
universel ; aucun seuil de regroupement n'est imposé. Résultats bruts :
`tests/reference_dinov2_scores.json`. L'essai complet de lot a décodé six vidéos,
calculé 29 embeddings et exporté 30 liens orientés (cinq voisins par vidéo),
sans ORB. La référence a pris environ 38 secondes sur le poste local, ce qui
ne prédit pas la durée sur le VPS.

Validation locale : tests d'index à 1 000 publications (vecteurs de test),
reprise inter-sessions, absence de modèle, désactivation, cohérence temporelle,
interface et accès privé aux miniatures. Pas de traitement neuronal de 1 000
vidéos réelles réalisé. Docker absent localement : aucune construction Docker
ni exécution Coolify revendiquée. La CI Linux inclut le profil `semantique`.

### Déploiement

Reconstruire `deploy-scraptiktok` avec `INSTALL_VIDEO=semantique` (défaut) ou `1`.
`base` conserve les contrôles de copie mais n'installe pas DINOv2. Conserver
`/app/data` pour les modèles Hugging Face et les index inter-lots. PyTorch,
Transformers et FAISS sont utilisés sur CPU ; CUDA n'est pas nécessaire.

Sources techniques : [fiche DINOv2-small](https://huggingface.co/facebook/dinov2-small),
[index FAISS](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).
