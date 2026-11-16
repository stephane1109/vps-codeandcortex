# Qwen3-4B — IRaMuTeQ (Streamlit + Ollama)

Cette application Python code les commentaires français et renvoie des propositions de variables binaires `violence_evoquee`, `violence_denoncee`, `violence_justifiee`, `violence_minimisee`, `interpretation_indeterminee`, ainsi qu'un `acteur_cible`, un extrait d'appui (`indice_textuel`) et une justification. Les catégories ne sont pas exclusives. En cas d'erreur ou d'incertitude, la ligne est conservée et signalée. **Les sorties du LLM ne sont pas des annotations humaines ni une validation des représentations sociales.**

Le modèle utilisé est `qwen3:4b-q4_K_M` via [Ollama](https://ollama.com/library/qwen3), servi uniquement sur le réseau privé de la composition Docker. Les poids 4B quantifiés s'exécutent sur CPU mais leur vitesse dépend fortement de la charge du VPS. Aucune clé API Qwen externe ni service cloud d'inférence n'est requis. Télécharger le modèle nécessite un accès réseau sortant au démarrage.

## Import et export

Importer un ou plusieurs corpus texte IRaMuTeQ : `**** *source_original *id_123 *profil_exemple *texte_commentaire` puis commentaire sur les lignes suivantes. L'ensemble des métadonnées étoilées et du texte est conservé. Option de contexte commun (description de vidéo saisie par le chercheur) et inclusion de métadonnées. Sans contexte ajouté, le modèle n'accède à **aucune image, aucun son, aucune vidéo**. Le modèle analyse au maximum 3 000 caractères de texte et 1 200 caractères de contexte par ligne ; toute troncature est signalée.

L'interface propose un parcours unique : écrire un prompt, importer des commentaires ou des textes longs, annoter chaque texte dans trois thèmes indépendants, comparer les sources et corriger les annotations. Le prompt est conservé dans `parametres.json`.

L'interface ne demande plus le nombre de commentaires par lot. Le bouton **Analyser tous les textes restants** parcourt automatiquement les unités non traitées, dans leur ordre d'origine, et affiche un indicateur de progression. Une autre commande permet de réessayer les commentaires en erreur. Le traitement s'arrête après trois erreurs consécutives de communication ou de décodage, afin d'éviter de multiplier des requêtes inutiles. Les commentaires vides restent identifiés et les résultats partiels restent accessibles dans la session Streamlit. **La progression ne s'exécute pas en arrière-plan** : en cas de redémarrage du conteneur ou de perte de session, importer un CSV précédemment téléchargé pour reprendre.

Le ZIP unique regroupe le fichier historique \`codage_commentaires.csv\`, le nouveau \`reponses_qwen.csv\`, le TXT IRaMuTeQ enrichi et les paramètres, dont la consigne. Le CSV de reprise inclut une signature du corpus et une empreinte des paramètres, afin de ne pas mélanger des analyses fondées sur des prompts différents. Les anciens CSV sans empreinte de prompt ne sont admis en reprise qu'en mode structuré historique, avec un avertissement sur l'impossibilité de vérifier la consigne exacte.

Le même prompt sert à analyser les commentaires courts et les textes descriptifs longs. Le moteur segmente automatiquement les textes longs sans modifier la grille des trois thèmes.

## Affichage des réponses et diagnostic du modèle (15 novembre 2026)

L'interface donne maintenant la priorité aux **réponses réellement générées par Qwen**, avec les colonnes `nom_affiche`, `texte`, `reponse_qwen` et `statut_codage`. Une sélection par numéro de document permet de lire intégralement, dans deux zones distinctes, le commentaire d'origine et la réponse produite par le LLM. Le tableau intégral des variables IRaMuTeQ et des métadonnées CSV est conservé dans un panneau secondaire.

L'utilisateur peut lancer **Tester sur un texte** pour vérifier la génération d'une réponse avant d'exécuter **Analyser tous les textes restants**. Le bouton principal conserve l'analyse automatique sans lots. En l'absence de résultat, une explication indique si les commentaires attendent encore l'analyse, si Ollama est indisponible, si le modèle manque ou si les requêtes ont échoué. Une section distincte **Erreurs de Qwen** présente `statut_codage` et `erreur_codage` pour les commentaires concernés. Les boutons d'analyse sont désactivés lorsque l'API Ollama ne répond pas ou que le modèle n'est pas téléchargé.

Le contenu brut importé n'est jamais présenté comme une annotation générée par Qwen. Les exports CSV et IRaMuTeQ, le ZIP unique et la reprise restent disponibles.

## Aperçu des dix premières lignes du CSV (16 novembre 2026)

Dans la section **Choix des colonnes CSV**, chaque fichier CSV importé possède désormais un tableau d'aperçu affichant ses dix premières lignes de données, ou toutes ses lignes s'il en comporte moins de dix. Les noms et l'ordre de toutes les colonnes d'origine sont conservés dans cet aperçu, quelle que soit la colonne sélectionnée pour le commentaire et l'auteur. Les cellules multiligne sont lues comme un seul commentaire. Cet affichage n'envoie aucune donnée au modèle et ne limite pas l'importation complète aux dix lignes visibles. Le comportement des corpus IRaMuTeQ TXT, des sélecteurs, des prompts, de la reprise et de tous les exports reste inchangé.

## Affichage systématique du modèle réellement sollicité (16 novembre 2026)

L'interface indique toujours le modèle transmis à l'API Ollama et la fenêtre de contexte configurée, dès l'ouverture de la page après authentification. Les messages d'erreur, les détails de la ligne `erreur_codage` et le message d'interruption mentionnent également ces informations. Le nom affiché est celui **demandé par l'application** via `OLLAMA_MODEL`, et non une garantie que le processus d'inférence a pu se lancer. Le cas `signal: killed` provoque l'arrêt dès la première occurrence ; le message n'indique plus à tort « trois erreurs consécutives ».

Cette modification répond au manque de diagnostic mais **ne supprime pas l'arrêt du processus Ollama**. Le journal du service Ollama et les compteurs mémoire restent nécessaires pour établir la cause de la panne.

## Import de CSV volumineux et erreur 502 (16 novembre 2026)

L'application utilise désormais une limite mémoire de **1 Gio** par défaut pour le service Streamlit (`QWEN_APP_MEMORY_LIMIT` dans les variables Coolify), au lieu de 768 Mio, afin de disposer d'une marge supérieure pour les importations volumineuses. Cette valeur est un **plafond et non une réservation** ; elle ne doit pas être augmentée sans vérifier la RAM disponible sur le VPS. Le moteur Ollama dispose de sa propre limite, indépendante.

Pour les CSV de plusieurs dizaines de mégaoctets, l'import complet et le tableau des documents sont maintenant conservés dans la session Streamlit : modifier un prompt, un thème ou un filtre ne provoque plus un nouvel import intégral. Changer le CSV ou les colonnes sélectionnées déclenche une nouvelle lecture. L'aperçu des dix premières lignes est également réutilisé. Les colonnes sources sont partagées en lecture seule avec la table d'analyse ; les colonnes de résultats restent indépendantes.

**Le ZIP unique et le CSV de reprise ne sont plus générés automatiquement à chaque réaffichage.** Les deux boutons de téléchargement existants sont conservés ; Streamlit prépare le fichier demandé seulement lorsque l'utilisateur clique dessus. Cette possibilité nécessite Streamlit 1.54 ou plus récent. Les formats d'export, les colonnes, les noms de fichiers et la reprise ne sont pas changés.

Un code HTTP 502 n'est pas une preuve à lui seul d'un dépassement de mémoire : le proxy peut également perdre la connexion pour d'autres raisons. Vérifier la mémoire et les redémarrages du service Streamlit, par exemple avec `docker inspect NOM_APP --format '{{.State.OOMKilled}} {{.State.ExitCode}} {{.RestartCount}}'`, puis consulter `docker logs --tail 100 NOM_APP` et les logs du proxy Coolify. Si la 502 survient pendant le transfert avant l'importation, il faut aussi examiner le proxy et son routage.

## Déblocage des boutons après import CSV (16 novembre 2026)

Après importation des commentaires, l'application présente un diagnostic de préparation explicite : nombre de textes restants, validité du prompt et des trois thèmes, et état de l'inventaire Ollama. Le panneau d'édition des six champs de la grille est désormais replié par défaut pour rendre les commandes d'analyse plus rapidement accessibles. Les trois titres restent visibles et tous les champs demeurent éditables.

La vérification de l'inventaire Ollama `/api/tags` n'interdit plus automatiquement les commandes d'analyse. Cette vérification ne prouve pas qu'une inférence aboutira et peut temporairement échouer même si le moteur fonctionne. Le bouton **Tester sur un texte** permet d'envoyer une véritable requête, puis d'afficher le résultat ou une erreur technique. Les boutons restent désactivés si le prompt est vide, la grille invalide ou qu'aucun document pertinent n'est en attente ; chaque blocage est signalé immédiatement au-dessus des commandes.

Les sélecteurs CSV, l'aperçu des dix lignes, les analyses, le CSV de reprise et le ZIP unique restent disponibles.

## Arrêt manuel de l'analyse (16 novembre 2026)

Le bouton **Arrêter l'analyse**, placé à côté des commandes de lancement, demande l'interruption du traitement. Les annotations réalisées sont conservées dans la session et dans les exports partiels ; les textes restants gardent leur statut initial. Une requête Ollama déjà envoyée peut devoir se terminer avant que l'arrêt soit pris en compte. Cliquer sur **Analyser tous les textes restants** permet de reprendre les unités non traitées. La reprise après perte de session reste assurée par l'import du CSV de résultats, comme auparavant.

## Parcours unique d'annotation des textes et commentaires (16 novembre 2026)

L'interface ne présente plus la sélection de modes « Codage structuré sur la violence », « Analyse libre » ou « Classification en trois thèmes ». Elle propose directement **un seul prompt d'annotation** et la **matrice de trois thèmes non exclusifs**. La même grille s'applique aussi bien aux commentaires très courts de type SMS qu'aux descriptions longues. Les textes longs sont découpés en segments automatiquement puis leurs annotations réunies ; la longueur n'entraîne pas un changement de méthode.

Dans « Choix des colonnes CSV », la colonne principale du texte est toujours choisie directement. La provenance textuelle et la comparaison de plusieurs colonnes au sein d'une vidéo sont des paramètres facultatifs dans un panneau replié. Un CSV avec une seule colonne de commentaires ne nécessite donc aucun paramétrage de sources supplémentaires. La distinction des sources textuelles sert uniquement aux regroupements, au bilan et aux comparaisons, et non au choix de l'algorithme.

Le ZIP continue de contenir la matrice complète, les sous-corpus par thème, le bilan par source, la comparaison entre sources lorsqu'un identifiant vidéo est renseigné, les variables d'analyse et le texte original. Le mécanisme de reprise et la validation manuelle sont conservés.

## Classification des discours sur la violence en trois thèmes (16 novembre 2026)

L'analyse utilise une matrice unique de trois thèmes indépendants, sans choix de méthode.

La grille initiale distingue les catégories suivantes : **Dénonciation de la violence**, définie comme une condamnation ou une critique normative explicite de violences ; **Indignation face à la violence**, définie comme une réaction affective explicite de colère, de révolte, de consternation ou d'injustice ; **Détermination d'un persécuteur face à la violence**, définie comme la désignation explicite d'un acteur supposé responsable d'une violence, d'une persécution ou d'une oppression. Cette dernière catégorie décrit une attribution de responsabilité dans le discours et ne constitue pas une preuve de responsabilité objective.

Le classement conserve le mode exclusif préexistant : Qwen détermine **un thème principal** par commentaire, parmi `theme_1`, `theme_2`, `theme_3`, ou `indetermine` si les indices explicites sont insuffisants ou qu'aucune dominante ne se distingue. Ces catégories peuvent se chevaucher dans les discours, mais le résultat actuel représente exclusivement la catégorie dominante. Il faut conserver cette limite méthodologique dans l'interprétation du corpus.

L'utilisateur peut toujours modifier librement les titres et les définitions de la grille. Le bouton **Affiner les définitions avec Qwen** remplace la proposition entièrement libre : les nouvelles définitions sont proposées à partir de l'échantillon sans changer les trois intitulés de la grille courante. Aucun résultat n'est présenté comme une annotation humaine validée.

L'export ZIP conserve les fichiers historiques et les variables `theme_retenu`, `theme_intitule`, `these_retenue`, `these_intitule`, `indice_textuel` et `justification`, ainsi que le bilan des thèmes, la grille JSON, le corpus IRaMuTeQ et le prompt dans les paramètres. Les sélecteurs CSV, l'aperçu des dix premières lignes, la reprise CSV et les autres outils ne sont pas supprimés.

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
