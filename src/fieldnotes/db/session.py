"""Database engine and session helpers."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DATABASE_URL = ""


def get_database_url(default: str = DEFAULT_DATABASE_URL) -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    database_url = (
        os.getenv("DB_ENGINE_URL")
        or os.getenv("FIELDNOTES_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or default
    )
    if not database_url:
        raise RuntimeError(
            "Set DB_ENGINE_URL, FIELDNOTES_DATABASE_URL, or DATABASE_URL before "
            "running database commands."
        )
    return database_url


def sync_database_url(database_url: str) -> str:
    """Use a sync driver for SQLAlchemy CLI/Alembic commands."""

    url = make_url(database_url)
    if url.drivername == "postgresql+asyncpg":
        return url.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        )
    return database_url


def make_engine(database_url: str | None = None, *, echo: bool = False) -> Engine:
    return create_engine(
        sync_database_url(database_url or get_database_url()),
        echo=echo,
        pool_pre_ping=True,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
