from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from arnold_pipelines.megaplan.resident.profile import MegaplanResidentProfile
from arnold_pipelines.megaplan.store import FileStore


def test_megaplan_resident_tool_catalog_exposes_initiatives_policy(tmp_path: Path) -> None:
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))

    names = {tool.name for tool in profile.tools().list()}

    assert {
        "list_initiatives",
        "create_initiative",
        "read_initiative",
        "write_initiative_doc",
        "classify_initiative_doc",
        "migrate_initiative_layout",
    }.issubset(names)
    prompt = profile.system_prompt()
    assert ".megaplan/initiatives/<slug>/" in prompt
    assert "Never create planning docs directly under .megaplan/briefs" in prompt


def test_megaplan_resident_write_initiative_doc_creates_canonical_folder(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    tool = profile.tools().get("write_initiative_doc")

    result = tool.handler(
        tool.input_model(
            project_root=str(project),
            initiative_slug="Project Alpha",
            doc_kind="research",
            filename="notes.md",
            content_text="# Notes\n",
        )
    )

    assert result.ok is True
    path = project / ".megaplan" / "initiatives" / "project-alpha" / "research" / "notes.md"
    assert path.read_text(encoding="utf-8") == "# Notes\n"
    assert not (project / ".megaplan" / "briefs").exists()


def test_megaplan_resident_create_initiative_writes_description_metadata(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    tool = profile.tools().get("create_initiative")

    result = tool.handler(
        tool.input_model(
            project_root=str(project),
            slug="Discord Context",
            title="Discord Context",
            description="Classify worker messages and preserve initiative structure.",
            create_chain=True,
        )
    )

    assert result.ok is True
    initiative = result.data["initiative"]
    assert initiative["slug"] == "discord-context"
    assert initiative["description"] == "Classify worker messages and preserve initiative structure."
    root = project / ".megaplan" / "initiatives" / "discord-context"
    assert (root / "README.md").read_text(encoding="utf-8") == (
        "# Discord Context\n\n"
        "Classify worker messages and preserve initiative structure.\n"
    )
    assert (root / "chain.yaml").exists()


def test_megaplan_resident_create_initiative_requires_description(tmp_path: Path) -> None:
    profile = MegaplanResidentProfile(store=FileStore(tmp_path / "store"))
    tool = profile.tools().get("create_initiative")

    with pytest.raises(ValidationError):
        tool.input_model(project_root=str(tmp_path), slug="No Description")
