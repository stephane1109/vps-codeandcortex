"""Tests de non-régression des statuts du tableau de bord."""

from dashboard_shared.tickets import _statut_application_depuis_compteurs


def test_scraptiktok_occupe_ne_marque_pas_les_autres_applications_occupees():
    """L'occupation d'une application ne doit pas modifier les autres statuts."""
    statuts = {
        "scraptiktok": _statut_application_depuis_compteurs(1, 1, 0),
        "iramuteq-lite": _statut_application_depuis_compteurs(0, 1, 0),
        "iramuteq-lab": _statut_application_depuis_compteurs(0, 1, 0),
        "chdrainette": _statut_application_depuis_compteurs(0, 1, 0),
    }
    assert statuts["scraptiktok"] == ("busy", "Occupée")
    assert all(
        statut == ("available", "Libre")
        for application, statut in statuts.items()
        if application != "scraptiktok"
    )


def test_file_attente_est_propre_a_chaque_application():
    """Une attente dans ScrapTikTok ne doit pas affecter IRaMuTeQ."""
    assert _statut_application_depuis_compteurs(1, 1, 1) == ("queued", "File d'attente")
    assert _statut_application_depuis_compteurs(0, 1, 0) == ("available", "Libre")
