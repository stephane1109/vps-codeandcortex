# Qwen — annotation thématique polyvalente (Streamlit + Ollama)

L'application annote des corpus textuels pour les sciences humaines et sociales. Aucun thème ni domaine de recherche n'est imposé. Le chercheur rédige son prompt, Qwen propose une grille de catégories, puis le chercheur peut modifier les titres et les définitions avant d'annoter les textes. Les thèmes ne sont pas exclusifs : plusieurs catégories peuvent être présentes dans une même unité.

## Prompt initial sur la violence (16 novembre 2026)

L'interface affiche maintenant, par défaut, le prompt sur les trois thèmes demandés : dénonciation de la violence, indignation face à la violence et détermination d'un persécuteur face à la violence. Ce prompt sert de **point de départ modifiable** et ne réintroduit pas un menu de codage structuré. Le bouton de proposition des thèmes reconstruit une grille à partir de la consigne et d'extraits du corpus, qui reste éditable avant l'annotation. La limite du champ de consigne est passée de 1 600 à 2 200 caractères pour accepter intégralement ce prompt. Lors du redéploiement, seule une session contenant l'ancien texte générique strictement inchangé est migrée ; un prompt personnalisé est préservé.

## Utilisation

L'interface propose un seul parcours pour des commentaires courts (y compris des formulations SMS), des publications et des descriptions longues. Les textes longs sont segmentés automatiquement, puis les annotations sont réunies sans changer de grille.

Après authentification, saisir le prompt et importer un ou plusieurs fichiers CSV ou des corpus IRaMuTeQ TXT. Choisir la colonne textuelle à analyser et éventuellement la colonne auteur. Un aperçu des dix premières lignes est affiché, avec toutes les colonnes du CSV d'origine. Les CSV d'une seule colonne de texte sont acceptés.

Dans « Définir les thèmes à partir de votre prompt », cliquer sur « Construire les thèmes avec Qwen à partir du prompt » pour obtenir une proposition de grille, ou ajouter des thèmes manuellement. La grille accepte de un à huit thèmes indépendants ; tous les intitulés et définitions sont modifiables. Elle doit être valide avant de lancer l'annotation.

Les boutons « Tester sur un texte », « Analyser tous les textes restants », « Réessayer les textes en erreur » et « Arrêter l'analyse » sont conservés. L'arrêt est vérifié entre les requêtes : une requête Ollama déjà engagée peut devoir se terminer. Les annotations déjà abouties sont conservées et peuvent être exportées.

## Noms de colonnes CSV et provenance (16 novembre 2026)

Dans la matrice, **source_texte** affiche à l'identique le nom de la colonne CSV sélectionnée, et non une étiquette comme « commentaire ». **type_source** conserve séparément la provenance facultative (commentaire, texte IA, texte auteur, voice-to-text ou texte libre). La comparaison des sources d'une même vidéo continue à utiliser cette catégorie. Le bilan présente les deux champs, et les exports conservent les noms d'origine.

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
