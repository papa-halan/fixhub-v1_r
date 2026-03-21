from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import load_settings


ROOT_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = ROOT_DIR / "alembic.ini"
ALEMBIC_SCRIPT_PATH = ROOT_DIR / "alembic"
DEFAULT_POSTGRES_CONNECT_TIMEOUT = 5


@dataclass(frozen=True)
class DatabaseTarget:
    dialect: str
    host: str
    port: str
    database: str


def resolve_database_url(database_url: str | None = None) -> str:
    return load_settings(database_url=database_url).database_url


def prepare_database_url(database_url: str | None = None) -> str:
    resolved_url = resolve_database_url(database_url)
    parsed_url = make_url(resolved_url)
    if parsed_url.get_backend_name() != "postgresql" or "connect_timeout" in parsed_url.query:
        return resolved_url

    return parsed_url.set(
        query={**parsed_url.query, "connect_timeout": str(DEFAULT_POSTGRES_CONNECT_TIMEOUT)}
    ).render_as_string(hide_password=False)


def describe_database_target(database_url: str | None = None) -> DatabaseTarget:
    parsed_url = make_url(database_url or resolve_database_url())
    dialect = parsed_url.get_backend_name()
    if dialect == "sqlite":
        return DatabaseTarget(
            dialect=dialect,
            host="local",
            port="-",
            database=parsed_url.database or ":memory:",
        )

    return DatabaseTarget(
        dialect=dialect,
        host=parsed_url.host or "-",
        port=str(parsed_url.port) if parsed_url.port is not None else "-",
        database=parsed_url.database or "-",
    )


def database_connection_error_message(
    database_url: str,
    *,
    demo_mode: bool,
) -> str:
    target = describe_database_target(database_url)
    guidance = (
        "Demo mode does not override DATABASE_URL; unset DATABASE_URL to use the default local SQLite database."
        if demo_mode
        else "Start the expected database service or correct DATABASE_URL."
    )
    return (
        "Could not connect to the configured database "
        f"(dialect={target.dialect}, host={target.host}, port={target.port}, "
        f"database={target.database}, demo_mode={demo_mode}). {guidance} "
        "Once the target is reachable, rerun the Alembic command."
    )


def build_engine(database_url: str | None = None) -> Engine:
    url = prepare_database_url(database_url)
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
