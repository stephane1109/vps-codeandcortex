"""Classes fixes documentées ; aucune imputation des valeurs absentes."""
import math

def discretiser(valeur, bornes, etiquettes):
    if valeur is None or not math.isfinite(valeur): return "indetermine"
    if len(etiquettes) != len(bornes)+1 or sorted(bornes) != list(bornes): raise ValueError("Classes invalides.")
    return etiquettes[sum(valeur >= borne for borne in bornes)]
