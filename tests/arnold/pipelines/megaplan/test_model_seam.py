from __future__ import annotations

import json

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


def test_capture_step_output_runs_enumerated_compatibility_projection_before_audit() -> None:
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
            "task_updates": [{"id": "T7", "status": "completed"}],
            "sense_check_acknowledgments": [],
        },
    )

    assert outcome.legacy_payload == {
        "task_updates": [{"id": "T7", "task_id": "T7", "status": "done"}],
        "sense_check_acknowledgments": [],
    }
    assert outcome.telemetry.audit_result is AuditStatus.PASSED
    assert outcome.contract_result.payload["telemetry"]["audit_result"] == "passed"


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
