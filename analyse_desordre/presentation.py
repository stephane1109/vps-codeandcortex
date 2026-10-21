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
    'violence_visible':"Codage manuel réalisé après visionnage de la portion de vidéo analysée : 1 = violence physique visible ; 0 = absence de violence physique visible ; valeur manquante = vidéo non évaluée. Ce codage humain ne se déduit pas de l’indice automatique de désordre. La variable binaire permet des comparaisons exploratoires, sans prouver de lien causal.",
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
    compte_brut=axe_y in ('likes','commentaires','partages','favoris','vues')
    points=[]
    for _,ligne in donnees.iterrows():
        x,y=float(ligne[axe_x]),float(ligne[axe_y]);numeros=groupes[(x,y)]
        points.append({'x':x,'y':y,'numero_video':int(ligne['numero_video']),
            'publication_id':str(ligne.get('publication_id','')),'url':str(ligne.get('url')) if pd.notna(ligne.get('url')) else '',
            'valeur_x':("Oui (1)" if x==1 else "Non (0)") if axe_x=='violence_visible' else formater_nombre(x,4),
            'valeur_y':formater_nombre(y,0 if compte_brut else 4),
            'videos_superposees':', '.join(map(str,numeros)),'nombre_superposees':len(numeros)})
    # La locale du navigateur ne doit pas réintroduire 1,600,000 ou une notation scientifique.
    precision_x=2 if axe_x=='indice_desordre' else 4
    expression_x=f"replace(replace(format(datum.value, ',.{precision_x}f'), /,/g, ' '), '.', ',')"
    expression_y="replace(format(datum.value, ',.0f'), /,/g, ' ')" if compte_brut else expression_x
    if axe_x == 'violence_visible':
        axe_horizontal = {'values':[0,1],
            'labelExpr':"datum.value === 0 ? 'Non (0)' : datum.value === 1 ? 'Oui (1)' : ''"}
    else:
        axe_horizontal = {'labelExpr':expression_x,'labelOverlap':True}
    specification={
        'mark':{'type':'circle','size':85,'opacity':.65},
        'encoding':{
            'x':{'field':'x','type':'quantitative','title':libelle_x,
                 'axis':axe_horizontal,
                 **({'scale':{'domain':[-0.2,1.2]}} if axe_x=='violence_visible' else {})},
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


def superposer_droite_regression(points, specification):
    """Ajouter une droite MCO dans Vega-Lite, sans modifier les points originaux.

    C'est une régression linéaire sur les valeurs brutes, distincte de la
    corrélation de rangs (Spearman). Aucun tracé pour un nuage inexploitable.
    """
    if len(points) < 3:
        return specification, "Il faut au moins trois vidéos ayant les deux mesures."
    if points["x"].nunique() < 2 or points["y"].nunique() < 2:
        return specification, "Une des deux variables est constante ; aucune tendance linéaire informative ne peut être tracée."

    # Les données sont transmises à st.vega_lite_chart comme source commune.
    # Tracer la droite en premier laisse chaque point et son infobulle visibles.
    graphique = {cle: valeur for cle, valeur in specification.items()
                 if cle not in ("mark", "encoding")}
    graphique["layer"] = [
        {
            "transform": [{"regression": "y", "on": "x", "method": "linear"}],
            "mark": {"type": "line", "strokeDash": [6, 4], "strokeWidth": 2.5},
            "encoding": {
                "x": {"field": "x", "type": "quantitative"},
                "y": {"field": "y", "type": "quantitative"},
            },
        },
        {"mark": specification["mark"], "encoding": specification["encoding"]},
    ]
    return graphique, None


AIDES_STATISTIQUES={
    'rho':"Rho (ρ) est le coefficient de Spearman, entre −1 et +1. Proche de +1 : les deux variables tendent à augmenter ensemble. Proche de −1 : l’une tend à diminuer quand l’autre augmente. Proche de 0 : aucune tendance monotone nette, mais une autre forme de relation peut exister. Ce n’est ni un pourcentage ni une preuve de causalité.",
    'n':"Nombre de vidéos ayant une valeur valide pour les deux variables comparées. Les vidéos avec une mesure manquante sont exclues de ce calcul. Ce nombre peut être inférieur au nombre de publications collectées.",
    'p':"P-value bilatérale obtenue par permutations : sous l’hypothèse d’absence d’association et d’échangeabilité des observations, fréquence d’une corrélation au moins aussi extrême que celle observée. Ce n’est pas la probabilité que l’hypothèse soit vraie, ni la taille de l’effet.",
    'p_ajustee_bh':"P-value ajustée par Benjamini–Hochberg sur les croisements calculables, pour tenir compte des comparaisons multiples. L’ajustement ne corrige ni les biais du corpus ni la dépendance entre vidéos d’un même compte.",
    'methode':"Méthode du test : permutations exactes jusqu’à sept vidéos utilisables, sinon tirages aléatoires reproductibles. Le coefficient rho reste calculé sur les rangs, avec rangs moyens pour les ex aequo.",
    'raison':"Explication lorsqu’une corrélation ne peut pas être calculée : moins de trois vidéos utilisables ou variable constante. Une cellule vide signifie que le calcul a pu être effectué.",
    'indicateur':"Indicateur visuel comparé à la variable d’engagement de cette ligne. Sa définition figure dans l’aide du tableau des vidéos et du sélecteur du graphique.",
    'engagement':"Compteur ou taux comparé à l’indicateur automatique ou au codage humain de violence : likes, commentaires, partages, favoris, vues ou taux pour 1 000 vues."
}
AIDES_COLONNES={
    **AIDES_INDICATEURS,
    'numero_video':"Numéro de repérage dans cette analyse, repris au survol des points. Ce n’est pas l’identifiant TikTok.",
    'publication_id':"Identifiant de la publication TikTok, conservé comme texte pour préserver tous ses chiffres.",
    'violence_visible':AIDES_INDICATEURS['violence_visible'],
    'url':"Lien vers la publication TikTok correspondante.",
    'metadonnees_presentes':"Indique si cette vidéo dispose d’une ligne de métadonnées collectées. Cela ne garantit pas que tous ses compteurs sont connus.",
    'vues':"Nombre de vues observé lors de la collecte. Il ne s’agit pas nécessairement de personnes distinctes.",
    'likes':"Nombre de likes observé lors de la collecte, sans division par le nombre de vues.",
    'commentaires':"Nombre de commentaires indiqué pour la publication, pas le nombre de textes de commentaires effectivement récupérés.",
    'partages':"Nombre de partages observé lors de la collecte, sans division par le nombre de vues.",
    'favoris':"Nombre de mises en favoris (enregistrements) observées sur TikTok lors de la collecte. Ce compteur peut être absent pour certaines publications ; une absence ne vaut pas zéro.",
    'fps_source':"Fréquence d’images annoncée par le fichier vidéo, en images par seconde. Elle peut différer de la fréquence choisie pour l’analyse.",
    'duree_annoncee_s':"Durée du fichier estimée à partir du nombre d’images et de sa fréquence annoncés, en secondes.",
    'images_decodees':"Nombre d’images lues dans le fichier ; seule une partie peut être retenue pour l’analyse.",
    'images_extraites':"Nombre d’images retenues à la fréquence d’analyse choisie. Ce n’est pas le nombre de vidéos.",
    'horodatage_reconstitue':"Vrai lorsque des horodatages ont dû être reconstruits depuis la fréquence annoncée, faute de timestamps vidéo progressant normalement.",
    'tronque':"Vrai lorsque la limite de durée configurée a interrompu l’analyse avant la fin de la vidéo.",
    'dernier_temps_s':"Horodatage de la dernière image retenue pour l’analyse, en secondes depuis le début de la vidéo.",
    'decodage_incomplet':"Vrai lorsque la lecture s’est terminée avant le nombre d’images annoncé, sans atteindre la limite de durée.",
    'duree_observee_s':"Somme des intervalles entre les images analysées, en secondes, y compris les intervalles ensuite exclus.",
    'duree_valide_s':"Durée totale des intervalles pour lesquels la compensation du mouvement de caméra a permis une mesure, en secondes.",
    'couverture_mouvement':"Part de la durée observée où le mouvement a pu être mesuré : 0,8 signifie 80 %. Une faible couverture rend la moyenne moins représentative.",
    'changements_plan':"Nombre de transitions classées comme changements de plans. Elles sont exclues du calcul des mouvements ; la détection reste heuristique.",
    'paires_exclues':"Nombre de paires d’images exclues, par exemple en raison d’une coupure, d’un changement de format ou d’une compensation de caméra indisponible.",
    'statut':"État de l’analyse : mesure disponible, résultat partiel, données insuffisantes ou erreur. Consulter la couverture et les erreurs avant d’interpréter le score.",
    'erreur':"Message expliquant un échec de traitement. Une cellule vide signifie qu’aucune erreur n’a été renseignée pour cette vidéo."
}
for _nom in ('likes','commentaires','partages'):
    AIDES_COLONNES[_nom+'_pour_1000_vues']=f"Nombre de {_nom} divisé par le nombre de vues, multiplié par 1 000. Ce n’est pas un pourcentage. Une valeur manque si les compteurs sont inconnus ou si le nombre de vues est nul."
for _nom in AIDES_INDICATEURS:
    AIDES_COLONNES[_nom+'_duree_s']="Durée des intervalles ayant effectivement contribué à la moyenne de cet indicateur, en secondes. Elle peut différer de celle des autres indicateurs."
