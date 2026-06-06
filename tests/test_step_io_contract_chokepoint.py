from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from arnold.pipeline import (
    ContractSchemaRegistry,
    STEP_IO_READ_LENIENT_ENV,
    StepIOClassification,
    StepIOContractContext,
    StepIOContractDecision,
    StepIOOperation,
    TELEMETRY_FILENAME,
    decide_step_io_read,
    decision_blocks_read,
    load_step_io_policy,
    read_violation_records,
    resolve_step_io_policy,
    step_io_read_lenient_escape_on,
    step_io_policy_path,
    validate_payload_against_schema,
    write_step_io_policy,
)
from arnold.pipelines.megaplan.orchestration.completion_contract import (
    normalize_contract_mode,
)
from arnold.pipelines.megaplan.store import PlanRepository
from arnold.pipelines.megaplan.store import plan_repository as plan_repository_module
from arnold.pipelines.megaplan.cli import main as megaplan_cli_main


def _write_minimal_state(plan_dir) -> None:
    (plan_dir / "state.json").write_text(
        json.dumps(
            {
                "name": plan_dir.name,
                "idea": "idea",
                "current_state": "initialized",
                "iteration": 1,
                "created_at": "2026-06-06T00:00:00Z",
                "config": {},
                "sessions": {},
                "plan_versions": [],
                "history": [],
                "meta": {},
                "last_gate": {},
            }
        ),
        encoding="utf-8",
    )


def test_plan_repository_typed_artifact_envelope_reads_as_payload_while_legacy_shapes_pass_through(
    tmp_path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    registry = ContractSchemaRegistry(tmp_path)
    retained_schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "integer"}},
        "additionalProperties": False,
    }
    version = registry.register("review", retained_schema)

    typed_envelope = {
        "logical_type": "review",
        "schema_version": version,
        "payload": {"answer": 7},
    }
    (plan_dir / "typed.json").write_text(json.dumps(typed_envelope), encoding="utf-8")
    (plan_dir / "object.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (plan_dir / "array.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    (plan_dir / "scalar.json").write_text(json.dumps("plain-string"), encoding="utf-8")

    assert validate_payload_against_schema(
        typed_envelope["payload"],
        registry.get_schema(typed_envelope["schema_version"]),
    ).ok

    # M1 chokepoint contract: typed envelopes unwrap to the validated payload,
    # while legacy scalar/list/dict artifacts continue to pass through unchanged.
    assert repo.read_artifact_json("typed.json") == {"answer": 7}
    assert repo.read_artifact_json("object.json") == {"ok": True}
    assert repo.read_artifact_json("array.json") == [1, 2, 3]
    assert repo.read_artifact_json("scalar.json") == "plain-string"


def test_plan_repository_typed_envelope_requires_logical_type_root_schema_version_and_payload(
    tmp_path,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    invalid_missing_payload = {
        "logical_type": "finalize",
        "schema_version": "sha256:" + ("1" * 64),
    }
    invalid_missing_schema_version = {
        "logical_type": "finalize",
        "payload": {"tasks": []},
    }
    legacy_plain_object = {"tasks": []}

    (plan_dir / "missing-payload.json").write_text(
        json.dumps(invalid_missing_payload),
        encoding="utf-8",
    )
    (plan_dir / "missing-schema-version.json").write_text(
        json.dumps(invalid_missing_schema_version),
        encoding="utf-8",
    )
    (plan_dir / "legacy.json").write_text(json.dumps(legacy_plain_object), encoding="utf-8")

    # These assertions define the future repository contract: only the full M1
    # envelope is treated as typed; partial roots stay legacy/unknown and must
    # not be mistaken for a typed artifact.
    assert repo.read_artifact_json("missing-payload.json") == invalid_missing_payload
    assert repo.read_artifact_json("missing-schema-version.json") == invalid_missing_schema_version
    assert repo.read_artifact_json("legacy.json") == legacy_plain_object


@dataclass(frozen=True)
class _Binding:
    producer_typed: bool
    consumer_typed: bool


def test_step_io_policy_reuses_completion_mode_normalization_and_persists(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()

    policy = resolve_step_io_policy(
        configured_mode="not-a-mode",
        producer_typed=True,
        consumer_typed=True,
    )
    assert policy.configured_mode == normalize_contract_mode("not-a-mode")
    assert policy.effective_mode == "shadow"

    persisted = resolve_step_io_policy(
        configured_mode="warn",
        producer_typed=True,
        consumer_typed=True,
    )
    out = write_step_io_policy(plan_dir, persisted)
    assert out == step_io_policy_path(plan_dir)
    assert load_step_io_policy(plan_dir)["effective_mode"] == "warn"

    loaded = resolve_step_io_policy(plan_dir=plan_dir, binding=_Binding(True, True))
    assert loaded.configured_mode == "warn"
    assert loaded.effective_mode == "warn"


def test_step_io_policy_caps_warn_and_enforce_when_not_both_sides_typed() -> None:
    producer_only = resolve_step_io_policy(
        configured_mode="enforce",
        producer_typed=True,
        consumer_typed=False,
    )
    assert producer_only.configured_mode == "enforce"
    assert producer_only.effective_mode == "shadow"
    assert producer_only.enforcement_eligible is False

    fully_typed = resolve_step_io_policy(
        configured_mode="enforce",
        binding=_Binding(producer_typed=True, consumer_typed=True),
    )
    assert fully_typed.effective_mode == "enforce"
    assert fully_typed.enforcement_eligible is True


def test_step_io_policy_binding_lookup_fallback_caps_to_shadow() -> None:
    fallback = resolve_step_io_policy(configured_mode="enforce", binding=None)

    assert fallback.configured_mode == "enforce"
    assert fallback.effective_mode == "shadow"
    assert fallback.reason == "binding lookup unavailable"


def test_step_io_read_lenient_escape_flag_forces_shadow_without_weakening_writes(
    tmp_path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    registry = ContractSchemaRegistry(tmp_path)
    version = registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    write_step_io_policy(
        plan_dir,
        resolve_step_io_policy(
            configured_mode="enforce",
            producer_typed=True,
            consumer_typed=True,
        ),
    )
    typed_invalid = {
        "logical_type": "review",
        "schema_version": version,
        "payload": {"answer": "wrong"},
    }
    (plan_dir / "typed.json").write_text(json.dumps(typed_invalid), encoding="utf-8")

    monkeypatch.setenv(STEP_IO_READ_LENIENT_ENV, "1")

    assert step_io_read_lenient_escape_on() is True
    escaped_policy = resolve_step_io_policy(
        configured_mode="enforce",
        producer_typed=True,
        consumer_typed=True,
    )
    assert escaped_policy.effective_mode == "shadow"
    assert repo.read_artifact_json(
        "typed.json",
        contract_context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
        contract_binding=_Binding(producer_typed=True, consumer_typed=True),
    ) == {"answer": "wrong"}

    try:
        repo.write_artifact_json(
            "typed-out.json",
            typed_invalid,
            contract_context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
            contract_binding=_Binding(producer_typed=True, consumer_typed=True),
        )
    except ValueError as exc:
        assert "typed artifact write blocked" in str(exc)
    else:
        raise AssertionError("escape flag must not bypass strict typed writes")


def test_step_io_policy_only_enforce_blocks_invalid_typed_reads() -> None:
    invalid = StepIOContractDecision(
        classification=StepIOClassification.TYPED_INVALID,
        allow_read=True,
        allow_write=False,
        value={"answer": "wrong"},
        block_reason="typed artifact payload failed schema validation",
    )

    shadow = resolve_step_io_policy(
        configured_mode="shadow",
        producer_typed=True,
        consumer_typed=True,
    )
    enforce = resolve_step_io_policy(
        configured_mode="enforce",
        producer_typed=True,
        consumer_typed=True,
    )

    assert decision_blocks_read(invalid, shadow) is False
    assert decision_blocks_read(invalid, enforce) is True


def test_plan_repository_off_mode_skips_registry_policy_work_for_typed_envelopes(
    tmp_path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    policy = resolve_step_io_policy(
        configured_mode="off",
        producer_typed=True,
        consumer_typed=True,
    )
    write_step_io_policy(plan_dir, policy)

    typed_envelope = {
        "logical_type": "review",
        "schema_version": "sha256:" + ("1" * 64),
        "payload": {"answer": "schema is intentionally unavailable"},
    }
    (plan_dir / "typed.json").write_text(json.dumps(typed_envelope), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.store.plan_repository.decide_step_io_read",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("registry read path should be skipped")),
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.store.plan_repository.decide_step_io_write",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("registry write path should be skipped")),
    )

    assert repo.read_artifact_json("typed.json") == typed_envelope
    repo.write_artifact_json("typed-out.json", typed_envelope)
    assert json.loads((plan_dir / "typed-out.json").read_text(encoding="utf-8")) == typed_envelope


def test_plan_repository_uses_explicit_contract_context_for_typed_reads_and_writes(
    tmp_path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    registry = ContractSchemaRegistry(tmp_path)
    schema = {
        "type": "object",
        "required": ["answer"],
        "properties": {"answer": {"type": "integer"}},
        "additionalProperties": False,
    }
    version = registry.register("review", schema)
    typed_envelope = {
        "logical_type": "review",
        "schema_version": version,
        "payload": {"answer": 7},
    }
    (plan_dir / "typed.json").write_text(json.dumps(typed_envelope), encoding="utf-8")

    seen: dict[str, StepIOContractContext] = {}
    original_read = decide_step_io_read
    original_write = plan_repository_module.decide_step_io_write

    def _capture_read(value, context):
        seen["read"] = context
        return original_read(value, context)

    def _capture_write(value, context):
        seen["write"] = context
        return original_write(value, context)

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.store.plan_repository.decide_step_io_read",
        _capture_read,
    )
    monkeypatch.setattr(
        "arnold.pipelines.megaplan.store.plan_repository.decide_step_io_write",
        _capture_write,
    )

    context = StepIOContractContext(operation=StepIOOperation.READ, registry=registry)
    assert repo.read_artifact_json("typed.json", contract_context=context) == {"answer": 7}
    assert seen["read"] is context

    write_context = StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry)
    repo.write_artifact_json("typed-out.json", typed_envelope, contract_context=write_context)
    assert seen["write"] is write_context


def test_plan_repository_read_artifact_json_missing_files_and_legacy_values_are_unchanged(
    tmp_path,
    monkeypatch,
) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    legacy_values = {
        "object.json": {"ok": True},
        "array.json": [1, 2, 3],
        "scalar.json": "plain-string",
        "partial-envelope.json": {
            "logical_type": "review",
            "payload": {"answer": 7},
        },
    }
    for name, value in legacy_values.items():
        (plan_dir / name).write_text(json.dumps(value), encoding="utf-8")

    monkeypatch.setattr(
        "arnold.pipelines.megaplan.store.plan_repository.decide_step_io_read",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("legacy reads must stay on fast path")),
    )

    assert repo.read_artifact_json("missing.json") is None
    for name, value in legacy_values.items():
        assert repo.read_artifact_json(name) == value


def test_plan_repository_typed_invalid_read_shadows_with_payload_and_telemetry(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    registry = ContractSchemaRegistry(tmp_path)
    version = registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    write_step_io_policy(
        plan_dir,
        resolve_step_io_policy(
            configured_mode="shadow",
            producer_typed=True,
            consumer_typed=True,
        ),
    )
    envelope = {
        "logical_type": "review",
        "schema_version": version,
        "payload": {"answer": "wrong"},
    }
    (plan_dir / "typed.json").write_text(json.dumps(envelope), encoding="utf-8")

    assert repo.read_artifact_json(
        "typed.json",
        contract_context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
    ) == {"answer": "wrong"}
    records = read_violation_records(plan_dir / TELEMETRY_FILENAME)
    assert [record["classification"] for record in records] == ["typed_invalid"]
    assert records[0]["mode"] == "shadow"


def test_plan_repository_typed_invalid_read_blocks_in_enforce_and_emits_telemetry(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    registry = ContractSchemaRegistry(tmp_path)
    version = registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    write_step_io_policy(
        plan_dir,
        resolve_step_io_policy(
            configured_mode="enforce",
            producer_typed=True,
            consumer_typed=True,
        ),
    )
    (plan_dir / "typed.json").write_text(
        json.dumps(
            {
                "logical_type": "review",
                "schema_version": version,
                "payload": {"answer": "wrong"},
            }
        ),
        encoding="utf-8",
    )

    try:
        repo.read_artifact_json(
            "typed.json",
            contract_context=StepIOContractContext(operation=StepIOOperation.READ, registry=registry),
            contract_binding=_Binding(producer_typed=True, consumer_typed=True),
        )
    except ValueError as exc:
        assert "typed artifact read blocked" in str(exc)
    else:
        raise AssertionError("enforce mode must block invalid typed reads")

    records = read_violation_records(plan_dir / TELEMETRY_FILENAME)
    assert [record["classification"] for record in records] == ["typed_invalid"]
    assert records[0]["mode"] == "enforce"


def test_plan_repository_schema_unavailable_read_is_shadow_lenient(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    write_step_io_policy(
        plan_dir,
        resolve_step_io_policy(
            configured_mode="shadow",
            producer_typed=True,
            consumer_typed=True,
        ),
    )
    envelope = {
        "logical_type": "review",
        "schema_version": "sha256:" + ("1" * 64),
        "payload": {"answer": 7},
    }
    (plan_dir / "typed.json").write_text(json.dumps(envelope), encoding="utf-8")

    assert repo.read_artifact_json("typed.json") == {"answer": 7}
    records = read_violation_records(plan_dir / TELEMETRY_FILENAME)
    assert [record["classification"] for record in records] == ["schema_unavailable"]


def test_plan_repository_typed_invalid_write_rejects_before_persisting_bytes(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    registry = ContractSchemaRegistry(tmp_path)
    version = registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    write_step_io_policy(
        plan_dir,
        resolve_step_io_policy(
            configured_mode="enforce",
            producer_typed=True,
            consumer_typed=True,
        ),
    )
    target = plan_dir / "typed.json"
    target.write_text('{"old": true}\n', encoding="utf-8")
    before = target.read_bytes()

    try:
        repo.write_artifact_json(
            "typed.json",
            {
                "logical_type": "review",
                "schema_version": version,
                "payload": {"answer": "wrong"},
            },
            contract_context=StepIOContractContext(operation=StepIOOperation.WRITE, registry=registry),
            contract_binding=_Binding(producer_typed=True, consumer_typed=True),
        )
    except ValueError as exc:
        assert "typed artifact write blocked" in str(exc)
    else:
        raise AssertionError("invalid typed writes must fail closed")

    assert target.read_bytes() == before
    records = read_violation_records(plan_dir / TELEMETRY_FILENAME)
    assert [record["classification"] for record in records] == ["typed_invalid"]
    assert records[0]["operation"] == "write"


def test_plan_repository_schema_unavailable_write_rejects_without_creating_file(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    write_step_io_policy(
        plan_dir,
        resolve_step_io_policy(
            configured_mode="enforce",
            producer_typed=True,
            consumer_typed=True,
        ),
    )

    try:
        repo.write_artifact_json(
            "missing-schema.json",
            {
                "logical_type": "review",
                "schema_version": "sha256:" + ("1" * 64),
                "payload": {"answer": 7},
            },
            contract_binding=_Binding(producer_typed=True, consumer_typed=True),
        )
    except ValueError as exc:
        assert "typed artifact write blocked" in str(exc)
    else:
        raise AssertionError("schema-unavailable typed writes must fail closed")

    assert not (plan_dir / "missing-schema.json").exists()
    records = read_violation_records(plan_dir / TELEMETRY_FILENAME)
    assert [record["classification"] for record in records] == ["schema_unavailable"]


def test_plan_repository_legacy_untyped_write_still_succeeds(tmp_path) -> None:
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    _write_minimal_state(plan_dir)
    repo = PlanRepository.from_plan_dir(plan_dir)

    repo.write_artifact_json("legacy.json", {"logical_type": "review", "payload": {"answer": "freeform"}})

    assert json.loads((plan_dir / "legacy.json").read_text(encoding="utf-8")) == {
        "logical_type": "review",
        "payload": {"answer": "freeform"},
    }


def test_contract_cli_mode_set_is_honored_by_later_repository_call_and_violations_json(
    tmp_path,
    capsys,
) -> None:
    root = tmp_path / "project"
    plan_dir = root / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    _write_minimal_state(plan_dir)
    registry = ContractSchemaRegistry(root)
    version = registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    (plan_dir / "typed-valid.json").write_text(
        json.dumps(
            {
                "logical_type": "review",
                "schema_version": version,
                "payload": {"answer": 7},
            }
        ),
        encoding="utf-8",
    )

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "self-validate", "--plan", "plan"]
    ) == 0
    capsys.readouterr()

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "mode", "set", "enforce", "--plan", "plan"]
    ) == 0
    capsys.readouterr()

    repo = PlanRepository.from_plan_dir(plan_dir)
    try:
        repo.write_artifact_json(
            "typed.json",
            {
                "logical_type": "review",
                "schema_version": "sha256:" + ("1" * 64),
                "payload": {"answer": 7},
            },
            contract_binding=_Binding(producer_typed=True, consumer_typed=True),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("persisted enforce policy must block later typed invalid writes")

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "violations", "--plan", "plan", "--json"]
    ) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["success"] is True
    assert payload["violations"][0]["artifact"] == "typed.json"
    assert payload["violations"][0]["classification"] == "schema_unavailable"
    assert payload["violations"][0]["block_reason"]


def test_contract_cli_self_validate_refuses_vacuous_markers_and_gates_enforce_promotion(
    tmp_path,
    capsys,
) -> None:
    root = tmp_path / "project"
    plan_dir = root / ".megaplan" / "plans" / "plan"
    plan_dir.mkdir(parents=True)
    _write_minimal_state(plan_dir)
    (plan_dir / "legacy.json").write_text(json.dumps({"answer": 7}), encoding="utf-8")

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "mode", "set", "enforce", "--plan", "plan"]
    ) != 0
    assert "self-validate" in capsys.readouterr().out

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "self-validate", "--plan", "plan"]
    ) != 0
    assert "typed artifact" in capsys.readouterr().out

    registry = ContractSchemaRegistry(root)
    version = registry.register(
        "review",
        {
            "type": "object",
            "required": ["answer"],
            "properties": {"answer": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    (plan_dir / "typed-valid.json").write_text(
        json.dumps(
            {
                "logical_type": "review",
                "schema_version": version,
                "payload": {"answer": 7},
            }
        ),
        encoding="utf-8",
    )

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "self-validate", "--plan", "plan"]
    ) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["typed_artifacts"] == ["typed-valid.json"]
    assert load_step_io_policy(plan_dir)["self_validation"]["validated"] is True

    assert megaplan_cli_main(
        ["contract", "--project-dir", str(root), "mode", "set", "enforce", "--plan", "plan"]
    ) == 0


# ── telemetry serialization tests ────────────────────────────────────────────


from arnold.pipeline.step_io_telemetry import (
    TELEMETRY_FILENAME,
    StepIOViolationRecord,
    append_violation_record,
    emit_decision_telemetry,
    read_violation_records,
)


def _make_invalid_decision():
    from arnold.pipeline import StepIOClassification, StepIOContractDecision, StepIODiagnostic, StepIOEnvelope

    return StepIOContractDecision(
        classification=StepIOClassification.TYPED_INVALID,
        allow_read=True,
        allow_write=False,
        value={"answer": "wrong-type"},
        envelope=StepIOEnvelope(
            logical_type="review",
            schema_version="sha256:" + ("a" * 64),
            payload={"answer": "wrong-type"},
        ),
        diagnostics=(
            StepIODiagnostic(
                code="type_mismatch",
                message="expected integer, got string",
                payload_pointer="/answer",
                schema_pointer="/properties/answer/type",
            ),
        ),
        block_reason="typed artifact payload failed schema validation",
    )


def _make_enforce_policy():
    from arnold.pipeline import resolve_step_io_policy
    return resolve_step_io_policy(
        configured_mode="enforce",
        producer_typed=True,
        consumer_typed=True,
    )


def _make_off_policy():
    from arnold.pipeline import resolve_step_io_policy
    return resolve_step_io_policy(
        configured_mode="off",
        producer_typed=True,
        consumer_typed=True,
    )


def test_telemetry_violation_record_serializes_all_required_fields() -> None:
    """A violation record JSON contains seam, mode, artifact, operation,
    logical_type, schema_version, classification, and diagnostic_details."""
    decision = _make_invalid_decision()
    policy = _make_enforce_policy()
    record = StepIOViolationRecord.from_decision(
        decision=decision,
        policy=policy,
        artifact="review/result.json",
        operation="write",
    )

    data = record.to_json()
    assert data["seam"] == "step_io"
    assert data["mode"] == "enforce"
    assert data["artifact"] == "review/result.json"
    assert data["operation"] == "write"
    assert data["logical_type"] == "review"
    assert data["schema_version"] == "sha256:" + ("a" * 64)
    assert data["classification"] == "typed_invalid"
    assert len(data["diagnostic_details"]) == 1
    assert data["diagnostic_details"][0]["code"] == "type_mismatch"
    assert data["diagnostic_details"][0]["message"] == "expected integer, got string"
    assert data["block_reason"] == "typed artifact payload failed schema validation"
    assert data["record_schema_version"] == "1.0.0"
    assert "timestamp" in data


def test_telemetry_violation_record_json_roundtrips_through_jsonl(tmp_path) -> None:
    """A violation record written via append_violation_record can be read
    back through read_violation_records with all fields intact."""
    decision = _make_invalid_decision()
    policy = _make_enforce_policy()
    record = StepIOViolationRecord.from_decision(
        decision=decision,
        policy=policy,
        artifact="review/result.json",
        operation="write",
    )

    telemetry_path = tmp_path / TELEMETRY_FILENAME
    append_violation_record(telemetry_path, record)

    records = read_violation_records(telemetry_path)
    assert len(records) == 1
    assert records[0]["seam"] == "step_io"
    assert records[0]["classification"] == "typed_invalid"
    assert len(records[0]["diagnostic_details"]) == 1


def test_telemetry_emit_decision_returns_none_and_writes_nothing_for_off_mode(
    tmp_path,
) -> None:
    """emit_decision_telemetry returns None and produces no file when
    policy effective_mode is off."""
    decision = _make_invalid_decision()
    policy = _make_off_policy()
    telemetry_path = tmp_path / TELEMETRY_FILENAME

    result = emit_decision_telemetry(
        decision=decision,
        policy=policy,
        artifact="r.json",
        operation="read",
        telemetry_path=telemetry_path,
    )
    assert result is None
    assert not telemetry_path.exists()


def test_telemetry_emit_decision_returns_none_for_typed_valid(tmp_path) -> None:
    """emit_decision_telemetry does not emit records for typed_valid
    classifications even under enforce mode."""
    from arnold.pipeline import StepIOClassification, StepIOContractDecision

    valid_decision = StepIOContractDecision(
        classification=StepIOClassification.TYPED_VALID,
        allow_read=True,
        allow_write=True,
        value={"answer": 42},
    )
    policy = _make_enforce_policy()
    telemetry_path = tmp_path / TELEMETRY_FILENAME

    result = emit_decision_telemetry(
        decision=valid_decision,
        policy=policy,
        artifact="r.json",
        operation="read",
        telemetry_path=telemetry_path,
    )
    assert result is None
    assert not telemetry_path.exists()


def test_telemetry_emit_decision_returns_none_for_legacy_unknown(tmp_path) -> None:
    """emit_decision_telemetry does not emit records for legacy_unknown
    classifications even under enforce mode."""
    from arnold.pipeline import StepIOClassification, StepIOContractDecision

    legacy_decision = StepIOContractDecision(
        classification=StepIOClassification.LEGACY_UNKNOWN,
        allow_read=True,
        allow_write=True,
        value={"old": "shape"},
    )
    policy = _make_enforce_policy()
    telemetry_path = tmp_path / TELEMETRY_FILENAME

    result = emit_decision_telemetry(
        decision=legacy_decision,
        policy=policy,
        artifact="r.json",
        operation="read",
        telemetry_path=telemetry_path,
    )
    assert result is None
    assert not telemetry_path.exists()


def test_telemetry_read_violation_records_returns_empty_for_missing_file() -> None:
    """read_violation_records returns [] when the telemetry file does not exist."""
    records = read_violation_records("/tmp/nonexistent_step_io_contract_violations.jsonl")
    assert records == []


def test_telemetry_multiple_records_appended_and_read_in_order(tmp_path) -> None:
    """Multiple violation records are appended and read back in insertion order."""
    decision = _make_invalid_decision()
    policy = _make_enforce_policy()
    telemetry_path = tmp_path / TELEMETRY_FILENAME

    for i in range(3):
        record = StepIOViolationRecord.from_decision(
            decision=decision,
            policy=policy,
            artifact=f"artifact_{i}.json",
            operation="write",
        )
        append_violation_record(telemetry_path, record)

    records = read_violation_records(telemetry_path)
    assert len(records) == 3
    assert [r["artifact"] for r in records] == [
        "artifact_0.json",
        "artifact_1.json",
        "artifact_2.json",
    ]


def test_telemetry_emit_decision_returns_record_for_schema_unavailable(tmp_path) -> None:
    """emit_decision_telemetry writes a record for schema_unavailable classification."""
    from arnold.pipeline import StepIOClassification, StepIOContractDecision, StepIODiagnostic, StepIOEnvelope

    schema_unavail_decision = StepIOContractDecision(
        classification=StepIOClassification.SCHEMA_UNAVAILABLE,
        allow_read=True,
        allow_write=False,
        value={"payload": "orphaned"},
        envelope=StepIOEnvelope(
            logical_type="execute",
            schema_version="sha256:" + ("b" * 64),
            payload={"payload": "orphaned"},
        ),
        diagnostics=(
            StepIODiagnostic(
                code="schema_unavailable",
                message="typed artifact schema is unavailable",
            ),
        ),
        block_reason="typed artifact schema is unavailable",
    )
    policy = _make_enforce_policy()
    telemetry_path = tmp_path / TELEMETRY_FILENAME

    result = emit_decision_telemetry(
        decision=schema_unavail_decision,
        policy=policy,
        artifact="execute/batch.json",
        operation="read",
        telemetry_path=telemetry_path,
    )

    assert result is not None
    assert result.classification == "schema_unavailable"
    assert telemetry_path.exists()

    records = read_violation_records(telemetry_path)
    assert len(records) == 1
    assert records[0]["classification"] == "schema_unavailable"
    assert records[0]["logical_type"] == "execute"
    assert records[0]["operation"] == "read"
