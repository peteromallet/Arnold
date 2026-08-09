"""CL2 admission contract gate — fail-closed verification of the externally
reviewed CL1 admission bundle.

This module is the sole authority that derives the :class:`AcceptedCL1Binding`,
the authorization token required by every v2 store open and public writer. It
is **strictly read-only**: it never creates signatures, trust entries, or any
other acceptance / reviewer-approval data. It only reads externally supplied
artifacts and verifies them.

Verification order (each check raises a typed error before the next begins):

  1. prerequisite presence  — declared artifact paths must exist on disk
  2. hash freshness         — recomputed SHA-256 must match the declared hash
  3. JSON well-formedness   — each artifact parses and has required fields
  4. target version         — supported handoff schema identifier + milestone
  5. derived acceptance     — ``accepted_for_cl2.value`` is ``True`` and every
                              sub-check passed with no blocking reasons
  6. blocker-free gates     — no ``open_gates`` entry carries a blocking status
  7. reviewer trust         — declared fingerprint appears in the trust binding
  8. review scope           — both the trust entry and receipt scope include
                              ``cl2_admission``
  9. non-expiry             — receipt and trust entry have not expired
 10. detached signature     — Ed25519 signature over the canonical receipt
                              message verifies against the trusted public key
 11. three-way binding      — receipt cross-references match the recomputed
                              disk hashes and the declared amendment checksum
 12. policy revisions       — six policy revision hashes match the declared set

The detached signature is an Ed25519 detached signature over the UTF-8 bytes of
the canonical JSON encoding of the review receipt with the ``signature`` field
removed, keys sorted ascending, compact separators ``(",", ":")``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# ────────────────────────────────────────────────────────────────────
# Constants
# ────────────────────────────────────────────────────────────────────

#: The only handoff schema identifier this gate accepts.
SUPPORTED_HANDOFF_SCHEMAS: frozenset[str] = frozenset({"cl.handoff.v1"})

#: The target milestone this gate admits.
SUPPORTED_TARGET_MILESTONE: str = "CL2"

#: The scope tag that must be present on both the trust entry and the receipt.
REQUIRED_SCOPE: str = "cl2_admission"

#: Open-gate statuses that are considered blocking (case-insensitive).
_BLOCKING_GATE_STATUSES: frozenset[str] = frozenset(
    {
        "BLOCKED",
        "INCOHERENT",
        "FAILED",
        "PENDING",
        "UNKNOWN",
    }
)

#: Statuses that are explicitly acceptable (everything else is treated as
#: blocking to keep the gate fail-closed).
_OK_GATE_STATUSES: frozenset[str] = frozenset(
    {
        "PASSED",
        "COMPLETE",
        "COMPLETED",
        "OK",
        "ACCEPTED",
        "RESOLVED",
        "COHERENT",
        "DONE",
        "N/A",
        "NA",
        "",
    }
)


# ────────────────────────────────────────────────────────────────────
# Typed prerequisite failures
# ────────────────────────────────────────────────────────────────────


class CL2AdmissionError(Exception):
    """Base class for every CL2 admission prerequisite failure."""


class PrerequisiteUnresolvedError(CL2AdmissionError):
    """An externally owned accepted artifact or trust binding is absent."""


class MissingArtifactError(CL2AdmissionError):
    """A declared artifact path does not exist on disk."""


class HashDriftError(CL2AdmissionError):
    """A recomputed disk hash does not match the declared hash."""


class MalformedArtifactError(CL2AdmissionError):
    """An artifact is not valid JSON or is missing required fields."""


class UnsupportedTargetVersionError(CL2AdmissionError):
    """The handoff schema identifier or target milestone is unsupported."""


class DerivedAcceptanceFalseError(CL2AdmissionError):
    """The amended handoff's derived ``accepted_for_cl2`` expression is not
    fully accepting."""


class BlockerBearingError(CL2AdmissionError):
    """The amended handoff still carries open gates with blocking statuses."""


class ReviewerNotTrustedError(CL2AdmissionError):
    """The declared reviewer fingerprint is absent from the trust binding."""


class ReviewScopeMismatchError(CL2AdmissionError):
    """The trust entry or review receipt scope does not include cl2_admission."""


class ReviewExpiredError(CL2AdmissionError):
    """The review receipt or reviewer trust entry has expired."""


class DetachedSignatureInvalidError(CL2AdmissionError):
    """The detached review signature is absent or does not verify."""


class PolicyRevisionDriftError(CL2AdmissionError):
    """The policy bundle revisions do not match the declared set."""


class BindingCrossReferenceError(CL2AdmissionError):
    """The review receipt's cross-references do not match the recomputed disk
    hashes or the declared amendment checksum."""


# ────────────────────────────────────────────────────────────────────
# Frozen data records
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PolicyRevisions:
    """The six frozen policy revision hashes that pin the policy bundle.

    These are content hashes (not thresholds) so that the gate never invents
    policy values — it only pins the exact reviewed revisions.
    """

    prompt_revision: str
    implementation_revision: str
    briefing_revision: str
    near_match_policy_revision: str
    false_positive_budget_revision: str
    audit_policy_revision: str

    def to_dict(self) -> dict[str, str]:
        return {
            "prompt_revision": self.prompt_revision,
            "implementation_revision": self.implementation_revision,
            "briefing_revision": self.briefing_revision,
            "near_match_policy_revision": self.near_match_policy_revision,
            "false_positive_budget_revision": self.false_positive_budget_revision,
            "audit_policy_revision": self.audit_policy_revision,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PolicyRevisions":
        required = [
            "prompt_revision",
            "implementation_revision",
            "briefing_revision",
            "near_match_policy_revision",
            "false_positive_budget_revision",
            "audit_policy_revision",
        ]
        missing = [k for k in required if k not in d]
        if missing:
            raise MalformedArtifactError(
                f"Policy revisions missing keys: {missing}"
            )
        return cls(**{k: str(d[k]) for k in required})


@dataclass(frozen=True)
class CL2AdmissionInput:
    """The closed admission input — every externally owned artifact path and
    its declared SHA-256, plus the reviewer fingerprint, target schema,
    amendment checksum, and frozen policy revisions.

    This is a *closed* type: callers cannot add fields. Every path is resolved
    relative to the process working directory unless absolute.
    """

    amended_handoff_path: Path
    amended_handoff_sha256: str
    policy_bundle_path: Path
    policy_bundle_sha256: str
    review_receipt_path: Path
    review_receipt_sha256: str
    reviewer_trust_path: Path
    reviewer_trust_sha256: str
    reviewer_fingerprint: str
    target_schema: str
    amendment_checksum: str
    policy_revisions: PolicyRevisions


@dataclass(frozen=True)
class ReviewerTrustEntry:
    """One trusted reviewer parsed from the reviewer trust binding."""

    fingerprint: str
    public_key: str  # base64-encoded raw Ed25519 public key bytes
    scope: tuple[str, ...]
    expires_at: str  # ISO-8601; "" means no explicit expiry


@dataclass(frozen=True)
class AcceptedCL1Binding:
    """Immutable output of a successful admission verification.

    ``binding_hash`` is the deterministic authorization token that every v2
    store open and public writer must receive. It is the SHA-256 of the
    canonical encoding of the binding inputs and is stable across reruns as
    long as the accepted artifacts are byte-identical.
    """

    binding_hash: str
    amended_handoff_sha256: str
    policy_bundle_sha256: str
    review_receipt_sha256: str
    reviewer_trust_sha256: str
    reviewer_fingerprint: str
    target_schema: str
    amendment_checksum: str
    policy_revisions: PolicyRevisions


# ────────────────────────────────────────────────────────────────────
# Signature verifier protocol
# ────────────────────────────────────────────────────────────────────

#: ``(public_key_raw, message_bytes, signature_bytes) -> bool``
SignatureVerifier = Callable[[bytes, bytes, bytes], bool]


def _default_ed25519_verifier(
    public_key_raw: bytes, message_bytes: bytes, signature_bytes: bytes
) -> bool:
    """Default Ed25519 detached-signature verifier backed by ``cryptography``."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey,
    )

    try:
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(
            signature_bytes, message_bytes
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ────────────────────────────────────────────────────────────────────
# Hashing / parsing helpers
# ────────────────────────────────────────────────────────────────────


def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Compute the SHA-256 hex digest of a byte string."""
    return hashlib.sha256(data).hexdigest()


def _canonical_receipt_message(receipt: dict[str, Any]) -> bytes:
    """Compute the canonical signed message bytes for a review receipt.

    The signature covers the UTF-8 bytes of the receipt serialized with keys
    sorted ascending and compact separators, **excluding** the ``signature``
    field itself.
    """
    redacted = {k: v for k, v in receipt.items() if k != "signature"}
    return json.dumps(
        redacted, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _load_json(path: Path, label: str) -> dict[str, Any]:
    """Load and parse a JSON object from *path*, raising on malformed content."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise MalformedArtifactError(f"{label}: cannot read {path}: {exc}")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise MalformedArtifactError(
            f"{label}: invalid JSON at {path}: {exc}"
        )
    if not isinstance(data, dict):
        raise MalformedArtifactError(
            f"{label}: expected JSON object, got {type(data).__name__}"
        )
    return data


def _parse_iso(value: str) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp into an aware UTC datetime.

    Returns ``None`` for an empty string (meaning "no explicit expiry").
    """
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ────────────────────────────────────────────────────────────────────
# Individual verification checks (exposed for unit testing)
# ────────────────────────────────────────────────────────────────────


def _check_prerequisite_presence(admission: CL2AdmissionInput) -> None:
    """Check 1: every declared artifact path must exist."""
    artifacts = [
        ("amended_handoff", admission.amended_handoff_path),
        ("policy_bundle", admission.policy_bundle_path),
        ("review_receipt", admission.review_receipt_path),
        ("reviewer_trust", admission.reviewer_trust_path),
    ]
    missing = [
        f"{label}: {path}" for label, path in artifacts if not path.exists()
    ]
    if missing:
        raise PrerequisiteUnresolvedError(
            "CL2 admission gate is closed — externally owned accepted "
            "artifacts are absent: " + ", ".join(missing)
        )


def _check_hash_freshness(
    label: str, path: Path, declared_sha256: str
) -> str:
    """Check 2: recompute SHA-256 from disk and compare to the declared hash.

    Returns the recomputed hash on success.
    """
    actual = sha256_file(path)
    if actual != declared_sha256:
        raise HashDriftError(
            f"{label}: hash drift — declared {declared_sha256[:16]}… "
            f"but recomputed {actual[:16]}…"
        )
    return actual


def _check_target_version(handoff: dict[str, Any], target_schema: str) -> None:
    """Check 4: handoff schema and target milestone must be supported."""
    schema = handoff.get("schema", "")
    if schema not in SUPPORTED_HANDOFF_SCHEMAS:
        raise UnsupportedTargetVersionError(
            f"Unsupported handoff schema {schema!r}. "
            f"Supported: {sorted(SUPPORTED_HANDOFF_SCHEMAS)}."
        )
    milestone = handoff.get("target_milestone", "")
    if milestone != SUPPORTED_TARGET_MILESTONE:
        raise UnsupportedTargetVersionError(
            f"Unsupported target milestone {milestone!r}. "
            f"Required: {SUPPORTED_TARGET_MILESTONE!r}."
        )
    if target_schema != schema:
        raise UnsupportedTargetVersionError(
            f"Declared target_schema {target_schema!r} does not match "
            f"handoff schema {schema!r}."
        )


def _check_derived_acceptance(handoff: dict[str, Any]) -> None:
    """Check 5: ``accepted_for_cl2.value`` must be ``True`` with all sub-checks
    passed and no blocking reasons."""
    afc = handoff.get("accepted_for_cl2")
    if not isinstance(afc, dict):
        raise MalformedArtifactError(
            "amended_handoff: missing or non-object 'accepted_for_cl2'"
        )
    if afc.get("value") is not True:
        raise DerivedAcceptanceFalseError(
            "accepted_for_cl2.value is not True"
        )
    checks = afc.get("checks", {})
    if not isinstance(checks, dict):
        raise MalformedArtifactError(
            "amended_handoff: 'accepted_for_cl2.checks' is not an object"
        )
    failed_checks = [
        name
        for name, chk in checks.items()
        if not (isinstance(chk, dict) and chk.get("passed") is True)
    ]
    if failed_checks:
        raise DerivedAcceptanceFalseError(
            "accepted_for_cl2 sub-checks not all passed: "
            + ", ".join(sorted(failed_checks))
        )
    blocking = afc.get("blocking_reasons", [])
    if blocking:
        raise DerivedAcceptanceFalseError(
            "accepted_for_cl2.blocking_reasons is non-empty: "
            + json.dumps(blocking)
        )


def _check_blocker_free_gates(handoff: dict[str, Any]) -> None:
    """Check 6: independently scan ``open_gates`` for blocking statuses.

    This does not trust the derived ``accepted_for_cl2`` value — it verifies
    the raw gate inventory so that a handoff with ``value=True`` but real
    blockers is still rejected.
    """
    gates = handoff.get("open_gates")
    if gates is None:
        raise MalformedArtifactError(
            "amended_handoff: missing 'open_gates' section"
        )
    if not isinstance(gates, dict):
        raise MalformedArtifactError(
            "amended_handoff: 'open_gates' is not an object"
        )
    blockers: list[str] = []
    for name, gate in gates.items():
        if not isinstance(gate, dict):
            blockers.append(f"{name}: non-object gate entry")
            continue
        status = str(gate.get("status", "")).upper()
        if status in _BLOCKING_GATE_STATUSES:
            blockers.append(f"{name}: status={status!r}")
        elif status not in _OK_GATE_STATUSES:
            # Fail-closed: unknown statuses are treated as blocking.
            blockers.append(f"{name}: status={status!r} (unrecognized)")
        if gate.get("validation_passed") is False:
            blockers.append(f"{name}: validation_passed=false")
    if blockers:
        raise BlockerBearingError(
            "open_gates carry blocking statuses: " + "; ".join(blockers)
        )


def _find_trusted_entry(
    trust_doc: dict[str, Any], fingerprint: str
) -> ReviewerTrustEntry:
    """Check 7 (partial): locate the declared fingerprint in the trust binding."""
    reviewers = trust_doc.get("trusted_reviewers")
    if not isinstance(reviewers, list):
        raise MalformedArtifactError(
            "reviewer_trust: missing or non-list 'trusted_reviewers'"
        )
    for entry in reviewers:
        if not isinstance(entry, dict):
            continue
        if entry.get("fingerprint") == fingerprint:
            return ReviewerTrustEntry(
                fingerprint=str(entry.get("fingerprint", "")),
                public_key=str(entry.get("public_key", "")),
                scope=tuple(entry.get("scope", [])),
                expires_at=str(entry.get("expires_at", "")),
            )
    raise ReviewerNotTrustedError(
        f"Reviewer fingerprint {fingerprint!r} is not present in the trust "
        f"binding ({len(reviewers)} trusted reviewers)."
    )


def _check_review_scope(
    trust_entry: ReviewerTrustEntry, receipt: dict[str, Any]
) -> None:
    """Check 8: both the trust entry and receipt must scope cl2_admission."""
    if REQUIRED_SCOPE not in trust_entry.scope:
        raise ReviewScopeMismatchError(
            f"Trust entry for {trust_entry.fingerprint!r} scope "
            f"{list(trust_entry.scope)} does not include {REQUIRED_SCOPE!r}."
        )
    receipt_scope = receipt.get("scope", [])
    if not isinstance(receipt_scope, list):
        receipt_scope = []
    if REQUIRED_SCOPE not in receipt_scope:
        raise ReviewScopeMismatchError(
            f"Review receipt scope {receipt_scope} does not include "
            f"{REQUIRED_SCOPE!r}."
        )


def _check_non_expiry(
    trust_entry: ReviewerTrustEntry,
    receipt: dict[str, Any],
    now: datetime,
) -> None:
    """Check 9: neither the trust entry nor the receipt may have expired."""
    trust_expiry = _parse_iso(trust_entry.expires_at)
    if trust_expiry is not None and trust_expiry <= now:
        raise ReviewExpiredError(
            f"Trust entry for {trust_entry.fingerprint!r} expired at "
            f"{trust_entry.expires_at}."
        )
    receipt_expiry_raw = str(receipt.get("expires_at", ""))
    receipt_expiry = _parse_iso(receipt_expiry_raw)
    if receipt_expiry is not None and receipt_expiry <= now:
        raise ReviewExpiredError(
            f"Review receipt expired at {receipt_expiry_raw}."
        )


def verify_detached_signature(
    public_key_b64: str,
    message_bytes: bytes,
    signature_b64: str,
    verifier: Optional[SignatureVerifier] = None,
) -> bool:
    """Verify an Ed25519 detached signature.

    Returns ``True`` only when the signature is present, well-formed, and
    cryptographically valid. This helper **never creates** signatures — it
    only verifies.
    """
    if not public_key_b64 or not signature_b64:
        return False
    resolve = verifier or _default_ed25519_verifier
    try:
        public_key_raw = base64.b64decode(public_key_b64, validate=True)
        signature_raw = base64.b64decode(signature_b64, validate=True)
    except (ValueError, TypeError):
        return False
    if len(signature_raw) != 64:
        return False
    return resolve(public_key_raw, message_bytes, signature_raw)


def _check_detached_signature(
    trust_entry: ReviewerTrustEntry,
    receipt: dict[str, Any],
    verifier: Optional[SignatureVerifier],
) -> None:
    """Check 10: the receipt's detached signature must verify against the
    trusted reviewer's public key."""
    signature_b64 = str(receipt.get("signature", ""))
    message_bytes = _canonical_receipt_message(receipt)
    ok = verify_detached_signature(
        trust_entry.public_key, message_bytes, signature_b64, verifier
    )
    if not ok:
        raise DetachedSignatureInvalidError(
            "Review receipt detached signature is absent or failed "
            "verification."
        )


def _check_binding_cross_references(
    receipt: dict[str, Any],
    handoff: dict[str, Any],
    handoff_disk_sha: str,
    policy_disk_sha: str,
    admission: CL2AdmissionInput,
) -> None:
    """Check 11: the receipt's cross-references must match the recomputed disk
    hashes and the declared amendment checksum."""
    reviewed = str(receipt.get("reviewed_artifact_sha256", ""))
    if reviewed != handoff_disk_sha:
        raise BindingCrossReferenceError(
            "Receipt reviewed_artifact_sha256 does not match the recomputed "
            f"handoff hash ({reviewed[:16]}… vs {handoff_disk_sha[:16]}…)."
        )
    policy_ref = str(receipt.get("policy_bundle_sha256", ""))
    if policy_ref != policy_disk_sha:
        raise BindingCrossReferenceError(
            "Receipt policy_bundle_sha256 does not match the recomputed "
            f"policy bundle hash ({policy_ref[:16]}… vs {policy_disk_sha[:16]}…)."
        )
    receipt_fp = str(receipt.get("reviewer_fingerprint", ""))
    if receipt_fp != admission.reviewer_fingerprint:
        raise BindingCrossReferenceError(
            "Receipt reviewer_fingerprint does not match the declared "
            f"fingerprint ({receipt_fp!r} vs {admission.reviewer_fingerprint!r})."
        )
    receipt_amendment = str(receipt.get("amendment_checksum", ""))
    if receipt_amendment != admission.amendment_checksum:
        raise BindingCrossReferenceError(
            "Receipt amendment_checksum does not match the declared checksum."
        )
    handoff_amendment = str(handoff.get("amendment_checksum", ""))
    if handoff_amendment != admission.amendment_checksum:
        raise BindingCrossReferenceError(
            "Handoff amendment_checksum does not match the declared checksum."
        )


def _check_policy_revisions(
    policy_bundle: dict[str, Any], declared: PolicyRevisions
) -> None:
    """Check 12: the six policy revision hashes in the bundle must match."""
    declared_dict = declared.to_dict()
    mismatches: list[str] = []
    for key, expected in declared_dict.items():
        actual = str(policy_bundle.get(key, ""))
        if actual != expected:
            mismatches.append(
                f"{key}: declared {expected[:16]}… vs bundle {actual[:16]}…"
            )
    if mismatches:
        raise PolicyRevisionDriftError(
            "Policy revision drift: " + "; ".join(mismatches)
        )


def _compute_binding_hash(
    handoff_disk_sha: str,
    policy_disk_sha: str,
    receipt_disk_sha: str,
    trust_disk_sha: str,
    admission: CL2AdmissionInput,
) -> str:
    """Compute the deterministic ``binding_hash`` authorization token."""
    payload = {
        "v": 1,
        "amended_handoff_sha256": handoff_disk_sha,
        "policy_bundle_sha256": policy_disk_sha,
        "review_receipt_sha256": receipt_disk_sha,
        "reviewer_trust_sha256": trust_disk_sha,
        "reviewer_fingerprint": admission.reviewer_fingerprint,
        "target_schema": admission.target_schema,
        "amendment_checksum": admission.amendment_checksum,
        "policy_revisions": admission.policy_revisions.to_dict(),
    }
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ────────────────────────────────────────────────────────────────────
# Public entry point
# ────────────────────────────────────────────────────────────────────


def verify_cl2_admission(
    admission: CL2AdmissionInput,
    *,
    now: Optional[datetime] = None,
    signature_verifier: Optional[SignatureVerifier] = None,
) -> AcceptedCL1Binding:
    """Verify the CL2 admission bundle and return an immutable binding.

    This is the sole read-only entry point. It performs every check in the
    documented order and raises the first applicable :class:`CL2AdmissionError`
    subclass. On success it returns an :class:`AcceptedCL1Binding` whose
    ``binding_hash`` is the deterministic authorization token.

    Args:
        admission: The closed admission input with declared paths and hashes.
        now: Optional override for the current UTC time (expiry check).
        signature_verifier: Optional injected verifier for testing the
            signature path. Defaults to the Ed25519 verifier from
            ``cryptography``.

    Raises:
        CL2AdmissionError: a typed subclass describing the first failing check.
    """
    current = now or datetime.now(timezone.utc)

    # 1 — prerequisite presence
    _check_prerequisite_presence(admission)

    # 2 — hash freshness (recompute from disk)
    handoff_disk_sha = _check_hash_freshness(
        "amended_handoff",
        admission.amended_handoff_path,
        admission.amended_handoff_sha256,
    )
    policy_disk_sha = _check_hash_freshness(
        "policy_bundle",
        admission.policy_bundle_path,
        admission.policy_bundle_sha256,
    )
    receipt_disk_sha = _check_hash_freshness(
        "review_receipt",
        admission.review_receipt_path,
        admission.review_receipt_sha256,
    )
    trust_disk_sha = _check_hash_freshness(
        "reviewer_trust",
        admission.reviewer_trust_path,
        admission.reviewer_trust_sha256,
    )

    # 3 — JSON parse
    handoff = _load_json(admission.amended_handoff_path, "amended_handoff")
    policy_bundle = _load_json(admission.policy_bundle_path, "policy_bundle")
    receipt = _load_json(admission.review_receipt_path, "review_receipt")
    trust_doc = _load_json(admission.reviewer_trust_path, "reviewer_trust")

    # 4 — target version
    _check_target_version(handoff, admission.target_schema)

    # 5 — derived acceptance
    _check_derived_acceptance(handoff)

    # 6 — blocker-free gates (independent of derived value)
    _check_blocker_free_gates(handoff)

    # 7 — reviewer trust
    trust_entry = _find_trusted_entry(trust_doc, admission.reviewer_fingerprint)

    # 8 — review scope
    _check_review_scope(trust_entry, receipt)

    # 9 — non-expiry
    _check_non_expiry(trust_entry, receipt, current)

    # 10 — detached signature
    _check_detached_signature(trust_entry, receipt, signature_verifier)

    # 11 — three-way binding cross-references
    _check_binding_cross_references(
        receipt, handoff, handoff_disk_sha, policy_disk_sha, admission
    )

    # 12 — policy revisions
    _check_policy_revisions(policy_bundle, admission.policy_revisions)

    # Success — return immutable binding
    binding_hash = _compute_binding_hash(
        handoff_disk_sha,
        policy_disk_sha,
        receipt_disk_sha,
        trust_disk_sha,
        admission,
    )
    return AcceptedCL1Binding(
        binding_hash=binding_hash,
        amended_handoff_sha256=handoff_disk_sha,
        policy_bundle_sha256=policy_disk_sha,
        review_receipt_sha256=receipt_disk_sha,
        reviewer_trust_sha256=trust_disk_sha,
        reviewer_fingerprint=admission.reviewer_fingerprint,
        target_schema=admission.target_schema,
        amendment_checksum=admission.amendment_checksum,
        policy_revisions=admission.policy_revisions,
    )
