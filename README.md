-----------------------------------------
### Projet : Analyse de cooccurrences
- Auteur : Stéphane Meurisse
- Site Web : https://www.codeandcortex.fr
- Date d'adaptation VPS : 19 juin 2026

-----------------------------------------
### Description

Cette application **Streamlit** calcule et visualise des cooccurrences lexicales à partir d'un ou plusieurs fichiers texte.

Fonctionnalités principales :

- graphe global pondéré par fréquence
- calcul des associations par log-likelihood
- nuages de cooccurrences
- concordanciers HTML
- export CSV, HTML et PNG

-----------------------------------------
### Déploiement OVH / Coolify

Le projet inclut les fichiers nécessaires pour un déploiement sur **VPS OVH** via **Coolify** :

- `Dockerfile`
- `docker-entrypoint.sh`
- `.streamlit/config.toml`
- `DEPLOIEMENT_OVH_COOLIFY.md`

Exemple de sous-domaine cible :

- `analyse-coccurrences.codeandcortex.fr`

Lancement local du conteneur :

```bash
docker build -t analyse-coccurrences .
docker run --rm -p 8501:8501 analyse-coccurrences
```

L'application sera ensuite accessible sur `http://localhost:8501`.

-----------------------------------------
### Dépendances

Le conteneur installe notamment :

- `streamlit`
- `spacy`
- `fr_core_news_md`
- `pandas`
- `matplotlib`
- `wordcloud`
- `networkx`
- `pyvis`
- `scipy`

-----------------------------------------
### Notes techniques

- le modèle spaCy français est installé à la build Docker
- le chargement du pipeline spaCy est mis en cache côté Streamlit pour limiter le coût mémoire/CPU des reruns
- l'application n'a pas besoin de volume persistant pour fonctionner
