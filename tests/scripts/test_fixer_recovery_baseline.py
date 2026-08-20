"""Focused tests for scripts/fixer_recovery_baseline.py (T-0601 collector)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import fixer_recovery_baseline as baseline
from scripts.fixer_recovery_baseline import (
    BASELINE_SCHEMA,
    BaselineConfig,
    BaselineError,
    CANONICAL_ACTIONS,
    capture_baseline,
    classify_queue_record,
    main as baseline_main,
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
    extra_queue_kind: str | None = None,
) -> tuple[BaselineConfig, Path]:
    """Build one complete, coherent live-state fixture; returns (config, ws).

    Layout mirrors the live box: the chain store and plan state live under
    the epic worktree (``<ws>/megaplan-maintenance/Arnold/.megaplan/...``),
    the per-epic runtime manifest at workspace level
    (``<ws>/.megaplan/megaplan-maintenance.json``), and session markers in
    ``<ws>/.megaplan/cloud-sessions``.  The fixture git repo has two commits;
    ``head`` is the initial commit (a real SHA) unless ``other_head`` is set.
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

    # ── initiative inputs (chain.yaml + NORTHSTAR.md + chain briefs) ──────
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

    # ── chain store (epic worktree) ───────────────────────────────────────
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

    # ── cloud-session marker (workspace level) ────────────────────────────
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

    # ── runtime root + launch wrapper ──────────────────────────────────────
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
    # T-0301 shared generation venv OUTSIDE the runtime root.
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

    # ── plan state (ledger): one writer-proven, one CAS-proven ─────────────
    # Scoped to the pinned plan's directory (rglob state.json).  Each state
    # declares its own plan name + chain linkage so the content identity
    # check (not just the directory name) passes.
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

    # ── repair queue (canonical request/join/reclaim + receipts + index) ───
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
    if extra_queue_kind is not None:
        _write(
            ws / ".megaplan" / "repair-queue" / "requests" / "x-1.json",
            json.dumps(
                {
                    "schema_version": 1,
                    "kind": extra_queue_kind,
                    "request_id": "req-x",
                    "created_at": "2026-08-13T00:00:00Z",
                }
            ),
        )

    # ── schedules ──────────────────────────────────────────────────────────
    _write(
        ws / "arnold" / ".megaplan" / "resident" / "scheduled_jobs" / "hourly.json",
        json.dumps({"job": "superfixer_proactive", "state": "cancelled", "keep_cancelled": True}),
    )
    _write(
        ws / ".megaplan" / "ops" / "schedules" / "ops.json",
        json.dumps({"job": "ops", "state": "cancelled"}),
    )
    _write(
        ws / ".megaplan" / "schedule-inputs" / "input-1" / "SKILL.md",
        "# input\n",
    )

    # ── reconcile receipts + branch refs ───────────────────────────────────
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


def _file_snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


# ── coherent envelope ───────────────────────────────────────────────────────


def test_capture_produces_coherent_envelope(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    head = _git(config.git_root, "rev-parse", "HEAD~1")
    envelope = capture_baseline(config)

    assert envelope["schema"] == BASELINE_SCHEMA
    assert envelope["collector_mode"] is True
    assert envelope["baseline_id"] == envelope["root"]["content_sha256"]
    assert envelope["root"]["coherent"] is True
    assert envelope["overlaps"] == []
    assert envelope["router"]["canonical_only"] is True
    assert envelope["router"]["violations"] == []
    assert set(envelope["sources"]) == {"chain", "session", "runtime", "queue", "schedule", "reconcile"}
    assert envelope["initiative"]["initiative_revision"] == head
    assert envelope["root"]["lineage"]["engine"] == [head]

    # The envelope pins EXACTLY the G13 session/plan/chain record.
    assert envelope["pinned"] == {
        "session": "megaplan-maintenance",
        "plan": "m1-containment-and-truthful-20260811-0640",
        "chain_record": "chain-c511d8baf7d7.json",
    }
    assert envelope["sources"]["session"]["sessions"] == ["megaplan-maintenance"]
    assert envelope["sources"]["session"]["classification"]["status"] == "current"
    assert envelope["sources"]["chain"]["chain_record"] == "chain-c511d8baf7d7.json"
    assert envelope["sources"]["chain"]["resolved_from"] == "named"
    assert any(
        config.plan in record["path"]
        for record in envelope["ledger"]["files"]
    )

    # Every captured file has a real path with a content address.
    for source in ("chain", "session", "runtime", "queue", "schedule", "reconcile"):
        assert envelope["sources"][source]["files"], source
    assert all(
        record["content_sha256"].startswith("sha256:")
        for source in ("chain", "session", "runtime", "queue", "schedule", "reconcile")
        for record in envelope["sources"][source]["files"]
    )
    # The repair queue routed exactly the canonical actions.
    actions = {entry["action"] for entry in envelope["router"]["actions"]}
    assert actions <= CANONICAL_ACTIONS
    assert envelope["router"]["receipts"], "the attempt receipt must be captured"
    assert all(not record["torn"] for record in envelope["windows"].values())
    assert envelope["selectors"]["hits"] == []
    assert envelope["editable_residue"]["hits"] == []
    assert envelope["ledger"]["violations"] == []
    assert ws.is_dir()


def test_capture_is_replayable_and_content_addressed(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    first = capture_baseline(config)
    second = capture_baseline(config)
    assert first["baseline_id"] == second["baseline_id"]
    assert first["root"]["content_sha256"] == second["root"]["content_sha256"]
    # Identical except the capture timestamp (which is outside the digest).
    first_no_time = {key: value for key, value in first.items() if key != "captured_at"}
    second_no_time = {key: value for key, value in second.items() if key != "captured_at"}
    assert first_no_time == second_no_time


def test_collector_mode_performs_zero_effects(tmp_path: Path, capsys) -> None:
    config, ws = build_fixture(tmp_path)
    before = _file_snapshot(tmp_path)
    args = [
        "--session", config.session,
        "--plan", config.plan,
        "--workspace", str(config.workspace),
        "--initiative-dir", str(config.initiative_dir),
        "--chain-store", str(config.chain_store),
        "--marker-dir", str(config.marker_dirs[0]),
        "--runtime-manifest", str(config.runtime_manifest),
        "--repair-queue", str(config.repair_queue),
        "--plan-state-dir", str(config.plan_state_dir),
        "--schedule-dir", str(config.schedule_dirs[0]),
        "--schedule-dir", str(config.schedule_dirs[1]),
        "--schedule-dir", str(config.schedule_dirs[2]),
        "--reconcile-dir", str(config.reconcile_dir),
        "--reconcile-ref", "refs/heads/fixer/*",
        "--reconcile-ref", "refs/heads/reconcile/*",
        "--reconcile-ref", "refs/heads/editible-install",
        "--git-root", str(config.git_root),
    ]
    exit_code = baseline_main(args)
    assert exit_code == 0
    after = _file_snapshot(tmp_path)
    assert before == after, "collector mode must not create/modify/remove any file"
    printed = json.loads(capsys.readouterr().out)
    assert printed["collector_mode"] is True
    assert printed["baseline_id"] == printed["root"]["content_sha256"]


# ── half-open cursored windows ──────────────────────────────────────────────


def test_windows_are_half_open_cursored_and_disjoint(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    envelope = capture_baseline(config)

    all_paths: list[str] = []
    for source, window in envelope["windows"].items():
        assert window["schema"].endswith("fixer_recovery_window.v1")
        assert window["torn"] is False
        assert window["ordered"] is True
        assert window["file_count"] >= 0
        if source == "ledger":
            files = envelope["ledger"]["files"]
        elif source == "initiative":
            files = envelope["initiative"]["files"]
        else:
            files = envelope["sources"][source]["files"]
        for record in files:
            assert record["stable"] is True
            # Half-open [start, end): the end cursor is the exclusive horizon
            # and must be >= the start cursor for the same file.
            start, end = record["start"], record["end"]
            assert (start["mtime_ns"], start["size"], start["ino"]) <= (
                end["mtime_ns"],
                end["size"],
                end["ino"],
            )
            all_paths.append(record["path"])
    assert len(all_paths) == len(set(all_paths)), "windows must not overlap"


def test_torn_read_flags_window_and_breaks_coherence(
    tmp_path: Path, monkeypatch
) -> None:
    config, _ws = build_fixture(tmp_path)
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
    envelope = capture_baseline(config)
    assert envelope["windows"]["chain"]["torn"] is True
    assert envelope["root"]["coherent"] is False


def test_overlapping_windows_are_detected() -> None:
    shared = {"path": "/tmp/shared.json", "content_sha256": "sha256:x",
              "start": {"mtime_ns": 1, "size": 1, "ino": 1},
              "end": {"mtime_ns": 1, "size": 1, "ino": 1}, "stable": True}
    window = {"schema": "w", "start": shared["start"], "end": shared["end"],
              "torn": False, "ordered": True, "file_count": 1}
    sources = {
        "initiative": {"files": [shared]},
        "chain": {"files": [shared]},
        "session": {"files": []},
        "runtime": {"files": []},
        "queue": {"files": []},
        "schedule": {"files": []},
        "reconcile": {"files": []},
    }
    envelope = baseline._build_envelope(
        BaselineConfig(collector=True),
        sources=sources,
        windows={
            "initiative": window,
            "chain": window,
            "session": window,
            "runtime": window,
            "queue": window,
            "schedule": window,
            "reconcile": window,
            "ledger": window,
        },
        router={"schema": "r", "canonical_only": True, "violations": [], "actions": [], "receipts": [], "index_records": []},
        ledger={"files": [], "violations": [], "missing": []},
        initiative_revision=SHA,
        engine_lineage=[SHA],
    )
    assert envelope["overlaps"], "shared paths across windows must be flagged"
    assert envelope["root"]["coherent"] is False


# ── canonical router ────────────────────────────────────────────────────────


def test_classify_queue_record_vocabulary() -> None:
    assert classify_queue_record({"kind": "repair_request"}) == ("action", "request")
    assert classify_queue_record({"kind": "repair_request_decision"}) == ("action", "join")
    assert classify_queue_record({"kind": "repair_request_attempt"}) == ("receipt", "attempt")
    assert classify_queue_record({"kind": "occurrence_claim", "action": "reclaim"}) == ("action", "reclaim")
    assert classify_queue_record({"kind": "active_repair_request_claim"}) == ("action", "join")
    assert classify_queue_record({"schema": "claim-alias/v1"}) == ("index", "index")
    assert classify_queue_record({"kind": "raw_state_write"})[0] == "violation"


def test_router_rejects_non_canonical_action(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path, extra_queue_kind="raw_state_write")
    envelope = capture_baseline(config)
    assert envelope["router"]["canonical_only"] is False
    assert any(
        violation["reason"] == "non_canonical_action"
        for violation in envelope["router"]["violations"]
    )
    assert envelope["root"]["coherent"] is False


def test_router_rejects_dangling_reference(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)

    _write(
        ws / ".megaplan" / "repair-queue" / "decisions" / "d-ghost.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "repair_request_decision",
                "decision_id": "dec-ghost",
                "request_id": "req-ghost",
                "decision": "accepted",
                "created_at": "2026-08-13T00:00:00Z",
            }
        ),
    )
    envelope = capture_baseline(config)
    assert any(
        violation["reason"] == "missing_request_reference"
        for violation in envelope["router"]["violations"]
    )


def test_router_rejects_claim_without_accepted_decision(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)

    _write(
        ws / ".megaplan" / "repair-queue" / "requests" / "r-2.json",
        json.dumps(
            {
                "schema_version": 1,
                "kind": "repair_request",
                "request_id": "req-2",
                "created_at": "2026-08-13T00:00:00Z",
            }
        ),
    )
    _write(
        ws / ".megaplan" / "repair-queue" / "active-claims" / "beef.lock" / "owner.json",
        json.dumps(
            {
                "kind": "active_repair_request_claim",
                "schema_version": 1,
                "request_id": "req-2",
                "actor": "fixer",
                "session": "megaplan-maintenance",
            }
        ),
    )
    envelope = capture_baseline(config)
    assert any(
        violation["reason"] == "claim_without_accepted_decision"
        for violation in envelope["router"]["violations"]
    )


# ── capture facts surfaced for the verdict ──────────────────────────────────


def test_selector_hits_are_recorded(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path, selector_in_wrapper=True)
    envelope = capture_baseline(config)
    assert any(
        hit["token"] == "MEGAPLAN_RUNTIME_SRC"
        for hit in envelope["selectors"]["hits"]
    )


def test_runtime_editable_facts_are_recorded(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path, venv_in_root=True)
    envelope = capture_baseline(config)
    assert envelope["sources"]["runtime"]["runtime_venv_present"] is True
    assert (
        envelope["sources"]["runtime"]["parsed"]["epic"]["venv_path"]
        .endswith("/runtime/arnold-main/.venv")
    )


def test_capture_fails_closed_on_missing_required_source(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    (config.initiative_dir / "chain.yaml").unlink()
    with pytest.raises(BaselineError, match="chain.yaml"):
        capture_baseline(config)


# ── G13: exact live session/plan pinning + live-box defaults ───────────────


def test_session_and_plan_required_on_cli() -> None:
    with pytest.raises(SystemExit):
        baseline_main(["--workspace", "/tmp/nowhere"])


def test_live_defaults_pin_exact_session_plan_and_layout() -> None:
    defaults = BaselineConfig()
    assert defaults.session == "megaplan-maintenance"
    assert defaults.plan == "m1-containment-and-truthful-20260811-0640"
    assert defaults.chain_record == "chain-c511d8baf7d7.json"
    # Blocker 2: advertised live-box defaults must match the live layout.
    assert defaults.chain_store == Path(
        "/workspace/megaplan-maintenance/Arnold/.megaplan/plans/.chains"
    )
    assert defaults.runtime_manifest == Path("/workspace/.megaplan/megaplan-maintenance.json")
    assert defaults.plan_state_dir == Path(
        "/workspace/megaplan-maintenance/Arnold/.megaplan/plans/"
        "m1-containment-and-truthful-20260811-0640"
    )


def test_capture_resolves_exact_marker_plan_state_and_chain(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    envelope = capture_baseline(config)
    assert envelope["sources"]["session"]["sessions"] == [config.session]
    assert envelope["sources"]["session"]["classification"]["status"] == "current"
    assert envelope["sources"]["chain"]["chain_record"] == config.chain_record
    assert envelope["sources"]["chain"]["resolved_from"] == "named"
    ledger_paths = [record["path"] for record in envelope["ledger"]["files"]]
    assert any(config.plan in path for path in ledger_paths)


def test_extra_session_identity_in_lineage_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    # A marker whose filename carries the pinned session but whose content
    # declares a DIFFERENT session would leak a foreign identity into the
    # captured lineage -> fail-closed.
    _write(
        ws / ".megaplan" / "cloud-sessions" / "megaplan-maintenance-extra.json",
        json.dumps({"session": "some-other-session"}),
    )
    with pytest.raises(BaselineError, match="leak"):
        capture_baseline(config)


def test_missing_session_marker_fails(tmp_path: Path) -> None:
    config, ws = build_fixture(tmp_path)
    (ws / ".megaplan" / "cloud-sessions" / "megaplan-maintenance.json").unlink()
    with pytest.raises(BaselineError, match="session"):
        capture_baseline(config)


def test_missing_plan_state_fails(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    shutil.rmtree(config.plan_state_dir)
    with pytest.raises(BaselineError, match="plan"):
        capture_baseline(config)


def test_plan_identity_mismatch_fails(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    config = dataclasses.replace(config, plan="some-other-plan")
    with pytest.raises(BaselineError, match="plan"):
        capture_baseline(config)


def test_stale_session_is_classified_stale(tmp_path: Path) -> None:
    config, _ws = build_fixture(tmp_path)
    config = dataclasses.replace(config, now="2030-01-01T00:00:00.000000Z")
    envelope = capture_baseline(config)
    classification = envelope["sources"]["session"]["classification"]
    assert classification["status"] == "stale"
    assert classification["latest_source"].endswith(":mtime")


# ── G13: atomic --out write (crash can never tear the envelope) ────────────


def test_out_write_is_atomic_under_crash(tmp_path: Path, monkeypatch) -> None:
    config, ws = build_fixture(tmp_path)
    out = ws / "evidence" / "baseline.json"
    args = [
        "--session", config.session,
        "--plan", config.plan,
        "--workspace", str(config.workspace),
        "--initiative-dir", str(config.initiative_dir),
        "--chain-store", str(config.chain_store),
        "--marker-dir", str(config.marker_dirs[0]),
        "--runtime-manifest", str(config.runtime_manifest),
        "--repair-queue", str(config.repair_queue),
        "--plan-state-dir", str(config.plan_state_dir),
        "--schedule-dir", str(config.schedule_dirs[0]),
        "--schedule-dir", str(config.schedule_dirs[1]),
        "--schedule-dir", str(config.schedule_dirs[2]),
        "--reconcile-dir", str(config.reconcile_dir),
        "--reconcile-ref", "refs/heads/fixer/*",
        "--reconcile-ref", "refs/heads/reconcile/*",
        "--reconcile-ref", "refs/heads/editible-install",
        "--git-root", str(config.git_root),
        "--out", str(out),
    ]
    assert baseline_main(args) == 0
    original = out.read_bytes()
    assert not list((ws / "evidence").glob("*.tmp"))

    def crash(src, dst):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(os, "replace", crash)
    with pytest.raises(RuntimeError, match="simulated crash"):
        baseline_main(args)
    # The final path must still hold the complete, valid first envelope.
    assert out.read_bytes() == original
    monkeypatch.undo()
    assert baseline_main(args) == 0
    assert not list((ws / "evidence").glob("*.tmp"))
    json.loads(out.read_text(encoding="utf-8"))


# ── G13 round 2: repo-relative briefs, lease-aware staleness, schedule
# ── tolerance, content-based plan identity ─────────────────────────────────


def test_repo_relative_brief_resolution_passes(tmp_path: Path) -> None:
    """Live chain.yaml shape: idea paths are REPO-RELATIVE (git_root / idea).

    The chain engine resolves ``idea`` as ``git_root / idea``
    (chain/__init__.py:_resolve_idea_path); capture must do the same BEFORE
    falling back to ``initiative_dir / idea``.
    """
    config, _ws = build_fixture(tmp_path)
    head = _git(config.git_root, "rev-parse", "HEAD~1")
    # Remove the initiative-relative brief so ONLY the git-root form resolves.
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
anchors:
  north_star: NORTHSTAR.md
milestones:
- label: m1
  idea: .megaplan/initiatives/megaplan-maintenance/briefs/m1.md
  profile: partnered-5
  vendor: codex
driver:
  robustness: full
  auto_approve: false
  intended_initiative_revision: {head}
  initiative_path: {config.initiative_dir}
""",
    )
    envelope = capture_baseline(config)
    brief_paths = [record["path"] for record in envelope["initiative"]["files"]]
    assert str(repo_brief.resolve(strict=False)) in brief_paths
    assert envelope["initiative"]["initiative_revision"] == head


def test_both_brief_resolutions_miss_fails(tmp_path: Path) -> None:
    """An idea resolving under NEITHER git_root NOR the initiative dir fails."""
    config, _ws = build_fixture(tmp_path)
    head = _git(config.git_root, "rev-parse", "HEAD~1")
    _write(
        config.initiative_dir / "chain.yaml",
        f"""base_branch: main
milestones:
- label: m1
  idea: briefs/ghost.md
driver:
  intended_initiative_revision: {head}
""",
    )
    with pytest.raises(BaselineError, match="brief missing"):
        capture_baseline(config)


def test_parked_but_leased_session_is_current(tmp_path: Path) -> None:
    """A parked session with a CURRENT live lease is current despite an old
    marker mtime (the lease IS the liveness signal)."""
    config, ws = build_fixture(tmp_path)
    marker = ws / ".megaplan" / "cloud-sessions" / "megaplan-maintenance.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["liveness_claimed_at"] = "2026-08-11T00:00:00.000000Z"
    payload["updated_at"] = "2026-08-11T00:00:00.000000Z"
    marker.write_text(json.dumps(payload), encoding="utf-8")
    old = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)
    os.utime(marker, (old.timestamp(), old.timestamp()))
    # Live runner-lease sidecar: future expiry encoded as Unix epoch seconds
    # (invisible to the ISO-only generic liveness walk) + status live.
    lease_path = (
        ws
        / ".megaplan"
        / "cloud-sessions"
        / "megaplan-maintenance.liveness-lease.json"
    )
    _write(
        lease_path,
        json.dumps(
            {
                "schema": "arnold.megaplan.runner_liveness_lease.v2",
                "session": "megaplan-maintenance",
                "run_kind": "chain",
                "run_id": "r1",
                "lease_id": "lease-1",
                "runner_fence": 7,
                "sequence": 1,
                "status": "live",
                "generated_at": "2026-08-11T00:00:00.000000Z",
                "expires_at": int((old + timedelta(days=30)).timestamp()),
            }
        ),
    )
    os.utime(lease_path, (old.timestamp(), old.timestamp()))
    config = dataclasses.replace(
        config,
        now="2026-08-13T00:00:00.000000Z",
        session_stale_after=3600.0,
    )
    envelope = capture_baseline(config)
    classification = envelope["sources"]["session"]["classification"]
    assert classification["status"] == "current"
    assert classification["lease_alive"] is True
    assert classification["lease_expires_at"] is not None


def test_absent_optional_schedule_dir_is_recorded_not_failed(tmp_path: Path) -> None:
    """Absent default schedule dirs on the box are recorded, not a failure."""
    config, ws = build_fixture(tmp_path)
    optional = ws / ".megaplan" / "schedule-inputs"
    shutil.rmtree(optional)
    envelope = capture_baseline(config)
    assert envelope["sources"]["schedule"]["missing"] == [
        str(optional.resolve(strict=False))
    ]
    assert envelope["sources"]["schedule"]["files"], "present stores still captured"


def test_missing_required_schedule_dir_fails(tmp_path: Path) -> None:
    """The REQUIRED schedule (the first / megaplan-maintenance store) must
    resolve; its absence is a failure."""
    config, _ws = build_fixture(tmp_path)
    shutil.rmtree(config.schedule_dirs[0])
    with pytest.raises(BaselineError, match="required schedule"):
        capture_baseline(config)


def test_swapped_state_in_correctly_named_dir_fails_identity(tmp_path: Path) -> None:
    """A foreign state.json swapped into the correctly named plan dir must
    NOT pass identity: the directory name is only the capture scope, the
    plan-name field (and chain linkage) must match the pinned plan."""
    config, _ws = build_fixture(tmp_path)
    _write(
        config.plan_state_dir / "state.json",
        json.dumps({"name": "some-other-plan", "metadata": {}, "phase": "done"}),
    )
    with pytest.raises(BaselineError, match="plan identity"):
        capture_baseline(config)


def test_state_declaring_wrong_chain_linkage_fails_identity(tmp_path: Path) -> None:
    """A captured state declaring a chain linkage that contradicts the pinned
    chain fails identity even when its plan name matches."""
    config, _ws = build_fixture(tmp_path)
    _write(
        config.plan_state_dir / "state.json",
        json.dumps(
            {
                "name": config.plan,
                "chain": "some-other-chain",
                "metadata": {"writer": "megaplan.chain.wbc.advance"},
                "phase": "done",
            }
        ),
    )
    with pytest.raises(BaselineError, match="plan identity"):
        capture_baseline(config)
