# iramuteq-lite_autoCHD

Version **web/VPS uniquement** d'IRaMuTeQ Lab, prévue pour Coolify sur le VPS OVH.

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
- Base Directory : `/applications/iramuteq-lite_autoCHD`
- Port : `8000`
- Domaine conseillé : `iramuteqliteautochd.codeandcortex.fr`

## Note build VPS

- le conteneur preinstalle par defaut le bootstrap R/CHD pendant le `docker build`
- les dependances runtime eventuellement reinstallees sont conservees dans `/data/app`
