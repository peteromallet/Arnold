from __future__ import annotations

import json
from pathlib import Path

from megaplan.store.warrant_sources import (
    REQUIRED_WARRANT_SOURCE_FIELDS,
    build_warrant_source_projection,
    inventory_warrant_sources,
)


def _complete_kwargs(kind: str) -> dict:
    verified_result_ref = {"kind": "verified_result", "sha256": "sha256:" + "a" * 64}
    return {
        "authority_envelope": {
            "authority_id": f"{kind}-authority",
            "policy_envelope": {"allow_models": ["codex:gpt-5.5"], "spend_ceiling_usd": 10},
            "grantor": "ops",
            "autonomy_level": "supervised",
        },
        "verified_work_account": {
            "account_id": f"{kind}-account",
            "verified_work_units": [{"task_id": "T1", "unit": 1}],
            "verified_result_ref": verified_result_ref,
        },
        "rationale_anchor": {
            "anchor_id": f"{kind}-rationale",
            "manifest_hash": "sha256:" + "b" * 64,
            "rationale_ref": {"path": "review.json", "field": "summary"},
        },
        "behavioral_or_manifest_hash": "sha256:" + "b" * 64,
        "verified_result_ref": verified_result_ref,
        "unsupported": ("provider_cost_ref", "ledger_refs"),
        "projection_id": f"{kind}-projection",
    }


def test_synthetic_complete_warrant_sources_are_signable_with_topology_independent_required_fields() -> None:
    one_shot = build_warrant_source_projection(**_complete_kwargs("one-shot"))
    multi_step = build_warrant_source_projection(**_complete_kwargs("multi-step"))

    assert one_shot.completeness.required_fields == list(REQUIRED_WARRANT_SOURCE_FIELDS)
    assert one_shot.completeness.signable is True
    assert multi_step.completeness.signable is True
    assert set(one_shot.completeness.present) >= set(REQUIRED_WARRANT_SOURCE_FIELDS)
    assert set(multi_step.completeness.present) >= set(REQUIRED_WARRANT_SOURCE_FIELDS)
    assert one_shot.verified_result_ref == multi_step.verified_result_ref


def test_real_source_partial_inventory_is_not_signable_and_does_not_mutate_receipts(tmp_path: Path) -> None:
    receipt = tmp_path / "step_receipt_execute_v1.json"
    receipt.write_text(json.dumps({"phase": "execute", "status": "ok"}, sort_keys=True), encoding="utf-8")
    before = receipt.read_text(encoding="utf-8")
    (tmp_path / "phase_result.json").write_text(
        json.dumps({"phase": "execute", "exit_kind": "success"}, sort_keys=True),
        encoding="utf-8",
    )

    projection = inventory_warrant_sources(tmp_path)

    assert receipt.read_text(encoding="utf-8") == before
    assert projection.completeness.signable is False
    assert "verified_result_ref" in projection.completeness.present
    assert "receipt_refs" in projection.completeness.present
    assert "authority_envelope" in projection.completeness.missing
    assert "verified_work_account" in projection.completeness.missing
    assert "rationale_anchor" in projection.completeness.missing
    assert "behavioral_or_manifest_hash" in projection.completeness.unsupported


def test_signability_is_computed_only_from_required_fields() -> None:
    kwargs = _complete_kwargs("optional-missing")
    kwargs.pop("unsupported")
    projection = build_warrant_source_projection(
        **kwargs,
        unsupported=("provider_cost_ref", "ledger_refs", "runtime_topology_hash"),
    )

    assert projection.completeness.signable is True
    assert "provider_cost_ref" in projection.completeness.unsupported
    assert "runtime_topology_hash" in projection.completeness.unsupported
