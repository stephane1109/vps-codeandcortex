
# Calcul de la LMS (Longueur Moyenne des Segments) dans l'onglet Hash

Cette note décrit la façon dont la LMS est calculée dans l'onglet **Hash**, depuis le découpage des segments jusqu'à l'agrégation finale.

## 1. Découpage des segments

1. **Nettoyage préalable** : les lignes de métadonnées commençant par quatre astérisques (`****`) sont supprimées.
2. **Détection des connecteurs** :
   - Les connecteurs disponibles proviennent du dictionnaire sélectionné dans l'onglet Connecteurs.
   - Un motif regex est construit pour reconnaître chaque connecteur (y compris ceux composés uniquement de ponctuation ou d'espaces, comme le retour à la ligne `\n`).
3. **Bornes de segment** :
   - Mode `connecteurs` : seuls les connecteurs servent de bornes.
   - Mode `connecteurs_et_ponctuation` : on ajoute la ponctuation forte (`.`, `!`, `?`, `;`, `:`) comme bornes supplémentaires.
4. **Extraction** : le texte est parcouru pour conserver uniquement les segments qui sont bornés par au moins un connecteur (précédent ou suivant). Les segments vides ou purement blancs sont ignorés.

## 2. Comptage des mots par segment

Chaque segment retenu est tokenisé puis compté en nombre de mots :
- **Mode `regex`** : correspond aux occurrences `\b\w+\b` (caractères alphanumériques entre bornes de mots).
- **Mode `spacy`** : utilise le tokenizer `fr_core_news_md` en excluant les composants coûteux, en ignorant espaces et ponctuation.

Seuls les segments contenant au moins un token sont conservés. Pour chaque segment, on retient sa longueur en mots.

## 3. Calcul de la LMS

Pour un texte (une réponse ou l'ensemble d'une modalité), la LMS est la moyenne arithmétique des longueurs des segments non vides :

```
LMS = somme(longueurs_des_segments) / nombre_de_segments
```

## 4. Agrégation par modalité : moyenne « par segment »

Dans l'onglet **Hash**, les statistiques affichées par modalité suivent la règle « moyenne par segment » :

- On concatène toutes les réponses de la modalité.
- On applique les étapes 1 à 3 pour obtenir toutes les longueurs de segments de la modalité.
- La LMS affichée pour la modalité est la moyenne arithmétique de **tous** ces segments (chaque segment pèse autant), et le nombre de segments est le dénombré de ces segments.

Cette pondération par segment garantit que les réponses riches en segments influencent proportionnellement la LMS de leur modalité.

## 5. Indicateurs visibles sur le graphique « Distribution de l'indicateur par modalité »

Dans la section « Inférence au niveau réponse », le graphique de distribution affiche un **boxplot par modalité** pour l'indicateur sélectionné dans la liste déroulante. Les valeurs tracées correspondent à **une valeur par réponse**, calculée avec les mêmes réglages de segmentation/tokenisation et le seuil de « segment court » choisi.

Indicateurs proposés :

- **LMS (moyenne des segments)** : moyenne des longueurs de segments d'une réponse.
- **Écart-type des segments** : dispersion des longueurs de segments de la réponse.
- **Coefficient de variation** : écart-type divisé par la moyenne des segments de la réponse.
- **Médiane des segments** : médiane des longueurs de segments de la réponse.
- **Proportion de segments courts** : part des segments dont la longueur est ≤ au seuil défini.

Chaque point du boxplot représente une réponse individuelle ; la boîte et les moustaches résument la distribution des valeurs de l'indicateur pour toutes les réponses de la modalité.
