"""Variation temporelle du mouvement résiduel, calculée à l'intérieur de chaque plan."""


def mesurer_irregularite(vitesse, precedente):
    """Différence relative symétrique, comprise entre zéro et un ; silence stable = zéro."""
    if precedente is None: return None
    return abs(vitesse-precedente)/(abs(vitesse)+abs(precedente)+1e-12)
