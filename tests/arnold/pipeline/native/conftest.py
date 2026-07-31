"""Isolation fixtures for native-runtime tests.

The production runtime intentionally treats ``artifact_root="."`` as the
caller's working directory.  Tests that exercise that default must therefore
run from a disposable directory rather than the repository checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_native_runtime_default_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep default native artifacts and child roots outside the source tree."""

    monkeypatch.chdir(tmp_path)
