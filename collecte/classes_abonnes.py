"""Classes fixes d'audience pour les variables illustratives IRaMuTeQ."""


def classer_nombre_abonnes(nombre):
    """Regrouper l'effectif brut en cinq classes, sans imputer les absences."""
    if isinstance(nombre, bool):
        return "abonnes_indetermine"
    if isinstance(nombre, str):
        nombre = nombre.strip()
        if not nombre.isdecimal():
            return "abonnes_indetermine"
        nombre = int(nombre)
    if not isinstance(nombre, int) or nombre < 0:
        return "abonnes_indetermine"
    if nombre < 1_000:
        return "abonnes_moins_1k"
    if nombre < 10_000:
        return "abonnes_1k_10k"
    if nombre < 100_000:
        return "abonnes_10k_100k"
    if nombre < 1_000_000:
        return "abonnes_100k_1m"
    return "abonnes_plus_1m"
