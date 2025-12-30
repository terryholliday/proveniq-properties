"""Alembic environment configuration - SYNC MODE for migrations."""

from logging.config import fileConfig
import os
from pathlib import Path

# Load .env FIRST before anything else
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

from sqlalchemy import pool, create_engine
from sqlalchemy import MetaData

from alembic import context

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Create metadata without importing async models
target_metadata = MetaData()


def get_url():
    """Get database URL from environment."""
    url = os.getenv("DATABASE_URL", "")
    # Force sync driver for Alembic
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    print(f"[DEBUG] Using DB URL: {url[:50]}...")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with SYNC engine."""
    url = get_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
