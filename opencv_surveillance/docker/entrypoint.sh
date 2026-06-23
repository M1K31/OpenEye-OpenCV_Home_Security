#!/bin/bash

set -e

# Ensure Python packages are in PATH (using openeye user's home)
export PATH=/home/openeye/.local/bin:$PATH

echo "🚀 Starting OpenEye Surveillance System..."
echo "================================================"

# Wait for database if using PostgreSQL
if [[ "$DATABASE_URL" == postgresql* ]]; then
    echo "⏳ Waiting for PostgreSQL..."
    
    # Extract host and port from DATABASE_URL
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    
    timeout 60 bash -c "until nc -z $DB_HOST ${DB_PORT:-5432}; do sleep 1; done" || echo "⚠️  Could not connect to database"
    echo "✅ PostgreSQL is ready"
fi

# Run database migrations
if [ -f "alembic.ini" ]; then
    echo "🔄 Running database migrations..."
    alembic upgrade head || echo "⚠️  No migrations or alembic not configured"
fi

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
echo "  Database: ${DATABASE_URL%%@*}@***"
echo "  Log Level: ${LOG_LEVEL:-INFO}"
echo "  Workers: ${WORKERS:-1}"
echo "  Face Recognition: ${ENABLE_FACE_RECOGNITION:-true}"
echo "================================================"

echo "✅ OpenEye ready to start"
echo ""

# Execute the main command
exec "$@"
