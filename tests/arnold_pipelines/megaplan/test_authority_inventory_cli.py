from __future__ import annotations

import hashlib
import json
from pathlib import Path

from arnold_pipelines.megaplan import cli
import arnold_pipelines.megaplan.authority.inventory as inventory_module
from arnold_pipelines.megaplan.authority.inventory import SOURCE_REGISTRY


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _plan(root: Path) -> Path:
    plan = root / ".megaplan" / "plans" / "demo-plan"
    _write_json(
        plan / "state.json",
        {"name": "demo-plan", "schema_version": 1, "current_state": "initialized"},
    )
    _write_json(plan / "finalize.json", {"tasks": [{"id": "T1", "status": "pending"}]})
    # A legacy artifact is deliberately incomplete so the command must expose
    # its contradiction instead of treating it as task authority.
    _write_json(plan / "execution_batch_1.json", {"task_updates": [{"task_id": "T1", "status": "done"}]})
    return plan


def test_authority_inventory_command_is_deterministic_read_only_and_complete(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root = tmp_path / "root"
    plan = _plan(root)
    marker_dir = tmp_path / "missing-markers"
    monkeypatch.setattr(cli, "maybe_auto_sync_repo_editor_support", lambda _root: None)
    monkeypatch.setattr(cli, "_auto_sync_installed_skills", lambda: None)
    monkeypatch.setattr(cli, "ensure_runtime_layout", lambda _root: None)
    monkeypatch.setattr(
        inventory_module,
        "resolve_current_target",
        lambda session, **_kwargs: {
            "schema_version": 1,
            "target_id": session,
            "target_session": session,
            "authoritative_source": "resolver_observe_disabled",
            "marker": {},
            "event_cursors": {},
            "needs_human": {},
            "active_step_heartbeat": {},
            "stale_evidence": [],
        },
    )

    parser_args = cli.build_parser().parse_args(
        [
            "authority-inventory",
            "--plan",
            "demo-plan",
            "--session",
            "session-a",
            "--marker-dir",
            str(marker_dir),
        ]
    )
    assert parser_args.command == "authority-inventory"
    assert parser_args.session == "session-a"
    assert parser_args.marker_dir == str(marker_dir)

    before = _snapshot(plan)
    argv = [
        "authority-inventory",
        "--project-dir",
        str(root),
        "--plan",
        "demo-plan",
        "--session",
        "session-a",
        "--marker-dir",
        str(marker_dir),
    ]
    assert cli.main(argv) == 0
    first_output = capsys.readouterr().out
    assert cli.main(argv) == 0
    second_output = capsys.readouterr().out

    assert first_output == second_output
    assert _snapshot(plan) == before
    payload = json.loads(first_output)
    assert payload["success"] is True
    assert payload["step"] == "authority-inventory"
    assert payload["plan"] == "demo-plan"
    assert payload["fingerprint"].startswith("sha256:")
    assert len(payload["fingerprint"]) == len("sha256:") + 64
    records = payload["inventory"]["records"]
    parent_keys = {(record["category"], record["source_class"]) for record in records}
    assert {(spec.category, spec.source_class) for spec in SOURCE_REGISTRY} <= parent_keys
    assert "legacy_authority_identity_incomplete" in {
        contradiction["code"] for contradiction in payload["inventory"]["contradictions"]
    }
    by_key = {(record["category"], record["source_class"]): record for record in records}
    assert by_key[("cloud", "session_marker")]["presence"] == "degraded"
    assert by_key[("cloud", "current_target")]["presence"] == "degraded"


def test_authority_inventory_command_reports_unconfigured_optional_collectors(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    root = tmp_path / "root"
    _plan(root)
    monkeypatch.setattr(cli, "maybe_auto_sync_repo_editor_support", lambda _root: None)
    monkeypatch.setattr(cli, "_auto_sync_installed_skills", lambda: None)
    monkeypatch.setattr(cli, "ensure_runtime_layout", lambda _root: None)

    assert cli.main(
        ["authority-inventory", "--project-dir", str(root), "--plan", "demo-plan"]
    ) == 0

    records = json.loads(capsys.readouterr().out)["inventory"]["records"]
    by_key = {(record["category"], record["source_class"]): record for record in records}
    assert by_key[("cloud", "session_marker")]["presence"] == "not_configured"
    assert by_key[("cloud", "current_target")]["presence"] == "not_configured"
    assert "session and marker directory are not configured" in by_key[("cloud", "current_target")]["reason"]
