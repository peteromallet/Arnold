"""Subprocess-based import-isolation test for vibecomfy.security.

Verifies that importing ``vibecomfy.security`` does NOT transitively pull
``vibecomfy.analysis``, ``vibecomfy.runtime``, ``vibecomfy.porting``, or
``vibecomfy.registry`` into ``sys.modules``.

This is enforced via a fresh subprocess ``python -c "..."`` to avoid
any contamination from the test runner's own ``sys.modules``.
"""

from __future__ import annotations

import subprocess
import sys


# Modules that MUST NOT appear in sys.modules after importing vibecomfy.security
FORBIDDEN_MODULES: list[str] = [
    "vibecomfy.analysis",
    "vibecomfy.runtime",
    "vibecomfy.porting",
    "vibecomfy.registry",
]


def test_security_import_isolation() -> None:
    """Fresh subprocess: import vibecomfy.security, then check sys.modules."""
    forbidden_set = "{" + ", ".join(repr(m) for m in FORBIDDEN_MODULES) + "}"
    check_script = (
        "import sys\n"
        "import vibecomfy.security\n"
        f"forbidden = {forbidden_set}\n"
        "found = sorted(forbidden & set(sys.modules))\n"
        "if found:\n"
        "    print('FORBIDDEN:' + ','.join(found))\n"
        "    sys.exit(1)\n"
        "print('CLEAN')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    assert result.returncode == 0, (
        f"Import isolation subprocess failed (rc={result.returncode}).\n"
        f"stdout: {stdout}\n"
        f"stderr: {stderr}"
    )
    assert "CLEAN" in stdout, (
        f"Expected 'CLEAN' in stdout, got: {stdout}\nstderr: {stderr}"
    )


def test_security_import_does_not_pull_porting_modules() -> None:
    """Specifically verify no porting module leaks in."""
    check_script = (
        "import sys\n"
        "import vibecomfy.security\n"
        "porting_mods = sorted(k for k in sys.modules if k.startswith('vibecomfy.porting'))\n"
        "if porting_mods:\n"
        "    print('LEAK:' + ','.join(porting_mods))\n"
        "    sys.exit(1)\n"
        "print('CLEAN')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"Porting import leak detected (rc={result.returncode}).\n"
        f"stdout: {result.stdout.strip()}\n"
        f"stderr: {result.stderr.strip()}"
    )
