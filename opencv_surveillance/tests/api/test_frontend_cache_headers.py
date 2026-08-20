# Copyright (c) 2025 Mikel Smart
# This file is part of OpenEye-OpenCV_Home_Security

"""
Tests for the cache headers on the served frontend.

After an update, a browser holding the previous index.html asks for JavaScript
chunks whose filenames carry the PREVIOUS build's content hash. Those files are
gone, so every route fails to load with a 404 and the application appears
broken on a machine where nothing is actually wrong:

    GET /assets/FaceManagementPage-BiamIRFX.js   404
    GET /assets/RecordingsPage-BzS5--6B.js       404

FileResponse sets an ETag but no Cache-Control, which leaves the choice to the
browser's heuristic caching — and the heuristic is to reuse. The rule these
tests defend is the asymmetry:

    index.html      names the others, must always be revalidated
    /assets/*       content-hashed, safe to keep indefinitely

Getting this backwards in either direction is a bug. Caching index.html strands
clients on dead URLs; revalidating every asset throws away the entire benefit
of hashing them in the first place.
"""

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


class TestIndexIsAlwaysRevalidated:
    def test_root_is_not_cacheable_without_revalidation(self, client):
        response = client.get("/")

        if response.status_code == 404:
            pytest.skip("frontend not built in this checkout")

        cache_control = response.headers.get("Cache-Control", "")
        assert "no-cache" in cache_control, (
            "index.html may be reused without revalidation, which strands "
            "browsers on chunk URLs deleted by the next build"
        )

    def test_an_spa_route_is_not_cacheable_either(self, client):
        """
        The catch-all serves the same index.html. A user who reloads on
        /faces rather than / must not get a cacheable copy.
        """
        response = client.get("/faces")

        if response.status_code == 404:
            pytest.skip("frontend not built in this checkout")

        assert "no-cache" in response.headers.get("Cache-Control", "")

    def test_revalidation_stays_cheap(self, client):
        """
        no-cache means revalidate, not re-download. Without a validator every
        reload would transfer the whole document.
        """
        response = client.get("/")

        if response.status_code == 404:
            pytest.skip("frontend not built in this checkout")

        assert response.headers.get("ETag") or response.headers.get("Last-Modified")


class TestHashedAssetsAreKept:
    def test_an_asset_is_cacheable_for_a_long_time(self, client):
        from pathlib import Path
        from backend import main

        assets = Path(main.__file__).parent.parent / "frontend" / "dist" / "assets"
        if not assets.is_dir():
            pytest.skip("frontend not built in this checkout")

        some_asset = next((p for p in assets.iterdir() if p.suffix == ".js"), None)
        if some_asset is None:
            pytest.skip("no javascript assets in this build")

        response = client.get(f"/assets/{some_asset.name}")
        assert response.status_code == 200

        cache_control = response.headers.get("Cache-Control", "")
        assert "max-age=" in cache_control
        assert "immutable" in cache_control

    def test_the_header_is_not_applied_to_api_responses(self, client):
        """
        The middleware matches on a path prefix. An API response must never be
        marked immutable — it is the one thing that genuinely does change.
        """
        response = client.get("/api/health")

        assert "immutable" not in response.headers.get("Cache-Control", "")
