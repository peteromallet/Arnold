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
