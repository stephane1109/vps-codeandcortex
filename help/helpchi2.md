## Aide : interprétation du chi2 et de `Classe_max`

Le code calcule un chi2 global par terme sur l’ensemble des classes :

\[
\chi_j^2 = \sum \frac{(O - E)^2}{E}
\]

puis une p-value.

En plus, il calcule les résidus standardisés cellule par cellule :

\[
\frac{O - E}{E}
\]

- `Classe_max` = la classe où ce résidu est le plus grand pour le terme considéré (`which.max`).
- C’est la classe de surreprésentation la plus forte pour aider la lecture des résultats.
- Les classes elles-mêmes viennent du regroupement (`dfm_group`) et sont renommées « Classe X » pour affichage.
- L’interface confirme : couleur des mots selon la classe de plus forte surreprésentation (résidus), taille selon fréquence ou chi2.

## En une phrase

- `chi2` = « est-ce que la distribution du terme varie globalement selon les classes ? »
- `Classe_max` = « si oui, dans quelle classe l’excès est le plus marqué ? »
