from __future__ import annotations

from pathlib import Path

from arnold_pipelines.megaplan.chain.advancement import (
    assess_advancement,
    policy_for_spec_path,
)
from arnold_pipelines.megaplan.chain import _automatic_pr_progression_permitted
from arnold_pipelines.megaplan.chain.spec import load_spec


def _write_spec(path: Path, *, merge: str = "auto", review: str = "auto") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""merge_policy: {merge}
review_policy:
  clean_milestone_pr: {review}
driver:
  auto_approve: true
milestones: []
""",
        encoding="utf-8",
    )


def test_runtime_manual_review_override_disables_automatic_pr_progression(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    # Use the production writer rather than assuming the sidecar filename.
    from arnold_pipelines.megaplan.chain.spec import save_runtime_policy

    save_runtime_policy(
        spec_path,
        {"review_policy": {"clean_milestone_pr": "manual"}},
    )

    policy = policy_for_spec_path(spec_path)

    assert policy.automatic_pr_progression is False
    assert policy.clean_milestone_pr == "manual"
    assert policy.source == "runtime_override"
    assert _automatic_pr_progression_permitted(load_spec(spec_path), spec_path) is False


def test_awaiting_pr_merge_respects_manual_review_but_merged_evidence_advances(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path, review="manual")
    policy = policy_for_spec_path(spec_path)

    waiting = assess_advancement(
        policy,
        current_state="done",
        chain_last_state="awaiting_pr_merge",
        pr_state="open",
    )
    merged = assess_advancement(
        policy,
        current_state="done",
        chain_last_state="awaiting_pr_merge",
        pr_state="merged",
    )

    assert waiting.action == "await_human"
    assert waiting.automatic is False
    assert waiting.gate == "review_policy.clean_milestone_pr"
    assert merged.action == "reconcile_terminal"
    assert merged.automatic is True


def test_review_and_between_milestone_actions_are_automatic_when_policy_allows(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    policy = policy_for_spec_path(spec_path)

    review = assess_advancement(policy, current_state="executed")
    between = assess_advancement(
        policy,
        current_state="done",
        chain_last_state="between_milestones",
    )

    assert (review.action, review.automatic) == ("run_review", True)
    # Terminal reconciliation is the first safe action; the normal chain then
    # initializes the next milestone through its guarded loop.
    assert (between.action, between.automatic) == ("reconcile_terminal", True)


def test_explicit_human_and_security_gates_always_win(tmp_path: Path) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    policy = policy_for_spec_path(spec_path)

    for gate in ("security_approval", "credential_account", "verification"):
        decision = assess_advancement(
            policy,
            current_state="executed",
            explicit_human_gate=gate,
        )
        assert decision.action == "await_human"
        assert decision.automatic is False
        assert decision.gate == gate


def test_active_step_is_never_duplicated(tmp_path: Path) -> None:
    spec_path = tmp_path / "initiative" / "chain.yaml"
    _write_spec(spec_path)
    decision = assess_advancement(
        policy_for_spec_path(spec_path),
        current_state="executed",
        active_step=True,
    )

    assert decision.action == "preserve_live"
    assert decision.automatic is False
