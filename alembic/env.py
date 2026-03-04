import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ----------------------------------------------------------------------
# 1. IMPORTS FROM YOUR PROJECT
# ----------------------------------------------------------------------
import sys
import os

# Add the project root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the shared Base and Config
from aetherium_gallery.core.database import Base, settings

# Import ALL models so they are registered with Base.metadata
# (Alembic needs to see these to generate migrations)
from aetherium_gallery.features.images.models import Image, VideoSource
from aetherium_gallery.features.albums.models import Album
from aetherium_gallery.features.tags.models import Tag
# ----------------------------------------------------------------------

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ----------------------------------------------------------------------
# 2. SET METADATA & URL
# ----------------------------------------------------------------------
target_metadata = Base.metadata

# Overwrite the sqlalchemy.url in alembic.ini with the one from your settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
# ----------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode (Async)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())