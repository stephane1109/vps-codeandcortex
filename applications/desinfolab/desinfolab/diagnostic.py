"""Diagnostics publics limités à des messages fixes, sans URL ni requête SQL."""

from sqlalchemy.exc import OperationalError


def diagnostic_base(erreur):
    origine = getattr(erreur, "orig", None)
    code = getattr(origine, "sqlstate", None)
    if code in {"42P01", "42703"} or (
        origine is not None
        and origine.__class__.__module__ == "sqlite3"
        and "no such table" in str(origine).lower()
    ):
        return (
            "Les tables de DésinfoLab sont absentes ou ne sont pas à jour. "
            "Dans le terminal du conteneur de l'application, exécutez : "
            "cd /app && alembic upgrade head. Avec Docker Compose, vérifiez les logs du service migrations."
        )
    if code in {"28P01", "28000"}:
        return (
            "PostgreSQL refuse les identifiants. Vérifiez la valeur DATABASE_URL dans Coolify "
            "à partir du champ « Postgres URL (internal) » de la base, puis redéployez l'application."
        )
    if code == "3D000":
        return (
            "Le serveur PostgreSQL répond, mais la base demandée n'existe pas. "
            "Vérifiez « Initial Database » et l'URL interne de la ressource PostgreSQL dans Coolify."
        )
    if isinstance(erreur, OperationalError):
        return (
            "Connexion à PostgreSQL impossible. Vérifiez que la base est démarrée (Running / Healthy), "
            "que DATABASE_URL correspond à son URL interne et que la base et l'application "
            "partagent le même réseau Coolify."
        )
    return "Une opération sur la base a échoué. Actualisez la page ; si l'erreur persiste, consultez les logs du service web."
