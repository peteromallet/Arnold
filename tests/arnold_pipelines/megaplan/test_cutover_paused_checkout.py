from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from arnold_pipelines.megaplan.chain import spec as chain_spec
from arnold_pipelines.megaplan.incident.chain_control import chain_id_for_spec
from arnold_pipelines.megaplan.cloud.operator_control import RESUME_HOLD_SCHEMA
from arnold_pipelines.megaplan.chain.operator_pause import AUTHORITY_SCHEMA
from arnold_pipelines.megaplan.chain.target_rebind import (
    cutover_paused_checkout,
    sha256_path,
)
import arnold_pipelines.megaplan.chain.target_rebind as target_rebind
from arnold_pipelines.megaplan.cloud.runtime_cutover import normalize_runtime_identity
from arnold_pipelines.megaplan.types import CliError


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "paused-c2"
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    root.mkdir()
    subprocess.run(["git", "init", "--initial-branch", "legacy", str(root)], check=True, capture_output=True)
    _git(root, "config", "user.name", "paused-c2-test")
    _git(root, "config", "user.email", "paused-c2@example.invalid")
    _git(root, "remote", "add", "origin", str(origin))
    (root / ".gitignore").write_text(".megaplan/\n", encoding="utf-8")
    (root / "source.txt").write_text("old\n", encoding="utf-8")
    initiative = root / ".megaplan" / "initiatives" / "native"
    initiative.mkdir(parents=True)
    labels = [f"m{i}" for i in range(7)]
    spec = initiative / "chain.yaml"
    spec.write_text("milestones:\n" + "".join(f"- label: {label}\n  idea: brief.md\n" for label in labels), encoding="utf-8")
    (initiative / "brief.md").write_text("brief\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "legacy")
    old = _git(root, "rev-parse", "HEAD")
    _git(root, "push", "-u", "origin", "legacy")
    _git(root, "switch", "-c", "docs/target")
    (root / "source.txt").write_text("new\n", encoding="utf-8")
    _git(root, "add", "source.txt")
    _git(root, "commit", "-m", "target")
    target = _git(root, "rev-parse", "HEAD")
    _git(root, "push", "-u", "origin", "docs/target")
    _git(root, "switch", "legacy")
    state_path = chain_spec._state_path_for(spec)
    pause = {"schema_version": "arnold.megaplan.operator-pause.v1", "active": True, "plan": "c2-aborted", "paused_at": "2026-09-03T00:00:00Z"}
    runtime = normalize_runtime_identity({"import_root": str(root), "source_revision": old, "editable_root": str(root), "editable_revision": old, "direct_url": {}, "pth": [], "imports": {}})
    completed = [{"label": label, "status": "completed"} for label in labels[:6]]
    chain = {"schema_version": 1, "current_milestone_index": 6, "current_plan_name": None, "last_state": "paused", "completed": completed, "chain_session": root.name, "metadata": {"_nbf08_revision": 0, "chain_id": chain_id_for_spec(spec), "operator_pause": pause, "chain_policy": {"milestone_base_sha": old}, "execution_binding": {"launched_identity": {"runtime": runtime}}, "chain_spec_sha256": sha256_path(spec)}}
    _write(state_path, chain)
    plan_path = root / ".megaplan" / "plans" / "c2-aborted" / "state.json"
    _write(plan_path, {"name": "c2-aborted", "current_state": "aborted", "active_step": None, "history": [{"step": "execute", "result": "aborted"}], "meta": {}})
    marker_path = root / ".megaplan" / "marker.json"
    hold = {"schema_version": RESUME_HOLD_SCHEMA, "active": True, "session": root.name, "spec": str(spec.resolve()), "workspace": str(root.resolve()), "resume_authority": {"schema_version": AUTHORITY_SCHEMA, "active": True, "plan": "c2-aborted"}}
    _write(marker_path, {"should_run": False, "operator_pause": pause, "operator_resume_hold": hold, "runtime_binding": {"current_identity": runtime}, "editable_install_sync": {"source": str(root)}})
    return {"root": root, "spec": spec, "state": state_path, "plan": plan_path, "marker": marker_path, "old": old, "target": target, "prefix": completed, "pause": pause, "hold": hold, "runtime": runtime}


def _call(f: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "marker_path": f["marker"], "aborted_plan_path": f["plan"], "expected_session_id": f["root"].name,
        "expected_current_milestone": "m6", "expected_cursor": 6, "expected_completed_prefix": f["prefix"],
        "expected_chain_state_sha256": sha256_path(f["state"]), "expected_plan_state_sha256": sha256_path(f["plan"]),
        "expected_marker_sha256": sha256_path(f["marker"]), "expected_spec_sha256": sha256_path(f["spec"]),
        "expected_target_spec_sha256": sha256_path(f["spec"]), "expected_chain_revision": 0,
        "expected_hold": f["hold"], "expected_runtime_identity": f["runtime"],
        "from_branch": "legacy", "from_head": f["old"], "from_milestone_base": f["old"], "from_ref": "refs/heads/legacy",
        "to_branch": "docs/target", "to_head": f["target"], "to_milestone_base": f["old"], "to_ref": "refs/heads/docs/target",
        "reason": "adopt authorized paused checkout", "actor": "test",
    }
    values.update(overrides)
    return cutover_paused_checkout(f["spec"], f["root"], **values)


def test_cutover_paused_checkout_commits_binding_and_preserves_aborted_plan(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    plan_before = f["plan"].read_bytes()
    result = _call(f)
    assert result["outcome"] == "committed"
    assert _git(f["root"], "branch", "--show-current") == "docs/target"
    assert _git(f["root"], "rev-parse", "HEAD") == f["target"]
    chain = _json(f["state"])
    marker = _json(f["marker"])
    binding = chain["metadata"]["project_source_binding"]
    assert binding["current"]["head"] == f["target"] == binding["current"]["advertised_sha"]
    assert chain["current_milestone_index"] == 6 and chain["current_plan_name"] is None
    assert chain["last_state"] == "paused" and chain["metadata"]["operator_pause"] == f["pause"]
    assert marker["should_run"] is False and marker["operator_resume_hold"] == f["hold"]
    assert f["plan"].read_bytes() == plan_before


def test_cutover_paused_checkout_rejects_wrong_source_without_mutation(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    before = {p: p.read_bytes() for p in (f["state"], f["plan"], f["marker"])}
    with pytest.raises(CliError, match="source milestone base"):
        _call(f, from_head="0" * 40)
    assert _git(f["root"], "branch", "--show-current") == "legacy"
    assert {p: p.read_bytes() for p in before} == before


def test_cutover_rejects_forged_session_before_mutation(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    before = {p: p.read_bytes() for p in (f["state"], f["plan"], f["marker"])}
    with pytest.raises(CliError, match="canonical project-root name"):
        _call(f, expected_session_id="forged-session")
    assert _git(f["root"], "branch", "--show-current") == "legacy"
    assert {p: p.read_bytes() for p in before} == before


def test_cutover_rejects_forged_resume_authority_before_mutation(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    marker = _json(f["marker"])
    marker["operator_resume_hold"]["resume_authority"] = {"forged": True}
    _write(f["marker"], marker)
    before = {p: p.read_bytes() for p in (f["state"], f["plan"], f["marker"])}
    expected_hold = dict(f["hold"])
    expected_hold["resume_authority"] = {"forged": True}
    with pytest.raises(CliError, match="canonical active hold identity"):
        _call(f, expected_hold=expected_hold)
    assert _git(f["root"], "branch", "--show-current") == "legacy"
    assert {p: p.read_bytes() for p in before} == before


def test_cutover_paused_checkout_replay_is_evidence_only(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    first = _call(f)
    second = _call(f)
    assert first["operation_id"] == second["operation_id"]
    assert second["outcome"] == "replay"
    assert _git(f["root"], "rev-parse", "HEAD") == f["target"]


def test_cutover_paused_checkout_recovers_after_checkout_lost_ack(tmp_path: Path) -> None:
    f = _fixture(tmp_path)

    def lose_ack(stage: str) -> None:
        if stage == "after_git_switch":
            raise RuntimeError("simulated lost acknowledgement")

    with pytest.raises(RuntimeError, match="lost acknowledgement"):
        _call(f, failure_injector=lose_ack)
    assert _git(f["root"], "branch", "--show-current") == "legacy"
    second = _call(f)
    assert second["outcome"] == "committed"
    assert _git(f["root"], "rev-parse", "HEAD") == f["target"]


def test_cutover_paused_checkout_recovers_after_projection_lost_ack(tmp_path: Path) -> None:
    f = _fixture(tmp_path)

    def lose_ack(stage: str) -> None:
        if stage == "after_state_write":
            raise RuntimeError("simulated post-state lost acknowledgement")

    with pytest.raises(RuntimeError, match="post-state lost acknowledgement"):
        _call(f, failure_injector=lose_ack)
    assert _git(f["root"], "rev-parse", "HEAD") == f["target"]
    second = _call(f)
    assert second["outcome"] == "recovered"


def test_cutover_checks_action_off_before_remote_observation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = _fixture(tmp_path)
    marker = _json(f["marker"])
    marker["should_run"] = True
    _write(f["marker"], marker)

    def remote_must_not_run(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("remote observation occurred before action-off guard")

    monkeypatch.setattr(target_rebind, "_remote_advertised_sha", remote_must_not_run)
    with pytest.raises(CliError, match="replay authority hold or action-off"):
        _call(f)


def test_cutover_requires_canonical_session_and_chain_id(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    chain = _json(f["state"])
    chain["chain_session"] = None
    _write(f["state"], chain)
    with pytest.raises(CliError, match="replay authority session or chain ID"):
        _call(f)


def test_cutover_rejects_divergent_plan_binding_without_mutation(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    plan = _json(f["plan"])
    plan["meta"]["project_source_binding"] = {"current": {"branch": "other"}}
    _write(f["plan"], plan)
    with pytest.raises(CliError, match="plan source binding diverges"):
        _call(f)


def test_cutover_rejects_foreign_pending_journal_before_remote(tmp_path: Path) -> None:
    f = _fixture(tmp_path)

    def lose_ack(stage: str) -> None:
        if stage == "after_git_switch":
            raise RuntimeError("leave foreign intent")

    with pytest.raises(RuntimeError, match="leave foreign intent"):
        _call(f, failure_injector=lose_ack)
    _git(f["root"], "switch", "-c", "docs/target-2")
    (f["root"] / "source.txt").write_text("newer\n", encoding="utf-8")
    _git(f["root"], "add", "source.txt")
    _git(f["root"], "commit", "-m", "target 2")
    target_2 = _git(f["root"], "rev-parse", "HEAD")
    _git(f["root"], "push", "-u", "origin", "docs/target-2")
    _git(f["root"], "switch", "legacy")
    with pytest.raises(CliError, match="foreign journal operation"):
        _call(f, to_branch="docs/target-2", to_head=target_2, to_ref="refs/heads/docs/target-2")


def test_cutover_rejects_incomplete_hold_authority(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    marker = _json(f["marker"])
    marker["operator_resume_hold"].pop("resume_authority")
    _write(f["marker"], marker)
    with pytest.raises(CliError, match="replay authority hold"):
        _call(f)


def test_cutover_rejects_forged_prefix_fields(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    forged = [{**row, "completion_receipt": "forged"} for row in f["prefix"]]
    chain = _json(f["state"])
    chain["completed"] = forged
    _write(f["state"], chain)
    with pytest.raises(CliError, match="non-canonical caller fields"):
        _call(f, expected_completed_prefix=forged)


def test_cutover_rejects_source_base_not_tied_to_head(tmp_path: Path) -> None:
    f = _fixture(tmp_path)
    chain = _json(f["state"])
    chain["metadata"]["chain_policy"]["milestone_base_sha"] = f["target"]
    _write(f["state"], chain)
    with pytest.raises(CliError, match="source milestone base"):
        _call(f, from_milestone_base=f["target"])


def test_cutover_rechecks_plan_after_checkout(tmp_path: Path) -> None:
    f = _fixture(tmp_path)

    def mutate_plan(stage: str) -> None:
        if stage == "after_git_switch":
            plan = _json(f["plan"])
            plan["history"].append({"unexpected": True})
            _write(f["plan"], plan)

    with pytest.raises(CliError, match="final plan-state SHA-256"):
        _call(f, failure_injector=mutate_plan)


def test_parser_exposes_cutover_paused_checkout() -> None:
    from arnold_pipelines.megaplan.cli import build_parser
    parser = build_parser()
    args = parser.parse_args(["chain", "cutover-paused-checkout", "--spec", "spec", "--project-dir", "root", "--marker", "marker", "--aborted-plan", "plan", "--session-id", "s", "--current-milestone", "m6", "--cursor", "6", "--completed-prefix", "p", "--hold", "h", "--runtime-identity", "r", "--from-branch", "a", "--from-head", "a" * 40, "--from-milestone-base", "a" * 40, "--from-ref", "refs/heads/a", "--to-branch", "b", "--to-head", "b" * 40, "--to-milestone-base", "a" * 40, "--to-ref", "refs/heads/b", "--expected-chain-state-sha256", "c" * 64, "--expected-plan-state-sha256", "d" * 64, "--expected-marker-sha256", "e" * 64, "--expected-spec-sha256", "f" * 64, "--expected-chain-revision", "0", "--reason", "r"])
    assert args.chain_action == "cutover-paused-checkout"
