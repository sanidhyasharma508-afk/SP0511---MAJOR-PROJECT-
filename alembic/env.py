import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure MARVEL-main root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import centralized configuration and declarative metadata
from backend.core.config import settings
from backend.database import Base
import backend.models  # Guarantees all 22 models are imported and registered

config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate and diffing support
target_metadata = Base.metadata


def get_url() -> str:
    """Dynamically fetch the database URL from centralized application settings."""
    # Allow command line or environment override if passed
    url = config.get_main_option("sqlalchemy.url")
    if url:
        from backend.core.config import normalize_database_url
        return normalize_database_url(url)
    return settings.get_normalized_database_url()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well. By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    is_sqlite = url.startswith("sqlite")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=is_sqlite,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    url = get_url()
    is_sqlite = url.startswith("sqlite")

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connect_args = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            if is_sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF;")

            context.run_migrations()

            if is_sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=ON;")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
