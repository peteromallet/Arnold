"""Megaplan model-step seam: thin wrapper over arnold.pipeline.model_seam.

This module hosts the megaplan-pipeline-specific behavior layered on top of
the generic model seam in :mod:`arnold.pipeline.model_seam`:

* Step-keyed payload normalizers, compatibility projection guard, capture
  schema resolver, and recovery shape check — all registered against the
  generic hook tables at import time.
* Megaplan render helpers (:func:`render_prompt_for_dispatch`,
  :func:`render_compact_review_prompt`) that compose the megaplan prompt
  bundle and dispatch through :func:`render_step_message`.
* Recovery-aware :func:`capture_step_output` that walks the megaplan output
  files when the raw worker text fails strict JSON parsing.
* :func:`audit_step_payload` / :func:`schema_audits_step_payload` and the
  :func:`assert_all_compatibility_modes_native` guard used by the
  compatibility deletion epic.

Generic primitives (enums, dataclasses, tokenizer/budget machinery,
render_step_message, ModelStepInvocationAdapter, install_model_step_adapter,
recovery JSON parsers, _optional_str/_optional_int helpers) are re-exported
from :mod:`arnold.pipeline.model_seam` so existing megaplan importers keep
working unchanged.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline import (
    ContractResult,
    Provenance,
    validate_contract_result,
    validate_payload_against_schema,
)
from arnold.execution.step_invocation import StepInvocation, StepInvocationAdapterRegistry
from arnold.pipeline import model_seam as _generic
from arnold.pipeline.model_seam import (  # re-exports for megaplan consumers
    AuditStatus,
    BudgetStatus,
    CaptureOutcome,
    ModelBudget,
    ModelBudgetDefaults,
    ModelBudgetError,
    ModelFamily,
    ModelSeamTelemetry,
    ModelStepInvocationAdapter,
    ModelStructuralAuditError,
    ModelTier,
    RenderedStepMessage,
    TerminalStatus,
    TierMetadata,
    _RecoveredPayload,
    _extract_recovery_json_candidates,
    _iter_recovery_json_dicts,
    _parse_recovery_json_file,
    budget_model_input,
    capture_step_output as _generic_capture_step_output,
    classify_model_family,
    install_model_step_adapter,
    register_capture_schema_resolver,
    register_compatibility_projection,
    register_native_normalizer,
    register_recovery_step_shape_check,
    render_step_message,
)
from arnold.pipeline.model_seam import (
    _as_sequence,
    _capture_outcome_schema,
    _optional_int,
    _optional_str,
    _repair_callback,
    _repair_invocation,
)

from arnold_pipelines.megaplan.schemas import SCHEMAS
from arnold_pipelines.megaplan.orchestration.plan_structure import (
    PLAN_STRUCTURE_REQUIRED_STEP_ISSUE,
    validate_plan_structure,
)
from arnold_pipelines.megaplan.step_contracts import CompatibilityMode  # re-export (moved from deleted _compatibility.py)
from arnold_pipelines.megaplan.step_contracts import (
    STEP_CONTRACTS,
    build_capture_schema_keys_by_step,
    build_compatibility_mode_by_step,
    contract_to_invocation,
)

_GATE_CAPTURE_SCHEMA_TOP_LEVEL_FIELDS = frozenset(
    {
        "recommendation",
        "rationale",
        "signals_assessment",
        "warnings",
        "settled_decisions",
        "flag_resolutions",
        "accepted_tradeoffs",
        "north_star_actions",
        "tiebreaker_question",
        "tiebreaker_flag_ids",
        "tiebreaker_fuzzy_group_id",
    }
)
_gate_schema_properties = SCHEMAS["gate.json"].get("properties")
if not isinstance(_gate_schema_properties, Mapping):
    raise RuntimeError("gate.json schema must declare top-level properties")
if _GATE_CAPTURE_SCHEMA_TOP_LEVEL_FIELDS != frozenset(_gate_schema_properties):
    raise RuntimeError(
        "Gate capture normalizer field allowlist drifted from gate.json schema properties"
    )


# --------------------------------------------------------------------------- #
# Megaplan render helpers
# --------------------------------------------------------------------------- #


def render_prompt_for_dispatch(
    agent: str,
    step: str,
    state: Mapping[str, Any],
    plan_dir: Path,
    *,
    root: Path | None = None,
    worker: str | None = None,
    model: str | None = None,
    normalized_model: str | None = None,
    tier: ModelTier | str = ModelTier.NON_ENFORCED,
    schema: Mapping[str, Any] | None = None,
    template: Any | None = None,
    prompt_override: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    **prompt_kwargs: object,
) -> RenderedStepMessage:
    """Render shared prompt components through the model seam."""

    from arnold_pipelines.megaplan.prompts import PromptComponents, create_prompt_components

    component_metadata = {
        "tier": tier.value if isinstance(tier, ModelTier) else str(tier),
        "worker": worker or agent,
        "model": normalized_model or model,
        "normalized_model": normalized_model or model,
        "validation_step": step,
        **dict(metadata or {}),
    }
    if prompt_override is None:
        components = create_prompt_components(
            agent,
            step,
            state,  # type: ignore[arg-type]
            plan_dir,
            root=root,
            schema=schema,
            template=template,
            metadata=component_metadata,
            **prompt_kwargs,
        )
    else:
        components = PromptComponents(
            prompt=prompt_override,
            schema=dict(schema) if schema is not None else None,
            template=template,
            metadata=component_metadata,
        )
    invocation_metadata = components.to_model_metadata()
    invocation_metadata.update(component_metadata)
    return render_step_message(StepInvocation(kind="model", metadata=invocation_metadata))


def render_compact_review_prompt(
    agent: str,
    step: str,
    state: Mapping[str, Any],
    plan_dir: Path,
    *,
    root: Path | None = None,
    worker: str | None = None,
    model: str | None = None,
    normalized_model: str | None = None,
    tier: ModelTier | str = ModelTier.NON_ENFORCED,
    schema: Mapping[str, Any] | None = None,
    prompt_size_error: dict[str, Any] | None = None,
    pre_check_flags: list[dict[str, Any]] | None = None,
    projection_capabilities: Any | None = None,
) -> RenderedStepMessage:
    """Render a compacted review prompt through the model seam."""

    from arnold_pipelines.megaplan.prompts.review import compact_review_prompt

    compacted_text = compact_review_prompt(
        state,  # type: ignore[arg-type]
        plan_dir,
        root,
        prompt_size_error=prompt_size_error,
        pre_check_flags=pre_check_flags,
        projection_capabilities=projection_capabilities,
    )
    tier_value = tier.value if isinstance(tier, ModelTier) else str(tier)
    return render_step_message(
        StepInvocation(
            kind="model",
            metadata={
                "tier": tier_value,
                "worker": worker or agent,
                "model": normalized_model or model,
                "normalized_model": normalized_model or model,
                "validation_step": step,
                "prompt": compacted_text,
                "prompt_components": compacted_text,
                "schema": dict(schema) if schema is not None else None,
                "projection_capabilities": projection_capabilities,
            },
        )
    )


# --------------------------------------------------------------------------- #
# Capture path (recovery-aware wrapper around the generic core)
# --------------------------------------------------------------------------- #


def capture_step_output(
    invocation: StepInvocation,
    output: Mapping[str, Any] | str,
) -> CaptureOutcome:
    """Capture model output, optionally rescuing malformed JSON via on-disk files.

    Wraps :func:`arnold.pipeline.model_seam.capture_step_output` to add the
    megaplan-specific recovery flow: when ``capture_recovery`` metadata is
    present and either ``prefer_output_file`` is set or strict JSON parsing
    fails, fall through to file-based candidate scanning before bubbling up
    the original error. Everything else (normalization, projection, audit,
    repair) goes through the generic core via registered hooks.
    """

    legacy_payload, capture_sources = _capture_payload(invocation, output)
    legacy_payload = _normalize_native_capture_payload(invocation, legacy_payload)
    legacy_payload = _compatibility_projection(invocation, legacy_payload)
    telemetry = ModelSeamTelemetry.from_invocation(
        invocation,
        terminal_status=TerminalStatus.CAPTURED,
    )
    contract = ContractResult(
        payload={
            "legacy_payload": legacy_payload,
            "telemetry": telemetry.to_json(),
        },
        authority_level="typed",
        provenance=Provenance(
            sources=tuple(capture_sources),
            generator="arnold_pipelines.megaplan.model_seam",
        ),
    )
    try:
        _audit_capture_payload(invocation, legacy_payload, contract)
    except ModelStructuralAuditError:
        if telemetry.tier.enforced:
            raise
        repair_callback = _repair_callback(invocation)
        if repair_callback is None or telemetry.repair_attempt >= 1:
            raise
        repaired_output = repair_callback(legacy_payload, contract)
        repaired_invocation = _repair_invocation(invocation, telemetry.repair_attempt + 1)
        return capture_step_output(repaired_invocation, repaired_output)
    telemetry = replace(telemetry, audit_result=AuditStatus.PASSED)
    contract = replace(
        contract,
        payload={
            "legacy_payload": legacy_payload,
            "telemetry": telemetry.to_json(),
        },
    )
    return CaptureOutcome(
        contract_result=contract,
        legacy_payload=legacy_payload,
        telemetry=telemetry,
    )


def _capture_payload(
    invocation: StepInvocation,
    output: Mapping[str, Any] | str,
) -> tuple[dict[str, Any], tuple[str, ...]]:
    if isinstance(output, Mapping):
        return dict(output), ("model_step_output",)
    if not isinstance(output, str):
        raise TypeError(
            f"model output must be a mapping or JSON string, got {type(output).__name__}"
        )
    recovery = invocation.metadata.get("capture_recovery")
    if isinstance(recovery, Mapping) and bool(recovery.get("prefer_output_file", False)):
        recovered = _recover_payload_for_invocation(invocation, output)
        if recovered is not None:
            return recovered
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        recovered = _recover_payload_for_invocation(invocation, output)
        if recovered is not None:
            return recovered
        raise
    if not isinstance(parsed, Mapping):
        raise TypeError("model output JSON must contain an object")
    return dict(parsed), ("model_step_output",)


# --------------------------------------------------------------------------- #
# Audit + capture schema resolution
# --------------------------------------------------------------------------- #


def audit_step_payload(step: str, payload: Mapping[str, Any]) -> None:
    """Validate a recovered payload against its registered StepContract schema."""

    if step not in STEP_CONTRACTS:
        raise ValueError(f"Unknown Megaplan step contract: {step}")
    invocation = contract_to_invocation(STEP_CONTRACTS[step])
    contract = ContractResult(
        payload={
            "legacy_payload": dict(payload),
            "telemetry": {},
        },
        authority_level="typed",
        provenance=Provenance(
            sources=("recovered_step_output",),
            generator="arnold_pipelines.megaplan.model_seam",
        ),
    )
    _audit_capture_payload(invocation, payload, contract)


def _audit_capture_payload(
    invocation: StepInvocation,
    payload: Mapping[str, Any],
    contract: ContractResult,
) -> None:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get("output_schema")
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        schema = _capture_schema_for_invocation(invocation)
    normalized_payload: Mapping[str, Any] = payload
    if isinstance(schema, Mapping):
        normalized_payload = _normalize_native_capture_payload(invocation, dict(payload))
        result = validate_payload_against_schema(normalized_payload, schema)
    else:
        result = validate_contract_result(contract, _capture_outcome_schema())
    if not result.ok:
        details = "; ".join(
            f"{diagnostic.code} at {diagnostic.payload_pointer or '/'}: {diagnostic.message}"
            for diagnostic in result.diagnostics
        )
        raise ModelStructuralAuditError(details)
    if step == "plan":
        plan_text = normalized_payload.get("plan")
        if isinstance(plan_text, str):
            issues = validate_plan_structure(plan_text)
            if PLAN_STRUCTURE_REQUIRED_STEP_ISSUE in issues:
                raise ModelStructuralAuditError(PLAN_STRUCTURE_REQUIRED_STEP_ISSUE)


def _capture_schema_for_invocation(invocation: StepInvocation) -> Mapping[str, Any] | None:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    schema_key = _CAPTURE_SCHEMA_KEYS_BY_STEP.get(step or "")
    if schema_key is not None:
        schema = SCHEMAS.get(schema_key)
        if isinstance(schema, Mapping):
            capture_schema = deepcopy(schema)
            capture_schema.setdefault("additionalProperties", False)
            return capture_schema
    return None


# --------------------------------------------------------------------------- #
# Step-keyed normalizers + compatibility projection guard
# --------------------------------------------------------------------------- #


def _normalize_native_capture_payload(
    invocation: StepInvocation, payload: dict[str, Any]
) -> dict[str, Any]:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step == "plan":
        return _normalize_plan_capture_payload(payload)
    if step == "review":
        return _normalize_review_capture_payload(payload)
    if step == "execute":
        return _normalize_execute_capture_payload(payload)
    if step == "critique":
        return _normalize_critique_capture_payload(payload)
    if step == "gate":
        return _normalize_gate_capture_payload(payload)
    if step == "critique_evaluator":
        return _normalize_critique_evaluator_capture_payload(payload)
    if step == "prep-distill":
        return _normalize_prep_distill_capture_payload(payload)
    if step != "finalize":
        return payload
    if _finalize_schema_requires_nullable_task_optionals(invocation):
        return payload
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return payload
    normalized = dict(payload)
    normalized["tasks"] = [
        _strip_null_finalize_task_optionals(task) if isinstance(task, Mapping) else task
        for task in tasks
    ]
    return normalized


def _normalize_execute_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from arnold_pipelines.megaplan.execute.status_constants import normalize_execute_task_status

    normalized = dict(payload)
    normalized.pop("batch", None)
    task_updates: list[Any] = []
    for item in normalized.get("task_updates") or []:
        if not isinstance(item, Mapping):
            task_updates.append(item)
            continue
        update = {
            key: item[key]
            for key in (
                "task_id",
                "status",
                "executor_notes",
                "files_changed",
                "commands_run",
                "auto_attributed_files",
                "sections_written",
                "stance",
                "stop_signal",
                "stance_violations",
                "head_sha",
                "code_hash",
            )
            if key in item
        }
        if "task_id" not in update and isinstance(item.get("id"), str):
            update["task_id"] = item["id"]
        if "status" in update and isinstance(update["status"], str):
            raw_status = update["status"]
            canonical = normalize_execute_task_status(raw_status)
            if canonical != raw_status:
                update["status"] = str(canonical)
                existing = update.get("executor_notes", "")
                note_line = f"[harness] status normalized: {raw_status} -> {canonical}"
                if isinstance(existing, str) and existing:
                    update["executor_notes"] = f"{existing}\n{note_line}"
                else:
                    update["executor_notes"] = note_line
        update.setdefault("files_changed", [])
        update.setdefault("commands_run", [])
        update.setdefault("auto_attributed_files", False)
        task_updates.append(update)
    normalized["task_updates"] = task_updates

    acknowledgments: list[Any] = []
    for item in normalized.get("sense_check_acknowledgments") or []:
        if not isinstance(item, Mapping):
            acknowledgments.append(item)
            continue
        acknowledgment = {
            key: item[key]
            for key in ("sense_check_id", "executor_note")
            if key in item
        }
        if "sense_check_id" not in acknowledgment and isinstance(item.get("id"), str):
            acknowledgment["sense_check_id"] = item["id"]
        acknowledgments.append(acknowledgment)
    normalized["sense_check_acknowledgments"] = acknowledgments
    return normalized


def _normalize_prep_distill_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["key_evidence"] = [
        _normalize_prep_key_evidence(item)
        for item in _as_sequence(normalized.get("key_evidence"))
    ]
    normalized["relevant_code"] = [
        _normalize_prep_relevant_code(item)
        for item in _as_sequence(normalized.get("relevant_code"))
    ]
    normalized["test_expectations"] = [
        _normalize_prep_test_expectation(index, item)
        for index, item in enumerate(_as_sequence(normalized.get("test_expectations")), start=1)
    ]
    if "open_questions" in normalized:
        normalized["open_questions"] = [
            _normalize_prep_open_question(item)
            for item in _as_sequence(normalized.get("open_questions"))
        ]
    if "primary_criterion" in normalized:
        primary_criterion = _optional_str(normalized.get("primary_criterion"))
        normalized["primary_criterion"] = primary_criterion or ""
    return normalized


def _normalize_prep_key_evidence(item: Any) -> Any:
    if isinstance(item, str):
        return {"point": item, "source": "prep-distill", "relevance": "medium"}
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    if "point" not in normalized:
        normalized["point"] = _optional_str(
            normalized.get("finding")
            or normalized.get("summary")
            or normalized.get("text")
            or normalized.get("claim")
        ) or ""
    if "source" not in normalized:
        normalized["source"] = _optional_str(
            normalized.get("file")
            or normalized.get("file_path")
            or normalized.get("code_ref")
        ) or "prep-distill"
    normalized["relevance"] = _normalize_prep_relevance(normalized.get("relevance"))
    return {key: normalized[key] for key in ("point", "source", "relevance")}


def _normalize_prep_relevant_code(item: Any) -> Any:
    if isinstance(item, str):
        return {"file_path": item, "why": "Referenced by prep-distill.", "functions": []}
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    file_path = _optional_str(
        normalized.get("file_path")
        or normalized.get("path")
        or normalized.get("file")
        or normalized.get("code_ref")
    ) or ""
    why = _optional_str(
        normalized.get("why")
        or normalized.get("reason")
        or normalized.get("summary")
        or normalized.get("note")
    ) or "Referenced by prep-distill."
    functions = normalized.get("functions")
    if functions is None:
        functions = normalized.get("symbols")
    return {
        "file_path": file_path,
        "why": why,
        "functions": [_optional_str(item) or "" for item in _as_sequence(functions)],
    }


def _normalize_prep_test_expectation(index: int, item: Any) -> Any:
    if isinstance(item, str):
        return {
            "test_id": f"prep-distill-{index}",
            "what_it_checks": item,
            "status": "pass_to_pass",
        }
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    test_id = _optional_str(
        normalized.get("test_id")
        or normalized.get("id")
        or normalized.get("name")
    ) or f"prep-distill-{index}"
    what_it_checks = _optional_str(
        normalized.get("what_it_checks")
        or normalized.get("checks")
        or normalized.get("expectation")
        or normalized.get("description")
    ) or ""
    status = normalized.get("status")
    if status not in {"fail_to_pass", "pass_to_pass"}:
        status = "pass_to_pass"
    return {"test_id": test_id, "what_it_checks": what_it_checks, "status": status}


def _normalize_prep_open_question(item: Any) -> Any:
    if isinstance(item, str):
        return {"severity": "assume_and_proceed", "question": item}
    if not isinstance(item, Mapping):
        return item
    normalized = dict(item)
    classification = _optional_str(normalized.pop("classification", None))
    if normalized.get("severity") not in {"blocking", "assume_and_proceed"}:
        if classification == "blocking":
            normalized["severity"] = "blocking"
        else:
            normalized["severity"] = "assume_and_proceed"
    normalized["question"] = _optional_str(
        normalized.get("question")
        or normalized.get("gap")
        or normalized.get("issue")
        or normalized.get("text")
    ) or ""
    return {
        "severity": normalized["severity"],
        "question": normalized["question"],
        "assumption": _optional_str(normalized.get("assumption")) or "",
    }


def _normalize_prep_relevance(value: Any) -> str:
    if value in {"high", "medium", "low"}:
        return str(value)
    return "medium"


def _finalize_schema_requires_nullable_task_optionals(invocation: StepInvocation) -> bool:
    """Return true when the active finalize schema uses OpenAI strict nullables."""

    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get("output_schema")
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        return False
    try:
        task_schema = schema["properties"]["tasks"]["items"]
        required = set(task_schema.get("required", []))
        properties = task_schema.get("properties", {})
    except (KeyError, TypeError, AttributeError):
        return False
    for field in ("stance", "stop_signal"):
        if field not in required:
            return False
        field_schema = properties.get(field)
        if not isinstance(field_schema, Mapping):
            return False
        field_type = field_schema.get("type")
        if isinstance(field_type, str):
            if field_type != "null":
                return False
        elif isinstance(field_type, list):
            if "null" not in field_type:
                return False
        else:
            return False
    return True


def _normalize_review_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("checks") is None:
        normalized["checks"] = []
    normalized.pop("review_completion_status", None)
    return normalized


def _normalize_critique_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Strip hallucinated extra properties so strict JSON schemas
    # (additionalProperties=false) don't fail on keys like `check_id`
    # or `critique_iteration` that models occasionally invent.
    allowed_top = {"checks", "flags", "verified_flag_ids", "disputed_flag_ids"}
    normalized = {k: v for k, v in payload.items() if k in allowed_top}

    checks = normalized.get("checks")
    if isinstance(checks, list):
        normalized["checks"] = [
            _normalize_critique_check(check) if isinstance(check, Mapping) else check
            for check in checks
        ]

    flags = normalized.get("flags")
    if isinstance(flags, list):
        normalized["flags"] = [
            _normalize_critique_flag(flag) if isinstance(flag, Mapping) else flag
            for flag in flags
        ]

    normalized.setdefault("verified_flag_ids", [])
    normalized.setdefault("disputed_flag_ids", [])
    return normalized


def _normalize_critique_check(check: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"id", "question", "findings"}
    normalized = {k: v for k, v in check.items() if k in allowed}
    findings = normalized.get("findings")
    if isinstance(findings, list):
        normalized["findings"] = [
            _normalize_critique_finding(f) if isinstance(f, Mapping) else f
            for f in findings
        ]
    return normalized


def _normalize_critique_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"detail", "flagged"}
    return {k: v for k, v in finding.items() if k in allowed}


def _normalize_critique_flag(flag: Mapping[str, Any]) -> dict[str, Any]:
    # Models sometimes emit `severity`/`status` instead of the schema's
    # `severity_hint`.  Accept `severity` as an alias and drop other extras.
    allowed = {"id", "concern", "category", "severity_hint", "severity", "evidence"}
    normalized = {k: v for k, v in flag.items() if k in allowed}
    severity_hint = normalized.get("severity_hint")
    if severity_hint is None and "severity" in normalized:
        severity_hint = normalized.pop("severity")
        normalized["severity_hint"] = severity_hint
    if severity_hint in {"high", "significant", "major", "critical"}:
        normalized["severity_hint"] = "likely-significant"
    elif severity_hint in {"low", "minor", "trivial", "cosmetic"}:
        normalized["severity_hint"] = "likely-minor"
    elif severity_hint in {"medium", "moderate", "unknown", None, ""}:
        normalized["severity_hint"] = "uncertain"
    return normalized


def _normalize_gate_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        key: value
        for key, value in payload.items()
        if key in _GATE_CAPTURE_SCHEMA_TOP_LEVEL_FIELDS
    }

    resolutions = [
        item
        for item in normalized.get("flag_resolutions", [])
        if isinstance(item, Mapping)
    ]
    accept_tradeoff_resolutions = [
        item for item in resolutions if item.get("action") == "accept_tradeoff"
    ]

    tradeoffs: list[Any] = []
    for index, item in enumerate(_as_sequence(normalized.get("accepted_tradeoffs"))):
        resolution = (
            accept_tradeoff_resolutions[index]
            if index < len(accept_tradeoff_resolutions)
            else {}
        )
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            tradeoffs.append(
                {
                    "flag_id": _optional_str(resolution.get("flag_id")) or f"accepted-tradeoff-{index + 1}",
                    "concern": text,
                    "subsystem": "",
                    "rationale": _optional_str(resolution.get("rationale")) or "",
                }
            )
            continue
        if not isinstance(item, Mapping):
            tradeoffs.append(item)
            continue
        tradeoff = dict(item)
        tradeoff_text = _optional_str(tradeoff.pop("tradeoff", None))
        if "flag_id" not in tradeoff:
            tradeoff["flag_id"] = _optional_str(resolution.get("flag_id")) or f"accepted-tradeoff-{index + 1}"
        if "concern" not in tradeoff:
            tradeoff["concern"] = (
                _optional_str(tradeoff.get("concern_brief"))
                or tradeoff_text
                or _optional_str(resolution.get("rationale"))
                or ""
            )
        if "subsystem" not in tradeoff:
            tradeoff["subsystem"] = ""
        if "rationale" not in tradeoff:
            tradeoff["rationale"] = (
                _optional_str(tradeoff.get("rationale_brief"))
                or _optional_str(resolution.get("rationale"))
                or tradeoff_text
                or ""
            )
        tradeoffs.append(
            {
                key: tradeoff[key]
                for key in ("flag_id", "concern", "subsystem", "rationale")
                if key in tradeoff
            }
        )
    normalized["accepted_tradeoffs"] = tradeoffs
    return normalized


def _normalize_critique_evaluator_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "flag_verifications" in normalized:
        normalized["flag_verifications"] = _normalize_optional_list_marker(
            normalized["flag_verifications"],
        )
    selections = normalized.get("selections")
    if isinstance(selections, list):
        normalized["selections"] = [
            _normalize_critique_evaluator_selection(selection)
            if isinstance(selection, Mapping)
            else selection
            for selection in selections
        ]
    return normalized


def _normalize_plan_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize structured provider plan output to the canonical plan schema."""

    normalized: dict[str, Any] = {}
    if isinstance(payload.get("plan"), str):
        normalized["plan"] = payload["plan"]
        extracted = _extract_plan_markdown_metadata(payload["plan"])
        normalized["questions"] = _normalize_plan_questions(
            payload.get("questions", extracted.get("questions"))
        )
        normalized["success_criteria"] = _normalize_plan_success_criteria(
            payload.get("success_criteria", extracted.get("success_criteria"))
        )
        normalized["assumptions"] = _normalize_plan_assumptions(
            payload.get("assumptions", extracted.get("assumptions"))
        )
        # Pass through changed_surfaces and test_blast_radius if present
        changed = payload.get("changed_surfaces", extracted.get("changed_surfaces"))
        if isinstance(changed, list):
            normalized["changed_surfaces"] = [
                str(s) for s in changed if isinstance(s, str) and s.strip()
            ]
        blast = payload.get("test_blast_radius", extracted.get("test_blast_radius"))
        if isinstance(blast, dict):
            normalized["test_blast_radius"] = blast
        return normalized

    parts: list[str] = []
    title = _optional_str(payload.get("title"))
    if title:
        parts.append(f"# {title}")
    overview = _optional_str(payload.get("overview"))
    if overview:
        parts.append("## Overview")
        parts.append(overview)
    steps = payload.get("steps")
    if isinstance(steps, list):
        step_number = 1
        for step in steps:
            if isinstance(step, Mapping):
                step_title = _optional_str(step.get("title") or step.get("name"))
                step_desc = _optional_str(step.get("description") or step.get("details"))
                if step_title:
                    if re.match(r"(?i)^step\s+\d+:", step_title):
                        parts.append(f"### {step_title}")
                    else:
                        parts.append(f"### Step {step_number}: {step_title}")
                    step_number += 1
                if step_desc:
                    parts.append(step_desc)
                substeps = step.get("substeps") or step.get("instructions")
                if isinstance(substeps, list):
                    for sub in substeps:
                        if isinstance(sub, Mapping):
                            sub_text = _optional_str(
                                sub.get("instruction") or sub.get("text")
                            )
                            if sub_text:
                                parts.append(f"- {sub_text}")
                        elif isinstance(sub, str):
                            parts.append(f"- {sub}")
            elif isinstance(step, str):
                parts.append(f"- {step}")
    plan_text = payload.get("plan_text") or payload.get("markdown") or "\n\n".join(parts)
    if not isinstance(plan_text, str):
        plan_text = "\n\n".join(parts)
    extracted = _extract_plan_markdown_metadata(plan_text)
    normalized["plan"] = plan_text
    normalized["questions"] = _normalize_plan_questions(
        payload.get("questions", extracted.get("questions"))
    )
    normalized["success_criteria"] = _normalize_plan_success_criteria(
        payload.get("success_criteria", extracted.get("success_criteria"))
    )
    normalized["assumptions"] = _normalize_plan_assumptions(
        payload.get("assumptions", extracted.get("assumptions"))
    )
    # Pass through changed_surfaces and test_blast_radius if present
    changed = payload.get("changed_surfaces", extracted.get("changed_surfaces"))
    if isinstance(changed, list):
        normalized["changed_surfaces"] = [
            str(s) for s in changed if isinstance(s, str) and s.strip()
        ]
    blast = payload.get("test_blast_radius", extracted.get("test_blast_radius"))
    if isinstance(blast, dict):
        normalized["test_blast_radius"] = blast
    return normalized


def coerce_plan_markdown_payload(plan_text: str) -> dict[str, Any]:
    """Wrap raw plan markdown in the canonical plan payload shape."""

    return _normalize_plan_capture_payload({"plan": plan_text})


def _extract_plan_markdown_metadata(plan_text: str) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    questions_block = _extract_plan_markdown_section(plan_text, "Questions")
    if questions_block:
        extracted["questions"] = _extract_markdown_list_values(questions_block)
    assumptions_block = _extract_plan_markdown_section(plan_text, "Assumptions")
    if assumptions_block:
        extracted["assumptions"] = _extract_markdown_list_values(assumptions_block)
    success_block = _extract_plan_markdown_section(plan_text, "Success Criteria")
    success_value = _extract_markdown_json_value(success_block) if success_block else None
    if isinstance(success_value, list):
        extracted["success_criteria"] = success_value
    elif isinstance(success_value, dict):
        extracted["success_criteria"] = [success_value]
    changed_block = _extract_plan_markdown_section(plan_text, "Changed Surfaces")
    changed_value = _extract_markdown_json_value(changed_block) if changed_block else None
    if isinstance(changed_value, list):
        extracted["changed_surfaces"] = changed_value
    else:
        changed_list = _extract_markdown_list_values(changed_block or "")
        if changed_list:
            extracted["changed_surfaces"] = changed_list
    blast_block = _extract_plan_markdown_section(plan_text, "Test Blast Radius")
    blast_value = _extract_markdown_json_value(blast_block) if blast_block else None
    if isinstance(blast_value, dict):
        extracted["test_blast_radius"] = blast_value
    return extracted


def _extract_plan_markdown_section(plan_text: str, heading: str) -> str | None:
    match = re.search(
        rf"(?ms)^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s+|\Z)",
        plan_text,
    )
    if match is None:
        return None
    body = match.group(1).strip()
    return body or None


def _extract_markdown_list_values(section_text: str) -> list[str]:
    values: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(("-", "*")) and not re.match(r"^\d+\.\s+", stripped):
            continue
        item = re.sub(r"^(?:[-*]\s+|\d+\.\s+)", "", stripped).strip()
        if item:
            values.append(item)
    return values


def _extract_markdown_json_value(section_text: str) -> Any | None:
    text = section_text.strip()
    if not text:
        return None

    fenced_blocks = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    for block in fenced_blocks:
        try:
            return json.loads(block.strip())
        except json.JSONDecodeError:
            continue

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return parsed
    return None


def _normalize_plan_questions(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, Mapping):
                for key in ("question", "text", "q", "value"):
                    q = _optional_str(item.get(key))
                    if q:
                        result.append(q)
                        break
                else:
                    result.append(str(item))
            else:
                result.append(str(item))
        return result
    return []


def _normalize_plan_success_criteria(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, Mapping):
                criterion = _optional_str(
                    item.get("criterion") or item.get("name") or item.get("description")
                )
                priority = _optional_str(item.get("priority")) or "should"
                if priority not in ("must", "should", "info"):
                    priority = "should"
                requires = item.get("requires")
                if not isinstance(requires, list):
                    requires = []
                if priority == "must" and not requires:
                    requires = ["run_tests"]
                if criterion:
                    result.append(
                        {
                            "criterion": criterion,
                            "priority": priority,
                            "requires": requires,
                        }
                    )
            elif isinstance(item, str):
                result.append({"criterion": item, "priority": "should", "requires": []})
        return result
    return []


def _normalize_plan_assumptions(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, Mapping):
                for key in ("assumption", "text", "value"):
                    assumption = _optional_str(item.get(key))
                    if assumption:
                        result.append(assumption)
                        break
                else:
                    result.append(str(item))
            else:
                result.append(str(item))
        return result
    return []


def _normalize_optional_list_marker(value: Any) -> Any:
    """Normalize common empty markers for optional array fields.

    Some providers emit ``null``, ``"N/A"``, or a tiny explanatory object for
    optional arrays even when the prompt says to omit the field. Treat only
    unambiguously empty/not-applicable markers as an empty list; preserve real
    malformed content so structural validation still rejects it.
    """

    if value is None:
        return []
    if isinstance(value, str):
        marker = value.strip().lower().replace("_", " ").replace("-", " ")
        if marker in {"", "none", "null", "n/a", "na", "not applicable"}:
            return []
    if isinstance(value, Mapping):
        if not value:
            return []
        for key in ("flag_verifications", "verifications", "items", "entries"):
            wrapped = value.get(key)
            if isinstance(wrapped, list):
                return wrapped
        meaningful_keys = {"flag_id", "lens", "outcome", "rationale"}
        if meaningful_keys.isdisjoint(value):
            marker_keys = {
                "not_applicable",
                "not applicable",
                "reason",
                "why",
                "rationale_note",
                "note",
            }
            if set(value).issubset(marker_keys):
                return []
    return value


def _normalize_critique_evaluator_selection(selection: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(selection)
    if normalized.get("area") is None:
        normalized["area"] = ""
    if normalized.get("check_id") != "other":
        normalized.pop("why", None)
    return normalized


def _strip_null_finalize_task_optionals(task: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(task)
    for optional_object_field in ("stance", "stop_signal"):
        if normalized.get(optional_object_field) is None:
            normalized.pop(optional_object_field, None)
    return normalized


def _compatibility_projection(invocation: StepInvocation, payload: dict[str, Any]) -> dict[str, Any]:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step is None:
        return payload
    mode = _compatibility_mode_for_step(step)
    if mode is CompatibilityMode.NATIVE:
        return payload
    raise AssertionError(
        "Phase 5 deletion invariant violated: "
        f"_compatibility_projection received non-native step {step!r} "
        f"with mode {mode.value!r}. Run assert_all_compatibility_modes_native() "
        "before deleting shared legacy helpers."
    )


# --------------------------------------------------------------------------- #
# Recovery (megaplan-keyed, depends on step contract registry)
# --------------------------------------------------------------------------- #


def _recovery_payload_looks_like_step(step: str, payload: Mapping[str, Any]) -> bool:
    schema_key = _CAPTURE_SCHEMA_KEYS_BY_STEP.get(step)
    required: set[str] = set()
    if schema_key is not None:
        schema = SCHEMAS.get(schema_key)
        if isinstance(schema, Mapping):
            required = set(schema.get("required", ()))
    if required.intersection(payload):
        return True
    if step == "execute" and {"task_updates", "sense_check_acknowledgments"}.intersection(payload):
        return True
    return False


def _recovery_critique_completeness_score(item: _RecoveredPayload) -> tuple[int, int]:
    checks = item.payload.get("checks", [])
    if not isinstance(checks, list):
        return (0, 0)
    completed_checks = 0
    total_findings = 0
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        findings = check.get("findings", [])
        if not isinstance(findings, list) or not findings:
            continue
        completed_checks += 1
        total_findings += len(findings)
    return (completed_checks, total_findings)


def _recovery_plan_structure_score(item: _RecoveredPayload) -> tuple[int, int, int]:
    plan_text = item.payload.get("plan")
    if not isinstance(plan_text, str):
        return (0, 0, 0)
    issues = validate_plan_structure(plan_text)
    has_required_steps = PLAN_STRUCTURE_REQUIRED_STEP_ISSUE not in issues
    # Prefer structurally complete plans, then plans with fewer secondary
    # warnings, then richer plan text over terse status summaries.
    return (1 if has_required_steps else 0, -len(issues), len(plan_text))


def _recover_payload_with_provenance(
    step: str,
    *,
    plan_dir: Path,
    output_path: Path,
    raw: str,
    prefer_output_file: bool = True,
) -> _RecoveredPayload | None:
    file_payload = None
    template_payload = None
    candidate_payloads: list[_RecoveredPayload] = []
    try:
        file_payload = _parse_recovery_json_file(output_path)
    except (FileNotFoundError, TypeError, ValueError):
        try:
            file_raw = output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
        else:
            candidate_payloads.extend(
                _RecoveredPayload(payload=candidate, provenance="output_file_recovered")
                for candidate in _extract_recovery_json_candidates(file_raw)
            )
    fallback_names = {
        "critique": "critique_output.json",
        "review": "review_output.json",
    }
    fallback_name = fallback_names.get(step, f"{step}_output.json")
    fallback_path = plan_dir / fallback_name
    if fallback_path != output_path and fallback_path.exists():
        try:
            template_payload = _parse_recovery_json_file(fallback_path)
        except (FileNotFoundError, TypeError, ValueError):
            try:
                fallback_raw = fallback_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
            else:
                candidate_payloads.extend(
                    _RecoveredPayload(payload=candidate, provenance="template_file_recovered")
                    for candidate in _extract_recovery_json_candidates(fallback_raw)
                )
    if file_payload is None and template_payload is not None:
        file_payload = template_payload
        template_payload = None
    output_is_template_file = output_path == fallback_path
    output_is_single_critique_check = (
        step == "critique"
        and output_path.name.startswith("critique_check_")
        and output_path.suffix == ".json"
    )
    validation_errors: list[str] = []
    if (
        prefer_output_file
        and file_payload is not None
        and (step != "critique" or output_is_template_file or output_is_single_critique_check)
    ):
        preferred_payload = dict(file_payload)
        try:
            audit_step_payload(step, preferred_payload)
        except ModelStructuralAuditError as error:
            if _recovery_payload_looks_like_step(step, preferred_payload):
                candidate_payloads.insert(
                    0,
                    _RecoveredPayload(payload=file_payload, provenance="output_file"),
                )
                validation_errors.append(error.details)
        else:
            if (
                step == "plan"
                and _recovery_plan_structure_score(
                    _RecoveredPayload(payload=preferred_payload, provenance="output_file")
                )[0]
                == 0
            ):
                candidate_payloads.insert(
                    0,
                    _RecoveredPayload(payload=preferred_payload, provenance="output_file"),
                )
            else:
                return _RecoveredPayload(payload=preferred_payload, provenance="output_file")
    raw_candidates = _extract_recovery_json_candidates(raw)
    if file_payload is not None:
        if not any(candidate.payload is file_payload for candidate in candidate_payloads):
            candidate_payloads.insert(
                0,
                _RecoveredPayload(payload=file_payload, provenance="output_file"),
            )
    if template_payload is not None:
        insert_at = 1 if file_payload is not None else 0
        candidate_payloads.insert(
            insert_at,
            _RecoveredPayload(payload=template_payload, provenance="template_file"),
        )
    candidate_payloads.extend(
        _RecoveredPayload(payload=candidate, provenance="raw_output")
        for candidate in raw_candidates
    )
    valid_payloads: list[_RecoveredPayload] = []
    for candidate in candidate_payloads:
        payload = dict(candidate.payload)
        try:
            audit_step_payload(step, payload)
        except ModelStructuralAuditError as error:
            if _recovery_payload_looks_like_step(step, payload):
                validation_errors.append(error.details)
            continue
        valid_payloads.append(_RecoveredPayload(payload=payload, provenance=candidate.provenance))
    if not valid_payloads:
        if validation_errors:
            unique_errors = list(dict.fromkeys(validation_errors))
            raise ModelStructuralAuditError(
                f"Recovered JSON object for {step} failed validation: "
                + " | ".join(unique_errors),
            )
        return None
    if step == "critique" and len(valid_payloads) > 1:
        return max(valid_payloads, key=_recovery_critique_completeness_score)
    if step == "plan" and len(valid_payloads) > 1:
        return max(valid_payloads, key=_recovery_plan_structure_score)
    return valid_payloads[0]


def _recover_payload_for_invocation(
    invocation: StepInvocation, raw: str
) -> tuple[dict[str, Any], tuple[str, ...]] | None:
    recovery = invocation.metadata.get("capture_recovery")
    if not isinstance(recovery, Mapping):
        return None
    step = _optional_str(recovery.get("step") or invocation.metadata.get("validation_step"))
    plan_dir = recovery.get("plan_dir")
    output_path = recovery.get("output_path")
    if step is None or plan_dir is None or output_path is None:
        return None
    recovered = _recover_payload_with_provenance(
        step,
        plan_dir=Path(plan_dir),
        output_path=Path(output_path),
        raw=raw,
        prefer_output_file=bool(recovery.get("prefer_output_file", True)),
    )
    if recovered is None:
        return None
    return dict(recovered.payload), (
        "model_step_output",
        f"codex_recovery:{recovered.provenance}",
    )


# --------------------------------------------------------------------------- #
# Compatibility-mode bookkeeping
# --------------------------------------------------------------------------- #


_CAPTURE_SCHEMA_KEYS_BY_STEP: dict[str, str] = build_capture_schema_keys_by_step()
_COMPATIBILITY_MODE_BY_STEP: dict[str, CompatibilityMode] = build_compatibility_mode_by_step()


def schema_audits_step_payload(step: str | None) -> bool:
    return _compatibility_mode_for_step(step) is CompatibilityMode.NATIVE


def _compatibility_mode_for_step(step: str | None) -> CompatibilityMode:
    if step is None:
        return CompatibilityMode.LEGACY
    return _COMPATIBILITY_MODE_BY_STEP.get(step, CompatibilityMode.NATIVE)


def _remaining_legacy_compatibility_steps() -> tuple[str, ...]:
    return tuple(
        sorted(
            step
            for step, mode in _COMPATIBILITY_MODE_BY_STEP.items()
            if mode is CompatibilityMode.LEGACY
        )
    )


def assert_all_compatibility_modes_native() -> None:
    remaining = _remaining_legacy_compatibility_steps()
    if not remaining:
        return
    quoted_steps = ", ".join(f'"{step}"' for step in remaining)
    raise AssertionError(
        "Phase 5 deletion guard blocked: legacy compatibility steps remain in "
        f"_COMPATIBILITY_MODE_BY_STEP: {quoted_steps}. Migrate these steps to "
        "CompatibilityMode.NATIVE before deleting shared legacy helpers."
    )


# --------------------------------------------------------------------------- #
# Hook registration (generic registry sees megaplan step-keyed behavior)
# --------------------------------------------------------------------------- #


def _register_hooks() -> None:
    register_native_normalizer("plan", _normalize_plan_capture_payload)
    register_native_normalizer("review", _normalize_review_capture_payload)
    register_native_normalizer("execute", _normalize_execute_capture_payload)
    register_native_normalizer("gate", _normalize_gate_capture_payload)
    register_native_normalizer("critique", _normalize_critique_capture_payload)
    register_native_normalizer(
        "critique_evaluator", _normalize_critique_evaluator_capture_payload
    )
    register_native_normalizer("prep-distill", _normalize_prep_distill_capture_payload)

    def _finalize_normalizer(payload: Mapping[str, Any]) -> dict[str, Any]:
        # Generic hook signature is payload-only; schema-aware nullable handling
        # is invocation-keyed and stays in megaplan's own capture path. From the
        # generic side we conservatively strip nulls so non-strict schemas pass.
        result = dict(payload)
        tasks = result.get("tasks")
        if isinstance(tasks, list):
            result["tasks"] = [
                _strip_null_finalize_task_optionals(task) if isinstance(task, Mapping) else task
                for task in tasks
            ]
        return result

    register_native_normalizer("finalize", _finalize_normalizer)

    def _projection_guard(invocation: StepInvocation, payload: Mapping[str, Any]) -> dict[str, Any]:
        return _compatibility_projection(invocation, dict(payload))

    for step in _COMPATIBILITY_MODE_BY_STEP:
        register_compatibility_projection(step, _projection_guard)

    register_capture_schema_resolver(_capture_schema_for_invocation)
    register_recovery_step_shape_check(_recovery_payload_looks_like_step)


_register_hooks()


__all__ = [
    "AuditStatus",
    "BudgetStatus",
    "CaptureOutcome",
    "CompatibilityMode",
    "ModelBudget",
    "ModelBudgetDefaults",
    "ModelBudgetError",
    "ModelFamily",
    "ModelSeamTelemetry",
    "ModelStepInvocationAdapter",
    "ModelStructuralAuditError",
    "ModelTier",
    "RenderedStepMessage",
    "StepInvocation",
    "StepInvocationAdapterRegistry",
    "TerminalStatus",
    "TierMetadata",
    "audit_step_payload",
    "budget_model_input",
    "capture_step_output",
    "classify_model_family",
    "assert_all_compatibility_modes_native",
    "install_model_step_adapter",
    "render_compact_review_prompt",
    "render_prompt_for_dispatch",
    "render_step_message",
    "schema_audits_step_payload",
]
