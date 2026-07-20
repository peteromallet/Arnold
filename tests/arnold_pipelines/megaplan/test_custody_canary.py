"""Idle pinned-runtime canary tests — projection promotion gate.

Proves that the canary promotion gate composes source provenance, Run
Authority, Custody lease, and WBC attempt checks into a single conjunctive
gate that blocks projection promotion unless all four sources verify.

Covers:
- Shadow mode (enforcement disabled) returns SHADOW_PASS
- Enforcement mode blocks on missing source provenance
- Enforcement mode blocks on missing lease (no lease store)
- Enforcement mode blocks on missing WBC attempt (no outbox)
- All four check types are present in every result
- PromotionGateContext validation (rejects invalid inputs)
- Source provenance verification (test double behavior)
- CanaryCheck conversion from action_validator SourceCheck
- PromotionGateResult serialization round-trip
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from arnold_pipelines.megaplan.custody.action_validator import (
    SourceCheck,
    ValidationOutcome,
)
from arnold_pipelines.megaplan.custody.canary import (
    CANARY_CHECK_TYPES,
    CANARY_SCHEMA_VERSION,
    CanaryCheck,
    CanaryOutcome,
    PromotionGateContext,
    PromotionGateDecision,
    PromotionGateResult,
    SourceProvenanceCheck,
    _verify_source_provenance,
    canary_enforcement_enabled,
    validate_promotion_gate,
    validate_promotion_gate_simple,
)
from arnold_pipelines.megaplan.custody.contracts import (
    CustodyTargetKey,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_target(**overrides: str) -> CustodyTargetKey:
    """Build a minimal valid CustodyTargetKey for tests."""
    defaults = {
        "environment": "env1",
        "session": "sess1",
        "chain": "chain1",
        "plan_revision": "rev1",
        "phase": "repair",
        "task": "task1",
        "attempt": "1",
        "normalized_failure_kind": "timeout",
        "blocker_or_phase_result_hash": "abc123",
        "fence": "42",
        "chain_identity": "",
    }
    defaults.update(overrides)
    return CustodyTargetKey(**defaults)


def _make_context(**overrides: object) -> PromotionGateContext:
    """Build a minimal valid PromotionGateContext for tests."""
    defaults: dict[str, object] = {
        "projection_id": "proj-1",
        "target": _make_target(),
        "run_authority_grant_id": "grant-1",
        "coordinator_fence_token": 42,
        "source_path": "/tmp/test-source",
        "wbc_attempt_reference": "wbc-1",
    }
    defaults.update(overrides)
    return PromotionGateContext(**defaults)  # type: ignore[arg-type]


class _EnvPatch:
    """Context manager to temporarily set/clear environment variables."""

    def __init__(self, **kwargs: str | None):
        self._patch = kwargs
        self._originals: dict[str, str | None] = {}

    def __enter__(self) -> _EnvPatch:
        for key, value in self._patch.items():
            self._originals[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return self

    def __exit__(self, *args: object) -> None:
        for key, original in self._originals.items():
            if original is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


# ── CanaryOutcome enum ───────────────────────────────────────────────────


class CanaryOutcomeTests(TestCase):
    """CanaryOutcome values are complete and correct."""

    def test_all_nine_outcomes_exist(self) -> None:
        expected = {
            "satisfied",
            "missing",
            "stale",
            "conflict",
            "expired",
            "fenced",
            "not_owner",
            "provenance_unverified",
            "error",
        }
        actual = {e.value for e in CanaryOutcome}
        self.assertEqual(expected, actual)

    def test_satisfied_is_truthy_equivalent(self) -> None:
        self.assertEqual(CanaryOutcome.SATISFIED, "satisfied")


# ── PromotionGateDecision enum ───────────────────────────────────────────


class PromotionGateDecisionTests(TestCase):
    """PromotionGateDecision values are complete."""

    def test_all_twelve_decisions_exist(self) -> None:
        expected = {
            "authorized",
            "shadow_pass",
            "blocked_source_provenance",
            "blocked_missing_grant",
            "blocked_fence_mismatch",
            "blocked_no_lease",
            "blocked_expired_lease",
            "blocked_stale_epoch",
            "blocked_not_owner",
            "blocked_wbc_missing",
            "blocked_wbc_conflict",
            "error",
        }
        actual = {e.value for e in PromotionGateDecision}
        self.assertEqual(expected, actual)


# ── SourceProvenanceCheck ────────────────────────────────────────────────


class SourceProvenanceCheckTests(TestCase):
    """SourceProvenanceCheck creation and serialization."""

    def test_creation_sets_defaults(self) -> None:
        spc = SourceProvenanceCheck(outcome=CanaryOutcome.SATISFIED)
        self.assertEqual(spc.outcome, CanaryOutcome.SATISFIED)
        self.assertTrue(spc.verified_at)
        self.assertEqual(spc.provenance_source, "")
        self.assertEqual(spc.observed_digest, "")

    def test_to_dict_includes_all_fields(self) -> None:
        spc = SourceProvenanceCheck(
            outcome=CanaryOutcome.PROVENANCE_UNVERIFIED,
            detail="test",
            provenance_source="git",
            observed_digest="sha256:abc",
            expected_digest="sha256:def",
        )
        d = spc.to_dict()
        self.assertEqual(d["outcome"], "provenance_unverified")
        self.assertEqual(d["detail"], "test")
        self.assertEqual(d["provenance_source"], "git")
        self.assertEqual(d["observed_digest"], "sha256:abc")
        self.assertEqual(d["expected_digest"], "sha256:def")


# ── CanaryCheck ──────────────────────────────────────────────────────────


class CanaryCheckTests(TestCase):
    """CanaryCheck creation, properties, and conversion."""

    def test_satisfied_check_not_blocked(self) -> None:
        cc = CanaryCheck(
            check_type="source_provenance",
            outcome=CanaryOutcome.SATISFIED,
        )
        self.assertTrue(cc.satisfied)
        self.assertFalse(cc.blocked)

    def test_missing_check_is_blocked(self) -> None:
        cc = CanaryCheck(
            check_type="custody_lease",
            outcome=CanaryOutcome.MISSING,
        )
        self.assertFalse(cc.satisfied)
        self.assertTrue(cc.blocked)

    def test_error_check_is_blocked(self) -> None:
        cc = CanaryCheck(
            check_type="run_authority",
            outcome=CanaryOutcome.ERROR,
        )
        self.assertTrue(cc.blocked)

    def test_to_dict_round_trip(self) -> None:
        cc = CanaryCheck(
            check_type="wbc_attempt",
            outcome=CanaryOutcome.SATISFIED,
            detail="ok",
            observed_value={"key": "val"},
        )
        d = cc.to_dict()
        self.assertEqual(d["check_type"], "wbc_attempt")
        self.assertEqual(d["outcome"], "satisfied")
        self.assertEqual(d["detail"], "ok")
        self.assertEqual(d["observed_value"], {"key": "val"})
        self.assertTrue(d["observed_at"])

    def test_from_source_check_satisfied(self) -> None:
        sc = SourceCheck(
            source="run_authority_grant",
            outcome=ValidationOutcome.SATISFIED,
            detail="grant is valid",
        )
        cc = CanaryCheck.from_source_check("run_authority", sc)
        self.assertEqual(cc.check_type, "run_authority")
        self.assertEqual(cc.outcome, CanaryOutcome.SATISFIED)
        self.assertEqual(cc.detail, "grant is valid")

    def test_from_source_check_maps_all_outcomes(self) -> None:
        # Every ValidationOutcome must map to a CanaryOutcome
        for vo in ValidationOutcome:
            sc = SourceCheck(source="custody_lease", outcome=vo)
            cc = CanaryCheck.from_source_check("custody_lease", sc)
            self.assertIsInstance(cc.outcome, CanaryOutcome)
            self.assertEqual(cc.check_type, "custody_lease")

    def test_from_provenance_check(self) -> None:
        spc = SourceProvenanceCheck(
            outcome=CanaryOutcome.PROVENANCE_UNVERIFIED,
            detail="mismatch",
            provenance_source="pip",
            observed_digest="sha256:abc",
            expected_digest="sha256:def",
        )
        cc = CanaryCheck.from_provenance_check(spc)
        self.assertEqual(cc.check_type, "source_provenance")
        self.assertEqual(cc.outcome, CanaryOutcome.PROVENANCE_UNVERIFIED)
        self.assertEqual(cc.detail, "mismatch")

    def test_check_type_must_be_valid(self) -> None:
        # All CanaryCheckType values should work
        for ct in CANARY_CHECK_TYPES:
            cc = CanaryCheck(check_type=ct, outcome=CanaryOutcome.SATISFIED)
            self.assertEqual(cc.check_type, ct)


# ── PromotionGateContext ─────────────────────────────────────────────────


class PromotionGateContextTests(TestCase):
    """PromotionGateContext validation."""

    def test_valid_context_accepted(self) -> None:
        ctx = _make_context()
        self.assertEqual(ctx.projection_id, "proj-1")
        self.assertEqual(ctx.run_authority_grant_id, "grant-1")
        self.assertEqual(ctx.coordinator_fence_token, 42)

    def test_empty_projection_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_context(projection_id="")

    def test_whitespace_projection_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_context(projection_id="   ")

    def test_empty_grant_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_context(run_authority_grant_id="")

    def test_negative_fence_token_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_context(coordinator_fence_token=-1)

    def test_bool_fence_token_rejected(self) -> None:
        # bool is a subclass of int in Python
        with self.assertRaises(ValueError):
            _make_context(coordinator_fence_token=True)  # type: ignore[arg-type]

    def test_non_string_wbc_reference_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_context(wbc_attempt_reference=123)  # type: ignore[arg-type]

    def test_non_string_owner_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _make_context(owner_host=123)  # type: ignore[arg-type]

    def test_non_custody_target_key_rejected(self) -> None:
        with self.assertRaises(TypeError):
            PromotionGateContext(
                projection_id="p",
                target="not-a-target",  # type: ignore[arg-type]
                run_authority_grant_id="g",
                coordinator_fence_token=0,
            )


# ── Source provenance verification ───────────────────────────────────────


class SourceProvenanceVerificationTests(TestCase):
    """_verify_source_provenance behavior with test doubles."""

    def setUp(self) -> None:
        self._tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self._tmpfile.write("test content for canary")
        self._tmpfile.close()
        self._tmp_path = self._tmpfile.name

    def tearDown(self) -> None:
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_existing_file_returns_satisfied(self) -> None:
        result = _verify_source_provenance(self._tmp_path)
        self.assertEqual(result.outcome, CanaryOutcome.SATISFIED)
        self.assertTrue(result.observed_digest)

    def test_non_existent_path_returns_provenance_unverified(self) -> None:
        result = _verify_source_provenance("/tmp/__nonexistent_canary_test_path__")
        self.assertEqual(result.outcome, CanaryOutcome.PROVENANCE_UNVERIFIED)

    def test_empty_path_returns_provenance_unverified(self) -> None:
        result = _verify_source_provenance("")
        self.assertEqual(result.outcome, CanaryOutcome.PROVENANCE_UNVERIFIED)

    def test_digest_mismatch_returns_provenance_unverified(self) -> None:
        result = _verify_source_provenance(
            self._tmp_path, expected_digest="sha256:0000000000000000000000000000000000000000000000000000000000000000"
        )
        self.assertEqual(result.outcome, CanaryOutcome.PROVENANCE_UNVERIFIED)
        self.assertEqual(result.expected_digest, "sha256:0000000000000000000000000000000000000000000000000000000000000000")

    def test_provenance_source_is_recorded(self) -> None:
        result = _verify_source_provenance(
            self._tmp_path, provenance_source="pip-audit"
        )
        self.assertEqual(result.provenance_source, "pip-audit")

    def test_directory_verification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # Create a file in the temp directory
            (Path(td) / "test.txt").write_text("hello")
            result = _verify_source_provenance(td)
            self.assertEqual(result.outcome, CanaryOutcome.SATISFIED)
            self.assertTrue(result.observed_digest)


# ── Promotion gate: shadow mode ──────────────────────────────────────────


class PromotionGateShadowModeTests(TestCase):
    """validate_promotion_gate in shadow mode (enforcement disabled)."""

    def test_shadow_mode_returns_shadow_pass(self) -> None:
        ctx = _make_context()
        result = validate_promotion_gate(ctx, enforcement_enabled=False)
        self.assertEqual(result.gate_result, PromotionGateDecision.SHADOW_PASS)
        self.assertFalse(result.authorized)
        self.assertFalse(result.blocked)
        self.assertTrue(result.is_shadow)

    def test_shadow_mode_has_all_four_checks(self) -> None:
        ctx = _make_context()
        result = validate_promotion_gate(ctx, enforcement_enabled=False)
        check_types = {c.check_type for c in result.checks}
        self.assertIn("source_provenance", check_types)
        self.assertIn("run_authority", check_types)
        self.assertIn("custody_lease", check_types)
        self.assertIn("wbc_attempt", check_types)

    def test_shadow_mode_diagnostics_include_projection_id(self) -> None:
        ctx = _make_context()
        result = validate_promotion_gate(ctx, enforcement_enabled=False)
        self.assertEqual(
            dict(result.diagnostics).get("projection_id"), "proj-1"
        )

    def test_shadow_mode_enforcement_env_var_defaults_off(self) -> None:
        ctx = _make_context()
        result = validate_promotion_gate(ctx)
        self.assertEqual(result.gate_result, PromotionGateDecision.SHADOW_PASS)


# ── Promotion gate: enforcement mode ─────────────────────────────────────


class PromotionGateEnforcementModeTests(TestCase):
    """validate_promotion_gate in enforcement mode."""

    def setUp(self) -> None:
        self._tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self._tmpfile.write("test content for enforcement test")
        self._tmpfile.close()
        self._tmp_path = self._tmpfile.name

    def tearDown(self) -> None:
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_enforcement_with_no_lease_store_blocks(self) -> None:
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        self.assertTrue(result.blocked)
        self.assertFalse(result.authorized)
        custody_check = next(
            c for c in result.checks if c.check_type == "custody_lease"
        )
        self.assertEqual(custody_check.outcome, CanaryOutcome.MISSING)

    def test_enforcement_returns_blocked_no_lease_or_wbc(self) -> None:
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        # Source provenance passes (valid temp file).
        # With no lease store and no outbox, the gate should be
        # BLOCKED_NO_LEASE (checked before WBC in precedence order)
        self.assertEqual(
            result.gate_result,
            PromotionGateDecision.BLOCKED_NO_LEASE,
        )

    def test_missing_source_provenance_blocks(self) -> None:
        ctx = _make_context(source_path="")
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        self.assertTrue(result.blocked)
        prov_check = next(
            c for c in result.checks if c.check_type == "source_provenance"
        )
        self.assertEqual(prov_check.outcome, CanaryOutcome.PROVENANCE_UNVERIFIED)
        self.assertEqual(
            result.gate_result, PromotionGateDecision.BLOCKED_SOURCE_PROVENANCE
        )

    def test_enforcement_result_is_not_shadow(self) -> None:
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        self.assertFalse(result.is_shadow)

    def test_enforcement_has_target_digest(self) -> None:
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        self.assertTrue(result.target_digest)


# ── PromotionGateResult dataclass ────────────────────────────────────────


class PromotionGateResultTests(TestCase):
    """PromotionGateResult dataclass validation and serialization."""

    def test_authorized_when_gate_is_authorized(self) -> None:
        pgr = PromotionGateResult(
            gate_result=PromotionGateDecision.AUTHORIZED,
            projection_id="p",
            target_digest="abc",
            checks=(),
            enforcement_enabled=True,
        )
        self.assertTrue(pgr.authorized)
        self.assertFalse(pgr.blocked)
        self.assertFalse(pgr.is_shadow)

    def test_not_authorized_when_shadow_pass(self) -> None:
        pgr = PromotionGateResult(
            gate_result=PromotionGateDecision.SHADOW_PASS,
            projection_id="p",
            target_digest="abc",
            checks=(),
            enforcement_enabled=False,
        )
        self.assertFalse(pgr.authorized)
        self.assertFalse(pgr.blocked)

    def test_blocked_when_gate_is_blocked(self) -> None:
        pgr = PromotionGateResult(
            gate_result=PromotionGateDecision.BLOCKED_NO_LEASE,
            projection_id="p",
            target_digest="abc",
            checks=(),
            enforcement_enabled=True,
        )
        self.assertTrue(pgr.blocked)
        self.assertFalse(pgr.authorized)

    def test_to_dict_round_trip(self) -> None:
        checks = (
            CanaryCheck(
                check_type="source_provenance",
                outcome=CanaryOutcome.SATISFIED,
            ),
        )
        pgr = PromotionGateResult(
            gate_result=PromotionGateDecision.SHADOW_PASS,
            projection_id="proj-test",
            target_digest="sha256:abc123",
            checks=checks,
            enforcement_enabled=False,
            diagnostics={"key": "value"},
        )
        d = pgr.to_dict()
        self.assertEqual(d["gate_result"], "shadow_pass")
        self.assertEqual(d["projection_id"], "proj-test")
        self.assertEqual(d["target_digest"], "sha256:abc123")
        self.assertEqual(len(d["checks"]), 1)
        self.assertFalse(d["enforcement_enabled"])
        self.assertEqual(d["diagnostics"], {"key": "value"})

    def test_rejects_non_decision_gate_result(self) -> None:
        with self.assertRaises(TypeError):
            PromotionGateResult(
                gate_result="not-a-decision",  # type: ignore[arg-type]
                projection_id="p",
                target_digest="d",
                checks=(),
            )

    def test_rejects_empty_projection_id(self) -> None:
        with self.assertRaises(ValueError):
            PromotionGateResult(
                gate_result=PromotionGateDecision.SHADOW_PASS,
                projection_id="",
                target_digest="d",
                checks=(),
            )

    def test_rejects_empty_target_digest(self) -> None:
        with self.assertRaises(ValueError):
            PromotionGateResult(
                gate_result=PromotionGateDecision.SHADOW_PASS,
                projection_id="p",
                target_digest="",
                checks=(),
            )


# ── Convenience API ──────────────────────────────────────────────────────


class ValidatePromotionGateSimpleTests(TestCase):
    """validate_promotion_gate_simple convenience wrapper."""

    def test_returns_result_in_shadow_mode(self) -> None:
        target = _make_target()
        result = validate_promotion_gate_simple(
            projection_id="proj-simple",
            target=target,
            run_authority_grant_id="grant-1",
            coordinator_fence_token=42,
            source_path="/tmp/test",
            wbc_attempt_reference="wbc-1",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.gate_result, PromotionGateDecision.SHADOW_PASS)

    def test_accepts_dict_target(self) -> None:
        result = validate_promotion_gate_simple(
            projection_id="proj-dict",
            target={
                "environment": "e",
                "session": "s",
                "chain": "c",
                "plan_revision": "r",
                "phase": "repair",
                "task": "t",
                "attempt": "1",
                "normalized_failure_kind": "timeout",
                "blocker_or_phase_result_hash": "h",
                "fence": "42",
            },
            run_authority_grant_id="g",
            coordinator_fence_token=0,
        )
        self.assertEqual(result.gate_result, PromotionGateDecision.SHADOW_PASS)

    def test_invalid_dict_target_returns_shadow_pass(self) -> None:
        result = validate_promotion_gate_simple(
            projection_id="proj-bad",
            target={"bad": "target"},
            run_authority_grant_id="g",
            coordinator_fence_token=0,
        )
        self.assertEqual(result.gate_result, PromotionGateDecision.SHADOW_PASS)

    def test_rejects_non_dict_non_target(self) -> None:
        with self.assertRaises(TypeError):
            validate_promotion_gate_simple(
                projection_id="p",
                target=42,  # type: ignore[arg-type]
                run_authority_grant_id="g",
                coordinator_fence_token=0,
            )


# ── Enforcement flag ─────────────────────────────────────────────────────


class CanaryEnforcementFlagTests(TestCase):
    """canary_enforcement_enabled() behavior."""

    def test_defaults_to_false(self) -> None:
        with _EnvPatch(ARNOLD_M7_CANARY_ENFORCEMENT=None):
            self.assertFalse(canary_enforcement_enabled())

    def test_zero_is_false(self) -> None:
        with _EnvPatch(ARNOLD_M7_CANARY_ENFORCEMENT="0"):
            self.assertFalse(canary_enforcement_enabled())

    def test_false_string_is_false(self) -> None:
        with _EnvPatch(ARNOLD_M7_CANARY_ENFORCEMENT="false"):
            self.assertFalse(canary_enforcement_enabled())

    def test_one_is_true(self) -> None:
        with _EnvPatch(ARNOLD_M7_CANARY_ENFORCEMENT="1"):
            self.assertTrue(canary_enforcement_enabled())

    def test_true_string_is_true(self) -> None:
        with _EnvPatch(ARNOLD_M7_CANARY_ENFORCEMENT="true"):
            self.assertTrue(canary_enforcement_enabled())


# ── SC22: Canary blocks projection promotion unless all sources verify ───


class CanaryBlockingProjectionPromotionTests(TestCase):
    """SC22: Canary failure blocks projection promotion unless all sources verify.

    The canary must verify:
    1. Installed source provenance
    2. Current Run Authority grant/fence
    3. Current Custody lease/epoch
    4. Current WBC attempt status

    Any failure blocks promotion in enforcement mode.
    """

    def setUp(self) -> None:
        self._tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        )
        self._tmpfile.write("test content for blocking test")
        self._tmpfile.close()
        self._tmp_path = self._tmpfile.name

    def tearDown(self) -> None:
        if os.path.exists(self._tmp_path):
            os.unlink(self._tmp_path)

    def test_shadow_mode_never_blocks(self) -> None:
        """In shadow mode, the canary never blocks promotion."""
        ctx = _make_context(source_path="")
        result = validate_promotion_gate(ctx, enforcement_enabled=False)
        self.assertEqual(result.gate_result, PromotionGateDecision.SHADOW_PASS)
        self.assertFalse(result.blocked)

    def test_missing_provenance_blocks_in_enforcement(self) -> None:
        """Missing installed source provenance blocks promotion."""
        ctx = _make_context(source_path="")
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        self.assertEqual(
            result.gate_result, PromotionGateDecision.BLOCKED_SOURCE_PROVENANCE
        )

    def test_no_lease_store_blocks_in_enforcement(self) -> None:
        """Missing custody lease blocks promotion (with valid source path)."""
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        custody_check = next(
            c for c in result.checks if c.check_type == "custody_lease"
        )
        self.assertEqual(custody_check.outcome, CanaryOutcome.MISSING)
        # Source provenance passes (valid file), so we get BLOCKED_NO_LEASE
        self.assertEqual(
            result.gate_result, PromotionGateDecision.BLOCKED_NO_LEASE
        )

    def test_all_four_source_checks_present(self) -> None:
        """Every validation result includes all four conjunctive checks."""
        ctx = _make_context(source_path=self._tmp_path)
        for enforcement in (False, True):
            with self.subTest(enforcement=enforcement):
                result = validate_promotion_gate(
                    ctx, enforcement_enabled=enforcement
                )
                check_types = {c.check_type for c in result.checks}
                self.assertIn("source_provenance", check_types)
                self.assertIn("run_authority", check_types)
                self.assertIn("custody_lease", check_types)
                self.assertIn("wbc_attempt", check_types)

    def test_authorized_requires_all_satisfied(self) -> None:
        """Authorized gate result requires all checks to be SATISFIED."""
        # In enforcement mode with no lease/outbox, we get blocked
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        self.assertFalse(result.authorized)
        # At least one check should be non-SATISFIED
        non_satisfied = [
            c for c in result.checks if c.outcome != CanaryOutcome.SATISFIED
        ]
        self.assertTrue(len(non_satisfied) > 0)

    def test_result_serialization_includes_all_checks(self) -> None:
        """Serialized result includes all checks for diagnostics."""
        ctx = _make_context(source_path=self._tmp_path)
        result = validate_promotion_gate(ctx, enforcement_enabled=True)
        d = result.to_dict()
        self.assertIn("checks", d)
        self.assertEqual(len(d["checks"]), len(result.checks))
        for check_dict in d["checks"]:
            self.assertIn("check_type", check_dict)
            self.assertIn("outcome", check_dict)


# ── Schema version ───────────────────────────────────────────────────────


class CanarySchemaVersionTests(TestCase):
    """CANARY_SCHEMA_VERSION is defined and positive."""

    def test_schema_version_is_positive_integer(self) -> None:
        self.assertIsInstance(CANARY_SCHEMA_VERSION, int)
        self.assertGreater(CANARY_SCHEMA_VERSION, 0)

    def test_canary_check_types_is_frozenset(self) -> None:
        self.assertIsInstance(CANARY_CHECK_TYPES, frozenset)
        self.assertEqual(len(CANARY_CHECK_TYPES), 4)
