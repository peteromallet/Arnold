from __future__ import annotations

from pathlib import Path


def test_megaplan_package_declares_pep561_typing_marker() -> None:
    package_root = Path(__file__).resolve().parents[2] / "arnold" / "pipelines" / "megaplan"

    assert (package_root / "py.typed").is_file()
