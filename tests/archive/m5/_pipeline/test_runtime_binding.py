"""T11b — runtime port-binding tests.

Covers:
* Typed port bound correctly flag-ON via Pipeline.binding_map → ctx.inputs
  is populated with the upstream artifact path.
* Unbindable consume (missing binding_map entry OR no upstream artifact)
  raises :class:`PortBindError`.
* Flag-OFF: legacy ``v1.md`` fallback in :func:`resolve_inputs` still
  fires unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from arnold.pipeline import ContractResult
from arnold.pipelines.megaplan._pipeline.contracts import PortBindError
from arnold.pipelines.megaplan._pipeline.executor import (
    _prepare_enforcement_binding,
    run_pipeline,
)
from arnold.pipelines.megaplan._pipeline.step_io_policy_adapter import STEP_IO_POLICY_ENV
from arnold.pipelines.megaplan._pipeline.step_helpers import resolve_inputs
from arnold.pipelines.megaplan._pipeline.types import (
    Edge,
    Pipeline,
    Port,
    PortRef,
    Stage,
    StepContext,
    StepResult,
)
from arnold.pipeline.step_io_telemetry import TELEMETRY_FILENAME, read_violation_records


@dataclass
class _ProducerStep:
    """Writes a fixed artifact at <plan_dir>/<name>/v1.md."""

    name: str
    kind: str = "produce"
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        out_dir = ctx.plan_dir / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "v1.md"
        path.write_text(f"hello from {self.name}", encoding="utf-8")
        return StepResult(outputs={self.name: path}, next="next")


@dataclass
class _ContractProducerStep:
    name: str
    payload: dict
    write_output: bool = False
    kind: str = "produce"
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        outputs = {}
        if self.write_output:
            out_dir = ctx.plan_dir / self.name
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / "v1.json"
            path.write_text('{"ok": true}', encoding="utf-8")
            outputs[self.name] = path
        return StepResult(
            outputs=outputs,
            state_patch={"producer_merged": True},
            contract_result=ContractResult(payload=self.payload),
            next="next",
        )


@dataclass
class _ConsumerStep:
    """Records the resolved ctx.inputs[port_name] into state_patch."""

    name: str
    consume_name: str
    consume_ct: str = "text/markdown"
    kind: str = "produce"
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.consumes:
            self.consumes = (
                PortRef(port_name=self.consume_name, content_type=self.consume_ct),
            )

    def run(self, ctx: StepContext) -> StepResult:
        seen = ctx.inputs.get(self.consume_name)
        return StepResult(
            outputs={},
            state_patch={"seen_path": str(seen) if seen is not None else None},
            next="halt",
        )


@dataclass
class _StateOnlyConsumerStep:
    name: str
    kind: str = "consume"
    produces: tuple = field(default_factory=tuple)
    consumes: tuple = field(default_factory=tuple)

    def run(self, ctx: StepContext) -> StepResult:
        return StepResult(
            outputs={},
            state_patch={"consumer_merged": True},
            next="halt",
        )


def _mk_pipeline(producer: _ProducerStep, consumer: _ConsumerStep, *, binding_map):
    stages = {
        producer.name: Stage(
            name=producer.name,
            step=producer,
            edges=(Edge(label="next", target=consumer.name),),
        ),
        consumer.name: Stage(
            name=consumer.name,
            step=consumer,
            edges=(),
        ),
    }
    return Pipeline(
        stages=stages,
        entry=producer.name,
        binding_map=binding_map,
    )


@pytest.fixture(autouse=True)
def _isolate_flag(monkeypatch):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)
    yield


def test_typed_port_bound_correctly_flag_on(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="msg")
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={("cons", "msg"): ("prod", "msg")},
    )

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert out["state"]["seen_path"] == str(tmp_path / "prod" / "v1.md")


def test_unbindable_consume_raises_port_bind_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="ghost")
    # binding_map intentionally omits ("cons", "ghost").
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={},
    )

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    with pytest.raises(PortBindError) as ei:
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)
    assert ei.value.step_id == "cons"
    assert ei.value.consume_name == "ghost"


def test_flag_off_v1md_fallback_unchanged(tmp_path, monkeypatch):
    # Flag explicitly off: resolve_inputs should fall back to the legacy
    # v1.md path for any ref that is not in ctx.inputs and has no
    # produced artifact yet — and NOT raise PortBindError.
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "0")

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    resolved = resolve_inputs(["unproduced"], ctx)
    assert resolved == {"unproduced": tmp_path / "unproduced" / "v1.md"}


def test_flag_on_resolve_inputs_raises_on_miss(tmp_path, monkeypatch):
    monkeypatch.setenv("MEGAPLAN_TYPED_PORTS", "1")

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )
    with pytest.raises(PortBindError):
        resolve_inputs(["unproduced"], ctx)


def test_executor_startup_builds_enforcement_binding_once_with_typed_ports_true(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)

    from arnold.pipeline import contracts

    real_bind = contracts.bind
    calls = []

    def spy_bind(steps, edges, *, typed_ports=True):
        calls.append(
            {
                "steps": steps,
                "edges": tuple(edges),
                "typed_ports": typed_ports,
            }
        )
        return real_bind(steps, edges, typed_ports=typed_ports)

    monkeypatch.setattr(contracts, "bind", spy_bind)

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="msg")
    pipeline = _mk_pipeline(producer, consumer, binding_map=None)

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )

    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert len(calls) == 1
    assert calls[0]["typed_ports"] is True
    assert calls[0]["edges"] == (("prod", "cons"),)
    assert out["state"]["seen_path"] is None


def test_prepare_enforcement_binding_lowers_authored_stage_reads_and_writes(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)

    producer = _ProducerStep(name="prod")
    consumer = _ConsumerStep(name="cons", consume_name="msg")
    stages = {
        producer.name: Stage(
            name=producer.name,
            step=producer,
            edges=(Edge(label="next", target=consumer.name),),
            writes=(Port(name="msg", content_type="text/markdown"),),
        ),
        consumer.name: Stage(
            name=consumer.name,
            step=consumer,
            edges=(),
            reads=(PortRef(port_name="msg", content_type="text/markdown"),),
        ),
    }
    pipeline = Pipeline(stages=stages, entry=producer.name, binding_map=None)

    binding = _prepare_enforcement_binding(
        pipeline,
        artifact_root=tmp_path,
    )

    assert binding.diagnostics is None
    assert binding.binding_map == {("cons", "msg"): ("prod", "msg")}


def test_executor_startup_reuses_existing_binding_map_without_rebinding(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)

    from arnold.pipeline import contracts

    def fail_bind(*args, **kwargs):
        raise AssertionError("existing binding_map should be reused")

    monkeypatch.setattr(contracts, "bind", fail_bind)

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="msg")
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={("cons", "msg"): ("prod", "msg")},
    )

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )

    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert out["state"]["seen_path"] is None


def test_executor_startup_caches_binding_diagnostics_and_emits_telemetry_without_crashing_legacy_startup(
    tmp_path,
    monkeypatch,
):
    monkeypatch.delenv("MEGAPLAN_TYPED_PORTS", raising=False)

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="ghost")
    pipeline = _mk_pipeline(producer, consumer, binding_map=None)

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )

    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert out["state"]["seen_path"] is None
    records = read_violation_records(tmp_path / TELEMETRY_FILENAME)
    assert len(records) == 1
    assert records[0]["classification"] == "binding_unavailable"
    assert records[0]["artifact"] == "executor_binding"
    assert records[0]["operation"] == "bind"
    assert records[0]["seam"] == "executor_startup"


def test_executor_handoff_blocks_after_state_merge_and_before_cursor_dispatch(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(STEP_IO_POLICY_ENV, "enforce")

    producer = _ContractProducerStep(
        name="prod",
        payload={
            "logical_type": "review",
            "schema_version": "v1",
            "payload": {"answer": 7},
        },
        produces=(Port(name="msg", content_type="application/json", logical_type="review"),),
    )
    consumer = _ConsumerStep(
        name="cons",
        consume_name="msg",
        consume_ct="application/json",
    )
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={("cons", "msg"): ("prod", "msg")},
    )

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )

    with pytest.raises(ValueError, match="Step IO handoff blocked") as excinfo:
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    message = str(excinfo.value)
    assert "producer_stage='prod'" in message
    assert "consumer_stage='cons'" in message
    assert "failure_code='schema_unavailable'" in message
    assert "logical_type='review'" in message
    assert "Suggested author action:" in message
    assert (tmp_path / "state.json").read_text(encoding="utf-8")
    assert read_violation_records(tmp_path / TELEMETRY_FILENAME)[0]["classification"] == "schema_unavailable"


def test_executor_binding_unavailable_transition_blocks_under_enforce(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(STEP_IO_POLICY_ENV, "enforce")

    producer = _ContractProducerStep(
        name="prod",
        payload={
            "logical_type": "review",
            "schema_version": "sha256:" + "b" * 64,
            "payload": {"answer": "not validated"},
        },
        produces=(Port(name="msg", content_type="application/json", logical_type="review"),),
    )
    consumer = _ConsumerStep(
        name="cons",
        consume_name="ghost",
        consume_ct="application/json",
    )
    pipeline = _mk_pipeline(producer, consumer, binding_map=None)

    ctx = StepContext(
        plan_dir=tmp_path,
        state={},
        profile=None,
        mode="test",
    )

    with pytest.raises(ValueError, match="Step IO handoff blocked") as excinfo:
        run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    message = str(excinfo.value)
    assert "producer_stage='prod'" in message
    assert "consumer_stage='cons'" in message
    assert "failure_code='binding_unavailable'" in message
    assert "Suggested author action:" in message
    records = read_violation_records(tmp_path / TELEMETRY_FILENAME)
    transition_records = [record for record in records if record["operation"] == "write"]
    assert transition_records[0]["classification"] == "binding_unavailable"
    assert transition_records[0]["mode"] == "enforce"


def test_executor_typed_to_untyped_transition_passes_through_and_preserves_outputs_and_state_patch(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(STEP_IO_POLICY_ENV, "enforce")

    producer = _ContractProducerStep(
        name="prod",
        payload={
            "logical_type": "review",
            "schema_version": "sha256:" + "d" * 64,
            "payload": {"answer": "opaque"},
        },
        write_output=True,
        produces=(Port(name="msg", content_type="application/json", logical_type="review"),),
    )
    consumer = _StateOnlyConsumerStep(name="cons")
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={},
    )

    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert out["state"]["producer_merged"] is True
    assert out["state"]["consumer_merged"] is True
    assert (tmp_path / "prod" / "v1.json").exists()
    records = read_violation_records(tmp_path / TELEMETRY_FILENAME)
    assert records == []


def test_executor_untyped_to_typed_transition_passes_through_and_preserves_outputs_and_state_patch(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(STEP_IO_POLICY_ENV, "enforce")

    producer = _ContractProducerStep(
        name="prod",
        payload={
            "logical_type": "review",
            "schema_version": "sha256:" + "e" * 64,
            "payload": {"answer": "opaque"},
        },
        write_output=True,
        produces=(),
    )
    consumer = _ConsumerStep(
        name="cons",
        consume_name="msg",
        consume_ct="application/json",
        consumes=(PortRef("msg", "application/json", logical_type="review"),),
    )
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={("cons", "msg"): ("prod", "msg")},
    )

    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert out["state"]["producer_merged"] is True
    assert out["state"]["seen_path"] is None
    assert (tmp_path / "prod" / "v1.json").exists()
    records = read_violation_records(tmp_path / TELEMETRY_FILENAME)
    assert records == []


def test_executor_without_contract_result_keeps_legacy_transition_behavior(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(STEP_IO_POLICY_ENV, "enforce")

    producer = _ProducerStep(
        name="prod",
        produces=(Port(name="msg", content_type="text/markdown"),),
    )
    consumer = _ConsumerStep(name="cons", consume_name="msg")
    pipeline = _mk_pipeline(
        producer,
        consumer,
        binding_map={("cons", "msg"): ("prod", "msg")},
    )

    ctx = StepContext(plan_dir=tmp_path, state={}, profile=None, mode="test")
    out = run_pipeline(pipeline, ctx, artifact_root=tmp_path)

    assert out["state"]["seen_path"] is None
    assert (tmp_path / "prod" / "v1.md").exists()
    telemetry_path = tmp_path / TELEMETRY_FILENAME
    assert not telemetry_path.exists()


def test_executor_binding_unavailable_transition_blocks_only_under_enforce_mode(
    tmp_path,
    monkeypatch,
):
    producer = _ContractProducerStep(
        name="prod",
        payload={
            "logical_type": "review",
            "schema_version": "sha256:" + "f" * 64,
            "payload": {"answer": "not validated"},
        },
        produces=(Port(name="msg", content_type="application/json", logical_type="review"),),
    )
    consumer = _ConsumerStep(
        name="cons",
        consume_name="ghost",
        consume_ct="application/json",
    )
    pipeline = _mk_pipeline(producer, consumer, binding_map=None)

    modes = {}
    for mode in ("enforce", "shadow"):
        monkeypatch.setenv(STEP_IO_POLICY_ENV, mode)
        run_dir = tmp_path / mode
        run_dir.mkdir()
        ctx = StepContext(plan_dir=run_dir, state={}, profile=None, mode="test")
        if mode == "enforce":
            with pytest.raises(ValueError, match="Step IO handoff blocked"):
                run_pipeline(pipeline, ctx, artifact_root=run_dir)
            out_state = None
        else:
            out = run_pipeline(pipeline, ctx, artifact_root=run_dir)
            out_state = out["state"]
        records = read_violation_records(run_dir / TELEMETRY_FILENAME)
        transition_records = [record for record in records if record["operation"] == "write"]
        modes[mode] = {
            "state": out_state,
            "record": transition_records[0],
        }

    assert modes["enforce"]["state"] is None
    assert modes["shadow"]["state"]["producer_merged"] is True
    assert modes["enforce"]["record"]["classification"] == "binding_unavailable"
    assert modes["shadow"]["record"]["classification"] == "binding_unavailable"
    assert modes["enforce"]["record"]["mode"] == "enforce"
    assert modes["shadow"]["record"]["mode"] == "shadow"
