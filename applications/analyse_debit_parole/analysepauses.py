######################
# www.codeandcortex.fr
######################
# analysepauses.py

import pandas as pd
import altair as alt

def analyser_pauses(transcript_segments, seuil=1.0):
    """
    Analyse les pauses entre les segments transcrits.

    Pour chaque segment consécutif, calcule la durée de la pause (différence entre la fin du segment i
    et le début du segment i+1). Seules les pauses dont la durée est supérieure au seuil (en secondes)
    sont conservées.

    Renvoie une liste de dictionnaires contenant :
      - 'pause_start': timestamp de fin du segment précédent
      - 'pause_end': timestamp de début du segment suivant
      - 'duration': durée de la pause en secondes
    """
    pauses = []
    segments = sorted(transcript_segments, key=lambda s: s['start'])
    for i in range(len(segments) - 1):
        fin_seg = float(segments[i].get('end', segments[i]['start']))
        debut_seg = float(segments[i + 1]['start'])
        duree_pause = debut_seg - fin_seg
        if duree_pause > seuil:
            pauses.append({
                'pause_start': fin_seg,
                'pause_end': debut_seg,
                'duration': duree_pause
            })
    return pauses


def generer_export_pauses(pauses, format_timestamp_func):
    """
    Génère une chaîne de caractères détaillant l'analyse des pauses.
    Chaque pause est affichée avec ses timestamps (format HH:MM:SS et en secondes) et sa durée.

    Renvoie un texte à afficher dans l'interface.
    """
    lignes = ["Analyse des pauses (> 1 sec):"]
    for i, pause in enumerate(pauses, start=1):
        lignes.append(
            f"Pause {i}: de {format_timestamp_func(pause['pause_start'])} "
            f"({pause['pause_start']:.2f}s) à {format_timestamp_func(pause['pause_end'])} "
            f"({pause['pause_end']:.2f}s), durée = {pause['duration']:.2f}s"
        )
    return "\n".join(lignes)


def graph_pauses(pauses):
    """
    Génère un graphique en barre Altair qui représente pour chaque pause son
    point médian sur la timeline (axe x) et sa durée en secondes (axe y).
    """

    # Création d'un DataFrame à partir de la liste des pauses
    df_pauses = pd.DataFrame(pauses)
    # Calculer le point médian de chaque pause
    df_pauses['midpoint'] = (df_pauses['pause_start'] + df_pauses['pause_end']) / 2.0

    # Créer un graphique en barre avec une largeur fixe pour chaque barre (taille=20)
    chart = alt.Chart(df_pauses).mark_bar(size=20).encode(
        x=alt.X('midpoint:Q',
                title='Timeline de la vidéo (s)',
                axis=alt.Axis(format=".0f")),
        y=alt.Y('duration:Q',
                title='Durée de la pause (s)',
                axis=alt.Axis(format=".2f")),
        tooltip=[
            alt.Tooltip('pause_start:Q', format=".2f", title='Début pause (s)'),
            alt.Tooltip('pause_end:Q', format=".2f", title='Fin pause (s)'),
            alt.Tooltip('duration:Q', format=".2f", title='Durée (s)')
        ]
    ).properties(
        title="Distribution des pauses par timeline",
        width=600,
        height=300
    )
    return chart
