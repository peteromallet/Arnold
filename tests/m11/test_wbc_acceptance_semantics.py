from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import generate_m11_cross_contract_acceptance as aggregate


def _write_inventory(path: Path, *, static: list[dict], denies: list[dict],
                     declared: list[dict] | None = None,
                     runtime: list[dict] | None = None,
                     execute_ok: bool = True) -> None:
    rows = [{"boundary_id": "b1"}]
    payload = {
        "meta": {
            "schema": "m6.wbc-boundary-inventory.v1",
            "row_count": len(rows),
            "default_deny_count": len(denies),
            "unmatched_total_count": (
                len(static) + len(declared or []) + len(runtime or [])
            ),
            "content_hash": hashlib.sha256(
                json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest(),
        },
        "rows": rows,
        "default_deny_rows": denies,
        "unmatched_categories": {
            "unmatched_static": static,
            "unmatched_declared": declared or [],
            "unmatched_runtime": runtime or [],
        },
        "current_state_assertions": {
            "front_half_producers": {
                "expected_count": 5,
                "actual_count": 5,
                "count_matches": True,
            },
            "execute_batch_producers": {
                "expected_count": 8,
                "actual_count": 8 if execute_ok else 4,
                "count_matches": execute_ok,
                "missing": [] if execute_ok else ["execute_batch"],
            },
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _deny(target: str) -> dict:
    return {
        "row_kind": "default_deny",
        "target_path": target,
        "target_type": "runtime_module",
        "access": "denied",
        "reason": "Not an authoritative boundary surface.",
        "owner": "run_authority",
        "mitigation": "Add a classified matrix row before enabling access.",
    }


def test_static_candidate_is_closed_by_exact_default_deny(tmp_path: Path):
    path = tmp_path / "wbc.json"
    _write_inventory(
        path,
        static=[{"module_path": "pkg/mod.py"}],
        denies=[_deny("pkg/mod.py")],
    )
    result = aggregate._validate_wbc(tmp_path, Path("wbc.json"))
    assert result["passed"] is True


def test_static_candidate_without_default_deny_is_unresolved(tmp_path: Path):
    path = tmp_path / "wbc.json"
    _write_inventory(path, static=[{"module_path": "pkg/mod.py"}], denies=[])
    result = aggregate._validate_wbc(tmp_path, Path("wbc.json"))
    assert result["passed"] is False
    assert any(
        item["kind"] == "wbc_static_surface_without_default_deny"
        for item in result["failures"]
    )


def test_unknown_declared_and_runtime_rows_remain_real_gaps(tmp_path: Path):
    path = tmp_path / "wbc.json"
    _write_inventory(
        path,
        static=[],
        denies=[],
        declared=[{"boundary_id": "chain_complete", "reason_unmatched": "no_matrix_entry"}],
        runtime=[{"target_path": "runtime_trace", "status": "UNKNOWN", "owner": "UNKNOWN"}],
    )
    result = aggregate._validate_wbc(tmp_path, Path("wbc.json"))
    assert result["passed"] is False
    unresolved = next(
        item for item in result["failures"] if item["kind"] == "wbc_unresolved_rows"
    )
    assert unresolved["counts"] == {
        "unmatched_declared": 1,
        "unmatched_runtime": 1,
    }


def test_failed_execute_inventory_assertion_is_not_waived(tmp_path: Path):
    path = tmp_path / "wbc.json"
    _write_inventory(path, static=[], denies=[], execute_ok=False)
    result = aggregate._validate_wbc(tmp_path, Path("wbc.json"))
    assert result["passed"] is False
    assert any(
        item["kind"] == "wbc_current_state_assertion_failed"
        and item["assertion"] == "execute_batch_producers"
        for item in result["failures"]
    )
