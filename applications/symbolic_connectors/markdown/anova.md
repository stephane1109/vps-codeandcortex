# Test d’ANOVA : déroulement dans le script

Ce document décrit comment le test d’ANOVA à un facteur et les comparaisons post‑hoc sont réalisés dans le code.

## 1) Préparation des données

Le flux commence dans l’onglet ANOVA de l’application Streamlit :

- L’utilisateur choisit une variable de regroupement (par ex. modèle/LLM) via un menu déroulant.
- La densité de connecteurs est calculée **par réponse individuelle** (normalisée par 1 000 mots par défaut).
- Seules les réponses avec un nombre de mots strictement supérieur à 0 sont conservées.

Ces étapes sont gérées dans `onglets/onglet_anova.py`.

## 2) Calcul de la densité par réponse

La fonction `compute_density_per_response` construit le texte de chaque ligne (en concaténant `entete` et `texte` si nécessaire), puis calcule :

- le nombre de mots,
- le nombre de connecteurs,
- la densité des connecteurs (pour 1 000 mots par défaut).

Elle renvoie un DataFrame enrichi avec ces indicateurs.

> **Note** : le test ANOVA ne se base pas sur la Longueur Moyenne des Segments (LMS). Il compare uniquement les densités de connecteurs calculées par réponse, puis regroupées par modalité.

## 3) Constitution des groupes

Une fois les densités calculées, les réponses sont groupées par modalité de la variable choisie (ex. `grok`, `gpt`, etc.).
Pour chaque modalité, on récupère la liste des densités associées.

Cette structure est un dictionnaire de type :

```python
{
  "modalite_1": [densite_1, densite_2, ...],
  "modalite_2": [densite_1, densite_2, ...],
  ...
}
```

## 4) ANOVA à un facteur

Le test ANOVA est appliqué via `scipy.stats.f_oneway` dans la fonction `effectuer_test_anova` :

- Les valeurs `None` ou `NaN` sont retirées.
- Si moins de **deux** modalités ont des données valides, le test est abandonné.
- Le résultat renvoie : statistique F, p‑value, degrés de liberté inter/intra, effectif total, nombre de groupes.

Ces informations sont ensuite affichées dans l’interface Streamlit.

## 5) Comparaisons post‑hoc (t‑tests)

Après l’ANOVA, des comparaisons par paires sont effectuées entre toutes les modalités via `tests_post_hoc_ttest` :

- Chaque paire est comparée avec `scipy.stats.ttest_ind`.
- Par défaut, **Welch** est utilisé (`equal_var=False`), mais l’utilisateur peut cocher l’option “variances égales”.
- Une correction de p‑values peut être appliquée (`Bonferroni` ou `Holm`) via `statsmodels.stats.multitest.multipletests`.
- Les résultats sont triés par p‑value ajustée et affichés sous forme de tableau.

## 6) Résultat affiché

L’interface affiche :

- La ligne de synthèse de l’ANOVA (F, p‑value, ddl, effectif, nombre de groupes).
- Un tableau des t‑tests post‑hoc (modalités comparées, t, p brute, p ajustée, tailles d’échantillon).

---

## Résumé du flux

1. Choix de la variable de comparaison.
2. Calcul des densités de connecteurs par réponse.
3. Regroupement des densités par modalité.
4. ANOVA à un facteur (test global).
5. Comparaisons post‑hoc par t‑tests (avec correction optionnelle).
6. Affichage des résultats dans l’interface.

---

## Fichiers impliqués

- `anova.py` (calculs ANOVA + post‑hoc)
- `onglets/onglet_anova.py` (interface et orchestration)
- `densite.py` (calculs de densité et comptages)
