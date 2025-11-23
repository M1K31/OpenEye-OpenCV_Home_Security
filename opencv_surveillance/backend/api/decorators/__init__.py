# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API Decorators Module

Provides reusable decorators for API endpoints:
- Error handling with consistent responses
- Request timing and logging
- Database transaction management
- File operation security
"""

from .error_handler import (
    handle_api_errors,
    handle_database_errors,
    handle_file_operations,
)

__all__ = [
    "handle_api_errors",
    "handle_database_errors",
    "handle_file_operations",
]
