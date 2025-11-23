# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for database utility functions
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from backend.database.utils import get_db_context, execute_with_db


class TestGetDbContext:
    """Test get_db_context context manager"""

    @patch('backend.database.utils.SessionLocal')
    def test_get_db_context_success(self, mock_session_local):
        """Test successful database session context"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Use context manager
        with get_db_context() as db:
            assert db == mock_session
            # Simulate using the database
            db.query(Mock).all()

        # Verify session was created and closed
        mock_session_local.assert_called_once()
        mock_session.close.assert_called_once()
        mock_session.rollback.assert_not_called()

    @patch('backend.database.utils.SessionLocal')
    def test_get_db_context_exception_handling(self, mock_session_local):
        """Test context manager handles exceptions properly"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Test exception handling
        test_exception = ValueError("Test database error")

        with pytest.raises(ValueError) as exc_info:
            with get_db_context() as db:
                # Simulate an error during database operation
                raise test_exception

        # Verify exception was propagated
        assert exc_info.value == test_exception

        # Verify rollback was called
        mock_session.rollback.assert_called_once()

        # Verify session was still closed despite exception
        mock_session.close.assert_called_once()

    @patch('backend.database.utils.SessionLocal')
    @patch('backend.database.utils.logger')
    def test_get_db_context_logs_errors(self, mock_logger, mock_session_local):
        """Test context manager logs errors"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Test error logging
        test_error = RuntimeError("Database connection failed")

        with pytest.raises(RuntimeError):
            with get_db_context() as db:
                raise test_error

        # Verify error was logged
        mock_logger.error.assert_called_once()
        log_message = mock_logger.error.call_args[0][0]
        assert "Database session error" in log_message
        assert "Database connection failed" in log_message

    @patch('backend.database.utils.SessionLocal')
    def test_get_db_context_yields_session(self, mock_session_local):
        """Test that context manager yields the correct session"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Test that yielded value is the session
        with get_db_context() as db:
            assert db is mock_session
            assert isinstance(db, MagicMock)

    @patch('backend.database.utils.SessionLocal')
    def test_get_db_context_closes_on_success(self, mock_session_local):
        """Test session is properly closed on successful completion"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Use context manager successfully
        with get_db_context() as db:
            pass  # No operations, just testing closure

        # Verify close was called
        mock_session.close.assert_called_once()

    @patch('backend.database.utils.SessionLocal')
    def test_get_db_context_rollback_on_exception(self, mock_session_local):
        """Test session rollback is called on exception"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_session_local.return_value = mock_session

        # Raise exception in context
        with pytest.raises(Exception):
            with get_db_context() as db:
                raise Exception("Test exception")

        # Verify rollback was called before close
        assert mock_session.rollback.called
        assert mock_session.close.called
        # Rollback should be called before close
        assert mock_session.rollback.call_count == 1
        assert mock_session.close.call_count == 1


class TestExecuteWithDb:
    """Test execute_with_db function"""

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_success(self, mock_get_db_context):
        """Test successful function execution with database"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define test function
        def test_func(db, value):
            return f"Result: {value}"

        # Execute function
        result = execute_with_db(test_func, "test_value")

        # Verify result
        assert result == "Result: test_value"

        # Verify context manager was used
        mock_get_db_context.assert_called_once()

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_with_args(self, mock_get_db_context):
        """Test execute_with_db passes positional arguments correctly"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define test function with multiple args
        def test_func(db, arg1, arg2, arg3):
            return arg1 + arg2 + arg3

        # Execute with positional args
        result = execute_with_db(test_func, 10, 20, 30)

        # Verify result
        assert result == 60

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_with_kwargs(self, mock_get_db_context):
        """Test execute_with_db passes keyword arguments correctly"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define test function with kwargs
        def test_func(db, name="default", age=0):
            return f"{name} is {age} years old"

        # Execute with kwargs
        result = execute_with_db(test_func, name="Alice", age=25)

        # Verify result
        assert result == "Alice is 25 years old"

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_mixed_args(self, mock_get_db_context):
        """Test execute_with_db with both positional and keyword arguments"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define test function
        def test_func(db, pos_arg, kwarg1="default", kwarg2=None):
            return f"{pos_arg}, {kwarg1}, {kwarg2}"

        # Execute with mixed args
        result = execute_with_db(test_func, "positional", kwarg1="keyword", kwarg2="value")

        # Verify result
        assert result == "positional, keyword, value"

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_receives_session(self, mock_get_db_context):
        """Test that function receives database session as first argument"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Track received db argument
        received_db = None

        def test_func(db):
            nonlocal received_db
            received_db = db
            return "success"

        # Execute function
        execute_with_db(test_func)

        # Verify session was passed to function
        assert received_db is mock_session

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_propagates_exceptions(self, mock_get_db_context):
        """Test that exceptions from the function are propagated"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define function that raises exception
        def test_func(db):
            raise ValueError("Function error")

        # Verify exception is propagated
        with pytest.raises(ValueError) as exc_info:
            execute_with_db(test_func)

        assert str(exc_info.value) == "Function error"

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_returns_none(self, mock_get_db_context):
        """Test execute_with_db handles functions that return None"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define function that returns None
        def test_func(db):
            pass  # Implicitly returns None

        # Execute function
        result = execute_with_db(test_func)

        # Verify None is returned
        assert result is None

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_complex_return(self, mock_get_db_context):
        """Test execute_with_db handles complex return values"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define function that returns complex data
        def test_func(db):
            return {
                "users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
                "count": 2,
                "meta": {"page": 1, "total": 2}
            }

        # Execute function
        result = execute_with_db(test_func)

        # Verify complex return value
        assert result["count"] == 2
        assert len(result["users"]) == 2
        assert result["users"][0]["name"] == "Alice"
        assert result["meta"]["total"] == 2

    @patch('backend.database.utils.get_db_context')
    def test_execute_with_db_no_args(self, mock_get_db_context):
        """Test execute_with_db with function that takes only db"""
        # Setup mock session
        mock_session = MagicMock(spec=Session)
        mock_get_db_context.return_value.__enter__.return_value = mock_session

        # Define simple function
        def test_func(db):
            return "called"

        # Execute without additional args
        result = execute_with_db(test_func)

        # Verify execution
        assert result == "called"
        mock_get_db_context.assert_called_once()
