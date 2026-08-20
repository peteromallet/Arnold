"""Focused tests for scripts/fixer_recovery_predeploy.py (T-0601 verdict)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts import fixer_recovery_baseline as baseline
from scripts import fixer_recovery_predeploy as predeploy
from scripts.fixer_recovery_baseline import BaselineConfig, capture_baseline
from scripts.fixer_recovery_predeploy import (
    FAIL_EDITABLE_INSTALL,
    FAIL_INCOHERENT_CAPTURE,
    FAIL_INVALID_BASELINE,
    FAIL_LEDGER_BYPASS,
    FAIL_MISSING_PROOF,
    FAIL_MIXED_VERSIONS,
    FAIL_NON_CANONICAL_ACTION,
    FAIL_NOT_PINNED,
    FAIL_SELECTORS,
    FAIL_SOURCE_SHA,
    FAIL_STALE_SESSION,
    FAIL_UNSNAPSHOTTED_INPUTS,
    PREDEPLOY_SCHEMA,
    VERDICT_RECEIPT_NAME,
    run_predeploy,
)

SHA = "a" * 40
OTHER_SHA = "b" * 40
GEN_SHA = "c" * 64
GEN_VENV_DIGEST = "d" * 64


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")


def _commit_gate_scripts(git_root: Path) -> None:
    """The pinned source SHA must CONTAIN the gate tooling (G13 advisory 1).

    The predeploy ``source_sha_bound`` check cat-files these paths inside the
    pin; without them the pinned commit does not contain the gate that
    produced the baseline.
    """
    for name in ("fixer_recovery_baseline.py", "fixer_recovery_predeploy.py"):
        _write(git_root / "scripts" / name, f"# {name} fixture stub\n")
    _git(git_root, "add", "scripts/")
    _git(git_root, "commit", "-m", "add gate tooling")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_fixture(
    tmp_path: Path,
    *,
    selector_in_wrapper: bool = False,
    venv_in_root: bool = False,
    no_generation: bool = False,
    other_head: bool = False,
    include_unproven_state: bool = False,
    editable_residue_in_schedule: bool = False,
) -> tuple[BaselineConfig, Path]:
    """Build one complete, coherent live-state fixture; returns (config, ws).

    Layout mirrors the live box (chain store + plan state under the epic
    worktree, per-epic runtime manifest at workspace level, session markers
    in ``<ws>/.megaplan/cloud-sessions``).  The fixture git repo has two
    commits; ``head`` is the initial commit (a real SHA) unless
    ``other_head`` is set.
    """
    ws = tmp_path / "workspace"
    initiative = tmp_path / "initiative"
    runtime_root = ws / "runtime" / "arnold-main"
    gen_venv = ws / "generations" / GEN_SHA

    session = "megaplan-maintenance"
    plan = "m1-containment-and-truthful-20260811-0640"
    chain_record = "chain-c511d8baf7d7.json"
    epic = ws / "megaplan-maintenance" / "Arnold" / ".megaplan"

    git_root = ws / "git"
    _init_repo(git_root)
    _commit_gate_scripts(git_root)
    initial_sha = _git(git_root, "rev-parse", "HEAD")
    _git(git_root, "commit", "--allow-empty", "-m", "second")
    other_sha = _git(git_root, "rev-parse", "HEAD")
    _git(git_root, "branch", "fixer/f1")
    _git(git_root, "branch", "reconcile/r1")
    _git(git_root, "branch", "editible-install")
    head = other_sha if other_head else initial_sha

    _write(
        initiative / "chain.yaml",
        f"""base_branch: main
anchors:
  north_star: NORTHSTAR.md
milestones:
- label: m1
  idea: briefs/m1.md
  profile: partnered-5
  vendor: codex
driver:
  robustness: full
  auto_approve: false
  intended_initiative_revision: {head}
  initiative_path: {initiative}
""",
    )
    _write(initiative / "NORTHSTAR.md", "# North Star\n\nMaintenance control plane.\n")
    _write(initiative / "briefs" / "m1.md", "# M1 brief\n")

    _write(
        epic / "plans" / ".chains" / chain_record,
        json.dumps(
            {
                "schema": "arnold.megaplan.chain_state.v1",
                "chain": "megaplan-maintenance",
                "metadata": {
                    "execution_environment": {
                        "engine_root": str(runtime_root),
                        "run_revision": head,
                    }
                },
            }
        ),
    )
    _write(
        ws / ".megaplan" / "cloud-sessions" / f"{session}.json",
        json.dumps(
            {
                "session": session,
                "engine_root": str(runtime_root),
                "run_revision": head,
                "phase": "paused",
            }
        ),
    )

    wrapper = (
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        "exec python3 -m arnold_pipelines.megaplan.cloud.simple_fixer \"$@\"\n"
    )
    if selector_in_wrapper:
        wrapper += "export MEGAPLAN_RUNTIME_SRC=/tmp/retired-selector\n"
    _write(runtime_root / "bin" / "arnold-babysitter", wrapper)
    (runtime_root / "bin" / "arnold-babysitter").chmod(0o755)
    if venv_in_root:
        _write(runtime_root / ".venv" / "bin" / "python", "#!/bin/sh\n")
        (runtime_root / ".venv" / "bin" / "python").chmod(0o755)
    _write(gen_venv / "bin" / "python", "#!/bin/sh\n")
    (gen_venv / "bin" / "python").chmod(0o755)

    epic_venv = str(gen_venv) if not venv_in_root else str(runtime_root / ".venv")
    manifest = {
        "runtime_id": "arnold-megaplan-maintenance-r1",
        "schema": "1",
        "generation": 7,
        "epic_id": "megaplan-maintenance",
        "state": "active",
        "owner": "megaplan.chain",
        "base": {"ref": "main", "commit": head, "editable_install_path": "", "venv_path": epic_venv},
        "epic": {
            "branch": "main",
            "worktree_path": str(runtime_root),
            "venv_path": epic_venv,
            "runtime_root": str(runtime_root),
            "expected_head": head,
            "repair_bin": str(runtime_root / "bin" / "arnold-babysitter"),
            "deps_lockfile": str(runtime_root / "uv.lock"),
        },
        "indirection": {
            "host_path": str(runtime_root),
            "container_path": "/workspace/arnold",
            "mount_table": [],
            "execution_namespace": "host",
            "verified_head": head,
            "last_verified_at": "2026-08-13T00:00:00Z",
            "attestation": {
                "module_file": "arnold_pipelines/__init__.py",
                "module_digest": "x",
                "mount_id": "m",
            },
        },
        "policy": {"policy_sha": "p", "model_policy_sha": "m", "sync_policy": "none"},
        "promotions": [],
        "timestamps": {
            "created": "2026-08-01T00:00:00Z",
            "updated": "2026-08-13T00:00:00Z",
            "closed": "",
        },
        "gc_policy": {"keep": 2},
        "commands": [],
    }
    if not no_generation:
        manifest["epic"]["dependency_generation"] = {
            "id": GEN_SHA,
            "frozen_spec_sha256": GEN_SHA,
            "interpreter_path": str(gen_venv / "bin" / "python"),
            "venv_digest": GEN_VENV_DIGEST,
            "created": "2026-08-13T00:00:00Z",
        }
    _write(
        ws / ".megaplan" / "megaplan-maintenance.json",
        json.dumps(manifest, indent=2),
    )

    _write(
        epic / "plans" / plan / "state.json",
        json.dumps(
            {
                "name": plan,
                "chain": "megaplan-maintenance",
                "metadata": {"writer": "megaplan.chain.wbc.advance"},
                "phase": "done",
            }
        ),
    )
    cas_state = {
        "name": plan,
        "chain": "megaplan-maintenance",
        "metadata": {},
        "phase": "executing",
    }
    cas_bytes = json.dumps(cas_state).encode("utf-8")
    _write(
        epic / "plans" / plan / "occurrence" / "state.json",
        cas_bytes.decode("utf-8"),
    )
    if include_unproven_state:
        _write(
            epic / "plans" / plan / "mystery" / "state.json",
            json.dumps({"name": plan, "metadata": {}, "phase": "mystery"}),
        )

    _write(
        ws / ".megaplan" / "repair-queue" / "requests" / "r-1.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "repair_request",
                "request_id": "req-1",
                "created_at": "2026-08-13T00:00:00Z",
                "source": {"kind": "watchdog", "session": "megaplan-maintenance"},
                "authority": {
                    "chain_state_sha256": "sha256:" + hashlib.sha256(cas_bytes).hexdigest()
                },
            }
        ),
    )
    _write(
        ws / ".megaplan" / "repair-queue" / "decisions" / "d-1.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "repair_request_decision",
                "decision_id": "dec-1",
                "request_id": "req-1",
                "decision": "accepted",
                "created_at": "2026-08-13T00:00:00Z",
            }
        ),
    )
    _write(
        ws / ".megaplan" / "repair-queue" / "attempts" / "a-1.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "repair_request_attempt",
                "attempt_id": "att-1",
                "request_id": "req-1",
                "blocker_id": "b-1",
                "status": "launched",
                "created_at": "2026-08-13T00:00:00Z",
            }
        ),
    )
    _write(
        ws / ".megaplan" / "repair-queue" / "active-claims" / "cafe.lock" / "owner.json",
        json.dumps(
            {
                "kind": "active_repair_request_claim",
                "schema_version": 1,
                "request_id": "req-1",
                "actor": "fixer",
                "session": "megaplan-maintenance",
            }
        ),
    )
    _write(
        ws / ".megaplan" / "repair-queue" / "claims-index" / "abc.json",
        json.dumps(
            {
                "schema": "claim-alias/v1",
                "blocker_id": "b-1",
                "occurrence_fingerprint": "fp-1",
                "request_id": "req-1",
                "repair_identity_key": "k",
                "fence_epoch": 0,
                "fence_token": 0,
                "holder_namespaces": ["active"],
                "updated_at": "2026-08-13T00:00:00Z",
            }
        ),
    )

    _write(
        ws / "arnold" / ".megaplan" / "resident" / "scheduled_jobs" / "hourly.json",
        json.dumps({"job": "superfixer_proactive", "state": "cancelled", "keep_cancelled": True}),
    )
    _write(
        ws / ".megaplan" / "ops" / "schedules" / "ops.json",
        json.dumps({"job": "ops", "state": "cancelled"}),
    )
    if editable_residue_in_schedule:
        _write(
            ws / ".megaplan" / "ops" / "schedules" / "residue.json",
            json.dumps({"job": "stale", "note": "pip install -e /tmp/arnold residue"}),
        )
    _write(
        ws / ".megaplan" / "schedule-inputs" / "input-1" / "SKILL.md",
        "# input\n",
    )
    _write(
        ws / ".megaplan" / "reconcile-receipts" / "close.json",
        json.dumps(
            {
                "schema": "arnold.megaplan.reconcile_close.v1",
                "epic": "megaplan-maintenance",
                "outcome": "merged",
            }
        ),
    )

    config = BaselineConfig(
        workspace=ws,
        initiative_dir=initiative,
        chain_store=epic / "plans" / ".chains",
        marker_dirs=(ws / ".megaplan" / "cloud-sessions",),
        runtime_manifest=ws / ".megaplan" / "megaplan-maintenance.json",
        repair_queue=ws / ".megaplan" / "repair-queue",
        plan_state_dir=epic / "plans" / plan,
        schedule_dirs=(
            ws / "arnold" / ".megaplan" / "resident" / "scheduled_jobs",
            ws / ".megaplan" / "ops" / "schedules",
            ws / ".megaplan" / "schedule-inputs",
        ),
        reconcile_dir=ws / ".megaplan" / "reconcile-receipts",
        reconcile_refs=(
            "refs/heads/fixer/*",
            "refs/heads/reconcile/*",
            "refs/heads/editible-install",
        ),
        git_root=git_root,
        session=session,
        plan=plan,
        chain_record=chain_record,
        collector=True,
    )
    return config, ws


def fixture_head(config: BaselineConfig) -> str:
    """The initial commit SHA of the fixture git repo (the default head)."""
    return _git(config.git_root, "rev-parse", "HEAD~1")


def _capture_to(config: BaselineConfig, ws: Path, name: str = "baseline.json") -> Path:
    envelope = capture_baseline(config)
    out = ws / name
    out.write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")
    return out


# ── PASS path ───────────────────────────────────────────────────────────────


def test_pass_verdict_on_coherent_fixture(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "PASS"
    assert verdict["reasons"] == []
    assert verdict["schema"] == PREDEPLOY_SCHEMA
    assert verdict["baseline_id"] == json.loads(baseline_path.read_text())["baseline_id"]
    assert all(check["passed"] for check in verdict["checks"].values())


# ── fail-closed: corrupting ANY one receipt ────────────────────────────────


def test_corrupting_any_single_receipt_makes_predeploy_fail(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    envelope = json.loads(baseline_path.read_text(encoding="utf-8"))
    records = list(predeploy._iter_captured_files(envelope))
    assert len(records) >= 12, "the corruption sweep must cover every receipt"

    for kind, record in records:
        target = Path(record["path"])
        assert target.is_file(), kind
        original = target.read_bytes()
        target.write_bytes(original + b"\nCORRUPTED")
        try:
            verdict = run_predeploy(baseline_path, fixture_head(config))
            assert verdict["verdict"] == "FAIL", f"{kind}:{target}"
            assert any(
                reason["code"] in (FAIL_MISSING_PROOF, FAIL_UNSNAPSHOTTED_INPUTS)
                for reason in verdict["reasons"]
            ), (kind, target, verdict["reasons"])
        finally:
            target.write_bytes(original)

    # The baseline envelope itself is a receipt too.
    baseline_path.write_text("{corrupt json", encoding="utf-8")
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_INVALID_BASELINE for reason in verdict["reasons"])


def test_deleting_any_single_receipt_makes_predeploy_fail(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    envelope = json.loads(baseline_path.read_text(encoding="utf-8"))
    for kind, record in list(predeploy._iter_captured_files(envelope))[:3]:
        target = Path(record["path"])
        target.unlink()
        verdict = run_predeploy(baseline_path, fixture_head(config))
        assert verdict["verdict"] == "FAIL", kind
        assert any(reason["code"] == FAIL_MISSING_PROOF for reason in verdict["reasons"])
        target.write_bytes(b"restored\n")


# ── mixed versions ──────────────────────────────────────────────────────────


def test_mixed_versions_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path, other_head=True)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_MIXED_VERSIONS for reason in verdict["reasons"])


def test_source_sha_must_match_manifest_head(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    other = _git(config.git_root, "rev-parse", "HEAD")
    verdict = run_predeploy(baseline_path, other)
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_MIXED_VERSIONS for reason in verdict["reasons"])


# ── selectors ───────────────────────────────────────────────────────────────


def test_selector_env_var_fails(tmp_path: Path, monkeypatch) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    monkeypatch.setenv("MEGAPLAN_RUNTIME_SRC", "/tmp/retired")
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_SELECTORS for reason in verdict["reasons"])


def test_selector_in_launch_path_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path, selector_in_wrapper=True)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_SELECTORS for reason in verdict["reasons"])


# ── editable installs ───────────────────────────────────────────────────────


def test_venv_inside_runtime_root_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path, venv_in_root=True)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_EDITABLE_INSTALL for reason in verdict["reasons"])


def test_missing_dependency_generation_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path, no_generation=True)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_EDITABLE_INSTALL for reason in verdict["reasons"])


# ── ledger bypass ───────────────────────────────────────────────────────────


def test_unproven_state_write_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path, include_unproven_state=True)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_LEDGER_BYPASS for reason in verdict["reasons"])


# ── unsnapshotted initiative inputs ─────────────────────────────────────────


def test_initiative_input_drift_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    north_star = config.initiative_dir / "NORTHSTAR.md"
    original = north_star.read_bytes()
    north_star.write_bytes(original + b"\n# changed after baseline\n")
    try:
        verdict = run_predeploy(baseline_path, fixture_head(config))
        assert verdict["verdict"] == "FAIL"
        assert any(
            reason["code"] == FAIL_UNSNAPSHOTTED_INPUTS for reason in verdict["reasons"]
        )
    finally:
        north_star.write_bytes(original)


# ── reconcile ref drift ─────────────────────────────────────────────────────


def test_reconcile_ref_drift_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    git_root = config.git_root
    (git_root / "drift.txt").write_text("drift\n", encoding="utf-8")
    _git(git_root, "add", "drift.txt")
    _git(git_root, "commit", "-m", "drift")
    _git(git_root, "branch", "-f", "fixer/f1")
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_MISSING_PROOF for reason in verdict["reasons"])
    assert any(
        "reconcile" in item for item in verdict["checks"]["source_proof"]["reconcile_ref_drift"]
    )


# ── torn capture ────────────────────────────────────────────────────────────


def test_torn_baseline_fails(tmp_path: Path, monkeypatch) -> None:
    config, ws = build_fixture(tmp_path)
    original = baseline._cursor
    calls: dict[str, int] = {}

    def flaky(path: Path) -> dict[str, int]:
        key = str(path)
        calls[key] = calls.get(key, 0) + 1
        cursor = original(path)
        if key.endswith("chain-c511d8baf7d7.json") and calls[key] == 2:
            return {**cursor, "size": cursor["size"] + 1}
        return cursor

    monkeypatch.setattr(baseline, "_cursor", flaky)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_INCOHERENT_CAPTURE for reason in verdict["reasons"])


# ── non-canonical actions ───────────────────────────────────────────────────


def test_non_canonical_action_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    _write(
        ws / ".megaplan" / "repair-queue" / "requests" / "x-1.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "raw_state_write",
                "request_id": "req-x",
                "created_at": "2026-08-13T00:00:00Z",
            }
        ),
    )
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_NON_CANONICAL_ACTION for reason in verdict["reasons"])


# ── receipt effect (the only allowed predeploy write) ───────────────────────


def test_verdict_receipt_written_on_pass(tmp_path: Path, capsys) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    evidence = ws / "evidence"
    exit_code = predeploy.main(
        [
            "--baseline", str(baseline_path),
            "--source-sha", fixture_head(config),
            "--evidence-dir", str(evidence),
        ]
    )
    assert exit_code == 0
    receipt = evidence / VERDICT_RECEIPT_NAME
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["schema"] == PREDEPLOY_SCHEMA
    assert payload["verdict"] == "PASS"
    assert payload["reasons"] == []
    capsys.readouterr()


def test_fail_verdict_receipt_still_written(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path, include_unproven_state=True)
    baseline_path = _capture_to(config, ws)
    evidence = ws / "evidence"
    exit_code = predeploy.main(
        [
            "--baseline", str(baseline_path),
            "--source-sha", fixture_head(config),
            "--evidence-dir", str(evidence),
        ]
    )
    assert exit_code == 1
    receipt = evidence / VERDICT_RECEIPT_NAME
    assert receipt.is_file()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_LEDGER_BYPASS for reason in payload["reasons"])


def test_no_write_collector_mode_performs_zero_effects(tmp_path: Path, capsys) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    evidence = ws / "evidence"
    before = {
        str(path): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    exit_code = predeploy.main(
        [
            "--baseline", str(baseline_path),
            "--source-sha", fixture_head(config),
            "--evidence-dir", str(evidence),
            "--no-write",
        ]
    )
    assert exit_code == 0
    after = {
        str(path): path.read_bytes()
        for path in sorted(tmp_path.rglob("*"))
        if path.is_file()
    }
    assert before == after, "--no-write must not create any file"
    printed = json.loads(capsys.readouterr().out)
    assert printed["verdict"] == "PASS"
    assert not (evidence / VERDICT_RECEIPT_NAME).exists()


# ── G13: pinned target, stale session, source-sha binding, torn envelope ───


def test_source_sha_not_resolvable_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, "f" * 40)
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_SOURCE_SHA for reason in verdict["reasons"])


def test_source_sha_bound_to_working_tree(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    # A tracked file drifting from the source commit must not pass.
    git_root = config.git_root
    readme = git_root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "# dirty\n", encoding="utf-8")
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_SOURCE_SHA for reason in verdict["reasons"])
    assert "working tree differs" in verdict["checks"]["source_sha_bound"]["detail"]["error"]


def test_wrong_session_pin_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config), session="other-session")
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_NOT_PINNED for reason in verdict["reasons"])


def test_wrong_plan_pin_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config), plan="other-plan")
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_NOT_PINNED for reason in verdict["reasons"])


def test_stale_session_verdict_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    config = dataclasses.replace(config, now="2030-01-01T00:00:00.000000Z")
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_STALE_SESSION for reason in verdict["reasons"])


def test_torn_envelope_file_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    # Simulate a torn envelope left by a crash between the tmp write and the
    # rename: the destination holds truncated JSON.
    baseline_path.write_text(
        '{"schema": "arnold.megaplan.fixer_recovery_baseline.v1", "baseline_id": "sha',
        encoding="utf-8",
    )
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_INVALID_BASELINE for reason in verdict["reasons"])


# ── G13 round 2: gate tooling pinned in the source SHA + pip residue ───────


def test_source_sha_must_contain_gate_tooling(tmp_path: Path) -> None:
    """A pin whose commit does NOT contain the gate scripts is unbound
    (``git diff --quiet`` alone cannot see untracked/later-added files)."""
    config, ws = build_fixture(tmp_path)
    baseline_path = _capture_to(config, ws)
    git_root = config.git_root
    _git(git_root, "rm", "-r", "--quiet", "scripts")
    _git(git_root, "commit", "-m", "drop gate tooling")
    dropped_sha = _git(git_root, "rev-parse", "HEAD")
    verdict = run_predeploy(baseline_path, dropped_sha)
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_SOURCE_SHA for reason in verdict["reasons"])
    detail = verdict["checks"]["source_sha_bound"]["detail"]
    assert "does not contain the gate tooling" in detail["error"]
    assert set(detail["missing_gate_files"]) == set(predeploy.SOURCE_SHA_GATE_FILES)


def test_pip_editable_residue_alone_fails(tmp_path: Path) -> None:
    """``pip install -e`` residue in a launch-path file fails the verdict even
    when every other editable-install/venv/selector check is clean."""
    config, ws = build_fixture(tmp_path, editable_residue_in_schedule=True)
    baseline_path = _capture_to(config, ws)
    envelope = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert envelope["editable_residue"]["hits"], "fixture must produce residue hits"
    assert envelope["selectors"]["hits"] == []
    verdict = run_predeploy(baseline_path, fixture_head(config))
    assert verdict["verdict"] == "FAIL"
    assert any(reason["code"] == FAIL_EDITABLE_INSTALL for reason in verdict["reasons"])


def test_repo_relative_briefs_predeploy_passes(tmp_path: Path) -> None:
    """The LIVE chain.yaml shape (repo-relative idea) captures AND predeploys:
    this is the exact blocker that stopped T-0610 from emitting a G13 PASS."""
    config, ws = build_fixture(tmp_path)
    head = _git(config.git_root, "rev-parse", "HEAD~1")
    (config.initiative_dir / "briefs" / "m1.md").unlink()
    repo_brief = (
        config.git_root
        / ".megaplan"
        / "initiatives"
        / "megaplan-maintenance"
        / "briefs"
        / "m1.md"
    )
    _write(repo_brief, "# M1 repo-relative brief\n")
    _write(
        config.initiative_dir / "chain.yaml",
        f"""base_branch: main
milestones:
- label: m1
  idea: .megaplan/initiatives/megaplan-maintenance/briefs/m1.md
driver:
  intended_initiative_revision: {head}
""",
    )
    baseline_path = _capture_to(config, ws)
    verdict = run_predeploy(baseline_path, head, git_root=config.git_root)
    assert verdict["verdict"] == "PASS"
    assert verdict["reasons"] == []
