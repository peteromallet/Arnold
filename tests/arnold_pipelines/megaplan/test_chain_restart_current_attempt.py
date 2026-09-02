from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.chain.operator_pause import AUTHORITY_SCHEMA
from arnold_pipelines.megaplan.chain.restart_current_attempt import (
    RESTART_ERROR,
    RESTART_SCHEMA,
    restart_current_attempt,
)
from arnold_pipelines.megaplan.chain.target_rebind import sha256_path, target_rebind
from arnold_pipelines.megaplan.cli import build_parser
from arnold_pipelines.megaplan.types import CliError

PLAN_NAME = "c2-attempt-plan"
MILESTONE = "c2-unfinished"
SOURCE_BRANCH = "source"
TARGET_BRANCH = "target"


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.STDOUT
    ).strip()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _binding_digest(binding: Any) -> str:
    return hashlib.sha256(
        json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _fixture(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "c2-session"
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    root.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch", SOURCE_BRANCH, str(root)],
        check=True,
        capture_output=True,
    )
    _git(root, "config", "user.name", "Restart Test")
    _git(root, "config", "user.email", "restart@example.invalid")
    _git(root, "remote", "add", "origin", str(origin))
    (root / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (root / "source.txt").write_text("source\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "source.txt")
    _git(root, "commit", "-m", "source")
    source_head = _git(root, "rev-parse", "HEAD")
    _git(root, "push", "-u", "origin", SOURCE_BRANCH)
    _git(root, "switch", "-c", TARGET_BRANCH)
    (root / "source.txt").write_text("source\ntarget\n", encoding="utf-8")
    _git(root, "add", "source.txt")
    _git(root, "commit", "-m", "target")
    target_head = _git(root, "rev-parse", "HEAD")
    _git(root, "push", "-u", "origin", TARGET_BRANCH)
    _git(root, "switch", SOURCE_BRANCH)

    spec = root / ".megaplan" / "initiatives" / "c2" / "chain.yaml"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "base_branch: source\n"
        "milestones:\n"
        + "\n".join(
            f"- label: {label}\n  idea: brief-{index}.md\n  branch: {TARGET_BRANCH}"
            for index, label in enumerate(["c0", "c1", "c2", "c3", "c4", "c5", MILESTONE])
        )
        + "\n",
        encoding="utf-8",
    )
    for index in range(7):
        (spec.parent / f"brief-{index}.md").write_text("brief\n", encoding="utf-8")

    source = {
        "branch": SOURCE_BRANCH,
        "head": source_head,
        "milestone_base_sha": source_head,
        "advertised_ref": f"refs/heads/{SOURCE_BRANCH}",
        "advertised_sha": source_head,
    }
    binding = {
        "schema": "arnold.megaplan.project_source_binding.v1",
        "current": source,
        "original": source,
        "rebind_events": [{"direction": "rollback"}],
    }
    pause = {
        "schema_version": AUTHORITY_SCHEMA,
        "active": True,
        "paused_at": "2026-08-01T00:00:00Z",
        "actor": "operator",
        "reason": "hold for restart",
        "previous_chain_last_state": "blocked",
        "previous_plan_state": "executed",
        "plan": PLAN_NAME,
    }
    completed = [{"label": f"c{index}", "plan": f"{label}-plan"} for index, label in enumerate(range(6))]
    chain = {
        "schema_version": 0,
        "current_milestone_index": 6,
        "current_plan_name": PLAN_NAME,
        "last_state": "paused",
        "completed": completed,
        "metadata": {
            "_nbf08_revision": 3,
            "operator_pause": pause,
            "project_source_binding": binding,
            "execution_binding": {"preserve": "exact"},
            "holds": [{"id": "hold-1"}],
        },
    }
    state_path = chain_spec._state_path_for(spec)
    _write_json(state_path, chain)

    plan_dir = root / ".megaplan" / "plans" / PLAN_NAME
    plan = {
        "schema_version": 1,
        "name": PLAN_NAME,
        "current_state": "paused",
        "active_step": None,
        "history": [
            {"step": "init", "result": "success"},
            {"step": "finalize", "result": "success"},
            {"step": "execute", "result": "success"},
        ],
        "resume_cursor": {"phase": "execute"},
        "meta": {
            "chain_policy": {"milestone_base_sha": source_head},
            "project_source_binding": binding,
            "operator_pause": {
                "schema_version": AUTHORITY_SCHEMA,
                "paused_at": pause["paused_at"],
                "reason": pause["reason"],
                "previous_current_state": "executed",
                "previous_chain_last_state": "blocked",
            },
        },
    }
    plan_path = plan_dir / "state.json"
    _write_json(plan_path, plan)
    finalize_bytes = b'{"finalized":true}\n'
    execution_bytes = b'{"executed":true}\n'
    (plan_dir / "finalize.json").write_bytes(finalize_bytes)
    (plan_dir / "execution.json").write_bytes(execution_bytes)
    marker = root / ".megaplan" / "cloud-session.json"
    _write_json(marker, {"session": root.name, "should_run": False})
    return {
        "root": root,
        "spec": spec,
        "state_path": state_path,
        "plan_path": plan_path,
        "plan_dir": plan_dir,
        "marker": marker,
        "source": source_head,
        "target": target_head,
        "binding": binding,
        "finalize": finalize_bytes,
        "execution": execution_bytes,
    }


def _guards(fixture: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    values = {
        "marker_path": fixture["marker"],
        "expected_session_id": fixture["root"].name,
        "expected_cursor": 6,
        "expected_current_milestone": MILESTONE,
        "expected_current_plan": PLAN_NAME,
        "expected_spec_sha256": sha256_path(fixture["spec"]),
        "expected_chain_state_sha256": sha256_path(fixture["state_path"]),
        "expected_plan_state_sha256": sha256_path(fixture["plan_path"]),
        "expected_state_revision": 3,
        "expected_marker_sha256": sha256_path(fixture["marker"]),
        "expected_binding_sha256": _binding_digest(fixture["binding"]),
        "expected_source_head": fixture["source"],
        "reason": "restart unfinished C2 attempt",
        "actor": "test",
    }
    values.update(overrides)
    return values


def _restart(fixture: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return restart_current_attempt(fixture["spec"], fixture["root"], **_guards(fixture, **overrides))


def _ledger_bytes(fixture: dict[str, Any]) -> bytes | None:
    path = fixture["root"] / ".megaplan" / "incident-ledger" / "events.jsonl"
    return path.read_bytes() if path.exists() else None


def test_restart_retires_plan_preserves_prefix_artifacts_and_pause(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    before_finalize = fixture["plan_dir"] / "finalize.json"
    before_execution = fixture["plan_dir"] / "execution.json"
    result = _restart(fixture)

    assert result["outcome"] == "committed"
    chain = _load_json(fixture["state_path"])
    plan = _load_json(fixture["plan_path"])
    assert chain["current_milestone_index"] == 6
    assert chain["current_plan_name"] is None
    assert chain["completed"] == [{"label": f"c{index}", "plan": f"{index}-plan"} for index in range(6)]
    assert chain["last_state"] == "paused"
    assert chain["metadata"]["operator_pause"]["active"] is True
    assert chain["metadata"]["project_source_binding"] == fixture["binding"]
    assert chain["metadata"]["current_attempt_restart"]["schema"] == RESTART_SCHEMA
    assert plan["current_state"] == "aborted"
    assert plan["active_step"] is None
    assert plan["meta"]["retirement"]["kind"] == "retired_for_restart"
    assert before_finalize.read_bytes() == fixture["finalize"]
    ledger = _ledger_bytes(fixture)
    assert ledger is not None
    assert b"restart_current_attempt" in ledger


def test_restart_replay_does_not_rewrite_state_or_plan(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    guards = _guards(fixture)
    first = restart_current_attempt(fixture["spec"], fixture["root"], **guards)
    chain_bytes = fixture["state_path"].read_bytes()
    plan_bytes = fixture["plan_path"].read_bytes()
    second = restart_current_attempt(fixture["spec"], fixture["root"], **guards)
    assert first["outcome"] == "committed"
    assert second["outcome"] == "replay"
    assert fixture["state_path"].read_bytes() == chain_bytes
    assert fixture["plan_path"].read_bytes() == plan_bytes


def test_target_rebind_accepts_retired_plan_without_mutating_it(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    _restart(fixture)
    plan_bytes = fixture["plan_path"].read_bytes()
    finalize_bytes = (fixture["plan_dir"] / "finalize.json").read_bytes()
    execution_bytes = (fixture["plan_dir"] / "execution.json").read_bytes()
    chain = _load_json(fixture["state_path"])
    binding = chain["metadata"]["project_source_binding"]
    result = target_rebind(
        fixture["spec"],
        fixture["root"],
        direction="cutover",
        expected_session_id=fixture["root"].name,
        expected_current_milestone=MILESTONE,
        expected_current_plan=PLAN_NAME,
        from_branch=SOURCE_BRANCH,
        from_head=fixture["source"],
        from_milestone_base=fixture["source"],
        from_ref=f"refs/heads/{SOURCE_BRANCH}",
        to_branch=TARGET_BRANCH,
        to_head=fixture["target"],
        to_ref=f"refs/heads/{TARGET_BRANCH}",
        expected_spec_sha256=sha256_path(fixture["spec"]),
        expected_chain_state_sha256=sha256_path(fixture["state_path"]),
        expected_plan_state_sha256=sha256_path(fixture["plan_path"]),
        reason="rebind after retirement",
        actor="test",
    )
    assert result["head"] == fixture["target"]
    assert fixture["plan_path"].read_bytes() == plan_bytes
    assert (fixture["plan_dir"] / "finalize.json").read_bytes() == finalize_bytes
    assert (fixture["plan_dir"] / "execution.json").read_bytes() == execution_bytes
    rebound = _load_json(fixture["state_path"])
    assert rebound["current_plan_name"] is None
    assert rebound["metadata"]["project_source_binding"]["current"]["head"] == fixture["target"]
    assert rebound["metadata"]["current_attempt_restart"] == chain["metadata"]["current_attempt_restart"]
    assert binding["current"]["head"] == fixture["source"]


def test_post_restart_rebind_uses_guarded_source_when_retired_base_is_historical(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    plan = _load_json(fixture["plan_path"])
    plan["meta"]["chain_policy"]["milestone_base_sha"] = "9" * 40
    _write_json(fixture["plan_path"], plan)
    _restart(fixture)

    result = target_rebind(
        fixture["spec"],
        fixture["root"],
        direction="cutover",
        expected_session_id=fixture["root"].name,
        expected_current_milestone=MILESTONE,
        expected_current_plan=PLAN_NAME,
        from_branch=SOURCE_BRANCH,
        from_head=fixture["source"],
        from_milestone_base=fixture["source"],
        from_ref=f"refs/heads/{SOURCE_BRANCH}",
        to_branch=TARGET_BRANCH,
        to_head=fixture["target"],
        to_ref=f"refs/heads/{TARGET_BRANCH}",
        expected_spec_sha256=sha256_path(fixture["spec"]),
        expected_chain_state_sha256=sha256_path(fixture["state_path"]),
        expected_plan_state_sha256=sha256_path(fixture["plan_path"]),
        reason="rebind after guarded restart from historical plan base",
        actor="test",
    )

    assert result["head"] == fixture["target"]
    # The retired plan remains immutable; the new source is recorded only on
    # the chain boundary and is available to the resumed successor.
    assert _load_json(fixture["plan_path"])["meta"]["chain_policy"]["milestone_base_sha"] == "9" * 40


def test_forged_restart_record_with_live_plan_refuses_target_rebind(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    chain = _load_json(fixture["state_path"])
    chain["current_plan_name"] = None
    chain["metadata"]["current_attempt_restart"] = {
        "schema": RESTART_SCHEMA,
        "retired_plan": PLAN_NAME,
        "cursor": 6,
        "milestone": MILESTONE,
        "operation_id": "forged",
    }
    _write_json(fixture["state_path"], chain)
    before = fixture["plan_path"].read_bytes()
    with pytest.raises(CliError, match="retired plan to be terminal"):
        target_rebind(
            fixture["spec"],
            fixture["root"],
            direction="cutover",
            expected_session_id=fixture["root"].name,
            expected_current_milestone=MILESTONE,
            expected_current_plan=PLAN_NAME,
            from_branch=SOURCE_BRANCH,
            from_head=fixture["source"],
            from_milestone_base=fixture["source"],
            from_ref=f"refs/heads/{SOURCE_BRANCH}",
            to_branch=TARGET_BRANCH,
            to_head=fixture["target"],
            to_ref=f"refs/heads/{TARGET_BRANCH}",
            expected_spec_sha256=sha256_path(fixture["spec"]),
            expected_chain_state_sha256=sha256_path(fixture["state_path"]),
            expected_plan_state_sha256=sha256_path(fixture["plan_path"]),
            reason="must refuse live plan",
            actor="test",
        )
    assert fixture["plan_path"].read_bytes() == before


def test_live_c2_before_restart_refuses_and_is_unchanged(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    before = {path: path.read_bytes() for path in (fixture["state_path"], fixture["plan_path"], fixture["marker"])}
    with pytest.raises(CliError, match="already has (?:finalize|execute) history"):
        target_rebind(
            fixture["spec"], fixture["root"], direction="cutover",
            expected_session_id=fixture["root"].name, expected_current_milestone=MILESTONE,
            expected_current_plan=PLAN_NAME, from_branch=SOURCE_BRANCH, from_head=fixture["source"],
            from_milestone_base=fixture["source"], from_ref=f"refs/heads/{SOURCE_BRANCH}",
            to_branch=TARGET_BRANCH, to_head=fixture["target"], to_ref=f"refs/heads/{TARGET_BRANCH}",
            expected_spec_sha256=sha256_path(fixture["spec"]),
            expected_chain_state_sha256=sha256_path(fixture["state_path"]),
            expected_plan_state_sha256=sha256_path(fixture["plan_path"]),
            reason="must refuse live executed plan", actor="test",
        )
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("case", ["plan", "cursor", "revision", "pause", "marker", "owner", "completed", "pre_execute"])
def test_restart_rejections_are_zero_mutation(tmp_path: Path, case: str) -> None:
    fixture = _fixture(tmp_path)
    if case == "plan":
        overrides = {"expected_current_plan": "wrong-plan"}
    elif case == "cursor":
        overrides = {"expected_cursor": 5}
    elif case == "revision":
        overrides = {"expected_state_revision": 2}
    else:
        overrides = {}
        if case == "pause":
            chain = _load_json(fixture["state_path"])
            chain["metadata"]["operator_pause"]["active"] = False
            _write_json(fixture["state_path"], chain)
            overrides["expected_chain_state_sha256"] = sha256_path(fixture["state_path"])
        elif case == "marker":
            marker = _load_json(fixture["marker"])
            marker["should_run"] = True
            _write_json(fixture["marker"], marker)
            overrides["expected_marker_sha256"] = sha256_path(fixture["marker"])
        elif case == "owner":
            plan = _load_json(fixture["plan_path"])
            plan["active_step"] = {"runner": "live"}
            _write_json(fixture["plan_path"], plan)
            overrides["expected_plan_state_sha256"] = sha256_path(fixture["plan_path"])
        elif case == "completed":
            chain = _load_json(fixture["state_path"])
            chain["completed"].append({"label": MILESTONE})
            _write_json(fixture["state_path"], chain)
            overrides["expected_chain_state_sha256"] = sha256_path(fixture["state_path"])
        elif case == "pre_execute":
            plan = _load_json(fixture["plan_path"])
            plan["history"] = [{"step": "init", "result": "success"}]
            _write_json(fixture["plan_path"], plan)
            (fixture["plan_dir"] / "finalize.json").unlink()
            (fixture["plan_dir"] / "execution.json").unlink()
            overrides["expected_plan_state_sha256"] = sha256_path(fixture["plan_path"])
    before = {path: path.read_bytes() for path in (fixture["state_path"], fixture["plan_path"], fixture["marker"])}
    with pytest.raises(CliError) as caught:
        _restart(fixture, **overrides)
    assert caught.value.code == RESTART_ERROR
    assert {path: path.read_bytes() for path in before} == before
    assert _ledger_bytes(fixture) is None


def test_restart_completes_after_plan_retired_before_chain_cas(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    guards = _guards(fixture)
    from arnold_pipelines.megaplan.incident.chain_control import _stable_id, chain_id_for_spec

    operation_id = _stable_id(
        "restart-current-attempt",
        chain_id_for_spec(fixture["spec"]),
        "3",
        "6",
        PLAN_NAME,
        guards["expected_plan_state_sha256"],
    )
    plan = _load_json(fixture["plan_path"])
    plan["current_state"] = "aborted"
    plan["active_step"] = None
    plan.setdefault("meta", {})["retirement"] = {
        "kind": "retired_for_restart",
        "retired_at": "2026-08-01T00:00:00Z",
        "actor": "test",
        "reason": "restart unfinished C2 attempt",
        "cursor": 6,
        "milestone": MILESTONE,
        "operation_id": operation_id,
    }
    _write_json(fixture["plan_path"], plan)
    result = restart_current_attempt(fixture["spec"], fixture["root"], **guards)
    assert result["outcome"] == "committed"
    chain = _load_json(fixture["state_path"])
    assert chain["current_plan_name"] is None
    assert chain["current_milestone_index"] == 6
    assert chain["metadata"]["current_attempt_restart"]["operation_id"] == operation_id
    assert (fixture["plan_dir"] / "finalize.json").read_bytes() == fixture["finalize"]


def test_restart_race_revision_refuses_without_terminalizing_plan(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    guards = _guards(fixture)
    chain = _load_json(fixture["state_path"])
    chain["metadata"]["_nbf08_revision"] = 4
    _write_json(fixture["state_path"], chain)
    guards["expected_chain_state_sha256"] = _guards(fixture)["expected_chain_state_sha256"]
    plan_before = fixture["plan_path"].read_bytes()
    with pytest.raises(CliError) as caught:
        restart_current_attempt(fixture["spec"], fixture["root"], **guards)
    assert caught.value.code == RESTART_ERROR
    assert fixture["plan_path"].read_bytes() == plan_before


def test_restart_parser_smoke() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "chain", "restart-current-attempt", "--spec", "spec.yaml", "--project-dir", ".",
            "--marker", "marker.json", "--expected-session-id", "session", "--expected-cursor", "6",
            "--expected-current-milestone", MILESTONE, "--expected-current-plan", PLAN_NAME,
            "--expected-spec-sha256", "a" * 64, "--expected-chain-state-sha256", "b" * 64,
            "--expected-plan-state-sha256", "c" * 64, "--expected-state-revision", "3",
            "--expected-marker-sha256", "d" * 64, "--expected-binding-sha256", "e" * 64,
            "--expected-source-head", "f" * 40, "--reason", "test",
        ]
    )
    assert args.chain_action == "restart-current-attempt"
