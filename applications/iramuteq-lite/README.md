# iramuteq-lite

Version **web/VPS uniquement** de `iramuteq-lite`, prévue pour Coolify sur le VPS OVH.

## Ce dossier contient

- `frontend/` : interface web statique
- `webapp/` : serveur FastAPI et pont HTTP
- `backend/` : orchestration Python et scripts R batch
- `iramuteqlite/`, `lda/` : logique métier utilisée au runtime
- `dictionnaires/`, `help/`, `images/` : ressources nécessaires à l'application
- `Dockerfile` et `docker-entrypoint.sh` : déploiement conteneur

## Ce dossier ne contient pas

- la version bureau Tauri native
- `app.R`, `ui.R`, `global.R`
- les anciens jobs locaux `backend/jobs/`
- les fichiers de packaging desktop

## Coolify

- Repo : `VPS`
- Base Directory : `/applications/iramuteq-lite`
- Port : `8000`
- Domaine conseillé : `iramuteqlite.codeandcortex.fr`

## Note build VPS

- le conteneur n'installe plus tous les packages R pendant le `docker build`
- le bootstrap applicatif installe les dependances texte essentielles au premier usage
