# DetectIA vidéo

Application Streamlit d'analyse forensique exploratoire pour repérer des incohérences temporelles dans une vidéo.

L'objectif est d'aider une analyse fake news en observant :

- le flux optique entre frames ;
- les résidus après compensation du mouvement ;
- le flicker temporel ;
- les accélérations ou ruptures de mouvement ;
- les frames localement suspectes.

## Important

DetectIA ne donne pas une preuve automatique qu'une vidéo est générée par IA. Le score est un indicateur heuristique. Une vidéo compressée, stabilisée, montée, ralentie, recadrée ou très dégradée peut produire des signaux suspects.

## Lancement local

```bash
cd "/Users/stephanemeurisse/Documents/OVH - VPS/detectia"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run main.py
```

## Docker

```bash
docker build -t detectia .
docker run --rm -p 8501:8501 detectia
```

Puis ouvrir :

```text
http://localhost:8501
```

## Sorties

L'application produit :

- un score de suspicion temporelle ;
- des courbes temporelles ;
- une heatmap du mouvement ;
- une heatmap des résidus ;
- des frames suspectes ;
- un ZIP contenant rapport JSON, CSV et images.
