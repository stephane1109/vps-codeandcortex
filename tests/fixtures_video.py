"""Vidéos artificielles déterministes ; aucun accès à TikTok."""
try:
    import cv2
    import numpy as np
    VIDEO = True
except ImportError:
    VIDEO = False

def image_test(graine=1):
    aleatoire=np.random.default_rng(graine)
    image=np.zeros((240,320,3),dtype=np.uint8)
    for _ in range(120):
        x,y=aleatoire.integers([0,0],[320,240]); couleur=tuple(int(v) for v in aleatoire.integers(40,255,3))
        cv2.circle(image,(int(x),int(y)),int(aleatoire.integers(2,12)),couleur,-1)
    return image

def ecrire_video(chemin, graines=(1,2,3,4,5), recadrer=False):
    sortie=cv2.VideoWriter(str(chemin),cv2.VideoWriter_fourcc(*"mp4v"),5,(320,240))
    assert sortie.isOpened()
    for graine in graines:
        image=image_test(graine)
        if recadrer: image=cv2.resize(image[12:228,16:304],(320,240))
        for _ in range(5): sortie.write(image)
    sortie.release()
