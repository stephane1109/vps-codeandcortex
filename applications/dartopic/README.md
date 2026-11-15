# DARTopic – IRaMuTeQ (Streamlit)

**Statut : reproduction expérimentale non officielle**, construite à partir de Seo, Cho et Yoo (2026), [article ACL](https://aclanthology.org/2026.aacl-long.241/). Le code des auteurs n'a pas été identifié comme publiquement disponible le 15 novembre 2026. Il ne faut pas comparer les scores à la publication comme s'il s'agissait de la même implémentation. Les auteurs n'ont évalué que des corpus anglais.

## Fonction

Importer un ou plusieurs fichiers `.txt` structurés sous la forme `**** *source_original *id_123 *profil_exemple *texte_commentaire`, suivis du texte libre sur une ou plusieurs lignes. L'application préserve les unités documentaires, l'intégralité des variables étoilées et le texte d'origine. Les textes vides sont conservés mais non analysés. Choix du nombre de thèmes, du nombre d'époques, de l'encodeur, du seuil des graphes, du vocabulaire, de la graine, des mots vides. Production des proportions de thèmes par document, mots caractéristiques, évolution de la perte et croisement exploratoire par métadonnées. Exports CSV, TXT IRaMuTeQ enrichi et ZIP unique.

Architecture : encodeur Transformer figé (par défaut **multilingue** pour commentaires français), graphe de similarité cosinus entre tokens, GCN à deux couches, agrégation moyenne, VAE et décodeur multinomial. Les paramètres tels que le poids KL et les dimensions cachées sont des choix de cette reproduction. L'inférence est calculée sur CPU, et la mémoire dépend du corpus.

## Coolify

Créer une application Dockerfile depuis `main`, répertoire de base `applications/dartopic`, Dockerfile `Dockerfile`, port `8501`, exposé uniquement derrière un domaine HTTPS avec authentification. Définir `APP_PASSWORD` avec un secret fort. Le lancement est refusé si cette variable manque, sauf `APP_ALLOW_PUBLIC=1` expressément choisi. Monter un volume persistant à `/data/huggingface` pour éviter le téléchargement du modèle à chaque redéploiement. Prévoir une limite mémoire et limiter l'usage simultané avec Qwen3, car le VPS héberge d'autres applications. Aucun secret ne doit être commité.

Le premier calcul exige l'accès à Hugging Face pour obtenir les poids du modèle (~plusieurs centaines de Mo). Il peut être lent sur CPU. Valeurs de départ suggérées : 8 thèmes, 35 époques, 64 tokens, 1 000 documents maximum, lot de 16. Limite de sécurité de 4 000 documents par calcul. Pour traiter un grand corpus, vérifier d'abord les résultats sur un échantillon représentatif puis programmer des lots reproductibles.

## Analyse R

Le script complémentaire `analyse_resultats.R` calcule une table thèmes × variables et le test du chi carré lorsque les effectifs le permettent. Il s'utilise sur le CSV exporté, et n'est pas nécessaire au démarrage de Streamlit.

## Limites

Des thèmes ne sont ni des catégories axiologiques, ni des représentations sociales. Les probabilités ne sont pas calibrées comme des certitudes de codage. L'évaluation en français informel requiert une annotation manuelle, l'étude de la stabilité selon la graine et une comparaison à des méthodes de référence.
