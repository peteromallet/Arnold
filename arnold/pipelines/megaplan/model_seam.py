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
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from arnold.pipeline import (
    ContractResult,
    Provenance,
    StepInvocation,
    StepInvocationAdapterRegistry,
    validate_contract_result,
    validate_payload_against_schema,
)
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

from arnold.pipelines.megaplan.schemas import SCHEMAS
from arnold.pipelines.megaplan._compatibility import CompatibilityMode  # re-export
from arnold.pipelines.megaplan.step_contracts import (
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

    from arnold.pipelines.megaplan.prompts import PromptComponents, create_prompt_components

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

    from arnold.pipelines.megaplan.prompts.review import compact_review_prompt

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
            generator="arnold.pipelines.megaplan.model_seam",
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

    invocation = contract_to_invocation(STEP_CONTRACTS[step])
    contract = ContractResult(
        payload={
            "legacy_payload": dict(payload),
            "telemetry": {},
        },
        authority_level="typed",
        provenance=Provenance(
            sources=("recovered_step_output",),
            generator="arnold.pipelines.megaplan.model_seam",
        ),
    )
    _audit_capture_payload(invocation, payload, contract)


def _audit_capture_payload(
    invocation: StepInvocation,
    payload: Mapping[str, Any],
    contract: ContractResult,
) -> None:
    schema = invocation.metadata.get("capture_schema") or invocation.metadata.get("output_schema")
    if not isinstance(schema, Mapping):
        schema = invocation.metadata.get("schema")
    if not isinstance(schema, Mapping):
        schema = _capture_schema_for_invocation(invocation)
    if isinstance(schema, Mapping):
        payload = _normalize_native_capture_payload(invocation, dict(payload))
        result = validate_payload_against_schema(payload, schema)
    else:
        result = validate_contract_result(contract, _capture_outcome_schema())
    if result.ok:
        return
    details = "; ".join(
        f"{diagnostic.code} at {diagnostic.payload_pointer or '/'}: {diagnostic.message}"
        for diagnostic in result.diagnostics
    )
    raise ModelStructuralAuditError(details)


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
    if step == "review":
        return _normalize_review_capture_payload(payload)
    if step == "execute":
        return _normalize_execute_capture_payload(payload)
    if step == "critique":
        return _normalize_critique_capture_payload(payload)
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
    normalized = dict(payload)
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
            )
            if key in item
        }
        if "task_id" not in update and isinstance(item.get("id"), str):
            update["task_id"] = item["id"]
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
    normalized = dict(payload)
    flags = normalized.get("flags")
    if isinstance(flags, list):
        normalized["flags"] = [
            _normalize_critique_flag(flag) if isinstance(flag, Mapping) else flag
            for flag in flags
        ]
    return normalized


def _normalize_critique_flag(flag: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(flag)
    severity_hint = normalized.get("severity_hint")
    if severity_hint in {"high", "significant", "major", "critical"}:
        normalized["severity_hint"] = "likely-significant"
    elif severity_hint in {"low", "minor", "trivial", "cosmetic"}:
        normalized["severity_hint"] = "likely-minor"
    elif severity_hint in {"medium", "moderate", "unknown", None, ""}:
        normalized["severity_hint"] = "uncertain"
    return normalized


def _normalize_critique_evaluator_capture_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("flag_verifications") is None:
        normalized["flag_verifications"] = []
    selections = normalized.get("selections")
    if isinstance(selections, list):
        normalized["selections"] = [
            _normalize_critique_evaluator_selection(selection)
            if isinstance(selection, Mapping)
            else selection
            for selection in selections
        ]
    return normalized


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
    register_native_normalizer("review", _normalize_review_capture_payload)
    register_native_normalizer("execute", _normalize_execute_capture_payload)
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
