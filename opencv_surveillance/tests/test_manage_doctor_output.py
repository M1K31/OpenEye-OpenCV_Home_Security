# Copyright (c) 2025-2026 Smart Industries LLC (Mikel Smart)
# This file is part of OpenEye-OpenCV_Home_Security
"""
`manage.py doctor` must not contradict itself.

Its `check()` printed the third argument unconditionally, but every caller
passes text explaining a FAILURE. On a healthy machine that produced:

    [ok  ] port 8200 available — another application holds it

which reads as a failure marked as passing. Someone reading that output to
decide whether the machine is ready cannot tell which half to believe.

Run as a subprocess because manage.py is a standalone CLI — it is not imported
by the application and `check` is a closure inside `cmd_doctor`, so the
observable behaviour is the output itself.
"""

import pathlib
import re
import subprocess
import sys

import pytest

MANAGE = pathlib.Path(__file__).resolve().parents[1] / "manage.py"

# Phrases that only make sense when something is wrong.
FAILURE_ONLY = [
    "another application holds it",
    "create one with:",
    "will fail",
    "do not support",
    "unavailable",
]


@pytest.fixture(scope="module")
def doctor_output():
    result = subprocess.run(
        [sys.executable, str(MANAGE), "doctor"],
        capture_output=True, text=True, cwd=str(MANAGE.parent), timeout=120,
    )
    return result.stdout


def test_doctor_runs(doctor_output):
    assert "Runtime prerequisites:" in doctor_output


def test_no_passing_check_carries_a_failure_explanation(doctor_output):
    offenders = [
        line for line in doctor_output.splitlines()
        if line.strip().startswith("[ok")
        and any(phrase in line for phrase in FAILURE_ONLY)
    ]
    assert not offenders, (
        "a passing check printed text that only applies to a failure:\n"
        + "\n".join(offenders)
    )


def test_failing_checks_still_explain_themselves(doctor_output):
    """
    The fix must not silence the hints — that would trade one bad output for
    a worse one. A FAIL with no reason is not actionable.
    """
    failures = [l for l in doctor_output.splitlines() if l.strip().startswith("[FAIL")]
    if not failures:
        pytest.skip("this machine has no failing prerequisites to check")
    explained = [l for l in failures if "—" in l]
    assert explained, "every failing check printed without any explanation"


def test_the_exit_code_reflects_the_findings():
    """A doctor that always exits 0 cannot be used in a script or CI."""
    result = subprocess.run(
        [sys.executable, str(MANAGE), "doctor"],
        capture_output=True, text=True, cwd=str(MANAGE.parent), timeout=120,
    )
    problems = re.search(r"(\d+) problem\(s\) found", result.stdout)
    if problems and int(problems.group(1)) > 0:
        assert result.returncode != 0, "problems were reported but the exit code was 0"
    else:
        assert result.returncode == 0
