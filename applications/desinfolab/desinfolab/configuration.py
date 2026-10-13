"""Configuration explicite, sans secret par défaut ni identifiant dans les erreurs."""

import os
from functools import lru_cache
from sqlalchemy import URL, make_url
from sqlalchemy.exc import ArgumentError


class ErreurConfiguration(RuntimeError):
    """Message contrôlé, affichable au public sans exposer les valeurs saisies."""


@lru_cache
def url_base() -> URL:
    explicite = os.getenv("DATABASE_URL", "").strip()
    if explicite:
        # Accepter aussi une ligne copiée depuis une configuration .env.
        if explicite.startswith("DATABASE_URL="):
            explicite = explicite.removeprefix("DATABASE_URL=").strip()
        try:
            url = make_url(explicite)
        except (ArgumentError, ValueError):
            raise ErreurConfiguration(
                "DATABASE_URL est invalide. Dans Coolify, copiez le champ « Postgres URL (internal) » "
                "de la base dans la valeur de DATABASE_URL, puis redéployez l'application."
            ) from None
        if url.drivername == "sqlite":
            return url  # Moteur des tests locaux uniquement.
        if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
            raise ErreurConfiguration("DATABASE_URL doit être une URL PostgreSQL fournie par Coolify.")
        if (
            not (url.host or url.query.get("host"))
            or not url.database
            or not (url.username or url.query.get("user"))
            or (url.port is not None and not 1 <= url.port <= 65535)
        ):
            raise ErreurConfiguration(
                "DATABASE_URL est incomplète : utilisateur, serveur ou nom de base manquant. "
                "Copiez entièrement « Postgres URL (internal) » depuis votre base Coolify."
            )
        # Coolify fournit postgres:// ou postgresql:// ; notre pilote installé est psycopg 3.
        return url.set(drivername="postgresql+psycopg")
    mot_de_passe = os.getenv("POSTGRES_PASSWORD")
    if not mot_de_passe:
        raise ErreurConfiguration(
            "Connexion à la base non configurée. Dans Coolify → Environment Variables, ajoutez "
            "DATABASE_URL avec le champ « Postgres URL (internal) » de votre base, puis redéployez. "
            "Pour la pile Docker Compose fournie, renseignez POSTGRES_PASSWORD."
        )
    try:
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ErreurConfiguration("POSTGRES_PORT doit être un nombre entre 1 et 65535.") from None
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "desinfolab"),
        password=mot_de_passe,
        host=os.getenv("POSTGRES_HOST", "db"),
        port=port,
        database=os.getenv("POSTGRES_DB", "desinfolab"),
    )


def secret_application() -> bytes:
    secret = os.getenv("APP_SECRET", "")
    if len(secret) < 32:
        raise ErreurConfiguration(
            "APP_SECRET manque ou est trop court. Dans les variables Coolify de l'application, "
            "renseignez une clé aléatoire d'au moins 32 caractères, puis redéployez."
        )
    return secret.encode()
