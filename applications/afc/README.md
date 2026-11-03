# Application web AFC — FactoMineR

Cette application Streamlit importe un fichier CSV puis calcule **une analyse factorielle des correspondances (AFC)** par la fonction **`FactoMineR::CA()`** dans R. Les données peuvent provenir de ScrapTikTok ou de tout autre tableau où une observation est représentée par une ligne.

## Fonctionnement

Importer un CSV (détection des séparateurs `;`, `,`, tabulation ou `|`, avec choix manuel possible), puis choisir une variable en lignes et une variable en colonnes. Les classes catégorielles de ScrapTikTok sont déjà prises en charge, notamment `vues_classe`, `likes_classe`, `commentaires_classe`, `partages_classe`, `favoris_classe`, `classe_taux_engagement`, `classe_abonnes`, `is_verified`, `region_code`, `type_media`.

L'analyse s'effectue exclusivement à partir d'un fichier CSV ou TXT importé par l'utilisateur. Aucun corpus de démonstration ni générateur de données fictives n'est proposé dans l'interface.

Le panneau de paramétrage permet de conserver uniquement les lignes `retenue`, de supprimer les doublons selon `publication_id`, d'exclure les modalités indéterminées, de traiter les cellules vides comme une modalité ou de les exclure, de filtrer sur une troisième variable, de limiter la cardinalité, et de régler le nombre de simulations Monte-Carlo.

La table de contingence s'affiche **avant** le lancement. Les contrôles rejettent les tableaux à une seule modalité et les cas d'inertie nulle. Le calcul rend un plan factoriel, l'histogramme des inerties, le Chi-deux, sa valeur p, le V de Cramér, les effectifs théoriques, résidus, profils, coordonnées, contributions et cos². Les résultats sont téléchargeables en ZIP et les tableaux séparément en CSV.

Sur le **plan à deux dimensions**, seules les modalités présentant une p-value brute inférieure ou égale à **0,05** sont affichées. Pour chaque modalité des lignes ou des colonnes, le moteur calcule un test du Chi-deux sur un tableau opposant cette modalité à toutes les autres de la même variable ; en présence d'effectifs attendus inférieurs à cinq, il estime la p-value par Monte-Carlo. Le fichier `18_significativite_modalites.csv` conserve toutes les modalités, les p-values brutes, les p-values corrigées par Benjamini-Hochberg et les décisions au seuil de 0,05. Les calculs factoriels, coordonnées, contributions, cos² et autres exports demeurent établis sur **le tableau complet**, même pour les modalités masquées. Le graphique à un seul axe reste inchangé et ne subit pas ce filtre.

Ce test par modalité évalue son **association globale** avec l'autre variable ; il **ne teste pas** la significativité de sa coordonnée sur un axe particulier. Le filtrage par p-value brute est exploratoire : les corrections de comparaisons multiples, les effectifs et les contributions doivent être examinés avant toute interprétation confirmatoire.

## Déploiement sur VPS avec Docker Compose

À la racine du projet :

```bash
docker compose up -d --build
```

Le service écoute **à l'intérieur du conteneur sur le port 8501**. Le fichier `compose.yaml` publie par défaut ce port seulement sur `127.0.0.1:8501` du VPS, pour ne pas rendre l'application publique sans contrôle. Il faut faire passer le trafic externe par un reverse proxy HTTPS avec authentification. Pour un essai local sur le VPS :

```bash
curl http://127.0.0.1:8501/_stcore/health
```

Consulter les logs :

```bash
docker compose logs -f afc-factominer
```

Arrêter :

```bash
docker compose down
```

**Coolify :** déposer ce projet dans un dépôt Git, créer une application de type **Dockerfile**, choisir la racine du projet, et utiliser **8501** comme port interne de destination. Configurer le domaine et HTTPS dans Coolify. Ne pas ouvrir le service sans contrôle d'accès. Ne pas utiliser simultanément un second service avec le même port local 8501 dans le fichier Compose ; modifier la liaison hôte si nécessaire.

Le `Dockerfile` installe automatiquement Python, R et le paquet Debian `r-cran-factominer` ; aucune configuration manuelle de R n'est nécessaire pour l'exécution dans Docker.

## Exécution hors Docker

Installer **R**, le paquet R **FactoMineR** et les dépendances Python :

```bash
Rscript -e "install.packages('FactoMineR', repos='https://cloud.r-project.org')"
python -m pip install -r requirements.txt
streamlit run application.py
```

L'environnement local doit comporter `Rscript` accessible dans le `PATH`.

## Confidentialité et ressources

Le CSV est transmis au processus Streamlit, donc au serveur où tourne l'application. Les données sont conservées en mémoire de session et le calcul R utilise un répertoire temporaire supprimé après la production des résultats. Aucun stockage PostgreSQL ni envoi automatique vers un service tiers n'est configuré. Les archives produites restent disponibles dans la session utilisateur jusqu'à fermeture ou invalidation. **Il faut cependant sécuriser l'accès à l'application au niveau du VPS / reverse proxy.**

Le téléversement est limité à 100 Mo par `.streamlit/config.toml` et les ressources à 3 Go de mémoire et 2 CPU dans `compose.yaml`. Adapter ces limites à la capacité du VPS et au volume du corpus. `AFC_TIMEOUT_SECONDS` contrôle le délai maximal d'un calcul R (180 secondes par défaut). Un nombre de publications important n'implique pas un tableau de contingence important si les variables comportent peu de modalités.

## Précautions scientifiques

La procédure porte sur un croisement de **deux variables qualitatives**. Ne pas introduire directement des identifiants, du texte libre ou des mesures numériques continues. Recoder si nécessaire les mesures en classes, avec des bornes explicites. Les effectifs faibles fragilisent l'interprétation ; la méthode Monte-Carlo estime une valeur p quand au moins une cellule a un effectif théorique inférieur à cinq. Un plan ne représente qu'un seul axe si l'une des variables possède seulement deux modalités.

L'AFC décrit des associations ; elle ne démontre pas de causalité. Les classes de vues et le taux d'engagement partagé par les vues comportent un risque de relation mathématique mécanique. Les hypothèses relatives à la violence nécessitent une variable de codage correspondante dans le corpus.

## Vérifier la préparation CSV

```bash
python -m unittest discover -s tests -v
```

Ces tests portent sur l'importation et la préparation Python. L'exécution du moteur R dépend de l'installation effective de FactoMineR et du déploiement Docker.
