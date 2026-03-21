from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import load_settings


ROOT_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = ROOT_DIR / "alembic.ini"
ALEMBIC_SCRIPT_PATH = ROOT_DIR / "alembic"


def build_engine(database_url: str | None = None) -> Engine:
    url = database_url or load_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@lru_cache(maxsize=1)
def alembic_head_revision() -> str:
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    return ScriptDirectory.from_config(config).get_current_head()


def current_database_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            return None
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()


def require_schema_ready(engine: Engine) -> None:
    current_revision = current_database_revision(engine)
    head_revision = alembic_head_revision()
    if current_revision == head_revision:
        return

    current_label = current_revision or "none"
    raise RuntimeError(
        f"Database schema revision {current_label} does not match Alembic head {head_revision}. "
        "Run `alembic upgrade head` before starting the app."
    )


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
