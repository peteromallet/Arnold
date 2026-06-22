from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--backend",
        action="store",
        default=None,
        help="Optional storage backend selector used by Sprint 1 backend tests.",
    )
    parser.addoption(
        "--write-fixture",
        action="store_true",
        default=False,
        help="Regenerate characterization test fixtures on disk.",
    )


def read_json(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
