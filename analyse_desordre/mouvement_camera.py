"""Mouvement global dominant par Farnebäck puis similitude robuste RANSAC."""
import cv2
import numpy as np


def distance_histogrammes(a,b):
    """Distance de Bhattacharyya des luminances pour repérer les ruptures franches."""
    histogrammes=[]
    for image in (a,b):
        h=cv2.calcHist([image],[0],None,[32],[0,256]);cv2.normalize(h,h,norm_type=cv2.NORM_L1);histogrammes.append(h)
    return float(cv2.compareHist(*histogrammes,cv2.HISTCMP_BHATTACHARYYA))


def compenser_camera(a,b,intervalle,parametres):
    """Séparer le flux dominant et le flux résiduel ; ne pas supposer une caméra fixe en cas d'échec."""
    if a.shape!=b.shape: return {'statut':'changement_format'}
    if distance_histogrammes(a,b)>parametres.seuil_coupure_histogramme:
        return {'statut':'changement_plan'}
    flux=cv2.calcOpticalFlowFarneback(a,b,None,.5,3,21,3,7,1.5,0)
    h,w=a.shape;yy,xx=np.mgrid[:h,:w].astype(np.float32)
    texture=cv2.cornerMinEigenVal(a,3)>1e-5
    grille=np.zeros(a.shape,bool);grille[4:-4:6,4:-4:6]=True
    selection=grille & texture
    origine=np.column_stack((xx[selection],yy[selection]))
    destination=origine+flux[selection]
    if len(origine)<20: return {'statut':'compensation_indisponible'}
    cv2.setRNGSeed(parametres.graine)
    matrice,accord=cv2.estimateAffinePartial2D(origine,destination,method=cv2.RANSAC,
        ransacReprojThreshold=1.5,maxIters=2000,confidence=.99,refineIters=10)
    if matrice is None: return {'statut':'compensation_indisponible'}
    qx=matrice[0,0]*xx+matrice[0,1]*yy+matrice[0,2]
    qy=matrice[1,0]*xx+matrice[1,1]*yy+matrice[1,2]
    valides=(qx>=2)&(qx<w-2)&(qy>=2)&(qy<h-2)&texture
    if valides.sum()<20: return {'statut':'compensation_indisponible'}
    alignee=cv2.remap(b,qx.astype(np.float32),qy.astype(np.float32),cv2.INTER_LINEAR)
    ecart=float(np.mean(np.abs(a.astype(float)[valides]-alignee[valides]))/255)
    # Une coupure à histogramme similaire reste détectable par l'erreur après alignement.
    source=a.astype(float)[valides];cible=alignee.astype(float)[valides]
    source-=source.mean();cible-=cible.mean()
    norme=np.linalg.norm(source)*np.linalg.norm(cible)
    correlation=float(source@cible/norme) if norme>1e-9 else 1.
    # Des plans différents peuvent partager leur histogramme et un faible contraste.
    # Leur structure disparaît après alignement, contrairement à un simple changement d'exposition.
    if ecart>parametres.seuil_coupure_photometrique or (ecart>parametres.seuil_ecart_structure and correlation<parametres.seuil_rupture_structure):
        return {'statut':'changement_plan'}
    proportion=float(accord.mean())
    # Un mouvement dominant trop peu soutenu ne doit pas être assimilé à la caméra.
    if proportion<.5 or np.linalg.det(matrice[:,:2])<=0:
        return {'statut':'compensation_indisponible'}
    diagonale=np.hypot(w,h)
    global_camera=np.stack((qx-xx,qy-yy),axis=2)
    residuel=flux-global_camera
    # Déplacements des quatre coins : translation, rotation et zoom, normalisés par la diagonale.
    coins=np.array([[0,0],[w-1,0],[0,h-1],[w-1,h-1]],float)
    vitesses=(coins@matrice[:,:2].T+matrice[:,2]-coins)/(diagonale*intervalle)
    return {'statut':'mesure','residuel':residuel,'valides':valides,'vitesses_camera':vitesses,
            'accord_camera':proportion,'erreur_alignement':ecart,'diagonale':diagonale}


def mesurer_instabilite(vitesse, precedente, intervalle_centres):
    """Norme moyenne de l'accélération aux coins, en diagonales d'image/s²."""
    if precedente is None: return None
    return float(np.linalg.norm(vitesse-precedente,axis=1).mean()/intervalle_centres)
