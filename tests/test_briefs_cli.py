from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_megaplan(argv: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env.pop("MEGAPLAN_BACKEND", None)
    return subprocess.run(
        [sys.executable, "-m", "megaplan", *argv],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def test_brief_new_writes_canonical_file(tmp_path: Path) -> None:
    proc = _run_megaplan(
        ["brief", "new", "My Idea", "-b", "Do the thing."],
        cwd=tmp_path,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    path = tmp_path / ".megaplan" / "briefs" / "my-idea.md"
    assert payload["path"] == str(path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\ntype: brief\nslug: my-idea\n")
    assert text.endswith("\nDo the thing.\n")


def test_brief_new_init_runs_from_created_brief(tmp_path: Path) -> None:
    proc = _run_megaplan(
        ["brief", "new", "Launch Me", "-b", "write a tiny plan", "--init"],
        cwd=tmp_path,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["initialized"] is True
    assert payload["init"]["success"] is True
    plan = payload["init"]["plan"]
    state = json.loads(
        (tmp_path / ".megaplan" / "plans" / plan / "state.json").read_text(
            encoding="utf-8"
        )
    )
    assert state["idea"] == "write a tiny plan"


def test_brief_epic_scaffolds_chain_and_milestones(tmp_path: Path) -> None:
    proc = _run_megaplan(
        [
            "brief",
            "epic",
            "Artifact Store",
            "--milestone",
            "m1-schema=Schema",
            "--milestone",
            "m2-api=API",
        ],
        cwd=tmp_path,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    epic_dir = tmp_path / ".megaplan" / "briefs" / "artifact-store"
    assert payload["chain"] == str(epic_dir / "chain.yaml")
    assert (epic_dir / "m1-schema.md").exists()
    assert (epic_dir / "m2-api.md").exists()
    chain = yaml.safe_load((epic_dir / "chain.yaml").read_text(encoding="utf-8"))
    assert chain["base_branch"] == "main"
    assert chain["milestones"] == [
        {"label": "m1-schema", "idea": ".megaplan/briefs/artifact-store/m1-schema.md"},
        {"label": "m2-api", "idea": ".megaplan/briefs/artifact-store/m2-api.md"},
    ]


def test_brief_list_show_and_search_use_common_artifact_shape(tmp_path: Path) -> None:
    create = _run_megaplan(
        ["brief", "new", "Shared Shape", "-b", "Searchable artifact body"],
        cwd=tmp_path,
    )
    assert create.returncode == 0, create.stderr

    listed = _run_megaplan(["brief", "list"], cwd=tmp_path)
    assert listed.returncode == 0, listed.stderr
    list_payload = json.loads(listed.stdout)
    assert list_payload["briefs"][0]["id"] == "shared-shape"
    assert list_payload["briefs"][0]["title"] == "Shared Shape"

    shown = _run_megaplan(["brief", "show", "shared-shape"], cwd=tmp_path)
    assert shown.returncode == 0, shown.stderr
    show_payload = json.loads(shown.stdout)
    assert show_payload["brief"]["body"] == "Searchable artifact body"
    assert show_payload["brief"]["metadata"]["type"] == "brief"

    searched = _run_megaplan(["brief", "search", "artifact"], cwd=tmp_path)
    assert searched.returncode == 0, searched.stderr
    search_payload = json.loads(searched.stdout)
    assert [item["id"] for item in search_payload["briefs"]] == ["shared-shape"]
    assert "snippet" in search_payload["briefs"][0]
