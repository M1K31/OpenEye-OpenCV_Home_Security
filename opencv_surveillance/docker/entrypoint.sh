#!/bin/bash

# -e: stop on a failed command.
# -u: an unset variable is an error, not an empty string. This script builds a
#     DATABASE_URL and a host/port from the environment; without -u a missing
#     one expands to nothing and the failure surfaces later, somewhere else.
# -o pipefail: a pipeline fails if ANY stage fails, not just the last. The
#     PostgreSQL wait below pipes through sed, which succeeds happily on empty
#     input, so without this a failed extraction looked like a successful one.
set -euo pipefail

# Ensure Python packages are in PATH (using openeye user's home)
export PATH=/home/openeye/.local/bin:$PATH

echo "🚀 Starting OpenEye Surveillance System..."
echo "================================================"

# Wait for database if using PostgreSQL
# Guarded because of `set -u` above. Running the image without compose
# leaves DATABASE_URL unset, and the application defaults to SQLite — an
# unguarded reference here would turn a supported way of starting the
# container into an immediate failure.
if [[ "${DATABASE_URL:-}" == postgresql* ]]; then
    echo "⏳ Waiting for PostgreSQL..."
    
    # Extract host and port from DATABASE_URL
    DB_HOST=$(echo "${DATABASE_URL:-}" | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo "${DATABASE_URL:-}" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    
    timeout 60 bash -c "until nc -z $DB_HOST ${DB_PORT:-5432}; do sleep 1; done" || echo "⚠️  Could not connect to database"
    echo "✅ PostgreSQL is ready"
fi

# Migrations are the application's job, not this script's.
#
# This used to run `alembic upgrade head` here. It was harmless only because
# alembic.ini was never copied into the image, so the block never ran. Once the
# migrations were shipped it started failing on every fresh container:
#
#     sqlalchemy.exc.NoSuchTableError: cameras
#
# No migration creates the base tables. They come from create_all(), and the
# chain only adds increments on top, so running it first against an empty
# database can only fail. backend/main.py already does this in the right order —
# create the tables, then stamp alembic_version on a fresh database so the chain
# starts from the right place — and says so at length. Doing it here as well,
# earlier and without that care, could only undo it.

# Create directories (may fail if volumes are mounted without correct permissions)
echo "📁 Creating data directories..."
if ! mkdir -p /app/data/recordings /app/data/faces /app/data/logs 2>/dev/null; then
    echo "⚠️  Warning: Could not create data subdirectories"
    echo "    This usually means the mounted volumes are owned by root."
    echo ""
    echo "    To fix, run on your host machine:"
    echo "      sudo chown -R 1000:1000 ./data ./recordings ./faces ./models"
    echo ""
    echo "    Or use: docker compose down && docker compose up"
    echo "    (the init-permissions service will fix this automatically)"
fi
mkdir -p /app/models /app/config 2>/dev/null || true

# Set permissions check
if [ -w "/app/data" ]; then
    echo "✅ Data directory is writable"
else
    echo "⚠️  Warning: Data directory is not writable - see instructions above"
fi

# Display configuration
echo "================================================"
echo "Configuration:"
echo "  Database: ${DATABASE_URL:-sqlite (default)}"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo "  Workers: ${WORKERS:-1}"
echo "  Face Recognition: ${ENABLE_FACE_RECOGNITION:-true}"
echo "================================================"

echo "✅ OpenEye ready to start"
echo ""

# Execute the main command
exec "$@"
