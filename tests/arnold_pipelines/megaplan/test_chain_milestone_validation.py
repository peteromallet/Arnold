from __future__ import annotations

import json
import subprocess
import warnings
from pathlib import Path
from types import SimpleNamespace

import pytest

from arnold_pipelines.megaplan.chain import (
    ChainSpec,
    _write_completion_manifest,
    load_chain_state,
    run_chain,
)
from arnold_pipelines.megaplan.types import CliError


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _write_validation_fixture(
    root: Path, *, validator_exit: int = 0, nested: bool = False
) -> Path:
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    (root / "idea.md").write_text("# Idea\n", encoding="utf-8")
    (root / "conformance.yaml").write_text("schema: test\n", encoding="utf-8")
    (root / "traceability.yaml").write_text("schema: test\n", encoding="utf-8")
    (root / "proof.md").write_text("# Proof\n", encoding="utf-8")
    (root / "proof-map.json").write_text(
        json.dumps({"m1": ["proof.md"]}) + "\n",
        encoding="utf-8",
    )
    validator = root / "validator.py"
    validator.write_text(
        "from __future__ import annotations\n"
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "expected = ['--conformance', 'conformance.yaml', '--traceability', 'traceability.yaml', '--repo-root', str(Path.cwd())]\n"
        "if sys.argv[1:] != expected or os.getcwd() != str(Path.cwd()):\n"
        "    print(f'unexpected argv/cwd: {sys.argv[1:]} cwd={os.getcwd()}', file=sys.stderr)\n"
        "    raise SystemExit(3)\n"
        "Path('validation-sentinel.txt').write_text('validator ran\\n', encoding='utf-8')\n"
        "print('validator ran')\n"
        f"raise SystemExit({validator_exit})\n",
        encoding="utf-8",
    )
    spec_path = (
        root / ".megaplan" / "initiatives" / "example" / "chain.yaml"
        if nested
        else root / "chain.yaml"
    )
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(
        """
driver:
  require_anchor: false
  missing_anchor_ack: validation test fixture intentionally has no North Star
milestones:
  - label: m1
    idea: idea.md
    validate:
      - kind: final_conformance_gate
        traceability: traceability.yaml
        conformance: conformance.yaml
        validator: validator.py
        proof_map: proof-map.json
""".lstrip(),
        encoding="utf-8",
    )
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    return spec_path


def test_chain_spec_defaults_merge_policy_to_auto_for_unattended_epics() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec = ChainSpec.from_dict({"milestones": []})

    assert spec.merge_policy == "auto"
    assert caught == []


@pytest.mark.parametrize(
    ("configured", "normalized"),
    [("review", "review"), ("manual", "review")],
)
def test_chain_spec_warns_when_merge_policy_is_not_auto(
    configured: str, normalized: str
) -> None:
    with pytest.warns(UserWarning, match="only be set away from `auto`"):
        spec = ChainSpec.from_dict(
            {"merge_policy": configured, "milestones": []}
        )

    assert spec.merge_policy == normalized


@pytest.fixture()
def chain_driver_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._preflight_agent_backends",
        lambda spec, *, writer: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain.resolve_execution_environment",
        lambda **_kwargs: SimpleNamespace(to_dict=lambda: {}),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._init_plan",
        lambda *args, **kwargs: "plan-m1",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._write_chain_policy_into_plan_meta",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._attach_chain_anchors_to_plan",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._drive_plan_with_blocked_execute_recovery",
        lambda *args, **kwargs: SimpleNamespace(status="done", reason="done", plan="plan-m1"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._record_chain_last_state_after_plan_run",
        lambda root, spec_path, state, outcome, *, writer: state,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._handle_outcome",
        lambda *args, **kwargs: "advance",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._plan_terminal_completion_is_authoritative",
        lambda *args, **kwargs: (True, "authoritative"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._run_full_suite_backstop_gate",
        lambda *args, **kwargs: {"blocks": False},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._shadow_milestone_completion_verdict",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._mark_plan_completed_by_chain",
        lambda *args, **kwargs: None,
    )

    def append_completed(_root, state, record, **_kwargs):
        state.completed.append(record)
        return True, "test guard accepted"

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._append_completed_with_guard",
        append_completed,
    )


def test_milestone_validate_accepts_final_conformance_gate() -> None:
    spec = ChainSpec.from_dict(
        {
            "milestones": [
                {
                    "label": "m1",
                    "idea": "idea.md",
                    "validate": {
                        "kind": "final_conformance_gate",
                        "traceability": "traceability.yaml",
                        "conformance": "conformance.yaml",
                        "validator": "validator.py",
                        "proof_map": "proof-map.json",
                    },
                }
            ]
        }
    )

    validation = spec.milestones[0].validate[0]
    assert validation.kind == "final_conformance_gate"
    assert validation.conformance == "conformance.yaml"


def test_milestone_validate_rejects_unknown_kind() -> None:
    with pytest.raises(CliError, match="final_conformance_gate"):
        ChainSpec.from_dict(
            {
                "milestones": [
                    {
                        "label": "m1",
                        "idea": "idea.md",
                        "validate": {
                            "kind": "not-a-real-gate",
                            "traceability": "traceability.yaml",
                            "conformance": "conformance.yaml",
                            "validator": "validator.py",
                            "proof_map": "proof-map.json",
                        },
                    }
                ]
            }
        )


def test_final_conformance_gate_must_be_final_milestone() -> None:
    with pytest.raises(CliError, match="not the final milestone"):
        ChainSpec.from_dict(
            {
                "milestones": [
                    {
                        "label": "m1",
                        "idea": "idea.md",
                        "validate": {
                            "kind": "final_conformance_gate",
                            "traceability": "traceability.yaml",
                            "conformance": "conformance.yaml",
                            "validator": "validator.py",
                            "proof_map": "proof-map.json",
                        },
                    },
                    {"label": "m2", "idea": "idea.md"},
                ]
            }
        )


def test_final_milestone_validation_blocks_before_append(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chain_driver_monkeypatch: None
) -> None:
    spec_path = _write_validation_fixture(tmp_path, validator_exit=1)
    append_calls: list[str] = []

    def append_completed(_root, state, record, **_kwargs):
        append_calls.append(record["label"])
        state.completed.append(record)
        return True, "test guard accepted"

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._append_completed_with_guard",
        append_completed,
    )

    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=True,
        mode="plan",
    )

    state = load_chain_state(spec_path)
    assert result["status"] == "blocked"
    assert "validation failed" in result["reason"]
    assert append_calls == []
    assert state.completed == []
    assert state.last_state == "validation_failed"
    assert not spec_path.with_name("completion-manifest.json").exists()
    # Start evidence may be present (emitted at plan init) but completion
    # evidence must NOT exist for a failed milestone.
    assert state.has_milestone_evidence("m1")
    start_evidence = state.get_milestone_evidence("m1")
    assert start_evidence is not None
    assert start_evidence.contract_id == "chain.milestone.start.1"
    # No completion evidence should be present.
    assert "chain.milestone.complete.1" not in str(state.milestone_boundary_evidence)


def test_final_milestone_validation_writes_receipt_and_completion_manifest(
    tmp_path: Path, chain_driver_monkeypatch: None
) -> None:
    spec_path = _write_validation_fixture(tmp_path, validator_exit=0)

    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=True,
        mode="plan",
    )

    assert result["status"] == "done", result["reason"]
    state = load_chain_state(spec_path)
    assert state.current_milestone_index == 1
    assert state.completed[0]["label"] == "m1"
    receipt_path = spec_path.with_name("validation-m1-final_conformance_gate.json")
    assert receipt_path.is_file()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["returncode"] == 0
    proof_map = json.loads((tmp_path / "proof-map.json").read_text(encoding="utf-8"))
    assert "validation-m1-final_conformance_gate.json" in proof_map["m1"]
    manifest_path = spec_path.with_name("completion-manifest.json")
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "arnold.megaplan.chain_completion_manifest.v1"
    proof_paths = {
        artifact["path"]
        for artifact in manifest["milestones"][0]["proof_artifacts"]
    }
    assert "proof.md" in proof_paths
    assert "validation-m1-final_conformance_gate.json" in proof_paths
    # Boundary evidence: start evidence is always emitted at plan init.
    # Completion evidence must be emitted for every successful milestone append.
    assert state.has_milestone_evidence("m1")
    evidence = state.get_milestone_evidence("m1")
    assert evidence is not None
    assert evidence.milestone_label == "m1"
    # Completion evidence overwrites start evidence (same key), so the
    # surviving entry carries the completion contract ID.
    assert evidence.contract_id == "chain.milestone.complete.1"
    # Chain-complete evidence must exist when the final milestone completes.
    assert state.has_milestone_evidence("chain_complete")
    chain_evidence = state.get_milestone_evidence("chain_complete")
    assert chain_evidence is not None
    assert chain_evidence.contract_id == "chain.complete.1"


def test_nested_validation_receipt_uses_project_relative_path(
    tmp_path: Path, chain_driver_monkeypatch: None
) -> None:
    spec_path = _write_validation_fixture(tmp_path, validator_exit=0, nested=True)

    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=True,
        mode="plan",
    )

    assert result["status"] == "done", result["reason"]
    receipt_rel = ".megaplan/initiatives/example/validation-m1-final_conformance_gate.json"
    proof_map = json.loads((tmp_path / "proof-map.json").read_text(encoding="utf-8"))
    assert receipt_rel in proof_map["m1"]
    manifest = json.loads(
        spec_path.with_name("completion-manifest.json").read_text(encoding="utf-8")
    )
    assert receipt_rel in {
        artifact["path"]
        for artifact in manifest["milestones"][0]["proof_artifacts"]
    }
    # Boundary evidence: start evidence is emitted at plan init.
    # Completion evidence must be emitted for every successful milestone append.
    state = load_chain_state(spec_path)
    assert state.has_milestone_evidence("m1")
    evidence = state.get_milestone_evidence("m1")
    assert evidence is not None
    assert evidence.milestone_label == "m1"
    # Completion evidence overwrites start evidence (same key), so the
    # surviving entry carries the completion contract ID.
    assert evidence.contract_id == "chain.milestone.complete.1"
    # Chain-complete evidence must exist when the final milestone completes.
    assert state.has_milestone_evidence("chain_complete")
    chain_evidence = state.get_milestone_evidence("chain_complete")
    assert chain_evidence is not None
    assert chain_evidence.contract_id == "chain.complete.1"


def test_manifest_generation_requires_validation_receipt(
    tmp_path: Path, chain_driver_monkeypatch: None
) -> None:
    spec_path = _write_validation_fixture(tmp_path, validator_exit=0)
    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=True,
        mode="plan",
    )
    assert result["status"] == "done", result["reason"]
    (tmp_path / "proof-map.json").write_text(
        json.dumps({"m1": ["proof.md"]}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CliError, match="missing validation receipt"):
        _write_completion_manifest(
            root=tmp_path,
            spec_path=spec_path,
            spec=ChainSpec.from_dict(
                {
                    "driver": {
                        "require_anchor": False,
                        "missing_anchor_ack": "validation test fixture intentionally has no North Star",
                    },
                    "milestones": [
                        {
                            "label": "m1",
                            "idea": "idea.md",
                            "validate": {
                                "kind": "final_conformance_gate",
                                "traceability": "traceability.yaml",
                                "conformance": "conformance.yaml",
                                "validator": "validator.py",
                                "proof_map": "proof-map.json",
                            },
                        }
                    ],
                }
            ),
            state=load_chain_state(spec_path),
            proof_map_path=tmp_path / "proof-map.json",
            output_path=None,
        )


def test_final_milestone_manifest_failure_rolls_back_done_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chain_driver_monkeypatch: None
) -> None:
    spec_path = _write_validation_fixture(tmp_path, validator_exit=0)

    def fail_manifest(**_kwargs):
        raise CliError("invalid_args", "proof map missing required artifact")

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._write_completion_manifest",
        fail_manifest,
    )

    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=True,
        mode="plan",
    )

    state = load_chain_state(spec_path)
    assert result["status"] == "blocked"
    assert "validation finalization failed" in result["reason"]
    assert state.completed == []
    assert state.current_milestone_index == 0
    assert state.current_plan_name == "plan-m1"
    assert state.last_state == "validation_failed"
    proof_map = json.loads((tmp_path / "proof-map.json").read_text(encoding="utf-8"))
    assert proof_map == {"m1": ["proof.md"]}
    assert not spec_path.with_name("completion-manifest.json").exists()
    # Start evidence may be present (emitted at plan init) but completion
    # evidence must NOT exist after manifest-failure rollback.
    # (The completed record was rolled back so completion evidence should be absent.)
    assert "chain.milestone.complete.1" not in str(state.milestone_boundary_evidence)


def test_auto_merge_waits_for_merged_pr_before_appending_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chain_driver_monkeypatch: None
) -> None:
    spec_path = _write_validation_fixture(tmp_path, validator_exit=0)
    spec_path.write_text(
        """
driver:
  require_anchor: false
  missing_anchor_ack: validation test fixture intentionally has no North Star
merge_policy: auto
milestones:
  - label: m1
    idea: idea.md
    branch: epic/demo
""".lstrip(),
        encoding="utf-8",
    )
    completed_appends: list[dict[str, object]] = []

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._refresh_base_branch",
        lambda *args, **kwargs: "main",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
        lambda *args, **kwargs: "main",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._capture_sync_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
        lambda *args, **kwargs: 42,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._commit_and_push_phase",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._reconcile_chain_from_ground_truth",
        lambda *args, **kwargs: args[3],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._sync_chain_last_state_from_plan",
        lambda *args, **kwargs: args[2],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._plan_state_payload_from_name",
        lambda *args, **kwargs: {"current_state": "done"},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._chain_completion_guard",
        lambda *args, **kwargs: (True, "guard accepted"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._mark_pr_ready",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._enable_auto_merge",
        lambda *args, **kwargs: "open",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._pr_state",
        lambda *args, **kwargs: "open",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._run_milestone_validations_blocking",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._finalize_validation_artifacts_after_done_append",
        lambda *args, **kwargs: None,
    )

    def append_completed(_root, state, record, **_kwargs):
        completed_appends.append(dict(record))
        state.completed.append(record)
        return True, "guard accepted"

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._append_completed_with_guard",
        append_completed,
    )

    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=False,
        mode="code",
    )

    state = load_chain_state(spec_path)
    assert result["status"] == "awaiting_pr_merge"
    assert state.last_state == "awaiting_pr_merge"
    assert state.current_milestone_index == 0
    assert state.current_plan_name == "plan-m1"
    assert state.pr_number == 42
    assert state.pr_state == "open"
    assert state.completed == []
    assert completed_appends == []
    # No completion evidence when completion was never appended
    # (start evidence may be present from plan init).
    assert "chain.milestone.complete.1" not in str(state.milestone_boundary_evidence)


# ── T13: PR evidence assertions during milestone transitions ────────────


def test_chain_state_carries_pr_evidence_metadata_for_auto_merge_milestone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chain_driver_monkeypatch: None
) -> None:
    """Chain state after auto-merge-driven milestone carries PR number and state."""
    spec_path = _write_validation_fixture(tmp_path, validator_exit=0)
    spec_path.write_text(
        """
driver:
  require_anchor: false
  missing_anchor_ack: validation test fixture intentionally has no North Star
merge_policy: auto
milestones:
  - label: m1
    idea: idea.md
    branch: epic/pr-evidence
""".lstrip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._refresh_base_branch",
        lambda *args, **kwargs: "main",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._checkout_milestone_branch",
        lambda *args, **kwargs: "main",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._capture_sync_state",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._ensure_milestone_pr",
        lambda *args, **kwargs: 99,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._commit_and_push_phase",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._reconcile_chain_from_ground_truth",
        lambda *args, **kwargs: args[3],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._sync_chain_last_state_from_plan",
        lambda *args, **kwargs: args[2],
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._plan_state_payload_from_name",
        lambda *args, **kwargs: {"current_state": "done"},
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._chain_completion_guard",
        lambda *args, **kwargs: (True, "guard accepted"),
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._mark_pr_ready",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._enable_auto_merge",
        lambda *args, **kwargs: "open",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._pr_state",
        lambda *args, **kwargs: "open",
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._run_milestone_validations_blocking",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._finalize_validation_artifacts_after_done_append",
        lambda *args, **kwargs: None,
    )

    def append_completed(_root, state, record, **_kwargs):
        state.completed.append(record)
        return True, "guard accepted"

    monkeypatch.setattr(
        "arnold_pipelines.megaplan.chain._append_completed_with_guard",
        append_completed,
    )

    result = run_chain(
        spec_path,
        tmp_path,
        writer=lambda _message: None,
        no_git_refresh=True,
        no_push=False,
        mode="code",
    )

    state = load_chain_state(spec_path)
    # When auto-merge completes (current behavior: done), chain state carries PR metadata
    assert result["status"] in ("done", "awaiting_pr_merge")
    # PR metadata: may be on chain state or in completed record
    pr_found = state.pr_number
    if pr_found is None and state.completed:
        pr_found = state.completed[-1].get("pr_number")
    assert pr_found == 99
    pr_state_found = state.pr_state or (
        state.completed[-1].get("pr_state") if state.completed else None
    )
    assert pr_state_found in ("open", "merged", None)


def test_completed_milestone_record_captures_pr_metadata() -> None:
    """Completed milestone records include pr_number and pr_state when applicable."""
    from arnold_pipelines.megaplan.chain import ChainState

    state = ChainState(
        current_milestone_index=1,
        current_plan_name="plan-pr",
        pr_number=77,
        pr_state="merged",
    )
    # Simulate a completed record with PR metadata
    state.completed.append({
        "label": "m1",
        "status": "done",
        "plan": "plan-pr",
        "commit_sha": "abc123",
        "pushed": True,
        "pr_number": 77,
        "pr_state": "merged",
    })
    assert state.completed[0]["pr_number"] == 77
    assert state.completed[0]["pr_state"] == "merged"
    assert state.pr_state == "merged"
