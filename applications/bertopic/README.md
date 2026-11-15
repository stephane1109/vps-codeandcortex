# BERTopic — analyse textuelle IRaMuTeQ (Streamlit)

Application Streamlit indépendante, utilisant le BERTopic officiel (version 0.17.4 stable), pour découvrir les structures thématiques de textes courts et de commentaires TikTok en français. Elle ne modifie pas les applications DARTopic ou Qwen3-4B du même dépôt.

## Format des fichiers

Un ou plusieurs fichiers TXT UTF-8 (ou cp1252) au format IRaMuTeQ. Chaque document commence par une ligne de métadonnées étoilées, puis son texte libre sur une ou plusieurs lignes :

    **** *source_original *hatg_manifestations *profil_bfmtv *id_7700347271031885078 *texte_commentaire
    Exemple de texte de commentaire.

Les en-têtes et les textes d'origine sont conservés dans l'export enrichi. Les documents vides et les unités hors échantillon sont conservés avec la modalité non_analyse. Les variables sont également exportées en colonnes dans les fichiers CSV (par exemple variable_profil, variable_id, variable_source). Les variables mal orthographiées dans le corpus ne sont pas corrigées automatiquement.

## Fonctions

Import de plusieurs TXT et prévisualisation des métadonnées. Encodage sémantique multilingue (par défaut paraphrase-multilingual-MiniLM-L12-v2), réduction UMAP, HDBSCAN, interprétation des thèmes par c-TF-IDF. Réglage de la taille minimale des thèmes, de la densité, des n-grammes, du vocabulaire, du modèle de phrases, du nombre de voisins UMAP, de la graine et de la réduction éventuelle des thèmes. Exclusion NLTK des mots vides français et mots supplémentaires. Échantillonnage reproductible plafonné à 4 000 textes sur le VPS ; documents exclus toujours sauvegardés dans le CSV et le TXT de sortie.

BERTopic peut affecter la modalité -1 aux textes hors thème. Cette modalité n'est jamais présentée comme un thème sociologique validé. La probabilité du thème dominant est un indice HDBSCAN approximatif, non une certitude. L'option de calcul de toute la matrice des probabilités reste facultative car elle consomme davantage de mémoire.

Sorties : tableau des thèmes, effectifs, mots et pondérations c-TF-IDF, textes représentatifs, attribution par document, croisements avec une variable étoilée, pourcentages par modalité, test du χ² (avec avertissement si effectifs attendus faibles), V de Cramér. Export unique ZIP comprenant documents_themes.csv, themes.csv, themes_mots.csv, textes_representatifs.csv, corpus_themes_iramuteq.txt et parametres.json. Le TXT enrichi ajoute une seule variable *bertopic_theme_XX, *bertopic_hors_theme ou *bertopic_non_analyse, sans détruire les variables d'origine.

## Déploiement Coolify sur le VPS

Source GitHub : dépôt stephane1109/vps-codeandcortex, branche main.
Type : Dockerfile.
Base directory : applications/bertopic.
Dockerfile : Dockerfile.
Port du service : 8501.
Ajouter une variable d'environnement APP_PASSWORD avec un secret fort ; l'application ne démarre pas publiquement sans ce secret, sauf si APP_ALLOW_PUBLIC=1 est renseigné volontairement.
Configurer un domaine HTTPS. Ajouter un volume persistant monté dans /data/huggingface (cache des modèles téléchargés). Limiter à une analyse concurrente dans ce processus. Éviter de faire travailler BERTopic, DARTopic et Qwen3-4B simultanément sur le VPS de 12 Go de RAM. La première exécution demande une connexion sortante à Hugging Face pour récupérer les poids multilingues.

La construction de l'image téléchargera les roues PyTorch CPU et les dépendances BERTopic. Aucun téléchargement du code ni paramétrage GPU n'est nécessaire. Les dépendances ne sont pas préinstallées sur le serveur avant la construction Docker.

## Analyse R

À partir de l'archive ZIP extraire documents_themes.csv, puis exécuter :

    Rscript analyse_resultats.R documents_themes.csv variable_profil

Le troisième argument facultatif correspond au chemin de sauvegarde CSV du tableau croisé.

## Tests

    python -m unittest discover -s tests -v

Les tests rapides valident la lecture et les exports IRaMuTeQ, ainsi que l'alignement des thèmes avec les unités documentaires. Ils ne remplacent pas un essai réel de l'entraînement BERTopic dans l'image Coolify.

## Limites méthodologiques

Un thème identifié par BERTopic ne constitue ni une représentation sociale ni une prise de position axiologique. La dénonciation, la justification ou la minimisation de la violence exigent un codage interprétatif distinct et une validation humaine. Les commentaires français mal orthographiés peuvent être mal représentés ; la stabilité des thèmes selon la graine et les paramètres doit être évaluée. Les textes classés -1 ne doivent pas être supprimés des bilans sans justification. Un échantillon de 1 000 commentaires n'est pas nécessairement représentatif de la population d'origine.

Référence : Grootendorst, M. (2022). BERTopic: Neural topic modeling with a class-based TF-IDF procedure. https://arxiv.org/abs/2203.05794
Documentation : https://maartengr.github.io/BERTopic/
