"""Indice descriptif exploratoire à échelles fixes, indépendant du corpus comparé."""
import numpy as np

INDICATEURS=('instabilite_camera','entropie_directionnelle','irregularite_temporelle','vitesse_residuelle','indice_desordre')


def calculer_indice(instabilite,entropie,irregularite,vitesse):
    """Moyenne de trois composantes bornées ; poids égaux, non calibrés sur les engagements."""
    if instabilite is None or irregularite is None: return None
    camera=instabilite/(instabilite+.05)
    # Une entropie élevée sur un mouvement très faible ne doit pas dominer l'indice.
    directions=entropie*vitesse/(vitesse+.01)
    return 100*(camera+directions+irregularite)/3


def resumer_mesures(lignes):
    """Pondérer par la durée observée, sans intégrer les coupures ni combler les inconnues."""
    resultat={}
    for nom in INDICATEURS:
        presentes=[r for r in lignes if r.get(nom) is not None and np.isfinite(r[nom])]
        resultat[nom]=float(np.average([r[nom] for r in presentes],weights=[r['intervalle_s'] for r in presentes])) if presentes else None
        resultat[nom+'_duree_s']=sum(r['intervalle_s'] for r in presentes)
    return resultat
