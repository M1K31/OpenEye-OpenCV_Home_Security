# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for SQLAlchemy query profiler middleware
"""

import pytest
import time
from unittest.mock import MagicMock, patch, call
from sqlalchemy.engine import Engine

from backend.middleware.query_profiler import (
    QueryProfiler,
    enable_query_profiling,
    get_query_profiler,
    query_profiler as global_profiler,
)


class TestQueryProfilerInit:
    """Test QueryProfiler initialization"""

    def test_init_default_threshold(self):
        """Test initialization with default threshold"""
        profiler = QueryProfiler()

        assert profiler.slow_query_threshold_ms == 100.0
        assert profiler.enabled is False
        assert profiler.query_count == 0
        assert profiler.total_query_time == 0.0
        assert profiler.slow_queries == []
        assert profiler.max_slow_queries == 100

    def test_init_custom_threshold(self):
        """Test initialization with custom threshold"""
        profiler = QueryProfiler(slow_query_threshold_ms=50.0)

        assert profiler.slow_query_threshold_ms == 50.0
        assert profiler.enabled is False


class TestQueryProfilerEnable:
    """Test QueryProfiler enable functionality"""

    @patch("backend.middleware.query_profiler.event.listens_for")
    def test_enable_registers_listeners(self, mock_listens_for):
        """Test that enable registers SQLAlchemy event listeners"""
        profiler = QueryProfiler()

        # Enable profiling
        profiler.enable()

        # Should register two event listeners
        assert mock_listens_for.call_count == 2

        # Check that listeners were registered for before and after cursor execute
        calls = mock_listens_for.call_args_list
        assert calls[0][0] == (Engine, "before_cursor_execute")
        assert calls[1][0] == (Engine, "after_cursor_execute")

        assert profiler.enabled is True

    @patch("backend.middleware.query_profiler.event.listens_for")
    def test_enable_already_enabled_warning(self, mock_listens_for):
        """Test warning when enabling already enabled profiler"""
        profiler = QueryProfiler()

        # Enable first time
        profiler.enable()

        # Reset mock to check second call
        mock_listens_for.reset_mock()

        # Enable second time - should warn and not re-register
        profiler.enable()

        # Should not register listeners again
        mock_listens_for.assert_not_called()


class TestQueryProfilerEventHandlers:
    """Test query profiling event handlers"""

    @patch("backend.middleware.query_profiler.event.listens_for")
    def test_before_cursor_execute_records_start_time(self, mock_listens_for):
        """Test before_cursor_execute handler records start time"""
        # Capture the handlers that get registered
        registered_handlers = {}

        def mock_decorator(engine, event_name):
            def decorator(func):
                registered_handlers[event_name] = func
                return func
            return decorator

        mock_listens_for.side_effect = mock_decorator

        profiler = QueryProfiler()
        profiler.enable()

        # Get the registered before_cursor_execute handler
        before_handler = registered_handlers["before_cursor_execute"]

        # Create mock connection
        mock_conn = MagicMock()
        mock_conn.info = {}

        # Call the handler
        before_handler(mock_conn, None, "SELECT * FROM users", None, None, False)

        # Check that start time was recorded
        assert 'query_start_time' in mock_conn.info
        assert len(mock_conn.info['query_start_time']) == 1
        assert 'query_statement' in mock_conn.info
        assert mock_conn.info['query_statement'][0] == "SELECT * FROM users"

    @patch("backend.middleware.query_profiler.event.listens_for")
    @patch("backend.middleware.query_profiler.time.time")
    def test_after_cursor_execute_calculates_duration(self, mock_time, mock_listens_for):
        """Test after_cursor_execute handler calculates query duration"""
        # Capture the handlers that get registered
        registered_handlers = {}

        def mock_decorator(engine, event_name):
            def decorator(func):
                registered_handlers[event_name] = func
                return func
            return decorator

        mock_listens_for.side_effect = mock_decorator

        profiler = QueryProfiler(slow_query_threshold_ms=100.0)
        profiler.enable()

        # Get the registered handlers
        before_handler = registered_handlers["before_cursor_execute"]
        after_handler = registered_handlers["after_cursor_execute"]

        # Create mock connection
        mock_conn = MagicMock()
        mock_conn.info = {}

        # Set up time mock - 50ms query
        mock_time.side_effect = [1000.0, 1000.05]  # 50ms difference

        # Simulate query execution
        before_handler(mock_conn, None, "SELECT * FROM users", None, None, False)
        after_handler(mock_conn, None, "SELECT * FROM users", None, None, False)

        # Check statistics updated
        assert profiler.query_count == 1
        assert profiler.total_query_time == pytest.approx(50.0, rel=1e-5)  # 50ms (with float tolerance)

    @patch("backend.middleware.query_profiler.event.listens_for")
    @patch("backend.middleware.query_profiler.time.time")
    def test_after_cursor_execute_logs_slow_query(self, mock_time, mock_listens_for):
        """Test after_cursor_execute handler logs slow queries"""
        # Capture the handlers that get registered
        registered_handlers = {}

        def mock_decorator(engine, event_name):
            def decorator(func):
                registered_handlers[event_name] = func
                return func
            return decorator

        mock_listens_for.side_effect = mock_decorator

        profiler = QueryProfiler(slow_query_threshold_ms=50.0)
        profiler.enable()

        # Get the registered handlers
        before_handler = registered_handlers["before_cursor_execute"]
        after_handler = registered_handlers["after_cursor_execute"]

        # Create mock connection
        mock_conn = MagicMock()
        mock_conn.info = {}

        # Set up time mock - 100ms query (exceeds 50ms threshold)
        # Provide extra values for logging calls
        mock_time.side_effect = [1000.0, 1000.1, 1000.2, 1000.3, 1000.4]  # 100ms difference + extras

        # Simulate slow query execution
        before_handler(mock_conn, None, "SELECT * FROM users WHERE id = 1", {"id": 1}, None, False)
        after_handler(mock_conn, None, "SELECT * FROM users WHERE id = 1", {"id": 1}, None, False)

        # Check slow query was logged
        assert len(profiler.slow_queries) == 1
        assert profiler.slow_queries[0]['duration_ms'] == 100.0
        assert "SELECT * FROM users" in profiler.slow_queries[0]['statement']

    @patch("backend.middleware.query_profiler.event.listens_for")
    def test_after_cursor_execute_no_start_time(self, mock_listens_for):
        """Test after_cursor_execute handler handles missing start time"""
        # Capture the handlers that get registered
        registered_handlers = {}

        def mock_decorator(engine, event_name):
            def decorator(func):
                registered_handlers[event_name] = func
                return func
            return decorator

        mock_listens_for.side_effect = mock_decorator

        profiler = QueryProfiler()
        profiler.enable()

        # Get the registered after handler
        after_handler = registered_handlers["after_cursor_execute"]

        # Create mock connection without query_start_time
        mock_conn = MagicMock()
        mock_conn.info = {}

        # Call handler - should not raise error
        after_handler(mock_conn, None, "SELECT * FROM users", None, None, False)

        # Statistics should not be updated
        assert profiler.query_count == 0


class TestLogSlowQuery:
    """Test _log_slow_query method"""

    def test_log_slow_query_stores_query(self):
        """Test that slow queries are stored"""
        profiler = QueryProfiler()

        profiler._log_slow_query("SELECT * FROM users", 150.5, {"id": 1})

        assert len(profiler.slow_queries) == 1
        assert profiler.slow_queries[0]['duration_ms'] == 150.5
        assert profiler.slow_queries[0]['statement'] == "SELECT * FROM users"
        assert profiler.slow_queries[0]['parameters'] == "{'id': 1}"

    def test_log_slow_query_truncates_long_statement(self):
        """Test that long statements are truncated"""
        profiler = QueryProfiler()

        long_query = "SELECT * FROM users WHERE " + "id = 1 OR " * 100
        profiler._log_slow_query(long_query, 100.0, None)

        assert len(profiler.slow_queries[0]['statement']) <= 503  # 500 + '...'
        assert profiler.slow_queries[0]['statement'].endswith('...')

    def test_log_slow_query_cleans_whitespace(self):
        """Test that whitespace is cleaned from statements"""
        profiler = QueryProfiler()

        query_with_whitespace = "SELECT   *\n  FROM\t\tusers\n  WHERE id = 1"
        profiler._log_slow_query(query_with_whitespace, 100.0, None)

        # Whitespace should be collapsed
        assert '\n' not in profiler.slow_queries[0]['statement']
        assert '\t' not in profiler.slow_queries[0]['statement']

    def test_log_slow_query_limits_stored_queries(self):
        """Test that only max_slow_queries are kept"""
        profiler = QueryProfiler()
        profiler.max_slow_queries = 5

        # Add 10 slow queries
        for i in range(10):
            profiler._log_slow_query(f"SELECT {i}", 100.0, None)

        # Should keep only last 5
        assert len(profiler.slow_queries) == 5
        assert profiler.slow_queries[0]['statement'] == "SELECT 5"
        assert profiler.slow_queries[4]['statement'] == "SELECT 9"

    def test_log_slow_query_truncates_long_parameters(self):
        """Test that long parameter strings are truncated"""
        profiler = QueryProfiler()

        long_params = {"data": "x" * 500}
        profiler._log_slow_query("SELECT * FROM users", 100.0, long_params)

        # Parameters should be truncated to 200 chars
        assert len(profiler.slow_queries[0]['parameters']) <= 200


class TestGetStatistics:
    """Test get_statistics method"""

    def test_get_statistics_initial_state(self):
        """Test statistics for newly initialized profiler"""
        profiler = QueryProfiler(slow_query_threshold_ms=75.0)

        stats = profiler.get_statistics()

        assert stats['enabled'] is False
        assert stats['total_queries'] == 0
        assert stats['total_query_time_ms'] == 0.0
        assert stats['avg_query_time_ms'] == 0.0
        assert stats['slow_query_count'] == 0
        assert stats['slow_query_threshold_ms'] == 75.0

    def test_get_statistics_with_queries(self):
        """Test statistics after some queries"""
        profiler = QueryProfiler()
        profiler.enabled = True
        profiler.query_count = 10
        profiler.total_query_time = 250.5
        profiler.slow_queries = [{'duration_ms': 100}, {'duration_ms': 150}]

        stats = profiler.get_statistics()

        assert stats['enabled'] is True
        assert stats['total_queries'] == 10
        assert stats['total_query_time_ms'] == 250.5
        assert stats['avg_query_time_ms'] == 25.05  # 250.5 / 10
        assert stats['slow_query_count'] == 2


class TestGetSlowQueries:
    """Test get_slow_queries method"""

    def test_get_slow_queries_no_limit(self):
        """Test getting all slow queries"""
        profiler = QueryProfiler()

        # Add some slow queries
        for i in range(5):
            profiler.slow_queries.append({'duration_ms': i * 10, 'statement': f'SELECT {i}'})

        queries = profiler.get_slow_queries()

        assert len(queries) == 5
        assert queries[0]['statement'] == 'SELECT 0'
        assert queries[4]['statement'] == 'SELECT 4'

    def test_get_slow_queries_with_limit(self):
        """Test getting limited number of slow queries"""
        profiler = QueryProfiler()

        # Add 10 slow queries
        for i in range(10):
            profiler.slow_queries.append({'duration_ms': i * 10, 'statement': f'SELECT {i}'})

        queries = profiler.get_slow_queries(limit=3)

        # Should return last 3 queries
        assert len(queries) == 3
        assert queries[0]['statement'] == 'SELECT 7'
        assert queries[2]['statement'] == 'SELECT 9'

    def test_get_slow_queries_returns_copy(self):
        """Test that get_slow_queries returns a copy"""
        profiler = QueryProfiler()
        profiler.slow_queries.append({'duration_ms': 100, 'statement': 'SELECT 1'})

        queries = profiler.get_slow_queries()
        queries.append({'duration_ms': 200, 'statement': 'SELECT 2'})

        # Original should not be modified
        assert len(profiler.slow_queries) == 1


class TestReset:
    """Test reset method"""

    def test_reset_clears_statistics(self):
        """Test that reset clears all statistics"""
        profiler = QueryProfiler()
        profiler.query_count = 100
        profiler.total_query_time = 5000.0
        profiler.slow_queries = [{'duration_ms': 100}] * 10

        profiler.reset()

        assert profiler.query_count == 0
        assert profiler.total_query_time == 0.0
        assert profiler.slow_queries == []


class TestGlobalFunctions:
    """Test global helper functions"""

    def test_get_query_profiler_returns_global(self):
        """Test that get_query_profiler returns the global instance"""
        profiler = get_query_profiler()

        assert profiler is global_profiler
        assert isinstance(profiler, QueryProfiler)

    @patch("backend.middleware.query_profiler.event.listens_for")
    def test_enable_query_profiling_enables_global(self, mock_listens_for):
        """Test that enable_query_profiling enables the global profiler"""
        # Reset global profiler
        global_profiler.enabled = False
        global_profiler.slow_query_threshold_ms = 100.0

        # Enable with custom threshold
        enable_query_profiling(slow_query_threshold_ms=50.0)

        assert global_profiler.slow_query_threshold_ms == 50.0
        assert global_profiler.enabled is True

    @patch("backend.middleware.query_profiler.event.listens_for")
    def test_enable_query_profiling_default_threshold(self, mock_listens_for):
        """Test enable_query_profiling with default threshold"""
        # Reset global profiler
        global_profiler.enabled = False

        enable_query_profiling()

        assert global_profiler.slow_query_threshold_ms == 100.0
        assert global_profiler.enabled is True
