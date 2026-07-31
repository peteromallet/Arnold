from __future__ import annotations

import json
from pathlib import Path

from scripts import generate_m11_cross_contract_acceptance as aggregate
from scripts.generate_m11_no_debt import _digest


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _sha(value: str) -> str:
    return "sha256:" + value * 64


def test_recovery_rejects_claimed_counts_without_rows(tmp_path: Path):
    path = Path("evidence/recovery.json")
    _write(tmp_path / path, {
        "schema_version": 1,
        "milestone": "M11",
        "sample_count": 42,
        "total_rows": 42,
        "eligible_rows": 42,
        "minimum_cohort_size": 20,
        "p95_seconds": 245.7,
        "slo_threshold_seconds": 300,
        "slo_met": True,
        "latency_ledger_rows": [],
    })
    result = aggregate._validate_recovery(tmp_path, path)
    assert result["passed"] is False
    kinds = {failure["kind"] for failure in result["failures"]}
    assert "recovery_latency_rows_empty" in kinds
    assert "recovery_claimed_count_mismatch" in kinds


def test_recovery_recomputes_rows_counts_and_p95(tmp_path: Path):
    path = Path("evidence/recovery.json")
    rows = [
        {
            "occurrence_id": f"occ-{index}",
            "eligible": True,
            "eligible_to_terminal_seconds": float(index),
            "terminal_receipt_sha256": _sha("a"),
            "terminal_outcome": "accepted_repair",
        }
        for index in range(1, 21)
    ]
    _write(tmp_path / path, {
        "schema_version": 1,
        "milestone": "M11",
        "sample_count": 20,
        "total_rows": 20,
        "eligible_rows": 20,
        "minimum_cohort_size": 20,
        "p95_seconds": 19.0,
        "slo_threshold_seconds": 300,
        "slo_met": True,
        "latency_ledger_rows": rows,
    })
    assert aggregate._validate_recovery(tmp_path, path)["passed"] is True


def test_runtime_route_wbc_genuine_block_and_debt_are_content_gated(
    tmp_path: Path,
):
    runtime = Path("evidence/runtime.json")
    required = {
        "interpreter", "editable_root", "pth", "import_roots",
        "source_lineage", "process_command", "systemd_wrapper",
        "target_marker", "runtime_provenance_receipt",
    }
    _write(tmp_path / runtime, {
        "schema": "m11.runtime-evidence.v1",
        "valid": True,
        "components": {
            name: {"ok": True, "evidence_sha256": _sha("b")}
            for name in required
        },
    })
    assert aggregate._validate_runtime_file(tmp_path, runtime)["passed"] is True

    route = Path("evidence/route.json")
    proof = {
        "complete": True,
        "forbids": ["label", "liveness", "wbc_receipt", "rebuildable_projection"],
    }
    _write(tmp_path / route, {
        "baseline_kind": "final_route_authority_closure",
        "closure": {
            "closure_complete": True,
            "exact_set_equal": True,
            "manifest_complete": True,
            "unplanned_count": 0,
            "planned_pending_count": 0,
            "manifest_surface_count": 1,
        },
        "route_closure_manifest": {
            "surface-1": {
                "surface_id": "surface-1",
                "closure_state": "closed",
                "content_hash": _sha("c"),
                "zero_authority_proof": proof,
            }
        },
    })
    assert aggregate._validate_route(tmp_path, route)["passed"] is True

    wbc = Path("evidence/wbc.json")
    wbc_rows = [{"boundary_id": "b1"}]
    wbc_hash = __import__("hashlib").sha256(
        json.dumps(wbc_rows, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    _write(tmp_path / wbc, {
        "meta": {
            "schema": "m6.wbc-boundary-inventory.v1",
            "row_count": 1,
            "default_deny_count": 0,
            "unmatched_total_count": 0,
            "content_hash": wbc_hash,
        },
        "rows": wbc_rows,
        "default_deny_rows": [],
        "unmatched_categories": {},
        "current_state_assertions": {
            "front_half_producers": {
                "expected_count": 5,
                "actual_count": 5,
                "count_matches": True,
            },
            "execute_batch_producers": {
                "expected_count": 4,
                "actual_count": 4,
                "count_matches": True,
                "missing": [],
            },
        },
    })
    assert aggregate._validate_wbc(tmp_path, wbc)["passed"] is True

    genuine = Path("evidence/genuine.json")
    _write(tmp_path / genuine, {
        "schema": "m11.genuine-block-receipt.v1",
        "status": "accepted_repair",
        "occurrence": {"digest": _sha("d")},
        "independent_verifier": {
            "accepted": True,
            "checks": {
                slot: {"passed": True}
                for slot in ("five_minute", "one_hour", "three_hour")
            },
        },
        "projection_agreement": True,
    })
    assert aggregate._validate_genuine_block(tmp_path, genuine)["passed"] is True

    debt = Path("evidence/no-debt.json")
    no_debt_receipt = {
        "schema": "m11.no-debt-receipt.v1",
        "aggregate_sha256": _sha("e"),
        "revision": {"git_commit": "a" * 40},
        "runtime": {"python": "/runtime/venv/bin/python"},
        "source_receipts": [
            {
                "kind": kind,
                "content_sha256": _sha(value),
                "command": ["python", "-P", "-m", "pytest", selector],
                "inventory_count": 1,
                "inventory_sha256": _sha(value),
                "custody_receipt_sha256": _sha("c"),
                "terminal_receipt_sha256": _sha("d"),
            }
            for kind, value, selector in (
                ("full_suite", "e", "tests"),
                ("semantic_carrier", "f", "tests/m11/test_semantics.py"),
            )
        ],
        "inventory_count": 2,
        "inventory_sha256": _sha("a"),
        "counts": {
            "collected": 2,
            "passed": 2,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "xfailed": 0,
            "xpassed": 0,
            "deselected": 0,
            "debt": 0,
        },
        "debt": {
            "xfail": 0,
            "xpass": 0,
            "skip": 0,
            "unresolved": 0,
        },
        "passed": True,
    }
    no_debt_receipt["content_sha256"] = _digest(no_debt_receipt)
    _write(tmp_path / debt, no_debt_receipt)
    assert aggregate._validate_no_debt(tmp_path, debt)["passed"] is True

    legacy = dict(no_debt_receipt)
    legacy["schema"] = "m11.no-debt.v1"
    legacy["content_sha256"] = _digest(
        {key: value for key, value in legacy.items() if key != "content_sha256"}
    )
    _write(tmp_path / debt, legacy)
    invalid = aggregate._validate_no_debt(tmp_path, debt)
    assert invalid["passed"] is False
    assert invalid["failures"][0]["kind"] == "no_debt_receipt_invalid"

    broken = json.loads((tmp_path / runtime).read_text())
    broken["components"]["target_marker"]["evidence_sha256"] = ""
    _write(tmp_path / runtime, broken)
    assert aggregate._validate_runtime_file(tmp_path, runtime)["passed"] is False


def test_audit_requires_real_complete_files_and_matching_digests(tmp_path: Path):
    repo = tmp_path / "repo"
    audit_root = tmp_path / "audit"
    rows = []
    for cycle_id in aggregate._REQUIRED_AUDIT_CYCLES:
        files = []
        for filename in aggregate._REQUIRED_AUDIT_FILES:
            path = audit_root / cycle_id / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"{cycle_id}:{filename}\n", encoding="utf-8")
            files.append({"filename": filename, "sha256": aggregate._file_sha256(path)})
        digest = aggregate._sha256_hex(aggregate._canonical_json_bytes({
            "cycle_id": cycle_id,
            "files": files,
        }))
        rows.append({
            "cycle_id": cycle_id,
            "is_complete": True,
            "provenance_digest": digest,
        })
    manifest = Path("evidence/audit-manifest.json")
    _write(repo / manifest, {"audit_cycle_trees": rows})
    assert aggregate._validate_audit(repo, manifest, audit_root)["passed"] is True

    rows[0]["provenance_digest"] = _sha("0")
    _write(repo / manifest, {"audit_cycle_trees": rows})
    result = aggregate._validate_audit(repo, manifest, audit_root)
    assert result["passed"] is False
    assert any(
        failure["kind"] == "audit_cycle_digest_or_status_mismatch"
        for failure in result["failures"]
    )


def test_forced_done_requires_independent_digest_bound_acceptance_receipt(
    tmp_path: Path,
):
    plan_dir = Path(".megaplan/plans/m11")
    forced = plan_dir / "operator_forced_chain_completion.json"
    _write(tmp_path / forced, {
        "schema": "arnold.megaplan.operator_forced_chain_completion.v1"
    })
    receipt = Path("evidence/m11-acceptance-receipt.json")
    result = aggregate._validate_forced_completion(
        tmp_path, plan_dir, receipt
    )
    assert result["passed"] is False
    assert any(
        failure["kind"] == "forced_done_without_acceptance_receipt"
        for failure in result["failures"]
    )

    _write(tmp_path / receipt, {
        "schema": "m11.acceptance-receipt.v1",
        "decision": "accepted",
        "forced_completion_sha256": aggregate._file_sha256(tmp_path / forced),
        "independent_verifier": True,
    })
    assert aggregate._validate_forced_completion(
        tmp_path, plan_dir, receipt
    )["passed"] is True
