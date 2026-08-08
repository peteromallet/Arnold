"""Tests for legacy critique-loop path retirement (CL5 Step 15).

Coverage:

* The inventory contains only real, existing modules (no phantom entries).
* critique_custody (bridge), gate_checks (reader), evaluation (reader) are
  RETIRED; critique_runtime is RETAINED as the single active target.
* Nonexistent modules are excluded from the inventory.
* ``retire_legacy_path`` verifies the BRIDGE hard-disable (CL4_BRIDGE_MODE is
  False) and binds the immutable CutoverConfig, rejecting an invalid config or
  an un-disabled bridge.
* ``generate_retirement_proof`` produces a well-formed proof bound to the
  North Star runtime.
"""

from __future__ import annotations

import json

import pytest

from arnold.critique_ledger.cutover.config import (
    CutoverConfig,
    CutoverConfigError,
    NORTH_STAR_RUNTIME_HASH,
)
from arnold.critique_ledger.cutover.retire import (
    ACTIVE_TARGET_MODULE,
    ComponentRole,
    LegacyComponent,
    RETIREMENT_PROOF_SCHEMA,
    RetirementError,
    RetirementStatus,
    build_inventory,
    generate_retirement_proof,
    retire_legacy_path,
)


def _valid_config() -> CutoverConfig:
    return CutoverConfig(
        source_revision=NORTH_STAR_RUNTIME_HASH,
        target_revision="t" * 40,
        schema_version="sch" * 13,
        wbc_contract_hash="w" * 40,
        m6_oracle_hash="o" * 40,
        corpus_fixture_hash="c" * 40,
        operator_approval_revision="op" * 20,
        backup_identity="b" * 40,
        build_revision="br" * 20,
        north_star_runtime_binding=NORTH_STAR_RUNTIME_HASH,
    )


# ── inventory ───────────────────────────────────────────────────────────────


class TestInventory:
    def test_inventory_contains_only_existing_modules(self) -> None:
        inventory = build_inventory()
        assert len(inventory) == 4
        # Every in-scope module is a real, importable module.
        import importlib

        for component in inventory:
            assert importlib.import_module(component.module) is not None

    def test_inventory_retires_bridge_and_legacy_readers(self) -> None:
        inventory = {c.module: c for c in build_inventory()}
        critique_custody = inventory[
            "arnold_pipelines.megaplan.orchestration.critique_custody"
        ]
        assert critique_custody.status is RetirementStatus.RETIRED
        assert critique_custody.role is ComponentRole.BRIDGE

        gate_checks = inventory[
            "arnold_pipelines.megaplan.orchestration.gate_checks"
        ]
        assert gate_checks.status is RetirementStatus.RETIRED
        assert gate_checks.role is ComponentRole.READER

        evaluation = inventory[
            "arnold_pipelines.megaplan.orchestration.evaluation"
        ]
        assert evaluation.status is RetirementStatus.RETIRED
        assert evaluation.role is ComponentRole.READER

    def test_inventory_retains_critique_runtime_as_active_target(self) -> None:
        inventory = {c.module: c for c in build_inventory()}
        runtime = inventory[ACTIVE_TARGET_MODULE]
        assert runtime.status is RetirementStatus.RETAINED
        assert runtime.role is ComponentRole.WRITER
        # critique_runtime must NOT be classified as legacy/retired.
        assert runtime.status is not RetirementStatus.RETIRED

    def test_excluded_nonexistent_module_is_absent_from_inventory(self) -> None:
        result = retire_legacy_path(_valid_config())
        # The genuinely-absent orchestration bridge is excluded.
        assert "arnold_pipelines.megaplan.orchestration.bridge" in result.excluded_nonexistent
        # And it is NOT in the inventory.
        inventory_modules = {c.module for c in result.inventory}
        assert "arnold_pipelines.megaplan.orchestration.bridge" not in inventory_modules


# ── retire_legacy_path ─────────────────────────────────────────────────────


class TestRetireLegacyPath:
    def test_succeeds_when_bridge_disabled_and_config_valid(self) -> None:
        result = retire_legacy_path(_valid_config())
        assert result.single_target_architecture_active is True
        assert result.retired_path_count == 3
        assert result.retained_path_count == 1
        assert result.bridge_mode_state == {
            "gate_signals": True,
            "critique_custody": True,
        }
        assert result.north_star_runtime_binding == NORTH_STAR_RUNTIME_HASH

    def test_rejects_invalid_config(self) -> None:
        bad = _valid_config()
        # Violate the North Star exact-runtime binding.
        invalid = CutoverConfig(
            source_revision="deadbeef" * 5,
            target_revision=bad.target_revision,
            schema_version=bad.schema_version,
            wbc_contract_hash=bad.wbc_contract_hash,
            m6_oracle_hash=bad.m6_oracle_hash,
            corpus_fixture_hash=bad.corpus_fixture_hash,
            operator_approval_revision=bad.operator_approval_revision,
            backup_identity=bad.backup_identity,
            build_revision=bad.build_revision,
            north_star_runtime_binding="deadbeef" * 5,
        )
        with pytest.raises(CutoverConfigError):
            retire_legacy_path(invalid)

    def test_fails_when_gate_signals_bridge_not_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.orchestration import gate_signals

        monkeypatch.setattr(gate_signals, "CL4_BRIDGE_MODE", True)
        with pytest.raises(RetirementError, match="gate_signals.CL4_BRIDGE_MODE"):
            retire_legacy_path(_valid_config())

    def test_fails_when_critique_custody_bridge_not_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.orchestration import critique_custody

        monkeypatch.setattr(critique_custody, "CL4_BRIDGE_MODE", True)
        with pytest.raises(RetirementError, match="critique_custody.CL4_BRIDGE_MODE"):
            retire_legacy_path(_valid_config())


# ── generate_retirement_proof ──────────────────────────────────────────────


class TestRetirementProof:
    def test_proof_structure_and_north_star_binding(self) -> None:
        proof = generate_retirement_proof(_valid_config(), now=0.0)
        assert proof["schema"] == RETIREMENT_PROOF_SCHEMA
        assert proof["single_target_architecture_active"] is True
        assert proof["active_target"] == ACTIVE_TARGET_MODULE
        # Immutable North Star exact-runtime binding.
        assert proof["cutover_config"]["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        assert proof["cutover_config"]["source_revision"] == NORTH_STAR_RUNTIME_HASH
        # Retired vs retained split.
        assert len(proof["retired_paths"]) == 3
        assert len(proof["retained_paths"]) == 1
        retained_modules = [p["module"] for p in proof["retained_paths"]]
        assert retained_modules == [ACTIVE_TARGET_MODULE]
        # Bridge hard-disable recorded.
        assert proof["bridge_mode_state"] == {
            "gate_signals": True,
            "critique_custody": True,
        }
        # Content hash present and well-formed.
        assert proof["content_hash"].startswith("sha256:")
        # No nonexistent module appears in the retired/retained inventory.
        all_modules = [p["module"] for p in proof["retired_paths"]] + [
            p["module"] for p in proof["retained_paths"]
        ]
        assert "arnold_pipelines.megaplan.orchestration.bridge" not in all_modules

    def test_proof_is_json_serializable(self) -> None:
        proof = generate_retirement_proof(_valid_config(), now=0.0)
        # Must round-trip through JSON (content_hash included).
        serialized = json.dumps(proof, sort_keys=True)
        restored = json.loads(serialized)
        assert restored["schema"] == RETIREMENT_PROOF_SCHEMA

    def test_proof_writes_to_output_path(self, tmp_path) -> None:
        out = tmp_path / "retirement-proof.json"
        proof = generate_retirement_proof(_valid_config(), output_path=str(out), now=0.0)
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["schema"] == RETIREMENT_PROOF_SCHEMA
        assert written["content_hash"] == proof["content_hash"]

    def test_proof_propagates_retirement_error_when_bridge_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from arnold_pipelines.megaplan.orchestration import gate_signals

        monkeypatch.setattr(gate_signals, "CL4_BRIDGE_MODE", True)
        with pytest.raises(RetirementError):
            generate_retirement_proof(_valid_config(), now=0.0)
