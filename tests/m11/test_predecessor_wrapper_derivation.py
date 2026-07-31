from __future__ import annotations

import json
import hashlib
import shutil
from pathlib import Path

from arnold_pipelines.megaplan.orchestration.m11_predecessor_wrappers import (
    A7_RESEARCH_PATH,
    A7_INVENTORY_PATH,
    A7_SOURCE_PATHS,
    BLOCKED,
    F01_F17_PATH,
    M10_C01_C20_PATH,
    M5_FINAL_ATTESTATION_PATH,
    M5_COMPLETION_MANIFEST_PATH,
    M5_MIGRATION_MATRIX_PATH,
    M5_PROOF_MAP_PATH,
    SATISFIED,
    WRAPPER_PATHS,
    derive_predecessors,
    validate_wrapper,
    write_predecessor_wrappers,
)
from arnold_pipelines.megaplan.orchestration.m11_a7_inventory import (
    generate_a7_inventory,
)


def _write_json(root: Path, relative_path: Path, payload: dict) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _seed_sources(root: Path, *, m5_status: str, a7_status: str) -> None:
    _write_json(root, M10_C01_C20_PATH, {
        "schema_version": 1,
        "milestone": "M10",
        "step": "23A-23E",
        "generated_at": "2026-07-30T16:43:28+00:00",
        "conformance_pass": True,
        "bound_files": {"effects/effect_protocol": "a" * 64},
    })
    _write_json(root, F01_F17_PATH, {
        "schema_version": 1,
        "status": "reconciled",
        "scenarios": [{"id": f"F{index:02d}"} for index in range(1, 18)],
        "reconciliation": {"step": "18A"},
    })
    completion = {"schema": "arnold.megaplan.chain_completion_manifest.v1"}
    _write_json(root, M5_COMPLETION_MANIFEST_PATH, completion)
    completion_digest = hashlib.sha256(
        (root / M5_COMPLETION_MANIFEST_PATH).read_bytes()
    ).hexdigest()
    _write_json(root, M5_PROOF_MAP_PATH, {
        "schema": "arnold.megaplan.proof_map.v1",
        "m5-handoff": [M5_FINAL_ATTESTATION_PATH.as_posix()],
    })
    bound_path = Path("evidence/m5-bound-receipt.json")
    _write_json(root, bound_path, {"status": "accepted"})
    bound_digest = hashlib.sha256((root / bound_path).read_bytes()).hexdigest()
    _write_json(root, M5_FINAL_ATTESTATION_PATH, {
        "schema": "m5.final-attestation.v2",
        "generated_at": "2026-07-14T20:27:36Z",
        "repository_subject_head": "8" * 40,
        "retirement_status": "completed",
        "unresolved_evidence": [],
        "gates": {"canonical_manifest_sha256": completion_digest},
        "bound_artifacts": {
            bound_path.as_posix(): {"exists": True, "sha256": bound_digest},
        },
    })
    _write_json(root, M5_MIGRATION_MATRIX_PATH, {
        "schema": "m6.migration-matrix-reconciled.v1",
        "generated_at": "2026-07-21T23:36:19Z",
        "prerequisite_status": m5_status,
        "rows": [{"row_index": 0, "row_hash": "m" * 64,
                  "current_authority": "legacy raw state"}],
    })
    a7_complete = a7_status == "complete"
    a7_sources = {
        A7_SOURCE_PATHS[0]: {
            "schema": "m6.authority-reader-registry.v1",
            "rows": [{"reader_id": "r1", "row_hash": "r" * 64,
                      "current_contract": "legacy status reader"}],
        },
        A7_SOURCE_PATHS[1]: {
            "schema": "m6.controlled-writer-registry.v1",
            "rows": [{"writer_id": "w1", "row_hash": "w" * 64,
                      "current_contract": "compatibility writer"}],
        },
        A7_SOURCE_PATHS[2]: {
            "schema": "m6.rollout-deletion-register.v1",
            "rows": [{"entry_id": "d1", "row_hash": "d" * 64,
                      "deletion_gate": "delete legacy wrapper"}],
        },
        A7_SOURCE_PATHS[3]: {
            "meta": {"schema": "m6.wbc-historical-adapters.v1"},
            "adapters": [{
                "adapter_id": "historical-prose-reader",
                "path_symbols": ["arnold_pipelines/megaplan/_core/modes.py"],
                "observed_read_operations": ["is_prose_mode"],
            }],
        },
    }
    for support_path, payload in a7_sources.items():
        _write_json(root, support_path, payload)
    fixture_source = Path("arnold_pipelines/megaplan/_core/modes.py")
    fixture_target = root / fixture_source
    fixture_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(fixture_source, fixture_target)
    _write_json(root, A7_RESEARCH_PATH, {
        "findings": [{
            "area": "A7",
            "status": a7_status,
            "findings": [{"path": "legacy/status"}] if a7_complete else [],
            "files": ["arnold/legacy.py"] if a7_complete else [],
            "static_call_site_set_equality": a7_complete,
            "runtime_trace_coverage": ["trace-1"] if a7_complete else [],
            "source_registry_digests": (
                {"registry": "sha256:test"} if a7_complete else {}
            ),
            "error": "" if a7_complete else (
                "worker_structural_audit_failed: model output structural audit failed"
            ),
        }],
    })
    if a7_complete:
        _write_json(root, A7_INVENTORY_PATH, generate_a7_inventory(root))


def test_real_source_shapes_derive_digest_bound_fail_closed_wrappers(tmp_path: Path):
    _seed_sources(tmp_path, m5_status="INCOHERENT", a7_status="error")

    derived = derive_predecessors(tmp_path)
    assert derived["m10_c01_c20"].satisfied is True
    assert derived["m10_handoff"].satisfied is True
    assert derived["m5"].satisfied is True
    assert derived["a7"].satisfied is False

    wrappers = write_predecessor_wrappers(tmp_path)
    assert wrappers["m10_c01_c20"]["status"] == SATISFIED
    assert wrappers["m10_handoff"]["status"] == SATISFIED
    assert wrappers["m5"]["status"] == SATISFIED
    assert wrappers["a7"]["status"] == BLOCKED
    assert any(
        source["path"] == "evidence/migration-matrix-reconciled.json"
        for source in wrappers["m5"]["source_artifacts"]
    )
    assert wrappers["m5"]["observations"][0]["actual"] == "INCOHERENT"
    assert "worker_structural_audit_failed" in (
        wrappers["a7"]["observations"][0]["detail"]
    )
    assert "residual matrix rows" in wrappers["m5"]["next_action"]
    assert "static call-site equality" in wrappers["a7"]["next_action"]
    for family, wrapper in wrappers.items():
        assert (tmp_path / WRAPPER_PATHS[family]).is_file()
        assert validate_wrapper(wrapper, repo_root=tmp_path) == []


def test_all_wrappers_satisfy_only_when_genuine_sources_are_complete(tmp_path: Path):
    _seed_sources(tmp_path, m5_status="PASS", a7_status="complete")
    wrappers = write_predecessor_wrappers(tmp_path)
    assert all(wrapper["status"] == SATISFIED for wrapper in wrappers.values())
    a7_result = wrappers["a7"]["adapter_results"][0]
    assert a7_result["source_path"] == A7_INVENTORY_PATH.as_posix()
    assert a7_result["acceptance_row"]["evidence_refs"] == [
        A7_INVENTORY_PATH.as_posix()
    ]


def test_a7_inventory_joins_registries_and_captures_exact_runtime_set(tmp_path: Path):
    _seed_sources(tmp_path, m5_status="PASS", a7_status="complete")
    inventory = json.loads(
        (tmp_path / A7_INVENTORY_PATH).read_text(encoding="utf-8")
    )
    assert inventory["status"] == "satisfied"
    assert inventory["static_call_site_set_equality"] is True
    assert inventory["declared_callsite_ids"] == inventory["runtime_callsite_ids"]
    assert inventory["declared_callsite_ids"] == [
        "arnold_pipelines.megaplan._core.modes.is_prose_mode"
    ]
    assert inventory["static_call_sites"][0]["source_path"] == (
        "arnold_pipelines/megaplan/_core/modes.py"
    )
    assert inventory["static_call_sites"][0]["discovery"] == (
        "ast_function_definition"
    )
    assert set(inventory["source_bindings"]) == {
        "readers", "writers", "deletion", "historical_adapters", "migration"
    }
    assert all(inventory["registry_rows"].values())
    assert inventory["legacy_candidates"]


def test_a7_runtime_capture_failure_stays_blocked(
    tmp_path: Path, monkeypatch
):
    _seed_sources(tmp_path, m5_status="PASS", a7_status="error")
    from arnold_pipelines.megaplan.orchestration import m11_a7_inventory

    def fail_invoke(function, scratch):
        del function, scratch
        raise RuntimeError("deliberate trace failure")

    monkeypatch.setattr(m11_a7_inventory, "_invoke", fail_invoke)
    inventory = m11_a7_inventory.generate_a7_inventory(tmp_path)
    assert inventory["status"] == "blocked"
    assert inventory["static_call_site_set_equality"] is False
    assert any(
        failure["kind"] == "runtime_trace_invocation_failed"
        for failure in inventory["failures"]
    )
    assert any(
        failure["kind"] == "runtime_trace_missing"
        for failure in inventory["failures"]
    )


def test_source_or_wrapper_tampering_is_detected(tmp_path: Path):
    _seed_sources(tmp_path, m5_status="PASS", a7_status="complete")
    wrappers = write_predecessor_wrappers(tmp_path)

    _write_json(tmp_path, M10_C01_C20_PATH, {"schema_version": 1})
    source_failures = validate_wrapper(
        wrappers["m10_c01_c20"], repo_root=tmp_path
    )
    assert any(failure["kind"] == "source_digest_mismatch"
               for failure in source_failures)

    tampered = dict(wrappers["a7"])
    tampered["family"] = "tampered-a7"
    wrapper_failures = validate_wrapper(tampered, repo_root=tmp_path)
    assert any(failure["kind"] == "wrapper_digest_mismatch"
               for failure in wrapper_failures)


def test_incomplete_f01_f17_never_produces_satisfied_handoff(tmp_path: Path):
    _seed_sources(tmp_path, m5_status="PASS", a7_status="complete")
    _write_json(tmp_path, F01_F17_PATH, {
        "schema_version": 1,
        "status": "reconciled",
        "scenarios": [{"id": "F01"}],
        "reconciliation": {"step": "18A"},
    })
    wrappers = write_predecessor_wrappers(tmp_path)
    assert wrappers["m10_handoff"]["status"] == BLOCKED
    assert any(
        failure["kind"] == "scenario_coverage_mismatch"
        for failure in wrappers["m10_handoff"]["failures"]
    )
