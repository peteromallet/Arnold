"""Freshness and shape gates for the generated NBF-05 signal inventory."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts/generate_nbf_signal_inventory.py"
ARTIFACT = ROOT / "docs/nbf-signal-inventory.json"
_GENERATOR = None


def _generator():
    global _GENERATOR
    if _GENERATOR is not None:
        return _GENERATOR
    spec = importlib.util.spec_from_file_location("nbf05_inventory_generator", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _GENERATOR = module
    return _GENERATOR


def test_generated_inventory_is_fresh():
    generator = _generator()
    assert generator.main(["--check"]) == 0


def test_inventory_schema_and_live_classes():
    generator = _generator()
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "nbf-signal-inventory-v1"
    assert payload["generator_version"] == "nbf05-signal-inventory-v1"
    assert payload["discovery_rules_version"] == generator.DISCOVERY_RULES_VERSION
    assert payload["discovery_rules"] == generator.DISCOVERY_RULES
    assert payload["source_inputs_sha256"]
    entries = payload["entries"]
    keys = [entry["site_id"] for entry in entries]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    assert any(entry["source_file"].endswith("incident/disposition.py") for entry in entries)
    assert any(entry["source_file"].endswith("cloud/wrappers/arnold-watchdog") for entry in entries)
    assert any(entry["source_file"].endswith("cloud/wrappers/arnold-heartbeat") for entry in entries)
    required = {
        "site_id", "source_file", "function_or_branch", "source_locator",
        "signal_or_probe", "subject_class", "worker_kill", "killer_kind",
        "context_resolver", "two_scan_required", "two_scan_owner",
        "confirmation_policy_identity", "disposition_test_id",
        "failure_order_test_id", "exclusion_reason",
    }
    assert all(required <= set(entry) for entry in entries)
    assert all(entry["exclusion_reason"] for entry in entries if not entry["worker_kill"])


def test_generator_is_deterministic_and_self_digest_is_excluded():
    generator = _generator()
    first = generator._render(generator.build_inventory())
    second = generator._render(generator.build_inventory())
    assert first == second
    payload = json.loads(first)
    source_files = generator._source_inputs(payload["entries"], generator.OUTPUT)
    assert generator.OUTPUT.resolve() not in source_files
    assert GENERATOR.resolve() not in source_files


def test_source_digest_excludes_generated_inventory_and_metadata():
    generator = _generator()
    first = generator.build_inventory(generator.OUTPUT)
    second = generator.build_inventory(ROOT / "docs/temporary-inventory.json")
    assert first["source_inputs_sha256"] == second["source_inputs_sha256"]
    assert "repository_revision" not in first
    assert "artifact_sha256" not in first


def test_source_digest_binds_discovery_contract(monkeypatch):
    generator = _generator()
    baseline = generator.build_inventory()["source_inputs_sha256"]
    monkeypatch.setattr(generator, "DISCOVERY_RULES_VERSION", "nbf05-discovery-rules-test-change")
    assert generator.build_inventory()["source_inputs_sha256"] != baseline
    assert generator.main(["--check"]) == 1


def test_source_digest_binds_normalized_discovery_rules_content(monkeypatch):
    generator = _generator()
    baseline = generator.build_inventory()["source_inputs_sha256"]
    monkeypatch.setitem(
        generator.DISCOVERY_RULES,
        "shell",
        generator.DISCOVERY_RULES["shell"] + "; normalized-content-change",
    )
    assert generator.build_inventory()["source_inputs_sha256"] != baseline
    assert generator.main(["--check"]) == 1


def test_check_rejects_stale_output(tmp_path: Path):
    generator = _generator()
    stale = tmp_path / "inventory.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert generator.main(["--check", "--output", str(stale)]) == 1


def test_python_generated_and_shell_controls_are_present():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    entries = payload["entries"]
    assert any(entry["site_id"].startswith("python-shell:") for entry in entries)
    assert any("ensure-megaplan-resident" in entry["source_file"] for entry in entries)
    assert any(entry["signal_or_probe"] == "probe:pgrep" for entry in entries)


def test_shell_signal_sites_are_classified():
    generator = _generator()
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    actual = [entry for entry in payload["entries"] if entry["site_id"].startswith("shell:")]
    expected = generator._shell_entries()
    assert {entry["site_id"] for entry in actual} == {entry["site_id"] for entry in expected}
    assert len(actual) == len(expected)
    for entry in actual:
        action = entry["signal_or_probe"].split(":", 1)[0]
        assert Path(entry["source_file"]).is_file() or (ROOT / entry["source_file"]).is_file()
        assert entry["disposition_test_id"] == "test_shell_signal_sites_are_classified"
        assert entry["failure_order_test_id"] == "test_shell_inventory_exclusions_are_explicit"
        if entry["worker_kill"]:
            assert action == "signal"
            assert entry["subject_class"] == "worker"
            assert entry["killer_kind"]
            assert entry["exclusion_reason"] is None
        else:
            assert entry["exclusion_reason"]
            assert entry["subject_class"] in {
                "liveness-probe", "process-supervision", "non-worker-lifecycle"
            }
        if entry["two_scan_required"]:
            assert entry["two_scan_owner"]
            assert entry["confirmation_policy_identity"]
        else:
            assert entry["two_scan_owner"] is None
            assert entry["confirmation_policy_identity"] is None
        source = (ROOT / entry["source_file"]).read_text(encoding="utf-8").splitlines()
        line = source[int(entry["source_locator"].rsplit(":", 1)[1]) - 1]
        assert not re.match(r"^\s*arnold_supervisor_signal_(?:non_worker_pid|bound_pid)\s*\(\)\s*\{", line)

    canonical = [
        entry for entry in actual
        if entry["signal_or_probe"] in {
            "signal:arnold_supervisor_signal_bound_pid",
            "signal:arnold_supervisor_signal_non_worker_pid",
        }
    ]
    assert canonical
    assert {Path(entry["source_file"]).name for entry in canonical} >= {
        "arnold-heartbeat", "arnold-progress-auditor", "arnold-supervisor-runtime-lib", "arnold-watchdog",
    }
    assert all(entry["subject_class"] == "non-worker-lifecycle" for entry in canonical)
    assert all(entry["worker_kill"] is False for entry in canonical)
    assert all(entry["two_scan_required"] is True for entry in canonical)
    assert all(entry["two_scan_owner"] == "arnold-supervisor-runtime-lib" for entry in canonical)
    assert all(entry["confirmation_policy_identity"] == "shell-nbf05-v1" for entry in canonical)
    assert all(entry["context_resolver"] == "canonical-non-worker-disposition" for entry in canonical)


def test_python_generated_shell_controls_are_classified():
    generator = _generator()
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    actual = [entry for entry in payload["entries"] if entry["site_id"].startswith("python-shell:")]
    expected = generator._python_generated_shell_entries()
    assert {entry["site_id"] for entry in actual} == {entry["site_id"] for entry in expected}
    assert len(actual) == len(expected)
    for entry in actual:
        assert (ROOT / entry["source_file"]).is_file()
        assert entry["subject_class"] == "non-worker-lifecycle"
        assert entry["worker_kill"] is False
        assert entry["context_resolver"] == "python-generated-shell"
        assert entry["two_scan_required"] is False
        assert entry["two_scan_owner"] is None
        assert entry["confirmation_policy_identity"] is None
        assert entry["disposition_test_id"] == "test_python_generated_shell_controls_are_classified"
        assert entry["failure_order_test_id"] == "test_shell_inventory_exclusions_are_explicit"
        assert entry["exclusion_reason"] == (
            "Python-generated shell lifecycle control is not a managed worker disposition"
        )


def test_shell_inventory_exclusions_are_explicit():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    rows = [
        entry for entry in payload["entries"]
        if entry["site_id"].startswith(("shell:", "python-shell:"))
        and not entry["worker_kill"]
    ]
    assert rows
    assert all(entry["failure_order_test_id"] == "test_shell_inventory_exclusions_are_explicit" for entry in rows)
    assert all(entry["exclusion_reason"] and len(entry["exclusion_reason"].split()) >= 5 for entry in rows)
    for entry in rows:
        action = entry["signal_or_probe"].split(":", 1)[0]
        if entry["site_id"].startswith("python-shell:"):
            assert action == "shell-generated"
            assert entry["subject_class"] == "non-worker-lifecycle"
        elif action == "probe":
            assert entry["subject_class"] == "liveness-probe"
        elif action == "supervision":
            assert entry["subject_class"] == "process-supervision"
        else:
            assert entry["subject_class"] == "non-worker-lifecycle"


def test_policy_prose_is_excluded_but_command_materializers_remain():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    entries = payload["entries"]
    assert not any(
        entry["source_file"].endswith("resident/profile.py")
        and entry["signal_or_probe"].endswith("tmux kill-server")
        for entry in entries
    )
    assert any(
        entry["source_file"] == "arnold_pipelines/megaplan/runtime/process.py"
        and entry["signal_or_probe"] == "shell-generated:tmux kill-server"
        for entry in entries
    )


def test_ensure_services_use_non_worker_post_proof_two_scan_bridge():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    entries = payload["entries"]
    bridge = [
        entry for entry in entries
        if entry["source_file"].endswith(("ensure-megaplan-watchdog", "ensure-megaplan-resident"))
        and entry["signal_or_probe"] == "signal:arnold_supervisor_signal_bound_pid"
    ]
    assert bridge
    assert all(entry["subject_class"] == "non-worker-lifecycle" for entry in bridge)
    assert all(entry["worker_kill"] is False for entry in bridge)
    assert all(entry["two_scan_required"] is True for entry in bridge)
    assert all(entry["two_scan_owner"] == "arnold-supervisor-runtime-lib" for entry in bridge)
    assert all(entry["confirmation_policy_identity"] == "shell-nbf05-v1" for entry in bridge)
    cleanup = [
        entry for entry in entries
        if entry["source_file"].endswith(("ensure-megaplan-watchdog", "ensure-megaplan-resident"))
        and entry["signal_or_probe"] == "signal:tmux kill-session"
    ]
    assert cleanup
    assert all(entry["worker_kill"] is False for entry in cleanup)
    assert all("post-proof" in entry["context_resolver"] for entry in cleanup)


def test_watchdog_tmux_cleanup_is_post_proof_non_worker():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    rows = [
        entry for entry in payload["entries"]
        if entry["source_file"].endswith("cloud/wrappers/arnold-watchdog")
        and entry["signal_or_probe"] == "signal:tmux kill-session"
    ]
    assert rows
    assert all(entry["subject_class"] == "non-worker-lifecycle" for entry in rows)
    assert all(entry["worker_kill"] is False for entry in rows)
    assert all(entry["two_scan_required"] is False for entry in rows)
    assert all(entry["two_scan_owner"] is None for entry in rows)
    assert all(entry["confirmation_policy_identity"] is None for entry in rows)
    assert all(entry["context_resolver"] == "canonical-supervisor-post-proof-cleanup" for entry in rows)
    assert all("post-proof" in entry["exclusion_reason"] for entry in rows)


def test_fan_kill_sites_use_typed_non_worker_lifecycle_door():
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    fan = [
        entry for entry in payload["entries"]
        if entry["source_file"].endswith("skills/subagent-launcher/fan_kill.py")
        and entry["signal_or_probe"].startswith("signal:")
    ]
    assert len(fan) == 2
    assert all(entry["subject_class"] == "non-worker-lifecycle" for entry in fan)
    assert all(entry["worker_kill"] is False for entry in fan)
    assert all(entry["context_resolver"] == "canonical-non-worker-disposition" for entry in fan)
    assert all(entry["two_scan_required"] is False for entry in fan)
    assert all(entry["two_scan_owner"] is None for entry in fan)
    assert all(entry["confirmation_policy_identity"] is None for entry in fan)
