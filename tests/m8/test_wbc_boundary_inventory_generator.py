from __future__ import annotations

import json
import textwrap
from pathlib import Path

from tools import generate_wbc_boundary_inventory as inventory_tool


def _module_scan_from_source(
    source: str,
    *,
    module_path: str = "synthetic/runtime_module.py",
) -> inventory_tool.ModuleScan:
    parsed = inventory_tool._parse_module_ast(textwrap.dedent(source))
    surface_types = tuple(
        inventory_tool._classify_module_surfaces(
            module_path,
            parsed["classes"],
            parsed["functions"],
            parsed["imports"],
            parsed["docstring"],
        )
    )
    return inventory_tool.ModuleScan(
        module_path=module_path,
        category="synthetic",
        owner=inventory_tool._owner_for_path(module_path),
        surface_types=surface_types,
        is_authority=inventory_tool._is_authority_surface(surface_types),
        classes=parsed["classes"],
        functions=parsed["functions"],
        imports=parsed["imports"],
        docstring_summary=parsed["docstring"],
        calls=parsed["calls"],
        try_scans=parsed["try_scans"],
        text_hits=parsed["text_hits"],
    )


def test_generator_emits_extended_inventory_and_preserves_c1_matrix(
    tmp_path: Path, monkeypatch
) -> None:
    evidence_dir = tmp_path / "evidence"
    output_path = evidence_dir / "wbc-boundary-inventory.json"
    historical_path = evidence_dir / "wbc-historical-adapters.json"
    rules_path = evidence_dir / "wbc-boundary-discovery-rules.yaml"
    support_manifest_path = tmp_path / "support_manifest.json"
    support_manifest_path.write_text(
        inventory_tool.SUPPORT_MANIFEST_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    before_hash = inventory_tool._matrix_hash()

    monkeypatch.setattr(inventory_tool, "EVIDENCE_DIR", evidence_dir)
    monkeypatch.setattr(inventory_tool, "DEFAULT_OUTPUT", output_path)
    monkeypatch.setattr(inventory_tool, "HISTORICAL_ADAPTERS_PATH", historical_path)
    monkeypatch.setattr(inventory_tool, "DISCOVERY_RULES_PATH", rules_path)
    monkeypatch.setattr(inventory_tool, "SUPPORT_MANIFEST_PATH", support_manifest_path)

    inventory = inventory_tool.generate(output_path)
    after_hash = inventory_tool._matrix_hash()

    assert before_hash == after_hash
    assert output_path.exists()
    assert historical_path.exists()
    assert rules_path.exists()
    assert (evidence_dir / "wbc-boundary-inventory-validation.json").exists()

    assert inventory["current_state_assertions"]["c1_matrix_unchanged"] is True
    assert inventory["current_state_assertions"]["support_rows_require_exact_set_equality"] is True
    assert (
        inventory["current_state_assertions"]["support_gate"]["exact_boundary_set_equality"] is False
    )
    assert len(inventory["rows"]) > 100
    assert inventory["meta"]["producer_callsite_count"] == len(inventory["producer_call_sites"])
    assert inventory["meta"]["compatibility_reader_count"] == len(
        inventory["compatibility_readers"]
    )
    assert inventory["meta"]["runtime_trace_digest_count"] == len(
        inventory["runtime_trace_digests"]
    )

    assert any(
        row["row_kind"] == "boundary_contract" and row["boundary_id"] == "execute_approval"
        for row in inventory["rows"]
    )
    assert any(
        row["module_path"] == "arnold_pipelines/megaplan/execute/batch.py"
        and row["callee"] == "write_boundary_receipt"
        and "execute_batch_checkpoint" in row["boundary_ids"]
        for row in inventory["producer_call_sites"]
    )
    assert any(
        "legacy-chain-state-reader" in row["reader_ids"]
        for row in inventory["compatibility_readers"]
    )
    assert any(
        row["registration_source"] == "writer_map_snapshot"
        for row in inventory["writer_registrations"]
    )
    assert any(
        row["module_path"] == "arnold_pipelines/megaplan/execute/batch.py"
        and row["candidate_type"] == "without_raising"
        for row in inventory["bypass_candidates"]
    )
    assert any(
        row["scenario_id"] == "D12-runtime-trace"
        and row["trace_directory_digest"].startswith("sha256:")
        and row["mapping_status"] == "unmapped"
        for row in inventory["runtime_trace_digests"]
    )

    execute_approval = next(
        row
        for row in inventory["rows"]
        if row["row_kind"] == "manifest_entry"
        and row["step_id"] == "megaplan.s4.execute_approval"
    )
    assert execute_approval["boundary_id"] == "execute_approval"
    assert execute_approval["declared_support_status"] == "supported"
    assert execute_approval["support_status"] == "partial"
    assert (
        execute_approval["support_verification"]["evidence_flags"]["exact_set_equality"] is False
    )
    assert "runtime trace digest" in execute_approval["support_verification"][
        "missing_requirements"
    ]
    assert all(
        row.get("support_status") != "supported"
        for row in inventory["rows"]
        if row["row_kind"] == "manifest_entry" and row.get("boundary_id")
    )

    regenerated_manifest = json.loads(support_manifest_path.read_text(encoding="utf-8"))
    regenerated_execute_approval = next(
        entry
        for family in regenerated_manifest["families"]
        for entry in family["entries"]
        if entry["step_id"] == "megaplan.s4.execute_approval"
    )
    assert regenerated_execute_approval["declared_support_status"] == "supported"
    assert regenerated_execute_approval["support_status"] == "partial"
    assert (
        regenerated_execute_approval["support_verification"]["support_gate_applicable"] is True
    )

    regenerated_schema_entry = next(
        entry
        for family in regenerated_manifest["families"]
        for entry in family["entries"]
        if entry["step_id"] == "arnold.workflow.authoring"
    )
    assert regenerated_schema_entry["declared_support_status"] == "supported"
    assert regenerated_schema_entry["support_status"] == "supported"
    assert regenerated_schema_entry["support_verification"]["support_gate_applicable"] is False

    historical = json.loads(historical_path.read_text(encoding="utf-8"))
    assert historical["meta"]["adapter_count"] >= 11
    assert set(historical["meta"]["adapter_classes_present"]) >= {
        "raw_json",
        "prose",
        "token",
        "filename",
        "marker",
        "process",
        "mutable_receipt",
    }
    assert historical["meta"]["adapter_count"] == historical["meta"]["read_only_verified_count"]
    by_id = {adapter["adapter_id"]: adapter for adapter in historical["adapters"]}
    assert "legacy-chain-state-reader" in by_id
    assert "historical-process-reader" in by_id
    assert by_id["legacy-chain-state-reader"]["adapter_class"] == "raw_json"
    assert by_id["historical-process-reader"]["adapter_class"] == "process"
    for adapter in historical["adapters"]:
        assert adapter["diagnostics"]
        assert adapter["expiry"]["milestone"]
        assert adapter["expiry"]["current_milestone"] == "M7"
        assert adapter["expiry"]["status"] in {"compatible", "expiring", "expired"}
        proof = adapter["zero_authority_caller_proof"]
        assert proof["read_only"] is True
        assert proof["diagnostic_only"] is True
        assert proof["authority_increasing_write_allowed"] is False
        assert proof["read_only_verified"] is True
        assert proof["authority_increasing_writes_detected"] == []

    rules_text = rules_path.read_text(encoding="utf-8")
    assert "producer_call_names:" in rules_text
    assert "legacy-chain-state-reader" in rules_text
    assert "historical-process-reader" in rules_text


def test_discover_bypass_candidates_flags_required_write_bypass_patterns(
    tmp_path: Path, monkeypatch
) -> None:
    repo_root = tmp_path / "repo"
    wrapper_path = repo_root / "wrappers" / "producer.sh"
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text("python emit_boundary.py || true\n", encoding="utf-8")
    monkeypatch.setattr(inventory_tool, "REPO_ROOT", repo_root)

    scan = _module_scan_from_source(
        """
        def emit_required_wbc_write(runtime, plan_dir):
            try:
                runtime.append_event("attempt-started")
            except Exception:
                pass

            # warn-and-continue path
            runtime.append_event("warn-path")

            # best-effort append path
            runtime.append_event("best-effort-path")

            # emit without raising
            runtime.append_event("without-raising-path")

            expected_source_version = "HEAD"
            latest_state = load_chain_state(plan_dir)
            runtime.append_event("latest-source-path")
        """,
        module_path="synthetic/required_write.py",
    )

    candidates = inventory_tool._discover_bypass_candidates(
        [scan],
        [{"path": "wrappers/producer.sh"}],
    )

    assert {
        row["candidate_type"]
        for row in candidates
        if row["module_path"] in {"synthetic/required_write.py", "wrappers/producer.sh"}
    } >= {
        "broad_exception",
        "warn_and_continue",
        "best_effort",
        "without_raising",
        "mutable_alias_overwrite",
        "implicit_latest_lookup",
        "shell_or_true",
    }


def test_discover_bypass_candidates_exempts_read_only_diagnostics() -> None:
    scan = _module_scan_from_source(
        """
        def summarize_diagnostics(plan_dir):
            \"\"\"diagnostic-only helper; read-only lookup for operator debugging.\"\"\"
            expected_source_version = "HEAD"
            try:
                return load_chain_state(plan_dir)
            except Exception:
                return {"warning": "diagnostic-only"}
        """,
        module_path="synthetic/read_only_diagnostics.py",
    )

    assert inventory_tool._discover_bypass_candidates([scan], []) == []
