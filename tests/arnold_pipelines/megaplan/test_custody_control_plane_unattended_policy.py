from __future__ import annotations

from pathlib import Path

import yaml

from arnold_pipelines.megaplan.chain.advancement import policy_for_spec
from arnold_pipelines.megaplan.chain.spec import load_spec


REPO_ROOT = Path(__file__).resolve().parents[3]
INITIATIVE = REPO_ROOT / ".megaplan" / "initiatives" / "custody-control-plane"
TARGET_BRANCH = "consolidate/arnold-runtime-activation-20260714"


def test_custody_chain_advances_automatically_after_review() -> None:
    spec = load_spec(INITIATIVE / "chain.yaml")
    policy = policy_for_spec(spec)

    assert spec.base_branch == TARGET_BRANCH
    assert spec.auto_approve is True
    assert policy.automatic_pr_progression is True
    assert policy.clean_milestone_pr == "auto"


def test_custody_cloud_uses_the_verified_runtime_target() -> None:
    cloud = yaml.safe_load((INITIATIVE / "cloud.yaml").read_text(encoding="utf-8"))

    assert cloud["repo"]["branch"] == TARGET_BRANCH
    assert cloud["megaplan"]["ref"] == TARGET_BRANCH


def test_future_custody_handoffs_use_evidence_not_discretionary_approval() -> None:
    future_briefs = (
        "m6-authority-contract-and-residual-inventory.md",
        "m6a-wbc-transactional-ledger-foundation.md",
        "m7-controlled-authoritative-writers.md",
    )

    combined = "\n".join(
        (INITIATIVE / "briefs" / name).read_text(encoding="utf-8")
        for name in future_briefs
    ).lower()
    assert "accepted human approval" not in combined
    assert "accepted approval record" not in combined
    assert "machine-verifiable ownership-decision record" in combined


def test_m5a_acceptance_gate_preserves_systemic_repair_goal_custody() -> None:
    watchdog = (
        REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "wrappers" / "arnold-watchdog"
    ).read_text(encoding="utf-8")

    retry_custody = watchdog.index("next_repair_goal_retry_sequence")
    acceptance_gate = watchdog.index("check_wrapper_acceptance_gate")
    dispatch = watchdog.index('if [[ ! -x "$PRIMARY_REPAIR_BIN" ]]')
    assert retry_custody < acceptance_gate < dispatch


def test_status_snapshot_retains_review_and_accepted_progress() -> None:
    status_snapshot = (
        REPO_ROOT / "arnold_pipelines" / "megaplan" / "cloud" / "status_snapshot.py"
    ).read_text(encoding="utf-8")

    assert '"review_verdict": review_verdict or None' in status_snapshot
    assert '"accepted_progress": accepted_progress' in status_snapshot
