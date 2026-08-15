import logging
from logging.config import fileConfig
import sys
import os
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import all models to ensure they're registered with SQLAlchemy
from backend.database.session import Base, SQLALCHEMY_DATABASE_URL
from backend.database.models import (
    User,
    FaceDetectionEvent,
    FaceCluster,
    RecordingEvent,
    Camera,
    MotionDetectionEvent,
    SystemLog,
    SystemSettings,
    AutomationRule
)
from backend.database.alert_models import AlertConfiguration, NotificationLog, AlertThrottle

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set the database URL from our session configuration
config.set_main_option('sqlalchemy.url', SQLALCHEMY_DATABASE_URL)

# Interpret the config file for Python logging — but only when nothing has
# configured logging already.
#
# Migrations run IN-PROCESS at application startup (main.py -> command.upgrade),
# and fileConfig does more than enable loggers: it REPLACES the root logger's
# handlers with the ones named in alembic.ini, which is a console handler. An
# earlier fix passed disable_existing_loggers=False, and that was necessary but
# not sufficient — the app's loggers stayed alive while the file handler they
# wrote through was thrown away.
#
# In the packaged application the effect was total: the log file stopped at
# "Running database migrations..." and every later line — camera startup, the
# storage layout, errors — went to a stderr that a Finder-launched bundle has
# nowhere to put. The server looked like it had hung immediately after starting.
#
# So: if the application has already set up logging, leave it alone. When
# alembic is run from the command line the root logger has no handlers and this
# configures them as usual.
if config.config_file_name is not None and not logging.getLogger().handlers:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Enable batch mode for SQLite to support ALTER operations
            render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
