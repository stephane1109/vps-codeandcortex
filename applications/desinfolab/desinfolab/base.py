"""Sessions transactionnelles partagées par Streamlit et FastAPI."""

from contextlib import contextmanager
from functools import lru_cache
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .configuration import url_base


@lru_cache
def moteur():
    url = url_base()
    sqlite = str(url).startswith("sqlite")
    engine = create_engine(
        url,
        pool_pre_ping=True,
        echo=False,
        hide_parameters=True,
        connect_args={"check_same_thread": False} if sqlite else {},
    )
    if sqlite:

        @event.listens_for(engine, "connect")
        def activer_cles(dbapi, _):
            dbapi.execute("PRAGMA foreign_keys=ON")

    return engine


@contextmanager
def transaction():
    with sessionmaker(moteur(), expire_on_commit=False)() as session:
        with session.begin():
            yield session
