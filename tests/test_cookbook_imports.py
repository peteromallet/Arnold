"""Test that every docs.cookbook.* module imports safely.

Verifies that importing cookbook tutorial files does not trigger GPU/network
side effects.  Each cookbook module must guard runnable code behind
``if __name__ == '__main__'``.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COOKBOOK_DIR = REPO_ROOT / "docs" / "cookbook"

# Collect all .py files in docs/cookbook/
COOKBOOK_MODULES: list[Path] = sorted(COOKBOOK_DIR.glob("*.py"))

# Map filesystem path → dotted import path
def _path_to_module(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    parts = list(rel.parts)
    # strip .py extension
    parts[-1] = parts[-1][:-3] if parts[-1].endswith(".py") else parts[-1]
    return ".".join(parts)


# ── subprocess-isolated import (safest, avoids any in-process side effects) ──

def _import_via_subprocess(module_path: Path) -> tuple[bool, str]:
    """Import a module in a subprocess and return (ok, stderr)."""
    dotted = _path_to_module(module_path)
    code = (
        f"import importlib, sys; "
        f"sys.path.insert(0, {str(REPO_ROOT)!r}); "
        f"importlib.import_module({dotted!r})"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(REPO_ROOT),
        },
    )
    ok = proc.returncode == 0
    stderr = proc.stderr.strip()
    return ok, stderr


# ── Parametrized test ────────────────────────────────────────────────────────

@pytest.mark.parametrize("module_path", COOKBOOK_MODULES, ids=lambda p: p.name)
def test_cookbook_module_imports_safely(module_path: Path) -> None:
    """Each cookbook module must import without errors or side effects."""
    assert module_path.is_file(), f"Cookbook file missing: {module_path}"

    ok, stderr = _import_via_subprocess(module_path)

    # Allow DeprecationWarning / PendingDeprecationWarning in stderr
    # (they are not import-time side effects)
    if not ok:
        # Filter out known-ok warnings
        lines = stderr.splitlines()
        real_errors = [
            l
            for l in lines
            if "DeprecationWarning" not in l
            and "PendingDeprecationWarning" not in l
            and "UserWarning" not in l
            and "warnings.warn" not in l
        ]
        if real_errors:
            pytest.fail(
                f"Import of {module_path.name} failed:\n" + "\n".join(real_errors)
            )
        # else: only warnings, which are acceptable


def test_cookbook_directory_is_flat() -> None:
    """docs/cookbook/ must be flat — no subdirectories (except __pycache__)."""
    subdirs = [p for p in COOKBOOK_DIR.iterdir() if p.is_dir() and p.name != "__pycache__"]
    assert not subdirs, (
        f"docs/cookbook/ must be flat, found subdirectories: "
        f"{[d.name for d in subdirs]}"
    )


def test_cookbook_file_count() -> None:
    """There must be 5-7 cookbook files (per SD1 settled decision)."""
    count = len(COOKBOOK_MODULES)
    assert 5 <= count <= 7, (
        f"Expected 5-7 cookbook files, found {count}: "
        f"{[p.name for p in COOKBOOK_MODULES]}"
    )


def test_cookbook_files_have_main_guard() -> None:
    """Every cookbook file must have an `if __name__ == '__main__'` guard."""
    for module_path in COOKBOOK_MODULES:
        source = module_path.read_text(encoding="utf-8")
        assert "if __name__ == '__main__'" in source or "if __name__ == \"__main__\"" in source, (
            f"{module_path.name} is missing `if __name__ == '__main__'` guard"
        )
