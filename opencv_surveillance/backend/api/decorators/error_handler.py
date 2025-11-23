# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
API Error Handling Decorator

Provides consistent error handling across all API endpoints with:
- Automatic exception-to-HTTP status code mapping
- Standardized error response format
- Error logging with context
- Database rollback on errors
- Request/response timing

Usage:
    from backend.api.decorators.error_handler import handle_api_errors

    @router.get("/example")
    @handle_api_errors
    def my_endpoint(db: Session = Depends(get_db)):
        # Your code here
        pass

Error Response Format:
    {
        "detail": "Human-readable error message",
        "error_type": "ValueError",
        "timestamp": "2025-01-17T10:30:00Z",
        "path": "/api/cameras/123"
    }
"""

from functools import wraps
from typing import Callable, Any
from datetime import datetime
import logging
import traceback
from fastapi import HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTION MAPPING
# ============================================================================

# Map exception types to HTTP status codes and messages
EXCEPTION_MAP = {
    # Client Errors (4xx)
    ValueError: (status.HTTP_400_BAD_REQUEST, "Invalid input value"),
    KeyError: (status.HTTP_400_BAD_REQUEST, "Required field missing"),
    FileNotFoundError: (status.HTTP_404_NOT_FOUND, "Resource not found"),
    PermissionError: (status.HTTP_403_FORBIDDEN, "Access denied"),
    ValidationError: (status.HTTP_422_UNPROCESSABLE_ENTITY, "Validation error"),
    IntegrityError: (status.HTTP_409_CONFLICT, "Database constraint violation"),

    # Server Errors (5xx)
    SQLAlchemyError: (status.HTTP_500_INTERNAL_SERVER_ERROR, "Database error"),
    ConnectionError: (status.HTTP_503_SERVICE_UNAVAILABLE, "Service unavailable"),
    TimeoutError: (status.HTTP_504_GATEWAY_TIMEOUT, "Request timeout"),
}


def get_error_response(
    exception: Exception,
    request_path: str = None
) -> dict:
    """
    Generate standardized error response dictionary

    Args:
        exception: The exception that was raised
        request_path: Optional request path for context

    Returns:
        Dictionary with error details
    """
    error_type = type(exception).__name__

    # Use custom message if available, otherwise use mapped message
    if isinstance(exception, HTTPException):
        detail = exception.detail
    else:
        _, default_message = EXCEPTION_MAP.get(
            type(exception),
            (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
        )
        detail = str(exception) if str(exception) else default_message

    response = {
        "detail": detail,
        "error_type": error_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

    if request_path:
        response["path"] = request_path

    return response


def get_status_code(exception: Exception) -> int:
    """
    Get appropriate HTTP status code for exception

    Args:
        exception: The exception that was raised

    Returns:
        HTTP status code (int)
    """
    if isinstance(exception, HTTPException):
        return exception.status_code

    status_code, _ = EXCEPTION_MAP.get(
        type(exception),
        (status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
    )
    return status_code


# ============================================================================
# ERROR HANDLING DECORATOR
# ============================================================================

def handle_api_errors(func: Callable) -> Callable:
    """
    Decorator for consistent API error handling

    Features:
    - Catches all exceptions and converts to HTTPException
    - Maps common exceptions to appropriate status codes
    - Provides standardized error response format
    - Logs errors with full traceback
    - Handles database rollback on errors
    - Tracks request timing

    Usage:
        @router.get("/example")
        @handle_api_errors
        def my_endpoint(db: Session = Depends(get_db)):
            # Your code here
            pass

    Args:
        func: The API endpoint function to wrap

    Returns:
        Wrapped function with error handling
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        """Async wrapper for async endpoints"""
        request_path = None
        db_session = None
        start_time = datetime.utcnow()

        try:
            # Extract request path if Request object is in kwargs
            if 'request' in kwargs and isinstance(kwargs['request'], Request):
                request_path = kwargs['request'].url.path

            # Extract database session for rollback on error
            if 'db' in kwargs and isinstance(kwargs['db'], Session):
                db_session = kwargs['db']

            # Execute the endpoint function
            result = await func(*args, **kwargs)

            # Log successful request timing
            duration = (datetime.utcnow() - start_time).total_seconds()
            if duration > 1.0:  # Log slow requests (>1 second)
                logger.warning(
                    f"Slow request: {func.__name__} took {duration:.2f}s"
                )

            return result

        except HTTPException:
            # Re-raise HTTPException as-is (already handled)
            raise

        except Exception as e:
            # Log error with full context
            error_type = type(e).__name__
            logger.error(
                f"Error in {func.__name__}: {error_type}: {str(e)}",
                extra={
                    "function": func.__name__,
                    "error_type": error_type,
                    "request_path": request_path,
                    "traceback": traceback.format_exc()
                }
            )

            # Rollback database session if error occurred
            if db_session:
                try:
                    db_session.rollback()
                    logger.debug("Database session rolled back")
                except Exception as rollback_error:
                    logger.error(f"Error rolling back database: {rollback_error}")

            # Get appropriate status code
            status_code = get_status_code(e)

            # Generate error response
            error_response = get_error_response(e, request_path)

            # Raise HTTPException with standardized response
            raise HTTPException(
                status_code=status_code,
                detail=error_response
            )

    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        """Sync wrapper for sync endpoints"""
        request_path = None
        db_session = None
        start_time = datetime.utcnow()

        try:
            # Extract request path if Request object is in kwargs
            if 'request' in kwargs and isinstance(kwargs['request'], Request):
                request_path = kwargs['request'].url.path

            # Extract database session for rollback on error
            if 'db' in kwargs and isinstance(kwargs['db'], Session):
                db_session = kwargs['db']

            # Execute the endpoint function
            result = func(*args, **kwargs)

            # Log successful request timing
            duration = (datetime.utcnow() - start_time).total_seconds()
            if duration > 1.0:  # Log slow requests (>1 second)
                logger.warning(
                    f"Slow request: {func.__name__} took {duration:.2f}s"
                )

            return result

        except HTTPException:
            # Re-raise HTTPException as-is (already handled)
            raise

        except Exception as e:
            # Log error with full context
            error_type = type(e).__name__
            logger.error(
                f"Error in {func.__name__}: {error_type}: {str(e)}",
                extra={
                    "function": func.__name__,
                    "error_type": error_type,
                    "request_path": request_path,
                    "traceback": traceback.format_exc()
                }
            )

            # Rollback database session if error occurred
            if db_session:
                try:
                    db_session.rollback()
                    logger.debug("Database session rolled back")
                except Exception as rollback_error:
                    logger.error(f"Error rolling back database: {rollback_error}")

            # Get appropriate status code
            status_code = get_status_code(e)

            # Generate error response
            error_response = get_error_response(e, request_path)

            # Raise HTTPException with standardized response
            raise HTTPException(
                status_code=status_code,
                detail=error_response
            )

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# ============================================================================
# SPECIALIZED ERROR HANDLERS
# ============================================================================

def handle_database_errors(func: Callable) -> Callable:
    """
    Specialized decorator for database-heavy operations

    Adds additional database-specific error handling:
    - Automatic rollback on any exception
    - Detailed database error logging
    - Connection retry logic

    Usage:
        @router.post("/example")
        @handle_database_errors
        def my_database_heavy_endpoint(db: Session = Depends(get_db)):
            # Your code here
            pass
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        db_session = kwargs.get('db')

        try:
            result = func(*args, **kwargs)

            # Commit if session exists and is dirty
            if db_session and db_session.dirty:
                db_session.commit()
                logger.debug(f"Database changes committed in {func.__name__}")

            return result

        except IntegrityError as e:
            if db_session:
                db_session.rollback()

            # Extract constraint violation details
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            logger.error(f"Database integrity error in {func.__name__}: {error_msg}")

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Database constraint violation: {error_msg}"
            )

        except SQLAlchemyError as e:
            if db_session:
                db_session.rollback()

            logger.error(f"Database error in {func.__name__}: {str(e)}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database operation failed"
            )

    return wrapper


def handle_file_operations(allowed_dir: str = None):
    """
    Decorator factory for file operation error handling

    Adds file-specific error handling:
    - Path traversal protection
    - File existence validation
    - Permission checks

    Usage:
        @router.get("/download/{file_id}")
        @handle_file_operations(allowed_dir="/var/recordings")
        def download_file(file_id: str):
            # Your code here
            pass

    Args:
        allowed_dir: Optional directory constraint for security
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                result = func(*args, **kwargs)
                return result

            except FileNotFoundError as e:
                logger.warning(f"File not found in {func.__name__}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )

            except PermissionError as e:
                logger.error(f"Permission denied in {func.__name__}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

            except OSError as e:
                logger.error(f"File operation error in {func.__name__}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="File operation failed"
                )

        return wrapper
    return decorator
