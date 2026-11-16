# Qwen3-4B — IRaMuTeQ (Streamlit + Ollama)

Cette application Python code les commentaires français et renvoie des propositions de variables binaires `violence_evoquee`, `violence_denoncee`, `violence_justifiee`, `violence_minimisee`, `interpretation_indeterminee`, ainsi qu'un `acteur_cible`, un extrait d'appui (`indice_textuel`) et une justification. Les catégories ne sont pas exclusives. En cas d'erreur ou d'incertitude, la ligne est conservée et signalée. **Les sorties du LLM ne sont pas des annotations humaines ni une validation des représentations sociales.**

Le modèle utilisé est `qwen3:4b-q4_K_M` via [Ollama](https://ollama.com/library/qwen3), servi uniquement sur le réseau privé de la composition Docker. Les poids 4B quantifiés s'exécutent sur CPU mais leur vitesse dépend fortement de la charge du VPS. Aucune clé API Qwen externe ni service cloud d'inférence n'est requis. Télécharger le modèle nécessite un accès réseau sortant au démarrage.

## Import et export

Importer un ou plusieurs corpus texte IRaMuTeQ : `**** *source_original *id_123 *profil_exemple *texte_commentaire` puis commentaire sur les lignes suivantes. L'ensemble des métadonnées étoilées et du texte est conservé. Option de contexte commun (description de vidéo saisie par le chercheur) et inclusion de métadonnées. Sans contexte ajouté, le modèle n'accède à **aucune image, aucun son, aucune vidéo**. Le modèle analyse au maximum 3 000 caractères de texte et 1 200 caractères de contexte par ligne ; toute troncature est signalée.

L'interface propose désormais deux modes d'analyse. Le mode **Analyse libre avec mon prompt** est affiché par défaut : le chercheur rédige ou modifie une consigne et obtient une réponse par commentaire dans la colonne \`reponse_qwen\`. Le mode **Codage structuré sur la violence** est conservé pour reproduire la grille initiale, avec ses colonnes binaires, sa validation JSON et ses croisements statistiques. Dans les deux modes, le prompt complet est enregistré dans \`parametres.json\`.

L'interface ne demande plus le nombre de commentaires par lot. Le bouton **Analyser tous les commentaires restants** parcourt automatiquement les unités non traitées, dans leur ordre d'origine, et affiche un indicateur de progression. Une autre commande permet de réessayer les commentaires en erreur. Le traitement s'arrête après trois erreurs consécutives de communication ou de décodage, afin d'éviter de multiplier des requêtes inutiles. Les commentaires vides restent identifiés et les résultats partiels restent accessibles dans la session Streamlit. **La progression ne s'exécute pas en arrière-plan** : en cas de redémarrage du conteneur ou de perte de session, importer un CSV précédemment téléchargé pour reprendre.

Le ZIP unique regroupe le fichier historique \`codage_commentaires.csv\`, le nouveau \`reponses_qwen.csv\`, le TXT IRaMuTeQ enrichi et les paramètres, dont la consigne. Le CSV de reprise inclut une signature du corpus et une empreinte des paramètres, afin de ne pas mélanger des analyses fondées sur des prompts différents. Les anciens CSV sans empreinte de prompt ne sont admis en reprise qu'en mode structuré historique, avec un avertissement sur l'impossibilité de vérifier la consigne exacte.

Un prompt libre n'impose pas les catégories liées à la violence. Seul le mode structuré conserve volontairement cette grille ; pour une autre problématique, choisir le mode libre. Le modèle ne reçoit pas le corpus entier dans une seule requête : chaque commentaire est envoyé séparément, conformément à la consigne affichée dans l'interface.

## Affichage des réponses et diagnostic du modèle (15 novembre 2026)

L'interface donne maintenant la priorité aux **réponses réellement générées par Qwen**, avec les colonnes `nom_affiche`, `texte`, `reponse_qwen` et `statut_codage`. Une sélection par numéro de document permet de lire intégralement, dans deux zones distinctes, le commentaire d'origine et la réponse produite par le LLM. Le tableau intégral des variables IRaMuTeQ et des métadonnées CSV est conservé dans un panneau secondaire.

L'utilisateur peut lancer **Tester sur un commentaire** pour vérifier la génération d'une réponse avant d'exécuter **Analyser tous les commentaires restants**. Le bouton principal conserve l'analyse automatique sans lots. En l'absence de résultat, une explication indique si les commentaires attendent encore l'analyse, si Ollama est indisponible, si le modèle manque ou si les requêtes ont échoué. Une section distincte **Erreurs de Qwen** présente `statut_codage` et `erreur_codage` pour les commentaires concernés. Les boutons d'analyse sont désactivés lorsque l'API Ollama ne répond pas ou que le modèle n'est pas téléchargé.

Le contenu brut importé n'est jamais présenté comme une sortie générée par Qwen. Toutes les fonctions existantes, les deux modes (libre et structuré), les prompts éditables, les CSV, les exports IRaMuTeQ, le ZIP unique et la restauration restent disponibles. Ces corrections d'interface ne résolvent pas à elles seules une erreur HTTP 503 du proxy Coolify ou une panne du conteneur Ollama.

## Classification en trois thèmes : violence et autocensure (16 novembre 2026)

Un troisième mode est désormais disponible : **Classification en trois thèmes : violence et autocensure**. Il complète sans les remplacer les modes « Analyse libre avec mon prompt » et « Codage structuré sur la violence ».

Dans ce mode, le prompt est entièrement modifiable. Après l'importation, le bouton **Proposer trois thèmes avec Qwen** soumet au modèle au plus cinq extraits de commentaires répartis sur le corpus. Qwen retourne exactement trois intitulés avec leurs définitions opérationnelles. Cette proposition n'est pas une classification réalisée sur le corpus entier : l'échantillon de travail est limité et n'est pas nécessairement représentatif.

Le chercheur peut ensuite corriger les trois titres et définitions. Le prompt de découverte n'est pas répété lors du classement : Qwen reçoit la grille validée et une consigne de classification distincte pour ne pas proposer de nouveaux thèmes à chaque commentaire. Une grille initiale de travail est proposée tant que Qwen n'a pas été sollicité ; elle est explicitement signalée comme telle et non présentée comme une génération automatique. Une fois la grille validée, la commande habituelle **Tester sur un commentaire** puis **Analyser tous les commentaires restants** envoie chaque texte individuellement à Qwen, toujours avec les mêmes trois définitions. Le modèle doit attribuer au commentaire une seule catégorie parmi les trois ou **indéterminé** lorsqu'aucune catégorie n'est démontrable. Les instructions interdisent d'inférer l'autocensure d'un simple silence ou d'une absence de position explicite.

Le tableau des réponses indique la catégorie attribuée, l'intitulé et la justification textuelle. Un bilan affiche les effectifs de chaque thème, y compris les indéterminés. Le ZIP unique contient désormais, dans ce mode, `bilan_themes_qwen.csv` et `grille_themes_qwen.json`, en plus des fichiers existants. Le corpus IRaMuTeQ enrichi contient `*qwen_theme_1`, `*qwen_theme_2`, `*qwen_theme_3` ou `*qwen_theme_indetermine` et conserve toutes les variables initiales. Les colonnes `theme_retenu` et `theme_intitule` identifient explicitement les thèmes ; les anciens alias `these_retenue` et `these_intitule` restent disponibles dans les CSV, ainsi que le prompt et les définitions dans `parametres.json`. Une modification des thèmes fait évoluer l'empreinte de configuration pour empêcher le mélange entre codages fondés sur différentes grilles.

Ces classifications restent des propositions algorithmiques nécessitant une validation humaine avant toute conclusion scientifique.

## Aperçu des dix premières lignes du CSV (16 novembre 2026)

Dans la section **Choix des colonnes CSV**, chaque fichier CSV importé possède désormais un tableau d'aperçu affichant ses dix premières lignes de données, ou toutes ses lignes s'il en comporte moins de dix. Les noms et l'ordre de toutes les colonnes d'origine sont conservés dans cet aperçu, quelle que soit la colonne sélectionnée pour le commentaire et l'auteur. Les cellules multiligne sont lues comme un seul commentaire. Cet affichage n'envoie aucune donnée au modèle et ne limite pas l'importation complète aux dix lignes visibles. Le comportement des corpus IRaMuTeQ TXT, des sélecteurs, des prompts, de la reprise et de tous les exports reste inchangé.

## Affichage systématique du modèle réellement sollicité (16 novembre 2026)

L'interface indique toujours le modèle transmis à l'API Ollama et la fenêtre de contexte configurée, dès l'ouverture de la page après authentification. Les messages d'erreur, les détails de la ligne `erreur_codage` et le message d'interruption mentionnent également ces informations. Le nom affiché est celui **demandé par l'application** via `OLLAMA_MODEL`, et non une garantie que le processus d'inférence a pu se lancer. Le cas `signal: killed` provoque l'arrêt dès la première occurrence ; le message n'indique plus à tort « trois erreurs consécutives ».

Cette modification répond au manque de diagnostic mais **ne supprime pas l'arrêt du processus Ollama**. Le journal du service Ollama et les compteurs mémoire restent nécessaires pour établir la cause de la panne.

## Choix des colonnes CSV et erreur Ollama « unexpected EOF » (16 novembre 2026)

L'interface permet maintenant de **sélectionner explicitement pour chaque fichier CSV** la colonne qui contient le commentaire et, facultativement, celle qui contient le nom de l'auteur. Les colonnes ne sont plus obligatoirement appelées `texte` et `nom_affiche` : des noms comme `commentaire`, `message`, `content` ou tout autre intitulé sont acceptés. Chaque CSV possède ses propres sélecteurs. L'import historique avec `nom_affiche` et `texte` fonctionne toujours sans modification des données.

La colonne choisie pour le commentaire devient `texte` dans la table interne, afin que le prompt libre, la grille de violence, le TXT IRaMuTeQ, la restauration, les statistiques et les exports fonctionnent comme avant. Les autres colonnes CSV sont conservées dans le fichier `codage_commentaires.csv` sous leurs noms préfixés par `csv_`. Les champs `colonne_texte_source` et `colonne_auteur_source` documentent la correspondance. La configuration et la signature du corpus tiennent compte des colonnes sélectionnées : changer le choix n'entraîne pas la réutilisation de réponses produites sur une autre colonne. Les signatures historiques restent reconnues lorsque les colonnes par défaut sont utilisées.

L'erreur `HTTP 500: an error was encountered while running the model: unexpected EOF` signifie que le serveur Ollama a perdu la connexion avec son moteur d'inférence avant la fin de la réponse. Elle ne permet pas, à elle seule, d'attribuer la panne à la RAM : il faut vérifier les journaux du conteneur Ollama autour de l'heure du test. Les causes possibles comprennent une saturation mémoire, un arrêt du moteur, une incompatibilité de l'image Ollama ou une erreur interne. L'application s'arrête désormais immédiatement après cette erreur, pour ne pas répéter inutilement des requêtes vouées à échouer. Cette modification de l'interface **ne répare pas un moteur Ollama instable**.

Dans Coolify, consulter le service `ollama` → `Logs` et rechercher les lignes `error`, `panic`, `OOM`, `killed`, `segmentation fault`, `runner` ou `llama-server`. Pour le système Docker, utiliser `docker logs --tail 100 NOM_DU_CONTENEUR_OLLAMA`. La version réelle du modèle configuré est désormais affichée dans le titre de la page, ce qui permet de vérifier l'utilisation de Qwen3-1.7B ou 4B.

## Import de commentaire.csv

Qwen accepte désormais un ou plusieurs fichiers \`commentaire.csv\` (ou d'autres CSV) contenant les colonnes obligatoires \`nom_affiche\` et \`texte\`. Le séparateur peut être le point-virgule, la virgule ou la tabulation ; les caractères accentués, les emojis et les retours à la ligne contenus dans les champs entre guillemets sont pris en charge. Le CSV peut être encodé en UTF-8, UTF-8 avec BOM ou Windows-1252. Par exemple :

\`\`\`csv
nom_affiche;texte
Beryl;"Rome, Milan et Turin en vrac."
julie;"l'Italie et la France aujourd'hui"
M@th_❤️💙;"Paname influence le monde"
\`\`\`

Chaque ligne CSV devient un document distinct. Le texte originel est conservé et analysé individuellement selon le prompt choisi. Le nom affiché est conservé intégralement dans les colonnes \`nom_affiche\` de \`codage_commentaires.csv\` et de \`reponses_qwen.csv\`. L'identifiant d'auteur du TXT IRaMuTeQ est normalisé et complété par une empreinte pour respecter la syntaxe des métadonnées étoilées, sans perte de la correspondance dans les CSV. L'archive ZIP inclut les fichiers de résultats historiques et ne change pas de nom.

Les imports IRaMuTeQ TXT fonctionnent toujours. On peut charger plusieurs CSV, plusieurs TXT, ou les deux formats dans une même analyse. L'ordre des lignes, les numéros des documents, le fichier source, le statut d'analyse, les réponses, les prompts personnalisés et la possibilité de reprise par CSV sont conservés. Les commentaires vides restent visibles avec le statut \`vide\`, mais ne sont pas envoyés au modèle.

## Erreur 500 « llama-server process has terminated: signal: killed »

Cette erreur signifie que le processus d'inférence a été arrêté de force. Une saturation de la mémoire RAM du VPS ou du groupe mémoire Docker est l'explication la plus probable, mais elle doit être confirmée dans les compteurs du système. Le conteneur `ollama` peut rester actif tandis que son processus `llama-server` est tué. Dans ce cas, le statut global du conteneur ne suffit pas à diagnostiquer la panne.

L'application conserve **Qwen3-4B par défaut**. Le fichier Compose permet maintenant de sélectionner un modèle moins gourmand en RAM avec la variable Coolify `OLLAMA_MODEL=qwen3:1.7b-q4_K_M`. Le modèle 1.7B est officiel, avec des poids d'environ 1,4 Go, contre 2,6 Go pour Qwen3-4B. Le service `charger_modele` téléchargera le même modèle que celui demandé par Streamlit. Le modèle 1.7B est différent et sa qualité de codage doit être validée : ne pas mélanger ses résultats avec ceux du 4B sans conserver le nom du modèle dans le rapport.

La fenêtre de contexte est réglable avec `QWEN_NUM_CTX=1024` (2048 par défaut), au prix d'une réduction de la quantité de texte et de réponse pouvant être prise en compte. La limite Docker d'Ollama est réglable avec `OLLAMA_MEMORY_LIMIT` (valeur 7g par défaut). Ne l'augmentez pas sans examiner la RAM disponible sur le VPS, qui héberge d'autres applications.

Pour confirmer un événement OOM, identifier le conteneur Ollama avec `docker ps`, puis inspecter `docker exec ID_CONTENEUR cat /sys/fs/cgroup/memory.events` si le système utilise cgroup v2. Un compteur `oom_kill` non nul signifie qu'au moins un processus de ce groupe a subi un arrêt faute de mémoire ; comparer les valeurs avant et après l'essai pour l'attribuer à l'analyse en cours. Vérifier aussi `free -h` et `journalctl -k` pour les messages du noyau.

En cas de signal `killed`, l'application interrompt désormais l'analyse dès le premier échec au lieu de renouveler trois fois la requête, tout en conservant les résultats précédents.
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
