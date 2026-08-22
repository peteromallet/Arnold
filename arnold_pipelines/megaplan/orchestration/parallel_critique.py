"""Parallel critique runner — dispatches one read-only worker per check via
the generic worker fan-out primitives in :mod:`megaplan._core.worker_fanout`.

Each check carries a resolved :class:`~megaplan.types.AgentMode` (attached by
the critique handler per gate decision SD1).  The runner builds one
:class:`~megaplan._core.WorkerUnit` per check, scatters them through
:func:`~megaplan._core.scatter_worker_units`, and reduces the ordered results
while preserving the verified/disputed flag-merge semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

from arnold_pipelines.megaplan._core import (
    _merge_unique,
    atomic_write_json,
    atomic_write_text,
    sha256_file,
    WorkerUnit,
    WorkerUnitResult,
    scatter_worker_units,
)
from arnold_pipelines.megaplan.orchestration.critique_status import (
    UNVERIFIABLE_STATUS,
    annotate_unverifiable_checks,
    unverifiable_detail,
)
from arnold_pipelines.megaplan.orchestration.critique_custody import (
    canonical_critique_flag_id,
)
from arnold_pipelines.megaplan.custody.phase_wbc import phase_wbc_state
from arnold_pipelines.megaplan.custody.worker_dispatch_wbc import (
    query_worker_dispatch_manifest,
)
from arnold_pipelines.megaplan.model_seam import ModelTier
from arnold_pipelines.megaplan.prompts.critique import single_check_critique_prompt, write_single_check_template
from arnold_pipelines.megaplan.pipelines.creative.prompts.critique_joke import single_check_critique_joke_prompt
from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.types import CliError, PlanState
from arnold_pipelines.megaplan.workers import STEP_SCHEMA_FILENAMES, WorkerResult
from arnold_pipelines.megaplan.workers.result_metadata import aggregate_rate_limits


_CRITIQUE_WORKER_SHAPE_RETRIES = 2
_CRITIQUE_REPAIR_INSTRUCTION = (
    "Return a JSON object with a top-level `checks` array containing EXACTLY ONE "
    "check object for this single lens. Do not include multiple checks or wrap it differently. "
    "Every flag must be an object with non-empty concern and evidence strings. Flag IDs are "
    "worker-local labels only; the reducer assigns canonical global IDs."
)
_CRITIQUE_UNVERIFIABLE_SHAPE_REASON = (
    "parallel critique worker output did not contain a usable check object for "
    "this lens after retry; operator review may be needed"
)
_SANDBOX_NAMESPACE_REASON_MARKERS = (
    "bwrap",
    "bubblewrap",
    "sandbox namespace",
    "no permissions to create new namespace",
    "shell/file access is blocked in this environment",
)


class _RetryableCritiqueContractError(Exception):
    """Internal signal for a locally attributable worker contract failure."""

    def __init__(self, check_id: str, diagnostic: str, raw_payload: Any) -> None:
        super().__init__(f"Parallel critique worker '{check_id}' {diagnostic}")
        self.check_id = check_id
        self.diagnostic = diagnostic
        self.raw_payload = raw_payload


class _RetryableCritiqueShapeError(_RetryableCritiqueContractError):
    """Internal signal for a critique worker shape that can be repaired by retry."""

    def __init__(self, check_id: str, check_count: int, raw_payload: Any) -> None:
        super().__init__(
            check_id,
            f"returned {check_count} checks instead of exactly one",
            raw_payload,
        )
        self.check_count = check_count


def _critique_raw_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_raw.txt")
def critique_seed_output_name(check_id: str, *, agent: str | None = None) -> str:
    """Return the schema seed filename used by the critique capture contract."""
    suffix = ".seed.json" if agent == "codex" else ".json"
    return f"critique_check_{check_id}{suffix}"


def _unit_evidence_path(plan_dir: Path, unit: WorkerUnit) -> Path:
    """Resolve a worker's evidence path, including an unbound seed fallback."""
    if unit.output_path is not None:
        return unit.output_path
    check_id = unit.extra.get("check_id", "unknown")
    return plan_dir / critique_seed_output_name(str(check_id), agent="codex")



def _persist_critique_raw_output(
    output_path: Path,
    raw_output: object,
    *,
    iteration: int | None = None,
) -> None:
    text = "" if raw_output is None else str(raw_output)
    if not text:
        return
    try:
        path = (
            output_path.with_name(f"{output_path.stem}_raw_v{iteration}.txt")
            if iteration is not None
            else _critique_raw_output_path(output_path)
        )
        atomic_write_text(path, text)
    except OSError:
        pass


def _unverifiable_check_payload(
    check_id: str,
    question: str,
    reason: str,
    *,
    cause: str | None = None,
    retryable: bool | None = None,
    error_kind: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": check_id,
        "question": question,
        "status": UNVERIFIABLE_STATUS,
        "unverifiable_reason": reason,
        "findings": [
            {"detail": unverifiable_detail(reason), "flagged": False},
        ],
    }
    if cause:
        payload["unverifiable_cause"] = cause
    if retryable is not None:
        payload["unverifiable_retryable"] = retryable
    if error_kind:
        payload["unverifiable_error_kind"] = error_kind
    return payload


def _source_flags_with_id_map(
    raw_payload: Any, check_id: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Validate one producer and assign reducer-owned globally stable flag IDs."""
    if not isinstance(raw_payload, dict) or not isinstance(raw_payload.get("flags"), list):
        return [], {}
    sourced: list[dict[str, Any]] = []
    local_to_global: dict[str, str] = {}
    local_id_indices: dict[str, int] = {}
    canonical_id_indices: dict[str, int] = {}
    issues: list[str] = []
    for index, raw_flag in enumerate(raw_payload["flags"]):
        if not isinstance(raw_flag, dict):
            issues.append(f"flags[{index}] is not an object")
            continue
        flag = dict(raw_flag)
        producer_category = str(flag.get("category") or "other").strip().lower()
        category_aliases = {
            "scope": "completeness",
            "structure": "completeness",
            "sizing": "completeness",
            "documentation": "doc-quality",
        }
        canonical_categories = {
            "correctness", "security", "completeness", "performance",
            "maintainability", "doc-quality", "other", "verifiability",
        }
        flag["category"] = category_aliases.get(
            producer_category,
            producer_category if producer_category in canonical_categories else "other",
        )
        if flag["category"] != producer_category:
            flag["producer_category"] = producer_category
        producer_severity = str(
            flag.get("severity_hint") or flag.get("severity") or "uncertain"
        ).strip().lower()
        flag.pop("severity", None)
        if producer_severity in {"high", "major", "critical", "significant", "likely-significant"}:
            severity_hint = "likely-significant"
        elif producer_severity in {"low", "minor", "cosmetic", "likely-minor"}:
            severity_hint = "likely-minor"
        else:
            severity_hint = "uncertain"
        flag["severity_hint"] = severity_hint
        if producer_severity != severity_hint:
            flag["producer_severity"] = producer_severity
        concern = str(flag.get("concern") or flag.get("evidence") or "").strip()
        evidence = str(flag.get("evidence") or "").strip() or concern
        if not concern:
            issues.append(f"flags[{index}].concern and evidence are blank")
            continue
        if not evidence:
            issues.append(f"flags[{index}].evidence is blank and cannot be normalized")
            continue
        flag["concern"] = concern
        flag["evidence"] = evidence
        flag["source_check_id"] = check_id
        local_id = str(flag.get("id") or "").strip()
        canonical_id = canonical_critique_flag_id(flag)
        if local_id:
            prior = local_to_global.get(local_id)
            if prior is not None:
                issues.append(
                    f"flags[{index}].id {local_id!r} duplicates flags[{local_id_indices[local_id]}]"
                )
                continue
            local_to_global[local_id] = canonical_id
            local_id_indices[local_id] = index
            flag["producer_flag_id"] = local_id
        if canonical_id in canonical_id_indices:
            issues.append(
                f"flags[{index}] duplicates the canonical finding at "
                f"flags[{canonical_id_indices[canonical_id]}]"
            )
            continue
        canonical_id_indices[canonical_id] = index
        flag["id"] = canonical_id
        sourced.append(flag)
    if issues:
        raise _RetryableCritiqueContractError(
            check_id,
            "failed producer validation: " + "; ".join(issues),
            raw_payload,
        )
    return sourced, local_to_global


def _source_flags(raw_payload: Any, check_id: str) -> list[dict[str, Any]]:
    """Compatibility wrapper returning validated, canonically identified flags."""
    return _source_flags_with_id_map(raw_payload, check_id)[0]


def _infer_unverifiable_cause(reason: str) -> tuple[str | None, bool | None, str | None]:
    normalized = str(reason or "").lower()
    if any(marker in normalized for marker in _SANDBOX_NAMESPACE_REASON_MARKERS):
        return "sandbox_namespace", False, "sandbox_namespace"
    if "rate limit" in normalized or "rate_limit" in normalized:
        return "provider_rate_limit", True, "rate_limit"
    if "capacity" in normalized or "quota" in normalized:
        return "provider_capacity", True, "rate_limit"
    return None, None, None


def _flags_only_unverifiable_payload(
    raw_payload: Any,
    *,
    check_id: str,
    question: str,
) -> dict[str, Any] | None:
    if not isinstance(raw_payload, dict):
        return None
    flags = raw_payload.get("flags")
    if not isinstance(flags, list) or not flags:
        return None
    dict_flags = [item for item in flags if isinstance(item, dict)]
    if not dict_flags:
        return None
    flag = dict_flags[0]
    category = str(flag.get("category", "")).strip().lower()
    concern = str(flag.get("concern", "")).strip()
    evidence = str(flag.get("evidence", "")).strip()
    reason = evidence or concern or "the worker could not verify this check"
    cause, retryable, error_kind = _infer_unverifiable_cause(reason)
    if category == "verifiability" and cause is not None:
        return _unverifiable_check_payload(
            check_id,
            question,
            reason,
            cause=cause,
            retryable=retryable,
            error_kind=error_kind,
        )
    # A valid flags-only critique is substantive evidence, not a parse
    # failure. Preserve every flag as a blocking finding instead of converting
    # it to a synthetic flagged:false unverifiable record.
    return {
        "id": check_id,
        "question": question,
        "status": "complete",
        "findings": [
            {
                "detail": str(item.get("evidence") or item.get("concern") or item.get("id") or "critique flag"),
                "flagged": True,
            }
            for item in dict_flags
        ],
    }



def run_parallel_critique(
    state: PlanState,
    plan_dir: Path,
    *,
    root: Path,
    model: str | None,
    checks: tuple[dict[str, Any], ...],
    effort: str | None = None,
    max_concurrent: int | None = None,
) -> WorkerResult:
    """Run one single-check critique per *check* in parallel via worker fan-out.

    Each check MUST carry a ``_resolved_agent_mode`` key (an
    :class:`~megaplan.types.AgentMode` attached by the critique handler per
    gate decision SD1).  A :class:`~megaplan._core.WorkerUnit` is built per
    check with a unique output path, the single-check critique prompt, and
    ``read_only=True``.  Units are dispatched through
    :func:`~megaplan._core.scatter_worker_units`; results are reduced in
    input order while preserving the verified/disputed flag-merge semantics
    (disputed flags override verified).

    No session state is mutated — every unit is dispatched read-only.
    """
    started = time.monotonic()
    phase = phase_wbc_state(state, step="critique")
    invocation_id = str((state.get("meta") or {}).get("current_invocation_id") or "")
    if (
        phase is None
        or not invocation_id
        or phase.get("invocation_id") != invocation_id
    ):
        raise CliError(
            "critique_phase_custody_missing",
            "Parallel critique requires a fresh matching critique phase WBC before scatter",
        )
    if not checks:
        return WorkerResult(
            payload={"checks": [], "flags": [], "verified_flag_ids": [], "disputed_flag_ids": []},
            raw_output="parallel",
            duration_ms=0,
            cost_usd=0.0,
            session_id=None,
        )

    # Minimal args namespace for worker dispatch — the real args are not
    # available at this layer and the downstream uses of args (explicit-agent
    # detection, phase-model overrides) are handled by the caller.
    _args = argparse.Namespace(
        agent=None,
        phase_model=[],
    )

    _mode = state.get("config", {}).get("mode", "code")
    _prompt_builder = (
        single_check_critique_joke_prompt
        if _mode == "joke"
        else single_check_critique_prompt
    )
    _schema = SCHEMAS[STEP_SCHEMA_FILENAMES["critique"]]

    # ------------------------------------------------------------------
    # Build one WorkerUnit per check
    # ------------------------------------------------------------------
    # Each unit runs in its OWN process and opens its own session DB. The
    # step+agent session_key collapses to a single shared db path, so without
    # an override every concurrent worker writes the SAME SQLite file →
    # "database is locked". Give each check its own session db (the legacy
    # _run_check path did this); the override is plumbed through
    # WorkerUnit.extra["worker_options"]["session_db_path"] (worker_fanout.py)
    # → the worker step's db_override.
    from arnold_pipelines.megaplan.workers._payload import _worker_db_path

    units: list[WorkerUnit] = []
    for _idx, _check in enumerate(checks):
        _resolved = _check.get("_resolved_agent_mode")
        if _resolved is None:
            raise CliError(
                "invariant_error",
                f"No _resolved_agent_mode metadata on check '{_check.get('id', '?')}' — "
                "the critique handler must attach a resolved AgentMode per SD1",
            )

        _output_path = write_single_check_template(
            plan_dir, state, _check, f"critique_check_{_check['id']}.json",
        )
        _prompt = _prompt_builder(state, plan_dir, root, _check, _output_path)
        _seam_tier = (
            ModelTier.ENFORCED if _resolved.agent in {"codex", "omp"} else ModelTier.NON_ENFORCED
        )

        units.append(
            WorkerUnit(
                step="critique",
                resolved=_resolved,
                prompt=_prompt,
                output_path=_output_path,
                read_only=True,
                validation_step="critique",
                schema=_schema,
                model=_resolved.resolved_model or _resolved.model,
                tier=_seam_tier,
                extra={
                    "check_id": _check["id"],
                    "question": _check.get("question", ""),
                    "index": _idx,
                    "ledger_step_label": _check["id"],
                    "ledger_selected_spec": _check.get("_routing_selected_spec"),
                    "ledger_tier": _check.get("_routing_tier"),
                    "ledger_complexity": _check.get("complexity"),
                    "ledger_tier_routing_active": bool(_check.get("_routing_tier_active", False)),
                    "wbc_dispatch_key": f"critique:{_check['id']}:initial",
                    "worker_options": {
                        "session_db_path": str(_worker_db_path(plan_dir, f"critique_{_check['id']}")),
                        "check_id": str(_check["id"]),
                        "question": str(_check.get("question", "")),
                    },
                },
            )
        )

    # ------------------------------------------------------------------
    # Parse hook: extract exactly one check + verified/disputed per unit
    # ------------------------------------------------------------------
    def _parse_result(
        _index: int,
        raw_payload: Any,
        unit: WorkerUnit,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]]:
        _checks_list = raw_payload.get("checks") if isinstance(raw_payload, dict) else None
        _cid = unit.extra.get("check_id", "?")
        if isinstance(raw_payload, dict):
            _status = raw_payload.get("status") or raw_payload.get("result")
            _status_text = str(_status).strip().lower() if _status is not None else ""
            if _status_text == UNVERIFIABLE_STATUS or raw_payload.get(UNVERIFIABLE_STATUS) is True:
                _reason = (
                    raw_payload.get("reason")
                    or raw_payload.get("detail")
                    or raw_payload.get("message")
                    or "the worker could not verify this check"
                )
                return (
                    {
                        "id": _cid,
                        "question": unit.extra.get("question", ""),
                        "status": UNVERIFIABLE_STATUS,
                        "unverifiable_reason": str(_reason),
                        "findings": [
                            {"detail": unverifiable_detail(str(_reason)), "flagged": False}
                        ],
                    },
                    [],
                    [],
                    [],
                )
            # A producer may return both its canonical check assessment and
            # supporting flags.  The flags-only compatibility path must never
            # replace that valid check: flag evidence is allowed to be terse,
            # while check findings intentionally have a stronger minimum
            # detail contract.  Treating a full payload as flags-only caused
            # valid parallel critiques to fail nondeterministically depending
            # on which lens happened to include a short evidence locator.
            _has_usable_check = (
                isinstance(_checks_list, list)
                and any(isinstance(item, dict) for item in _checks_list)
            )
            _flags_only = (
                None
                if _has_usable_check
                else _flags_only_unverifiable_payload(
                    raw_payload,
                    check_id=str(_cid),
                    question=str(unit.extra.get("question", "")),
                )
            )
            if _flags_only is not None:
                _verified = raw_payload.get("verified_flag_ids", [])
                _disputed = raw_payload.get("disputed_flag_ids", [])
                _flags, _id_map = _source_flags_with_id_map(raw_payload, str(_cid))
                return (
                    _flags_only,
                    _flags,
                    [_id_map.get(value, value) for value in _verified]
                    if isinstance(_verified, list)
                    else [],
                    [_id_map.get(value, value) for value in _disputed]
                    if isinstance(_disputed, list)
                    else [],
                )
        if isinstance(_checks_list, list) and len(_checks_list) != 1:
            _matching = [
                item for item in _checks_list
                if isinstance(item, dict) and item.get("id") == _cid
            ]
            _dict_checks = [item for item in _checks_list if isinstance(item, dict)]
            _selected = _matching[0] if _matching else (_dict_checks[0] if _dict_checks else None)
            if _selected is not None:
                print(
                    f"[parallel-critique] worker '{_cid}' returned "
                    f"{len(_checks_list)} checks; using "
                    f"{'matching' if _matching else 'first'} check",
                    file=sys.stderr,
                )
                _checks_list = [_selected]
        if not isinstance(_checks_list, list) or len(_checks_list) != 1 or not isinstance(_checks_list[0], dict):
            _count = len(_checks_list) if isinstance(_checks_list, list) else 0
            raise _RetryableCritiqueShapeError(str(_cid), _count, raw_payload)
        _verified = raw_payload.get("verified_flag_ids", [])
        _disputed = raw_payload.get("disputed_flag_ids", [])
        _check_payload = _checks_list[0]
        if _check_payload.get("id") != _cid:
            _check_payload = dict(_check_payload)
            _check_payload["id"] = _cid
            print(
                f"[parallel-critique] worker '{_cid}' returned check id "
                f"'{_checks_list[0].get('id', '?')}'; normalizing to requested check",
                file=sys.stderr,
            )
        if (
            not isinstance(_check_payload.get("question"), str)
            or not _check_payload.get("question", "").strip()
        ):
            _check_payload = dict(_check_payload)
            _check_payload["question"] = unit.extra.get("question", "")
        annotate_unverifiable_checks({"checks": [_check_payload]})
        _flags, _id_map = _source_flags_with_id_map(raw_payload, str(_cid))
        return (
            _check_payload,
            _flags,
            [_id_map.get(value, value) for value in _verified]
            if isinstance(_verified, list)
            else [],
            [_id_map.get(value, value) for value in _disputed]
            if isinstance(_disputed, list)
            else [],
        )

    def _repair_unit(unit: WorkerUnit, retry_number: int) -> WorkerUnit:
        extra = dict(unit.extra)
        extra["wbc_dispatch_key"] = (
            f"critique:{unit.extra.get('check_id', unit.output_path.stem)}:"
            f"shape-repair:{retry_number}"
        )
        return WorkerUnit(
            step=unit.step,
            resolved=unit.resolved,
            prompt=f"{_CRITIQUE_REPAIR_INSTRUCTION}\n\n{unit.prompt}",
            output_path=unit.output_path,
            read_only=unit.read_only,
            validation_step=unit.validation_step,
            schema=unit.schema,
            model=unit.model,
            tier=unit.tier,
            extra=extra,
        )

    def _scatter_raw(current_units: list[WorkerUnit]) -> Any:
        def _on_unit_error(_index: int, exc: Exception) -> tuple[Any, float, int, int, int]:
            unit = current_units[_index]
            check_id = str(unit.extra.get("check_id", "?"))
            cause = None
            retryable = None
            error_kind = None
            if isinstance(exc, CliError):
                _persist_critique_raw_output(
                    unit.output_path,
                    exc.extra.get("raw_output") or exc.message,
                )
                cause = str(exc.extra.get("source") or "") or None
                retryable_raw = exc.extra.get("retryable")
                retryable = retryable_raw if isinstance(retryable_raw, bool) else None
                error_kind = str(exc.code or "") or None
            else:
                _persist_critique_raw_output(unit.output_path, str(exc))
            reason = f"parallel critique worker failed for check '{check_id}': {exc}"
            return (
                {
                    "checks": [
                        _unverifiable_check_payload(
                            check_id,
                            str(unit.extra.get("question", "")),
                            reason,
                            cause=cause,
                            retryable=retryable,
                            error_kind=error_kind,
                        )
                    ],
                    "flags": [],
                    "verified_flag_ids": [],
                    "disputed_flag_ids": [],
                },
                0.0,
                0,
                0,
                0,
            )

        return scatter_worker_units(
            units=current_units,
            state=state,
            plan_dir=plan_dir,
            root=root,
            args=_args,
            parse_result=lambda _idx, item, _unit: item,
            max_concurrent=max_concurrent,
            on_unit_error=_on_unit_error,
        )

    def _accumulate_scatter_totals(scatter_result: Any) -> None:
        nonlocal _total_cost, _total_prompt_tokens, _total_completion_tokens, _total_tokens
        _total_cost += scatter_result.total_cost
        _total_prompt_tokens += scatter_result.total_prompt_tokens
        _total_completion_tokens += scatter_result.total_completion_tokens
        _total_tokens += scatter_result.total_tokens

    # ------------------------------------------------------------------
    # Scatter + repair malformed worker shapes locally
    # ------------------------------------------------------------------
    _total_cost = 0.0
    _total_prompt_tokens = 0
    _total_completion_tokens = 0
    _total_tokens = 0
    _parsed_results: list[
        tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]] | None
    ] = [None] * len(units)
    _rate_limits: list[dict[str, Any] | None] = []

    _sr = _scatter_raw(units)
    _accumulate_scatter_totals(_sr)

    _failures: dict[int, _RetryableCritiqueContractError] = {}
    for _idx, _item in enumerate(_sr.ordered_results):
        _payload = _item.payload if isinstance(_item, WorkerUnitResult) else _item
        atomic_write_json(
            plan_dir / f"critique_check_{units[_idx].extra.get('check_id', _idx)}_producer_v{state['iteration']}.json",
            _payload,
        )
        if isinstance(_item, WorkerUnitResult):
            _persist_critique_raw_output(
                units[_idx].output_path,
                _item.raw_output,
                iteration=int(state["iteration"]),
            )
        _rate_limits.append(_item.rate_limit if isinstance(_item, WorkerUnitResult) else None)
        try:
            _parsed_results[_idx] = _parse_result(_idx, _payload, units[_idx])
        except _RetryableCritiqueContractError as exc:
            if isinstance(_item, WorkerUnitResult):
                _persist_critique_raw_output(units[_idx].output_path, _item.raw_output)
            _failures[_idx] = exc

    _retry_units = units
    for _retry_number in range(1, _CRITIQUE_WORKER_SHAPE_RETRIES + 1):
        if not _failures:
            break
        _next_attempt = _retry_number + 1
        _total_attempts = _CRITIQUE_WORKER_SHAPE_RETRIES + 1
        _retry_indices = list(_failures)
        for _failure in _failures.values():
            print(
                f"[parallel-critique] worker '{_failure.check_id}' contract invalid: "
                f"{_failure.diagnostic}; retrying (attempt {_next_attempt}/{_total_attempts})",
                file=sys.stderr,
            )

        _subset_units = [
            _repair_unit(_retry_units[_idx], _retry_number)
            for _idx in _retry_indices
        ]
        _retry_units_by_index = dict(zip(_retry_indices, _subset_units, strict=True))
        _retry_sr = _scatter_raw(_subset_units)
        _accumulate_scatter_totals(_retry_sr)

        _next_failures: dict[int, _RetryableCritiqueContractError] = {}
        for _subset_pos, _item in enumerate(_retry_sr.ordered_results):
            _original_idx = _retry_indices[_subset_pos]
            _unit = _retry_units_by_index[_original_idx]
            _payload = _item.payload if isinstance(_item, WorkerUnitResult) else _item
            atomic_write_json(
                plan_dir
                / (
                    f"critique_check_{_unit.extra.get('check_id', _original_idx)}"
                    f"_producer_v{state['iteration']}.json"
                ),
                _payload,
            )
            if isinstance(_item, WorkerUnitResult):
                _persist_critique_raw_output(
                    _unit.output_path,
                    _item.raw_output,
                    iteration=int(state["iteration"]),
                )
            _rate_limits.append(_item.rate_limit if isinstance(_item, WorkerUnitResult) else None)
            try:
                _parsed_results[_original_idx] = _parse_result(_original_idx, _payload, _unit)
            except _RetryableCritiqueContractError as exc:
                if isinstance(_item, WorkerUnitResult):
                    _persist_critique_raw_output(_unit.output_path, _item.raw_output)
                _next_failures[_original_idx] = exc
        _failures = _next_failures
        for _idx, _unit in _retry_units_by_index.items():
            _retry_units[_idx] = _unit

    for _idx, _failure in _failures.items():
        _unit = _retry_units[_idx]
        print(
            f"[parallel-critique] worker '{_failure.check_id}' contract invalid after retry "
            f"budget: {_failure.diagnostic}; marking check unverifiable",
            file=sys.stderr,
        )
        _parsed_results[_idx] = (
            _unverifiable_check_payload(
                _failure.check_id,
                str(_unit.extra.get("question", "")),
                _CRITIQUE_UNVERIFIABLE_SHAPE_REASON,
            ),
            [],
            [],
            [],
        )

    # ------------------------------------------------------------------
    # Reduce: ordered checks + flag merge (disputed trumps verified)
    # ------------------------------------------------------------------
    ordered_checks: list[dict[str, Any]] = []
    ordered_flags: list[dict[str, Any]] = []
    verified_groups: list[list[str]] = []
    disputed_groups: list[list[str]] = []
    for _item in _parsed_results:
        if _item is None:
            raise CliError(
                "worker_parse_error",
                "Parallel critique worker result missing after retry processing",
            )
        _check_payload, _flags, _v_ids, _d_ids = _item
        ordered_checks.append(_check_payload)
        ordered_flags.extend(_flags)
        verified_groups.append(_v_ids)
        disputed_groups.append(_d_ids)

    _disputed_flag_ids = _merge_unique(disputed_groups)
    _disputed_set = set(_disputed_flag_ids)
    _verified_flag_ids = [
        flag_id for flag_id in _merge_unique(verified_groups) if flag_id not in _disputed_set
    ]

    child_dispatches = query_worker_dispatch_manifest(
        plan_dir,
        phase_attempt_id=str(phase["attempt_id"]),
    )
    expected_initial_keys = {
        f"critique:{unit.extra['check_id']}:initial" for unit in units
    }
    observed_initial_keys = {
        str(row.get("dispatch_key"))
        for row in child_dispatches
        if row.get("dispatch_key") in expected_initial_keys
    }
    if observed_initial_keys != expected_initial_keys:
        raise CliError(
            "critique_child_custody_incomplete",
            "Parallel critique child dispatch manifest is incomplete: "
            f"expected {sorted(expected_initial_keys)!r}, observed {sorted(observed_initial_keys)!r}",
        )
    producer_artifacts = []
    for unit in units:
        check_id = str(unit.extra["check_id"])
        producer_path = (
            plan_dir
            / f"critique_check_{check_id}_producer_v{state['iteration']}.json"
        )
        raw_path = plan_dir / f"critique_check_{check_id}_raw_v{state['iteration']}.txt"
        if not producer_path.is_file():
            raise CliError(
                "critique_child_custody_incomplete",
                f"Missing persisted producer artifact for critique child {check_id!r}",
            )
        row = {
            "check_id": check_id,
            "producer_artifact": producer_path.name,
            "producer_sha256": sha256_file(producer_path),
        }
        if raw_path.is_file():
            row["raw_artifact"] = raw_path.name
            row["raw_sha256"] = sha256_file(raw_path)
        producer_artifacts.append(row)
    manifest = {
        "schema_version": "megaplan-parallel-critique-child-manifest-v1",
        "iteration": int(state["iteration"]),
        "invocation_id": invocation_id,
        "phase_attempt_id": str(phase["attempt_id"]),
        "expected_check_ids": [str(unit.extra["check_id"]) for unit in units],
        "dispatches": child_dispatches,
        "producer_artifacts": producer_artifacts,
    }
    manifest_digest = "sha256:" + hashlib.sha256(
        json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    manifest["manifest_digest"] = manifest_digest
    manifest_path = plan_dir / f"critique_parallel_manifest_v{state['iteration']}.json"
    atomic_write_json(manifest_path, manifest)

    return WorkerResult(
        payload={
            "checks": ordered_checks,
            "flags": ordered_flags,
            "verified_flag_ids": _verified_flag_ids,
            "disputed_flag_ids": _disputed_flag_ids,
        },
        raw_output="parallel",
        duration_ms=int((time.monotonic() - started) * 1000),
        cost_usd=_total_cost,
        session_id=None,
        prompt_tokens=_total_prompt_tokens,
        completion_tokens=_total_completion_tokens,
        total_tokens=_total_tokens,
        rate_limit=aggregate_rate_limits(_rate_limits),
        auth_metadata={
            "parallel_critique": {
                "manifest_artifact": manifest_path.name,
                "manifest_sha256": sha256_file(manifest_path),
                "manifest_digest": manifest_digest,
                "phase_attempt_id": str(phase["attempt_id"]),
                "invocation_id": invocation_id,
                "child_dispatch_count": len(child_dispatches),
            }
        },
    )
