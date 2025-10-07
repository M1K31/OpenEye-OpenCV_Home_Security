#!/bin/bash

set -e

# Check if API is responding
if curl -f http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Health check passed"
    exit 0
else
    echo "❌ Health check failed"
    exit 1
fi
