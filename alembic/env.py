from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import sys
import os

# -------------------------------------------------------------
# Step 1: Fix Python path so 'app' can be imported
# -------------------------------------------------------------
# Alembic is in ai-video-course-generator/alembic
# 'app' folder is one level above alembic/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# -------------------------------------------------------------
# Step 2: Import your SQLAlchemy Base and models
# -------------------------------------------------------------
try:
    from app.db.database import Base  # Your declarative Base
    import app.db.model  # Ensure all models are loaded so metadata is populated
except ImportError as e:
    print(f"ERROR importing models: {e}")
    raise

# -------------------------------------------------------------
# Step 3: Alembic configuration
# -------------------------------------------------------------
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata
print(f"DEBUG: Tables available for Alembic: {list(target_metadata.tables.keys())}")

# -------------------------------------------------------------
# Step 4: Migration functions
# -------------------------------------------------------------
def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,  # This is critical!
        )

        with context.begin_transaction():
            context.run_migrations()


# -------------------------------------------------------------
# Step 5: Run the proper migration mode
# -------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
