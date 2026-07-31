"""Tests for M11 Step 23: review routing bound to runtime provenance.

Proves:
* ``_attach_next_step_runtime`` exists and is callable in the loaded runtime.
* Generic runnable REVIEW IDs are rejected (converted to ``r:`` markers).
* Review routing outcomes carry runtime provenance receipts.
"""

from __future__ import annotations

import pytest

from arnold_pipelines.megaplan.handlers.review import (
    _bind_review_routing_provenance,
    _is_synthetic_review_task_id,
    _reject_runnable_review_ids,
    _verify_attach_next_step_runtime,
)


# ── Runtime provenance: _attach_next_step_runtime exists ──────────────────


def test_attach_next_step_runtime_exists_in_loaded_runtime():
    """T17: _attach_next_step_runtime is resolvable and callable.

    The review routing path calls _bind_review_routing_provenance, which
    internally calls _verify_attach_next_step_runtime.  This test proves
    the function is importable, callable, and bound to the expected module
    (arnold_pipelines.megaplan.handlers.shared).
    """
    proof = _verify_attach_next_step_runtime()

    assert proof["function"] == "_attach_next_step_runtime"
    assert proof["callable"] is True
    assert proof["present"] is True
    assert "arnold_pipelines.megaplan.handlers.shared" in proof["module"]
    assert proof["qualname"] == "_attach_next_step_runtime"


# ── Synthetic REVIEW task ID rejection ───────────────────────────────────


def test_is_synthetic_review_task_id_detects_review_prefix():
    """T17: synthetic REVIEW-{check_id} task IDs are detected.

    These are review-scoped concern markers created when review checks omit
    ``concerned_task_ids``.  They must not be routed to execute as generic
    runnable finalize task IDs.
    """
    assert _is_synthetic_review_task_id("REVIEW-001") is True
    assert _is_synthetic_review_task_id("REVIEW-coverage-missing") is True
    assert _is_synthetic_review_task_id("REVIEW-SC5") is True

    # Real task IDs are not synthetic
    assert _is_synthetic_review_task_id("T1") is False
    assert _is_synthetic_review_task_id("T17") is False
    assert _is_synthetic_review_task_id("REVIEW") is False  # no hyphen-suffix
    assert _is_synthetic_review_task_id("review-001") is False  # lowercase

    # Non-strings are never synthetic
    assert _is_synthetic_review_task_id(42) is False  # type: ignore[arg-type]
    assert _is_synthetic_review_task_id(None) is False  # type: ignore[arg-type]


def test_reject_runnable_review_ids_replaces_with_r_prefix():
    """T17: synthetic REVIEW IDs are replaced with ``r:`` markers.

    Downstream routing must never see a bare ``REVIEW-...`` task ID because
    it could be misinterpreted as a runnable finalize target.  The sanitized
    list replaces every synthetic ID with ``r:REVIEW-...``.
    """
    # All synthetic → all replaced
    result = _reject_runnable_review_ids(
        ["REVIEW-001", "REVIEW-002"]
    )
    assert result == ["r:REVIEW-001", "r:REVIEW-002"]

    # Mixed synthetic and real → only synthetic replaced
    result = _reject_runnable_review_ids(
        ["T1", "REVIEW-SC5", "T17", "REVIEW-coverage-missing"]
    )
    assert result == ["T1", "r:REVIEW-SC5", "T17", "r:REVIEW-coverage-missing"]

    # No synthetic → unchanged
    result = _reject_runnable_review_ids(["T1", "T17", "T42"])
    assert result == ["T1", "T17", "T42"]

    # Empty list
    assert _reject_runnable_review_ids([]) == []

    # Lowercase or hyphen-less REVIEW not treated as synthetic
    result = _reject_runnable_review_ids(["review-001", "REVIEW", "T1"])
    assert result == ["review-001", "REVIEW", "T1"]


# ── Review routing provenance binding ────────────────────────────────────


def test_bind_review_routing_provenance_attaches_receipt():
    """T17: _bind_review_routing_provenance attaches a provenance receipt
    with the expected schema marker and _attach_next_step_runtime proof.

    The receipt proves the routing decision was made under a known runtime.
    When verify_runtime=True (the default), the proof includes the function
    resolution status.
    """
    response: dict = {}
    _bind_review_routing_provenance(response, verify_runtime=True)

    prov = response.get("review_routing_provenance")
    assert prov is not None, "review_routing_provenance key missing"
    assert prov["schema"] == "arnold.megaplan.review_routing_provenance.v1"

    rt_proof = prov.get("_attach_next_step_runtime")
    assert rt_proof is not None, "_attach_next_step_runtime proof missing"
    assert rt_proof["function"] == "_attach_next_step_runtime"
    assert rt_proof["callable"] is True
    assert rt_proof["present"] is True


def test_bind_review_routing_provenance_handles_missing_runtime():
    """T17: when verify_runtime=False, the provenance receipt is still
    attached but without the _attach_next_step_runtime proof.

    This path is used when the caller already knows the runtime is not
    available (e.g. dry-run or pre-init contexts).
    """
    response: dict = {}
    _bind_review_routing_provenance(response, verify_runtime=False)

    prov = response.get("review_routing_provenance")
    assert prov is not None
    assert prov["schema"] == "arnold.megaplan.review_routing_provenance.v1"
    # No _attach_next_step_runtime proof when verify_runtime=False
    assert "_attach_next_step_runtime" not in prov


def test_bind_review_routing_provenance_does_not_mutate_other_keys():
    """T17: _bind_review_routing_provenance only adds its own key and
    leaves pre-existing response keys untouched.
    """
    response: dict = {
        "next_step": "finalize",
        "state": "reviewed",
        "other_field": 42,
    }
    _bind_review_routing_provenance(response)

    assert response["next_step"] == "finalize"
    assert response["state"] == "reviewed"
    assert response["other_field"] == 42
    assert "review_routing_provenance" in response


# ── End-to-end: synthetic REVIEW IDs cannot become runnable ──────────────


def test_synthetic_review_ids_never_reach_execute_as_runnable():
    """T17: a batch of task IDs containing synthetic REVIEW- entries is
    sanitized so no downstream execute routing can mistake them for
    runnable finalize task IDs.

    This is the integration-level proof that the review routing contract
    prevents generic runnable REVIEW IDs from reaching execute.
    """
    # Simulate a review outcome that produced synthetic concern markers
    raw_task_ids = [
        "T1",
        "T5",
        "REVIEW-SC5",
        "T6",
        "REVIEW-coverage-missing",
        "T17",
        "REVIEW-001",
    ]

    sanitized = _reject_runnable_review_ids(raw_task_ids)

    # No bare REVIEW- prefix survives
    for tid in sanitized:
        assert not tid.startswith("REVIEW-"), (
            f"Bare REVIEW- prefix survived sanitization: {tid!r}"
        )

    # Real task IDs are unchanged
    assert "T1" in sanitized
    assert "T5" in sanitized
    assert "T6" in sanitized
    assert "T17" in sanitized

    # Every original synthetic ID has a corresponding r: entry
    assert "r:REVIEW-SC5" in sanitized
    assert "r:REVIEW-coverage-missing" in sanitized
    assert "r:REVIEW-001" in sanitized

    # Length preserved (no dropping, no duplication)
    assert len(sanitized) == len(raw_task_ids)


# ── Step 24: Review prompts do not emit generic runnable REVIEW IDs ──────


def test_review_prompts_do_not_emit_generic_runnable_review_id():
    """T18 / Step 24: the review.md and review_rework.md prompt contracts
    carry explicit review outcome markers and a strict schema hash so that
    generated output cannot emit runnable generic REVIEW IDs.

    This test proves:
    * review.md exists, contains REVIEW_SCHEMA_HASH, forbids REVIEW- patterns
    * review_rework.md exists, contains REVIEW_REWORK_SCHEMA_HASH, forbids REVIEW- patterns
    * Both files explicitly forbid bare ``REVIEW-{anything}`` task IDs
    * Both files require typed target routing (``target.kind``)
    * Schema hashes are non-trivial (at least 16 hex chars)
    """
    import re
    from pathlib import Path

    prompts_dir = Path("arnold_pipelines/megaplan/prompts")

    # ── review.md ─────────────────────────────────────────────────────────
    review_path = prompts_dir / "review.md"
    assert review_path.exists(), f"{review_path} does not exist"
    review_text = review_path.read_text(encoding="utf-8")

    # Schema hash is present and non-trivial
    hash_match = re.search(
        r"REVIEW_SCHEMA_HASH.*?(sha256:[a-f0-9]{16,})",
        review_text,
    )
    assert hash_match is not None, "review.md must contain REVIEW_SCHEMA_HASH"
    schema_hash = hash_match.group(1)
    assert len(schema_hash) > 16, f"Schema hash too short: {schema_hash}"

    # Explicitly forbids REVIEW- task IDs
    assert "REVIEW-{" in review_text or "REVIEW-{anything}" in review_text, (
        "review.md must explicitly forbid REVIEW- patterns in task_id fields"
    )
    assert "REVIEW-001" in review_text, (
        "review.md must include a concrete example of forbidden REVIEW-001 ID"
    )
    assert "FORBIDDEN" in review_text.upper(), (
        "review.md must have explicit FORBIDDEN section for REVIEW IDs"
    )

    # Requires typed target routing
    assert 'target' in review_text, "review.md must require target field"
    assert '"kind": "task"' in review_text, "review.md must show task target example"

    # Review outcome markers
    assert "review_verdict" in review_text, "review.md must define review_verdict"
    assert "review_completion_status" in review_text, (
        "review.md must define review_completion_status"
    )
    assert "deterministic_check" in review_text, (
        "review.md must require deterministic_check for blocking rework"
    )

    # ── review_rework.md ──────────────────────────────────────────────────
    rework_path = prompts_dir / "review_rework.md"
    assert rework_path.exists(), f"{rework_path} does not exist"
    rework_text = rework_path.read_text(encoding="utf-8")

    # Schema hash is present and non-trivial
    rework_hash_match = re.search(
        r"REVIEW_REWORK_SCHEMA_HASH.*?(sha256:[a-f0-9]{16,})",
        rework_text,
    )
    assert rework_hash_match is not None, (
        "review_rework.md must contain REVIEW_REWORK_SCHEMA_HASH"
    )
    rework_schema_hash = rework_hash_match.group(1)
    assert len(rework_schema_hash) > 16, f"Rework schema hash too short: {rework_schema_hash}"

    # Different from review.md hash
    assert schema_hash != rework_schema_hash, (
        "review.md and review_rework.md must have different schema hashes"
    )

    # Explicitly forbids REVIEW- task IDs
    assert "REVIEW-{" in rework_text or "REVIEW-{anything}" in rework_text, (
        "review_rework.md must explicitly forbid REVIEW- patterns in task_id fields"
    )
    assert "FORBIDDEN" in rework_text.upper(), (
        "review_rework.md must have explicit FORBIDDEN section for REVIEW IDs"
    )

    # Requires typed target routing
    assert 'target' in rework_text or '"kind": "task"' in rework_text, (
        "review_rework.md must require target field"
    )

    # Rework outcome markers
    assert "rework_verdict" in rework_text, "review_rework.md must define rework_verdict"
    assert "deterministic_check" in rework_text, (
        "review_rework.md must require deterministic_check for resolved rework"
    )

    # ── REVIEW- prefix is explicitly cited as forbidden ────────────────────
    for text, name in [(review_text, "review.md"), (rework_text, "review_rework.md")]:
        # The string "REVIEW-001" appears as a forbidden example
        has_explicit_review_rejection = (
            "REVIEW-001" in text
            or "REVIEW-" in text
        )
        assert has_explicit_review_rejection, (
            f"{name} must contain an explicit reference to REVIEW- prefix as forbidden"
        )
