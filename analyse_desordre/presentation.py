"""Aides et présentation françaises ; aucune modification des mesures statistiques."""
import math

AIDE_INDICE=(
    "Score exploratoire de 0 à 100 décrivant l’agitation visuelle mesurée. Il combine à poids égaux "
    "l’instabilité de la caméra, la diversité des directions de mouvement après compensation caméra "
    "(pondérée par leur amplitude), et l’irrégularité du mouvement dans le temps. "
    "Plus il augmente, plus cette combinaison est élevée. Les changements de plans sont exclus. "
    "Ce n’est ni un pourcentage, ni une probabilité, ni une mesure validée de violence ou de désordre social. "
    "Les échelles et les poids sont des choix exploratoires ; la couverture indique la part réellement mesurée."
)
AIDES_INDICATEURS={
    'indice_desordre':AIDE_INDICE,
    'instabilite_camera':'Variation de la vitesse du mouvement global estimé, en diagonales d’image par seconde au carré. Un déplacement régulier peut avoir une faible instabilité.',
    'entropie_directionnelle':'Diversité des directions du mouvement résiduel, de 0 à 1 : proche de 0 pour une direction dominante ou aucun mouvement, proche de 1 pour des directions équilibrées.',
    'irregularite_temporelle':'Variation relative de l’amplitude du mouvement entre deux intervalles du même plan, de 0 à 1. Proche de 0 si elle reste stable.',
    'vitesse_residuelle':'Vitesse moyenne après retrait du mouvement dominant de caméra, en diagonales d’image par seconde.'}
AIDE_SPEARMAN=(
    "Spearman sert ici à explorer si les vidéos ayant un indicateur plus élevé ont généralement plus "
    "ou moins d’engagement. Son coefficient ρ varie de −1 à +1. Ce n’est pas un test universellement "
    "meilleur et il ne prouve pas une causalité. Avec dix vidéos, les conclusions restent fragiles. "
    "Les p-values sont obtenues par permutations, avec une correction des comparaisons multiples. "
    "Ce calcul ne corrige pas les différences de compte, de date de collecte, d’audience ou la dépendance "
    "entre vidéos d’un même compte. Une analyse explicative demanderait un modèle adapté aux compteurs "
    "et aux facteurs de confusion, avec davantage de données."
)


def formater_nombre(valeur,decimales=2):
    """Séparer les milliers par des espaces et les décimales par une virgule."""
    if valeur is None or not math.isfinite(float(valeur)): return 'Non disponible'
    texte=f'{float(valeur):,.{decimales}f}'.replace(',',' ').replace('.',',')
    return texte.rstrip('0').rstrip(',') if decimales else texte


def preparer_graphique(tableau,axe_x,axe_y,libelle_x,libelle_y):
    """Une observation par vidéo, sans jitter ni agrégation qui modifierait ses coordonnées."""
    import pandas as pd
    donnees=tableau.copy()
    for colonne in (axe_x,axe_y): donnees[colonne]=pd.to_numeric(donnees[colonne],errors='coerce')
    donnees=donnees[donnees[axe_x].map(lambda x:pd.notna(x) and math.isfinite(x)) &
                    donnees[axe_y].map(lambda x:pd.notna(x) and math.isfinite(x))]
    groupes={}
    for _,ligne in donnees.iterrows():
        groupes.setdefault((float(ligne[axe_x]),float(ligne[axe_y])),[]).append(int(ligne['numero_video']))
    compte_brut=axe_y in ('likes','commentaires','partages','vues')
    points=[]
    for _,ligne in donnees.iterrows():
        x,y=float(ligne[axe_x]),float(ligne[axe_y]);numeros=groupes[(x,y)]
        points.append({'x':x,'y':y,'numero_video':int(ligne['numero_video']),
            'publication_id':str(ligne.get('publication_id','')),'url':str(ligne.get('url')) if pd.notna(ligne.get('url')) else '',
            'valeur_x':formater_nombre(x,4),'valeur_y':formater_nombre(y,0 if compte_brut else 4),
            'videos_superposees':', '.join(map(str,numeros)),'nombre_superposees':len(numeros)})
    # La locale du navigateur ne doit pas réintroduire 1,600,000 ou une notation scientifique.
    precision_x=2 if axe_x=='indice_desordre' else 4
    expression_x=f"replace(replace(format(datum.value, ',.{precision_x}f'), /,/g, ' '), '.', ',')"
    expression_y="replace(format(datum.value, ',.0f'), /,/g, ' ')" if compte_brut else expression_x
    specification={
        'mark':{'type':'circle','size':85,'opacity':.65},
        'encoding':{
            'x':{'field':'x','type':'quantitative','title':libelle_x,
                 'axis':{'labelExpr':expression_x,'labelOverlap':True}},
            'y':{'field':'y','type':'quantitative','title':libelle_y,
                 'axis':{'labelExpr':expression_y,**({'tickMinStep':1} if compte_brut else {})}},
            'tooltip':[{'field':'numero_video','type':'ordinal','title':'N° vidéo'},
                       {'field':'publication_id','type':'nominal','title':'Identifiant TikTok'},
                       {'field':'valeur_x','type':'nominal','title':libelle_x},
                       {'field':'valeur_y','type':'nominal','title':libelle_y},
                       {'field':'videos_superposees','type':'nominal','title':'Vidéos à ces coordonnées'},
                       {'field':'url','type':'nominal','title':'URL TikTok'}]},
        'height':380}
    return pd.DataFrame(points),specification,{
        'videos':len(points),'exclues':len(tableau)-len(points),'positions':len(groupes),
        'superposees':sum(len(n) for n in groupes.values() if len(n)>1)}
