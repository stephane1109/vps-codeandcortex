"""Entropie directionnelle des mouvements après compensation globale."""
import numpy as np


def mesurer_mouvements(residuel,valides,diagonale,intervalle,parametres):
    """Entropie pondérée par les amplitudes ; ignorer les flux sous le plancher de bruit."""
    amplitudes=np.linalg.norm(residuel,axis=2)
    actifs=valides & (amplitudes>=parametres.seuil_mouvement_pixels)
    vitesse=float(np.where(actifs,amplitudes,0)[valides].mean()/diagonale/intervalle)
    proportion=float(actifs.sum()/valides.sum())
    if not actifs.any(): return {'entropie_directionnelle':0.,'vitesse_residuelle':0.,'fraction_mobile':0.}
    angles=np.mod(np.arctan2(residuel[:,:,1][actifs],residuel[:,:,0][actifs]),2*np.pi)
    poids,_=np.histogram(angles,bins=parametres.secteurs,range=(0,2*np.pi),weights=amplitudes[actifs])
    probabilites=poids[poids>0]/poids.sum()
    entropie=float(-(probabilites*np.log(probabilites)).sum()/np.log(parametres.secteurs))
    return {'entropie_directionnelle':entropie,'vitesse_residuelle':vitesse,'fraction_mobile':proportion}
