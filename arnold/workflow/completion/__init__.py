"""Completion — non-authoritative shadow-only completion kernel (experimental).

.. caution::
   This package is **experimental and non-authoritative**.  It provides shadow
   infrastructure only: no live acceptance cutover, no completion authority,
   and no effect capability.  All generated specs, bindings, and verdicts have
   **zero authority** and **cannot satisfy completion**.  See S2R GO-0 for the
   future live-enablement gate.

   The hashing functions in :mod:`.hashing` are a deliberate reimplementation
   of the algorithm in ``acceptance_transaction.py`` (canonical JSON + SHA-256)
   with an identical output format (``sha256:`` prefix).  The duplication is
   required by the neutral-package import boundary — the completion package
   must not import from ``arnold_pipelines.megaplan`` or any product module.
   Extraction into a shared library is tracked as a C2 / S2R candidate.
"""

from __future__ import annotations

from arnold.workflow.completion.binding import (
    CompletionBinding,
    SubjectInstanceId,
    SubjectInstanceId,
    bind,
    compute_binding_hash,
)
from arnold.workflow.completion.durability import (
    DURABLE_REQUIRED_INDICATORS,
    LintViolation,
    classify_subject,
    is_pure_helper,
    run_omission_lint,
)
from arnold.workflow.completion.hashing import (
    canonical_json,
    content_addressed_store_path,
    hash_canonical,
)
from arnold.workflow.completion.ledger import (
    DivergenceEntry,
    DivergenceLedger,
    append_entry,
    compute_entry_hash,
    narrow_entry,
    validate_ledger_chain,
)
from arnold.workflow.completion.outcomes import (
    CandidateOutcome,
    SUBJECT_KIND_OUTCOME_CROSSWALK,
    is_laundering,
    is_terminal,
    outcome_requires_acceptance,
    validate_supersession,
)
from arnold.workflow.completion.shadow import (
    ShadowEvaluation,
    ShadowVerdict,
    evaluate_shadow,
    generate_shadow_bindings,
    generate_shadow_specs,
)
from arnold.workflow.completion.source_declaration import (
    SourceDeclaration,
    SubjectDeclaration,
)
from arnold.workflow.completion.spec import (
    CompletionSpec,
    Obligation,
    ProofMode,
    SubjectKind,
    compute_spec_hash,
    make_completion_spec,
    obligation_identity,
    tombstone_spec,
)
from arnold.workflow.completion.terminals import (
    NamedExit,
    compute_exit_hash,
    superseded_by_named_exit,
    validate_named_exit_chain,
)

__all__ = [
    "canonical_json",
    "content_addressed_store_path",
    "hash_canonical",
    "SourceDeclaration",
    "SubjectDeclaration",
    "CompletionSpec",
    "Obligation",
    "ProofMode",
    "SubjectKind",
    "compute_spec_hash",
    "make_completion_spec",
    "obligation_identity",
    "tombstone_spec",
    # binding
    "CompletionBinding",
    "SubjectInstanceId",
    "SubjectInstanceId",
    "bind",
    "compute_binding_hash",
    # outcomes
    "CandidateOutcome",
    "is_terminal",
    "outcome_requires_acceptance",
    "validate_supersession",
    "is_laundering",
    "SUBJECT_KIND_OUTCOME_CROSSWALK",
    # terminals
    "NamedExit",
    "compute_exit_hash",
    "superseded_by_named_exit",
    "validate_named_exit_chain",
    # ledger
    "DivergenceEntry",
    "DivergenceLedger",
    "append_entry",
    "compute_entry_hash",
    "narrow_entry",
    "validate_ledger_chain",
    # shadow
    "ShadowVerdict",
    "ShadowEvaluation",
    "evaluate_shadow",
    "generate_shadow_specs",
    "generate_shadow_bindings",
    # durability
    "classify_subject",
    "is_pure_helper",
    "DURABLE_REQUIRED_INDICATORS",
    "LintViolation",
    "run_omission_lint",
]
