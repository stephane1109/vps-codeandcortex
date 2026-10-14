# VisioTrack

Application Streamlit autonome pour mesurer la **visibilité** des smartphones et
des 79 autres catégories COCO dans des lots de vidéos. Elle n'infère pas leur
utilisation effective. Le smartphone correspond à la classe COCO `cell phone` (67),
qui peut aussi reconnaître d'autres téléphones portables.

## Utilisation

1. Ajouter des URL HTTPS YouTube/TikTok, plusieurs MP4 ou des ZIP contenant des MP4.
2. Choisir les catégories (smartphone par défaut) et la fréquence (1 image/s).
3. Lancer l'analyse puis télécharger les résultats, intervalles et détections CSV.

Les sous-dossiers ZIP sont parcourus automatiquement, sans extraction globale.
Une erreur de téléchargement, d'archive ou de décodage est inscrite dans le tableau
et le lot continue. Les noms identiques restent distincts grâce à `video_id`.
Les vidéos sans objet détecté figurent dans les résultats avec des valeurs nulles.
Les vidéos en erreur ont des mesures vides, jamais des zéros trompeurs.

## Calculs et interprétation

- YOLO11n fonctionne sur CPU, avec une taille d'inférence de 640 pixels et un seuil
  de confiance de 0,25. La suppression des boîtes redondantes utilise un IoU de 0,5.
- ByteTrack reçoit aussi les boîtes de confiance 0,1 à 0,25 pour les associations.
  Un suivi distinct est créé par catégorie et par vidéo. Une nouvelle détection
  non encore confirmée par ByteTrack compte dans la visibilité, avec `piste_id` vide.
- La lecture est séquentielle et utilise les horodatages OpenCV, y compris pour
  les vidéos à cadence variable. La première image à partir de chaque cible
  temporelle est analysée ; si la fréquence demandée dépasse celle de la vidéo,
  chaque image est analysée une seule fois.
- Chaque échantillon représente l'intervalle allant jusqu'au prochain échantillon.
  Le dernier est borné par la durée de la piste vidéo lue avec ffprobe. Les intervalles
  sont semi-ouverts `[début, fin[`, sauf la borne finale du média.
- La durée d'une catégorie est l'union de ses plages visibles, et non la somme
  des durées de ses objets : deux téléphones pendant 10 s donnent **10 s**, maximum **2**.
- Le pourcentage vaut `100 × durée visible / durée vidéo` et reste entre 0 et 100.
  Le maximum simultané provient uniquement des boîtes réellement observées.
- Une image analysée sans détection ferme l'intervalle. Les pistes perdues ou les
  prédictions de ByteTrack ne prolongent jamais artificiellement la visibilité.
- À 1 image/s, les durées restent des **estimations** : les apparitions brèves peuvent
  être manquées et les frontières se situent entre deux échantillons. Un faible
  échantillonnage fragmente aussi les identifiants ByteTrack. Le calcul par catégorie
  reste indépendant de ces changements d'identifiant. Les petits objets, occultations
  et faux positifs limitent la précision ; les horodatages permettent un contrôle.

## Exports

Les trois CSV sont encodés en UTF-8 avec BOM et séparés par des virgules. Les valeurs
exportées gardent leur précision ; seul l'affichage du tableau est arrondi.

| Fichier | Contenu |
| --- | --- |
| `resultats.csv` | Une ligne par vidéo et catégorie sélectionnée : source, statut, durée totale, présence, durée visible, pourcentage, maximum, fréquence demandée, images analysées. Une ligne par vidéo en erreur. |
| `intervalles.csv` | Une ligne par plage continue de visibilité et catégorie : identifiant vidéo, début, fin, durée, maximum simultané. |
| `detections.csv` | Une ligne par boîte observée : identifiant vidéo, index d'image depuis zéro, horodatage réel, catégorie, piste éventuelle, confiance et coordonnées en pixels. |

Les pistes s'interprètent dans le contexte `(video_id, catégorie, piste_id)` ; elles
ne constituent pas une reconnaissance d'identité entre vidéos. Les détections et
intervalles partiels d'une vidéo en erreur sont exclus des exports communs.

## Installation locale

Python 3.11, FFmpeg/ffprobe et Deno ≥ 2.3 doivent être disponibles dans le PATH.
Deno sert à résoudre les challenges JavaScript de YouTube via yt-dlp.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Au premier lancement d'une analyse locale, les poids officiels `yolo11n.pt` sont
téléchargés dans `~/.cache/visiotrack`. Dans Docker, ils sont déjà téléchargés à la
construction. Il faut donc un accès réseau lors de la construction de l'image.

## Déploiement Coolify

Créer une application à partir du dépôt `stephane1109/vps-codeandcortex` :

| Paramètre | Valeur |
| --- | --- |
| Branche | `main` |
| Build Pack | `Dockerfile` |
| Base Directory | `/applications/visiotrack` |
| Dockerfile Location | `/Dockerfile` |
| Port | `8501` |
| Healthcheck HTTP | `/_stcore/health` |

Le conteneur s'exécute sans privilège root et installe PyTorch CPU. Il n'a besoin ni
de GPU, ni de Redis, ni du tableau de bord VPS. Prévoir initialement 2 vCPU et 4 Go
de mémoire, à ajuster selon les résolutions et les imports, ainsi que suffisamment
d'espace temporaire pour la plus grosse vidéo. Configurer le proxy Coolify pour
autoriser les volumes de téléversement souhaités et les connexions WebSocket.

```bash
docker build -t visiotrack .
docker run --rm -p 8501:8501 visiotrack
```

Variables d'environnement techniques (aucune option supplémentaire dans l'interface) :

| Variable | Défaut Docker | Rôle |
| --- | --- | --- |
| `PORT` | `8501` | Port Streamlit. |
| `VISIOTRACK_CPU_THREADS` | `2` | Nombre de threads PyTorch. |
| `VISIOTRACK_MAX_VIDEO_MB` | `4096` | Taille maximale d'une vidéo, y compris après décompression. |
| `STREAMLIT_SERVER_MAX_UPLOAD_SIZE` | `1024` | Taille maximale de chaque import navigateur, en Mo. |
| `VISIOTRACK_VIDEO_DIR` | vide | Dossier serveur dont tous les MP4 seront ajoutés à chaque lot. |
| `VISIOTRACK_MODEL` | `/app/models/yolo11n.pt` | Chemin d'un modèle YOLO compatible avec les 80 classes COCO. |

### Grands lots et mémoire

Une seule vidéo est préparée et analysée à la fois. Les images ne sont pas empilées,
les détections et intervalles sont écrits au fil de l'eau sur disque. Les médias
temporaires sont supprimés après chaque vidéo ; les CSV restent disponibles durant
la session puis sont supprimés avec son répertoire temporaire, ou remplacés au lot
suivant. Un verrou partagé limite à un seul lot actif par processus Streamlit.

**Streamlit conserve les fichiers téléversés et les exports téléchargeables en
mémoire.** Le traitement séquentiel ne supprime pas cette limite du navigateur.
Pour les lots de plusieurs Go, monter un dossier serveur en lecture seule, puis
définir `VISIOTRACK_VIDEO_DIR=/videos`. L'analyse inclut ses sous-dossiers et ne charge
pas le lot dans l'uploader. Exemple :

```bash
docker run --rm -p 8501:8501 \
  -v /chemin/lot:/videos:ro -e VISIOTRACK_VIDEO_DIR=/videos visiotrack
```

Les URL privées, indisponibles, bloquées par la plateforme ou nécessitant une
authentification peuvent échouer ; le diagnostic est conservé par vidéo. Les directs
et les playlists sont refusés. yt-dlp est actualisé lors de la reconstruction de
l'image pour suivre les changements des plateformes.

## Vérification

```bash
python -m unittest discover -s tests -v
```

Les tests contrôlent notamment l'union des présences, les absences et réapparitions,
la fraction finale, la cadence variable, le suivi ByteTrack réel, les archives et
la poursuite d'un lot après erreur. L'inférence YOLO peut être vérifiée séparément
avec un MP4 et les poids téléchargés.

Références d'implémentation : [Ultralytics ByteTrack](https://docs.ultralytics.com/reference/trackers/byte_tracker/),
[yt-dlp et ses moteurs JavaScript](https://github.com/yt-dlp/yt-dlp/wiki/EJS),
[limites de l'uploader Streamlit](https://docs.streamlit.io/develop/api-reference/widgets/st.file_uploader).
