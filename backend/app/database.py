# app/database.py
import logging
import time
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

logger = logging.getLogger("senalert")

# DATABASE_URL vient de l'environnement (Secret Kubernetes) : voir config.py.
# Seuls les tests utilisent SQLite.

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Clé arbitraire du verrou PostgreSQL utilisé au démarrage
CLE_VERROU_DEMARRAGE = 727_001


def attendre_base(tentatives: int = 30, delai: float = 2.0) -> None:
    """Attend que la base réponde (sur Kubernetes, le pod peut démarrer avant PostgreSQL)."""
    for essai in range(1, tentatives + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            logger.warning("Base indisponible (essai %s/%s)", essai, tentatives)
            if essai == tentatives:
                raise
            time.sleep(delai)


@contextmanager
def verrou_demarrage():
    """Un seul pod à la fois crée les tables et charge les données de démo.

    Verrou consultatif PostgreSQL : les autres pods attendent, puis trouvent
    les tables et les données déjà en place. Sans effet avec SQLite (tests).
    """
    if engine.dialect.name != "postgresql":
        yield
        return
    with engine.connect() as conn:
        conn.execute(text("SELECT pg_advisory_lock(:cle)"), {"cle": CLE_VERROU_DEMARRAGE})
        try:
            yield
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:cle)"), {"cle": CLE_VERROU_DEMARRAGE})
            conn.commit()
