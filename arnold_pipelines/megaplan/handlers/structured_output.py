"""Strict scratch promotion helper for structured-output file-fill phases.

This module defines the shared promotion semantics that every file-fill
handler (finalize, gate, critique_evaluator, critique, review) relies on.
It is kept small and strict by design — no broad type coercion, no
permissive schema changes.

Decision records (SD1–SD3 from the plan):
  SD1: TemplateRegistration is separate from StepContract.
  SD2: File-fill applies only to Hermes/file-tool workers.
  SD3: Missing/unmodified scratch → fallback to worker.payload;
       modified+invalid scratch → hard fail *only* when the worker was
       instructed to fill the file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from arnold_pipelines.megaplan.template_registry import get_template_registration
from arnold_pipelines.megaplan.workers import WorkerResult

LOGGER = logging.getLogger("megaplan")

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

#: Outcomes of a scratch-file promotion attempt.
ScratchStatus = Literal["missing", "unmodified", "filled", "invalid"]


# ---------------------------------------------------------------------------
# Core promotion logic
# ---------------------------------------------------------------------------


def _scratch_path(plan_dir: Path, scratch_filename: str) -> Path:
    """Return the expected scratch file path — absolute, no traversal."""
    candidate = plan_dir / scratch_filename
    # Defend against accidental path traversal that could escape plan_dir.
    # (The registry enforces flat filenames, but belt-and-suspenders.)
    resolved = candidate.resolve()
    if not str(resolved).startswith(str(plan_dir.resolve())):
        raise ValueError(
            f"Scratch filename {scratch_filename!r} escapes plan_dir"
        )
    return resolved


def _read_scratch_json(path: Path) -> Any | None:
    """Try to read *path* as JSON.  Returns parsed value or ``None``."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _strip_unknown_keys(payload: dict[str, Any], known_keys: frozenset[str]) -> dict[str, Any]:
    """Return *payload* with only *known_keys* preserved at the top level.

    Unknown top-level keys are stripped before promotion so that promoted
    canonical artifacts remain schema-valid.  The model may inject
    commentary keys the template didn't include; those are dropped.
    """
    if not isinstance(payload, dict):
        return payload
    return {k: v for k, v in payload.items() if k in known_keys}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_scratch(
    plan_dir: Path,
    scratch_filename: str,
    seed_json: str | None = None,
) -> tuple[ScratchStatus, dict[str, Any] | None]:
    """Read the expected scratch file and classify its status.

    Args:
        plan_dir: The plan directory where the scratch file lives.
        scratch_filename: The scratch filename (e.g. ``"finalize_output.json"``).
        seed_json: The seed template that was written before worker invocation.
            If ``None``, only *missing* vs *invalid* can be distinguished;
            *unmodified* can only be detected when a seed is supplied.

    Returns:
        ``(status, parsed_payload)`` where *status* is one of:

        * ``"missing"`` — the scratch file does not exist.
        * ``"unmodified"`` — the scratch file exists and is byte-identical
          to *seed_json*.  The model did not fill it.
        * ``"filled"`` — the scratch file exists, differs from the seed,
          and parses as valid JSON (a ``dict``).
        * ``"invalid"`` — the scratch file exists, differs from the seed,
          and does **not** parse as a valid JSON ``dict``.

        *parsed_payload* is the parsed JSON ``dict`` for ``"filled"``
        status, or ``None`` for all other statuses.
    """
    path = _scratch_path(plan_dir, scratch_filename)

    if not path.exists():
        return "missing", None

    # If a seed is supplied, compare byte-for-byte.  An identical file
    # means the model never touched it — it's the idempotent seed.
    if seed_json is not None:
        try:
            current_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return "missing", None
        if current_text == seed_json:
            return "unmodified", None

    # File exists and is different from the seed (or no seed).  Try to parse.
    parsed = _read_scratch_json(path)
    if isinstance(parsed, dict):
        return "filled", parsed
    else:
        return "invalid", None


def promote_scratch(
    plan_dir: Path,
    scratch_filename: str,
    known_keys: frozenset[str],
    worker: WorkerResult,
    *,
    seed_json: str | None = None,
    file_fill_instructed: bool = True,
    phase_identity: str | None = None,
) -> tuple[ScratchStatus, dict[str, Any]]:
    """Promote a scratch file to a handler-usable payload.

    This is the single shared entry-point for every file-fill handler.
    It reads **only** the expected scratch file (*expected-path-only reads*),
    classifies its status, strips unknown top-level keys, and falls back
    to ``worker.payload`` when the scratch is missing or unmodified.

    A model write to a wrong path (e.g. writing to the canonical artifact
    path instead of the scratch path) is silently ignored — the handler
    only reads the expected scratch file.

    Args:
        plan_dir: The plan directory.
        scratch_filename: The scratch filename (e.g. ``"finalize_output.json"``).
        known_keys: The set of expected top-level keys.  Unknown keys
            are stripped before the payload is returned.
        worker: The ``WorkerResult`` from the worker invocation.  Its
            ``.payload`` is the inline JSON fallback.
        seed_json: The seed template content.  Used for unmodified detection.
        file_fill_instructed: Whether the worker was instructed to fill
            the scratch file.  When ``True``, a modified-but-invalid scratch
            file is a hard failure (raises :class:`ValueError`).  When
            ``False``, falls back to ``worker.payload``.
        phase_identity: Optional phase identity (e.g. ``"finalize"``).
            When supplied, ``batch_assembly`` phases are rejected with a
            :class:`ValueError` before any file I/O.  ``markdown_exempt``
            and ``subloop_exempt`` phases are also rejected.  When ``None``
            (default), no phase-mode check is performed (backward compatible).

    Returns:
        ``(status, payload)`` where *payload* is the promoted (and
        possibly stripped) content ready for handler consumption.

    Raises:
        ValueError: When *phase_identity* is a ``batch_assembly`` phase,
            or when the scratch file was modified by the model but does
            not parse as valid JSON AND *file_fill_instructed* is ``True``
            (``SD3`` — modified invalid scratch under file-fill instruction
            is a hard failure).
    """
    # ── Reject batch_assembly (and other ineligible modes) before any I/O ──
    if phase_identity is not None:
        assert_file_fill_eligible(phase_identity)

    LOGGER.debug(
        "promote_scratch: phase=%s scratch=%s file_fill_instructed=%s",
        scratch_filename.removesuffix("_output.json"),
        scratch_filename,
        file_fill_instructed,
    )

    status, parsed = classify_scratch(plan_dir, scratch_filename, seed_json=seed_json)

    # ── Missing or unmodified → inline JSON fallback ──────────────────
    if status in ("missing", "unmodified"):
        LOGGER.debug(
            "promote_scratch: %s scratch (%s) → falling back to worker.payload",
            status,
            scratch_filename,
        )
        return status, worker.payload

    # ── Modified but invalid ──────────────────────────────────────────
    if status == "invalid":
        if file_fill_instructed:
            LOGGER.error(
                "promote_scratch: modified invalid scratch (%s) with "
                "file_fill_instructed=True → failing hard",
                scratch_filename,
            )
            raise ValueError(
                f"Scratch file {scratch_filename!r} was modified by the model "
                f"but does not contain valid JSON.  The worker was instructed "
                f"to fill this file — cannot fall back."
            )
        else:
            LOGGER.debug(
                "promote_scratch: modified invalid scratch (%s) with "
                "file_fill_instructed=False → falling back to worker.payload",
                scratch_filename,
            )
            return status, worker.payload

    # ── Filled (valid JSON dict) → strip unknown keys, promote ────────
    assert parsed is not None  # "filled" always carries parsed dict
    stripped = _strip_unknown_keys(parsed, known_keys)
    if len(stripped) != len(parsed):
        dropped = [k for k in parsed if k not in known_keys]
        LOGGER.debug(
            "promote_scratch: stripped %d unknown top-level keys from %s: %s",
            len(dropped),
            scratch_filename,
            dropped,
        )
    return "filled", stripped


def resolve_scratch_filename_for_phase(phase_identity: str) -> str | None:
    """Return the scratch filename for *phase_identity*, or ``None``.

    Convenience helper that looks up the :class:`TemplateRegistration`
    for *phase_identity* and returns its ``scratch_filename``.
    Returns ``None`` when the phase is not registered or has no scratch
    filename (markdown_exempt / subloop_exempt modes).
    """
    reg = get_template_registration(phase_identity)
    if reg is None or not reg.scratch_filename:
        return None
    return reg.scratch_filename


def require_scratch_filename_for_phase(phase_identity: str) -> str:
    """Return the registered scratch filename or fail loudly."""

    scratch_filename = resolve_scratch_filename_for_phase(phase_identity)
    if scratch_filename is None:
        raise ValueError(f"{phase_identity}: no registered scratch filename")
    return scratch_filename


# ---------------------------------------------------------------------------
# File-fill eligibility guard (prevents batch_assembly promotion)
# ---------------------------------------------------------------------------


def assert_file_fill_eligible(phase_identity: str) -> None:
    """Raise :class:`ValueError` if *phase_identity* is not eligible for
    single-file scratch promotion.

    ``batch_assembly`` phases (e.g. ``execute``) assemble their output from
    multiple batch outputs — single-file scratch promotion is semantically
    wrong for them.  ``markdown_exempt`` and ``subloop_exempt`` phases have
    no scratch file at all.

    Callers should invoke this before ``promote_scratch`` for defense-in-depth;
    ``promote_scratch`` itself also rejects ``batch_assembly`` when
    *phase_identity* is supplied.
    """
    reg = get_template_registration(phase_identity)
    if reg is None:
        raise ValueError(
            f"Phase {phase_identity!r} is not registered in the template registry. "
            f"Only registered file_fill and deferred phases are eligible for "
            f"single-file scratch promotion."
        )
    if reg.mode == "batch_assembly":
        raise ValueError(
            f"Phase {phase_identity!r} is registered as batch_assembly. "
            f"Batch-assembly phases (e.g. execute) assemble output from "
            f"multiple batch outputs and MUST NOT use single-file scratch promotion. "
            f"Use the phase-specific handler instead."
        )
    if reg.mode in ("markdown_exempt", "subloop_exempt"):
        raise ValueError(
            f"Phase {phase_identity!r} is registered as {reg.mode}. "
            f"It has no scratch file and is not eligible for single-file "
            f"scratch promotion."
        )


# ---------------------------------------------------------------------------
# Structured promotion evidence (T9)
# ---------------------------------------------------------------------------


def _resolve_boundary_ids(phase_identity: str) -> tuple[str, ...]:
    """Return the boundary contract ids for *phase_identity* from the registry.

    Returns the registered ``boundary_contract_ids`` when the phase has them,
    falling back to a small phase-specific mapping for backward compatibility.
    Returns an empty tuple when no boundary ids can be resolved.
    """
    reg = get_template_registration(phase_identity)
    if reg is not None and reg.boundary_contract_ids:
        return reg.boundary_contract_ids
    # Phase-specific fallback for callers that haven't set up template registry
    # bindings (robustness: backward compat).
    if phase_identity == "gate":
        return ("gate_to_revise",)
    if phase_identity == "finalize":
        return ("finalize_artifacts",)
    return ()


def build_promotion_evidence(
    plan_dir: Path,
    scratch_status: ScratchStatus,
    *,
    phase_identity: str,
    scratch_filename: str,
    worker_payload_used: bool = False,
) -> list[dict[str, Any]]:
    """Emit structured evidence records describing the promotion outcome.

    This function inspects the plan directory after ``promote_scratch`` and
    produces evidence records for four distinct promotion states:

    * **scratch-written/unpromoted** — the model wrote to scratch but the
      content was not promoted (``missing`` / ``unmodified`` / ``invalid``).
    * **canonical-without-receipt** — a canonical output artifact exists in
      the plan directory but no boundary receipt has been emitted.
    * **receipt-without-phase_result** — a boundary receipt exists but
      ``phase_result.json`` is missing or stale.
    * **model-written-wrong-path** — the model wrote output to an unexpected
      path (e.g. canonical artifact path instead of scratch path).

    Each evidence record is a plain ``dict`` with the standard boundary
    evidence shape so callers can convert to :class:`BoundaryEvidence` or
    serialize directly.  This function is intentionally read-only — it
    never writes files or mutates registry state.

    Args:
        plan_dir: The plan directory.
        scratch_status: The outcome from ``promote_scratch``
            (``\"missing\"``, ``\"unmodified\"``, ``\"filled\"``, ``\"invalid\"``).
        phase_identity: The phase identity (e.g. ``\"gate\"``, ``\"finalize\"``).
        scratch_filename: The scratch filename (e.g. ``\"gate_output.json\"``).
        worker_payload_used: Whether the handler fell back to
            ``worker.payload`` (inline JSON) instead of promoting scratch
            content.  Set ``True`` when *scratch_status* is ``\"missing\"``
            or ``\"unmodified\"``.

    Returns:
        A list of evidence dicts (possibly empty).  Each dict has keys:
        ``evidence_id``, ``boundary_id``, ``workflow_id``,
        ``promotion_state``, ``phase_identity``, ``scratch_status``,
        ``scratch_filename``, and ``details``.
    """
    evidence_records: list[dict[str, Any]] = []
    workflow_id = "megaplan-review"
    _now = None  # lazy import to avoid top-level dependency

    # ── resolve boundary ids for this phase ───────────────────────────
    boundary_ids = _resolve_boundary_ids(phase_identity)
    primary_boundary_id = boundary_ids[0] if boundary_ids else ""

    # ── canonical artifact paths ──────────────────────────────────────
    # Derive the likely canonical artifact filename from the scratch
    # filename (e.g. "gate_output.json" → "gate.json").
    canonical_candidate = scratch_filename.replace("_output.json", ".json")
    canonical_path = plan_dir / canonical_candidate

    # Detect whether the model wrote to a wrong path (e.g. wrote directly
    # to the canonical artifact path instead of the scratch path).
    scratch_path = plan_dir / scratch_filename
    scratch_exists = scratch_path.exists()
    canonical_exists = canonical_path.exists()

    model_wrote_wrong_path = (
        not scratch_exists
        and canonical_exists
        and scratch_status in ("missing", "unmodified")
    )

    # ── scratch-written / unpromoted ──────────────────────────────────
    if scratch_status in ("missing", "unmodified", "invalid"):
        import time as _time

        if _now is None:
            _now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())

        promotion_state: str
        if scratch_status == "missing":
            promotion_state = "scratch-missing-fallback"
        elif scratch_status == "unmodified":
            promotion_state = "scratch-unmodified-fallback"
        else:
            promotion_state = "scratch-invalid-fallback"

        evidence_records.append({
            "evidence_id": f"promotion-{phase_identity}-{promotion_state}",
            "boundary_id": primary_boundary_id,
            "workflow_id": workflow_id,
            "promotion_state": promotion_state,
            "phase_identity": phase_identity,
            "scratch_status": scratch_status,
            "scratch_filename": scratch_filename,
            "observation_time": _now,
            "details": {
                "fallback_source": (
                    "worker.payload" if worker_payload_used else "none"
                ),
                "scratch_exists": scratch_exists,
                "canonical_exists": canonical_exists,
                "model_wrote_wrong_path": model_wrote_wrong_path,
            },
        })

    # ── canonical-without-receipt ─────────────────────────────────────
    # When a canonical artifact exists but no boundary receipt for the
    # phase has been written.  Receipts are stored under the boundary id
    # filename (e.g. boundary_receipts/gate_to_revise.json), matching
    # write_boundary_receipt() and semantic-health receipt paths.
    if canonical_exists and boundary_ids:
        any_receipt_exists = any(
            (plan_dir / "boundary_receipts" / f"{bid}.json").exists()
            for bid in boundary_ids
        )
        if not any_receipt_exists:
            if _now is None:
                import time as _time
                _now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
            missing_paths = [
                str(plan_dir / "boundary_receipts" / f"{bid}.json")
                for bid in boundary_ids
            ]
            evidence_records.append({
                "evidence_id": (
                    f"promotion-{phase_identity}-canonical-without-receipt"
                ),
                "boundary_id": primary_boundary_id,
                "workflow_id": workflow_id,
                "promotion_state": "canonical-without-receipt",
                "phase_identity": phase_identity,
                "scratch_status": scratch_status,
                "scratch_filename": scratch_filename,
                "observation_time": _now,
                "details": {
                    "canonical_artifact": canonical_candidate,
                    "canonical_exists": True,
                    "receipt_exists": False,
                    "checked_boundary_ids": list(boundary_ids),
                    "receipt_paths_checked": missing_paths,
                },
            })

    # ── receipt-without-phase_result ──────────────────────────────────
    # When a boundary receipt exists but phase_result.json is missing
    # or does not record this phase.  Receipts are checked under the
    # boundary id filename, matching write_boundary_receipt().
    if boundary_ids:
        phase_result_path = plan_dir / "phase_result.json"
        phase_result_missing = not phase_result_path.exists()
        phase_result_stale = False
        recorded_phase = None
        if not phase_result_missing:
            try:
                import json as _json
                pr = _json.loads(phase_result_path.read_text(encoding="utf-8"))
                recorded_phase = pr.get("phase") if isinstance(pr, dict) else None
                phase_result_stale = recorded_phase != phase_identity
            except (OSError, ValueError):
                phase_result_missing = True

        for bid in boundary_ids:
            receipt_path = plan_dir / "boundary_receipts" / f"{bid}.json"
            if receipt_path.exists():
                if phase_result_missing or phase_result_stale:
                    if _now is None:
                        import time as _time
                        _now = _time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", _time.gmtime()
                        )
                    state_label = (
                        "missing" if phase_result_missing else "stale-phase"
                    )
                    evidence_records.append({
                        "evidence_id": (
                            f"promotion-{phase_identity}"
                            f"-receipt-without-phase-result"
                        ),
                        "boundary_id": bid,
                        "workflow_id": workflow_id,
                        "promotion_state": (
                            f"receipt-without-phase-result-{state_label}"
                        ),
                        "phase_identity": phase_identity,
                        "scratch_status": scratch_status,
                        "scratch_filename": scratch_filename,
                        "observation_time": _now,
                        "details": {
                            "receipt_exists": True,
                            "receipt_path": str(receipt_path),
                            "phase_result_missing": phase_result_missing,
                            "phase_result_stale": phase_result_stale,
                            "expected_phase": phase_identity,
                        },
                    })

    # ── model-written-wrong-path ──────────────────────────────────────
    if model_wrote_wrong_path:
        evidence_records.append({
            "evidence_id": (
                f"promotion-{phase_identity}-model-wrote-wrong-path"
            ),
            "boundary_id": primary_boundary_id,
            "workflow_id": workflow_id,
            "promotion_state": "model-wrote-wrong-path",
            "phase_identity": phase_identity,
            "scratch_status": scratch_status,
            "scratch_filename": scratch_filename,
            "observation_time": _now,
            "details": {
                "expected_path": str(scratch_path),
                "unexpected_path": str(canonical_path),
                "scratch_exists": False,
                "canonical_exists": True,
                "note": (
                    "Model wrote to canonical artifact path instead of "
                    "the expected scratch path. The handler only reads "
                    "the expected scratch file (expected-path-only), so "
                    "this write is silently ignored."
                ),
            },
        })

    return evidence_records
