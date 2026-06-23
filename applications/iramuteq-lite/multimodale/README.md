# Multimodale

Ce dossier prépare une approche multimodale orientée **sciences humaines** :
- texte transcrit et horodaté
- indicateurs audio
- mouvements vidéo
- synchronisation sur une timeline commune

L'objectif n'est pas de produire un diagnostic automatique.  
L'idée est plutôt de repérer des **configurations multimodales** :
- rupture discursive
- pré-rupture
- discordance entre verbal et non-verbal
- zones de tension, de retrait ou de bascule

Dans une lecture inspirée de **Gregory Bateson**, ces scripts peuvent servir à observer :
- des messages contradictoires entre texte, voix et corps
- des moments de double contrainte potentielle
- des transitions où le cadre interactionnel semble se reconfigurer

## Fichiers

- [`audio.py`](/Users/stephanemeurisse/Documents/Recherche/tauri-iramuteq-lite/multimodale/audio.py)
  - transcription Whisper depuis un fichier local ou une URL YouTube
  - segments horodatés
  - indicateurs audio simples

- [`mouvements.py`](/Users/stephanemeurisse/Documents/Recherche/tauri-iramuteq-lite/multimodale/mouvements.py)
  - optical flow dense
  - heatmap de mouvements
  - visages

- [`multivisage.py`](/Users/stephanemeurisse/Documents/Recherche/tauri-iramuteq-lite/multimodale/multivisage.py)
  - détection et suivi multi-visages
  - identifiants `face_id` stables entre images proches
  - préparation d'un export par visage pour une future interface multivisage

- [`synchronisation.py`](/Users/stephanemeurisse/Documents/Recherche/tauri-iramuteq-lite/multimodale/synchronisation.py)
  - synchronisation segments texte/audio avec fenêtres vidéo
  - agrégation des indicateurs par segment
  - clustering optionnel

- [`alignement.py`](/Users/stephanemeurisse/Documents/Recherche/tauri-iramuteq-lite/multimodale/alignement.py)
  - extraction d'images vidéo à cadence fixe
  - intervalle partiel ou vidéo complète
  - alignement des images avec les segments transcrits

- [`common.py`](/Users/stephanemeurisse/Documents/Recherche/tauri-iramuteq-lite/multimodale/common.py)
  - utilitaires communs

## Dépendances pratiques

Minimales :
- `python`
- `numpy`
- `ffmpeg`
- `yt-dlp` si la source est YouTube

Pour la transcription :
- `faster-whisper` ou `openai-whisper`

Pour les indicateurs audio étendus :
- `librosa`

Pour la vidéo :
- `opencv-python`

Pour le clustering :
- `scikit-learn`

Pour les vidéos YouTube restreintes :
- un fichier `cookies.txt` ou `.cookies` exporté par l'extension Cookies peut être fourni à `yt-dlp`

## Pipeline proposé

### 1. Texte + audio

Exemple :

```bash
python multimodale/audio.py \
  --source "https://www.youtube.com/watch?v=..." \
  --cookies "/chemin/vers/cookies.txt" \
  --output-dir multimodale/exports/audio_demo
```

Sorties principales :
- `transcription_segments_complet.csv`
- `transcription_segments_essentiel.csv`
- `transcription_segments.jsonl`
- `audio_summary.json`
- `audio_timeline_altair.html`

### 2. Mouvements vidéo

```bash
python multimodale/mouvements.py \
  --source "/chemin/vers/video.mp4" \
  --output-dir multimodale/exports/video_demo

Exemple YouTube avec cookies :

```bash
python multimodale/mouvements.py \
  --source "https://www.youtube.com/watch?v=..." \
  --cookies "/chemin/vers/cookies.cookies" \
  --output-dir multimodale/exports/video_demo
```
```

Sorties principales :
- `mouvements_frames.csv`
- `mouvements_multivisage.csv`
- `mouvements_windows.csv`
- `motion_heatmap.png`
- `mouvements_summary.json`
- `mouvements_timeline_altair.html`
- `keyframes/`

### 3. Synchronisation

```bash
python multimodale/synchronisation.py \
  --segments-csv multimodale/exports/audio_demo/transcription_segments_complet.csv \
  --windows-csv multimodale/exports/video_demo/mouvements_windows.csv \
  --output-dir multimodale/exports/sync_demo
```

Sorties principales :
- `segments_multimodaux.csv`
- `segments_multimodaux.jsonl`
- `synchronisation_summary.json`

### 4. Alignement images ↔ segments

```bash
python multimodale/alignement.py \
  --source "/chemin/vers/video.mp4" \
  --segments-csv multimodale/exports/audio_demo/transcription_segments_complet.csv \
  --fps 1 \
  --quality low \
  --output-dir multimodale/exports/alignement_demo
```

Exemple sur une URL YouTube avec cookies et extraction dense :

```bash
python multimodale/alignement.py \
  --source "https://www.youtube.com/watch?v=..." \
  --segments-csv multimodale/exports/audio_demo/transcription_segments_complet.csv \
  --cookies "/chemin/vers/cookies.txt" \
  --fps 25 \
  --start-sec 30 \
  --end-sec 90 \
  --quality high \
  --output-dir multimodale/exports/alignement_demo
```

Sorties principales :
- `frames_index.csv`
- `frames_index.jsonl`
- `segments_images_alignement.csv`
- `segments_images_alignement.jsonl`
- `alignement_summary.json`
- `alignement_segments_altair.html`

## Indicateurs audio proposés

Les scripts calculent déjà ou préparent :

- `pause_before_sec` / `pause_after_sec`
  - pauses avant et après chaque segment

- `pause_count`, `long_pause_count_1s`
  - structure des silences

- `words_per_sec`
  - vitesse de débit transcrit

- `rms_mean`, `rms_std`
  - énergie moyenne et variabilité

- `peak_dbfs`
  - pic sonore

- `zcr_mean`
  - rugosité / bruitage du signal

- `spectral_centroid_mean`
  - brillance ou déplacement spectral moyen

- `onset_strength_mean`
  - intensité des attaques sonores

- `silence_ratio`
  - part du silence dans un segment ou dans tout l'enregistrement

## Indicateurs visuels proposés

Les scripts calculent déjà ou préparent :

- `motion_mean`
  - agitation moyenne par fenêtre

- `motion_peak_p95`
  - pic de mouvement robuste

- `motion_active_ratio`
  - proportion de l'image en mouvement actif

- `direction_dx`, `direction_dy`
  - vecteur global du mouvement

- `dominant_direction`
  - gauche / droite / haut / bas / stable

- `heat_x_norm`, `heat_y_norm`
  - centre approximatif de la zone chaude du mouvement

- `face_count`
  - nombre de visages détectés

- `face_area_ratio`
  - poids relatif du visage principal dans l'image

## Indicateurs de synchronisation proposés

Le fichier synchronisé permet de suivre, pour chaque segment de texte :

- ce qui se dit
- la pause qui précède
- la charge sonore
- le niveau d'agitation visuelle
- la direction dominante du mouvement
- une image repère (`keyframe`)

Cela permet déjà de travailler sur :
- les segments de rupture
- les segments de pré-rupture
- les discordances entre contenu verbal et non-verbal

## Clustering proposé

Le clustering n'est pas pensé ici comme une vérité cachée, mais comme une aide à la lecture.

Le script de synchronisation peut former des groupes sur des vecteurs multimodaux du type :
- durée de segment
- pauses
- vitesse verbale
- énergie audio
- mouvement moyen
- pic de mouvement
- ratio de mouvement actif
- poids du visage

Lecture possible :
- cluster de retrait
- cluster d'agitation
- cluster de bascule
- cluster de tension faible

Le plus intéressant n'est pas seulement le cluster lui-même, mais :
- le passage d'un cluster à l'autre
- les segments qui précèdent un changement de cluster

## Pistes Bateson / double contrainte

Quelques pistes d'analyse intéressantes :

- **discordance verbal / non-verbal**
  - texte de calme, mais visage ou mouvement tendu

- **discordance verbal / prosodie**
  - contenu stable, mais pics sonores ou pauses longues

- **pré-rupture**
  - avant un changement lexical fort, voir si apparaissent déjà :
    - pauses
    - agitation

- **contrainte paradoxale**
  - texte allant dans une direction, non-verbal dans l'autre

## Propositions d'extension

- calculer une **JSD locale** sur fenêtres temporelles
- ajouter une **détection de contradiction multimodale**
- ajouter une **lecture pré-rupture** ciblée sur les segments précédant une rupture
