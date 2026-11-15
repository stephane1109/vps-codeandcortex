# Qwen3-4B — IRaMuTeQ (Streamlit + Ollama)

Cette application Python code les commentaires français et renvoie des propositions de variables binaires `violence_evoquee`, `violence_denoncee`, `violence_justifiee`, `violence_minimisee`, `interpretation_indeterminee`, ainsi qu'un `acteur_cible`, un extrait d'appui (`indice_textuel`) et une justification. Les catégories ne sont pas exclusives. En cas d'erreur ou d'incertitude, la ligne est conservée et signalée. **Les sorties du LLM ne sont pas des annotations humaines ni une validation des représentations sociales.**

Le modèle utilisé est `qwen3:4b-q4_K_M` via [Ollama](https://ollama.com/library/qwen3), servi uniquement sur le réseau privé de la composition Docker. Les poids 4B quantifiés s'exécutent sur CPU mais leur vitesse dépend fortement de la charge du VPS. Aucune clé API Qwen externe ni service cloud d'inférence n'est requis. Télécharger le modèle nécessite un accès réseau sortant au démarrage.

## Import et export

Importer un ou plusieurs corpus texte IRaMuTeQ : `**** *source_original *id_123 *profil_exemple *texte_commentaire` puis commentaire sur les lignes suivantes. L'ensemble des métadonnées étoilées et du texte est conservé. Option de contexte commun (description de vidéo saisie par le chercheur) et inclusion de métadonnées. Sans contexte ajouté, le modèle n'accède à **aucune image, aucun son, aucune vidéo**. Le modèle analyse au maximum 3 000 caractères de texte et 1 200 caractères de contexte par ligne ; toute troncature est signalée.

Un bouton traite les commentaires par lots (20 par défaut). Le ZIP unique regroupe le CSV des codages, un TXT IRaMuTeQ enrichi de `*qwen_position_...` et un JSON méthodologique. Un CSV de reprise peut être téléchargé puis importé après rechargement de la page : la compatibilité du corpus est vérifiée par SHA-256 et numéros des documents. Le codage n'est pas automatique en arrière-plan ; l'utilisateur lance chaque lot. Les erreurs d'API peuvent être retraitées séparément.

## Réduction de l'espace disque pour un VPS CPU (15 novembre 2026)

Le fichier \`compose.yaml\` utilise désormais, par défaut, l'image \`alpine/ollama:latest\`, une distribution **tierce** d'Ollama dédiée au CPU (environ 70 Mo, hors modèle). Elle est construite à partir d'Ollama mais n'est **pas l'image officielle** \`ollama/ollama\`. Son code source et son processus de construction sont consultables sur https://github.com/alpine-docker/ollama. Ce choix évite le téléchargement des bibliothèques CUDA, inutiles sur un VPS sans GPU. Le service de téléchargement \`charger_modele\` utilise la même image, et ne duplique pas les couches de stockage. L'interface Streamlit, les exports et les catégories Qwen restent inchangés.

La variable facultative \`OLLAMA_CPU_IMAGE\` permet de choisir explicitement une autre image. Pour revenir à l'image officielle, configurer \`OLLAMA_CPU_IMAGE=ollama/ollama:latest\` dans Coolify ; celle-ci contient aussi des backends GPU et consomme beaucoup plus d'espace. Une image tierce implique un risque de chaîne d'approvisionnement distinct ; en environnement sensible, privilégier une image construite et contrôlée par vous ou l'image officielle.

**Attention : remplacer l'image dans GitHub ne libère pas automatiquement le disque du VPS.** Avant tout redéploiement, vérifier l'espace libre avec \`df -h\`, les inodes avec \`df -i\` et les ressources Docker avec \`docker system df -v\`. Les nettoyages possibles, à lancer après examen et sauvegarde, sont \`docker builder prune\` et \`docker image prune\`, qui ne touchent pas aux volumes persistants. Ne pas utiliser \`docker system prune --volumes\`, \`docker volume prune\` ou supprimer manuellement \`/var/lib/containerd\` : votre VPS héberge notamment des bases de données et d'autres applications.

Le modèle \`qwen3:4b-q4_K_M\` est toujours téléchargé dans le volume \`ollama_modeles\`, et occupe plusieurs gigaoctets supplémentaires. Les volumes contenant les poids ou les données de vos autres services doivent être conservés. L'image CPU réduit le coût de l'image Docker, mais ne garantit pas l'espace nécessaire si le système de fichiers est déjà saturé. Le téléchargement et le fonctionnement effectif restent à tester dans Coolify.

## Coolify — deployment recommandé

Créer un projet de type **Docker Compose** depuis `main`, avec `applications/qwen3_4b/compose.yaml` (répertoire de base `applications/qwen3_4b`). Définir `APP_PASSWORD` avec un secret fort dans Coolify. Associer le domaine HTTPS au service **app**, port interne `8501`. **Ne jamais exposer Ollama (11434) à Internet.** Le service `charger_modele` attend l'API interne puis télécharge automatiquement `qwen3:4b-q4_K_M`. Le volume `ollama_modeles` permet de conserver les poids après redéploiement. Sur un VPS 12 Go RAM, éviter l'exécution simultanée de lourds entraînements DARTopic et de l'inférence Qwen. Vérifier la consommation réelle avant d'augmenter les lots.

Si Coolify ne sait pas interpréter le chemin Compose, configurer le répertoire `/applications/qwen3_4b` comme contexte de build et le nom `compose.yaml`, selon la version de Coolify. Aucune modification des applications existantes du dépôt n'est nécessaire. Ce dépôt **ne** provoque **pas** à lui seul le déploiement sur le VPS ; il faut créer le service dans Coolify ou disposer de son accès API.

## Analyse R

`analyse_resultats.R` croise une variable de codage avec une variable étoilée (chi carré exploratoire si applicable). Les comparaisons devraient être accompagnées d'une annotation humaine et d'un calcul d'accord intercodeurs sur un échantillon.
