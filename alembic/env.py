import logging
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine.url import make_url
from alembic import context

# Ensure MARVEL-main root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Import centralized configuration, URL utilities, and declarative metadata
from backend.core.config import settings, normalize_database_url, mask_database_url
from backend.database import Base
import backend.models  # Guarantees all 22 models are imported and registered

logger = logging.getLogger("alembic.env")
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate and diffing support
target_metadata = Base.metadata


def get_url() -> str:
    """Dynamically fetch and normalize the database URL from centralized application settings."""
    # Allow command line or programmatic override via config
    raw_url = config.get_main_option("sqlalchemy.url")
    if raw_url and str(raw_url).strip():
        url = str(raw_url).strip()
        # Resolve relative SQLite paths against BASE_DIR
        if url.startswith("sqlite:///./"):
            rel_name = url[len("sqlite:///./") :]
            abs_db_path = (BASE_DIR / rel_name).resolve().as_posix()
            url = f"sqlite:///{abs_db_path}"
        return normalize_database_url(url)

    return settings.get_normalized_database_url()


def get_dialect_info(url: str) -> tuple[str, bool, bool]:
    """Inspect dialect from normalized URL.

    Returns:
        tuple: (dialect_name, is_sqlite, is_postgres)
    """
    parsed = make_url(url)
    dialect = parsed.get_backend_name()
    is_sqlite = dialect == "sqlite"
    is_postgres = dialect == "postgresql"

    if not (is_sqlite or is_postgres):
        raise ValueError(
            f"Unsupported migration database dialect '{dialect}'. "
            "Campus Automation System (MARVEL) supports 'sqlite' and 'postgresql'."
        )

    return dialect, is_sqlite, is_postgres


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates static SQL scripts without establishing a live connection.
    Supports both SQLite and PostgreSQL dialects with masked credential logging.
    """
    url = get_url()
    dialect, is_sqlite, _ = get_dialect_info(url)
    masked = mask_database_url(url)
    logger.info("Running migrations offline for dialect '%s' against %s", dialect, masked)

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

    Configures engine and connection with dialect-specific transaction safety:
    - SQLite: Disables foreign keys outside transaction during batch alterations, restoring them in a finally block.
    - PostgreSQL: Executes within an atomic DDL transaction with Pool cleanup.
    """
    url = get_url()
    dialect, is_sqlite, _ = get_dialect_info(url)
    masked = mask_database_url(url)
    logger.info("Running migrations online for dialect '%s' against %s", dialect, masked)

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

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=is_sqlite,
                compare_type=True,
                compare_server_default=True,
            )

            if is_sqlite:
                connection.exec_driver_sql("PRAGMA foreign_keys=OFF;")

            try:
                with context.begin_transaction():
                    context.run_migrations()
            finally:
                if is_sqlite:
                    connection.exec_driver_sql("PRAGMA foreign_keys=ON;")
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
