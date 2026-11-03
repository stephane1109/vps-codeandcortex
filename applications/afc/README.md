# Application web AFC et ACM (TDC et Burt) — FactoMineR

Cette application Streamlit importe un ou plusieurs fichiers CSV de même structure, les concatène si nécessaire, puis calcule une **analyse factorielle des correspondances (AFC)** avec `FactoMineR::CA()` ou une **analyse des correspondances multiples (ACM)** avec `FactoMineR::MCA()`. Les données peuvent provenir de ScrapTikTok ou de tout autre tableau où une observation est représentée par une ligne.

## Onglet "Statistique descriptive"

L'interface propose un onglet indépendant **Statistique descriptive**, accessible dès l'importation du CSV, sans exécuter de calcul R. L'onglet **AFC / ACM** conserve les analyses factorielles existantes, les méthodes TDC et Burt, les exclusions interactives de modalités et le filtre de significativité des plans.

La navigation descriptive repose sur deux menus déroulants : **"Variable à analyser"** et **"Test / analyse descriptive"**. Le deuxième menu s'adapte au type de variable. Pour une métrique numérique, il propose résumé statistique, histogramme, boîte à moustaches, comparaison par catégorie, nuage de points et évolution temporelle selon les données disponibles. Pour une variable catégorielle, il propose les effectifs, les pourcentages et la comparaison de l'engagement entre modalités. L'entrée **"Ensemble des métriques"** donne accès aux volumes cumulés d'interactions et aux données manquantes. Sous les menus apparaît **un seul tableau et un seul graphique**, mis à jour lors de chaque sélection ; les réglages complémentaires ne sont présentés que lorsqu'ils sont utiles à l'analyse choisie. Les filtres et les exports sont conservés dans des sections repliables.

L'onglet descriptif travaille sur un **échantillon explicite** : publications retenues (si `retenue` figure dans le CSV), dédoublonnage facultatif par `publication_id` et filtrage optionnel sur les variables catégorielles présentes. Les réglages sont indépendants de ceux de l'AFC et de l'ACM, sans modification du fichier original.

Les indicateurs reconnus comprennent les vues, likes, commentaires, partages, favoris, abonnés et taux d'engagement, ainsi que leurs appellations usuelles d'API. Les valeurs manquantes restent distinctes de zéro. Pour chaque mesure, le tableau présente l'effectif valide, le nombre de valeurs absentes, la proportion d'absences, les zéros, la somme, la moyenne, la médiane, l'écart-type, les quartiles, les percentiles 90 et 95 ainsi que les valeurs extrêmes. Si le taux d'engagement est absent ou partiellement manquant, il est calculé exclusivement lorsque les quatre composantes d'interaction et un nombre de vues strictement positif sont disponibles : **(likes + commentaires + partages + favoris) / vues × 100**. Les valeurs préexistantes du CSV sont conservées.

Les graphiques comprennent les volumes d'interactions, les données absentes, les histogrammes individuels à nombre de classes paramétrable, la représentation logarithmique facultative `log(1 + x)`, les répartitions des classes d'engagement, les médianes par type de média ou autres catégories disponibles, un nuage vues–interactions et des séries temporelles (volume quotidien et médiane). La date de collecte est explicitement distinguée d'une date de publication. Le nuage est limité à un sous-échantillon reproductible de 5 000 points lorsque le corpus est très volumineux ; tous les autres résultats descriptifs portent sur les observations filtrées.

Les tableaux `statistiques_descriptives_engagement.csv`, `mesures_engagement_normalisees.csv` et `echantillon_descriptif_filtre.csv` sont téléchargeables. Les graphiques et comparaisons sont descriptifs : ils ne démontrent ni significativité, ni causalité. Les filtres et les variables quantitatives utilisées dans ces graphiques ne changent pas les calculs des onglets AFC et ACM.

## Deux méthodes complémentaires : AFC et ACM

L'interface propose **AFC** et **ACM**, avec deux formulations pour l'ACM : **tableau disjonctif complet (TDC)** et **tableau de Burt**. L'AFC conserve le croisement de deux variables catégorielles et son tableau de contingence, avec suppression interactive des lignes et colonnes. Elle utilise exclusivement `FactoMineR::CA()` et `FactoMineR::descfreq()`.

L'ACM permet de sélectionner **au moins trois variables catégorielles** simultanément, par exemple les classes de vues, les classes de likes, les types de médias et des modalités d'annotation. Dans la même interface, l'utilisateur choisit **FactoMineR::MCA(method="Indicator")** pour le tableau disjonctif complet ou **FactoMineR::MCA(method="Burt")** pour le tableau de Burt. Le choix de la méthode relance le calcul sans supprimer les modalités précédemment exclues. L'application conserve les filtres, le choix des valeurs manquantes, le dédoublonnage, la limite de cardinalité et une exclusion interactive des modalités de chaque variable. Son moteur statistique est `FactoMineR::MCA()`. Pour le filtre à p ≤ 0,05, les p-values sont lues directement dans `FactoMineR::dimdesc()`. L'appel `proba = 1` fournit les résultats natifs des modalités pour le diagnostic complet ; `proba = 0.05` fournit la description des axes au seuil dans le rapport. Aucun recalcul de p-values à partir des valeurs-tests n'est effectué. Les observations associées aux modalités exclues sont retirées avant le calcul, sans modifier le CSV original.

Sur les plans factoriels de l'ACM, **chaque variable active possède une couleur distincte**, utilisée pour les points et les libellés de toutes ses modalités. La palette est déterministe : les mêmes variables gardent les mêmes couleurs entre le tableau disjonctif (TDC), le tableau de Burt, le plan complet et le plan filtré à p ≤ 0,05. Une légende réservée à droite du graphique évite de recouvrir les points et identifie les variables. Les graphiques PNG et PDF sont agrandis afin d'accueillir cette légende. Le fichier `19_couleurs_variables.csv` contient pour chaque variable son code couleur hexadécimal et son nombre de modalités. Cette modification concerne uniquement la visualisation, sans modification des coordonnées ni des inerties produites par FactoMineR.

Dans les deux méthodes, le plan factoriel **complet est affiché par défaut**. La case **"Afficher uniquement les modalités significatives (p ≤ 0,05)"** active ou désactive un filtre d'affichage sans recalcul des coordonnées ou des inerties. Les deux versions du plan sont produites au format PNG et PDF et incluses dans l'archive ZIP. En AFC, le critère de `descfreq()` décrit des associations entre modalités des deux variables ; en ACM, le filtre utilise directement les p-values de `FactoMineR::dimdesc()` pour caractériser les modalités des axes 1 et 2. Les critères diffèrent et ne doivent pas être assimilés. Ces p-values ACM sont exploratoires et non corrigées pour comparaisons multiples.

Chaque méthode possède ses propres exports de coordonnées, contributions, cos² et inerties en pourcentage et pourcentage cumulé. L'ACM exporte également les coordonnées des individus et la description significative des modalités pour les axes représentés. Elle produit le fichier `18_comparaison_inerties_tdc_burt.csv` présentant les deux conventions de valeurs propres et d'inerties, ainsi que `tdc.csv` et `burt.csv` lorsque leurs tailles respectives ne dépassent pas 2 millions et 1 million de cellules. Ces seuils concernent seulement les exports des matrices, pas le calcul ACM. Les tests sont limités aux fonctions natives de FactoMineR.

## Fonctionnement

Importer un ou plusieurs CSV de même structure (détection des séparateurs `;`, `,`, tabulation ou `|`, avec choix manuel possible). Chaque fichier est lu séparément et les noms de colonnes sont comparés à ceux du premier fichier. L'ordre peut différer : les colonnes sont réalignées par leur nom avant concaténation. Si un fichier présente une colonne manquante ou supplémentaire, le traitement s'interrompt et affiche le fichier et les colonnes en cause. Toutes les observations sont conservées, y compris les doublons éventuels ; le dédoublonnage reste une option au stade de l'analyse. Un tableau donne le nombre de lignes et la taille de chaque fichier. Le corpus fusionné peut être téléchargé en CSV. Après importation, choisir une variable en lignes et une variable en colonnes. Les classes catégorielles de ScrapTikTok sont déjà prises en charge, notamment `vues_classe`, `likes_classe`, `commentaires_classe`, `partages_classe`, `favoris_classe`, `classe_taux_engagement`, `classe_abonnes`, `is_verified`, `region_code`, `type_media`.

L'analyse s'effectue exclusivement à partir d'un ou plusieurs fichiers CSV ou TXT importés par l'utilisateur. Aucun corpus de démonstration ni générateur de données fictives n'est proposé dans l'interface.

Le panneau de paramétrage permet de conserver uniquement les lignes `retenue`, de supprimer les doublons selon `publication_id`, d'exclure les modalités indéterminées, de traiter les cellules vides comme une modalité ou de les exclure, de filtrer sur une troisième variable, de limiter la cardinalité.

## Suppression interactive de modalités et recalcul

Le tableau de contingence de l'étape 4 propose deux sélecteurs : **"Supprimer des lignes (modalités)"** et **"Supprimer des colonnes (modalités)"**. Il est ainsi possible de retirer une valeur comme `modalité_nontrouvé` d'une variable, sans supprimer le champ d'origine du CSV ni modifier le fichier importé. La commande **"Rétablir toutes les lignes et colonnes"** annule ces exclusions.

À chaque modification de ces sélecteurs, l'application reconstruit le tableau des effectifs et **relance automatiquement `FactoMineR::CA()` et `FactoMineR::descfreq()`** ; le plan factoriel, les inerties, les associations significatives et les exports sont mis à jour. Le bouton de lancement manuel reste disponible pour la première AFC ou une autre modification des paramètres. Les exclusions sont conservées pendant l'analyse du même tableau, puis réinitialisées lors du changement de CSV, de variables ou de filtres.

L'analyse ne peut être calculée qu'avec au moins deux modalités actives en lignes et en colonnes. Si la suppression d'une modalité crée une ligne ou une colonne sans effectif, cette dernière est également retirée et signalée dans l'interface. Le nombre d'observations avant et après suppression figure dans l'interface et dans `17_parametres_analyse.json`. Le tableau exporté `01_tableau_contingence.csv` correspond aux effectifs effectivement soumis à FactoMineR.

La table de contingence s'affiche **avant** le lancement. La préparation contrôle le nombre de modalités de chaque variable ; FactoMineR contrôle l'inertie du tableau. L'application affiche le plan factoriel, l'histogramme des inerties et le tableau des valeurs propres, inerties en pourcentage et pourcentages cumulés, les profils, coordonnées, contributions et cos² fournis par FactoMineR. Pour les AFC comportant plusieurs axes, le rapport utilise le résumé natif de `FactoMineR::summary.CA()`, avec le Chi-deux et sa p-value tels qu'affichés par cette fonction. Pour une AFC ne comportant qu'un seul axe (tableau à deux lignes ou deux colonnes), `summary.CA()` peut échouer en raison de la mise en forme des valeurs propres ; le rapport reprend alors directement les matrices de `FactoMineR::CA()`, sans recalcul statistique. Le moteur dispose également d'un repli sur ces matrices si le résumé standard échoue pour une autre raison. Les résultats sont téléchargeables en ZIP et les tableaux séparément en CSV. Aucun V de Cramér, effectif théorique, résidu de Pearson ou test supplémentaire n'est calculé par le script.

Sur le **plan à deux dimensions**, toutes les modalités sont affichées par défaut. La case **"Afficher uniquement les modalités significatives (p ≤ 0,05)"** permet de masquer les modalités sans association significative, sans recalculer l'AFC. L'identification des associations repose exclusivement sur `FactoMineR::descfreq()`, qui effectue le test hypergéométrique natif de FactoMineR sur les lignes, puis sur les colonnes du tableau de contingence. Aucune correction Benjamini-Hochberg, aucun test du Chi-deux par modalité ni autre méthode ajoutée ne participe à ce filtre. Le fichier `significativite_modalites_factominer.csv` conserve toutes les modalités, la p-value minimale parmi leurs associations significatives, les modalités correspondantes et la décision d'affichage. Les calculs factoriels, coordonnées, contributions, cos² et autres exports restent établis sur **le tableau complet**, y compris pour les modalités masquées. Le graphique à un seul axe reste inchangé.

La p-value de `descfreq()` caractérise une **association entre modalités du tableau**, et non la significativité d'une coordonnée sur l'un des axes. La sélection est donc descriptive et exploratoire. L'application n'effectue aucun test statistique supplémentaire : le résumé natif de FactoMineR reste accessible dans le rapport méthodologique.

## Comparaison de l'ACM sur TDC et sur Burt

Les deux formulations sont disponibles dans **ACM → Formulation de l'ACM**. Le tableau disjonctif complet code les observations en modalités (0/1). Le tableau de Burt est le produit croisé de ce codage, soit `B = t(TDC) %*% TDC`. La méthode de calcul du moteur est toujours native à FactoMineR, ce qui préserve les fonctionnalités d'analyse et les exports.

Les valeurs propres du tableau de Burt sont les carrés des valeurs propres du TDC. Par conséquent, une valeur propre de 0,45 dans la méthode TDC correspond à 0,2025 dans la méthode Burt, et les **pourcentages d'inertie sont normalisés différemment** : un pourcentage d'un mode ne peut pas être lu comme le même pourcentage dans l'autre mode. Le tableau comparatif des inerties est affiché dans l'onglet **Inerties** ; les analyses sont conservées séparément selon la formulation choisie. Pour comparer les coordonnées, tenir compte de la différence d'échelle et de la possibilité d'une inversion de signe des axes.

Les plans complet et filtré restent disponibles en PNG et PDF. Le filtre à p ≤ 0,05 utilise les p-values natives de `FactoMineR::dimdesc()` et conserve un statut exploratoire, quel que soit le mode de calcul. La correspondance entre les résultats de `dimdesc()` et les coordonnées est établie par les identifiants uniques `variable=modalité`, en tenant compte des libellés différents de `tab.disjonctif()`. Le rapport inclut la description `dimdesc()` des axes au seuil de 0,05. Les valeurs-tests `FactoMineR::MCA()$var$v.test` sont conservées pour information, mais ne sont pas converties en p-values dans l'application. Les exports `significativite_modalites_factominer.csv` et `20_diagnostic_filtre_pvalue.csv` fournissent, pour toutes les modalités, les p-values par axe, la décision d'affichage, les effectifs valides et la p-value minimale. L'interface affiche ces vérifications sous le graphique, avec un tableau dépliable et un avertissement explicite si aucune modalité n'atteint le seuil. Un test de régression sur un corpus corrélé de 900 observations a été ajouté ; les tests d'intégration nécessitent un environnement R avec FactoMineR.

## Compatibilité graphique de l'ACM sous Docker

Le moteur ACM produit des titres courts dans les graphiques : la méthode (TDC ou Burt) et le nombre de variables actives sont affichés, tandis que la liste intégrale des variables reste conservée dans le rapport méthodologique et les fichiers CSV. Les libellés accentués sont translittérés uniquement lors du dessin des graphiques afin de prévenir les avertissements `mbcsToSbcs` dans les environnements R sans locale graphique Unicode complète. Les noms des variables et des modalités sont conservés sans modification dans les résultats exportés.

Le Dockerfile définit `LANG=C.UTF-8` et `LC_ALL=C.UTF-8`. **Reconstruire l'image dans Coolify** est nécessaire pour appliquer la nouvelle configuration. Si un calcul R échoue encore, l'interface met désormais en avant le message `Error in ...` plutôt que de tronquer le diagnostic sur les avertissements graphiques initiaux. Les tests incluent un scénario ACM de Burt à 11 variables sous `LC_ALL=C`.

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

L'AFC porte sur un croisement de **deux variables qualitatives** ; l'ACM analyse **au moins trois variables qualitatives**. Ne pas introduire directement des identifiants, du texte libre ou des mesures numériques continues. Recoder si nécessaire les mesures en classes, avec des bornes explicites. Les faibles effectifs fragilisent l'interprétation ; ils ne déclenchent aucun test additionnel dans l'application. Un plan ne représente qu'un seul axe si l'une des variables possède seulement deux modalités.

L'AFC décrit des associations ; elle ne démontre pas de causalité. Les classes de vues et le taux d'engagement partagé par les vues comportent un risque de relation mathématique mécanique. Les hypothèses relatives à la violence nécessitent une variable de codage correspondante dans le corpus.

## Vérifier la préparation CSV

```bash
python -m unittest discover -s tests -v
```

Les tests vérifient l'importation et la préparation Python, ainsi que l'absence de calculs statistiques additionnels. Les tests d'intégration du moteur R s'exécutent lorsque R et FactoMineR sont installés ; le déploiement Docker fournit ces dépendances.
