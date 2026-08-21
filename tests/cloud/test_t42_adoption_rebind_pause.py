"""Focused T4.2 proofs: guarded adoption, pause, rebind, fixer contract."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold_pipelines.megaplan.blocker_recovery import compact_failure_identity
from arnold_pipelines.megaplan.chain.operator_pause import pause_chain as fce_pause_chain
from arnold_pipelines.megaplan.chain.spec import ChainState, save_chain_state
from arnold_pipelines.megaplan.cloud.current_target_liveness import (
    MutationCapability,
    MutationDenied,
    mint_mutation_capability,
    require_mutation_capability,
)
from arnold_pipelines.megaplan.cloud.fixer_executable_recovery import (
    AUTHORITY,
    MILESTONE_LABEL_M7,
    SEQUENCE_INDEX_FORBIDDEN,
    chain_start_argv,
    execute_fixer_recovery_contract,
    mint_recover_capability,
    recover_blocked_argv,
    require_seed_import_env,
    runtime_rebind_argv,
    seed_import_environment,
)
from arnold_pipelines.megaplan.cloud.occurrence_adoption import (
    ADOPTION_ACTION,
    bind_operator_intent,
    guarded_occurrence_adoption,
    plan_payload_without_pause,
    resume_cursor_bytes,
)
from arnold_pipelines.megaplan.cloud.operator_pause import (
    PAUSE_ACTION,
    pause_chain,
)
from arnold_pipelines.megaplan.cloud.target_rebind import (
    REBIND_ACTION,
    require_milestone_identity_label,
    runtime_rebind,
)
from arnold_pipelines.megaplan.types import CliError

REPO_ROOT = Path(__file__).resolve().parents[2]


def _assert_disposable_root(root: Path) -> Path:
    resolved = root.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    assert resolved != REPO_ROOT
    assert "runtime-candidates" not in resolved.parts
    assert not (resolved / "arnold_pipelines" / "megaplan").exists()
    sentinel = resolved / ".t42-disposable-root"
    sentinel.write_text("disposable\n", encoding="utf-8")
    return resolved


def _digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _git_init(root: Path) -> str:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t42@example.test"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t42"], cwd=root, check=True)
    (root / "README").write_text("t42\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return head


def _live_tree(tmp_path: Path, name: str = "seed-import-root") -> tuple[Path, Path, str]:
    root = _assert_disposable_root(tmp_path / name)
    interpreter = tmp_path / name / "generation" / "bin" / "python"
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_text("#!/bin/sh\n", encoding="utf-8")
    interpreter.chmod(0o755)
    head = _git_init(root)
    return root, interpreter, head


def _mint(
    tmp_path: Path,
    *,
    action: str,
    occurrence: str = "occ-1",
    target: str = "target-1",
    fence_epoch: int = 3,
    extra: dict[str, object] | None = None,
) -> MutationCapability:
    live, interpreter, _head = _live_tree(tmp_path, name=f"{action}-root")
    payload: dict[str, object] = {
        "occurrence": occurrence,
        "target": target,
        "cursor": "cursor-1",
        "fence_epoch": fence_epoch,
        "evidence_digest": _digest({"occurrence": occurrence, "cursor": "cursor-1"}),
        "scope": action,
        "custody": f"custody:{occurrence}",
        "import_root": str(live),
        "interpreter": str(interpreter),
        "runtime_manifest": {
            "epic": {
                "runtime_root": str(live),
                "dependency_generation": {"interpreter_path": str(interpreter)},
            }
        },
    }
    if extra:
        payload.update(extra)
    return mint_mutation_capability(
        action=action,
        evidence=payload,
        process_root=live,
        process_python=interpreter,
    )


def _chain_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = _assert_disposable_root(tmp_path / "pause-root")
    initiative = root / ".megaplan" / "initiatives" / "demo"
    initiative.mkdir(parents=True)
    (initiative / "brief.md").write_text("# brief\n", encoding="utf-8")
    spec = initiative / "chain.yaml"
    spec.write_text(
        "anchors:\n  north_star: brief.md\n"
        "milestones:\n  - label: m7\n    idea: brief.md\n",
        encoding="utf-8",
    )
    plan = root / ".megaplan" / "plans" / "m7-plan"
    plan.mkdir(parents=True)
    (plan / "state.json").write_text(
        json.dumps(
            {
                "name": "m7-plan",
                "current_state": "blocked",
                "resume_cursor": {
                    "phase": "critique",
                    "retry_strategy": "repair_phase_contract",
                    "fence_epoch": 3,
                },
                "latest_failure": {
                    "kind": "deterministic_phase_failure",
                    "phase": "critique",
                    "message": "phase contract failed",
                },
                "meta": {"kept": True},
            }
        ),
        encoding="utf-8",
    )
    state = ChainState(
        current_milestone_index=0,
        current_plan_name="m7-plan",
        last_state="blocked",
        completed=[],
    )
    save_chain_state(spec, state)
    return root, spec, plan


def test_permission_truth_table(tmp_path: Path) -> None:
    for action in (ADOPTION_ACTION, PAUSE_ACTION, REBIND_ACTION, "recover-blocked"):
        cap = _mint(tmp_path / action, action=action)
        require_mutation_capability(cap, action=action, occurrence="occ-1", scope=action)
        bind_operator_intent(
            cap,
            action=action,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            scope=action,
        )


def test_mismatched_occurrence_plan_runtime_fail_closed(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action=ADOPTION_ACTION)
    root = _assert_disposable_root(tmp_path / "adopt")
    plan = {"name": "plan-a", "resume_cursor": {"phase": "critique"}}
    with pytest.raises(CliError, match="plan"):
        guarded_occurrence_adoption(
            capability=cap,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            binding_root=root,
            plan=plan,
            expected_plan="plan-b",
        )
    with pytest.raises(CliError, match="runtime"):
        guarded_occurrence_adoption(
            capability=cap,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            binding_root=root,
            runtime_identity={"import_root": str(tmp_path / "other-runtime")},
            expected_runtime=str(tmp_path / "expected-runtime"),
        )
    with pytest.raises(MutationDenied) as denied:
        bind_operator_intent(
            cap,
            action=ADOPTION_ACTION,
            occurrence="occ-other",
            target="target-1",
            fence_epoch=3,
            scope=ADOPTION_ACTION,
        )
    assert denied.value.code == "occurrence_mismatch"


def test_stale_marker_with_live_process_cannot_authorize(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action=ADOPTION_ACTION)
    root = _assert_disposable_root(tmp_path / "ops")
    with pytest.raises(MutationDenied) as denied:
        guarded_occurrence_adoption(
            capability=cap,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            binding_root=root,
            evidence={
                "pid": os.getpid(),
                "tmux": "sess",
                "stale_marker": True,
                "stopped_lease": {"epoch": 1},
                "live_process": True,
                "authorizes_from_operational_evidence": True,
            },
        )
    assert denied.value.code == "operational_evidence_not_authority"
    # Diagnostic presence of PID/tmux without a grant still requires capability.
    result = guarded_occurrence_adoption(
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=root,
        evidence={"pid": os.getpid(), "tmux": "sess", "stale_marker": True},
    )
    assert result["adopted"] is True


def test_stale_epoch_fails_closed(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action=ADOPTION_ACTION, fence_epoch=3)
    with pytest.raises(MutationDenied) as denied:
        bind_operator_intent(
            cap,
            action=ADOPTION_ACTION,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=2,
            scope=ADOPTION_ACTION,
        )
    assert denied.value.code == "stale_fence"


def test_pause_resume_race_preserves_cursor_and_payload(tmp_path: Path) -> None:
    project, spec, plan_dir = _chain_fixture(tmp_path)
    cap = _mint(tmp_path, action=PAUSE_ACTION)
    before = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    first = pause_chain(
        spec,
        project,
        reason="operator pause",
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=project,
    )
    after = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert first["changed"] is True
    assert resume_cursor_bytes(after) == resume_cursor_bytes(before)
    assert plan_payload_without_pause(after) == plan_payload_without_pause(before)
    assert after["meta"]["operator_pause"]["reason"] == "operator pause"
    second = pause_chain(
        spec,
        project,
        reason="replay",
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=project,
    )
    assert second["changed"] is False
    raced = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert resume_cursor_bytes(raced) == resume_cursor_bytes(before)


def test_cursor_and_plan_payload_preservation_with_pause_event_append(
    tmp_path: Path,
) -> None:
    project, spec, plan_dir = _chain_fixture(tmp_path)
    before = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    fce_pause_chain(spec, project, reason="append-only pause metadata")
    after = json.loads((plan_dir / "state.json").read_text(encoding="utf-8"))
    assert resume_cursor_bytes(after) == resume_cursor_bytes(before)
    assert plan_payload_without_pause(after) == plan_payload_without_pause(before)
    assert "operator_pause" in after["meta"]


def test_action_occurrence_token_replay_rejects(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action=ADOPTION_ACTION)
    with pytest.raises(MutationDenied) as action_denied:
        bind_operator_intent(
            cap,
            action=PAUSE_ACTION,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            scope=PAUSE_ACTION,
        )
    assert action_denied.value.code == "action_mismatch"
    with pytest.raises(MutationDenied) as occ_denied:
        bind_operator_intent(
            cap,
            action=ADOPTION_ACTION,
            occurrence="occ-2",
            target="target-1",
            fence_epoch=3,
            scope=ADOPTION_ACTION,
        )
    assert occ_denied.value.code == "occurrence_mismatch"


def test_duplicate_adoption_is_idempotent_then_contradiction_fails(
    tmp_path: Path,
) -> None:
    cap = _mint(tmp_path, action=ADOPTION_ACTION)
    root = _assert_disposable_root(tmp_path / "dup")
    first = guarded_occurrence_adoption(
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=root,
        plan={"name": "m7-plan", "resume_cursor": {"phase": "critique"}},
    )
    replay = guarded_occurrence_adoption(
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=root,
        plan={"name": "m7-plan", "resume_cursor": {"phase": "critique"}},
    )
    assert first["changed"] is True
    assert replay["changed"] is False
    other = _mint(tmp_path / "other", action=ADOPTION_ACTION, target="target-other")
    with pytest.raises((MutationDenied, CliError)):
        guarded_occurrence_adoption(
            capability=other,
            occurrence="occ-1",
            target="target-other",
            fence_epoch=3,
            binding_root=root,
        )



def test_rebind_rollback_returns_exact_prior_binding(tmp_path: Path) -> None:
    cap = _mint(tmp_path, action=REBIND_ACTION)
    root = _assert_disposable_root(tmp_path / "rebind")
    live = Path(cap.import_root)
    interpreter = Path(cap.interpreter)
    dest_root = _assert_disposable_root(tmp_path / "dest-root")
    dest_python = tmp_path / "dest-root" / "generation" / "bin" / "python"
    dest_python.parent.mkdir(parents=True, exist_ok=True)
    dest_python.write_text("#!/bin/sh\n", encoding="utf-8")
    cutover = runtime_rebind(
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        expected_current_milestone=MILESTONE_LABEL_M7,
        binding_root=root,
        from_import_root=str(live),
        from_interpreter=str(interpreter),
        to_import_root=str(dest_root),
        to_interpreter=str(dest_python),
        direction="cutover",
        identity={"milestone_sequence": [{"index": 0, "label": "m7"}]},
    )
    assert cutover["binding"]["to"]["import_root"] == str(dest_root.resolve())
    rolled = runtime_rebind(
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        expected_current_milestone=MILESTONE_LABEL_M7,
        binding_root=root,
        from_import_root=str(dest_root),
        from_interpreter=str(dest_python),
        to_import_root=str(live),
        to_interpreter=str(interpreter),
        direction="rollback",
        identity={"milestone_sequence": [{"index": 0, "label": "m7"}]},
    )
    assert rolled["binding"]["restored"]["import_root"] == str(live.resolve())
    assert rolled["binding"]["restored"]["interpreter"] == str(interpreter.resolve())
    with pytest.raises(CliError, match="exact prior binding"):
        runtime_rebind(
            capability=cap,
            occurrence="occ-1",
            target="target-1",
            fence_epoch=3,
            expected_current_milestone=MILESTONE_LABEL_M7,
            binding_root=root,
            from_import_root=str(dest_root),
            from_interpreter=str(dest_python),
            to_import_root=str(tmp_path / "wrong"),
            to_interpreter=str(interpreter),
            direction="rollback",
            identity={"milestone_sequence": [{"index": 0, "label": "m7"}]},
        )


def test_runtime_rebind_label_m7_accepted_index_6_rejected(tmp_path: Path) -> None:
    assert require_milestone_identity_label("m7") == "m7"
    with pytest.raises(CliError, match="_identity_labels") as denied:
        require_milestone_identity_label(SEQUENCE_INDEX_FORBIDDEN)
    assert denied.value.extra["guard"] == "_identity_labels"
    with pytest.raises(CliError, match="_identity_labels"):
        runtime_rebind_argv(milestone="6", spec="chain.yaml")
    argv = runtime_rebind_argv(milestone="m7", spec="chain.yaml")
    assert "m7" in argv
    assert "6" not in argv[argv.index("--expected-current-milestone") + 1]


def test_fixer_executable_contract_under_seed_import_env(tmp_path: Path) -> None:
    live, interpreter, head = _live_tree(tmp_path, name="fixer-import-root")
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "patch"],
        cwd=live,
        check=True,
        capture_output=True,
    )
    repair_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=live, text=True
    ).strip()
    fixture = _assert_disposable_root(tmp_path / "fixer-fixture")
    manifest_path = fixture / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generation": 1,
                "epic": {
                    "runtime_root": str(live),
                    "expected_head": head,
                    "dependency_generation": {"interpreter_path": str(interpreter)},
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    latest_failure = {
        "kind": "deterministic_phase_failure",
        "phase": "critique",
        "message": "phase contract failed seed-import",
    }

    fingerprint = compact_failure_identity(latest_failure)["fingerprint"]
    cap = mint_recover_capability(
        occurrence=str(fingerprint),
        fence_epoch=3,
        import_root=live,
        interpreter=interpreter,
    )
    env = seed_import_environment(import_root=live, manifest_path=manifest_path)
    require_seed_import_env(env, import_root=live)
    plan_state = {
        "latest_failure": latest_failure,
        "resume_cursor": {
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
            "fence_epoch": 3,
        },
    }
    result = execute_fixer_recovery_contract(
        capability=cap,
        occurrence=str(fingerprint),
        target=str(fingerprint),
        fence_epoch=3,
        binding_root=fixture,
        import_root=live,
        interpreter=interpreter,
        manifest_path=manifest_path,
        repair_commit=repair_commit,
        failure_fingerprint=str(fingerprint),
        plan_state=plan_state,
        resume_cursor=plan_state["resume_cursor"],
        env=env,
        process_root=live,
        seed_gates_present=True,
    )
    assert result["authority"] == AUTHORITY
    assert result["automatic"] is False
    assert result["telemetry"]["advance_generation"] is False
    assert result["telemetry"]["expected_head"] == repair_commit
    assert json.loads(manifest_path.read_text())["generation"] == 1
    assert result["recover_evidence"]["authority"] == AUTHORITY
    assert "--user-approved" in result["argv"]["recover_blocked"]
    assert "--repair-scope" in result["argv"]["recover_blocked"]
    assert "engine_runtime" in result["argv"]["recover_blocked"]
    assert "--one" in result["argv"]["chain_start"]
    assert "m7" in result["argv"]["runtime_rebind"]
    replay = recover_blocked_argv(
        repair_commit=repair_commit,
        failure_fingerprint=str(fingerprint),
    )
    assert replay == result["argv"]["recover_blocked"]
    with pytest.raises(CliError, match="_identity_labels"):
        require_milestone_identity_label("6")
    ambient = seed_import_environment(
        import_root=_assert_disposable_root(tmp_path / "ambient-live"),
        manifest_path=manifest_path,
    )
    with pytest.raises(MutationDenied) as denied:
        require_seed_import_env(ambient, import_root=live)
    assert denied.value.code == "import_root_mismatch"


def test_same_import_root_post_gate_deletion_is_non_event(tmp_path: Path) -> None:
    live, interpreter, head = _live_tree(tmp_path, name="post-gate-root")
    fixture = _assert_disposable_root(tmp_path / "post-gate-fixture")
    manifest_path = fixture / "runtime-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "generation": 4,
                "epic": {
                    "runtime_root": str(live),
                    "expected_head": head,
                    "dependency_generation": {"interpreter_path": str(interpreter)},
                },
            }
        ),
        encoding="utf-8",
    )
    latest_failure = {
        "kind": "deterministic_phase_failure",
        "phase": "critique",
        "message": "phase contract failed post-gate",
    }

    fingerprint = compact_failure_identity(latest_failure)["fingerprint"]
    cap = mint_recover_capability(
        occurrence=str(fingerprint),
        fence_epoch=3,
        import_root=live,
        interpreter=interpreter,
    )
    env = seed_import_environment(import_root=live, manifest_path=manifest_path)
    result = execute_fixer_recovery_contract(
        capability=cap,
        occurrence=str(fingerprint),
        target=str(fingerprint),
        fence_epoch=3,
        binding_root=fixture,
        import_root=live,
        interpreter=interpreter,
        manifest_path=manifest_path,
        repair_commit=head,
        failure_fingerprint=str(fingerprint),
        plan_state={
            "latest_failure": latest_failure,
            "resume_cursor": {
                "phase": "critique",
                "retry_strategy": "repair_phase_contract",
            },
        },
        resume_cursor={
            "phase": "critique",
            "retry_strategy": "repair_phase_contract",
        },
        env=env,
        process_root=live,
        seed_gates_present=False,
    )
    assert "same_import_root_non_event" in result["steps"]
    assert result["rebind"] is None
    assert json.loads(manifest_path.read_text())["generation"] == 4
    assert json.loads(manifest_path.read_text())["epic"]["expected_head"] == head


def test_replay_without_new_repair_commit_remains_fenced(tmp_path: Path) -> None:
    live, interpreter, head = _live_tree(tmp_path, name="fence-root")
    latest_failure = {
        "kind": "deterministic_phase_failure",
        "phase": "critique",
        "message": "phase contract failed replay-fence",
    }

    fingerprint = compact_failure_identity(latest_failure)["fingerprint"]
    from arnold_pipelines.megaplan.blocker_recovery import (
        validated_deterministic_phase_repair,
    )

    with pytest.raises(CliError) as denied:
        validated_deterministic_phase_repair(
            live,
            {
                "latest_failure": latest_failure,
                "resume_cursor": {
                    "phase": "critique",
                    "retry_strategy": "repair_phase_contract",
                },
            },
            {
                "phase": "critique",
                "retry_strategy": "repair_phase_contract",
            },
            "0" * 40,
            fingerprint,
            "engine_runtime",
        )
    assert denied.value.code in {
        "capability_absent",
        "import_root_mismatch",
        "phase_repair_commit_mismatch",
        "missing_phase_repair_commit",
    }
    cap = mint_recover_capability(
        occurrence=str(fingerprint),
        fence_epoch=3,
        import_root=live,
        interpreter=interpreter,
    )
    from arnold_pipelines.megaplan.cloud.current_target_liveness import (
        attach_mutation_capability,
    )
    from unittest.mock import patch

    attach_mutation_capability(cap, identity=str(fingerprint))
    with patch(
        "arnold_pipelines.megaplan.cloud.current_target_liveness.process_import_root",
        return_value=live.resolve(),
    ), pytest.raises(CliError) as mismatch:
        validated_deterministic_phase_repair(
            live,
            {
                "latest_failure": latest_failure,
                "resume_cursor": {
                    "phase": "critique",
                    "retry_strategy": "repair_phase_contract",
                    "mutation_capability": cap,
                    "mutation_capability_handle": str(fingerprint),
                },
            },
            {
                "phase": "critique",
                "retry_strategy": "repair_phase_contract",
                "mutation_capability": cap,
                "mutation_capability_handle": str(fingerprint),
            },
            "0" * 40,
            fingerprint,
            "engine_runtime",
        )
    assert mismatch.value.code == "phase_repair_commit_mismatch"

    del head


def test_valid_downstream_evidence_without_capability_rejects(tmp_path: Path) -> None:
    with pytest.raises(MutationDenied) as denied:
        pause_chain(
            tmp_path / "missing.yaml",
            tmp_path,
            reason="no capability",
        )
    assert denied.value.code == "capability_absent"


def test_expired_capability_rejects(tmp_path: Path) -> None:
    cap = _mint(
        tmp_path,
        action=ADOPTION_ACTION,
        extra={},
    )
    expired = mint_mutation_capability(
        action=ADOPTION_ACTION,
        evidence={
            "occurrence": "occ-1",
            "target": "target-1",
            "cursor": "cursor-1",
            "fence_epoch": 3,
            "evidence_digest": _digest({"occurrence": "occ-1"}),
            "scope": ADOPTION_ACTION,
            "custody": "custody:occ-1",
            "import_root": cap.import_root,
            "interpreter": cap.interpreter,
            "runtime_manifest": {
                "epic": {
                    "runtime_root": cap.import_root,
                    "dependency_generation": {"interpreter_path": cap.interpreter},
                }
            },
        },
        process_root=Path(cap.import_root),
        process_python=Path(cap.interpreter),
        now=datetime.now(timezone.utc) - timedelta(hours=2),
        ttl=timedelta(seconds=1),
    )
    with pytest.raises(MutationDenied) as denied:
        require_mutation_capability(
            expired, action=ADOPTION_ACTION, occurrence="occ-1", scope=ADOPTION_ACTION
        )
    assert denied.value.code == "capability_expired"


def test_static_search_proves_t42_owners_and_no_7272_facade() -> None:
    owners = {
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/occurrence_adoption.py": "def guarded_occurrence_adoption",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/operator_pause.py": "def pause_chain",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/target_rebind.py": "def target_rebind",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/fixer_executable_recovery.py": "def execute_fixer_recovery_contract",
        REPO_ROOT / "arnold_pipelines/megaplan/chain/__init__.py": "from arnold_pipelines.megaplan.cloud.operator_pause import pause_chain",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/operator_control.py": "from arnold_pipelines.megaplan.cloud.operator_pause import",
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/cli.py": "--capability-handle",
    }
    for path, needle in owners.items():
        source = path.read_text(encoding="utf-8")
        assert needle in source
        assert "commit_chain_runtime_cutover" not in source
        tree = ast.parse(source)
        names = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        assert "prepare_cutover" not in names
    chain_cli = (
        REPO_ROOT / "arnold_pipelines/megaplan/chain/__init__.py"
    ).read_text(encoding="utf-8")
    assert "from arnold_pipelines.megaplan.cloud.target_rebind import runtime_rebind" in chain_cli
    assert "from arnold_pipelines.megaplan.cloud.target_rebind import target_rebind" in chain_cli
    assert ".t42-adoption" not in (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/occurrence_adoption.py"
    ).read_text(encoding="utf-8")
    assert ".t42-runtime-binding.json" not in (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/target_rebind.py"
    ).read_text(encoding="utf-8")
    assert "_identity_labels" in (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/target_rebind.py"
    ).read_text(encoding="utf-8")
    assert "m7" in (
        REPO_ROOT / "arnold_pipelines/megaplan/cloud/fixer_executable_recovery.py"
    ).read_text(encoding="utf-8")


def test_chain_start_one_argv_is_seed_import_bound() -> None:
    argv = chain_start_argv(spec="/tmp/disposable/chain.yaml", project_dir="/tmp/disposable")
    assert argv[-1] == "--one"
    assert "--spec" in argv

def test_second_pause_different_identity_fails_closed(tmp_path: Path) -> None:
    project, spec, _plan_dir = _chain_fixture(tmp_path)
    cap = _mint(tmp_path, action=PAUSE_ACTION)
    first = pause_chain(
        spec,
        project,
        reason="operator pause",
        capability=cap,
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        binding_root=project,
    )
    assert first["changed"] is True
    assert first["authority"]["occurrence"] == "occ-1"
    other = _mint(tmp_path / "occ-2", action=PAUSE_ACTION, occurrence="occ-2")
    with pytest.raises(CliError) as denied:
        pause_chain(
            spec,
            project,
            reason="other occurrence",
            capability=other,
            occurrence="occ-2",
            target="target-1",
            fence_epoch=3,
            binding_root=project,
        )
    assert denied.value.code == "identity_contradiction"


def test_production_chain_pause_requires_minted_capability(tmp_path: Path) -> None:
    from argparse import Namespace
    from arnold_pipelines.megaplan.chain import run_chain_cli

    project, spec, _plan_dir = _chain_fixture(tmp_path)
    args = Namespace(
        chain_action="pause",
        spec=str(spec),
        project_dir=str(project),
        reason="operator pause",
        actor="operator",
        occurrence="",
        target="",
        fence_epoch=None,
        capability_handle="",
        mutation_capability=None,
    )
    rc = run_chain_cli(project, args)
    assert rc != 0


def test_production_runtime_rebind_rejects_sequence_index(tmp_path: Path) -> None:
    from argparse import Namespace
    from arnold_pipelines.megaplan.chain import run_chain_cli

    project, spec, _plan_dir = _chain_fixture(tmp_path)
    cap = _mint(tmp_path, action=REBIND_ACTION)
    from arnold_pipelines.megaplan.cloud.current_target_liveness import (
        attach_mutation_capability,
    )

    attach_mutation_capability(cap, identity="occ-1")
    args = Namespace(
        chain_action="runtime-rebind",
        spec=str(spec),
        project_dir=str(project),
        from_runtime_sha256=None,
        to_runtime_sha256=None,
        from_import_root=cap.import_root,
        from_interpreter=cap.interpreter,
        to_import_root=cap.import_root,
        to_interpreter=cap.interpreter,
        expected_current_milestone="6",
        expected_current_plan="m7-plan",
        direction="cutover",
        reason="rebind",
        actor="operator",
        runtime_identity="",
        runtime_provenance_receipt="",
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        capability_handle="occ-1",
        mutation_capability=cap,
    )
    rc = run_chain_cli(project, args)
    assert rc != 0



def test_production_runtime_rebind_rejects_sha_cas(tmp_path: Path) -> None:
    from argparse import Namespace
    from arnold_pipelines.megaplan.chain import run_chain_cli
    from arnold_pipelines.megaplan.cloud.current_target_liveness import (
        attach_mutation_capability,
    )

    project, spec, _plan_dir = _chain_fixture(tmp_path)
    cap = _mint(tmp_path, action=REBIND_ACTION)
    attach_mutation_capability(cap, identity="occ-1")
    args = Namespace(
        chain_action="runtime-rebind",
        spec=str(spec),
        project_dir=str(project),
        from_runtime_sha256="a" * 64,
        to_runtime_sha256="b" * 64,
        from_import_root=cap.import_root,
        from_interpreter=cap.interpreter,
        to_import_root=cap.import_root,
        to_interpreter=cap.interpreter,
        expected_current_milestone="m7",
        expected_current_plan="m7-plan",
        direction="cutover",
        reason="rebind",
        actor="operator",
        runtime_identity="",
        runtime_provenance_receipt="",
        occurrence="occ-1",
        target="target-1",
        fence_epoch=3,
        capability_handle="occ-1",
        mutation_capability=cap,
    )
    rc = run_chain_cli(project, args)
    assert rc != 0
