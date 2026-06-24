"""Pytest fixtures for megaplan agentic tests.

Provides per-test ``MEGAPLAN_HOME`` isolation so that adapter tests
do not read or mutate the user's real ``~/.megaplan/`` directory.

Only affects pytest collection within ``megaplan/tests/agentic/``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def isolated_megaplan_home(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect MEGAPLAN_HOME to a temp directory for each test.

    Also patches Path.home()/.megaplan to point at the same temp dir
    so that any megaplan code path hard-coding ``~/.megaplan/`` is
    caught and isolated.
    """
    tmp = tempfile.mkdtemp(prefix="megaplan_test_")
    fake_home = Path(tmp)

    monkeypatch.setenv("MEGAPLAN_HOME", str(fake_home))

    # Guard against code paths that hard-code ~/.megaplan/.
    real_home = Path.home()

    def _safe_home() -> Path:
        return fake_home

    monkeypatch.setattr(Path, "home", _safe_home)

    yield

    # Cleanup the temp directory.
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
