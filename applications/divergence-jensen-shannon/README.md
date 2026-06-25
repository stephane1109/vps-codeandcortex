# Divergence Jensen-Shannon - version VPS

Application Streamlit pour :

- comparer deux textes
- calculer la divergence de Jensen-Shannon entre leurs distributions lexicales
- classer les mots qui expliquent le plus l'ecart entre les deux corpus
- afficher un graphique oriente gauche/droite entre texte A et texte B
- telecharger les resultats au format TXT, CSV et PNG

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- interface Streamlit exploitable depuis un navigateur
- conteneur Docker autonome
- compatibilite Coolify via `PORT` et `STREAMLIT_SERVER_BASE_URL_PATH`
- telechargement des stopwords NLTK au build du conteneur
- rendu Matplotlib compatible environnement headless
- aucun stockage persistant requis

## Lancer localement avec Docker

```bash
docker build -t divergence-jensen-shannon .
docker run --rm -p 8501:8501 divergence-jensen-shannon
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin

## Notes

- Le score global JSD augmente avec la divergence lexicale entre les deux textes.
- Les barres a gauche signalent des mots davantage portes par le texte A.
- Les barres a droite signalent des mots davantage portes par le texte B.
