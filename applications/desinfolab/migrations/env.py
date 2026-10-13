"""Migrations exécutées une fois par le service dédié."""

from alembic import context
from sqlalchemy import create_engine, pool
from desinfolab.configuration import url_base
from desinfolab.modeles import Base

if context.is_offline_mode():
    context.configure(
        url=url_base(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    moteur = create_engine(url_base(), poolclass=pool.NullPool)
    with moteur.connect() as connexion:
        context.configure(connection=connexion, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
