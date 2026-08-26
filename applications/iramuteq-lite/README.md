# iramuteq-lite

Version **web/VPS uniquement** de `iramuteq-lite`, prévue pour Coolify sur le VPS OVH.

## Ce dossier contient

- `frontend/` : interface web statique
- `webapp/` : serveur FastAPI et pont HTTP
- `backend/` : orchestration Python et scripts R batch
- `iramuteqlite/` : logique métier utilisée au runtime
- `dictionnaires/`, `help/`, `images/` : ressources nécessaires à l'application
- `Dockerfile` et `docker-entrypoint.sh` : déploiement conteneur
