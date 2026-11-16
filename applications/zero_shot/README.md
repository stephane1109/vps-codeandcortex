# Zero-shot — classification de corpus pour les sciences humaines et sociales

Application Streamlit indépendante, construite à partir des fonctionnalités d'import et d'export utilisées dans les applications DARTopic, BERTopic et Qwen3-4B de ce dépôt. L'application classe chaque texte dans des catégories **définies par le chercheur**. Elle ne présuppose aucun corpus ni aucune catégorie liée à la violence, au tourisme ou à une autre thématique.

## Modèle et méthode

Modèle : [MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli](https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli), multilingue et adapté à la classification zero-shot par inférence en langage naturel (NLI). Le modèle fonctionne sur CPU avec PyTorch **CPU-only** et Transformers. Il n'utilise ni Ollama, ni Qwen, ni conteneur GPU, ni API d'inférence externe. Le premier lancement nécessite de télécharger les poids sur Hugging Face, ensuite conservés dans un volume Docker.

L'utilisateur saisit librement une catégorie par ligne, au maximum trente. La consigne "Ce commentaire évoque {}." transforme chaque catégorie en une hypothèse soumise au modèle. Le format de cette phrase peut être modifié ; le marqueur \`{}\` doit rester présent exactement une fois. Deux modes sont disponibles. En **multilabel**, plusieurs catégories peuvent dépasser le seuil. En **exclusif**, une seule catégorie est retenue si le score maximal dépasse le seuil. Si aucun score n'atteint ce seuil, la sortie indique \`indetermine\`. Les scores ne sont pas des taux de fiabilité : pour mesurer la qualité de la classification, comparer les sorties à un échantillon codé manuellement.

Le zero-shot **ne découvre pas de thèmes émergents** au sens du topic modeling. Il classe des documents dans les catégories proposées, sans entraînement supplémentaire. Il ne produit pas de commentaire interprétatif libre comme un LLM.

## Corpus, langues et métadonnées

L'application importe un ou plusieurs CSV comportant les colonnes \`nom_affiche\` et \`texte\`. Séparateurs reconnus : point-virgule, virgule, tabulation. Les textes multiligne correctement cités, les accents et les caractères Unicode sont conservés. Encodage pris en charge : UTF-8 (avec ou sans BOM), ou Windows-1252. Plusieurs CSV et TXT IRaMuTeQ peuvent être combinés.

Le format IRaMuTeQ attend les en-têtes \`**** *source_original *profil_exemple\`. Les métadonnées étoilées existantes et les textes originaux sont conservés. Le CSV garde également le pseudonyme original dans \`nom_affiche\`, même lorsque celui-ci contient des emojis.

Le filtre facultatif "Exclure les commentaires identifiés comme non français" utilise Lingua. Les commentaires trop courts ou linguistiquement ambigus **restent** dans le corpus analysable ; les commentaires clairement détectés comme non français sont marqués \`exclu_langue\`, jamais supprimés des exports. Le modèle reste multilingue lorsque le filtre est désactivé.

## Utilisation

À l'ouverture, saisir le mot de passe défini par \`APP_PASSWORD\`. Définir ensuite les catégories et le mode de classification, importer les fichiers, puis utiliser "Tester 3 commentaires" pour vérifier l'inférence sur quelques textes. "Classifier tous les commentaires restants" lance toute la suite sans demander à l'utilisateur de sélectionner des lots. Les micro-lots techniques, de quatre documents, sont internes et servent uniquement à limiter la RAM et à accélérer l'exécution.

Les résultats de chaque document sont enregistrés immédiatement dans SQLite sur le volume \`zero_shot_resultats\`. En cas de redémarrage du conteneur, réimporter **les mêmes fichiers dans le même ordre** et réutiliser les mêmes catégories, phrase d'hypothèse, seuil et filtre linguistique pour retrouver automatiquement le progrès. Le bouton "Réessayer les erreurs" traite uniquement les échecs. On peut aussi importer \`codage_zero_shot.csv\` pour reprendre une analyse ; la signature du corpus et de la configuration est contrôlée.

Le tableau principal présente le texte, le pseudonyme, la catégorie principale, les catégories retenues et les scores, avec lecture détaillée d'un commentaire. Un histogramme présente la répartition des catégories. Le tableau d'origine est disponible dans un panneau secondaire, sans être confondu avec des résultats calculés.

## Exports

Le bouton "Télécharger tous les résultats (ZIP unique)" produit :

\`codage_zero_shot.csv\` : toutes les lignes, les variables initiales, les pseudonymes, les statuts d'analyse, les scores et les colonnes \`classe_01\`, \`classe_02\`, etc. Ce fichier sert aussi à la reprise.

\`scores_zero_shot.csv\` : synthèse par commentaire avec catégorie principale, score maximal et scores individuels.

\`bilan_categories.csv\` : correspondance entre les catégories, les colonnes de scores et les variables IRaMuTeQ, avec les effectifs attribués.

\`bilan_statuts.csv\` : documents traités, non traités, vides, en erreur ou exclus.

\`bilan_langues.csv\` : produit lorsque le filtre linguistique est activé.

\`corpus_zero_shot_iramuteq.txt\` : corpus d'origine enrichi de variables étoilées, comme \`*zs_statut_ok\`, \`*zs_principale_<identifiant>\` et \`*zs_<identifiant>_oui\`. Les identifiants sont normalisés et stabilisés par empreinte ; \`bilan_categories.csv\` les relie à leurs libellés complets.

\`parametres.json\` : modèle, catégories exactes, mode, seuil, phrase d'hypothèse, signature et paramètres de filtrage.

Les commentaires vides et ceux qui n'ont pas été classés restent dans les fichiers, avec un statut explicite. L'archive peut être téléchargée même lorsque l'analyse est partielle.

## Déploiement Coolify et stockage

Créer une **nouvelle application Docker Compose** dans le dépôt \`stephane1109/vps-codeandcortex\`, en utilisant :

\`\`\`text
Branche GitHub : deploy-zero-shot
Répertoire de base : /applications/zero_shot
Fichier Docker Compose : compose.yaml
Service à exposer : app
Port interne HTTP : 8501
\`\`\`

Définir obligatoirement \`APP_PASSWORD\` dans les variables d'environnement Coolify, sans inscrire le mot de passe dans le dépôt. Associer un domaine HTTPS au **service \`app\`**, et non à un autre service. Aucun nom de domaine n'est créé automatiquement par GitHub. Ne pas déployer cette application en remplacement de Qwen, BERTopic ou DARTopic : il s'agit d'un service autonome.

Le Dockerfile installe explicitement \`torch==2.6.0\` depuis l'index **CPU** de PyTorch, puis Streamlit, Transformers et Lingua. Il évite les paquets CUDA qui avaient saturé le disque lors d'un précédent déploiement Ollama. La construction Python, PyTorch et Transformers nécessite néanmoins un espace disque suffisant.

Le fichier Compose contient seulement le service \`app\` et deux volumes persistants nommés \`zero_shot_modeles\` et \`zero_shot_resultats\`. Le premier conserve les poids du modèle, le second la base SQLite. Ils ne doivent **pas être supprimés** au redéploiement. La mémoire du service est limitée à 4 Go par défaut ; elle peut être ajustée avec \`ZERO_SHOT_MEMORY_LIMIT\`. Sur le VPS de 12 Go, éviter les entraînements DARTopic ou BERTopic lourds simultanément. Le téléchargement des poids est déclenché lors du premier test et nécessite une connexion réseau sortante. Il peut durer plus longtemps que les traitements ultérieurs.

L'analyse de très grands corpus (plusieurs dizaines de milliers de textes) reste potentiellement longue sur CPU : elle effectue une comparaison texte × catégorie et sauvegarde la progression. Ce n'est **pas** une tâche exécutée en arrière-plan ; laisser la page ouverte pendant le traitement. Après interruption, l'état peut être récupéré via SQLite, sous réserve de réimporter les fichiers. Il n'y a pas de traitement automatique nocturne ou de file de tâches sur le serveur.

## Tests

Depuis \`applications/zero_shot\`, après installation des dépendances, lancer :

\`\`\`bash
python -m unittest discover -s tests -v
\`\`\`

Les tests couvrent le parsing CSV avec accents et lignes multiples, le TXT IRaMuTeQ, le calcul des catégories avec un classifieur simulé, les identifiants d'export et la reprise SQLite. Ils n'effectuent pas de téléchargement de modèle, ni d'inférence réelle sur le VPS. La vérification fonctionnelle complète doit être effectuée après déploiement, en lançant "Tester 3 commentaires".
