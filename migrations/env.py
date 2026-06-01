"""Alembic env.py — reads DATABASE_URL from src.config.Settings (never hardcoded)."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Load settings from src/config.py
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config import settings  # noqa: E402

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url from Settings — never hardcode
# Convert asyncpg URL (postgresql+asyncpg://...) to sync URL for Alembic
db_url = settings.database_url
# If asyncpg driver specified, swap to sync URL for Alembic
if "+asyncpg" in db_url:
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No target_metadata since we use raw SQL in migration (not ORM declarative)
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
