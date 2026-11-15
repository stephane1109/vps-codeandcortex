# DARTopic – IRaMuTeQ (Streamlit)

**Statut : reproduction expérimentale non officielle**, construite à partir de Seo, Cho et Yoo (2026), [article ACL](https://aclanthology.org/2026.aacl-long.241/). Le code des auteurs n'a pas été identifié comme publiquement disponible le 15 novembre 2026. Il ne faut pas comparer les scores à la publication comme s'il s'agissait de la même implémentation. Les auteurs n'ont évalué que des corpus anglais.

## Fonction

Importer un ou plusieurs fichiers `.txt` structurés sous la forme `**** *source_original *id_123 *profil_exemple *texte_commentaire`, suivis du texte libre sur une ou plusieurs lignes. L'application préserve les unités documentaires, l'intégralité des variables étoilées et le texte d'origine. Les textes vides sont conservés mais non analysés. Choix du nombre de thèmes, du nombre d'époques, de l'encodeur, du seuil des graphes, du vocabulaire, de la graine, des mots vides. Production des proportions de thèmes par document, mots caractéristiques, évolution de la perte et croisement exploratoire par métadonnées. Exports CSV, TXT IRaMuTeQ enrichi et ZIP unique.

Architecture : encodeur Transformer figé (par défaut **multilingue** pour commentaires français), graphe de similarité cosinus entre tokens, GCN à deux couches, agrégation moyenne, VAE et décodeur multinomial. Les paramètres tels que le poids KL et les dimensions cachées sont des choix de cette reproduction. L'inférence est calculée sur CPU, et la mémoire dépend du corpus.

## Import des commentaires CSV (15 novembre 2026)

Un fichier CSV peut remplacer le TXT IRaMuTeQ, sans suppression de la compatibilité TXT.
La première ligne contient obligatoirement les noms de colonnes :

    nom_affiche;texte
    Beryl;"Rome, Milan et Turin en vrac."
    julie;"l'Italie et la France aujourd'hui"
    M@th_❤️💙;"Paname influence le monde"

Séparateurs reconnus : \`; \`, \`,\` et tabulation, avec ou sans BOM UTF-8 ; prise en charge du texte entre guillemets, des retours à la ligne dans une cellule, des accents et des emoji. Les colonnes \`nom_affiche\` et \`texte\` sont indispensables ; la casse et les espaces entourant les noms de colonnes sont ignorés. Chaque ligne devient un document distinct, même si le commentaire est vide. Un texte vide n'est pas entraîné mais reste présent dans les résultats.

Le CSV source conserve exactement le nom affiché dans la colonne \`nom_affiche\` du fichier \`documents_themes.csv\` ainsi que le texte dans \`texte\`. Le fichier TXT IRaMuTeQ généré contient un identifiant d'auteur normalisé et une empreinte stable pour respecter la syntaxe des variables étoilées, ainsi que l'identifiant de la ligne, sans insérer d'emoji ou d'espaces dans l'en-tête. La correspondance exacte reste disponible dans le CSV. Un import mixte de plusieurs CSV et TXT IRaMuTeQ conserve la numérotation globale et l'ordre des documents.

### Stopwords NLTK

La liste française est chargée depuis \`nltk.corpus.stopwords.words("french")\` ; il ne s'agit pas d'une liste de mots vide reconstruite arbitrairement. L'interface indique le nombre de mots exclus, permet de les visualiser, d'ajouter des exclusions manuelles et de conserver les négations si nécessaire. L'option de conservation des négations est désactivée par défaut pour ne pas changer les résultats de l'ancienne configuration. Les stopwords sont retirés uniquement du vocabulaire \`CountVectorizer\` ; ils restent présents dans le texte transmis à l'encodeur Transformer. Les mots originaux et les pseudonymes ne sont pas modifiés.

## Correctifs du 15 novembre 2026 : thèmes différenciés, 30 000 textes et langue française

Le modèle reste une reproduction expérimentale non officielle, enrichie d'une **initialisation et d'un ancrage NMF** pour limiter les thèmes identiques. Le poids de régularisation KL a été réduit et son effet est introduit progressivement. Le champ \`mots\` classe désormais les quinze mots selon un score combinant leur probabilité dans le thème et leur spécificité par rapport aux autres thèmes. Le champ \`mots_frequents\` conserve les termes les plus fréquents dans les thèmes pour comparaison. Ce changement nécessite de recalculer les analyses anciennes.

La nouvelle tokenisation lexicale sépare les contractions au lieu de conserver l'apostrophe dans les tokens. Par exemple, \`c'est\` se sépare en \`c\` et \`est\` ; les mots d'une seule lettre ne sont pas retenus dans le vocabulaire. Les stopwords français restent chargés depuis NLTK, et peuvent conserver les négations. Les termes de contenu comme "violence", "police" ou "RN" ne sont pas exclus automatiquement. Le seuil de fréquence documentaire maximale (95 % par défaut) filtre les mots apparaissant dans une proportion excessive de documents, sans modifier les textes soumis à l'encodeur sémantique. Ce filtrage ne remplace pas une analyse sociologique.

L'interface autorise **jusqu'à 30 000 textes admissibles** par analyse, et conserve les commentaires exclus et hors échantillon dans les exports avec un statut explicite. Le traitement des plongements de tokens et des graphes est réalisé par blocs et enregistré temporairement sur disque via des fichiers memmap. Les calculs NMF et l'optimisation par lots restent coûteux sur CPU : l'augmentation du plafond **ne garantit pas** que 30 000 textes seront rapides ou exécutables simultanément avec les autres applications du VPS. Prévoir plusieurs Go de stockage temporaire (pour 30 000 textes et 64 tokens, environ 2 Go de données intermédiaires, selon l'encodeur). Le dossier peut être configuré par \`DARTOPIC_SCRATCH_DIR\` ; \`/tmp\` par défaut. Il est supprimé à la fin d'un calcul normal. Une interruption brutale peut laisser des fichiers à nettoyer.

### Filtre linguistique

L'option "Exclure les commentaires identifiés comme non francophones" est activée par défaut. Le détecteur **Lingua 2.1.1**, compatible avec Python 3.11, compare le français à treize autres langues. Son évaluation se fait **sur les textes complets avant l'échantillonnage thématique**. La colonne \`statut_langue\` prend les valeurs \`francais\`, \`hors_francais\` et \`indetermine\`. La colonne \`langue_detectee\` donne la langue candidate dominante et les scores relatifs sont exportés.

Par défaut, les textes jugés non francophones sont écartés de l'apprentissage, tandis que les textes trop courts ou ambigus restent admissibles. Une option permet également d'écarter les indéterminés. Les erreurs de classification linguistique sont possibles, notamment pour les réponses très courtes, les emojis et les langues mélangées. Les commentaires exclus restent présents dans \`documents_themes.csv\` et dans le TXT IRaMuTeQ exporté. Le fichier \`bilan_langues.csv\` complète l'archive ZIP.

### Diagnostic des résultats

L'application calcule le chevauchement moyen des listes des quinze mots distinctifs et le nombre de thèmes sans document majoritaire. Une alerte est affichée lorsque plusieurs thèmes restent trop similaires. **L'initialisation NMF ne garantit pas que les thèmes correspondent à des catégories sociologiques** : leurs interprétations doivent être confrontées aux textes représentatifs et à BERTopic.

## Coolify

Créer une application Dockerfile depuis `main`, répertoire de base `applications/dartopic`, Dockerfile `Dockerfile`, port `8501`, exposé uniquement derrière un domaine HTTPS avec authentification. Définir `APP_PASSWORD` avec un secret fort. Le lancement est refusé si cette variable manque, sauf `APP_ALLOW_PUBLIC=1` expressément choisi. Monter un volume persistant à `/data/huggingface` pour éviter le téléchargement du modèle à chaque redéploiement. Prévoir une limite mémoire et limiter l'usage simultané avec Qwen3, car le VPS héberge d'autres applications. Aucun secret ne doit être commité.

Le premier calcul exige l'accès à Hugging Face pour obtenir les poids du modèle (~plusieurs centaines de Mo). Il peut être lent sur CPU. Valeurs de départ suggérées : 8 thèmes, 35 époques, 64 tokens, 1 000 documents maximum, lot de 16. Limite de sécurité de 4 000 documents par calcul. Pour traiter un grand corpus, vérifier d'abord les résultats sur un échantillon représentatif puis programmer des lots reproductibles.

## Analyse R

Le script complémentaire `analyse_resultats.R` calcule une table thèmes × variables et le test du chi carré lorsque les effectifs le permettent. Il s'utilise sur le CSV exporté, et n'est pas nécessaire au démarrage de Streamlit.

## Limites

Des thèmes ne sont ni des catégories axiologiques, ni des représentations sociales. Les probabilités ne sont pas calibrées comme des certitudes de codage. L'évaluation en français informel requiert une annotation manuelle, l'étude de la stabilité selon la graine et une comparaison à des méthodes de référence.
