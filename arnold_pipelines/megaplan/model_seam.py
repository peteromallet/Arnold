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

import hashlib
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

from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.schema_projection import (
    project_schema_owned_fields,
    schema_mapping_at_path,
    schema_owned_field_drops,
    schema_property_names,
)
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
    metadata: Mapping[str, Any] | None = None,
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
                **dict(metadata or {}),
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
    legacy_payload, projection_receipts = _apply_exact_duplicate_field_projections(
        invocation,
        legacy_payload,
    )
    capture_sources = (
        *capture_sources,
        *(
            "model_schema_projection:"
            + json.dumps(receipt, sort_keys=True, separators=(",", ":"))
            for receipt in projection_receipts
        ),
    )
    legacy_payload = _normalize_capture_payload_with_contract(
        invocation,
        legacy_payload,
    )
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
        _audit_capture_payload(
            invocation,
            legacy_payload,
            contract,
            already_normalized=True,
        )
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


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _apply_exact_duplicate_field_projections(
    invocation: StepInvocation,
    payload: Mapping[str, Any],
) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    """Repair only schema-declared, byte-identical duplicate projections.

    Plan and revise deliberately expose ``changed_surfaces`` twice: once as a
    top-level model field and once inside ``test_blast_radius``.  Some providers
    emit the complete top-level value but omit the required nested duplicate.
    That shape error is mechanically repairable without semantic inference,
    but only when the authoritative schema declares both fields with identical
    schemas and the source value was actually emitted by the model.

    Every projection produces a deterministic provenance receipt.  All other
    omissions remain untouched and fail the ordinary model schema audit.
    """

    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    if step not in {"plan", "revise"}:
        return dict(payload), ()

    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get(
        "output_schema"
    )
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        schema = _capture_schema_for_invocation(invocation)
    if not isinstance(schema, Mapping):
        return dict(payload), ()

    properties = schema.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}
    source_schema = properties.get("changed_surfaces")
    blast_schema = properties.get("test_blast_radius")
    blast_properties = (
        blast_schema.get("properties")
        if isinstance(blast_schema, Mapping)
        else None
    )
    target_schema = (
        blast_properties.get("changed_surfaces")
        if isinstance(blast_properties, Mapping)
        else None
    )
    blast_required = (
        blast_schema.get("required")
        if isinstance(blast_schema, Mapping)
        else None
    )
    if (
        not isinstance(source_schema, Mapping)
        or not isinstance(target_schema, Mapping)
        or not isinstance(blast_required, list)
        or "changed_surfaces" not in blast_required
        or _canonical_json_bytes(source_schema) != _canonical_json_bytes(target_schema)
    ):
        return dict(payload), ()

    source_value = payload.get("changed_surfaces")
    blast_value = payload.get("test_blast_radius")
    if (
        not isinstance(source_value, list)
        or not isinstance(blast_value, Mapping)
        or "changed_surfaces" in blast_value
    ):
        return dict(payload), ()

    projected = dict(payload)
    projected_blast = dict(blast_value)
    projected_blast["changed_surfaces"] = deepcopy(source_value)
    if _canonical_json_bytes(projected_blast["changed_surfaces"]) != _canonical_json_bytes(
        source_value
    ):
        raise ModelStructuralAuditError(
            "exact duplicate-field projection changed model-emitted bytes"
        )
    projected["test_blast_radius"] = projected_blast

    schema_sha256 = hashlib.sha256(_canonical_json_bytes(source_schema)).hexdigest()
    value_sha256 = hashlib.sha256(_canonical_json_bytes(source_value)).hexdigest()
    receipt = {
        "kind": "exact_duplicate_field_projection",
        "source_pointer": "/changed_surfaces",
        "target_pointer": "/test_blast_radius/changed_surfaces",
        "schema_sha256": schema_sha256,
        "value_sha256": value_sha256,
    }
    return projected, (receipt,)


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
    *,
    already_normalized: bool = False,
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
        if step == "gate":
            # Use the exact recursively strict contract materialized for the
            # worker.  Closing objects alone is insufficient: OpenAI-strict
            # materialization also promotes every declared property to
            # ``required``.  Every gate reader must therefore validate the
            # same shape the producer was instructed to emit.
            schema = strict_schema(schema)
        normalized_payload = (
            payload
            if already_normalized
            else _normalize_capture_payload_with_contract(invocation, payload)
        )
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


def _normalize_capture_payload_with_contract(
    invocation: StepInvocation,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Normalize once and reject any undeclared schema-owned field loss."""

    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get(
        "output_schema"
    )
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        schema = _capture_schema_for_invocation(invocation)
    normalized = _normalize_native_capture_payload(invocation, dict(payload))
    if not isinstance(schema, Mapping):
        return normalized
    dropped = tuple(
        pointer
        for pointer in schema_owned_field_drops(payload, normalized, schema)
        if not _schema_owned_drop_is_declared(step, pointer)
    )
    if dropped:
        raise ModelStructuralAuditError(
            "schema_owned_field_dropped during capture normalization at "
            + ", ".join(dropped)
        )
    return normalized


def _capture_schema_for_invocation(invocation: StepInvocation) -> Mapping[str, Any] | None:
    step = _optional_str(
        invocation.metadata.get("compatibility_validation_step")
        or invocation.metadata.get("validation_step")
    )
    schema_key = _CAPTURE_SCHEMA_KEYS_BY_STEP.get(step or "")
    if schema_key is not None:
        schema = SCHEMAS.get(schema_key)
        if isinstance(schema, Mapping):
            capture_schema = (
                strict_schema(deepcopy(schema))
                if step == "gate"
                else deepcopy(schema)
            )
            capture_schema.setdefault("additionalProperties", False)
            return capture_schema
    return None


def _schema_owned_drop_is_declared(step: str | None, pointer: str) -> bool:
    """Return whether a lossy compatibility transform is explicitly owned."""

    if step != "finalize":
        return False
    # OpenAI-strict finalize schemas carry nullable task stance objects. The
    # authored/stored schema treats them as optional objects, so the adapter
    # deliberately removes null transport placeholders before local audit.
    parts = pointer.strip("/").split("/")
    return (
        len(parts) == 3
        and parts[0] == "tasks"
        and parts[1].isdigit()
        and parts[2] in {"stance", "stop_signal"}
    )


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
    if step == "tiebreaker_researcher":
        return _normalize_tiebreaker_researcher_capture_payload(payload)
    if step == "tiebreaker_challenger":
        return _normalize_tiebreaker_challenger_capture_payload(payload)
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
            for key in execute_capture_task_field_names()
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
        acknowledgment = project_schema_owned_fields(
            item,
            _execute_capture_sense_check_schema(),
            contract="execute sense-check capture normalization",
        )
        if "sense_check_id" not in acknowledgment and isinstance(item.get("id"), str):
            acknowledgment["sense_check_id"] = item["id"]
        acknowledgments.append(acknowledgment)
    normalized["sense_check_acknowledgments"] = acknowledgments
    return normalized


_EXECUTE_TASK_CAPTURE_EXTENSION_FIELDS: frozenset[str] = frozenset(
    {
        # These fields are handler evidence attached before or immediately
        # after structural capture. They are not model-schema fields, but they
        # are part of the durable execute envelope and must survive the adapter.
        "evidence_files",
        "sections_written",
        "stance",
        "stop_signal",
        "stance_violations",
        "head_sha",
        "code_hash",
    }
)


def _execute_capture_task_schema() -> Mapping[str, Any]:
    return schema_mapping_at_path(
        SCHEMAS["execution_batch_relaxed.json"],
        ("properties", "task_updates", "items"),
        contract="execute task capture schema",
    )


def _execute_capture_sense_check_schema() -> Mapping[str, Any]:
    return schema_mapping_at_path(
        SCHEMAS["execution_batch_relaxed.json"],
        ("properties", "sense_check_acknowledgments", "items"),
        contract="execute sense-check capture schema",
    )


def execute_capture_task_field_names() -> frozenset[str]:
    """Return schema fields plus documented execute-envelope extensions."""

    return schema_property_names(
        _execute_capture_task_schema(),
        contract="execute task capture normalization",
    ) | _EXECUTE_TASK_CAPTURE_EXTENSION_FIELDS


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
    normalized = project_schema_owned_fields(
        item,
        schema_mapping_at_path(
            SCHEMAS["prep.json"],
            ("properties", "key_evidence", "items"),
            contract="prep key-evidence capture schema",
        ),
        contract="prep key-evidence capture normalization",
    )
    if "point" not in normalized:
        normalized["point"] = _optional_str(
            item.get("finding")
            or item.get("summary")
            or item.get("text")
            or item.get("claim")
        ) or ""
    if "source" not in normalized:
        normalized["source"] = _optional_str(
            item.get("file")
            or item.get("file_path")
            or item.get("code_ref")
        ) or "prep-distill"
    normalized["relevance"] = _normalize_prep_relevance(item.get("relevance"))
    return normalized


def _normalize_prep_relevant_code(item: Any) -> Any:
    if isinstance(item, str):
        return {"file_path": item, "why": "Referenced by prep-distill.", "functions": []}
    if not isinstance(item, Mapping):
        return item
    normalized = project_schema_owned_fields(
        item,
        schema_mapping_at_path(
            SCHEMAS["prep.json"],
            ("properties", "relevant_code", "items"),
            contract="prep relevant-code capture schema",
        ),
        contract="prep relevant-code capture normalization",
    )
    file_path = _optional_str(
        item.get("file_path")
        or item.get("path")
        or item.get("file")
        or item.get("code_ref")
    ) or ""
    why = _optional_str(
        item.get("why")
        or item.get("reason")
        or item.get("summary")
        or item.get("note")
    ) or "Referenced by prep-distill."
    functions = item.get("functions")
    if functions is None:
        functions = item.get("symbols")
    normalized.update(
        {
            "file_path": file_path,
            "why": why,
            "functions": [_optional_str(item) or "" for item in _as_sequence(functions)],
        }
    )
    return normalized


def _normalize_prep_test_expectation(index: int, item: Any) -> Any:
    if isinstance(item, str):
        return {
            "test_id": f"prep-distill-{index}",
            "what_it_checks": item,
            "status": "pass_to_pass",
        }
    if not isinstance(item, Mapping):
        return item
    normalized = project_schema_owned_fields(
        item,
        schema_mapping_at_path(
            SCHEMAS["prep.json"],
            ("properties", "test_expectations", "items"),
            contract="prep test-expectation capture schema",
        ),
        contract="prep test-expectation capture normalization",
    )
    test_id = _optional_str(
        item.get("test_id")
        or item.get("id")
        or item.get("name")
    ) or f"prep-distill-{index}"
    what_it_checks = _optional_str(
        item.get("what_it_checks")
        or item.get("checks")
        or item.get("expectation")
        or item.get("description")
    ) or ""
    status = item.get("status")
    if status not in {"fail_to_pass", "pass_to_pass"}:
        status = "pass_to_pass"
    normalized.update(
        {"test_id": test_id, "what_it_checks": what_it_checks, "status": status}
    )
    return normalized


def _normalize_prep_open_question(item: Any) -> Any:
    if isinstance(item, str):
        return {"severity": "assume_and_proceed", "question": item}
    if not isinstance(item, Mapping):
        return item
    normalized = project_schema_owned_fields(
        item,
        schema_mapping_at_path(
            SCHEMAS["prep.json"],
            ("properties", "open_questions", "items"),
            contract="prep open-question capture schema",
        ),
        contract="prep open-question capture normalization",
    )
    classification = _optional_str(item.get("classification"))
    if item.get("severity") not in {"blocking", "assume_and_proceed"}:
        if classification == "blocking":
            normalized["severity"] = "blocking"
        else:
            normalized["severity"] = "assume_and_proceed"
    else:
        normalized["severity"] = item["severity"]
    normalized["question"] = _optional_str(
        item.get("question")
        or item.get("gap")
        or item.get("issue")
        or item.get("text")
    ) or ""
    normalized["assumption"] = _optional_str(item.get("assumption")) or ""
    return normalized


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
    normalized = project_schema_owned_fields(
        payload,
        SCHEMAS["critique.json"],
        contract="critique capture normalization",
    )

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
    normalized = project_schema_owned_fields(
        check,
        schema_mapping_at_path(
            SCHEMAS["critique.json"],
            ("properties", "checks", "items"),
            contract="critique check capture schema",
        ),
        contract="critique check capture normalization",
    )
    findings = normalized.get("findings")
    if isinstance(findings, list):
        normalized["findings"] = [
            _normalize_critique_finding(f) if isinstance(f, Mapping) else f
            for f in findings
        ]
    return normalized


def _normalize_critique_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    return project_schema_owned_fields(
        finding,
        schema_mapping_at_path(
            SCHEMAS["critique.json"],
            ("properties", "checks", "items", "properties", "findings", "items"),
            contract="critique finding capture schema",
        ),
        contract="critique finding capture normalization",
    )


def _normalize_critique_flag(flag: Mapping[str, Any]) -> dict[str, Any]:
    # Models sometimes emit `severity`/`status` instead of the schema's
    # `severity_hint`.  Accept `severity` as an alias and drop other extras.
    flag_schema = schema_mapping_at_path(
        SCHEMAS["critique.json"],
        ("properties", "flags", "items"),
        contract="critique flag capture schema",
    )
    normalized = project_schema_owned_fields(
        flag,
        flag_schema,
        contract="critique flag capture normalization",
    )
    alias_severity = flag.get("severity")
    severity_hint = normalized.get("severity_hint")
    if severity_hint is None and alias_severity is not None:
        severity_hint = alias_severity
        normalized["severity_hint"] = severity_hint
    if severity_hint in {"high", "significant", "major", "critical"}:
        normalized["severity_hint"] = "likely-significant"
    elif severity_hint in {"low", "minor", "trivial", "cosmetic"}:
        normalized["severity_hint"] = "likely-minor"
    elif severity_hint in {"medium", "moderate", "unknown", None, ""}:
        normalized["severity_hint"] = "uncertain"
    return normalized


def _normalize_gate_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    # Keep capture lossless: validation must see both missing required fields
    # and undeclared fields. Projecting before validation would turn a schema
    # mismatch into silent data loss. Schema-owned projection is reserved for
    # already-validated persistence boundaries.
    return dict(payload)


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


def _normalize_tiebreaker_researcher_capture_payload(
    payload: dict[str, Any]
) -> dict[str, Any]:
    """Resilient GLM/hermes tiebreaker-researcher normalizer.

    GLM investigates correctly but its field naming is highly variable across
    runs (``type``/``files``/``paths``, ``question``/``decision_question``,
    ``least_sure``/``least_sure_about``/``what_im_least_sure_about``, pick as
    bare string or object with ``chosen_option``/``option_name``/``choice``...).
    Rather than chase each spelling, this normalizer maps by alias family and
    coerces ``preliminary_pick`` from any shape, so the strict
    ``additionalProperties=false`` schema passes while preserving substance.
    """
    raw = payload if isinstance(payload, Mapping) else {}

    # ── alias families (first non-empty hit wins) ──
    def _first(d, aliases, default=None):
        if not isinstance(d, Mapping):
            return default
        for a in aliases:
            v = d.get(a)
            if v not in (None, "", [], {}):
                return v
        return default

    QUESTION_ALIASES = ("question", "decision_question", "decision", "the_question", "prompt")
    ETYPE_ALIASES = ("evidence_type", "type", "kind", "category")
    FILEPATHS_ALIASES = ("file_paths", "files", "paths", "file_path", "file", "locations", "sources")
    QUOTE_ALIASES = ("quote", "snippet", "text", "excerpt", "code")
    CLAIM_ALIASES = ("claim", "statement", "assertion", "finding", "summary")
    PICK_OPTION_ALIASES = ("option_name", "chosen_option", "choice", "pick", "selected_option", "recommended_option", "recommendation", "answer", "option", "selected", "verdict")
    PICK_RATIONALE_ALIASES = ("rationale", "reason", "reasoning", "justification", "why", "explanation")
    PICK_UNSURE_ALIASES = ("what_im_least_sure_about", "least_sure_about", "least_sure", "not_sure_about", "uncertainties", "caveats", "uncertainty", "doubts", "reservations")

    # ── evidence: rebuild each item from aliases ──
    evidence_out = []
    for item in (raw.get("evidence") or []):
        if not isinstance(item, Mapping):
            continue
        etype = _first(item, ETYPE_ALIASES, "code")
        if etype not in ("code", "measurement", "pattern", "doc"):
            etype_l = str(etype).lower()
            etype = "code" if "code" in etype_l else "measurement" if "meas" in etype_l else "pattern" if "pattern" in etype_l else "doc" if "doc" in etype_l else "code"
        fp = _first(item, FILEPATHS_ALIASES, [])
        if isinstance(fp, str):
            fp = [fp] if fp else []
        elif not isinstance(fp, list):
            fp = []
        evidence_out.append({
            "claim": str(_first(item, CLAIM_ALIASES, "")),
            "evidence_type": etype,
            "file_paths": [str(x) for x in fp],
            "quote": str(_first(item, QUOTE_ALIASES, "")),
        })

    # ── options: rebuild each from aliases ──
    options_out = []
    for opt in (raw.get("options") or []):
        if not isinstance(opt, Mapping):
            continue
        desc = _first(opt, ("description", "desc", "summary", "what"), "")
        assum = _first(opt, ("assumptions", "assumption", "assumes"), [])
        if isinstance(assum, str):
            assum = [assum] if assum else []
        costs = _first(opt, ("costs", "cost", "tradeoffs", "downsides", "drawbacks"), [])
        if isinstance(costs, str):
            costs = [costs] if costs else []
        options_out.append({
            "name": str(_first(opt, ("name", "option", "option_name", "label", "title"), "")),
            "description": str(desc),
            "assumptions": [str(x) for x in assum] if isinstance(assum, list) else [],
            "costs": [str(x) for x in costs] if isinstance(costs, list) else [],
        })

    # ── preliminary_pick: coerce from any shape ──
    # When GLM hoists rationale/unsure to the top level (common when it emits
    # pick as a bare string), fall back to the top-level raw payload.
    pick_raw = raw.get("preliminary_pick")
    if isinstance(pick_raw, Mapping):
        pick_src = pick_raw
    elif isinstance(pick_raw, str):
        pick_src = {"chosen_option": pick_raw}
    else:
        pick_src = {}
    pick_option = _first(pick_src, PICK_OPTION_ALIASES, "") or ""
    pick_rationale = _first(pick_src, PICK_RATIONALE_ALIASES, "") or _first(raw, PICK_RATIONALE_ALIASES, "") or ""
    pick_unsure = _first(pick_src, PICK_UNSURE_ALIASES, "") or _first(raw, PICK_UNSURE_ALIASES, "") or ""
    preliminary_pick = {
        "option_name": str(pick_option),
        "rationale": str(pick_rationale),
        "what_im_least_sure_about": str(pick_unsure),
    }

    return {
        "question": str(_first(raw, QUESTION_ALIASES, "")),
        "evidence": evidence_out,
        "options": options_out,
        "preliminary_pick": preliminary_pick,
    }


def _normalize_tiebreaker_challenger_capture_payload(
    payload: dict[str, Any]
) -> dict[str, Any]:
    """Normalize GLM/hermes tiebreaker-challenger output to the strict schema.

    Mirrors the researcher normalizer: GLM's analysis is sound but its field
    shapes drift from ``tiebreaker_challenger.json`` (extra properties, missing
    required sub-fields, bare strings where objects are required). Project to
    schema-owned fields at every strict node and backfill required defaults so
    ``additionalProperties=false`` passes without losing the substance.
    """
    schema = SCHEMAS["tiebreaker_challenger.json"]
    normalized = project_schema_owned_fields(
        payload,
        schema,
        contract="tiebreaker challenger capture normalization",
    )

    def _project_list_items(value, schema_path, required_defaults):
        if not isinstance(value, list):
            return []
        item_schema = schema_mapping_at_path(
            schema, schema_path, contract="tiebreaker challenger item schema"
        )
        out = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            projected = project_schema_owned_fields(
                dict(item),
                item_schema,
                contract="tiebreaker challenger item normalization",
            )
            for req_key, default in required_defaults.items():
                projected.setdefault(req_key, default)
            out.append(projected)
        return out

    normalized["missing_options"] = _project_list_items(
        normalized.get("missing_options"),
        ("properties", "missing_options", "items"),
        {"name": "", "description": "", "why_missed": ""},
    )
    normalized["hard_cases"] = _project_list_items(
        normalized.get("hard_cases"),
        ("properties", "hard_cases", "items"),
        {"scenario": "", "which_option_breaks": "", "severity": "uncertain"},
    )
    reframings = normalized.get("reframings")
    normalized["reframings"] = [
        r for r in reframings if isinstance(r, str)
    ] if isinstance(reframings, list) else []

    # counter_recommendation is a required strict object; accept bare string
    # (option name) and backfill required fields.
    counter = normalized.get("counter_recommendation")
    if isinstance(counter, str):
        counter = {"option_name": counter}
    if not isinstance(counter, Mapping):
        counter = {}
    counter = project_schema_owned_fields(
        dict(counter),
        schema_mapping_at_path(
            schema,
            ("properties", "counter_recommendation"),
            contract="tiebreaker challenger counter schema",
        ),
        contract="tiebreaker challenger counter normalization",
    )
    agrees = counter.get("agrees_with_researcher")
    if not isinstance(agrees, bool):
        counter["agrees_with_researcher"] = False
    counter.setdefault("option_name", "")
    counter.setdefault("rationale", "")
    normalized["counter_recommendation"] = counter

    # GLM sometimes emits these required string fields as lists/objects/nulls;
    # coerce any non-string to a string (join lists, stringify objects, "" for null).
    def _coerce_str(value):
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "; ".join(str(x) for x in value if x not in (None, ""))
        if value is None:
            return ""
        return str(value)
    normalized["measurements_vs_assumptions"] = _coerce_str(normalized.get("measurements_vs_assumptions"))
    normalized["aging_analysis"] = _coerce_str(normalized.get("aging_analysis"))
    return normalized


def _normalize_plan_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize structured provider plan output to the canonical plan schema."""

    normalized: dict[str, Any] = project_schema_owned_fields(
        payload,
        SCHEMAS["plan.json"],
        contract="plan capture normalization",
    )
    # Prefer full step-bearing markdown over a provider summary.
    _plan_candidate = payload.get("plan_markdown")
    if isinstance(_plan_candidate, str) and "### Step " in _plan_candidate:
        _plan_source = _plan_candidate
    elif isinstance(payload.get("plan"), str):
        _plan_source = payload["plan"]
    else:
        _plan_source = None
    if isinstance(_plan_source, str):
        normalized["plan"] = _plan_source
        extracted = _extract_plan_markdown_metadata(_plan_source)
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
    plan_text = (
        payload.get("plan_markdown")
        or payload.get("plan_text")
        or payload.get("markdown")
        or "\n\n".join(parts)
    )
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
    register_native_normalizer(
        "tiebreaker_researcher", _normalize_tiebreaker_researcher_capture_payload
    )
    register_native_normalizer(
        "tiebreaker_challenger", _normalize_tiebreaker_challenger_capture_payload
    )

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
