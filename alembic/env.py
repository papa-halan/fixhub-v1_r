from __future__ import annotations

from logging import getLogger
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import load_settings
from app.core.database import (
    database_connection_error_message,
    describe_database_target,
    prepare_database_url,
)
from app.models import Base
import app.models  # noqa: F401


config = context.config
logger = getLogger("alembic.env")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

configured_url = config.get_main_option("sqlalchemy.url")
explicit_database_url = bool(config.attributes.get("database_url_explicit"))
selected_database_url = configured_url if explicit_database_url else None
resolved_database_url = prepare_database_url(selected_database_url)
config.set_main_option("sqlalchemy.url", resolved_database_url)
settings = load_settings(database_url=selected_database_url)
database_target = describe_database_target(resolved_database_url)
database_target_source = "explicit-config" if explicit_database_url else "app-settings"


target_metadata = Base.metadata


def log_database_target(mode: str) -> None:
    logger.info(
        "Alembic %s database target source=%s dialect=%s host=%s port=%s database=%s demo_mode=%s",
        mode,
        database_target_source,
        database_target.dialect,
        database_target.host,
        database_target.port,
        database_target.database,
        settings.demo_mode,
    )


def run_migrations_offline() -> None:
    log_database_target("offline")
    url = resolved_database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    log_database_target("online")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=connection.dialect.name == "sqlite",
            )

            with context.begin_transaction():
                context.run_migrations()
    except SQLAlchemyError as exc:
        raise RuntimeError(
            database_connection_error_message(
                resolved_database_url,
                demo_mode=settings.demo_mode,
            )
        ) from exc


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
