# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Unit tests for security middleware
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import Request, HTTPException, FastAPI

from backend.middleware.security import (
    SecurityHeadersMiddleware,
    IPWhitelistMiddleware,
    SQLInjectionProtection,
)


class TestSecurityHeadersMiddleware:
    """Test SecurityHeadersMiddleware"""

    def setup_method(self):
        """Create middleware instance for tests"""
        app = FastAPI()
        self.middleware = SecurityHeadersMiddleware(app)

    @pytest.mark.asyncio
    async def test_dispatch_adds_security_headers(self):
        """Test that all security headers are added to response"""
        # Mock request
        mock_request = MagicMock(spec=Request)

        # Mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        # Dispatch request
        response = await self.middleware.dispatch(mock_request, call_next)

        # Verify all security headers are present
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        assert "Strict-Transport-Security" in response.headers
        assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
        assert "includeSubDomains" in response.headers["Strict-Transport-Security"]

        assert "Content-Security-Policy" in response.headers
        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "img-src 'self' data:" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp
        assert "script-src 'self'" in csp

        # Verify call_next was called
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_preserves_existing_headers(self):
        """Test that existing response headers are preserved"""
        # Mock request
        mock_request = MagicMock(spec=Request)

        # Mock response with existing headers
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/json"}
        call_next = AsyncMock(return_value=mock_response)

        # Dispatch request
        response = await self.middleware.dispatch(mock_request, call_next)

        # Verify existing header preserved
        assert response.headers["Content-Type"] == "application/json"

        # Verify security headers added
        assert "X-Content-Type-Options" in response.headers


class TestIPWhitelistMiddleware:
    """Test IPWhitelistMiddleware"""

    def test_init_disabled_no_ips(self):
        """Test initialization with no IPs (disabled)"""
        app = FastAPI()
        middleware = IPWhitelistMiddleware(app)

        assert middleware.allowed_ips == []
        assert middleware.enabled is False

    def test_init_disabled_empty_list(self):
        """Test initialization with empty list (disabled)"""
        app = FastAPI()
        middleware = IPWhitelistMiddleware(app, allowed_ips=[])

        assert middleware.allowed_ips == []
        assert middleware.enabled is False

    def test_init_enabled_with_ips(self):
        """Test initialization with IPs (enabled)"""
        app = FastAPI()
        allowed_ips = ["192.168.1.100", "10.0.0.1"]
        middleware = IPWhitelistMiddleware(app, allowed_ips=allowed_ips)

        assert middleware.allowed_ips == allowed_ips
        assert middleware.enabled is True

    @pytest.mark.asyncio
    async def test_dispatch_disabled_allows_all(self):
        """Test that disabled whitelist allows all IPs"""
        app = FastAPI()
        middleware = IPWhitelistMiddleware(app)  # No IPs = disabled

        # Mock request from any IP
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "1.2.3.4"

        # Mock call_next
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        # Should allow request through
        response = await middleware.dispatch(mock_request, call_next)

        assert response == mock_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_enabled_whitelisted_ip(self):
        """Test that whitelisted IP is allowed"""
        app = FastAPI()
        allowed_ips = ["192.168.1.100", "10.0.0.1"]
        middleware = IPWhitelistMiddleware(app, allowed_ips=allowed_ips)

        # Mock request from whitelisted IP
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "192.168.1.100"

        # Mock call_next
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        # Should allow request through
        response = await middleware.dispatch(mock_request, call_next)

        assert response == mock_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_enabled_non_whitelisted_ip(self):
        """Test that non-whitelisted IP is blocked"""
        app = FastAPI()
        allowed_ips = ["192.168.1.100", "10.0.0.1"]
        middleware = IPWhitelistMiddleware(app, allowed_ips=allowed_ips)

        # Mock request from non-whitelisted IP
        mock_request = MagicMock(spec=Request)
        mock_request.client.host = "1.2.3.4"

        # Mock call_next
        call_next = AsyncMock()

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, call_next)

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail
        assert "IP not whitelisted" in exc_info.value.detail

        # call_next should NOT be called
        call_next.assert_not_called()


class TestSQLInjectionProtection:
    """Test SQLInjectionProtection"""

    def setup_method(self):
        """Create middleware instance for tests"""
        app = FastAPI()
        self.middleware = SQLInjectionProtection(app)

    def test_init_compiles_patterns(self):
        """Test initialization compiles regex patterns"""
        assert len(self.middleware.patterns) == len(
            SQLInjectionProtection.SQL_INJECTION_PATTERNS
        )
        assert all(hasattr(p, "search") for p in self.middleware.patterns)

    def test_check_sql_injection_clean_string(self):
        """Test check_sql_injection with clean string"""
        clean_strings = [
            "camera123",
            "John Doe",
            "2024-01-15",
            "test@example.com",
            "192.168.1.1",
        ]

        for s in clean_strings:
            assert self.middleware.check_sql_injection(s) is False

    def test_check_sql_injection_union_select(self):
        """Test detection of UNION SELECT attack"""
        attacks = [
            "1 UNION SELECT * FROM users",
            "test' UNION SELECT password FROM accounts--",
            "id=1 union select null,null,null",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_select_from(self):
        """Test detection of SELECT FROM attack"""
        attacks = [
            "SELECT * FROM users",
            "1' AND SELECT password FROM accounts",
            "test; select * from cameras",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_insert_into(self):
        """Test detection of INSERT INTO attack"""
        attacks = [
            "INSERT INTO users VALUES ('admin', 'pass')",
            "test'; INSERT INTO cameras (name) VALUES ('hacked')--",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_delete_from(self):
        """Test detection of DELETE FROM attack"""
        attacks = [
            "DELETE FROM users",
            "test'; DELETE FROM cameras WHERE 1=1--",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_drop_table(self):
        """Test detection of DROP TABLE attack"""
        attacks = [
            "DROP TABLE users",
            "test'; DROP TABLE cameras--",
            "id=1; drop table recordings",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_comment_injection(self):
        """Test detection of SQL comment injection"""
        attacks = [
            "admin'--",
            "test' # comment",
            "id=1 /* comment */ OR 1=1",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_or_attack(self):
        """Test detection of OR = attack"""
        attacks = [
            "1' OR '1'='1",
            "admin' OR 1=1--",
            "test OR 2=2",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    def test_check_sql_injection_and_attack(self):
        """Test detection of AND = attack"""
        attacks = [
            "1' AND '1'='1",
            "admin' AND 1=1--",
            "test AND 2=2",
        ]

        for attack in attacks:
            assert self.middleware.check_sql_injection(attack) is True

    @pytest.mark.asyncio
    async def test_dispatch_clean_query_params(self):
        """Test dispatch with clean query parameters"""
        # Mock request with clean query params
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"camera_id": "cam1", "limit": "10"}
        mock_request.url.path = "/api/cameras/"

        # Mock call_next
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        # Should allow request through
        response = await self.middleware.dispatch(mock_request, call_next)

        assert response == mock_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_sql_injection_in_query_params(self):
        """Test dispatch with SQL injection in query parameters"""
        # Mock request with SQL injection in query params
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {"camera_id": "1' OR '1'='1", "limit": "10"}
        mock_request.url.path = "/api/cameras/"

        # Mock call_next
        call_next = AsyncMock()

        # Returns a 400 response (raising inside BaseHTTPMiddleware would 500)
        response = await self.middleware.dispatch(mock_request, call_next)
        assert response.status_code == 400


        # call_next should NOT be called
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_sql_injection_in_multiple_query_params(self):
        """Test dispatch checks all query parameters"""
        # Mock request with SQL injection in second param
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {
            "camera_id": "cam1",
            "search": "test' UNION SELECT * FROM users--",
        }
        mock_request.url.path = "/api/cameras/"

        # Mock call_next
        call_next = AsyncMock()

        # Returns a 400 response (raising inside BaseHTTPMiddleware would 500)
        response = await self.middleware.dispatch(mock_request, call_next)
        assert response.status_code == 400

        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_clean_path(self):
        """Test dispatch with clean path"""
        # Mock request with clean path
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.url.path = "/api/cameras/cam1/stream"

        # Mock call_next
        mock_response = MagicMock()
        call_next = AsyncMock(return_value=mock_response)

        # Should allow request through
        response = await self.middleware.dispatch(mock_request, call_next)

        assert response == mock_response
        call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_dispatch_sql_injection_in_path(self):
        """Test dispatch with SQL injection in path"""
        # Mock request with SQL injection in path
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.url.path = "/api/cameras/1' OR '1'='1/stream"

        # Mock call_next
        call_next = AsyncMock()

        # Returns a 400 response (raising inside BaseHTTPMiddleware would 500)
        response = await self.middleware.dispatch(mock_request, call_next)
        assert response.status_code == 400


        # call_next should NOT be called
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_sql_injection_drop_table_in_path(self):
        """Test dispatch with DROP TABLE in path"""
        # Mock request with DROP TABLE in path
        mock_request = MagicMock(spec=Request)
        mock_request.query_params = {}
        mock_request.url.path = "/api/cameras/test; DROP TABLE cameras--"

        # Mock call_next
        call_next = AsyncMock()

        # Returns a 400 response (raising inside BaseHTTPMiddleware would 500)
        response = await self.middleware.dispatch(mock_request, call_next)
        assert response.status_code == 400

        call_next.assert_not_called()


class TestSQLInjectionStaticAssets:
    """Hashed build artifacts (Vite chunks like 'TwoFactorSettings--CHBeorH.js')
    contain SQL comment tokens; the path heuristic must not block static mounts,
    and rejections must be real 400s (not HTTPException-in-middleware 500s)."""

    def _app(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.add_middleware(SQLInjectionProtection)

        @app.get("/assets/{name}")
        async def asset(name: str):
            return {"served": name}

        @app.get("/api/echo")
        async def echo(q: str = ""):
            return {"q": q}

        return TestClient(app, raise_server_exceptions=False)

    def test_double_dash_asset_is_served(self):
        client = self._app()
        r = client.get("/assets/TwoFactorSettings--CHBeorH.js")
        assert r.status_code == 200
        assert r.json()["served"] == "TwoFactorSettings--CHBeorH.js"

    def test_query_param_injection_still_rejected_as_400(self):
        client = self._app()
        r = client.get("/api/echo", params={"q": "1 UNION SELECT * FROM users"})
        assert r.status_code == 400  # not 500

    def test_non_static_path_injection_still_rejected_as_400(self):
        client = self._app()
        r = client.get("/api/thing--comment")
        assert r.status_code == 400  # heuristics still apply off the static mounts
