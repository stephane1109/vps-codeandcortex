# Analyses multi modales

Application Streamlit d'analyse multimodale de la temporalite a partir de texte, audio et images synchronisees.

## Fonctionnalites conservees

- analyse textuelle avec spaCy Transformer
- analyse audio (pauses, activite vocale, debit)
- alignement temporel via Whisper ou fichier de timestamps
- synchronisation d'images 1 fps
- detection d'attitudes non verbales
- detection d'emotions sur images
- vecteur emotionnel
- detection d'anomalies multimodales
- tests croises et exports CSV / Excel

## Execution locale

```bash
streamlit run main.py
```

## Deploiement VPS / Coolify

Les fichiers ajoutes pour le VPS sont :

- `Dockerfile`
- `docker-entrypoint.sh`
- `.streamlit/config.toml`
- `DEPLOIEMENT_OVH_COOLIFY.md`

Le dossier GitHub cible est `applications/Analyses_multi_modales`.
