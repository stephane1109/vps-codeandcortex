"""Identité binaire SHA-256 et signature perceptuelle DCT de 63 bits."""
import hashlib

def calculer_sha256(chemin):
    empreinte = hashlib.sha256()
    with open(chemin,"rb") as flux:
        for bloc in iter(lambda: flux.read(1024*1024),b""): empreinte.update(bloc)
    return empreinte.hexdigest()

def calculer_phash(image):
    import cv2
    import numpy as np
    gris = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    coefficients = cv2.dct(cv2.resize(gris,(32,32)).astype(np.float32))[:8,:8].flatten()[1:]
    mediane = float(np.median(coefficients)); nombre = 0
    for bit in coefficients > mediane: nombre = (nombre << 1) | int(bit)
    return f"{nombre:016x}"

def distance_phash(a,b):
    return (int(a,16)^int(b,16)).bit_count()
