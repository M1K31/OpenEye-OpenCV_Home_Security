#!/bin/bash
# Stop OpenEye Surveillance System

echo "Stopping OpenEye Surveillance System..."

# Find and kill the uvicorn process
pkill -f "uvicorn backend.main:app"

echo "OpenEye Surveillance System stopped"
