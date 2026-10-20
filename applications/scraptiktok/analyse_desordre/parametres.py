"""Paramètres reproductibles propres à cette analyse, sans dépendance au moteur TikTok."""
from dataclasses import dataclass, asdict
import math


@dataclass(frozen=True)
class Parametres:
    frequence: float = 10.0
    dimension: int = 320
    duree_max: float = 600.0
    seuil_coupure_histogramme: float = .65
    seuil_coupure_photometrique: float = .22
    seuil_rupture_structure: float = .2
    seuil_ecart_structure: float = .06
    seuil_mouvement_pixels: float = .3
    secteurs: int = 12
    permutations: int = 1999
    graine: int = 42

    def __post_init__(self):
        for nom in ('frequence','duree_max','seuil_mouvement_pixels'):
            if not math.isfinite(getattr(self,nom)) or getattr(self,nom)<=0: raise ValueError(f'{nom} doit être positif et fini.')
        if not 1<=self.frequence<=60 or not 64<=self.dimension<=1280: raise ValueError('Fréquence : 1–60 Hz ; dimension : 64–1280 pixels.')
        if not 4<=self.secteurs<=36 or not 99<=self.permutations<=99999: raise ValueError('Secteurs : 4–36 ; permutations : 99–99999.')
        for nom in ('seuil_coupure_histogramme','seuil_coupure_photometrique','seuil_rupture_structure','seuil_ecart_structure'):
            if not 0<getattr(self,nom)<1: raise ValueError(f'{nom} doit être compris entre 0 et 1.')

    def dictionnaire(self):
        return asdict(self)
