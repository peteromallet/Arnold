"""Pytest configuration for M8 benchmark tests.

Registers the legacy ``--m8-benchmark`` option and the ``m8_benchmark`` marker.
The acceptance benchmarks now run in the default suite; the option remains a
compatibility no-op for existing CI invocations.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--m8-benchmark`` flag for opt-in benchmark runs."""
    parser.addoption(
        "--m8-benchmark",
        action="store_true",
        default=False,
        help="Compatibility flag; M8 acceptance benchmarks run by default",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the custom marker so pytest does not warn about it."""
    config.addinivalue_line(
        "markers",
        "m8_benchmark: M8 acceptance-gate benchmark tests (width-32 thresholds)",
    )
