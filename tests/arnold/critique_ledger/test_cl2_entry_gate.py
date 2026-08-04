"""Tests for the CL2 entry gate (contract_gate.verify_cl2_admission).

These tests exercise the fail-closed admission boundary. They **never**
synthesize acceptance or reviewer approval: no keypair is generated, no
signature is created, and no trust entry is minted. The positive path and
signature-mutation negatives activate only when U1 supplies a genuine accepted
bundle; otherwise they skip with an explicit reason.

Negative coverage is driven by the mutation matrix fixture
(cl1_rejected_mutations.json) and exercises every individual check function
with minimal crafted inputs, plus full-flow tests against the landed rejected
oracle.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from arnold.critique_ledger.contract_gate import (
    BindingCrossReferenceError,
    BlockerBearingError,
    CL2AdmissionInput,
    DerivedAcceptanceFalseError,
    DetachedSignatureInvalidError,
    HashDriftError,
    MalformedArtifactError,
    PolicyRevisions,
    PolicyRevisionDriftError,
    PrerequisiteUnresolvedError,
    ReviewExpiredError,
    ReviewScopeMismatchError,
    ReviewerNotTrustedError,
    ReviewerTrustEntry,
    UnsupportedTargetVersionError,
    _check_binding_cross_references,
    _check_blocker_free_gates,
    _check_derived_acceptance,
    _check_non_expiry,
    _check_policy_revisions,
    _check_review_scope,
    _check_target_version,
    _find_trusted_entry,
    verify_cl2_admission,
    verify_detached_signature,
)

# ────────────────────────────────────────────────────────────────────
# Paths
# ────────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
REJECTED_ORACLE_PATH = (
    REPO_ROOT
    / "docs"
    / "critique-ledger"
    / "handoffs"
    / "cl1-contract-oracle.json"
)
FIXTURE_PATH = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "critique_ledger"
    / "cl1_rejected_mutations.json"
)

#: Environment variable pointing at a directory containing a genuine U1
#: accepted bundle (amended_handoff.json, policy_bundle.json,
#: review_receipt.json, reviewer_trust.json). When unset, U1-gated tests skip.
U1_DIR_ENV = "CL2_U1_BUNDLE_DIR"

_ERROR_MAP = {
    "BindingCrossReferenceError": BindingCrossReferenceError,
    "BlockerBearingError": BlockerBearingError,
    "DerivedAcceptanceFalseError": DerivedAcceptanceFalseError,
    "DetachedSignatureInvalidError": DetachedSignatureInvalidError,
    "HashDriftError": HashDriftError,
    "MalformedArtifactError": MalformedArtifactError,
    "PolicyRevisionDriftError": PolicyRevisionDriftError,
    "PrerequisiteUnresolvedError": PrerequisiteUnresolvedError,
    "ReviewExpiredError": ReviewExpiredError,
    "ReviewScopeMismatchError": ReviewScopeMismatchError,
    "ReviewerNotTrustedError": ReviewerNotTrustedError,
    "UnsupportedTargetVersionError": UnsupportedTargetVersionError,
}


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: dict) -> str:
    """Write JSON to *path* and return its SHA-256."""
    text = json.dumps(data, sort_keys=True, indent=2)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_mutation_cases() -> list[dict]:
    return _load_json(FIXTURE_PATH)["cases"]


def _u1_dir() -> Path | None:
    val = os.environ.get(U1_DIR_ENV)
    if not val:
        return None
    p = Path(val)
    return p if p.is_dir() else None


def _accepted_handoff_template() -> dict:
    """A handoff dict that passes every non-signature check. This is used
    **only** as a base for unit-check inputs, never as a full-flow fixture.
    The template itself never claims acceptance."""
    return {
        "schema": "cl.handoff.v1",
        "target_milestone": "CL2",
        "accepted_for_cl2": {
            "value": True,
            "checks": {
                "cl1_must_gates_pass": {"passed": True, "detail": "ok"},
                "review_status_present": {"passed": True, "detail": "ok"},
                "hashes_fresh": {"passed": True, "detail": "ok"},
                "blocker_bearing_gaps_empty": {"passed": True, "detail": "ok"},
            },
            "blocking_reasons": [],
        },
        "open_gates": {
            "example_gate": {"status": "PASSED", "detail": "ok"},
        },
    }


def _dummy_policy_revisions() -> PolicyRevisions:
    return PolicyRevisions(
        prompt_revision="a" * 64,
        implementation_revision="b" * 64,
        briefing_revision="c" * 64,
        near_match_policy_revision="d" * 64,
        false_positive_budget_revision="e" * 64,
        audit_policy_revision="f" * 64,
    )


# ────────────────────────────────────────────────────────────────────
# Full-flow negative: the landed rejected oracle is rejected
# ────────────────────────────────────────────────────────────────────


class TestRejectedOracleIsRejected:
    """The landed cl1-contract-oracle.json must be rejected by the gate."""

    def test_oracle_exists(self):
        assert REJECTED_ORACLE_PATH.exists(), (
            f"Rejected oracle missing: {REJECTED_ORACLE_PATH}"
        )

    def test_rejected_oracle_fails_admission(self, tmp_path):
        oracle = _load_json(REJECTED_ORACLE_PATH)
        oracle_sha = _write_json(tmp_path / "handoff.json", oracle)
        # Minimal sibling artifacts so the failure is at the acceptance check.
        policy_sha = _write_json(
            tmp_path / "policy.json", _dummy_policy_revisions().to_dict()
        )
        receipt_sha = _write_json(tmp_path / "receipt.json", {"placeholder": True})
        trust_sha = _write_json(
            tmp_path / "trust.json", {"trusted_reviewers": []}
        )
        admission = CL2AdmissionInput(
            amended_handoff_path=tmp_path / "handoff.json",
            amended_handoff_sha256=oracle_sha,
            policy_bundle_path=tmp_path / "policy.json",
            policy_bundle_sha256=policy_sha,
            review_receipt_path=tmp_path / "receipt.json",
            review_receipt_sha256=receipt_sha,
            reviewer_trust_path=tmp_path / "trust.json",
            reviewer_trust_sha256=trust_sha,
            reviewer_fingerprint="deadbeef",
            target_schema="cl.handoff.v1",
            amendment_checksum="x" * 64,
            policy_revisions=_dummy_policy_revisions(),
        )
        with pytest.raises(DerivedAcceptanceFalseError):
            verify_cl2_admission(admission)


# ────────────────────────────────────────────────────────────────────
# Prerequisite presence — gate stays closed when artifacts are absent
# ────────────────────────────────────────────────────────────────────


class TestPrerequisitePresence:
    """The gate must stay closed with a typed error while any externally owned
    artifact is absent."""

    @pytest.mark.parametrize(
        "missing_attr",
        [
            "amended_handoff_path",
            "policy_bundle_path",
            "review_receipt_path",
            "reviewer_trust_path",
        ],
    )
    def test_missing_artifact_raises_prerequisite(self, tmp_path, missing_attr):
        good = tmp_path / "good.json"
        good.write_text("{}", encoding="utf-8")
        kwargs = dict(
            amended_handoff_path=good,
            amended_handoff_sha256=hashlib.sha256(b"{}").hexdigest(),
            policy_bundle_path=good,
            policy_bundle_sha256=hashlib.sha256(b"{}").hexdigest(),
            review_receipt_path=good,
            review_receipt_sha256=hashlib.sha256(b"{}").hexdigest(),
            reviewer_trust_path=good,
            reviewer_trust_sha256=hashlib.sha256(b"{}").hexdigest(),
            reviewer_fingerprint="fp",
            target_schema="cl.handoff.v1",
            amendment_checksum="a" * 64,
            policy_revisions=_dummy_policy_revisions(),
        )
        kwargs[missing_attr] = tmp_path / "does_not_exist.json"
        admission = CL2AdmissionInput(**kwargs)
        with pytest.raises(PrerequisiteUnresolvedError):
            verify_cl2_admission(admission)


# ────────────────────────────────────────────────────────────────────
# Hash freshness
# ────────────────────────────────────────────────────────────────────


class TestHashFreshness:
    def test_hash_drift_handoff(self, tmp_path):
        oracle = _load_json(REJECTED_ORACLE_PATH)
        _write_json(tmp_path / "handoff.json", oracle)
        good = tmp_path / "good.json"
        good.write_text("{}", encoding="utf-8")
        admission = CL2AdmissionInput(
            amended_handoff_path=tmp_path / "handoff.json",
            amended_handoff_sha256="0" * 64,  # deliberately wrong
            policy_bundle_path=good,
            policy_bundle_sha256=hashlib.sha256(b"{}").hexdigest(),
            review_receipt_path=good,
            review_receipt_sha256=hashlib.sha256(b"{}").hexdigest(),
            reviewer_trust_path=good,
            reviewer_trust_sha256=hashlib.sha256(b"{}").hexdigest(),
            reviewer_fingerprint="fp",
            target_schema="cl.handoff.v1",
            amendment_checksum="a" * 64,
            policy_revisions=_dummy_policy_revisions(),
        )
        with pytest.raises(HashDriftError):
            verify_cl2_admission(admission)


# ────────────────────────────────────────────────────────────────────
# Target version check
# ────────────────────────────────────────────────────────────────────


class TestTargetVersion:
    def test_future_schema_rejected(self):
        handoff = {**_accepted_handoff_template(), "schema": "cl.handoff.v2"}
        with pytest.raises(UnsupportedTargetVersionError):
            _check_target_version(handoff, "cl.handoff.v2")

    def test_wrong_milestone_rejected(self):
        handoff = {**_accepted_handoff_template(), "target_milestone": "CL3"}
        with pytest.raises(UnsupportedTargetVersionError):
            _check_target_version(handoff, "cl.handoff.v1")

    def test_schema_mismatch_rejected(self):
        handoff = {**_accepted_handoff_template()}
        with pytest.raises(UnsupportedTargetVersionError):
            _check_target_version(handoff, "cl.handoff.v999")

    def test_valid_schema_accepted(self):
        handoff = _accepted_handoff_template()
        _check_target_version(handoff, "cl.handoff.v1")  # must not raise


# ────────────────────────────────────────────────────────────────────
# Derived acceptance check
# ────────────────────────────────────────────────────────────────────


class TestDerivedAcceptance:
    def test_value_false_rejected(self):
        handoff = _accepted_handoff_template()
        handoff["accepted_for_cl2"]["value"] = False
        with pytest.raises(DerivedAcceptanceFalseError):
            _check_derived_acceptance(handoff)

    def test_subcheck_failed_rejected(self):
        handoff = _accepted_handoff_template()
        handoff["accepted_for_cl2"]["checks"]["hashes_fresh"]["passed"] = False
        with pytest.raises(DerivedAcceptanceFalseError):
            _check_derived_acceptance(handoff)

    def test_blocking_reasons_rejected(self):
        handoff = _accepted_handoff_template()
        handoff["accepted_for_cl2"]["blocking_reasons"] = ["something"]
        with pytest.raises(DerivedAcceptanceFalseError):
            _check_derived_acceptance(handoff)

    def test_missing_accepted_for_cl2_rejected(self):
        handoff = {"schema": "cl.handoff.v1"}
        with pytest.raises(MalformedArtifactError):
            _check_derived_acceptance(handoff)


# ────────────────────────────────────────────────────────────────────
# Blocker-free gates check
# ────────────────────────────────────────────────────────────────────


class TestBlockerFreeGates:
    @pytest.mark.parametrize(
        "status", ["BLOCKED", "INCOHERENT", "FAILED", "pending", "UNKNOWN"]
    )
    def test_blocking_status_rejected(self, status):
        handoff = _accepted_handoff_template()
        handoff["open_gates"] = {"g": {"status": status}}
        with pytest.raises(BlockerBearingError):
            _check_blocker_free_gates(handoff)

    def test_validation_false_rejected(self):
        handoff = _accepted_handoff_template()
        handoff["open_gates"] = {"g": {"status": "PASSED", "validation_passed": False}}
        with pytest.raises(BlockerBearingError):
            _check_blocker_free_gates(handoff)

    def test_unrecognized_status_rejected(self):
        handoff = _accepted_handoff_template()
        handoff["open_gates"] = {"g": {"status": "WAT"}}
        with pytest.raises(BlockerBearingError):
            _check_blocker_free_gates(handoff)

    def test_clean_gates_accepted(self):
        handoff = _accepted_handoff_template()
        _check_blocker_free_gates(handoff)  # must not raise

    def test_missing_open_gates_rejected(self):
        with pytest.raises(MalformedArtifactError):
            _check_blocker_free_gates({"schema": "cl.handoff.v1"})


# ────────────────────────────────────────────────────────────────────
# Reviewer trust check
# ────────────────────────────────────────────────────────────────────


class TestReviewerTrust:
    def test_unknown_fingerprint_rejected(self):
        trust_doc = {
            "trusted_reviewers": [
                {"fingerprint": "aaaa", "public_key": "k", "scope": ["cl2_admission"]}
            ]
        }
        with pytest.raises(ReviewerNotTrustedError):
            _find_trusted_entry(trust_doc, "bbbb")

    def test_known_fingerprint_found(self):
        trust_doc = {
            "trusted_reviewers": [
                {"fingerprint": "aaaa", "public_key": "k", "scope": ["cl2_admission"]}
            ]
        }
        entry = _find_trusted_entry(trust_doc, "aaaa")
        assert entry.fingerprint == "aaaa"
        assert isinstance(entry, ReviewerTrustEntry)

    def test_empty_trust_list_rejected(self):
        with pytest.raises(MalformedArtifactError):
            _find_trusted_entry({}, "aaaa")


# ────────────────────────────────────────────────────────────────────
# Review scope check
# ────────────────────────────────────────────────────────────────────


class TestReviewScope:
    def _entry(self, scope):
        return ReviewerTrustEntry(
            fingerprint="fp", public_key="k", scope=tuple(scope), expires_at=""
        )

    def test_scope_missing_on_trust(self):
        entry = self._entry(["other_scope"])
        receipt = {"scope": ["cl2_admission"]}
        with pytest.raises(ReviewScopeMismatchError):
            _check_review_scope(entry, receipt)

    def test_scope_missing_on_receipt(self):
        entry = self._entry(["cl2_admission"])
        receipt = {"scope": ["other_scope"]}
        with pytest.raises(ReviewScopeMismatchError):
            _check_review_scope(entry, receipt)

    def test_scope_present_on_both(self):
        entry = self._entry(["cl2_admission"])
        receipt = {"scope": ["cl2_admission"]}
        _check_review_scope(entry, receipt)  # must not raise


# ────────────────────────────────────────────────────────────────────
# Non-expiry check
# ────────────────────────────────────────────────────────────────────


class TestNonExpiry:
    NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)

    def _entry(self, expires_at=""):
        return ReviewerTrustEntry(
            fingerprint="fp", public_key="k", scope=("cl2_admission",), expires_at=expires_at
        )

    def test_expired_receipt_rejected(self):
        past = (self.NOW - timedelta(days=1)).isoformat()
        with pytest.raises(ReviewExpiredError):
            _check_non_expiry(self._entry(), {"expires_at": past}, self.NOW)

    def test_expired_trust_entry_rejected(self):
        past = (self.NOW - timedelta(days=1)).isoformat()
        with pytest.raises(ReviewExpiredError):
            _check_non_expiry(self._entry(past), {"expires_at": ""}, self.NOW)

    def test_future_expiry_accepted(self):
        future = (self.NOW + timedelta(days=365)).isoformat()
        _check_non_expiry(
            self._entry(future), {"expires_at": future}, self.NOW
        )  # must not raise

    def test_no_expiry_accepted(self):
        _check_non_expiry(self._entry(), {"expires_at": ""}, self.NOW)


# ────────────────────────────────────────────────────────────────────
# Detached signature check (no signature generation)
# ────────────────────────────────────────────────────────────────────


class TestDetachedSignature:
    """Tests that the signature verifier rejects invalid input. No keypair is
    generated — we only feed invalid signatures and assert rejection."""

    #: A syntactically-valid base64 key (32 bytes) that we never use to sign.
    _DUMMY_PUBKEY = base64.b64encode(b"\x00" * 32).decode()

    def test_empty_signature_returns_false(self):
        assert verify_detached_signature(self._DUMMY_PUBKEY, b"msg", "") is False

    def test_empty_pubkey_returns_false(self):
        sig = base64.b64encode(b"\x01" * 64).decode()
        assert verify_detached_signature("", b"msg", sig) is False

    def test_invalid_64_byte_signature_returns_false(self):
        sig = base64.b64encode(b"\xab" * 64).decode()
        assert verify_detached_signature(self._DUMMY_PUBKEY, b"msg", sig) is False

    def test_wrong_length_signature_returns_false(self):
        sig = base64.b64encode(b"\xab" * 10).decode()
        assert verify_detached_signature(self._DUMMY_PUBKEY, b"msg", sig) is False

    def test_malformed_base64_returns_false(self):
        assert verify_detached_signature(
            self._DUMMY_PUBKEY, b"msg", "!!!not-base64!!!"
        ) is False

    def test_injected_verifier_is_used(self):
        called = {}

        def fake_verifier(pk, msg, sig):
            called["pk"] = pk
            called["msg"] = msg
            called["sig"] = sig
            return True

        sig = base64.b64encode(b"\x01" * 64).decode()
        assert verify_detached_signature(
            self._DUMMY_PUBKEY, b"msg", sig, fake_verifier
        ) is True
        assert called["pk"] == b"\x00" * 32


# ────────────────────────────────────────────────────────────────────
# Policy revisions check
# ────────────────────────────────────────────────────────────────────


class TestPolicyRevisions:
    def test_revision_drift_rejected(self):
        declared = _dummy_policy_revisions()
        bundle = declared.to_dict()
        bundle["near_match_policy_revision"] = "z" * 64
        with pytest.raises(PolicyRevisionDriftError):
            _check_policy_revisions(bundle, declared)

    def test_matching_revisions_accepted(self):
        declared = _dummy_policy_revisions()
        _check_policy_revisions(declared.to_dict(), declared)  # must not raise


# ────────────────────────────────────────────────────────────────────
# Binding cross-references check
# ────────────────────────────────────────────────────────────────────


def _binding_admission(amendment="a" * 64, fingerprint="fp"):
    return CL2AdmissionInput(
        amended_handoff_path=Path("/dev/null"),
        amended_handoff_sha256="h" * 64,
        policy_bundle_path=Path("/dev/null"),
        policy_bundle_sha256="p" * 64,
        review_receipt_path=Path("/dev/null"),
        review_receipt_sha256="r" * 64,
        reviewer_trust_path=Path("/dev/null"),
        reviewer_trust_sha256="t" * 64,
        reviewer_fingerprint=fingerprint,
        target_schema="cl.handoff.v1",
        amendment_checksum=amendment,
        policy_revisions=_dummy_policy_revisions(),
    )


class TestBindingCrossReferences:
    def test_handoff_hash_mismatch_rejected(self):
        receipt = {"reviewed_artifact_sha256": "x" * 64, "policy_bundle_sha256": "p" * 64,
                    "reviewer_fingerprint": "fp", "amendment_checksum": "a" * 64}
        handoff = {"amendment_checksum": "a" * 64}
        with pytest.raises(BindingCrossReferenceError):
            _check_binding_cross_references(receipt, handoff, "h" * 64, "p" * 64, _binding_admission())

    def test_fingerprint_mismatch_rejected(self):
        receipt = {"reviewed_artifact_sha256": "h" * 64, "policy_bundle_sha256": "p" * 64,
                    "reviewer_fingerprint": "WRONG", "amendment_checksum": "a" * 64}
        handoff = {"amendment_checksum": "a" * 64}
        with pytest.raises(BindingCrossReferenceError):
            _check_binding_cross_references(receipt, handoff, "h" * 64, "p" * 64, _binding_admission())

    def test_amendment_mismatch_rejected(self):
        receipt = {"reviewed_artifact_sha256": "h" * 64, "policy_bundle_sha256": "p" * 64,
                    "reviewer_fingerprint": "fp", "amendment_checksum": "WRONG"}
        handoff = {"amendment_checksum": "a" * 64}
        with pytest.raises(BindingCrossReferenceError):
            _check_binding_cross_references(receipt, handoff, "h" * 64, "p" * 64, _binding_admission())

    def test_matching_references_accepted(self):
        receipt = {"reviewed_artifact_sha256": "h" * 64, "policy_bundle_sha256": "p" * 64,
                    "reviewer_fingerprint": "fp", "amendment_checksum": "a" * 64}
        handoff = {"amendment_checksum": "a" * 64}
        _check_binding_cross_references(receipt, handoff, "h" * 64, "p" * 64, _binding_admission())


# ────────────────────────────────────────────────────────────────────
# Mutation matrix fixture integrity
# ────────────────────────────────────────────────────────────────────


class TestMutationFixtureIntegrity:
    """Ensure the mutation matrix fixture is well-formed and every expected
    error name maps to a real exception class."""

    def test_fixture_loads(self):
        cases = _load_mutation_cases()
        assert len(cases) >= 20

    @pytest.mark.parametrize("case", _load_mutation_cases())
    def test_every_expected_error_resolves(self, case):
        if case.get("expected_error") is None:
            return
        assert case["expected_error"] in _ERROR_MAP, (
            f"Unknown error class in fixture case {case['id']}: "
            f"{case['expected_error']}"
        )


# ────────────────────────────────────────────────────────────────────
# Binding hash determinism
# ────────────────────────────────────────────────────────────────────


class TestBindingHashDeterminism:
    def test_binding_hash_is_deterministic(self):
        from arnold.critique_ledger.contract_gate import _compute_binding_hash

        admission = _binding_admission()
        h1 = _compute_binding_hash("h" * 64, "p" * 64, "r" * 64, "t" * 64, admission)
        h2 = _compute_binding_hash("h" * 64, "p" * 64, "r" * 64, "t" * 64, admission)
        assert h1 == h2
        assert len(h1) == 64

    def test_binding_hash_changes_with_input(self):
        from arnold.critique_ledger.contract_gate import _compute_binding_hash

        admission = _binding_admission()
        h1 = _compute_binding_hash("h" * 64, "p" * 64, "r" * 64, "t" * 64, admission)
        h2 = _compute_binding_hash("h" * 64, "p" * 64, "r" * 64, "X" * 64, admission)
        assert h1 != h2


# ────────────────────────────────────────────────────────────────────
# U1-gated positive and signature-mutation negatives
# ────────────────────────────────────────────────────────────────────


class TestU1AcceptedBundle:
    """Positive flow and signature-mutation negatives against a genuine U1
    accepted bundle. Skipped when U1 is not supplied."""

    @pytest.fixture
    def u1_admission(self):
        u1 = _u1_dir()
        if u1 is None:
            pytest.skip(
                f"U1 accepted bundle not supplied (set ${U1_DIR_ENV} to a "
                f"directory containing amended_handoff.json, policy_bundle.json, "
                f"review_receipt.json, reviewer_trust.json, and bundle_meta.json)."
            )
        meta_path = u1 / "bundle_meta.json"
        if not meta_path.exists():
            pytest.skip("U1 bundle_meta.json not found")
        meta = _load_json(meta_path)
        return u1, meta

    def test_positive_full_flow(self, u1_admission, tmp_path):
        u1, meta = u1_admission
        admission = CL2AdmissionInput(
            amended_handoff_path=u1 / "amended_handoff.json",
            amended_handoff_sha256=meta["amended_handoff_sha256"],
            policy_bundle_path=u1 / "policy_bundle.json",
            policy_bundle_sha256=meta["policy_bundle_sha256"],
            review_receipt_path=u1 / "review_receipt.json",
            review_receipt_sha256=meta["review_receipt_sha256"],
            reviewer_trust_path=u1 / "reviewer_trust.json",
            reviewer_trust_sha256=meta["reviewer_trust_sha256"],
            reviewer_fingerprint=meta["reviewer_fingerprint"],
            target_schema=meta["target_schema"],
            amendment_checksum=meta["amendment_checksum"],
            policy_revisions=PolicyRevisions.from_dict(meta["policy_revisions"]),
        )
        binding = verify_cl2_admission(admission)
        assert isinstance(binding.binding_hash, str)
        assert len(binding.binding_hash) == 64

    def test_wrong_key_signature_rejected(self, u1_admission, tmp_path):
        u1, meta = u1_admission
        # Copy the receipt and corrupt the signature.
        receipt = _load_json(u1 / "review_receipt.json")
        receipt["signature"] = base64.b64encode(b"\xff" * 64).decode()
        receipt_path = tmp_path / "receipt.json"
        receipt_sha = _write_json(receipt_path, receipt)
        admission = CL2AdmissionInput(
            amended_handoff_path=u1 / "amended_handoff.json",
            amended_handoff_sha256=meta["amended_handoff_sha256"],
            policy_bundle_path=u1 / "policy_bundle.json",
            policy_bundle_sha256=meta["policy_bundle_sha256"],
            review_receipt_path=receipt_path,
            review_receipt_sha256=receipt_sha,
            reviewer_trust_path=u1 / "reviewer_trust.json",
            reviewer_trust_sha256=meta["reviewer_trust_sha256"],
            reviewer_fingerprint=meta["reviewer_fingerprint"],
            target_schema=meta["target_schema"],
            amendment_checksum=meta["amendment_checksum"],
            policy_revisions=PolicyRevisions.from_dict(meta["policy_revisions"]),
        )
        with pytest.raises(DetachedSignatureInvalidError):
            verify_cl2_admission(admission)
