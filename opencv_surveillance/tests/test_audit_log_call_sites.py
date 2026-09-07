# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
Every audit_logger.log_event() call must match the function it calls.

`AuditLogger.log_event` takes `user=`. Seven call sites in
backend/api/routes/users.py passed `username=` instead, which is a TypeError
raised at call time, not at import — so it stayed invisible until the endpoint
actually ran. The affected routes were:

    POST   /token/revoke              (sign out)
    POST   /token/revoke-all          (sign out everywhere)
    PUT    /users/{id}                (update user)
    DELETE /users/{id}                (delete user)
    PATCH  /users/{id}/role           (change role)
    POST   /users/{id}/password       (change password)
    POST   /users/{id}/link-face      (link face profile)

Each logs its audit event AFTER doing the work, so the effect was worse than a
plain failure: the password was changed, or the user deleted, and then the
request returned 500. Callers could not tell a completed action from a failed
one.

This is a static check on purpose. Covering seven endpoints with seven
integration tests would be slower, and would still miss the eighth call site
somebody adds next. Reading the signature and comparing it to every call site
catches the whole class.
"""

import ast
import inspect
import pathlib

import pytest

from backend.core.audit_logger import AuditLogger

BACKEND = pathlib.Path(__file__).resolve().parent.parent / "backend"


def _valid_parameter_names() -> set:
    signature = inspect.signature(AuditLogger.log_event)
    return {p for p in signature.parameters if p != "self"}


def _log_event_keywords():
    """Every (file, line, kwarg) passed to a log_event(...) call in the backend."""
    for path in BACKEND.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:            # not our problem here
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name != "log_event":
                continue
            for kw in node.keywords:
                if kw.arg is not None:
                    yield path.relative_to(BACKEND.parent), node.lineno, kw.arg


def test_log_event_accepts_a_user_parameter():
    """Guard the premise: if the parameter is renamed, this test says so first."""
    assert "user" in _valid_parameter_names()


def test_every_log_event_call_uses_real_parameter_names():
    valid = _valid_parameter_names()
    bad = [
        f"{path}:{line} passes {kwarg}= (valid: {sorted(valid)})"
        for path, line, kwarg in _log_event_keywords()
        if kwarg not in valid
    ]
    assert not bad, "log_event called with parameters it does not accept:\n" + "\n".join(bad)


def test_the_check_actually_finds_call_sites():
    """A scanner that silently matches nothing would pass the test above forever."""
    assert len(list(_log_event_keywords())) > 10
