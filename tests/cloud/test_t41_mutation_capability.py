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
    control_liveness_from_current_target,
    mint_mutation_capability,
    observe_current_target_liveness,
    require_mutation_capability,
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
    assert forged_denied.value.code == "capability_forged"

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
        cap.to_dict(), action="repair", occurrence="occ-1", scope="repair"
    )
    assert checked.token == cap.token
    narrowed = checked.narrow("repair")
    assert narrowed.scope == "repair"
    assert narrowed.import_root.endswith("live-import-root")


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


def test_static_search_proves_no_bypassing_in_scope_consumer() -> None:
    in_scope = [
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/current_target_liveness.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/cli.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/supervise.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/meta_repair.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/engine_runtime_repair.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/repair_contract.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/progress_auditor_controller.py",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/six_hour_auditor.py",
        REPO_ROOT / "arnold_pipelines/megaplan/blocker_recovery.py",
        REPO_ROOT / "arnold_pipelines/megaplan/handlers/override.py",
        REPO_ROOT / "arnold_pipelines/megaplan/planning/control_binding.py",
    ]
    required = {
        "supervise.py": "require_mutation_capability",
        "meta_repair.py": "require_mutation_capability",
        "engine_runtime_repair.py": "require_mutation_capability",
        "repair_contract.py": "require_mutation_capability",
        "progress_auditor_controller.py": "require_mutation_capability",
        "six_hour_auditor.py": "require_mutation_capability",
        "blocker_recovery.py": "require_mutation_capability",
        "override.py": "mint_mutation_capability",
        "control_binding.py": "mint_mutation_capability",
        "current_target_liveness.py": "class MutationCapability",
        "cli.py": '"mutation_permitted": False',
    }
    for path in in_scope:
        source = path.read_text(encoding="utf-8")
        needle = required[path.name]
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
