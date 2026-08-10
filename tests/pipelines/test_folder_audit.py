"""Retirement contract for the archived folder-audit pipeline."""

from pathlib import Path

from arnold_pipelines.discovery import discover_shipped_pipelines


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_folder_audit_is_archived_and_not_publicly_discoverable() -> None:
    """Retirement stays explicit without carrying an unconditional skip."""

    shipped_ids = {info.id for info in discover_shipped_pipelines()}
    assert "folder_audit" not in shipped_ids
    assert "folder-audit" not in shipped_ids
    assert (REPO_ROOT / "docs/archive/m5/pipelines/folder_audit").is_dir()
