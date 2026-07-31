"""Security-test fixtures with host-portable local endpoint paths."""

from __future__ import annotations

import sys
import tempfile
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def short_broker_socket_path() -> Iterator[Path]:
    """Yield a short disposable AF_UNIX path outside long workspace roots."""

    base = Path("/tmp") if sys.platform == "darwin" else Path(tempfile.gettempdir())
    path = base / f"arnold-broker-{uuid.uuid4().hex[:16]}.sock"
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)
