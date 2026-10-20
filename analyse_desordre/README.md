# Analyse autonome du désordre visuel

Ce module est **facultatif**. Il lit uniquement des MP4 locaux et les engagements
collectés par ScrapTikTok. Il n'importe aucun moteur de collecte, ORB, pHash,
DINOv2 ou comparaison vidéo. L’onglet **Désordre visuel** le lance uniquement après activation explicite et clic sur le bouton de lancement.
Aucun accès réseau, GPU ou téléchargement de poids n'est nécessaire.

## Arborescence

```text
analyse_desordre/
├── __init__.py                 # Fonction publique différée
├── parametres.py               # Réglages reproductibles
├── extraction_images.py        # Images et horodatages
├── mouvement_camera.py         # Farnebäck, compensation, coupures, instabilité
├── mouvements.py               # Entropie et amplitude résiduelles
├── irregularite_temporelle.py  # Variations entre mesures consécutives
├── indice.py                   # Indice exploratoire et agrégation
├── engagement.py               # Métadonnées et taux pour 1 000 vues
├── statistiques.py             # Spearman, permutations, correction BH
├── graphiques.py               # Nuages de points PNG
├── lancement.py                # CLI et orchestration autonome
├── requirements.txt
└── tests/test_analyse.py
```

## Installation et exécution

Depuis le dossier `applications/scraptiktok`, dans un environnement Python 3.11 :

```bash
python -m pip install -r analyse_desordre/requirements.txt
python analyse_desordre/lancement.py \
  --videos /donnees/collecte/videos \
  --metadonnees /donnees/collecte/publications.json \
  --sortie /donnees/analyse_desordre_001
```

Les chemins `/donnees` sont des exemples à adapter. `--metadonnees` accepte aussi
`engagement.csv` de ScrapTikTok. Les identifiants restent des chaînes, même pour
les très grands identifiants TikTok. Le JSON attendu est une liste de publications
avec `id`, `url` et `engagement.<compteur>.valeur`. Le CSV utilise `publication_id`
ou `id`, `url`, `vues`, `likes`, `commentaires`, `partages`.

Les fichiers vidéo doivent s'appeler `<identifiant>.mp4` ou `id_<identifiant>.mp4`.
Les sous-dossiers sont parcourus. Deux fichiers de même identifiant sont signalés,
jamais choisis arbitrairement. Les vidéos absentes, illisibles, sans métadonnées
ou sans mesures utilisables sont explicitement recensées.

Le dossier de sortie doit être nouveau : aucun fichier existant n'est écrasé.
Les sources ne sont ni modifiées ni supprimées. Une erreur de lecture d'une vidéo
n'interrompt pas les autres. Les erreurs de programmation ne sont pas masquées.

Réglages CLI : `--frequence 10`, `--dimension 320`, `--duree-max 600`,
`--permutations 1999`. Une limite atteinte produit un résultat **partiel**.
Les paramètres avancés sont disponibles dans `Parametres` pour les appels Python.
Farnebäck doit comparer des images assez proches : 10 Hz est un compromis initial,
et non la fréquence de 1 image/s du moteur de similarité. Un mouvement très rapide
peut dépasser sa capacité de mesure. Toutes les vidéos doivent être analysées
avec les mêmes réglages pour être comparables.

## Mesures et unités

1. **Extraction** : lecture séquentielle, image réduite à 320 pixels au plus,
   horodatage OpenCV en secondes. Si les timestamps ne progressent pas, ils sont
   reconstitués depuis les FPS et ce recours est signalé. Les vidéos à fréquence
   variable peuvent alors nécessiter un contrôle supplémentaire. Une fin de
   lecture anticipée par rapport au nombre de frames annoncé est signalée.
2. **Caméra** : flux dense Farnebäck, puis similitude RANSAC (translation,
   rotation, zoom) sur une grille de pixels texturés. Le flux global estimé est
   soustrait au flux dense. Les bords sortis de l'image sont ignorés. Une estimation
   soutenue par moins de 50 % des points est exclue, sans supposer une caméra fixe.
   Sur une image uniforme, la compensation reste indisponible.
3. **Changements de plans** : distance d'histogramme > 0,65 ou erreur photométrique
   après alignement > 0,22. Pour les plans à histogrammes proches : erreur > 0,06
   et corrélation des pixels alignés < 0,2. Ces règles sont heuristiques ; flashes,
   fondus et mouvements extrêmes peuvent être mal classés. La transition exclue
   reste dans le CSV. Aucune accélération ou irrégularité ne traverse une exclusion.
4. **Instabilité caméra** : norme moyenne de la différence des vitesses globales
   aux quatre coins, divisée par l'intervalle entre centres temporels des mesures.
   Unité : diagonales d'image/s². Une translation régulière doit rester proche
   de zéro ; l'instabilité est une accélération, pas une simple vitesse de caméra.
5. **Mouvements résiduels** : vitesse moyenne des pixels texturés valides, en
   diagonales/s. Les déplacements inférieurs à 0,3 pixel entre deux images sont
   mis à zéro pour limiter le bruit ; la fraction mobile est exportée.
6. **Entropie directionnelle** : histogramme de 12 directions, pondéré par les
   amplitudes résiduelles, Shannon divisée par `log(12)`. Entre 0 et 1 : zéro pour
   un mouvement unidirectionnel ou absent, un pour des directions équilibrées.
7. **Irrégularité temporelle** : `abs(v_t - v_précédente) /
   (abs(v_t) + abs(v_précédente) + 1e-12)`, entre 0 et 1. C'est une mesure de variation
   relative de l'amplitude, pas une mesure de complexité du montage.
8. **Indice de désordre visuel**, entre 0 et 100, pour chaque intervalle complet :

   ```text
   caméra = instabilité / (instabilité + 0,05)
   directions = entropie × vitesse résiduelle / (vitesse résiduelle + 0,01)
   indice = 100 × (caméra + directions + irrégularité) / 3
   ```

   Les trois poids sont égaux. Les échelles fixes 0,05 et 0,01 sont des choix
   exploratoires documentés, **pas des constantes validées scientifiquement**.
   Elles ne dépendent ni du corpus ni des engagements. Les premiers intervalles
   de chaque plan n'ont pas encore d'accélération/irrégularité et leur indice est
   absent. Les moyennes vidéo sont pondérées par la durée réellement mesurée.
   Chaque indicateur possède sa durée contributive ; la couverture est exportée.

La compensation estime le **mouvement dominant**, pas le mouvement physique
certain de la caméra : grande foule au premier plan, parallaxe, texte incrusté,
flou, compression, faible texture et mouvement non rigide sont des limites.
Une faible couverture rend la moyenne moins représentative. Aucun filtre de
couverture n'est appliqué silencieusement aux corrélations.

## Engagements et statistiques

`likes_pour_1000_vues = 1000 × likes / vues`, de même pour commentaires et partages.
Compteurs manquants, négatifs, non finis, abrégés non normalisés et vues nulles :
taux absent, jamais remplacé par zéro. Un zéro observé avec des vues positives
reste zéro. Les compteurs source sont exportés avec les taux.

Spearman est calculé entre chacun des cinq indicateurs et les sept variables d’engagement (likes, commentaires, partages, vues et trois taux), au
niveau **publication**, jamais en traitant les images comme observations
indépendantes. Ex aequo : rangs moyens. Valeurs absentes : exclusion paire par
paire. Moins de trois publications ou variable constante : résultat indisponible.
Test bilatéral exact jusqu'à sept publications, sinon permutations Monte-Carlo
(graine fixée, correction +1). Les 35 tests disponibles sont aussi corrigés par
Benjamini–Hochberg ; `p_ajustee_bh` accompagne les p brutes.

Il s'agit d'associations exploratoires, non causales : compte, audience, date,
ancienneté, sujets et durée sont des facteurs de confusion. Les publications d'un
même compte ou les copies ne sont pas indépendantes. Le test de permutation
simple ne modélise pas ces regroupements. Des compteurs arrondis et des collectes
à des dates différentes peuvent également biaiser l'interprétation.

## Résultats

- `parametres.json` : réglages du calcul.
- `environnement.json` : versions Python et bibliothèques.
- `indicateurs_engagement.csv` : une ligne par publication, URL, mesures,
  compteurs, taux, couverture, statut et erreurs.
- `mesures_temporelles.csv` : intervalles en secondes, plans, exclusions et mesures.
- `correlations_spearman.csv` : rho, n, p, p ajustée, méthode et nombre de permutations.
- Cinq PNG : chacun confronte un indicateur aux trois engagements, avec n, rho et p.

Les CSV sont UTF-8 avec BOM. Les cellules vides signifient « non mesuré ».

## Onglet Désordre visuel et appel Python

```python
# À exécuter seulement dans la branche d'activation explicite de cette option.
from analyse_desordre import analyser_lot
from analyse_desordre.parametres import Parametres

resultat = analyser_lot(
    videos=dossier_session / 'videos',
    metadonnees=dossier_session / 'publications.json',
    sortie=dossier_session / 'analyse_desordre_001',
    parametres=Parametres(),
    progression=lambda rang, total, identifiant, statut: print(rang, total, statut),
)
```

Dans l’onglet **Désordre visuel**, cocher l’activation puis lancer le calcul.
L’interface présente le nombre de MP4 locaux, une progression, un bouton d’arrêt,
les mesures par vidéo, un graphique interactif et les exports CSV. Le menu
« Variable à croiser » propose le nombre de likes par défaut, mais aussi les
commentaires, partages, vues et les trois taux pour 1 000 vues. Le changement de
variable réutilise les mesures sans réanalyser les vidéos. Le tableau de Spearman
indique rho, n, p et p ajustée pour chaque couple disponible. Les PNG autonomes
restent consacrés aux trois taux ; le graphique interactif couvre les sept variables.

L'import du paquet seul ne charge ni OpenCV ni modèle. L'appel Python est synchrone ;
l’interface utilise `service.py` dans un processus séparé, réservé au propriétaire
de la collecte. Les exports et l’état sont privés. La réservation CPU empêche un
calcul simultané avec la collecte ou l’analyse multimodale. Arrêt explicite,
libération d’accès et limite de deux heures interrompent le processus. Chaque
lancement écrit dans un nouveau sous-dossier ; les MP4 ne sont jamais supprimés.

Le Dockerfile installe les dépendances du module avec les profils
`INSTALL_VIDEO=base`, `semantique` ou `1`. Un redéploiement est nécessaire après
cette intégration. Le profil `0` reste limité aux textes. L’analyse ne démarre
jamais automatiquement. Calcul CPU séquentiel, OpenCV limité à un thread ; seules
les mesures scalaires d'une vidéo et le tableau des publications sont conservés.

## Validation

```bash
python -m unittest discover -s analyse_desordre/tests -v
```

Les tests couvrent translations compensées, scène fixe, secousses, objet mobile,
entropie connue, coupures à histogrammes proches, réinitialisation temporelle,
absence de texture, taux manquants/nuls, identifiants exacts, Spearman avec ex aequo,
MP4 corrompu et exports sans modification des sources.

Références : [Farnebäck dans OpenCV](https://docs.opencv.org/4.7.0/dc/d6b/group__video__track.html)
et [Spearman et précautions sur les p-values, SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html).
