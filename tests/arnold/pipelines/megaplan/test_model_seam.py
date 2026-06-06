from __future__ import annotations

import json

import pytest

import arnold.pipelines.megaplan.model_seam as model_seam
from arnold.pipeline import (
    ContractResult,
    StepInvocation,
    StepInvocationAdapterRegistry,
    validate_payload_against_schema,
)
from arnold.pipelines.megaplan.model_seam import (
    AuditStatus,
    BudgetStatus,
    CaptureOutcome,
    ModelBudgetError,
    ModelFamily,
    ModelSeamTelemetry,
    ModelStepInvocationAdapter,
    ModelTier,
    RenderedStepMessage,
    TerminalStatus,
    TierMetadata,
    budget_model_input,
    capture_step_output,
    classify_model_family,
    install_model_step_adapter,
    render_prompt_for_dispatch,
    render_step_message,
)
from arnold.pipelines.megaplan.schemas import SCHEMAS
from arnold.pipelines.megaplan.prompts import PromptComponents


def test_tier_metadata_defaults_to_non_enforced() -> None:
    invocation = StepInvocation(kind="model", metadata={})

    tier = TierMetadata.from_invocation(invocation)

    assert tier == TierMetadata(tier=ModelTier.NON_ENFORCED, enforced=False)
    assert tier.to_json() == {
        "tier": "non_enforced",
        "enforced": False,
        "worker": None,
        "model": None,
        "provider": None,
    }


def test_tier_metadata_carries_enforced_worker_model_provider() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.4",
            "provider": "openai",
        },
    )

    tier = TierMetadata.from_invocation(invocation)

    assert tier.tier is ModelTier.ENFORCED
    assert tier.enforced is True
    assert tier.worker == "codex"
    assert tier.model == "gpt-5.4"
    assert tier.provider == "openai"


def test_telemetry_serializes_stable_machine_fields() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "hermes",
            "model": "deepseek-v3",
            "provider": "fireworks",
            "degraded_reason": "unknown_model_family",
            "tokenizer_source": "fallback_estimate",
            "budget_result": "degraded_fallback",
            "audit_result": "failed",
            "repair_attempt": 1,
        },
    )

    telemetry = ModelSeamTelemetry.from_invocation(
        invocation,
        terminal_status=TerminalStatus.CAPTURED,
    )

    assert telemetry.to_json() == {
        "tier": {
            "tier": "enforced",
            "enforced": True,
            "worker": "hermes",
            "model": "deepseek-v3",
            "provider": "fireworks",
        },
        "degraded_reason": "unknown_model_family",
        "tokenizer_source": "fallback_estimate",
        "budget_result": "degraded_fallback",
        "audit_result": "failed",
        "repair_attempt": 1,
        "terminal_status": "captured",
    }


def test_registry_can_invoke_model_step_adapter() -> None:
    registry = StepInvocationAdapterRegistry()
    install_model_step_adapter(registry)
    invocation = StepInvocation(
        kind="model",
        metadata={
            "prompt": "Summarize the plan.",
            "tier": "enforced",
            "worker": "codex",
        },
    )

    rendered = registry.invoke(invocation)

    assert isinstance(rendered, RenderedStepMessage)
    assert rendered.text == "Summarize the plan."
    assert rendered.metadata["worker"] == "codex"
    assert rendered.telemetry.tier.tier is ModelTier.ENFORCED


def test_model_step_adapter_invokes_render_step_message() -> None:
    adapter = ModelStepInvocationAdapter()
    invocation = StepInvocation(kind="model", metadata={"message": "hello"})

    rendered = adapter.invoke(invocation)

    assert rendered.text == "hello"
    assert rendered.telemetry.terminal_status is TerminalStatus.RENDERED


def test_render_prompt_for_dispatch_accepts_union_schema_types(tmp_path) -> None:
    rendered = render_prompt_for_dispatch(
        "codex",
        "plan",
        {"config": {"mode": "code"}},
        tmp_path,
        schema={
            "type": "object",
            "properties": {
                "items": {"type": ["array", "null"]},
                "name": {"type": ["null", "string"]},
                "enabled": {"type": ["boolean", "null"]},
            },
        },
        prompt_override="Return structured data.",
    )

    assert rendered.template == {
        "items": [],
        "name": "...",
        "enabled": False,
    }


def test_capture_step_output_preserves_legacy_payload_and_typed_contract() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "shannon",
            "budget_result": BudgetStatus.WITHIN_BUDGET.value,
            "audit_result": AuditStatus.PASSED.value,
        },
    )
    legacy_payload = {
        "task_id": "T3",
        "status": "done",
        "extra": {"kept": True},
    }

    outcome = capture_step_output(invocation, legacy_payload)

    assert isinstance(outcome, CaptureOutcome)
    assert outcome.legacy_payload == legacy_payload
    assert outcome.contract_result.authority_level == "typed"
    assert outcome.contract_result.payload["legacy_payload"] == legacy_payload
    assert outcome.contract_result.payload["telemetry"]["tier"]["worker"] == "shannon"
    assert outcome.contract_result.payload["telemetry"]["terminal_status"] == "captured"

    rehydrated = ContractResult.from_json(outcome.contract_result.to_json())
    assert rehydrated.payload["legacy_payload"] == legacy_payload


def test_capture_step_output_skips_compatibility_projection_for_native_execute() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "compatibility_validation_step": "execute",
        },
    )

    outcome = capture_step_output(
        invocation,
        {
            "task_updates": [{"id": "T7", "status": "done"}],
            "sense_check_acknowledgments": [],
        },
    )

    assert outcome.legacy_payload == {
        "task_updates": [{"id": "T7", "status": "done"}],
        "sense_check_acknowledgments": [],
    }
    assert outcome.telemetry.audit_result is AuditStatus.PASSED
    assert outcome.contract_result.payload["telemetry"]["audit_result"] == "passed"


def test_capture_schema_for_invocation_maps_named_steps_to_approved_schemas() -> None:
    expected = {
        "execute": "execution_batch_relaxed.json",
        "finalize": "finalize.json",
        "critique": "critique.json",
        "review": "review.json",
        "gate": "gate.json",
    }

    for step, schema_key in expected.items():
        invocation = StepInvocation(
            kind="model",
            metadata={"validation_step": step},
        )

        capture_schema = model_seam._capture_schema_for_invocation(invocation)

        assert capture_schema is not None
        assert capture_schema["properties"] == SCHEMAS[schema_key]["properties"]
        assert capture_schema["required"] == SCHEMAS[schema_key]["required"]
        assert capture_schema.get("additionalProperties") is False


def test_execute_batch_relaxed_schema_preserves_batch_subset_without_duplicating_properties() -> None:
    relaxed = SCHEMAS["execution_batch_relaxed.json"]
    full = SCHEMAS["execution.json"]

    assert relaxed["required"] == ["task_updates", "sense_check_acknowledgments"]
    assert relaxed["properties"]["output"] == full["properties"]["output"]
    assert relaxed["properties"]["task_updates"]["items"]["properties"] == full["properties"]["task_updates"]["items"]["properties"]
    assert relaxed["properties"]["task_updates"]["items"]["required"] == []
    assert relaxed["properties"]["sense_check_acknowledgments"]["items"]["properties"] == full["properties"]["sense_check_acknowledgments"]["items"]["properties"]
    assert relaxed["properties"]["sense_check_acknowledgments"]["items"]["required"] == []


def test_capture_step_output_uses_execute_batch_relaxed_schema_for_present_field_types() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "compatibility_validation_step": "execute",
        },
    )

    try:
        capture_step_output(
            invocation,
            {
                "task_updates": "not-a-list",
                "sense_check_acknowledgments": [],
            },
        )
    except ValueError as exc:
        assert "type_mismatch" in str(exc)
    else:
        raise AssertionError("wrong-typed execute batch fields must fail structural audit")


def test_capture_step_output_uses_finalize_schema_for_wrong_typed_named_payload() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "finalize",
        },
    )

    try:
        capture_step_output(
            invocation,
            {
                "tasks": "not-a-list",
                "watch_items": [],
                "sense_checks": [],
                "user_actions": [],
                "meta_commentary": "",
                "validation": {
                    "plan_steps_covered": [],
                    "orphan_tasks": [],
                    "completeness_notes": "",
                    "coverage_complete": True,
                },
            },
        )
    except ValueError as exc:
        assert "type_mismatch" in str(exc)
    else:
        raise AssertionError("finalize capture must reject wrong-typed named payloads")


def test_capture_step_output_uses_review_schema_to_reject_hallucinated_named_keys() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "review",
        },
    )

    try:
        capture_step_output(
            invocation,
            {
                "review_verdict": "approved",
                "criteria": [],
                "issues": [],
                "rework_items": [],
                "summary": "Reviewed successfully.",
                "task_verdicts": [],
                "sense_check_verdicts": [],
                "hallucinated_extra": True,
            },
        )
    except ValueError as exc:
        assert "additional_property" in str(exc)
    else:
        raise AssertionError("review capture must reject hallucinated named payload keys")


def test_capture_step_output_uses_critique_schema_for_missing_required_fields() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "critique",
        },
    )

    try:
        capture_step_output(
            invocation,
            {
                "checks": [],
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
        )
    except ValueError as exc:
        assert "flags" in str(exc)
    else:
        raise AssertionError("critique capture must reject missing required fields")


def test_capture_step_output_uses_critique_schema_for_wrong_typed_named_payload() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "validation_step": "critique",
        },
    )

    try:
        capture_step_output(
            invocation,
            {
                "checks": [],
                "flags": "not-a-list",
                "verified_flag_ids": [],
                "disputed_flag_ids": [],
            },
        )
    except ValueError as exc:
        assert "type_mismatch" in str(exc)
    else:
        raise AssertionError("critique capture must reject wrong-typed named payloads")


def test_capture_step_output_rejects_wrong_typed_payload_under_structural_audit() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "capture_schema": {
                "type": "object",
                "required": ["task_updates"],
                "additionalProperties": False,
                "properties": {"task_updates": {"type": "array"}},
            }
        },
    )

    try:
        capture_step_output(invocation, {"task_updates": "not-a-list"})
    except ValueError as exc:
        assert "type_mismatch" in str(exc)
    else:
        raise AssertionError("wrong-typed model output must fail structural audit")


def test_capture_step_output_rejects_hallucinated_keys_under_structural_audit() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "capture_schema": {
                "type": "object",
                "required": ["output"],
                "additionalProperties": False,
                "properties": {"output": {"type": "string"}},
            }
        },
    )

    try:
        capture_step_output(invocation, {"output": "ok", "confidence": 0.99})
    except ValueError as exc:
        assert "additional_property" in str(exc)
    else:
        raise AssertionError("hallucinated model output keys must fail structural audit")


def test_capture_step_output_projects_codex_recovery_provenance(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    output_path = tmp_path / "codex-o.json"
    recovered_payload = {
        "task_updates": [{"task_id": "T8", "status": "done"}],
        "sense_check_acknowledgments": [],
    }
    (plan_dir / "execute_output.json").write_text(
        json.dumps(recovered_payload),
        encoding="utf-8",
    )
    invocation = StepInvocation(
        kind="model",
        metadata={
            "capture_recovery": {
                "step": "execute",
                "plan_dir": str(plan_dir),
                "output_path": str(output_path),
            },
            "capture_schema": {
                "type": "object",
                "required": ["task_updates", "sense_check_acknowledgments"],
                "additionalProperties": False,
                "properties": {
                    "task_updates": {"type": "array"},
                    "sense_check_acknowledgments": {"type": "array"},
                },
            },
        },
    )

    outcome = capture_step_output(invocation, "{not json")

    assert outcome.legacy_payload == recovered_payload
    assert outcome.contract_result.provenance.sources == (
        "model_step_output",
        "codex_recovery:output_file",
    )


def test_non_enforced_capture_attempts_exactly_one_envelope_repair() -> None:
    repair_inputs = []

    def repair(payload, contract):
        repair_inputs.append((dict(payload), contract.payload["telemetry"]["repair_attempt"]))
        return {"output": "repaired"}

    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "non_enforced",
            "envelope_repair_callback": repair,
            "capture_schema": {
                "type": "object",
                "required": ["output"],
                "additionalProperties": False,
                "properties": {"output": {"type": "string"}},
            },
        },
    )

    outcome = capture_step_output(invocation, {"wrong": "shape"})

    assert outcome.legacy_payload == {"output": "repaired"}
    assert outcome.telemetry.repair_attempt == 1
    assert len(repair_inputs) == 1


def test_non_enforced_capture_repair_is_bounded_before_terminal_failure() -> None:
    attempts = 0

    def repair(_payload, _contract):
        nonlocal attempts
        attempts += 1
        return {"wrong": "still-shape"}

    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "non_enforced",
            "envelope_repair_callback": repair,
            "capture_schema": {
                "type": "object",
                "required": ["output"],
                "additionalProperties": False,
                "properties": {"output": {"type": "string"}},
            },
        },
    )

    try:
        capture_step_output(invocation, {"wrong": "shape"})
    except ValueError as exc:
        assert "worker_structural_audit_failed" in str(exc)
    else:
        raise AssertionError("non-enforced repair must stop after one re-ask")

    assert attempts == 1


def test_m0b_structural_validator_subset_limits_are_documented_by_behavior() -> None:
    schema = {
        "type": "object",
        "required": ["name", "items", "mode"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string"},
            "items": {"type": "array", "items": {"type": "object", "properties": {"ok": {"type": "boolean"}}}},
            "mode": {"enum": ["fast", "safe"]},
            "tag": {"const": "m0b"},
            "fallback": {"anyOf": [{"type": "null"}, {"type": "string"}]},
            "choice": {"oneOf": [{"const": "a"}, {"const": "b"}]},
        },
    }

    valid = {
        "name": "capture",
        "items": [{"ok": True}],
        "mode": "safe",
        "tag": "m0b",
        "fallback": None,
        "choice": "a",
    }
    wrong_type = {**valid, "items": "not-an-array"}
    hallucinated_key = {**valid, "confidence": 0.99}

    assert validate_payload_against_schema(valid, schema).ok
    assert any(
        diagnostic.code == "type_mismatch"
        for diagnostic in validate_payload_against_schema(wrong_type, schema).diagnostics
    )
    assert any(
        diagnostic.code == "additional_property"
        for diagnostic in validate_payload_against_schema(hallucinated_key, schema).diagnostics
    )


def test_model_family_classification_rejects_raw_provider_prefixed_names() -> None:
    for raw_model in (
        "openrouter:gpt-5.5",
        "deepseek:deepseek-v3",
        "anthropic/claude-sonnet-4-6",
        "openai/gpt-5.4",
    ):
        try:
            classify_model_family(raw_model)
        except ModelBudgetError as exc:
            assert "provider-prefixed" in str(exc)
        else:
            raise AssertionError(f"{raw_model!r} should be rejected before classification")


def test_model_family_classification_separates_claude_and_codex() -> None:
    assert classify_model_family("gpt-5.4") is ModelFamily.CODEX
    assert classify_model_family("gpt-5-codex") is ModelFamily.CODEX
    assert classify_model_family("claude-sonnet-4-6") is ModelFamily.CLAUDE

    codex_budget = budget_model_input(
        "hello",
        model="gpt-5.4",
        tier=ModelTier.ENFORCED,
    )
    claude_budget = budget_model_input(
        "hello",
        model="claude-sonnet-4-6",
        tier=ModelTier.ENFORCED,
    )

    assert codex_budget.tokenizer_source == "tiktoken:o200k_base"
    assert claude_budget.tokenizer_source == "claude_conservative_estimate"


def test_render_step_message_applies_static_budget_and_request_override() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "gpt-5.4",
            "prompt": "x" * 60,
            "tier": "enforced",
            "max_input_tokens": 10,
        },
    )

    try:
        render_step_message(invocation)
    except ModelBudgetError as exc:
        assert "budget exceeded" in str(exc)
    else:
        raise AssertionError("render_step_message should fail before dispatch on budget overflow")


def test_non_enforced_unknown_family_uses_degraded_fallback_telemetry() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "unknown-local-model",
            "prompt": "small prompt",
            "tier": "non_enforced",
        },
    )

    rendered = render_step_message(invocation)

    assert rendered.budget is not None
    assert rendered.budget.family is None
    assert rendered.budget.budget_result is BudgetStatus.DEGRADED_FALLBACK
    assert rendered.telemetry.budget_result is BudgetStatus.DEGRADED_FALLBACK
    assert rendered.telemetry.degraded_reason == "unknown_model_family"
    assert rendered.telemetry.tokenizer_source == "byte_estimate:fallback"


def test_enforced_unknown_family_fails_closed() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "unknown-local-model",
            "prompt": "small prompt",
            "tier": "enforced",
        },
    )

    try:
        render_step_message(invocation)
    except ModelBudgetError as exc:
        assert "unknown normalized model family" in str(exc)
    else:
        raise AssertionError("enforced unknown families must fail closed")


def test_render_step_message_budgets_all_text_sections_before_dispatch() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "gpt-5.4",
            "tier": "enforced",
            "system": "system rules",
            "history": [{"role": "user", "content": "h" * 30}],
            "prompt": "p" * 30,
            "prefill": "prefill",
            "tool_schemas": [{"name": "terminal", "description": "run commands"}],
            "schema": {"type": "object", "required": ["output"]},
            "template": {"output": "..."},
            "descriptor": "execute batch descriptor",
            "max_input_tokens": 20,
        },
    )

    try:
        render_step_message(invocation)
    except ModelBudgetError as exc:
        assert "model input budget exceeded" in str(exc)
    else:
        raise AssertionError("all text-bearing fields must count toward the pre-dispatch budget")


def test_combined_history_overflow_counts_each_entry() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "claude-sonnet-4-6",
            "tier": "enforced",
            "history": [
                {"role": "user", "content": "x" * 35},
                {"role": "assistant", "content": "y" * 35},
            ],
            "prompt": "small final prompt",
            "max_input_tokens": 30,
        },
    )

    try:
        render_step_message(invocation)
    except ModelBudgetError as exc:
        assert "model input budget exceeded" in str(exc)
    else:
        raise AssertionError("combined history must not bypass the budget")


def test_oversized_media_fails_out_of_band_budget() -> None:
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "gpt-5.4",
            "tier": "enforced",
            "prompt": "describe the image",
            "media": [{"mime_type": "image/png", "bytes": 2048, "descriptor": "large diagram"}],
            "max_media_bytes": 1024,
        },
    )

    try:
        render_step_message(invocation)
    except ModelBudgetError as exc:
        assert "media budget exceeded" in str(exc)
    else:
        raise AssertionError("oversized media must fail before provider dispatch")


def test_budget_failure_terminates_before_dispatch_stub_is_called() -> None:
    dispatch_calls: list[RenderedStepMessage] = []
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "gpt-5.4",
            "tier": "enforced",
            "prompt": "x" * 100,
            "max_input_tokens": 5,
        },
    )

    def predispatch_then_dispatch(step_invocation: StepInvocation) -> None:
        rendered = render_step_message(step_invocation)
        dispatch_calls.append(rendered)

    try:
        predispatch_then_dispatch(invocation)
    except ModelBudgetError as exc:
        assert "model input budget exceeded" in str(exc)
    else:
        raise AssertionError("budget failure should terminate the pre-dispatch path")

    assert dispatch_calls == []


def test_render_step_message_exposes_worker_facing_payload_fields() -> None:
    schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "files_changed": {"type": "array"},
        },
    }
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "gpt-5.4",
            "tier": "enforced",
            "system": "system rules",
            "history": [{"role": "assistant", "content": "prior answer"}],
            "prompt": "produce the final JSON",
            "schema": schema,
        },
    )

    rendered = render_step_message(invocation)

    assert rendered.text == "produce the final JSON"
    assert rendered.prompt == "produce the final JSON"
    assert rendered.messages == (
        {"role": "assistant", "content": "prior answer"},
        {"role": "user", "content": "produce the final JSON"},
    )
    assert rendered.stdin is not None
    assert '"messages"' in rendered.stdin
    assert rendered.schema == schema
    assert rendered.template == {"output": "...", "files_changed": []}
    assert rendered.envelope_examples == ({"output": "...", "files_changed": []},)
    assert rendered.to_json()["prompt"] == "produce the final JSON"


# ---------------------------------------------------------------------------
# T1 characterization: inventory of _normalize_worker_payload and
# validate_payload call sites that pass through the model-seam
# _compatibility_projection() chokepoint.
#
# After m5 migration, _compatibility_projection() must skip
# _normalize_worker_payload() and validate_payload() for schema-audited native
# sites (finalize, critique, review, gate, execute) while preserving legacy
# behavior for the long tail until m6.
# ---------------------------------------------------------------------------

_MIGRATED_SITES: tuple[str, ...] = ("finalize", "critique", "review", "gate", "execute")

# Long-tail sites that are NOT migrated in m5 — the compatibility path
# must keep working for them until m6.
_LONG_TAIL_SITES: tuple[str, ...] = (
    "plan", "revise", "prep", "loop_plan", "loop_execute",
    "tiebreaker_challenger", "feedback",
)


def test_schema_audited_native_steps_explicitly_skip_legacy_compatibility_projection() -> None:
    payload = {
        "task_updates": [{"id": "T7", "status": "completed"}],
        "sense_check_acknowledgments": [],
    }

    for step in _MIGRATED_SITES:
        invocation = StepInvocation(
            kind="model",
            metadata={"compatibility_validation_step": step},
        )

        projected = model_seam._compatibility_projection(invocation, dict(payload))

        assert model_seam._compatibility_mode_for_step(step) is model_seam.CompatibilityMode.NATIVE
        assert model_seam._capture_schema_for_invocation(invocation) is not None
        assert projected == payload


def test_compatibility_projection_native_guard_precedes_legacy_normalize_import() -> None:
    import ast
    from pathlib import Path

    seam_path = (
        Path(__file__).resolve().parents[4]
        / "arnold/pipelines/megaplan/model_seam.py"
    )
    source = seam_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    compatibility_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_compatibility_projection"
    )
    native_guard_index = next(
        index
        for index, node in enumerate(compatibility_fn.body)
        if (
            isinstance(node, ast.If)
            and ast.get_source_segment(source, node.test) == (
                "_compatibility_mode_for_step(step) is CompatibilityMode.NATIVE"
            )
        )
    )
    import_index = next(
        index
        for index, node in enumerate(compatibility_fn.body)
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "arnold.pipelines.megaplan.workers._impl"
        )
    )

    native_guard = compatibility_fn.body[native_guard_index]
    assert isinstance(native_guard, ast.If)
    assert len(native_guard.body) == 1
    assert isinstance(native_guard.body[0], ast.Return)
    assert isinstance(native_guard.body[0].value, ast.Name)
    assert native_guard.body[0].value.id == "payload"
    assert native_guard_index < import_index, (
        "The native compatibility guard must return before the legacy "
        "_normalize_worker_payload import is reached."
    )


def test_audit_step_payload_reuses_native_schema_authority() -> None:
    payload = {
        "task_updates": [{"task_id": "T7", "status": "done"}],
        "sense_check_acknowledgments": [{"sense_check_id": "SC7", "executor_note": "ok"}],
    }

    model_seam.audit_step_payload("execute", payload)
    assert model_seam.schema_audits_step_payload("execute") is True
    assert model_seam.schema_audits_step_payload("plan") is False

    model_seam.audit_step_payload(
        "execute",
        {
            "task_updates": [{"id": "T7", "status": "completed"}],
            "sense_check_acknowledgments": [],
        },
    )

    with pytest.raises(model_seam.ModelStructuralAuditError, match="/task_updates/0/"):
        model_seam.audit_step_payload(
            "execute",
            {
                "task_updates": [{"id": "T7", "status": "finished"}],
                "sense_check_acknowledgments": [],
            },
        )


def test_compatibility_projection_calls_normalize_and_validate_for_long_tail_sites() -> None:
    """Long-tail sites stay on legacy normalize+validate until m6."""
    from arnold.pipelines.megaplan.workers._impl import (
        _normalize_worker_payload,
        validate_payload,
    )

    minimal_payloads: dict[str, dict[str, object]] = {
        "plan": {"plan": "x", "questions": [], "success_criteria": [], "assumptions": []},
        "revise": {
            "plan": "x",
            "changes_summary": "y",
            "flags_addressed": [],
            "assumptions": [],
            "success_criteria": [],
            "questions": [],
        },
        "prep": {
            "skip": False,
            "task_summary": "...",
            "key_evidence": [],
            "relevant_code": [],
            "test_expectations": [],
            "constraints": [],
            "suggested_approach": "...",
        },
        "tiebreaker_challenger": {
            "measurements_vs_assumptions": [],
            "missing_options": [],
            "hard_cases": [],
            "reframings": [],
            "aging_analysis": [],
            "counter_recommendation": "...",
        },
        "feedback": {"overall": "...", "stages": []},
    }

    for step in _LONG_TAIL_SITES:
        try:
            minimal_payloads[step]
        except KeyError:
            continue
        payload = dict(minimal_payloads[step])
        invocation = StepInvocation(
            kind="model",
            metadata={"compatibility_validation_step": step},
        )
        assert model_seam._compatibility_mode_for_step(step) is model_seam.CompatibilityMode.LEGACY
        assert model_seam._capture_schema_for_invocation(invocation) is None
        normalized = _normalize_worker_payload(step, payload)
        validate_payload(step, normalized)
        assert model_seam._compatibility_projection(invocation, dict(payload)) == normalized


def test_normalize_worker_payload_is_not_exported_from_workers_package() -> None:
    """_normalize_worker_payload is a private implementation detail — handlers
    must not call it directly.  Only recovery and the compatibility chokepoint
    invoke it."""
    import arnold.pipelines.megaplan.workers as _workers

    assert not hasattr(_workers, "_normalize_worker_payload") or (
        "_normalize_worker_payload" not in getattr(_workers, "__all__", [])
    )


def test_compatibility_projection_is_the_only_model_seam_caller() -> None:
    """Characterization: within model_seam.py, only _compatibility_projection()
    directly imports and calls _normalize_worker_payload + validate_payload.

    After m5 migration, this function must gate on the step name and skip
    migrated sites.  This test does NOT assert the gating exists yet — it only
    pins the current single-caller layout so later tasks can prove the gating
    was added.
    """
    import ast
    from pathlib import Path

    seam_path = (
        Path(__file__).resolve().parents[4]
        / "arnold/pipelines/megaplan/model_seam.py"
    )
    source = seam_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Find every function that imports _normalize_worker_payload or validate_payload
    # from workers._impl inside a function body (lazy import pattern).
    func_callers: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    if child.module == "arnold.pipelines.megaplan.workers._impl":
                        for alias in child.names:
                            if alias.name in (
                                "_normalize_worker_payload",
                                "validate_payload",
                            ):
                                func_callers.setdefault(func_name, set()).add(
                                    alias.name
                                )
    # Currently only _compatibility_projection should do this import.
    assert func_callers == {
        "_compatibility_projection": {
            "_normalize_worker_payload",
            "validate_payload",
        }
    }, (
        f"Unexpected callers of _normalize_worker_payload/validate_payload "
        f"in model_seam.py: {func_callers}"
    )


def test_render_step_message_consumes_structured_prompt_components() -> None:
    components = PromptComponents(
        prompt="component prompt",
        system="component system",
        messages=({"role": "assistant", "content": "history"},),
        schema={"type": "object", "properties": {"output": {"type": "string"}}},
        template={"output": "example"},
        metadata={"worker": "codex"},
    )
    invocation = StepInvocation(
        kind="model",
        metadata={
            "model": "gpt-5.4",
            "tier": "non_enforced",
            **components.to_model_metadata(),
        },
    )

    rendered = render_step_message(invocation)

    assert rendered.text == "component prompt"
    assert rendered.prompt == "component prompt"
    assert rendered.metadata["worker"] == "codex"
    assert rendered.messages[-1] == {"role": "user", "content": "component prompt"}
    assert rendered.schema == {"type": "object", "properties": {"output": {"type": "string"}}}
    assert rendered.template == {"output": "example"}


# ──────────────────────────────────────────────────────────────────────
# render_compact_review_prompt — seam-owned review compaction
# ──────────────────────────────────────────────────────────────────────


def test_render_compact_review_prompt_delegates_to_compact_review_prompt(
    tmp_path,
) -> None:
    """Proves the seam helper delegates to compact_review_prompt under the hood."""
    from unittest.mock import patch

    state: dict[str, object] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}
    plan_dir = tmp_path / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    with patch(
        "arnold.pipelines.megaplan.prompts.review.compact_review_prompt"
    ) as mock_compact:
        mock_compact.return_value = "compacted review text"

        result = model_seam.render_compact_review_prompt(
            "codex",
            "review",
            state,
            plan_dir,
            model="gpt-5.4",
            schema={"type": "object"},
            prompt_size_error={"message": "too large"},
            pre_check_flags=[{"flag": "FC01"}],
        )

    mock_compact.assert_called_once()
    call_args, call_kwargs = mock_compact.call_args
    # state and plan_dir are positional
    assert call_kwargs.get("prompt_size_error") == {"message": "too large"}
    assert call_kwargs.get("pre_check_flags") == [{"flag": "FC01"}]
    assert isinstance(result, model_seam.RenderedStepMessage)
    assert result.prompt == "compacted review text"


def test_render_compact_review_prompt_returns_rendered_step_message(
    tmp_path,
) -> None:
    """The output is a properly formed RenderedStepMessage with expected metadata."""
    from unittest.mock import patch

    state: dict[str, object] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}
    plan_dir = tmp_path / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    with patch(
        "arnold.pipelines.megaplan.prompts.review.compact_review_prompt"
    ) as mock_compact:
        mock_compact.return_value = "compacted prompt"

        result = model_seam.render_compact_review_prompt(
            "hermes",
            "review",
            state,
            plan_dir,
            worker="hermes",
            model="deepseek-v4",
            normalized_model="deepseek-v4",
            schema={"type": "object", "properties": {"review_verdict": {"type": "string"}}},
        )

    assert result.prompt == "compacted prompt"
    assert result.metadata["worker"] == "hermes"
    assert result.metadata["model"] == "deepseek-v4"
    assert result.metadata["validation_step"] == "review"
    assert result.metadata["tier"] == "non_enforced"
    assert result.schema == {"type": "object", "properties": {"review_verdict": {"type": "string"}}}
    assert result.telemetry.terminal_status is model_seam.TerminalStatus.RENDERED


def test_render_compact_review_prompt_preserves_pre_check_flags(
    tmp_path,
) -> None:
    """Pre-check flags are forwarded to compact_review_prompt exactly as received."""
    from unittest.mock import patch

    state: dict[str, object] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}
    plan_dir = tmp_path / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    pre_check = [
        {"flag_id": "FC01", "description": "missing evidence"},
        {"flag_id": "FC02", "description": "stale plan"},
    ]

    with patch(
        "arnold.pipelines.megaplan.prompts.review.compact_review_prompt"
    ) as mock_compact:
        mock_compact.return_value = "compacted"

        model_seam.render_compact_review_prompt(
            "codex",
            "review",
            state,
            plan_dir,
            pre_check_flags=pre_check,
        )

    assert mock_compact.call_args[1]["pre_check_flags"] == pre_check


def test_render_compact_review_prompt_preserves_projection_capabilities(
    tmp_path,
) -> None:
    """Projection capabilities are forwarded transparently."""
    from unittest.mock import patch

    from arnold.pipelines.megaplan.prompts._projection import PromptProjectionCapabilities

    state: dict[str, object] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}
    plan_dir = tmp_path / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    caps = PromptProjectionCapabilities.full()

    with patch(
        "arnold.pipelines.megaplan.prompts.review.compact_review_prompt"
    ) as mock_compact:
        mock_compact.return_value = "compacted"

        model_seam.render_compact_review_prompt(
            "codex",
            "review",
            state,
            plan_dir,
            projection_capabilities=caps,
        )

    assert mock_compact.call_args[1]["projection_capabilities"] is caps


def test_render_compact_review_prompt_handles_none_prompt_size_error(
    tmp_path,
) -> None:
    """None prompt_size_error is forwarded as-is (normal oversized-check fallback)."""
    from unittest.mock import patch

    state: dict[str, object] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}
    plan_dir = tmp_path / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    with patch(
        "arnold.pipelines.megaplan.prompts.review.compact_review_prompt"
    ) as mock_compact:
        mock_compact.return_value = "compacted"

        model_seam.render_compact_review_prompt(
            "codex",
            "review",
            state,
            plan_dir,
            prompt_size_error=None,
        )

    assert mock_compact.call_args[1]["prompt_size_error"] is None


def test_render_compact_review_prompt_enforced_tier_preserved(
    tmp_path,
) -> None:
    """Enforced tier is carried through to the rendered metadata."""
    from unittest.mock import patch

    state: dict[str, object] = {"config": {"project_dir": str(tmp_path), "mode": "code"}}
    plan_dir = tmp_path / "plans" / "test-plan"
    plan_dir.mkdir(parents=True)

    with patch(
        "arnold.pipelines.megaplan.prompts.review.compact_review_prompt"
    ) as mock_compact:
        mock_compact.return_value = "compacted"

        result = model_seam.render_compact_review_prompt(
            "codex",
            "review",
            state,
            plan_dir,
            tier=model_seam.ModelTier.ENFORCED,
        )

    assert result.metadata["tier"] == "enforced"


def test_render_compact_review_prompt_exported_in_all(tmp_path) -> None:
    """render_compact_review_prompt is in the module __all__ and is callable."""
    assert "render_compact_review_prompt" in model_seam.__all__

    from arnold.pipelines.megaplan.model_seam import render_compact_review_prompt

    assert callable(render_compact_review_prompt)
