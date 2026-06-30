# Vecteur emotionnel - version VPS

Application Streamlit pour :

- telecharger une video YouTube
- extraire 25 images par seconde sur une plage temporelle
- detecter les emotions via FER sur chaque frame
- calculer les moyennes emotionnelles par seconde
- construire un concordancier avec images, emotions et sous-titres YouTube
- produire des visualisations Altair, PCA, KMeans et similarite cosinus

## Adaptation VPS

Cette version est preparee pour un deploiement sur un VPS OVH via Coolify.

Les adaptations principales sont :

- stockage temporaire gere par session utilisateur
- exports telechargeables sans demander un chemin local a l'utilisateur
- extraction video geree directement par `opencv-python-headless`
- compatibilite Coolify via `PORT`, `STREAMLIT_SERVER_BASE_URL_PATH` et `APP_DATA_DIR`
- bundle ZIP regroupant concordancier, tableaux, graphiques et images annotees

## Lancer localement avec Docker

```bash
docker build -t vecteur-emotionnel .
docker run --rm -p 8501:8501 vecteur-emotionnel
```

Application accessible ensuite sur `http://localhost:8501`.

## Variables d'environnement utiles

- `PORT` : port d'ecoute Streamlit
- `STREAMLIT_SERVER_BASE_URL_PATH` : prefixe d'URL si besoin
- `APP_DATA_DIR` : stockage temporaire des sessions et exports
- `APP_SESSION_TTL_HOURS` : duree de retention des sessions temporaires

## Notes

- L'analyse emotionnelle repose sur `FER` et `tensorflow-cpu`, ce qui peut etre couteux en CPU.
- Les sous-titres YouTube sont recuperes si l'API publique de transcripts les expose.
- Les images annotees et les exports sont prepares dans un dossier temporaire par session, puis telechargeables depuis l'interface.
