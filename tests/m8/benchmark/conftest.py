"""Pytest configuration for M8 benchmark tests.

Registers the ``--m8-benchmark`` option and the ``m8_benchmark`` marker,
and defaults benchmark tests to skip unless explicitly opted in.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the ``--m8-benchmark`` flag for opt-in benchmark runs."""
    parser.addoption(
        "--m8-benchmark",
        action="store_true",
        default=False,
        help="Run M8 acceptance-gate benchmark tests (opt-in, width-32 thresholds)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the custom marker so pytest does not warn about it."""
    config.addinivalue_line(
        "markers",
        "m8_benchmark: M8 acceptance-gate benchmark tests (opt-in, width-32 thresholds)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip m8_benchmark tests unless ``--m8-benchmark`` is set."""
    if config.getoption("--m8-benchmark"):
        return
    skip_marker = pytest.mark.skip(reason="M8 benchmark tests are opt-in; use --m8-benchmark to run")
    for item in items:
        if "m8_benchmark" in item.keywords:
            item.add_marker(skip_marker)
