# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
A module-level fixture must not silently replace a conftest one.

pytest resolves fixtures by name, nearest first, so a module that defines
`client` gets its own — including whatever wiring the conftest version does and
this one does not. Nothing warns.

That is not hypothetical. tests/api/test_token_refresh_contract.py defined:

    @pytest.fixture
    def client():
        return TestClient(app)

which looks equivalent to conftest's and is not: conftest's installs
dependency_overrides[get_db] so the application talks to the test database, and
clears the startup handlers. Without it the endpoint ran against the real get_db
and failed with

    sqlite3.OperationalError: no such table: refresh_tokens

a message that points at the schema rather than at the fixture. It survived
because of that misdirection.

MODULE-level shadowing is what this catches. A CLASS-scoped override is
different and idiomatic — it is visibly local to the class and reads as
deliberate — so those are allowed.
"""

import ast
import pathlib

import pytest

TESTS = pathlib.Path(__file__).resolve().parent
CONFTEST = TESTS / "conftest.py"

# Intentional module-level overrides, with the reason. Anything not listed here
# is treated as accidental, which is the safer default.
ALLOWED = {
    # (module path relative to tests/, fixture name): why
}


def _is_fixture(node) -> bool:
    for decorator in node.decorator_list:
        if "fixture" in ast.dump(decorator):
            return True
    return False


def _conftest_fixture_names() -> set:
    tree = ast.parse(CONFTEST.read_text())
    return {
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_fixture(node)
    }


def _module_level_fixtures(path: pathlib.Path):
    """Fixtures defined at module scope — not those nested inside a class."""
    tree = ast.parse(path.read_text())
    for node in tree.body:                      # body only: no class members
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_fixture(node):
            yield node.name, node.lineno


def test_conftest_defines_the_shared_fixtures():
    """Guard the premise: if conftest is emptied, the check below passes vacuously."""
    names = _conftest_fixture_names()
    assert {"client", "db_session", "engine"} <= names, (
        f"conftest no longer defines the shared fixtures; found {sorted(names)}"
    )


def test_no_module_shadows_a_conftest_fixture():
    shared = _conftest_fixture_names()
    offenders = []

    for path in sorted(TESTS.rglob("test_*.py")):
        relative = path.relative_to(TESTS)
        for name, line in _module_level_fixtures(path):
            if name in shared and (str(relative), name) not in ALLOWED:
                offenders.append(
                    f"{relative}:{line} redefines '{name}' at module level, "
                    f"replacing conftest's for this whole module"
                )

    assert not offenders, (
        "module-level fixtures shadow conftest:\n  " + "\n  ".join(offenders)
        + "\n\nEither use conftest's, or rename the local one so the difference "
          "is visible at the call site. If the override is deliberate, add it to "
          "ALLOWED in this file with the reason."
    )


def test_the_scanner_actually_finds_fixtures():
    """A scanner matching nothing would pass the test above forever."""
    total = sum(
        1 for path in TESTS.rglob("test_*.py") for _ in _module_level_fixtures(path)
    )
    assert total > 10, f"only {total} module-level fixtures found; the scan looks broken"
