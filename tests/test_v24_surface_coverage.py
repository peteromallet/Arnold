from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TEST_SURFACE = {
    "resolver/cache": ("tests/test_pack_resolver.py", {"test_resolver_writes_deterministic_cache_and_reuses_it"}),
    "rich/legacy lockfile": ("tests/test_nodes_lock.py", {"test_lockfile_rich_toml_round_trip_with_v24_identity_fields", "test_lockfile_legacy_round_trip_to_text"}),
    "node install/ensure/restore": ("tests/test_nodes_install.py", {"test_install_registry_pack_fails_when_class_set_cannot_be_derived"}),
    "lookup/refresh CLI": ("tests/test_cli_sources_workflows_nodes.py", {"test_cmd_nodes_lookup_resolves_pack", "test_cmd_nodes_refresh_template_dry_run_reports_diff"}),
    "schema compatibility": ("tests/test_node_packs_compat.py", {"test_resolve_node_packs_uses_rich_lock_class_sets"}),
    "template metadata": ("tests/test_custom_node_refs.py", {"test_structured_custom_nodes_normalize_to_string_nodes_and_refs"}),
    "porting emitter": ("tests/test_porting_convert.py", {"test_port_convert_ready_template_emits_structured_custom_node_refs"}),
    "unknown class remediation": ("tests/test_porting_workbench.py", {"test_analyze_source_infers_node_packs_from_runtime_classes_only"}),
    "migration buckets": ("tests/test_custom_node_ref_backfill.py", {"test_backfill_report_buckets_unknown_and_manual"}),
    "provenance": ("tests/test_pack_provenance.py", {"test_missing_declared_ref_for_locked_class_fails"}),
    "pin conflicts": ("tests/test_custom_node_refs.py", {"test_pack_pin_compatibility_reports_commit_conflict"}),
    "model assets/fetch": ("tests/test_fetch.py", {"test_download_verifies_downloaded_file_sha256"}),
    "model registry staging": ("tests/test_models_registry.py", {"test_stage_entry_passes_hf_revision_and_verifies_pins"}),
    "hardware/python diagnostics": ("tests/test_environment_diagnostics.py", {"test_doctor_reports_hardware_and_python_env_metadata"}),
    "traceability fixtures": ("tests/test_template_traceability.py", {"test_clean_traceability_fixture_passes"}),
}


def test_v24_focused_test_surface_is_present() -> None:
    missing: list[str] = []
    for label, (relative_path, expected_tests) in EXPECTED_TEST_SURFACE.items():
        path = REPO_ROOT / relative_path
        if not path.exists():
            missing.append(f"{label}: missing {relative_path}")
            continue
        discovered = _test_functions(path)
        absent = sorted(expected_tests - discovered)
        if absent:
            missing.append(f"{label}: missing {relative_path}::{', '.join(absent)}")
    assert missing == []


def _test_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
