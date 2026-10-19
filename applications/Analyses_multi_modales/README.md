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

## Installation CPU sur le VPS

Le Dockerfile installe `torch==2.8.0+cpu` et `torchvision==0.23.0+cpu`
depuis l’index CPU officiel PyTorch. `constraints-cpu.txt` conserve ces variantes
pendant l’installation des autres dépendances, sans bibliothèques NVIDIA/CUDA.
La construction vérifie ensuite les versions, l’absence de paquets GPU et une
opération CPU de torchvision avec `verifier_installation_cpu.py`.

Cette modification réduit le volume à installer ; elle ne libère pas le cache
Docker déjà présent. Une erreur `No space left on device` peut encore nécessiter
de libérer de l’espace disque avant de redéployer.
