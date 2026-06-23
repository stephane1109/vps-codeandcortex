# Deploiement OVH / Coolify

## Repertoire

- Depot : `stephane1109/vps-codeandcortex`
- Base directory : `/applications/Analyses_multi_modales`

## Build

- Type : `Dockerfile`
- Port interne : `8501`

## Variables utiles

- `PORT=8501`
- `STREAMLIT_SERVER_BASE_URL_PATH=` laisser vide sauf reverse proxy avec sous-chemin

## Ressources conseillees

Cette application charge des briques lourdes (`spaCy Transformer`, `TensorFlow`, `DeepFace`, `Whisper`, `MediaPipe`).

- minimum conseille : `4 vCPU / 8 Go RAM`
- plus confortable : `6 vCPU / 12 Go RAM`

## Notes d'exploitation

- Les images attendues pour la synchro doivent suivre le format `i_{N}s_1fps.jpg`.
- Le premier lancement des briques vision / emotion peut etre plus long si certains poids doivent etre initialises.
- L'upload Streamlit a ete releve a `1024 MB` dans `.streamlit/config.toml` pour conserver les usages audio + images.
