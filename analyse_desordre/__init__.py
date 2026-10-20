"""Analyse facultative indépendante ; aucun calcul ni import lourd à l'importation."""


def analyser_lot(*arguments, **options):
    """Point d'entrée différé pour une future activation explicite dans l'interface."""
    from .lancement import analyser_lot as executer
    return executer(*arguments, **options)
