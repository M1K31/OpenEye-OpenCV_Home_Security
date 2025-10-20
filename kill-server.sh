#!/bin/bash

# Copyright (c) 2025 M1K31
# OpenEye Surveillance System - Graceful Shutdown Script
#npm run build
lsof -ti:8000 | xargs kill -9 2>/dev/null || true