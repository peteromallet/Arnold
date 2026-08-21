from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MUTATION_CAPABILITY_SCHEMA,
    SCHEMA,
    MutationCapability,
    MutationDenied,
    attach_mutation_capability,
    control_liveness_from_current_target,
    mint_mutation_capability,
    observe_current_target_liveness,
    require_mutation_capability,
    resolve_mutation_capability,
)
from arnold_pipelines.megaplan.cloud.engine_runtime_repair import (
    ENGINE_RUNTIME_EFFECT_CLASS,
    ENGINE_RUNTIME_REPAIR_SCHEMA,
    SOURCE_REPAIR_SCOPE,
    validate_engine_runtime_repair_admission,
)
from arnold_pipelines.megaplan.cloud.progress_auditor_liveness import (
    classify_runner_liveness,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert_disposable_root(root: Path) -> Path:
    resolved = root.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    project_root = REPO_ROOT
    assert resolved != project_root
    assert "runtime-candidates" not in resolved.parts
    # A pytest tmp dir may live under the worktree when TMPDIR is redirected.
    # That is still disposable unless it *is* the project, a candidate, or a
    # live runtime root that contains the package.
    assert not (resolved / "arnold_pipelines" / "megaplan").exists()
    sentinel = resolved / ".t41-disposable-root"
    sentinel.write_text("disposable\n", encoding="utf-8")
    return resolved


def _digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _complete_evidence(
    tmp_path: Path,
    *,
    action: str = "repair",
    occurrence: str = "occ-1",
    cursor: str = "cursor-1",
    fence_epoch: int = 3,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    root = _assert_disposable_root(tmp_path / "live-import-root")
    interpreter = tmp_path / "generation" / "bin" / "python"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    target = "target-1"
    payload: dict[str, object] = {
        "occurrence": occurrence,
        "target": target,
        "cursor": cursor,
        "fence_epoch": fence_epoch,
        "evidence_digest": _digest({"occurrence": occurrence, "cursor": cursor}),
        "scope": action,
        "custody": f"custody:{occurrence}",
        "import_root": str(root),
        "interpreter": str(interpreter),
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(root),
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    if extra:
        payload.update(extra)
    return payload


def _mint(
    tmp_path: Path,
    *,
    action: str = "repair",
    extra: dict[str, object] | None = None,
    **kwargs: object,
) -> MutationCapability:
    evidence = _complete_evidence(tmp_path, action=action, extra=extra)
    live_root = Path(str(evidence["import_root"]))
    interpreter = Path(str(evidence["interpreter"]))
    return mint_mutation_capability(
        action=action,
        evidence=evidence,
        process_root=live_root,
        process_python=interpreter,
        **kwargs,  # type: ignore[arg-type]
    )


def test_permission_truth_table(tmp_path: Path) -> None:
    cases = [
        ("repair", True),
        ("retrigger", True),
        ("escalation", True),
        ("engine_runtime", True),
        ("recover-blocked", True),
    ]
    for action, ok in cases:
        cap = _mint(tmp_path / action, action=action)
        assert isinstance(cap, MutationCapability)
        assert cap.action == action
        assert cap.schema == MUTATION_CAPABILITY_SCHEMA
        require_mutation_capability(cap, action=action, scope=action)
        assert ok is True

    with pytest.raises(MutationDenied) as missing:
        mint_mutation_capability(action="repair", evidence=None)
    assert missing.value.code == "evidence_missing"

    incomplete = _complete_evidence(tmp_path / "incomplete")
    incomplete.pop("occurrence")
    with pytest.raises(MutationDenied) as inc:
        mint_mutation_capability(
            action="repair",
            evidence=incomplete,
            process_root=Path(str(incomplete["import_root"])),
            process_python=Path(str(incomplete["interpreter"])),
        )
    assert inc.value.code == "identity_incomplete"


def test_stale_and_live_pid_combinations_are_diagnostic_only(tmp_path: Path) -> None:
    marker_dir = _assert_disposable_root(tmp_path / "markers")
    live = observe_current_target_liveness(
        {
            "session": "demo",
            "pid": 4242,
            "pid_namespace_id": "pid:[same]",
            "process_start_identity": "boot-a:10",
        },
        marker_dir=marker_dir,
        pid_is_live=lambda pid: True,
        process_start_identity=lambda pid: "boot-a:10",
        observer_pid_namespace_id="pid:[same]",
    )
    stale = observe_current_target_liveness(
        {
            "session": "demo",
            "pid": 4242,
            "pid_namespace_id": "pid:[same]",
            "process_start_identity": "boot-a:10",
        },
        marker_dir=marker_dir,
        pid_is_live=lambda pid: True,
        process_start_identity=lambda pid: "boot-b:99",
        observer_pid_namespace_id="pid:[same]",
    )
    dead = observe_current_target_liveness(
        {
            "session": "demo",
            "pid": 4242,
            "pid_namespace_id": "pid:[same]",
            "process_start_identity": "boot-a:10",
        },
        marker_dir=marker_dir,
        pid_is_live=lambda pid: False,
        process_start_identity=lambda pid: "boot-a:10",
        observer_pid_namespace_id="pid:[same]",
    )

    assert live["state"] == "live"
    assert stale["state"] == "dead"
    assert dead["state"] == "dead"
    for observed in (live, stale, dead):
        assert observed["mutation_permitted"] is False
        assert observed["control_permitted"] is False
        assert observed["authorizes_mutation"] is False
        control = control_liveness_from_current_target(
            {"current_target_liveness": observed}, action="mutation"
        )
        assert control["action_permitted"] is False


def test_marker_manifest_contradiction_fails_closed(tmp_path: Path) -> None:
    live = _assert_disposable_root(tmp_path / "live")
    foreign = _assert_disposable_root(tmp_path / "foreign-live")
    interpreter = tmp_path / "generation" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    evidence = {
        "occurrence": "occ-1",
        "target": "target-1",
        "cursor": "cursor-1",
        "fence_epoch": 1,
        "evidence_digest": "a" * 64,
        "scope": "repair",
        "custody": "custody:occ-1",
        "import_root": str(live),
        "interpreter": str(interpreter),
        "marker": {"import_root": str(foreign)},
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(live),
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    with pytest.raises(MutationDenied) as denied:
        mint_mutation_capability(
            action="repair",
            evidence=evidence,
            process_root=live,
            process_python=interpreter,
        )
    assert denied.value.code == "identity_contradiction"
    assert "marker_manifest_root_mismatch" in denied.value.reason


def test_stale_cursor_and_fence_fail_closed(tmp_path: Path) -> None:
    evidence = _complete_evidence(
        tmp_path / "stale",
        extra={"expected_cursor": "cursor-live", "cursor": "cursor-stale"},
    )
    with pytest.raises(MutationDenied) as cursor_denied:
        mint_mutation_capability(
            action="repair",
            evidence=evidence,
            process_root=Path(str(evidence["import_root"])),
            process_python=Path(str(evidence["interpreter"])),
        )
    assert "stale_cursor" in cursor_denied.value.reason

    evidence = _complete_evidence(
        tmp_path / "fence",
        fence_epoch=2,
        extra={"expected_fence_epoch": 5},
    )
    with pytest.raises(MutationDenied) as fence_denied:
        mint_mutation_capability(
            action="repair",
            evidence=evidence,
            process_root=Path(str(evidence["import_root"])),
            process_python=Path(str(evidence["interpreter"])),
        )
    assert "stale_fence" in fence_denied.value.reason


def test_valid_downstream_evidence_without_capability_rejects(tmp_path: Path) -> None:
    admission = {
        "schema_version": ENGINE_RUNTIME_REPAIR_SCHEMA,
        "admission_id": "admission:one",
        "effect_class": ENGINE_RUNTIME_EFFECT_CLASS,
        "repair_scope": SOURCE_REPAIR_SCOPE,
        "occurrence_fingerprint": "sha256:occurrence",
        "candidate": {
            "revision": "0123456789abcdef0123456789abcdef01234567",
            "runtime_sha256": "a" * 64,
            "verification_digest": "b" * 64,
            "provenance_digest": "c" * 64,
            "effect_barrier_digest": "d" * 64,
        },
        "authority": {
            "decision": "approved",
            "model": "gpt-5.6-sol",
            "profile": "horizon-a",
        },
        "run_authority_receipt": "run-authority:one",
        "custody_receipt": "custody:one",
        "wbc_receipt": "wbc:one",
        "fence_token": "fence:one",
        "one_effect": True,
    }
    ok, reason = validate_engine_runtime_repair_admission(
        admission, occurrence_fingerprint="sha256:occurrence"
    )
    assert ok is False
    assert "mutation requires a root MutationCapability" in reason

    with pytest.raises(MutationDenied) as denied:
        require_mutation_capability(None, action="engine_runtime")
    assert denied.value.code == "capability_absent"


def test_action_and_scope_replay_rejects(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action="repair")
    with pytest.raises(MutationDenied) as action_denied:
        require_mutation_capability(cap, action="escalation")
    assert action_denied.value.code == "action_mismatch"

    with pytest.raises(MutationDenied) as scope_denied:
        require_mutation_capability(cap, action="repair", scope="repair.other")
    assert scope_denied.value.code == "scope_mismatch"

    forged = dict(cap.to_dict())
    forged["occurrence"] = "occ-replay"
    with pytest.raises(MutationDenied) as forged_denied:
        require_mutation_capability(forged, action="repair")
    assert forged_denied.value.code == "capability_reconstructed"

    expired_evidence = _complete_evidence(tmp_path / "expired")
    expired = mint_mutation_capability(
        action="repair",
        evidence=expired_evidence,
        process_root=Path(str(expired_evidence["import_root"])),
        process_python=Path(str(expired_evidence["interpreter"])),
        now=datetime.now(timezone.utc) - timedelta(hours=2),
        ttl=timedelta(minutes=1),
    )
    with pytest.raises(MutationDenied) as expired_denied:
        require_mutation_capability(expired, action="repair")
    assert expired_denied.value.code == "capability_expired"


def test_complete_authorized_path(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action="repair")
    checked = require_mutation_capability(
        cap, action="repair", occurrence="occ-1", scope="repair"
    )
    assert checked is cap
    assert checked.custody == "custody:occ-1"
    narrowed = checked.narrow("repair")
    assert narrowed.scope == "repair"
    assert narrowed.import_root.endswith("live-import-root")
    require_mutation_capability(narrowed, action="repair", occurrence="occ-1", scope="repair")


def test_ambient_vs_seed_import_root_mismatch(tmp_path: Path) -> None:
    live = _assert_disposable_root(tmp_path / "seed-import-root")
    ambient = _assert_disposable_root(tmp_path / "ambient-live-tree")
    interpreter = tmp_path / "generation" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    evidence = {
        "occurrence": "occ-engine",
        "target": "target-engine",
        "cursor": "cursor-engine",
        "fence_epoch": 7,
        "evidence_digest": "b" * 64,
        "scope": "engine_runtime",
        "repair_scope": "engine_runtime",
        "custody": "custody:occ-engine",
        "import_root": str(live),
        "interpreter": str(interpreter),
        "ambient_engine_root": str(ambient),
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(live),
                "expected_head": "c" * 40,
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    with pytest.raises(MutationDenied) as denied:
        mint_mutation_capability(
            action="engine_runtime",
            evidence=evidence,
            process_root=live,
            process_python=interpreter,
        )
    assert denied.value.code == "ambient_engine_root_rejected"

    evidence.pop("ambient_engine_root")
    cap = mint_mutation_capability(
        action="recover-blocked",
        evidence=evidence,
        process_root=live,
        process_python=interpreter,
    )
    assert Path(cap.import_root) == live
    assert Path(cap.interpreter) == interpreter
    # SHA is telemetry, never CAS.
    assert cap.tree_sha_telemetry == "" or len(cap.tree_sha_telemetry) == 40

    with pytest.raises(MutationDenied) as mismatch:
        mint_mutation_capability(
            action="engine_runtime",
            evidence=evidence,
            process_root=ambient,
            process_python=interpreter,
        )
    assert mismatch.value.code == "import_root_mismatch"


def test_diagnostic_callers_remain_usable_when_evidence_incomplete(tmp_path: Path) -> None:
    observed = observe_current_target_liveness({}, marker_dir=tmp_path)
    assert observed["state"] == "unknown"
    assert observed["known"] is False
    control = control_liveness_from_current_target(None, action="mutation")
    assert control["state"] == "unknown"
    assert control["action_permitted"] is False
    classified = classify_runner_liveness(
        {"live_status": "dead"},
        {},
        ["terminal_repair_failure"],
        bound_observation={"schema": SCHEMA, "state": "unknown", "known": False, "live": False, "dead": False},
    )
    assert classified["state"] == "unknown"
    assert classified["control_permitted"] is False


def test_reconstructed_mapping_is_not_authority(tmp_path: Path) -> None:
    minted = _mint(tmp_path, action="repair")
    reconstructed = dict(minted.to_dict())
    with pytest.raises(MutationDenied) as denied:
        require_mutation_capability(reconstructed, action="repair")
    assert denied.value.code == "capability_reconstructed"

    with pytest.raises(MutationDenied) as ctor:
        MutationCapability(**reconstructed)
    assert ctor.value.code == "capability_reconstructed"


def test_missing_custody_fails_closed_identity_incomplete(tmp_path: Path) -> None:
    evidence = _complete_evidence(tmp_path / "no-custody")
    evidence.pop("custody")
    with pytest.raises(MutationDenied) as denied:
        mint_mutation_capability(
            action="repair",
            evidence=evidence,
            process_root=Path(str(evidence["import_root"])),
            process_python=Path(str(evidence["interpreter"])),
        )
    assert denied.value.code == "identity_incomplete"
    assert "custody" in denied.value.reason


def test_recover_blocked_live_handle_require_succeeds_mapping_rebuild_rejects(
    tmp_path: Path,
) -> None:
    fingerprint = "fp-recover-blocked-1"
    evidence = _complete_evidence(
        tmp_path / "recover-blocked",
        action="recover-blocked",
        occurrence=fingerprint,
        extra={
            "scope": "engine_runtime",
            "repair_scope": "engine_runtime",
            "target": fingerprint,
            "evidence_digest": fingerprint,
            "custody": {
                "identity": f"custody:{fingerprint}",
                "occurrence": fingerprint,
                "occurrence_fingerprint": fingerprint,
            },
        },
    )
    live_root = Path(str(evidence["import_root"]))
    interpreter = Path(str(evidence["interpreter"]))
    minted = mint_mutation_capability(
        action="recover-blocked",
        evidence=evidence,
        process_root=live_root,
        process_python=interpreter,
    )
    assert minted.custody
    assert minted.occurrence == fingerprint
    attach_mutation_capability(minted, identity=fingerprint)

    resume_cursor = {
        "phase": "critique",
        "retry_strategy": "repair_phase_contract",
        "mutation_capability": minted,
        "mutation_capability_handle": fingerprint,
    }
    checked = require_mutation_capability(
        resume_cursor,
        action="recover-blocked",
        occurrence=fingerprint,
        scope="engine_runtime",
    )
    assert checked is minted
    handle_only = require_mutation_capability(
        {"mutation_capability_handle": fingerprint},
        action="recover-blocked",
        occurrence=fingerprint,
        scope="engine_runtime",
    )
    assert handle_only is minted
    assert resolve_mutation_capability(fingerprint) is minted

    rebuilt = dict(minted.to_dict())
    with pytest.raises(MutationDenied) as denied:
        require_mutation_capability(
            rebuilt,
            action="recover-blocked",
            occurrence=fingerprint,
            scope="engine_runtime",
        )
    assert denied.value.code == "capability_reconstructed"

    from arnold_pipelines.megaplan.blocker_recovery import compact_failure_identity
    from arnold_pipelines.megaplan.cloud.engine_runtime_repair import (
        ENGINE_RUNTIME_EFFECT_CLASS,
        ENGINE_RUNTIME_REPAIR_SCHEMA,
        SOURCE_REPAIR_SCOPE,
        validate_engine_runtime_repair_admission,
    )

    latest_failure = {
        "kind": "deterministic_phase_failure",
        "phase": "critique",
        "message": "phase contract failed",
    }
    compact = compact_failure_identity(latest_failure)
    assert compact.get("fingerprint")
    # Producer custody is occurrence-bound to the compact failure fingerprint.
    producer_evidence = _complete_evidence(
        tmp_path / "producer",
        action="recover-blocked",
        occurrence=str(compact["fingerprint"]),
        extra={
            "scope": "engine_runtime",
            "repair_scope": "engine_runtime",
            "target": str(compact["fingerprint"]),
            "evidence_digest": str(compact["fingerprint"]),
            "custody": {
                "identity": f"custody:{compact['fingerprint']}",
                "occurrence": str(compact["fingerprint"]),
                "occurrence_fingerprint": str(compact["fingerprint"]),
            },
        },
    )
    producer_cap = mint_mutation_capability(
        action="recover-blocked",
        evidence=producer_evidence,
        process_root=Path(str(producer_evidence["import_root"])),
        process_python=Path(str(producer_evidence["interpreter"])),
    )
    attach_mutation_capability(producer_cap, identity=str(compact["fingerprint"]))
    required = require_mutation_capability(
        {"mutation_capability_handle": compact["fingerprint"]},
        action="recover-blocked",
        occurrence=str(compact["fingerprint"]),
        scope="engine_runtime",
    )
    assert required is producer_cap

    admission = {
        "schema_version": ENGINE_RUNTIME_REPAIR_SCHEMA,
        "admission_id": "admission:recover-blocked",
        "effect_class": ENGINE_RUNTIME_EFFECT_CLASS,
        "repair_scope": SOURCE_REPAIR_SCOPE,
        "occurrence_fingerprint": "sha256:occurrence",
        "candidate": {
            "revision": "0123456789abcdef0123456789abcdef01234567",
            "runtime_sha256": "a" * 64,
            "verification_digest": "b" * 64,
            "provenance_digest": "c" * 64,
            "effect_barrier_digest": "d" * 64,
        },
        "authority": {
            "decision": "approved",
            "model": "gpt-5.6-sol",
            "profile": "horizon-a",
        },
        "run_authority_receipt": "run-authority:one",
        "custody_receipt": "custody:one",
        "wbc_receipt": "wbc:one",
        "fence_token": "fence:one",
        "one_effect": True,
        "mutation_capability": dict(minted.to_dict()),
    }
    ok, reason = validate_engine_runtime_repair_admission(
        admission, occurrence_fingerprint="sha256:occurrence"
    )
    assert ok is False
    assert "reconstructed Mapping is not a minted MutationCapability" in reason


def test_static_search_proves_no_bypassing_in_scope_consumer() -> None:
    in_scope = {
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/current_target_liveness.py": "class MutationCapability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/cli.py": '"mutation_permitted": False',
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/supervise.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/meta_repair.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/engine_runtime_repair.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/repair_contract.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/progress_auditor_controller.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/six_hour_auditor.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/blocker_recovery.py": "require_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/handlers/override.py": "mint_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/planning/control_binding.py": "mint_mutation_capability",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog": "canonical_mutation_fenced",
    }
    out_of_scope = {
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/manual_repair_trigger.py": (
            "generic queue producer; T4.1 selected M3b/M4 mutation paths only"
        ),
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/repair_requests.py": (
            "occurrence-bound queue write; not a selected M3b/M4 mutation grant"
        ),
        REPO_ROOT / "arnold_pipelines/megaplan/auto.py": (
            "lifecycle_failure enqueue; generic queue producer, not T4.1 grant"
        ),
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/maintenance_recovery.py": (
            "allowlisted repair effects remain out of T4.1 root-grant scope"
        ),
    }
    for path, needle in in_scope.items():
        source = path.read_text(encoding="utf-8")
        assert needle in source, f"{path.name} missing {needle}"
        if path.suffix == ".py" and path.name != "current_target_liveness.py":
            tree = ast.parse(source)
            assigns_grant = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id in {
                            "mutation_permitted",
                            "action_permitted",
                        }:
                            assigns_grant = True
            assert assigns_grant is False or path.name in {
                "cli.py",
                "current_target_liveness.py",
            }
        if path.name == "arnold-watchdog":
            assert "canonical_mutation_permitted=1" not in source
            assert "minted MutationCapability" in source
            assert "babysitter/relaunch/drive require a minted MutationCapability" in source

    for path, reason in out_of_scope.items():
        assert path.exists(), f"missing out-of-scope producer {path}"
        source = path.read_text(encoding="utf-8")
        assert "mint_mutation_capability" not in source
        assert "require_mutation_capability" not in source
        assert reason

    named = {
        "manual_repair_trigger": "out_of_scope",
        "repair_requests": "out_of_scope",
        "auto.py": "out_of_scope",
        "maintenance_recovery": "out_of_scope",
        "arnold-watchdog": "in_scope",
    }
    in_scope_names = {path.name for path in in_scope}
    out_of_scope_names = {path.name for path in out_of_scope}
    assert named["arnold-watchdog"] == "in_scope"
    assert "arnold-watchdog" in in_scope_names
    for producer in ("manual_repair_trigger.py", "repair_requests.py", "auto.py", "maintenance_recovery.py"):
        assert producer in out_of_scope_names




def test_watchdog_marker_deletions_require_minted_capability_or_are_observe_only() -> None:
    """G4-004: the five rm -f sites require minted MutationCapability.

    canonical_mutation_fenced always returns 0 and is not a grant.
    No capability -> no deletion. Clearing needs-human unparks automation.
    """
    wrapper = REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    source = wrapper.read_text(encoding="utf-8")
    sites = (
        "T29-BYPASS-186B",
        "T29-BYPASS-197",
        "T29-BYPASS-198",
        "T29-BYPASS-200",
        "T29-BYPASS-201",
        "T29-BYPASS-151",
    )
    for site in sites:
        idx = source.index(site)
        window = source[max(0, idx - 400) : idx]
        assert "MUTATION_CAPABILITY_PRESENT" in window, site
        assert 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in window or 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in source[max(0, idx - 500) : idx + 80], site

    meta = source[source.index("meta_dispatch_marker_clear() {"):]
    meta = meta[: meta.index("write_partial_liveness_tick() {")]
    assert 'MUTATION_CAPABILITY_PRESENT:-0}" != "1"' in meta
    assert "observe-only without minted MutationCapability" in meta

    fence = source[source.index("canonical_mutation_fenced() {"):]
    fence = fence[: fence.index("babysitter_parked_chain_stall")]
    assert "return 0" in fence
    assert "canonical_mutation_permitted=1" not in source



def test_watchdog_five_rm_sites_are_observe_only_without_minted_capability(
    tmp_path: Path,
) -> None:
    """G4-004 behavioral: no capability -> no deletion at the five sites."""
    import subprocess
    import textwrap

    wrapper = REPO_ROOT / "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog"
    source = wrapper.read_text(encoding="utf-8")

    def _extract(name: str, until: str) -> str:
        start = source.index(f"{name}() {{")
        end = source.index(f"{until}() {{", start)
        return source[start:end]

    root = tmp_path / "g4-004"
    root.mkdir()
    session = "demo-session"
    marker_dir = root / "markers"
    repair_data_dir = marker_dir / "repair-data"
    marker_dir.mkdir()
    repair_data_dir.mkdir()
    log_path = root / "watchdog.log"
    workspace = root / "workspace"
    workspace.mkdir()
    spec = workspace / "chain.yaml"
    spec.write_text("anchors: {}\n", encoding="utf-8")
    meta_marker = marker_dir / f"{session}.meta-dispatch"
    meta_pgid = marker_dir / f"{session}.meta-pgid"
    env_gone = marker_dir / f"{session}.env-gone"
    for path, body in (
        (meta_marker, "dispatch\n"),
        (meta_pgid, "123\n"),
        (env_gone, "2\n"),
    ):
        path.write_text(body, encoding="utf-8")

    helpers = "\n".join(
        [
            _extract("safe_name", "repair_pidfile_path"),
            _extract("meta_dispatch_marker_path", "meta_pgid_path"),
            _extract("meta_pgid_path", "session_marker_path"),
            _extract("meta_dispatch_marker_clear", "write_partial_liveness_tick"),
            _extract("env_gone_sidecar_path", "environment_gone_check"),
            _extract("environment_gone_check", "persist_environment_gone_outcome"),
        ]
    )
    script = textwrap.dedent(
        f"""
        set -euo pipefail
        MARKER_DIR={str(marker_dir)!r}
        REPAIR_DATA_DIR={str(repair_data_dir)!r}
        LOG={str(log_path)!r}
        MUTATION_CAPABILITY_PRESENT=0
        ENV_GONE_STRIKES=3
        log() {{ printf '%s\\n' "$*" >>"$LOG"; }}
        authority_gap_continue() {{ return 0; }}
        {helpers}
        meta_dispatch_marker_clear {session!r}
        environment_gone_check {session!r} {str(workspace)!r} {str(spec)!r} >/dev/null || true
        """
    )
    subprocess.run(["bash", "-c", script], check=True, cwd=str(root))
    assert meta_marker.exists()
    assert meta_pgid.exists()
    assert env_gone.exists()
