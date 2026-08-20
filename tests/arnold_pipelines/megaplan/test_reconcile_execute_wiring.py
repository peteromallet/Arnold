"""P6 execute-path wiring for the ``kind: reconcile`` milestone.

Two contracts under test:

1. **Reconcile prompt override** — the chain writes ``reconcile_inputs.json``
   (rubric docs + ``git log --first-parent`` + candidate commits + target) into
   the reconcile plan dir; the execute path swaps the generic batch prompt for
   ``render_reconcile_prompt`` (the SELECTION contract whose JSON output shape
   is the deliverable).

2. **Capture seam** — the reconcile-shaped worker payload (top-level
   ``selected_shas`` + ``verification_evidence``) flows into the plan evidence
   artifact (``execution_batch_N.json``), which is what the controller reads to
   cherry-pick the selection.  The seam is the existing
   ``_capture_execute_payload`` + ``atomic_write_json(batch_artifact_path,
   payload)`` path; we assert the payload shape survives into the artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

from arnold_pipelines.megaplan.execute.batch import _reconcile_prompt_override
from arnold_pipelines.megaplan.prompts.execute import render_reconcile_prompt


def _write_inputs(plan_dir: Path, **overrides: object) -> Path:
    payload = {
        "rubric_docs": [
            "# Megaplan reference architecture\n\nrubric-a",
            "# Per-epic runtime end-state\n\nrubric-b",
        ],
        "first_parent_log": "abc123 feat(runtime): manifest admission (P1)",
        "candidate_commits": [
            {
                "sha": "abc123",
                "subject": "feat(runtime): manifest admission",
                "paths": ["arnold_pipelines/megaplan/chain/spec.py"],
            }
        ],
        "target_branch": "main",
    }
    payload.update(overrides)
    inputs = plan_dir / "reconcile_inputs.json"
    inputs.write_text(json.dumps(payload), encoding="utf-8")
    return inputs


# ── prompt override ──────────────────────────────────────────────────────────


def test_reconcile_prompt_override_renders_selection_contract(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "reconcile-plan"
    plan_dir.mkdir(parents=True)
    _write_inputs(plan_dir)

    prompt = _reconcile_prompt_override(plan_dir, "generic-batch-prompt")

    assert "SELECTION, not narrative" in prompt
    assert "selected_shas" in prompt
    assert "verification_evidence" in prompt
    assert "abc123" in prompt  # candidate commit sha
    assert "rubric-a" in prompt
    assert "rubric-b" in prompt
    assert "Target branch: main" in prompt
    assert "generic-batch-prompt" not in prompt  # fully replaced


def test_reconcile_prompt_override_matches_render_reconcile_prompt(
    tmp_path: Path,
) -> None:
    """The override is literally render_reconcile_prompt(**inputs) — the
    controller-facing prompt contract stays in one place."""
    plan_dir = tmp_path / ".megaplan" / "plans" / "reconcile-plan"
    plan_dir.mkdir(parents=True)
    _write_inputs(plan_dir)

    override = _reconcile_prompt_override(plan_dir, "generic-batch-prompt")
    expected = render_reconcile_prompt(
        rubric_docs=[
            "# Megaplan reference architecture\n\nrubric-a",
            "# Per-epic runtime end-state\n\nrubric-b",
        ],
        first_parent_log="abc123 feat(runtime): manifest admission (P1)",
        candidate_commits=[
            {
                "sha": "abc123",
                "subject": "feat(runtime): manifest admission",
                "paths": ["arnold_pipelines/megaplan/chain/spec.py"],
            }
        ],
        target_branch="main",
    )
    assert override == expected


def test_reconcile_prompt_override_preserves_review_rework_contract(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "reconcile-plan"
    plan_dir.mkdir(parents=True)
    _write_inputs(plan_dir)
    (plan_dir / "review.json").write_text(
        json.dumps(
            {
                "review_verdict": "needs_rework",
                "rework_items": [
                    {
                        "target": {"kind": "bulk", "task_ids": ["T3", "T4"]},
                        "task_id": "T4",
                        "issue": "notes contract is incomplete",
                        "expected": (
                            "verification_evidence.notes must state pr_required; "
                            "no selected_shas found in plan execution evidence; "
                            "cannot publish the reconcile PR; execute_batches/batch_; "
                            "operator resolution; execute.py:175-178; "
                            "01M0ETZ6W0K3H9XQ7N2D5B8RV4; ead33b1d"
                        ),
                        "actual": "notes omitted the operator contract",
                        "evidence_file": "execute_batches/batch_1/tasks_T4.json",
                        "source": "review_criterion_verification",
                        "deterministic_check": {
                            "command": "jq -e '.verification_evidence.notes' artifact.json",
                            "baseline_status": "failed",
                            "post_status": "failed",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    prompt = _reconcile_prompt_override(plan_dir, "generic-batch-prompt")

    assert "Persisted review rework contract" in prompt
    assert "verification_evidence.notes" in prompt
    for fragment in (
        "pr_required",
        "no selected_shas found in plan execution evidence; cannot publish the reconcile PR",
        "execute_batches/batch_",
        "operator",
        "execute.py:175-178",
        "01M0ETZ6W0K3H9XQ7N2D5B8RV4",
        "ead33b1d",
        "baseline_status",
        "post_status",
    ):
        assert fragment in prompt
    assert "Do not modify files, open PRs, or touch the repository state." in prompt
    assert "generic-batch-prompt" not in prompt


def test_reconcile_prompt_override_falls_back_without_marker(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "plain-plan"
    plan_dir.mkdir(parents=True)
    assert _reconcile_prompt_override(plan_dir, "generic-batch-prompt") == (
        "generic-batch-prompt"
    )


def test_reconcile_prompt_override_falls_back_on_bad_marker(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".megaplan" / "plans" / "bad-plan"
    plan_dir.mkdir(parents=True)
    (plan_dir / "reconcile_inputs.json").write_text("not json", encoding="utf-8")
    # marker problems never break execute: the generic prompt survives
    assert _reconcile_prompt_override(plan_dir, "generic-batch-prompt") == (
        "generic-batch-prompt"
    )
    (plan_dir / "reconcile_inputs.json").write_text(
        json.dumps({"rubric_docs": "not-a-list"}), encoding="utf-8"
    )
    assert _reconcile_prompt_override(plan_dir, "generic-batch-prompt") == (
        "generic-batch-prompt"
    )


# ── capture seam: reconcile payload → plan evidence ─────────────────────────


def test_reconcile_payload_flows_into_batch_artifact_payload(
    tmp_path: Path,
) -> None:
    """The controller reads the selection from plan evidence: the reconcile-
    shaped worker payload (top-level selected_shas + verification_evidence)
    must survive into the batch artifact payload the same way any execute
    batch payload does (capture_step_output → atomic_write_json)."""
    from arnold_pipelines.megaplan.execute.batch import _capture_execute_payload

    worker_payload = {
        "output": "Selected engine commits for release.",
        "task_updates": [
            {
                "task_id": "T1",
                "status": "done",
                "executor_notes": "selected via rubric",
            }
        ],
        "selected_shas": [
            "abc123",
            "def456",
        ],
        "verification_evidence": {
            "reachability_checked": True,
            "all_selected_reachable_from_target": True,
            "chain_control_commits_excluded": True,
            "excluded_shas": ["c0ffee"],
            "per_phase": [
                {
                    "phase": "P1",
                    "sha": "abc123",
                    "subject": "feat(runtime): manifest admission",
                }
            ],
        },
    }
    captured = _capture_execute_payload(
        agent="codex",
        model="codex-latest",
        resolved_model="codex-latest",
        payload=worker_payload,
    )
    # the authoritative selection shape is preserved at the top level
    assert captured["selected_shas"] == ["abc123", "def456"]
    assert captured["verification_evidence"]["chain_control_commits_excluded"] is True
    assert captured["verification_evidence"]["excluded_shas"] == ["c0ffee"]


def test_reconcile_prompt_contract_mentions_capture_keys(tmp_path: Path) -> None:
    """The prompt's output shape names the exact keys the controller reads:
    a drift between template and reader is a P6 contract break."""
    prompt = render_reconcile_prompt(
        rubric_docs=["doc"],
        first_parent_log="log",
        candidate_commits=[{"sha": "s1", "subject": "subj", "paths": ["p"]}],
        target_branch="main",
    )
    assert '"selected_shas"' in prompt
    assert '"verification_evidence"' in prompt
    assert '"excluded_shas"' in prompt
    assert '"reachability_checked"' in prompt


def test_reconcile_selection_payload_passes_execute_capture_audit() -> None:
    """A reconcile selection-only payload (selected_shas + verification_evidence)
    must pass the execute capture audit: the read-only selector produces no
    generic batch report, so the report fields must not be REQUIRED when the
    selection envelope is present (occurrence 47671addc195 — before this fix the
    audit rejected the selection and the tool-call reconstruction dropped it,
    stranding the milestone with 'no executor update')."""
    from arnold_pipelines.megaplan.model_seam import (
        _reconcile_selection_capture_schema,
    )
    from arnold_pipelines.megaplan.schemas import SCHEMAS
    from arnold.pipeline.model_seam import validate_payload_against_schema

    schema = SCHEMAS["execution.json"]
    selection_payload = {
        "selected_shas": ["abc123", "def456"],
        "verification_evidence": {
            "reachability_checked": True,
            "chain_control_commits_excluded": True,
            "excluded_shas": ["c0ffee"],
            "per_phase": [
                {
                    "phase": "P1",
                    "sha": "abc123",
                    "subject": "feat(runtime): manifest admission",
                    "reason": "engine-source change",
                }
            ],
        },
    }
    # Before the relaxation the selection payload fails the required-field audit.
    assert validate_payload_against_schema(selection_payload, schema).ok is False
    relaxed = _reconcile_selection_capture_schema(schema, selection_payload, step="execute")
    assert relaxed is not schema
    assert validate_payload_against_schema(selection_payload, relaxed).ok is True

    # Ordinary execute payloads keep the strict report contract (fail-closed).
    ordinary = {
        "output": "done",
        "files_changed": [],
        "commands_run": [],
        "deviations": [],
        "task_updates": [],
        "sense_check_acknowledgments": [],
    }
    assert _reconcile_selection_capture_schema(schema, ordinary, step="execute") is schema
    incomplete = {"output": "done"}
    assert (
        validate_payload_against_schema(
            incomplete,
            _reconcile_selection_capture_schema(schema, incomplete, step="execute"),
        ).ok
        is False
    )

    # Non-execute steps are untouched.
    from arnold_pipelines.megaplan.schemas import SCHEMAS as _S

    gate_schema = _S["gate.json"]
    assert (
        _reconcile_selection_capture_schema(gate_schema, selection_payload, step="gate")
        is gate_schema
    )


def test_reconcile_selection_payload_does_not_block_task_tracking_gate() -> None:
    """A reconcile selection payload must not trip the per-task tracking /
    sense-check acknowledgment blocking reasons: the read-only selector's
    authoritative output IS the selection, so the batch completion gates are
    satisfied by it (occurrence 47671addc195 — the milestone stranded blocked
    with 'N/M tasks have no executor update' despite a complete selection)."""
    from arnold_pipelines.megaplan.execute.batch import build_blocking_reasons

    selection_payload = {
        "selected_shas": ["abc123"],
        "verification_evidence": {
            "per_phase": [
                {
                    "phase": "P1",
                    "sha": "abc123",
                    "subject": "feat(runtime): manifest admission",
                    "reason": "engine-source change",
                }
            ]
        },
    }
    reasons = build_blocking_reasons(
        tracked_tasks=0,
        total_tasks=4,
        acknowledged_checks=0,
        total_checks=4,
        missing_task_evidence=[],
        payload=selection_payload,
    )
    assert reasons == [], reasons

    # Without the selection envelope the same counts still block (fail-closed).
    reasons = build_blocking_reasons(
        tracked_tasks=0,
        total_tasks=4,
        acknowledged_checks=0,
        total_checks=4,
        missing_task_evidence=[],
        payload=None,
    )
    assert len(reasons) == 2, reasons
    assert any("tasks have no executor update" in r for r in reasons)
    assert any("sense checks have no executor acknowledgment" in r for r in reasons)

    # Timeout reasons still surface alongside a selection payload.
    reasons = build_blocking_reasons(
        tracked_tasks=0,
        total_tasks=4,
        acknowledged_checks=0,
        total_checks=4,
        missing_task_evidence=[],
        timeout_reason="execution timed out",
        payload=selection_payload,
    )
    assert reasons == ["execution timed out"], reasons


def test_reconcile_selection_payload_corroborates_completion_authority(
    tmp_path: Path,
) -> None:
    """The execute completion authority and the chain milestone authority must
    accept a reconcile selection payload as corroborated completion evidence
    (occurrence 47671addc195 — execute succeeded but the drive blocked on
    'execute terminal success lacks corroborated task completion' and the
    chain-level authority rejected pending tasks without batch updates)."""
    import json as _json

    from arnold_pipelines.megaplan import auto as auto_mod
    from arnold_pipelines.megaplan._core.io import execute_batch_artifact_path

    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "state.json").write_text(
        _json.dumps(
            {
                "name": "reconcile-test",
                "current_state": "done",
                "config": {"project_dir": str(tmp_path), "mode": "code"},
                "meta": {},
            }
        ),
        encoding="utf-8",
    )
    (plan_dir / "finalize.json").write_text(
        _json.dumps(
            {
                "tasks": [
                    {
                        "id": "T1",
                        "status": "pending",
                        "files_changed": [],
                        "commands_run": [],
                    },
                    {
                        "id": "T2",
                        "status": "pending",
                        "files_changed": [],
                        "commands_run": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    artifact_path = execute_batch_artifact_path(plan_dir, 1, ["T1", "T2"])
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        _json.dumps(
            {
                "selected_shas": ["abc123"],
                "verification_evidence": {"per_phase": []},
            }
        ),
        encoding="utf-8",
    )

    ok, missing = auto_mod._execute_completion_authority(plan_dir)
    assert ok is True, missing
    assert missing == []

    import arnold_pipelines.megaplan.chain.__init__ as chain_mod

    ok, reason = chain_mod._latest_execution_batch_all_tasks_done(plan_dir)
    assert ok is True, reason

    from arnold_pipelines.megaplan.handlers.review import (
        _review_execute_authority_gaps,
    )

    assert _review_execute_authority_gaps(
        finalize_data={"tasks": [{"id": "T1", "status": "pending"}, {"id": "T2", "status": "pending"}]},
        plan_dir=plan_dir,
        project_dir=tmp_path,
        state={"config": {"project_dir": str(tmp_path)}, "meta": {}},
    ) == []
