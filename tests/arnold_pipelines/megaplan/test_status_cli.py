from __future__ import annotations

import argparse
import json
from pathlib import Path

from arnold_pipelines.megaplan import cli
from arnold_pipelines.megaplan.handlers.init import handle_init


def test_status_command_accepts_project_dir_and_plan(
    capsys,
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    base = cli.build_parser().parse_args(["init"])
    args = argparse.Namespace(**vars(base))
    args.project_dir = str(project_dir)
    args.idea = "fixture plan"
    args.name = "fixture-plan"
    args.robustness = "standard"

    response = handle_init(root, args)
    plan_name = response["plan"]

    rc = cli.main(["status", "--project-dir", str(root), "--plan", plan_name])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["success"] is True
    assert payload["plan"] == plan_name
    assert payload["state"] == "initialized"
    assert payload["status_route_authority"] == "workflow_source_only"
    assert payload["legacy_route_hints"]["authority"] == "display_only_non_authoritative"
    assert payload["legacy_route_hints"]["next_step"] == payload["next_step"]
    assert payload["legacy_route_hints"]["valid_next"] == payload["valid_next"]
    assert payload["next_step"] in payload["valid_next"]
    assert "workflow_cursor" not in payload
