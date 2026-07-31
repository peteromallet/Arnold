"""M9 proof tests for authority-risk bypass gates."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from arnold_pipelines.megaplan.chain.spec import ChainState, save_chain_state
from arnold_pipelines.megaplan.cloud.wrapper_acceptance_gate import (
    check_wrapper_acceptance_gate,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETED_WRAPPERS = {
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop",
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop",
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-supervise",
    "arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog",
}
GATED_CALL_RE = re.compile(
    r"authority_(?:gap_continue|fail_closed|gap_record)\s+\"(T29-BYPASS-\d+)\""
)
EXPECTED_AUTHORITY_RISK_IDS = {
    f"T29-BYPASS-{number:03d}"
    for number in (
        24,
        25,
        30,
        31,
        *range(33, 39),
        *range(40, 45),
        56,
        59,
        61,
        *range(63, 68),
        74,
        75,
        *range(77, 80),
        *range(90, 93),
        *range(95, 117),
        *range(121, 125),
        *range(126, 129),
        *range(131, 134),
        136,
        140,
        142,
        *range(144, 150),
        *range(151, 165),
        177,
        *range(180, 206),
        207,
        208,
        *range(212, 215),
    )
} - {"T29-BYPASS-163"}


def _wrapper_text(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_audited_authority_risk_bypasses_emit_typed_gap_or_fail_closed() -> None:
    gated_ids: set[str] = set()
    for path in TARGETED_WRAPPERS:
        text = _wrapper_text(path)
        assert '"schema_version": "arnold.megaplan.cloud.wrapper_authority_gap.v1"' in text
        gated_ids.update(GATED_CALL_RE.findall(text))

    assert EXPECTED_AUTHORITY_RISK_IDS <= gated_ids


def test_authority_gap_schema_does_not_authorize_action_or_hide_failures() -> None:
    forbidden_authorizers = (
        "authorizes_action",
        "authorizes_mutation",
        "dispatch_authorized",
        "suppress_drift",
        "drift_suppressed",
    )
    for path in TARGETED_WRAPPERS:
        text = _wrapper_text(path)
        function_start = text.index("authority_gap_record() {")
        function_end = text.index("\n}\n", function_start) + 3
        function = text[function_start:function_end]
        assert '"disposition": disposition' in function
        assert '"evidence_id": evidence_id' in function
        assert all(token not in function for token in forbidden_authorizers)


def test_no_audited_bypass_line_can_swallow_authority_risk_with_naked_true() -> None:
    for path in TARGETED_WRAPPERS:
        for line_number, line in enumerate(_wrapper_text(path).splitlines(), start=1):
            if "T29-BYPASS-" not in line:
                continue
            assert "|| true" not in line, f"{path}:{line_number}: {line}"
            assert (
                "authority_gap_continue" in line
                or "authority_fail_closed" in line
                or "authority_gap_record" in line
            ), f"{path}:{line_number}: {line}"


def test_acceptance_gate_closes_without_validated_receipt_not_authorization(
    tmp_path: Path,
) -> None:
    spec_path = tmp_path / "chain.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "milestones": [{"label": "M5A", "idea": "m5a.md"}],
                "successors": [
                    {
                        "chain_spec_path": "next/chain.yaml",
                        "label": "M6",
                        "require_accepted_transaction": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    save_chain_state(
        spec_path,
        ChainState(
            current_milestone_index=0,
            completion_contract_mode="enforce",
            completed=[
                {
                    "label": "M5A",
                    "plan": "m5a-plan",
                    "milestone_index": 0,
                    "transaction_id": "tx-001",
                    "snapshot_hash": "sha256:test",
                    "source_commit_ref": "a" * 40,
                    "runtime_identity": "ci-main",
                    "acceptance_receipt": {
                        "transaction_id": "tx-001",
                        "snapshot_hash": "sha256:test",
                        "milestone_label": "M5A",
                        "milestone_index": 0,
                        "plan_name": "m5a-plan",
                    },
                }
            ],
        ),
    )

    result = check_wrapper_acceptance_gate(
        str(spec_path),
        workspace=str(tmp_path),
        caller_kind="watchdog",
    )

    assert result["gate_open"] is False
    assert result["reason"] == "acceptance gate closed for 'M5A': no acceptance receipt"
    blocker = result["blocker_event"]
    assert blocker["kind"] == "cloud_watchdog_dispatch_acceptance_gate_closed"
    assert blocker["predicate_kind"] == "unknown_acceptance_failure"
    assert "authorizes_action" not in json.dumps(result, sort_keys=True)
    assert "authorizes_mutation" not in json.dumps(result, sort_keys=True)


def test_drift_related_bypass_sites_keep_drift_visible_as_typed_evidence() -> None:
    drift_sites = []
    for path in TARGETED_WRAPPERS:
        lines = _wrapper_text(path).splitlines()
        for index, line in enumerate(lines):
            if "T29-BYPASS-" not in line:
                continue
            context = "\n".join(lines[max(0, index - 3) : index + 4]).lower()
            if "drift" in context or "suppress" in context:
                drift_sites.append((path, index + 1, line))

    assert drift_sites
    for path, line_number, line in drift_sites:
        assert (
            "authority_gap_continue" in line
            or "authority_fail_closed" in line
            or "authority_gap_record" in line
        ), f"{path}:{line_number}: {line}"
