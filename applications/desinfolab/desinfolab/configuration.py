"""Configuration explicite, sans secret par défaut."""

import os
from functools import lru_cache
from sqlalchemy import URL


@lru_cache
def url_base() -> str | URL:
    explicite = os.getenv("DATABASE_URL")
    if explicite:
        return explicite
    mot_de_passe = os.getenv("POSTGRES_PASSWORD")
    if not mot_de_passe:
        raise RuntimeError("Configurer DATABASE_URL ou POSTGRES_PASSWORD avant de démarrer.")
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "desinfolab"),
        password=mot_de_passe,
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "desinfolab"),
    )


def secret_application() -> bytes:
    secret = os.getenv("APP_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("APP_SECRET doit contenir au moins 32 caractères aléatoires.")
    return secret.encode()
