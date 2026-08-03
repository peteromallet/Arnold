from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy

import pytest

from arnold.execution.step_invocation import StepInvocation
from arnold_pipelines.megaplan.auto import _is_retryable_external_error
from arnold_pipelines.megaplan.model_seam import (
    LOCAL_STRICT_ARTIFACT_RECEIPT_SCHEMA,
    capture_step_output,
    local_strict_repair_input,
)
from arnold.pipeline.model_seam import ModelStructuralAuditError
from arnold_pipelines.megaplan.orchestration.phase_result import ExternalError
from arnold_pipelines.megaplan.orchestration.phase_result_classify import (
    classify_external_error_payload,
)
from arnold_pipelines.megaplan.provider_response import (
    ProviderResponseContractError,
    ResponseEnforcement,
    compile_response_contract,
    persist_response_enforcement_attestation,
    schema_sha256,
)
from arnold_pipelines.megaplan.schemas import SCHEMAS, strict_schema
from arnold_pipelines.megaplan.workers._impl import (
    _WORKER_DISPATCH_BINDING,
    _build_response_contract_repair_prompt,
    _codex_repair_input,
    _new_response_occurrence,
    _persist_codex_response_evidence,
    _codex_provider_contract_error,
    _codex_response_schema_args,
    _is_codex_provider_schema_rejection,
    _local_response_contract_error,
    _prepare_local_strict_artifact_handoff,
    _preflight_trusted_container_artifact_handoff,
    _response_output_path,
    _select_codex_terminal_output,
)


def test_codex_repair_diagnoses_canonical_output_not_jsonl_transport() -> None:
    transport = '{"type":"thread.started"}\n{"type":"turn.completed"}\n'
    canonical = '{"tasks":[],"user_actions":[]}'

    selected, parse_error = _codex_repair_input(transport, canonical)

    assert selected == canonical
    assert parse_error is None


def test_codex_repair_never_falls_back_to_jsonl_transport() -> None:
    transport = '{"type":"item.completed","item":{"type":"agent_message","text":"{}"}}\n'

    selected, parse_error = _codex_repair_input(transport, "")

    assert selected == ""
    assert parse_error is None


def test_codex_terminal_selection_requires_nonempty_output_equal_to_last_message() -> None:
    selected = '{"tasks":[],"user_actions":[]}'
    transport = json.dumps(
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": selected},
        }
    )
    assert _select_codex_terminal_output(transport, selected + "\n") == selected + "\n"

    with pytest.raises(ModelStructuralAuditError, match="empty"):
        _select_codex_terminal_output(transport, "")
    with pytest.raises(ModelStructuralAuditError, match="does not equal"):
        _select_codex_terminal_output(transport, '{"different":true}')
    intermediate = transport
    final_transport = intermediate + "\n" + json.dumps(
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": '{"other":true}'},
        }
    )
    assert _select_codex_terminal_output(final_transport, '{"other":true}\n') == (
        '{"other":true}\n'
    )
    with pytest.raises(ModelStructuralAuditError, match="last JSONL"):
        _select_codex_terminal_output(final_transport, selected)


def test_response_occurrence_and_evidence_bind_exact_wbc_invocation(tmp_path) -> None:
    state = {
        "name": "attempt9",
        "iteration": 2,
        "active_step": {"run_id": "finalize-process-run-9"},
        "meta": {"current_invocation_id": "finalize-invocation-9"},
    }
    token = _WORKER_DISPATCH_BINDING.set(
        {
            "worker_wbc_attempt_id": "worker-attempt-9",
            "phase_wbc_attempt_id": "phase-attempt-9",
        }
    )
    try:
        first = _new_response_occurrence(state, tmp_path, step="finalize")
        second = _new_response_occurrence(state, tmp_path, step="finalize")
    finally:
        _WORKER_DISPATCH_BINDING.reset(token)

    assert first["occurrence_id"] != second["occurrence_id"]
    assert first["invocation_id"] == "finalize-invocation-9"
    assert first["worker_wbc_attempt_id"] == "worker-attempt-9"
    assert first["phase_wbc_attempt_id"] == "phase-attempt-9"
    transport = '{"type":"turn.completed"}\n'
    selected = '{"tasks":[],"user_actions":[]}'
    receipt = _persist_codex_response_evidence(
        tmp_path,
        occurrence=first,
        repair_ordinal=0,
        raw_transport=transport,
        terminal_output=selected,
        output_path=tmp_path / "primary.json",
        model="gpt-5.6-sol",
        selection_error=None,
    )
    assert receipt["repair_ordinal"] == 0
    assert receipt["transport"]["sha256"].startswith("sha256:")
    assert receipt["selected_terminal_output"]["sha256"].startswith("sha256:")
    persisted = json.loads((tmp_path / receipt["receipt_path"]).read_text())
    assert persisted["worker_wbc_attempt_id"] == "worker-attempt-9"
    with pytest.raises(Exception, match="already exists"):
        _persist_codex_response_evidence(
            tmp_path,
            occurrence=first,
            repair_ordinal=0,
            raw_transport=transport,
            terminal_output=selected,
            output_path=tmp_path / "primary.json",
            model="gpt-5.6-sol",
            selection_error=None,
        )


def test_repair_prompt_contains_full_selected_object_and_canonical_schema() -> None:
    prefix = "x" * 21000
    selected = json.dumps({"prefix": prefix, "user_actions": [{"id": "U1"}]})
    schema = {"type": "object", "required": ["user_actions"]}

    prompt = _build_response_contract_repair_prompt(
        step="finalize",
        schema=schema,
        failure_reason="requires_human_only_reason is required",
        selected_output=selected,
    )

    assert selected in prompt
    assert json.dumps(schema, sort_keys=True) in prompt
    assert "requires_human_only_reason is required" in prompt
    assert "NDJSON" in prompt


def test_primary_and_repair_output_paths_are_occurrence_unique(tmp_path) -> None:
    primary = _response_output_path(
        tmp_path, step="finalize", occurrence_id="a" * 64, repair_ordinal=0
    )
    repair = _response_output_path(
        tmp_path, step="finalize", occurrence_id="a" * 64, repair_ordinal=1
    )
    assert primary != repair
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text("original", encoding="utf-8")
    assert not repair.exists()
    assert primary.read_text(encoding="utf-8") == "original"


def test_trusted_container_handoff_preflight_requires_explicit_trust_and_is_clean(
    tmp_path, monkeypatch
) -> None:
    handoff = _prepare_local_strict_artifact_handoff(tmp_path, step="finalize")
    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    with pytest.raises(Exception, match="requires explicit"):
        _preflight_trusted_container_artifact_handoff(handoff)

    monkeypatch.setenv("MEGAPLAN_TRUSTED_CONTAINER", "1")
    _preflight_trusted_container_artifact_handoff(handoff)
    root = __import__("pathlib").Path(handoff["root"])
    assert not list(root.glob(".handoff-canary-*"))

    def deny_atomic_rename(*_args, **_kwargs):
        raise OSError("rename denied")

    monkeypatch.setattr(os, "replace", deny_atomic_rename)
    with pytest.raises(Exception, match="atomic non-empty") as raised:
        _preflight_trusted_container_artifact_handoff(handoff)
    assert raised.value.extra["pre_dispatch"] is True


def test_finalize_semantic_repair_preserves_primary_and_uses_exact_missing_field(
    tmp_path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    from arnold_pipelines.megaplan.workers import _impl

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    ensure_runtime_layout(runtime_root)
    plan_dir = runtime_root / ".megaplan" / "plans" / "attempt9"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "attempt9",
        "idea": "repair the exact missing field",
        "current_state": "gated",
        "iteration": 2,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"current_invocation_id": "finalize-attempt9"},
    }
    legacy = {
        "tasks": [],
        "sense_checks": [],
        "watch_items": [],
        "user_actions": [
            {
                "id": "U1",
                "description": "Approve the legal exception",
                "phase": "before_execute",
            }
        ],
        "meta_commentary": "legacy attempt9 shape",
    }
    repaired = deepcopy(legacy)
    repaired["user_actions"][0]["requires_human_only_reason"] = (
        "Legal liability requires a human signatory."
    )
    outputs: list[tuple[object, str, str]] = []

    def fake_run_command(command, **kwargs):
        output_path = __import__("pathlib").Path(command[command.index("-o") + 1])
        payload = legacy if not outputs else repaired
        rendered = json.dumps(payload, separators=(",", ":"))
        output_path.write_text(rendered, encoding="utf-8")
        outputs.append((output_path, rendered, kwargs["stdin_text"]))
        event = json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": rendered},
            }
        )
        return _impl.CommandResult(
            command=list(command),
            cwd=tmp_path,
            returncode=0,
            stdout=event + "\n",
            stderr="",
            duration_ms=5,
        )

    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.setattr(_impl, "run_command", fake_run_command)
    monkeypatch.setattr(
        _impl,
        "_codex_step_cost",
        lambda *args, **kwargs: (0.0, 0, 0, "gpt-5.6-sol", None),
    )
    primary = plan_dir / "attempt9-primary.json"

    result = _impl.run_codex_step(
        "finalize",
        state,
        plan_dir,
        root=runtime_root,
        persistent=False,
        fresh=True,
        model="gpt-5.6-sol",
        output_path=primary,
        prompt_override="Return the finalized task graph.",
    )

    assert len(outputs) == 2
    assert outputs[0][0] == primary
    assert outputs[1][0] != primary
    assert primary.read_text(encoding="utf-8") == outputs[0][1]
    assert "requires_human_only_reason" not in outputs[0][1]
    assert "requires_human_only_reason" in outputs[1][1]
    assert outputs[0][1] in outputs[1][2]
    assert "Canonical JSON Schema (complete)" in outputs[1][2]
    assert result.payload == repaired
    receipts = list(
        (plan_dir / ".megaplan" / "model-response-evidence" / "occurrences").glob(
            "*/repair-*.json"
        )
    )
    assert {path.name for path in receipts} == {"repair-0.json", "repair-1.json"}


def test_terminal_selection_mismatch_is_not_semantically_repaired(
    tmp_path, monkeypatch
) -> None:
    from arnold_pipelines.megaplan._core import ensure_runtime_layout
    from arnold_pipelines.megaplan.workers import _impl

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    ensure_runtime_layout(runtime_root)
    plan_dir = runtime_root / ".megaplan" / "plans" / "selection-mismatch"
    plan_dir.mkdir(parents=True)
    state = {
        "name": "selection-mismatch",
        "idea": "fail closed on response custody mismatch",
        "current_state": "gated",
        "iteration": 1,
        "created_at": "1970-01-01T00:00:00Z",
        "config": {"project_dir": str(tmp_path), "mode": "code"},
        "sessions": {},
        "plan_versions": [],
        "history": [],
        "meta": {"current_invocation_id": "finalize-selection-mismatch"},
    }
    selected = json.dumps(
        {
            "tasks": [],
            "sense_checks": [],
            "watch_items": [],
            "user_actions": [],
            "meta_commentary": "selected output",
        }
    )
    calls = 0

    def fake_run_command(command, **_kwargs):
        nonlocal calls
        calls += 1
        output_path = __import__("pathlib").Path(command[command.index("-o") + 1])
        output_path.write_text(selected, encoding="utf-8")
        event = json.dumps(
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": '{"different":true}'},
            }
        )
        return _impl.CommandResult(
            command=list(command),
            cwd=tmp_path,
            returncode=0,
            stdout=event + "\n",
            stderr="",
            duration_ms=5,
        )

    monkeypatch.delenv("MEGAPLAN_TRUSTED_CONTAINER", raising=False)
    monkeypatch.setattr(_impl, "run_command", fake_run_command)

    with pytest.raises(Exception) as raised:
        _impl.run_codex_step(
            "finalize",
            state,
            plan_dir,
            root=runtime_root,
            persistent=False,
            fresh=True,
            model="gpt-5.6-sol",
            prompt_override="Return the finalized task graph.",
        )

    assert calls == 1
    budget = raised.value.extra["local_response_contract"]
    assert budget["attempts"] == 1
    assert budget["repairs"] == 0
    assert budget["exhausted"] is True


@pytest.mark.parametrize(
    ("schema_name", "reason_fragment"),
    [
        ("finalize_capture.json", "dynamic_or_open_object"),
        ("feedback.json", "dynamic_or_open_object"),
        ("loop_plan.json", "dynamic_or_open_object"),
    ],
)
def test_dynamic_contracts_select_local_strict_json(
    schema_name: str, reason_fragment: str
) -> None:
    schema = strict_schema(deepcopy(SCHEMAS[schema_name]))

    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase=schema_name.removesuffix(".json"),
    )

    assert compiled.transport_schema is None
    assert (
        compiled.attestation.response_enforcement
        == ResponseEnforcement.LOCAL_STRICT_JSON.value
    )
    assert reason_fragment in compiled.attestation.enforcement_reason
    assert compiled.attestation.canonical_schema_hash == schema_sha256(schema)
    assert compiled.attestation.transport_schema_hash is None


def test_closed_schema_uses_provider_strict_and_output_schema_argument(tmp_path) -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="closed",
    )
    schema_path = tmp_path / "transport.json"
    schema_path.write_text(json.dumps(compiled.transport_schema), encoding="utf-8")

    assert (
        compiled.attestation.response_enforcement
        == ResponseEnforcement.PROVIDER_STRICT.value
    )
    assert compiled.transport_schema == schema
    assert compiled.attestation.transport_schema_hash == schema_sha256(schema)
    assert _codex_response_schema_args(schema_path) == [
        "--output-schema",
        str(schema_path),
        "-",
    ]


def test_local_strict_command_omits_output_schema() -> None:
    assert _codex_response_schema_args(None) == ["-"]


def test_optional_semantic_fields_are_not_promoted_for_provider_acceptance() -> None:
    schema = {
        "type": "object",
        "properties": {
            "required_value": {"type": "string"},
            "optional_value": {"type": "string"},
        },
        "required": ["required_value"],
        "additionalProperties": False,
    }

    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="semantic"
    )

    assert compiled.transport_schema is None
    assert compiled.attestation.response_enforcement == "local_strict_json"
    assert "optional_object_properties" in compiled.attestation.enforcement_reason
    assert compiled.attestation.canonical_schema_hash == schema_sha256(schema)


@pytest.mark.parametrize(
    ("schema", "reason"),
    [
        ({"type": "string"}, "root_schema_must_be_object"),
        (
            {
                "type": ["object", "null"],
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
            "unsupported_type_union",
        ),
        (
            {
                "type": "object",
                "properties": {"answers": {"type": "array"}},
                "required": ["answers"],
                "additionalProperties": False,
            },
            "array_without_item_schema",
        ),
        (
            {
                "type": "object",
                "properties": {"answer": {"type": "string"}},
                "required": ["answer", "answer"],
                "additionalProperties": False,
            },
            "optional_object_properties",
        ),
    ],
)
def test_ambiguous_provider_dialect_contracts_fail_closed_to_local_validation(
    schema, reason: str
) -> None:
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="conservative"
    )

    assert compiled.transport_schema is None
    assert compiled.attestation.response_enforcement == "local_strict_json"
    assert reason in compiled.attestation.enforcement_reason


def test_resume_transport_forces_local_strict_even_for_closed_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="execute",
        provider_schema_available=False,
    )
    assert compiled.transport_schema is None
    assert compiled.attestation.enforcement_reason == (
        "transport_does_not_support_provider_schema"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"default": "invented"},
        {"const": "invented"},
        {"oneOf": [{"type": "string"}, {"type": "integer"}]},
        {"minimum": 1},
    ],
)
def test_historical_schema_mutations_fail_closed_to_local_validation(mutation) -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string", **mutation}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="m9_mutation_replay",
    )

    assert compiled.transport_schema is None
    assert compiled.attestation.response_enforcement == "local_strict_json"
    assert compiled.attestation.enforcement_reason.startswith("unsupported_keyword:")


def test_local_strict_feedback_round_trip_preserves_dynamic_stage_keys() -> None:
    payload = {
        "overall": {"rating": 8, "comment": "good"},
        "stages": {
            "M9-provider-boundary": {"rating": 3, "comment": "reproduced"},
            "future-stage-id": {"rating": 7, "comment": "preserved"},
        },
    }
    schema = strict_schema(deepcopy(SCHEMAS["feedback.json"]))
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.6-sol",
            "validation_step": "feedback",
            "compatibility_validation_step": "feedback",
            "schema": schema,
            "capture_schema": SCHEMAS["feedback.json"],
        },
    )

    captured = capture_step_output(invocation, json.dumps(payload))

    assert captured.legacy_payload == payload


def test_local_strict_loop_plan_round_trip_preserves_open_spec_updates() -> None:
    payload = {
        "spec_updates": {
            "new_runtime_axis": {"enabled": True, "threshold": 4},
            "nested": {"provider": {"model": "future-model"}},
        },
        "next_action": "continue",
        "reasoning": "retain learned fields",
    }
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.6-sol",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": strict_schema(deepcopy(SCHEMAS["loop_plan.json"])),
            "capture_schema": SCHEMAS["loop_plan.json"],
        },
    )

    captured = capture_step_output(invocation, json.dumps(payload))

    assert captured.legacy_payload == payload


def test_attestation_is_durable_and_complete(tmp_path) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema,
        provider="codex",
        model="gpt-5.6-sol",
        phase="loop_plan",
    )

    path = persist_response_enforcement_attestation(tmp_path, compiled.attestation)
    record = json.loads(path.read_text(encoding="utf-8"))

    assert set(record) == {
        "canonical_schema_hash",
        "response_enforcement",
        "enforcement_reason",
        "provider",
        "model",
        "phase",
        "transport_schema_hash",
        "compiler_version",
    }
    assert record["phase"] == "loop_plan"


def test_invalid_compiler_input_has_typed_stable_external_error() -> None:
    with pytest.raises(ProviderResponseContractError) as first:
        compile_response_contract(
            {}, provider="codex", model="gpt-5.6-sol", phase="finalize"
        )
    with pytest.raises(ProviderResponseContractError) as second:
        compile_response_contract(
            {}, provider="codex", model="gpt-5.6-sol", phase="finalize"
        )

    error = first.value.external_error()
    assert error == {
        "error_kind": "provider_contract",
        "error_layer": "schema_error",
        "deterministic": True,
        "nonretryable": True,
        "failure_fingerprint": second.value.failure_fingerprint,
    }


@pytest.mark.parametrize(
    "rendered",
    [
        'prefix {"spec_updates": {}, "next_action": "continue", "reasoning": "ok"}',
        '```json\n{"spec_updates": {}, "next_action": "continue", "reasoning": "ok"}\n```',
    ],
)
def test_local_strict_capture_rejects_candidate_recovery(
    tmp_path, rendered: str
) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    output = tmp_path / "response.txt"
    output.write_text(rendered, encoding="utf-8")
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "worker": "codex",
            "model": "gpt-5.6-sol",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": compiled.attestation.to_json(),
            "capture_recovery": {
                "step": "loop_plan",
                "plan_dir": str(tmp_path),
                "output_path": str(output),
                "prefer_output_file": True,
            },
        },
    )

    with pytest.raises(json.JSONDecodeError):
        capture_step_output(invocation, rendered)


@pytest.mark.parametrize(
    "rendered, match",
    [
        (
            '{"spec_updates":{"x":1,"x":2},"next_action":"continue","reasoning":"ok"}',
            "duplicate JSON object key",
        ),
        (
            '{"spec_updates":{"x":NaN},"next_action":"continue","reasoning":"ok"}',
            "non-finite JSON number",
        ),
    ],
)
def test_local_strict_capture_rejects_ambiguous_json(
    tmp_path, rendered: str, match: str
) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    output = tmp_path / "response.txt"
    output.write_text(rendered, encoding="utf-8")
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": compiled.attestation.to_json(),
            "capture_recovery": {
                "step": "loop_plan",
                "plan_dir": str(tmp_path),
                "output_path": str(output),
            },
        },
    )

    with pytest.raises(ModelStructuralAuditError, match=match):
        capture_step_output(invocation, rendered)


def test_local_strict_capture_rejects_schema_attestation_substitution(tmp_path) -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    attestation = compiled.attestation.to_json()
    attestation["canonical_schema_hash"] = "0" * 64
    invocation = StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": attestation,
        },
    )

    with pytest.raises(ModelStructuralAuditError, match="does not bind"):
        capture_step_output(
            invocation,
            '{"spec_updates":{},"next_action":"continue","reasoning":"ok"}',
        )


def _artifact_handoff_invocation(tmp_path, candidate, *, max_bytes=1024 * 1024):
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="loop_plan"
    )
    return StepInvocation(
        kind="model",
        metadata={
            "tier": "enforced",
            "validation_step": "loop_plan",
            "compatibility_validation_step": "loop_plan",
            "schema": schema,
            "capture_schema": SCHEMAS["loop_plan.json"],
            "response_enforcement_attestation": compiled.attestation.to_json(),
            "capture_recovery": {
                "artifact_handoff": {
                    "schema": LOCAL_STRICT_ARTIFACT_RECEIPT_SCHEMA,
                    "root": str(candidate.parent),
                    "candidate_path": str(candidate),
                    "max_bytes": max_bytes,
                }
            },
        },
    )


def _artifact_receipt(candidate, data: bytes) -> str:
    return json.dumps(
        {
            "schema": LOCAL_STRICT_ARTIFACT_RECEIPT_SCHEMA,
            "path": str(candidate),
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
    )


def test_local_strict_artifact_handoff_round_trip_is_exact_and_schema_audited(tmp_path) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    payload = {
        "spec_updates": {"large": "x" * 50_000},
        "next_action": "continue",
        "reasoning": "durable handoff",
    }
    data = json.dumps(payload, separators=(",", ":")).encode()
    temporary = root / "write.tmp"
    temporary.write_bytes(data)
    os.replace(temporary, candidate)

    captured = capture_step_output(
        _artifact_handoff_invocation(tmp_path, candidate),
        _artifact_receipt(candidate, data),
    )

    assert captured.legacy_payload == payload
    assert "codex_capture:artifact_handoff" in captured.contract_result.provenance.sources


def test_local_strict_artifact_semantic_repair_receives_complete_candidate(tmp_path) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    payload = {
        "spec_updates": {"large": "x" * 50_000},
        "next_action": "continue",
        # Deliberately missing required ``reasoning`` so ordinary capture
        # reaches semantic repair after the receipt has been authenticated.
    }
    data = json.dumps(payload, separators=(",", ":")).encode()
    candidate.write_bytes(data)
    invocation = _artifact_handoff_invocation(tmp_path, candidate)
    receipt = _artifact_receipt(candidate, data)

    with pytest.raises(ModelStructuralAuditError):
        capture_step_output(invocation, receipt)

    repair_input = local_strict_repair_input(invocation, receipt)
    assert json.loads(repair_input) == payload
    assert len(repair_input) > 50_000


def test_local_strict_artifact_handoff_rejects_zero_byte_receipt(tmp_path) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "empty.candidate.json"
    candidate.write_bytes(b"")

    with pytest.raises(ModelStructuralAuditError, match="bytes is invalid"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, candidate),
            _artifact_receipt(candidate, b""),
        )


@pytest.mark.parametrize("mutation", ["path", "digest", "size", "extra"])
def test_local_strict_artifact_handoff_rejects_unbound_receipts(tmp_path, mutation) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    data = b'{"spec_updates":{},"next_action":"continue","reasoning":"ok"}'
    candidate.write_bytes(data)
    receipt = json.loads(_artifact_receipt(candidate, data))
    if mutation == "path":
        other = root / "stale.candidate.json"
        other.write_bytes(data)
        receipt["path"] = str(other)
    elif mutation == "digest":
        receipt["sha256"] = "0" * 64
    elif mutation == "size":
        receipt["bytes"] += 1
    else:
        receipt["nonce"] = "not-in-contract"

    with pytest.raises(ModelStructuralAuditError):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, candidate),
            json.dumps(receipt),
        )


def test_local_strict_artifact_handoff_rejects_symlink_and_path_escape(tmp_path) -> None:
    outside = tmp_path / "outside.json"
    data = b'{"spec_updates":{},"next_action":"continue","reasoning":"ok"}'
    outside.write_bytes(data)
    root = tmp_path / "handoff"
    root.mkdir()
    candidate = root / "unique.candidate.json"
    candidate.symlink_to(outside)

    with pytest.raises(ModelStructuralAuditError, match="non-symlink regular file"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, candidate),
            _artifact_receipt(candidate, data),
        )

    escaped = tmp_path / "escape.candidate.json"
    escaped.write_bytes(data)
    invocation = _artifact_handoff_invocation(tmp_path, escaped)
    invocation.metadata["capture_recovery"]["artifact_handoff"]["root"] = str(root)
    with pytest.raises(ModelStructuralAuditError, match="escapes"):
        capture_step_output(invocation, _artifact_receipt(escaped, data))


def test_local_strict_artifact_handoff_rejects_oversize_and_invalid_payload(tmp_path) -> None:
    root = tmp_path / "handoff"
    root.mkdir()
    oversized = root / "large.candidate.json"
    oversized_data = b'{' + b' ' * 64 + b'}'
    oversized.write_bytes(oversized_data)
    with pytest.raises(ModelStructuralAuditError, match="size limit"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, oversized, max_bytes=16),
            _artifact_receipt(oversized, oversized_data),
        )

    invalid = root / "invalid.candidate.json"
    invalid_data = b'{"spec_updates":{},"next_action":"continue"}'
    invalid.write_bytes(invalid_data)
    with pytest.raises(ModelStructuralAuditError):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, invalid),
            _artifact_receipt(invalid, invalid_data),
        )


def test_local_strict_handoff_paths_are_unique_and_replay_bound(tmp_path) -> None:
    first = _prepare_local_strict_artifact_handoff(tmp_path, step="finalize")
    second = _prepare_local_strict_artifact_handoff(tmp_path, step="finalize")
    assert first["candidate_path"] != second["candidate_path"]
    assert "local-strict-artifacts" in first["candidate_path"]
    assert not first["candidate_path"].endswith("finalize_output.json")

    first_path = first["candidate_path"]
    data = b'{"spec_updates":{},"next_action":"continue","reasoning":"ok"}'
    first_candidate = __import__("pathlib").Path(first_path)
    first_candidate.write_bytes(data)
    second_candidate = __import__("pathlib").Path(second["candidate_path"])
    with pytest.raises(ModelStructuralAuditError, match="does not match"):
        capture_step_output(
            _artifact_handoff_invocation(tmp_path, second_candidate),
            _artifact_receipt(first_candidate, data),
        )


def test_local_response_contract_exhaustion_is_nonretryable_and_bounded() -> None:
    schema = strict_schema(deepcopy(SCHEMAS["loop_plan.json"]))
    error = _local_response_contract_error(
        step="loop_plan", schema=schema, reason="bad receipt", raw="{}"
    )
    budget = error.extra["local_response_contract"]
    external = error.extra["_external_error"]
    assert budget == {
        "attempts": 2,
        "repairs": 1,
        "max_attempts": 2,
        "exhausted": True,
        "occurrence_id": budget["occurrence_id"],
        "failure_fingerprint": budget["failure_fingerprint"],
        "occurrence": {},
        "evidence_receipt": None,
    }
    assert external["nonretryable"] is True
    assert external["failure_fingerprint"] == budget["failure_fingerprint"]
    classified = classify_external_error_payload(error)
    assert classified is not None
    assert not _is_retryable_external_error(
        "finalize", ExternalError.from_dict(classified)
    )


def test_unexpected_backend_schema_rejection_is_typed_and_stable() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    compiled = compile_response_contract(
        schema, provider="codex", model="gpt-5.6-sol", phase="finalize"
    )
    raw_a = "HTTP 400 invalid_json_schema request_id=req-a"
    raw_b = "HTTP 400 invalid_json_schema request_id=req-b"

    assert _is_codex_provider_schema_rejection(raw_a)
    first = _codex_provider_contract_error(compiled, raw_a)
    second = _codex_provider_contract_error(compiled, raw_b)
    first_external = first.extra["_external_error"]
    second_external = second.extra["_external_error"]

    assert first.code == "provider_contract"
    assert first_external["error_kind"] == "provider_contract"
    assert first_external["deterministic"] is True
    assert first_external["nonretryable"] is True
    assert (
        first_external["failure_fingerprint"]
        == second_external["failure_fingerprint"]
    )


def test_generic_http_400_is_not_forged_into_schema_rejection() -> None:
    assert not _is_codex_provider_schema_rejection(
        "HTTP 400 invalid_request_error: malformed command argument"
    )
