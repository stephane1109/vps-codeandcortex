# IRaMuTeQ-Lab

Version expérimentale **web/VPS** dérivée de `iramuteq-lite`, prévue pour Coolify sur le VPS OVH.

## Ce dossier contient

- `frontend/` : interface web statique
- `webapp/` : serveur FastAPI et pont HTTP
- `backend/` : orchestration Python et scripts R batch
- `iramuteqlite/` : logique métier utilisée au runtime
- `dictionnaires/`, `help/`, `images/` : ressources nécessaires à l'application
- `Dockerfile` et `docker-entrypoint.sh` : déploiement conteneur

## Ce dossier ne contient pas

- la version bureau Tauri native
- `app.R`, `ui.R`, `global.R`
- les anciens jobs locaux `backend/jobs/`
- les fichiers de packaging desktop

## Coolify

- Repo : `VPS`
- Base Directory : `/applications/iramuteq-lab-lab`
- Port : `8000`
- Domaine : `iramuteqlab.codeandcortex.fr`

## Note build VPS

- le conteneur preinstalle par defaut le bootstrap R/CHD pendant le `docker build`
- les dependances runtime eventuellement reinstallees sont conservees dans `/data/app`

### Modèles spaCy

Les modèles anglais `en_core_web_md` et allemand `de_core_news_md` sont installés par défaut. Pour ajouter d’autres langues, définir l’argument de build `IRAMUTEQ_SPACY_MODELS` avec tous les modèles à installer, séparés par des virgules, par exemple :

```text
IRAMUTEQ_SPACY_MODELS=en_core_web_md,de_core_news_md,nl_core_news_sm
```

Les modèles sont téléchargés pendant le `docker build` par `python3 -m spacy download` et stockés dans le répertoire `site-packages` du Python système à l'intérieur de l'image Docker. Ils ne sont pas enregistrés dans les dossiers de corpus ou d'exports. Pour afficher leur emplacement exact dans un conteneur en cours d'exécution :

```bash
python3 -c "import en_core_web_md, de_core_news_md; print(en_core_web_md.__path__); print(de_core_news_md.__path__)"
```
