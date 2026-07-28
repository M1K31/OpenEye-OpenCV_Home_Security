#!/bin/bash
# Start OpenEye Surveillance System

# Run from the internal-disk snapshot, not the script's own location — the
# service must not depend on the repo volume (see install-local.sh).
cd "/Users/mikelsmart/.local/share/openeye/app"

echo "Starting OpenEye Surveillance System..."

# Activate virtual environment (runtime venv lives on the internal disk —
# see opencv_surveillance/scripts/install-local.sh for why).
source "/Users/mikelsmart/.local/share/openeye/venv/bin/activate"

# Load .env into the environment BEFORE importing the app. backend/core/auth.py
# reads SECRET_KEY / JWT_SECRET_KEY at import time, which happens before main.py
# calls load_dotenv(); exporting here guarantees os.getenv() sees them regardless
# of import order (otherwise the app silently falls back to a weak dev secret).
set -a
[ -f .env ] && . ./.env
set +a

# Start server (OpenEye's documented port is 8200; 8000 belongs to AI-for-Survival)
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8200}"
