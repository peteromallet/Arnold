"""Content-addressed cutover receipt (CL5 Step 16).

The cutover receipt is the **authority-bearing summary** of the entire cutover:
it binds every revision/hash (the immutable :class:`CutoverConfig`, including
the exact North Star runtime), the verified backup identity, the import counts,
the smoke results, the operator/reviewer approvals, the timestamp, the
retirement proof, and the resulting activation state into one canonical,
content-addressed JSON object.

Two invariants are enforced fail-closed (SC28):

1. **``bridge_mode`` is forced ``False``.** The post-cutover target is the
   single canonical critique runtime; there is no bridge path. The receipt
   hard-codes ``bridge_mode = False`` regardless of any input — a receipt can
   never attest a bridged cutover.
2. **``single_target_architecture_active`` is ``True`` ONLY after a verified
   retirement proof.** The receipt does not take activation on faith: it
   re-verifies the supplied retirement proof's schema, ``content_hash``, and
   North Star binding against the config, and only then sets
   ``single_target_architecture_active = True``. A tampered proof, a wrong
   schema, or a binding mismatch raises :class:`ReceiptError` so no false
   completion evidence is ever emitted.

The receipt's own ``content_hash`` is a ``sha256`` over the **complete canonical
JSON body** (every field, ``content_hash`` excluded because it cannot cover
itself), so any post-hoc field omission or mutation — including a change to
``bridge_mode`` or ``single_target_architecture_active`` — is independently
detectable.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

from arnold.critique_ledger.cutover.config import (
    CutoverConfig,
    NORTH_STAR_RUNTIME_HASH,
    validate_config,
)
from arnold.critique_ledger.cutover.retire import (
    ACTIVE_TARGET_MODULE,
    RETIREMENT_PROOF_SCHEMA,
)

#: Receipt schema identifier.
CUTOVER_RECEIPT_SCHEMA: str = "cl5.cutover-receipt.v1"

#: Canonical hash algorithm (content-addressing), matching the backup/proof.
HASH_ALGORITHM: str = "sha256"


class ReceiptError(RuntimeError):
    """Raised when a cutover receipt cannot be bound or a retirement proof
    cannot be verified.

    A tampered retirement proof (bad ``content_hash``), a wrong proof schema,
    a proof/config North Star binding mismatch, or an invalid cutover config
    all fail closed rather than emitting false completion evidence.
    """


@dataclass(frozen=True)
class ReceiptActivation:
    """Outcome of evaluating the receipt's activation conditions.

    ``single_target_architecture_active`` is ``True`` only when the retirement
    proof verifies against the config. ``bridge_mode`` is always ``False``.
    """

    single_target_architecture_active: bool
    bridge_mode: bool
    retirement_verified: bool


# ── retirement proof verification ────────────────────────────────────────────


def _canonical_content_hash(body: dict[str, Any]) -> str:
    """Return ``sha256:<hex>`` over the canonical JSON of *body*.

    The body MUST already exclude its own ``content_hash`` field. Uses
    ``sort_keys=True`` + ``ensure_ascii=False`` so the hash is reproducible by
    any verifier that re-serializes the same fields.
    """
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_retirement_proof(
    proof: dict[str, Any],
    config: CutoverConfig,
) -> bool:
    """Verify a retirement proof binds *config* and records activation.

    Fail-closed checks (raise :class:`ReceiptError`):

    * the proof schema is :data:`RETIREMENT_PROOF_SCHEMA`;
    * the proof ``content_hash`` matches its canonical body (no tampering);
    * the proof's ``source_revision`` equals ``config.source_revision``;
    * the proof's ``north_star_runtime_binding`` equals
      ``config.north_star_runtime_binding``.

    Returns ``True`` only when the proof additionally carries
    ``single_target_architecture_active is True``; otherwise ``False`` (the
    proof is well-formed and bound but does not activate — an honest "pending"
    state, not false evidence).
    """
    if not isinstance(proof, dict):
        raise ReceiptError(
            f"Retirement proof must be a dict; got {type(proof).__name__}."
        )
    if proof.get("schema") != RETIREMENT_PROOF_SCHEMA:
        raise ReceiptError(
            f"Retirement proof schema {proof.get('schema')!r} is not "
            f"{RETIREMENT_PROOF_SCHEMA!r}."
        )

    stored = proof.get("content_hash")
    if not isinstance(stored, str) or not stored.startswith("sha256:"):
        raise ReceiptError(
            "Retirement proof is missing a valid content_hash; it may have "
            "been truncated or forged."
        )
    body = {k: v for k, v in proof.items() if k != "content_hash"}
    if _canonical_content_hash(body) != stored:
        raise ReceiptError(
            "Retirement proof content_hash does not match its canonical body; "
            "the proof may have been tampered with after generation."
        )

    proof_cfg = proof.get("cutover_config", {})
    if proof_cfg.get("source_revision") != config.source_revision:
        raise ReceiptError(
            "Retirement proof source_revision does not match the cutover "
            "config; the proof binds a different runtime."
        )
    if proof_cfg.get("north_star_runtime_binding") != config.north_star_runtime_binding:
        raise ReceiptError(
            "Retirement proof north_star_runtime_binding does not match the "
            "cutover config; the proof binds a different North Star runtime."
        )

    return proof.get("single_target_architecture_active") is True


# ── receipt construction ─────────────────────────────────────────────────────


def evaluate_activation(
    config: CutoverConfig,
    retirement_proof: dict[str, Any],
) -> ReceiptActivation:
    """Evaluate the receipt's activation conditions.

    ``bridge_mode`` is unconditionally ``False``; ``single_target_architecture_active``
    mirrors :func:`verify_retirement_proof`. The config is validated first so an
    invalid config fails closed before the proof is inspected.
    """
    validate_config(config)
    retirement_verified = verify_retirement_proof(retirement_proof, config)
    return ReceiptActivation(
        single_target_architecture_active=retirement_verified,
        bridge_mode=False,
        retirement_verified=retirement_verified,
    )


def build_receipt_body(
    *,
    config: CutoverConfig,
    backup_manifest: dict[str, Any],
    retirement_proof: dict[str, Any],
    activation: ReceiptActivation,
    import_counts: dict[str, Any] | None,
    smoke_results: dict[str, Any] | None,
    operator: dict[str, Any] | None,
    reviewer: dict[str, Any] | None,
    now: float | None,
) -> dict[str, Any]:
    """Assemble the canonical receipt body (without its ``content_hash``).

    Every prescribed binding is populated: the full immutable config (source,
    target, schema, WBC, oracle, corpus, operator-approval, backup identity,
    build revision, and the exact North Star runtime), the verified backup
    identity, import counts, smoke results, operator/reviewer, the retirement
    proof binding, the forced ``bridge_mode = False``, and the conditional
    ``single_target_architecture_active``.
    """
    timestamp = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now if now is not None else time.time())
    )

    body: dict[str, Any] = {
        "schema": CUTOVER_RECEIPT_SCHEMA,
        "generated_at": timestamp,
        "hash_algorithm": HASH_ALGORITHM,
        "cutover_config": {
            "source_revision": config.source_revision,
            "target_revision": config.target_revision,
            "schema_version": config.schema_version,
            "wbc_contract_hash": config.wbc_contract_hash,
            "m6_oracle_hash": config.m6_oracle_hash,
            "corpus_fixture_hash": config.corpus_fixture_hash,
            "operator_approval_revision": config.operator_approval_revision,
            "backup_identity": config.backup_identity,
            "build_revision": config.build_revision,
            "north_star_runtime_binding": config.north_star_runtime_binding,
        },
        "north_star_runtime_binding": config.north_star_runtime_binding,
        "backup": {
            "manifest_schema": backup_manifest.get("schema"),
            "bundle_sha256": backup_manifest.get("bundle_sha256"),
            "manifest_content_hash": backup_manifest.get("content_hash"),
            "file_count": backup_manifest.get("file_count"),
        },
        "import_counts": dict(import_counts) if import_counts else {},
        "smoke_results": dict(smoke_results) if smoke_results else {},
        "operator": dict(operator) if operator else {},
        "reviewer": dict(reviewer) if reviewer else {},
        # bridge_mode is FORCED False: the post-cutover target is the single
        # canonical critique runtime; there is no bridge path. The receipt can
        # never attest a bridged cutover.
        "bridge_mode": False,
        "retirement_proof_binding": {
            "schema": retirement_proof.get("schema"),
            "content_hash": retirement_proof.get("content_hash"),
            "active_target": retirement_proof.get("active_target"),
            "proof_single_target_architecture_active": retirement_proof.get(
                "single_target_architecture_active"
            ),
        },
        # single_target_architecture_active is True ONLY after a verified
        # retirement proof (see evaluate_activation / verify_retirement_proof).
        "single_target_architecture_active": activation.single_target_architecture_active,
        "retirement_verified": activation.retirement_verified,
    }
    return body


def generate_cutover_receipt(
    config: CutoverConfig,
    *,
    backup_manifest: dict[str, Any],
    retirement_proof: dict[str, Any],
    import_counts: dict[str, Any] | None = None,
    smoke_results: dict[str, Any] | None = None,
    operator: dict[str, Any] | None = None,
    reviewer: dict[str, Any] | None = None,
    now: float | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Generate the canonical, content-addressed cutover receipt.

    Binds the immutable config (incl. the exact North Star runtime), the
    verified backup identity, import counts, smoke results, operator/reviewer,
    the retirement proof, forces ``bridge_mode = False``, and sets
    ``single_target_architecture_active`` only after the retirement proof
    verifies against the config. The receipt's ``content_hash`` is a ``sha256``
    over the complete canonical JSON body.

    Args:
        config: The immutable cutover config; validated (North Star binding)
            before any field is bound.
        backup_manifest: The verified backup manifest (from
            :func:`~arnold.critique_ledger.cutover.backup.verify_tarball` or
            :func:`~arnold.critique_ledger.cutover.backup.create_cutover_backup`).
        retirement_proof: The retirement proof (from
            :func:`~arnold.critique_ledger.cutover.retire.generate_retirement_proof`).
        import_counts: Optional import counts (occurrences/reconciliations/etc.).
        smoke_results: Optional smoke-results evidence.
        operator: Optional operator approval record.
        reviewer: Optional reviewer approval record.
        now: Override the wall-clock timestamp (deterministic testing).
        output_path: When given, write the canonical receipt JSON there.

    Returns:
        The content-addressed receipt dict.

    Raises:
        ReceiptError: If the config is invalid or the retirement proof is
            tampered, has the wrong schema, or does not bind the config. In all
            such cases no receipt is emitted, so no false completion evidence
            is created.
    """
    activation = evaluate_activation(config, retirement_proof)

    body = build_receipt_body(
        config=config,
        backup_manifest=backup_manifest,
        retirement_proof=retirement_proof,
        activation=activation,
        import_counts=import_counts,
        smoke_results=smoke_results,
        operator=operator,
        reviewer=reviewer,
        now=now,
    )

    receipt = dict(body)
    receipt["content_hash"] = _canonical_content_hash(body)
    return receipt


def write_receipt(receipt: dict[str, Any], output_path: str) -> None:
    """Write *receipt* to *output_path* as canonical (sorted-key) JSON."""
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, sort_keys=True, ensure_ascii=False, indent=2)


def verify_receipt_content_hash(receipt: dict[str, Any]) -> bool:
    """Return whether the receipt's ``content_hash`` matches its canonical body.

    Recomputes the ``sha256`` over the complete canonical JSON (excluding
    ``content_hash`` itself) and compares. Any post-hoc mutation of a bound
    field — including ``bridge_mode`` or ``single_target_architecture_active`` —
    makes this return ``False``.
    """
    stored = receipt.get("content_hash")
    if not isinstance(stored, str) or not stored.startswith("sha256:"):
        return False
    body = {k: v for k, v in receipt.items() if k != "content_hash"}
    return _canonical_content_hash(body) == stored


def generate_cutover_receipt_to_file(
    config: CutoverConfig,
    output_path: str,
    *,
    backup_manifest: dict[str, Any],
    retirement_proof: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Generate the receipt and write it to *output_path*; returns the receipt."""
    receipt = generate_cutover_receipt(
        config,
        backup_manifest=backup_manifest,
        retirement_proof=retirement_proof,
        **kwargs,
    )
    write_receipt(receipt, output_path)
    return receipt


__all__ = [
    "ACTIVE_TARGET_MODULE",
    "CUTOVER_RECEIPT_SCHEMA",
    "HASH_ALGORITHM",
    "ReceiptActivation",
    "ReceiptError",
    "RETIREMENT_PROOF_SCHEMA",
    "build_receipt_body",
    "evaluate_activation",
    "generate_cutover_receipt",
    "generate_cutover_receipt_to_file",
    "verify_receipt_content_hash",
    "verify_retirement_proof",
    "write_receipt",
]
