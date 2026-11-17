# Qwen — annotation thématique polyvalente (Streamlit + Ollama)

L'application annote des corpus textuels pour les sciences humaines et sociales. Aucun thème ni domaine de recherche n'est imposé. Le chercheur rédige son prompt, Qwen propose une grille de catégories, puis le chercheur peut modifier les titres et les définitions avant d'annoter les textes. Les thèmes ne sont pas exclusifs : plusieurs catégories peuvent être présentes dans une même unité.

## Prompt initial sur la violence (16 novembre 2026)

L'interface affiche maintenant, par défaut, la consigne courte demandée pour les trois thèmes : dénonciation de la violence, indignation face à la violence et détermination d'un persécuteur face à la violence. La version longue précédente a été remplacée afin de ne pas répéter inutilement les instructions dans une fenêtre Ollama limitée à 1 024 tokens. Ce prompt sert de **point de départ modifiable** et ne réintroduit pas un menu de codage structuré. Le bouton de proposition des thèmes reconstruit une grille à partir de la consigne et d'extraits du corpus, qui reste éditable avant l'annotation. La limite du champ de consigne est passée de 1 600 à 2 200 caractères pour accepter intégralement ce prompt. Lors du redéploiement, seule une session contenant l'ancien texte générique strictement inchangé est migrée ; un prompt personnalisé est préservé.

## Éviter les erreurs HTTP 500 lors de la proposition (16 novembre 2026)

Lorsque le prompt contient explicitement des intitulés de thèmes entre guillemets à la suite de « thèmes : » ou « catégories : », l'application construit la grille directement, sans solliciter Ollama. Les intitulés sont restitués tels quels, les définitions provisoires peuvent être modifiées avant l'analyse et aucune grille propre à la violence n'est imposée par le code. Pour les demandes ouvertes qui nécessitent effectivement une génération, le message détaillé renvoyé par Ollama est affiché en cas d'erreur HTTP, au lieu du seul « 500 Internal Server Error ». Ce changement ne modifie ni le modèle sélectionné dans Coolify ni les paramètres mémoire du VPS. Une erreur interne d'Ollama sur une véritable inférence doit toujours être examinée dans ses journaux.

## Modèles proposés et moteurs (16 novembre 2026)

Le sélecteur unique sous l'import propose six modèles : Qwen3 0.6B, Gemma 3 1B, Llama 3.2 3B et Qwen3 4B pour la génération via Ollama, ainsi que JuriBERT et BERTweetFR pour les encodages spécialisés via Transformers. La variable Coolify `OLLAMA_MODEL` définit le choix initial. Les quatre modèles génératifs sont envoyés à Ollama ; les deux modèles spécialisés passent par le service Transformers indépendant. Le conteneur `charger_modele` télécharge les quatre modèles Ollama, avec un seul modèle chargé simultanément.

## Modèles français spécialisés JuriBERT et BERTweetFR

Un service `encodeurs` indépendant d'Ollama charge les poids de `dascim/juribert-base` et `Yanzhu/bertweetfr-base` par Transformers (CPU). Le conteneur `charger_encodeurs` télécharge les deux modèles sur un volume persistant lors du déploiement. Le même menu principal permet désormais de choisir ces modèles, de tester un texte, d'analyser le corpus entier, de reprendre les erreurs et de télécharger les similarités dans une archive ZIP. Les scores sont calculés par comparaison cosinus entre chaque texte et les définitions de thèmes ; ils restent exploratoires et sont conservés dans des colonnes `similarite_theme_N`. Les textes de plus de 256 tokens peuvent être tronqués. **Ces scores ne sont ni des classifications ni des probabilités** : aucun entraînement supervisé sur la grille de recherche n'a été réalisé. Les annotations thématiques, les validations humaines et les CSV Qwen restent inchangés.

## Classification zero-shot NLI associée aux encodeurs (16 novembre 2026)

Lorsqu'on sélectionne JuriBERT ou BERTweetFR dans le menu principal, une deuxième commande permet de choisir entre la classification zero-shot NLI (par défaut) et les similarités cosinus exploratoires de l'encodeur sélectionné. Le mode NLI utilise indépendamment `MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli`, modèle NLI multilingue de 6 couches et environ 428 Mo de poids, sans supposer que JuriBERT et BERTweetFR ont été entraînés en NLI. Il évalue chaque thème séparément sous forme d'hypothèse, et renvoie les trois scores d'implication, de neutralité et de contradiction ainsi que la relation majoritaire, sans appliquer de seuil arbitraire de classification binaire. Une neutralité ne démontre pas la présence du thème. Les scores restent non calibrés et nécessitent une évaluation sur un corpus annoté manuellement. Le mode de calcul est inclus dans la clé de reprise des analyses. Le déploiement ajoute les poids NLI au cache persistant Transformers et conserve les quatre modèles Ollama inchangés.

## Colonne type_source invisible

Le champ interne `type_source` est conservé en mémoire pour assurer les calculs de comparaison par vidéo, mais il est masqué des tableaux de l'interface et supprimé des CSV exportés. Le champ `source_texte` conserve le nom exact de la colonne choisie dans le fichier importé.

## Utilisation

L'interface propose un seul parcours pour des commentaires courts (y compris des formulations SMS), des publications et des descriptions longues. Les textes longs sont segmentés automatiquement, puis les annotations sont réunies sans changer de grille.

Après authentification, saisir le prompt et importer un ou plusieurs fichiers CSV ou des corpus IRaMuTeQ TXT. Choisir la colonne textuelle à analyser et éventuellement la colonne auteur. Un aperçu des dix premières lignes est affiché, avec toutes les colonnes du CSV d'origine. Les CSV d'une seule colonne de texte sont acceptés.

Dans « Définir les thèmes à partir de votre prompt », cliquer sur « Construire les thèmes avec Qwen à partir du prompt » pour obtenir une proposition de grille, ou ajouter des thèmes manuellement. La grille accepte de un à huit thèmes indépendants ; tous les intitulés et définitions sont modifiables. Elle doit être valide avant de lancer l'annotation.

Les boutons « Tester sur un texte », « Analyser tous les textes restants », « Réessayer les textes en erreur » et « Arrêter l'analyse » sont conservés. L'arrêt est vérifié entre les requêtes : une requête Ollama déjà engagée peut devoir se terminer. Les annotations déjà abouties sont conservées et peuvent être exportées.

## Test Ollama sur un texte court (16 novembre 2026)

Le bouton « Tester sur un texte » exécute désormais un seul appel réel au modèle Ollama configuré, avec un maximum de 350 caractères et un délai de lecture de 60 secondes. Il choisit un texte court parmi les 200 premiers documents en attente, affiche la durée, le modèle utilisé et la sortie ou l'erreur. Si le texte tient intégralement dans le test, son annotation est conservée comme auparavant. Si le texte est plus long, l'essai sur un extrait ne valide pas l'ensemble du document, qui reste en attente. L'analyse complète et le traitement de ses segments sont conservés avec leur délai de lecture historique.

## Noms de colonnes CSV et provenance (16 novembre 2026)

Dans la matrice, **source_texte** affiche à l'identique le nom de la colonne CSV sélectionnée. Le champ interne de provenance `type_source` reste utilisé pour les comparaisons par vidéo, mais n'est plus exposé dans les tableaux ni dans les exports.

## Scores thématiques numériques et statut interne (16 novembre 2026)

Pour chaque thème, Qwen renvoie une annotation booléenne, un indice littéral et un score de présence de 0 à 1 dans la colonne probabilite_theme_N. La colonne probabilite_incertitude présente une estimation numérique de l'ambiguïté ; la case booléenne d'incertitude n'apparaît plus dans les tableaux. Les scores ne sont pas calibrés et ne constituent pas des probabilités fréquentistes ou bayésiennes validées. L'agrégation d'un document long retient le maximum des scores des segments, sans prétendre calculer une probabilité de document. Les corrections humaines s'appliquent aux annotations finales, en conservant les scores originaux du modèle.

La colonne statut_codage est masquée dans les tableaux et dans la matrice thématique exportée, mais conservée dans le CSV de reprise codage_commentaires.csv pour permettre l'arrêt, la poursuite des analyses et l'identification des erreurs.

## Matrice et validation humaine

Les catégories sont numérotées theme_1, theme_2, etc. Leur correspondance avec les titres et définitions du chercheur est conservée dans les fichiers grille_themes_qwen.json et parametres.json.

La matrice_annotations_qwen.csv contient une ligne par unité textuelle, ses métadonnées, chaque thème booléen, les indices littéraux justificatifs, l'incertitude, la justification, les corrections manuelles et le statut de traitement. Les colonnes manuel_theme_N conservent le contrôle humain ; les colonnes final_theme_N appliquent les corrections sans écraser la sortie initiale de Qwen.

L'interface affiche la matrice, les sous-corpus regroupés par thème, les fréquences par source et un panneau de validation ou correction. Un même texte peut figurer dans plusieurs catégories. Un texte non traité n'est pas considéré comme une absence de thème.

## Comparaison entre sources

Le panneau facultatif des sources permet de renseigner un identifiant vidéo et d'associer des colonnes à la description de la plateforme, au texte auteur, à la transcription et aux commentaires. La même grille et le même prompt sont alors appliqués aux différentes sources. L'absence d'une source est distinguée d'une annotation négative. Le fichier comparaison_videos_qwen.csv contient les états oui, non, non_traite, partiel et non_disponible, ainsi que les discordances effectivement mesurables.

Les corpus IRaMuTeQ TXT préservent leurs en-têtes et leurs textes. Les thèmes codés sont ajoutés sous forme de variables étoilées, par exemple *theme_1_oui ou *theme_1_non.

## Téléchargement et reprise

Le ZIP unique contient codage_commentaires.csv, reponses_qwen.csv, matrice_annotations_qwen.csv, corpus_qwen_iramuteq.txt, grille_themes_qwen.json, bilan_sources_themes_qwen.csv, comparaison_videos_qwen.csv, les sous-corpus textes_theme_N_qwen.csv et les paramètres. Le ZIP et le CSV de reprise sont générés au clic, pour éviter leur construction répétée lors de chaque affichage.

Le fichier de reprise conserve une empreinte du corpus et de la configuration. Une reprise n'est acceptée que si les fichiers, le prompt, les thèmes et leurs définitions concordent. Le script analyse_resultats.R réalise des croisements exploratoires entre les catégories et les variables du corpus.

## Coolify, Docker et mémoire

L'application Streamlit écoute sur le port interne 8501 derrière le proxy HTTPS de Coolify. Le moteur Ollama est accessible sur le réseau interne Docker et ne doit pas être exposé sur Internet. Configurer APP_PASSWORD pour protéger l'application.

OLLAMA_MODEL permet de choisir le modèle Qwen. QWEN_NUM_CTX règle la fenêtre de contexte (2048 tokens par défaut). QWEN_APP_MEMORY_LIMIT fixe le plafond de Streamlit (1 Gio par défaut), séparé de OLLAMA_MEMORY_LIMIT (7 Gio par défaut). Sur le VPS, contrôler les ressources avec docker stats et free -h avant d'augmenter ces limites.

Une erreur HTTP 502 ou une interruption d'Ollama ne permet pas à elle seule de conclure à un problème de RAM ; consulter les journaux Docker et le proxy. La découverte thématique et la classification peuvent être imparfaites : valider manuellement un échantillon avant toute interprétation scientifique.


## Conservation automatique des analyses et reprise après interruption (17 novembre 2026)

L'application enregistre **avant le premier traitement** la copie des fichiers CSV/TXT d'origine, le prompt, les colonnes choisies, le modèle, la grille et les paramètres. Après **chaque texte** (annotation réussie ou erreur technique), elle écrit les résultats dans SQLite avec une transaction atomique. Les validations humaines sont également enregistrées. Le service Streamlit utilise un volume Docker nommé `analyses_qwen` monté sur `/data/analyses_qwen`. Les données persistent donc après un redémarrage du conteneur ou une perte de session navigateur, sauf suppression volontaire du volume ou du VPS.

Après authentification, une nouvelle session recharge automatiquement la dernière analyse sauvegardée, ses fichiers et ses paramètres. L'interface « Analyses enregistrées sur le VPS » permet de choisir d'autres travaux ou de commencer un nouveau corpus sans supprimer les sauvegardes. Les lignes déjà traitées sont restaurées et l'utilisateur reprend uniquement les lignes restantes avec le bouton existant. Les CSV et le ZIP d'export restent disponibles.

**Limite :** les boucles d'analyse s'exécutent encore dans la session Streamlit. Si le navigateur ou le conteneur interrompt le calcul, le travail n'avance pas hors connexion ; il peut néanmoins être repris sans perdre les résultats enregistrés. Cette amélioration n'est pas un ordonnanceur autonome ou un traitement continu en arrière-plan. Les exécutions antérieures à cette mise à jour qui n'ont pas été exportées ne peuvent pas être recréées à partir d'une session Streamlit disparue.

Le SQLite contient les textes bruts : sécuriser les accès au VPS et conserver le mot de passe de l'application. La base n'est pas chiffrée par l'application. Les sauvegardes persistantes ne remplacent pas une sauvegarde externe du volume `analyses_qwen`.
