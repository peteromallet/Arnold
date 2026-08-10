"""Tests for the content-addressed cutover receipt (CL5 Step 16 / SC28).

Coverage (SC28: is the receipt hash computed over complete canonical JSON,
bridge_mode forced false, and activation conditional on verified retirement?):

* Happy path with a real backup manifest and a real retirement proof: every
  prescribed field is bound, ``bridge_mode`` is ``False``, and
  ``single_target_architecture_active`` is ``True`` only because the retirement
  proof verified against the config.
* **Hash over complete canonical JSON**: the receipt ``content_hash`` is a
  ``sha256`` over the full body; mutating ANY bound field (``bridge_mode``,
  ``single_target_architecture_active``, the North Star binding, an import
  count, the backup identity) is detected by ``verify_receipt_content_hash``.
* **bridge_mode forced false**: the receipt always carries ``bridge_mode =
  False``; there is no input path that can make it ``True``.
* **Activation conditional on verified retirement**: a tampered proof (bad
  content_hash), a wrong-schema proof, a proof that does not bind the config,
  or an invalid config all fail closed; a well-formed but non-activating proof
  yields an honest ``single_target_architecture_active = False`` receipt.
* The receipt binds the exact North Star runtime
  ``d5848010695e28ddb9d9cbee8675d7ebe725caae`` and the verified backup
  identity, and round-trips through JSON / output_path.
"""

from __future__ import annotations

import copy
import hashlib
import json
import uuid
from pathlib import Path

import pytest

from arnold.critique_ledger.cutover.config import (
    CutoverConfig,
    CutoverConfigError,
    NORTH_STAR_RUNTIME_HASH,
)
from arnold.critique_ledger.cutover.receipt import (
    CUTOVER_RECEIPT_SCHEMA,
    ReceiptError,
    evaluate_activation,
    generate_cutover_receipt,
    generate_cutover_receipt_to_file,
    verify_receipt_content_hash,
    verify_retirement_proof,
    write_receipt,
)
from arnold.critique_ledger.cutover.retire import (
    RETIREMENT_PROOF_SCHEMA,
    generate_retirement_proof,
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _valid_config(**overrides: str) -> CutoverConfig:
    base: dict[str, str] = {
        "source_revision": NORTH_STAR_RUNTIME_HASH,
        "target_revision": "t" * 40,
        "schema_version": "sch" * 13,
        "wbc_contract_hash": "w" * 40,
        "m6_oracle_hash": "o" * 40,
        "corpus_fixture_hash": "c" * 40,
        "operator_approval_revision": "op" * 20,
        "backup_identity": "b" * 40,
        "build_revision": "br" * 20,
        "north_star_runtime_binding": NORTH_STAR_RUNTIME_HASH,
    }
    base.update(overrides)
    return CutoverConfig(**base)


def _real_retirement_proof(now: float = 0.0) -> dict:
    """Generate a genuine retirement proof from the live (disabled) modules."""
    return generate_retirement_proof(_valid_config(), now=now)


def _synthetic_backup_manifest() -> dict:
    """A minimal but well-formed backup manifest for receipt binding tests."""
    return {
        "schema": "cl5.cutover-backup-manifest.v1",
        "bundle_sha256": "a" * 64,
        "content_hash": "sha256:" + "0" * 64,
        "file_count": 3,
    }


def _rehash(obj: dict) -> dict:
    """Recompute a content-addressed object's ``content_hash`` over its body."""
    body = {k: v for k, v in obj.items() if k != "content_hash"}
    obj["content_hash"] = "sha256:" + hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return obj


def _full_kwargs() -> dict:
    return {
        "backup_manifest": _synthetic_backup_manifest(),
        "import_counts": {"occurrences": 12, "reconciliations": 7, "dispositions": 5},
        "smoke_results": {"passed": True, "stages": ["quiesce", "backup", "receipt"]},
        "operator": {"identity": "arnold-op", "role": "release-engineer", "approved": True},
        "reviewer": {"identity": "reviewer-1", "role": "authority", "approved": True},
        "now": 0.0,
    }


# ── field binding ────────────────────────────────────────────────────────────


class TestReceiptBinding:
    def test_binds_every_prescribed_field_and_north_star(self) -> None:
        proof = _real_retirement_proof()
        receipt = generate_cutover_receipt(
            _valid_config(), retirement_proof=proof, **_full_kwargs()
        )
        assert receipt["schema"] == CUTOVER_RECEIPT_SCHEMA
        assert receipt["hash_algorithm"] == "sha256"
        # The exact North Star runtime.
        assert receipt["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        cfg = receipt["cutover_config"]
        assert cfg["source_revision"] == NORTH_STAR_RUNTIME_HASH
        assert cfg["target_revision"] == "t" * 40
        assert cfg["wbc_contract_hash"] == "w" * 40
        assert cfg["m6_oracle_hash"] == "o" * 40
        assert cfg["corpus_fixture_hash"] == "c" * 40
        assert cfg["north_star_runtime_binding"] == NORTH_STAR_RUNTIME_HASH
        # Backup identity bound.
        assert receipt["backup"]["bundle_sha256"] == "a" * 64
        assert receipt["backup"]["file_count"] == 3
        # Import counts + smoke + operator/reviewer bound.
        assert receipt["import_counts"]["occurrences"] == 12
        assert receipt["smoke_results"]["passed"] is True
        assert receipt["operator"]["identity"] == "arnold-op"
        assert receipt["reviewer"]["identity"] == "reviewer-1"
        assert receipt["generated_at"] == "1970-01-01T00:00:00Z"
        # Retirement proof identity bound.
        assert receipt["retirement_proof_binding"]["schema"] == RETIREMENT_PROOF_SCHEMA
        assert receipt["retirement_proof_binding"]["content_hash"] == proof["content_hash"]

    def test_receipt_is_json_serializable_and_round_trips(self) -> None:
        proof = _real_retirement_proof()
        receipt = generate_cutover_receipt(
            _valid_config(), retirement_proof=proof, **_full_kwargs()
        )
        restored = json.loads(json.dumps(receipt, sort_keys=True))
        assert restored["schema"] == CUTOVER_RECEIPT_SCHEMA
        assert verify_receipt_content_hash(restored) is True

    def test_writes_to_output_path(self, tmp_path: Path) -> None:
        proof = _real_retirement_proof()
        out = tmp_path / "receipt.json"
        receipt = generate_cutover_receipt_to_file(
            _valid_config(), str(out), retirement_proof=proof, **_full_kwargs()
        )
        written = json.loads(out.read_text(encoding="utf-8"))
        assert written["content_hash"] == receipt["content_hash"]
        assert verify_receipt_content_hash(written) is True


# ── bridge_mode forced false ─────────────────────────────────────────────────


class TestBridgeModeForcedFalse:
    def test_bridge_mode_is_false_on_activated_receipt(self) -> None:
        proof = _real_retirement_proof()
        receipt = generate_cutover_receipt(
            _valid_config(), retirement_proof=proof, **_full_kwargs()
        )
        assert receipt["bridge_mode"] is False
        assert receipt["single_target_architecture_active"] is True

    def test_bridge_mode_is_false_on_non_activated_receipt(self) -> None:
        # A well-formed proof that does not activate still yields bridge_mode
        # False (forced) — never a bridged receipt.
        proof = _real_retirement_proof()
        non_activating = copy.deepcopy(proof)
        non_activating["single_target_architecture_active"] = False
        _rehash(non_activating)
        receipt = generate_cutover_receipt(
            _valid_config(),
            retirement_proof=non_activating,
            backup_manifest=_synthetic_backup_manifest(),
            now=0.0,
        )
        assert receipt["bridge_mode"] is False
        assert receipt["single_target_architecture_active"] is False


# ── activation conditional on verified retirement ────────────────────────────


class TestActivationConditionalOnRetirement:
    def test_evaluate_activation_true_only_when_proof_verifies(self) -> None:
        proof = _real_retirement_proof()
        activation = evaluate_activation(_valid_config(), proof)
        assert activation.bridge_mode is False
        assert activation.retirement_verified is True
        assert activation.single_target_architecture_active is True

    def test_tampered_proof_content_hash_raises(self) -> None:
        proof = _real_retirement_proof()
        tampered = copy.deepcopy(proof)
        tampered["retired_path_count"] = 999  # body changed, content_hash stale
        with pytest.raises(ReceiptError, match="content_hash does not match"):
            generate_cutover_receipt(
                _valid_config(),
                retirement_proof=tampered,
                backup_manifest=_synthetic_backup_manifest(),
                now=0.0,
            )

    def test_wrong_schema_proof_raises(self) -> None:
        proof = _real_retirement_proof()
        bogus = copy.deepcopy(proof)
        bogus["schema"] = "something.else.v1"
        _rehash(bogus)
        with pytest.raises(ReceiptError, match="schema"):
            generate_cutover_receipt(
                _valid_config(),
                retirement_proof=bogus,
                backup_manifest=_synthetic_backup_manifest(),
                now=0.0,
            )

    def test_proof_binding_wrong_source_revision_raises(self) -> None:
        proof = _real_retirement_proof()
        mismatched = copy.deepcopy(proof)
        mismatched["cutover_config"]["source_revision"] = "deadbeef" * 5
        _rehash(mismatched)
        with pytest.raises(ReceiptError, match="source_revision does not match"):
            generate_cutover_receipt(
                _valid_config(),
                retirement_proof=mismatched,
                backup_manifest=_synthetic_backup_manifest(),
                now=0.0,
            )

    def test_proof_binding_wrong_north_star_raises(self) -> None:
        proof = _real_retirement_proof()
        mismatched = copy.deepcopy(proof)
        mismatched["cutover_config"]["north_star_runtime_binding"] = "deadbeef" * 5
        _rehash(mismatched)
        with pytest.raises(ReceiptError, match="north_star_runtime_binding"):
            generate_cutover_receipt(
                _valid_config(),
                retirement_proof=mismatched,
                backup_manifest=_synthetic_backup_manifest(),
                now=0.0,
            )

    def test_non_activating_proof_yields_false_not_raise(self) -> None:
        proof = _real_retirement_proof()
        non_activating = copy.deepcopy(proof)
        non_activating["single_target_architecture_active"] = False
        _rehash(non_activating)
        receipt = generate_cutover_receipt(
            _valid_config(),
            retirement_proof=non_activating,
            backup_manifest=_synthetic_backup_manifest(),
            now=0.0,
        )
        # Honest "pending" receipt: not activated, but still emitted (no false
        # completion evidence because single_target is False).
        assert receipt["single_target_architecture_active"] is False
        assert receipt["retirement_verified"] is False
        assert receipt["bridge_mode"] is False
        assert verify_receipt_content_hash(receipt) is True

    def test_invalid_config_raises_before_proof_inspection(self) -> None:
        proof = _real_retirement_proof()
        with pytest.raises(CutoverConfigError):
            generate_cutover_receipt(
                _valid_config(north_star_runtime_binding="deadbeef" * 5),
                retirement_proof=proof,
                backup_manifest=_synthetic_backup_manifest(),
                now=0.0,
            )

    def test_verify_retirement_proof_rejects_non_dict(self) -> None:
        with pytest.raises(ReceiptError, match="must be a dict"):
            verify_retirement_proof("not-a-dict", _valid_config())  # type: ignore[arg-type]


# ── content hash over complete canonical JSON ────────────────────────────────


class TestContentHashCompleteness:
    @pytest.mark.parametrize(
        "mutation",
        [
            # bridge_mode cannot be silently flipped to True.
            lambda r: r.__setitem__("bridge_mode", True),
            # activation cannot be silently flipped.
            lambda r: r.__setitem__("single_target_architecture_active", True),
            # North Star binding cannot be silently changed.
            lambda r: r.__setitem__("north_star_runtime_binding", "deadbeef" * 5),
            # An import count cannot be silently altered.
            lambda r: r["import_counts"].__setitem__("occurrences", 999),
            # The backup identity cannot be silently swapped.
            lambda r: r["backup"].__setitem__("bundle_sha256", "z" * 64),
            # The config target cannot be silently changed.
            lambda r: r["cutover_config"].__setitem__("target_revision", "hack"),
            # The retirement proof binding cannot be silently swapped.
            lambda r: r["retirement_proof_binding"].__setitem__("content_hash", "sha256:x"),
        ],
    )
    def test_any_field_mutation_breaks_content_hash(self, mutation) -> None:
        # Build a non-activated receipt so the activation-flip mutation is
        # meaningful (flipping False->True must be detectable).
        proof = _real_retirement_proof()
        non_activating = copy.deepcopy(proof)
        non_activating["single_target_architecture_active"] = False
        _rehash(non_activating)
        receipt = generate_cutover_receipt(
            _valid_config(),
            retirement_proof=non_activating,
            backup_manifest=_synthetic_backup_manifest(),
            import_counts={"occurrences": 12},
            now=0.0,
        )
        assert verify_receipt_content_hash(receipt) is True
        mutated = copy.deepcopy(receipt)
        mutation(mutated)
        # content_hash unchanged but a body field changed -> mismatch detected.
        assert verify_receipt_content_hash(mutated) is False

    def test_content_hash_covers_all_body_keys(self) -> None:
        proof = _real_retirement_proof()
        receipt = generate_cutover_receipt(
            _valid_config(),
            retirement_proof=proof,
            backup_manifest=_synthetic_backup_manifest(),
            now=0.0,
        )
        # Every key except content_hash participates in the canonical body.
        body_keys = {k for k in receipt if k != "content_hash"}
        body = {k: v for k, v in receipt.items() if k != "content_hash"}
        expected = "sha256:" + hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        assert receipt["content_hash"] == expected
        # And the body is the complete receipt minus the one self-hash field.
        assert body_keys == set(receipt.keys()) - {"content_hash"}
