**Native Python Runtime Spec**

**Premise**

A true native runtime cannot resume a normal CPython coroutine frame after process death. So `@pipeline async def ...` must be treated as author-facing Python that is compiled once into a resumable native state machine. It is still not the graph executor: execution follows the Python program’s await/branch/loop semantics, but the runtime owns checkpoint labels, frame state, eventing, contracts, and graph projection.

Proposed modules:

- `arnold.pipeline.native.decorators`: `@pipeline`, `@phase`, `@decision`
- `arnold.pipeline.native.compiler`: AST/source-to-resumable-program lowering
- `arnold.pipeline.native.runtime`: execution loop, resume, phase dispatch
- `arnold.pipeline.native.context`: `NativeRunContext`, frame stack, artifact roots
- `arnold.pipeline.native.checkpoint`: checkpoint serialization and cursor I/O
- `arnold.pipeline.native.contracts`: bridge to `Port`, `PortRef`, `contracts.bind`, `evaluate_step_io_handoff`
- `arnold.pipeline.native.graph`: derived `Pipeline` projection for validation/capsules
- `arnold.pipelines.megaplan.native_hooks`: Megaplan policy, state merge, overrides, WAL, subloop promotion

**1. Runtime Architecture**

Decorators register metadata; they do not execute orchestration themselves.

```python
@phase(
  name="gate",
  consumes=(critique_contract.consumer_port("critique_payload"),),
  produces=(gate_contract.producer_port("gate_payload"),),
)
async def gate(critique: Critique) -> Verdict: ...
```

`@pipeline("megaplan")` wraps the async function in a `NativePipelineDef`:

```python
@dataclass
class NativePipelineDef:
    name: str
    source_path: Path
    function_qualname: str
    compiled_program: NativeProgram
    phase_registry: dict[str, PhaseDef]
    graph_projection: Pipeline
```

The compiler rewrites every awaited native phase/decision/subpipeline call into a resumable operation:

```python
draft = await prep(inputs)
```

becomes conceptually:

```python
draft = await runtime.await_phase(
    checkpoint_id="megaplan:prep:001",
    phase="prep",
    args={"inputs": inputs},
    locals_schema=...
)
```

Runtime loop:

1. Load `NativeRunState`.
2. Enter compiled state machine at `cursor.frame_stack[-1].next_checkpoint`.
3. For each phase await:
   - persist pre-call checkpoint,
   - validate inputs against consumer ports,
   - inject override if `@decision`,
   - run phase body unless result already completed,
   - validate produced `ContractResult`,
   - merge outputs/state/envelope,
   - write `state.json`, `events.ndjson`, cursor.
4. Continue Python branch/loop logic in the compiled state machine.
5. Return terminal result or suspension.

Existing `ExecutorHooks` concepts map into `NativeRuntimeHooks`: `on_phase_start`, `on_phase_end`, `on_phase_error`, `merge_state`, `should_suspend`, `should_halt_loop`, `on_handoff`, `on_checkpoint`.

**2. Checkpoint / Resume**

Persist at every awaited `@phase`, `@decision`, and `run_subpipeline`.

Checkpoint document:

```json
{
  "schema_version": 1,
  "runtime": "native-python",
  "pipeline": "megaplan",
  "run_id": "...",
  "pipeline_manifest_hash": "sha256:...",
  "runtime_topology_hash": "sha256:...",
  "frame_stack": [
    {
      "pipeline": "megaplan",
      "frame_id": "root",
      "function": "arnold.pipelines.megaplan.pipeline:megaplan",
      "next_checkpoint": "gate@L42#2",
      "last_completed_checkpoint": "critique@L41#2",
      "loop_counters": {"main_review_loop": 2},
      "locals": {
        "plan": {"kind": "contract_ref", "producer": "plan", "port": "plan_payload"},
        "revision": null,
        "critique": {"kind": "contract_ref", "producer": "critique", "port": "critique_payload"}
      }
    }
  ],
  "input": null,
  "suspension": null
}
```

Durable file shape for compatibility:

```json
{
  "stage": "gate",
  "resume_cursor": "{\"kind\":\"native_checkpoint\",\"checkpoint\":\"gate@L42#2\"}",
  "kind": "native_checkpoint",
  "phase": "gate",
  "pipeline": "megaplan",
  "pipeline_manifest_hash": "sha256:...",
  "runtime_topology_hash": "sha256:...",
  "frame_stack": [...]
}
```

Rules:

- `stage` remains present for existing resume readers.
- `phase` mirrors `stage` for legacy Megaplan cursors.
- `frame_stack` handles nested subpipelines.
- Loop position is not inferred from stage name; it is stored in `loop_counters` and `next_checkpoint`.
- Locals must be JSON/schema serializable or contract/artifact refs. Non-serializable live locals crossing a checkpoint are a compile-time/runtime error.

Resume algorithm:

1. Read `resume_cursor.json`; if absent, inspect `state["resume_cursor"]`.
2. Rebuild state from `events.ndjson` using `fold_journal(..., kind_filter="state_written", last_state_snapshot_projector)` and overlay `state.json` only as legacy authority where Megaplan requires it.
3. Rehydrate contract refs from `__contract_results__`, artifacts, and typed payload envelopes.
4. Jump to `next_checkpoint`; completed checkpoint IDs are not re-run.

**3. Handoff / Contract Enforcement**

Native phases still declare `produces: tuple[Port]` and `consumes: tuple[PortRef]`.

At compile time:

- Build a derived `Pipeline` with stages/edges/checkpoint nodes.
- Run `contracts.bind(stages, edges, typed_ports=True)`.
- Store `binding_map` on `NativePipelineDef`.

At runtime:

- Producer return values are normalized to `ContractResult`.
- For Megaplan planning payloads, continue using `produce_payload_result()` / `with_stage_payload_result()` from `pipeline_contracts.py`.
- Before a consumer phase receives a value, call `evaluate_step_io_handoff()` with the resolved seam, producer port, consumer port, policy from `resolve_megaplan_step_io_policy()`, and telemetry path `step_io_telemetry`.
- Enforcement blocks before local assignment/state merge, matching `arnold.pipeline.executor` and Megaplan `_evaluate_cursor_handoff`.

**4. Override Injection**

`@decision` phases are intercepted before the decision body runs.

```python
async def await_decision(checkpoint, phase, args):
    override = override_policy.next_applicable(state, phase)
    if override:
        return synthesize_decision_result(override)
    return await run_phase_body(...)
```

For Megaplan:

- Read `state["meta"]["overrides"]` and the operation catalog from `planning.operations.override_catalog()`.
- Normalize CLI spelling with `routing.cli_to_internal_override()`.
- Emit `override_applied` exactly through existing observability helpers.
- Return a verdict with `override="force_proceed"` / `override="abort"` so routing priority matches `resolve_edge`: halt, override, decision, normal.
- The phase body is skipped for true control overrides; `add-note`, `set-model`, etc. remain state/config mutations consumed by later phase bodies.

**5. Subloops / Nested Pipelines**

`run_subpipeline(child, inputs, promote=..., artifact_subdir=...)` creates a child frame:

- artifact root: `parent_plan_dir / artifact_subdir`
- state: shallow copy of parent state
- envelope: child `RunEnvelope`, joined back after completion
- contract registry: inherited
- event journal: child writes under child root unless configured to also emit parent-scoped summary events

Child state never mutates parent directly. Promotion returns a `ChildRunResult` and a parent `StateDelta`, preserving current `SubloopStep` behavior:

- `subloop:<name>:state`
- `subloop:<name>:recommendation`
- optional `subloop:<name>:resume_cursor`

If child suspends, parent suspends with either the child cursor or a composite cursor:

```json
{
  "kind": "composite_suspension",
  "version": 1,
  "phase": "tiebreaker",
  "children": {"tiebreaker": {...}},
  "pending_suspensions": [...]
}
```

**6. Event Journal And State Persistence**

Native runtime writes the same files:

- `state.json`
- `events.ndjson`
- `resume_cursor.json`
- artifacts under per-phase directories

Use existing writers:

- `write_plan_state(..., mode="executor-key-merge", executor_owned_keys=...)`
- `observability.events.emit_state_written(...)`
- `EventKind.PHASE_START`, `PHASE_END`, `STATE_WRITTEN`, `ACTIVATION_TRANSITIONED`, `OVERRIDE_APPLIED`
- `RuntimeEnvelope._to_jsonable()` in `state["runtime_envelope"]`

Each phase boundary persists:

```json
{
  "_pipeline_name": "megaplan",
  "_pipeline_manifest_hash": "...",
  "runtime_envelope": {...},
  "__contract_results__": {...},
  "resume_cursor": {...},
  "...existing Megaplan state keys...": "..."
}
```

Order:

1. phase result produced or suspension result synthesized,
2. contract result stored,
3. envelope joined,
4. suspension cursor persisted if needed,
5. state merged to disk,
6. `state_written` WAL event emitted.

**7. Graph Derivation**

`arnold.pipeline.native.graph.derive_pipeline(native_def)` returns a normal `Pipeline`.

Inputs:

- decorator metadata for phase names, ports, vocabularies,
- AST control-flow pass for `if`, `while`, `break`, `continue`, `run_subpipeline`,
- observed runtime topology for dynamic branches.

For Megaplan, derived graph must match current nine-stage layout:

`prep → plan → critique → gate → revise/finalize/tiebreaker/escalate → execute → review`.

Projection must be accepted by `validator.validate_control_flow()` and compatible with `runtime_topology_projection_for_pipeline()`:

- stages include phase/checkpoint names,
- edges include `kind="decision"` / `kind="override"`,
- ports and `binding_map` match current `Port`/`PortRef` contracts,
- topology hash uses the same canonical JSON approach as `behavioral_manifest.py`.

Static graph is “possible topology”; runtime graph is “observed topology”. Capsules use static behavioral hash plus runtime topology hash as today.

**8. Migration Strategy**

Phase 0: Build parity corpus. Capture current Megaplan traces: stage sequence, `state.json`, `events.ndjson` fold, cursors, artifacts, topology hash.

Phase 1: Add native decorators and graph projection only. No native execution yet. `build_pipeline()` still returns graph.

Phase 2: Implement native runtime behind feature flag for test-only pipelines.

Phase 3: Port a small Megaplan pipeline. Prove event/state/cursor parity.

Phase 4: Implement Megaplan native hooks: state merge, override policy, step-IO policy, envelope join, suspension lift.

Phase 5: Port main Megaplan pipeline but default existing runs to old graph executor. New runs may opt into native.

Phase 6: In-flight compatibility. If `state.json.runtime_envelope.runtime == "graph"` or cursor lacks `kind="native_checkpoint"`, resume with legacy executor. Native may also accept `{"stage": "gate"}` by mapping stage to the first checkpoint for that phase, but old graph fallback is safer.

Phase 7: Flip default for new runs. Keep legacy executor read-only for old plans until a deprecation window passes.

Phase 8: Remove graph execution only after all active plans either finish or migrate through an explicit cursor-upgrade command.

**9. Risks And Mitigations**

Biggest risk: resumable Python locals. Mitigation: AST state-machine lowering, no frame pickling, strict serializable-locals check.

Semantic drift from graph executor. Mitigation: parity tests for every phase boundary and WAL fold.

Dynamic topology lying to dashboards. Mitigation: separate static possible graph from observed runtime graph; hash both explicitly.

Override ordering. Mitigation: intercept before `@decision` body and route through `verdict.override`, matching resolver priority.

Subloop suspension loss. Mitigation: frame-stack cursors and composite cursor writer.

Contract bypass. Mitigation: all phase returns become `ContractResult`; enforce before consumer assignment.

In-flight breakage. Mitigation: keep legacy graph runner for graph-born runs.

**10. Effort Estimate**

Large: roughly 8-12 engineering weeks for a production-grade first version, more if parallel panels are included.

What makes it large: durable Python state-machine compilation, exact WAL/state parity, contract enforcement outside edge traversal, nested suspension semantics, topology hashing, and compatibility with existing active plans. The implementation is effectively a second executor plus a graph projection layer.
tokens used
133,719
**Native Python Runtime Spec**

**Premise**

A true native runtime cannot resume a normal CPython coroutine frame after process death. So `@pipeline async def ...` must be treated as author-facing Python that is compiled once into a resumable native state machine. It is still not the graph executor: execution follows the Python program’s await/branch/loop semantics, but the runtime owns checkpoint labels, frame state, eventing, contracts, and graph projection.

Proposed modules:

- `arnold.pipeline.native.decorators`: `@pipeline`, `@phase`, `@decision`
- `arnold.pipeline.native.compiler`: AST/source-to-resumable-program lowering
- `arnold.pipeline.native.runtime`: execution loop, resume, phase dispatch
- `arnold.pipeline.native.context`: `NativeRunContext`, frame stack, artifact roots
- `arnold.pipeline.native.checkpoint`: checkpoint serialization and cursor I/O
- `arnold.pipeline.native.contracts`: bridge to `Port`, `PortRef`, `contracts.bind`, `evaluate_step_io_handoff`
- `arnold.pipeline.native.graph`: derived `Pipeline` projection for validation/capsules
- `arnold.pipelines.megaplan.native_hooks`: Megaplan policy, state merge, overrides, WAL, subloop promotion

**1. Runtime Architecture**

Decorators register metadata; they do not execute orchestration themselves.

```python
@phase(
  name="gate",
  consumes=(critique_contract.consumer_port("critique_payload"),),
  produces=(gate_contract.producer_port("gate_payload"),),
)
async def gate(critique: Critique) -> Verdict: ...
```

`@pipeline("megaplan")` wraps the async function in a `NativePipelineDef`:

```python
@dataclass
class NativePipelineDef:
    name: str
    source_path: Path
    function_qualname: str
    compiled_program: NativeProgram
    phase_registry: dict[str, PhaseDef]
    graph_projection: Pipeline
```

The compiler rewrites every awaited native phase/decision/subpipeline call into a resumable operation:

```python
draft = await prep(inputs)
```

becomes conceptually:

```python
draft = await runtime.await_phase(
    checkpoint_id="megaplan:prep:001",
    phase="prep",
    args={"inputs": inputs},
    locals_schema=...
)
```

Runtime loop:

1. Load `NativeRunState`.
2. Enter compiled state machine at `cursor.frame_stack[-1].next_checkpoint`.
3. For each phase await:
   - persist pre-call checkpoint,
   - validate inputs against consumer ports,
   - inject override if `@decision`,
   - run phase body unless result already completed,
   - validate produced `ContractResult`,
   - merge outputs/state/envelope,
   - write `state.json`, `events.ndjson`, cursor.
4. Continue Python branch/loop logic in the compiled state machine.
5. Return terminal result or suspension.

Existing `ExecutorHooks` concepts map into `NativeRuntimeHooks`: `on_phase_start`, `on_phase_end`, `on_phase_error`, `merge_state`, `should_suspend`, `should_halt_loop`, `on_handoff`, `on_checkpoint`.

**2. Checkpoint / Resume**

Persist at every awaited `@phase`, `@decision`, and `run_subpipeline`.

Checkpoint document:

```json
{
  "schema_version": 1,
  "runtime": "native-python",
  "pipeline": "megaplan",
  "run_id": "...",
  "pipeline_manifest_hash": "sha256:...",
  "runtime_topology_hash": "sha256:...",
  "frame_stack": [
    {
      "pipeline": "megaplan",
      "frame_id": "root",
      "function": "arnold.pipelines.megaplan.pipeline:megaplan",
      "next_checkpoint": "gate@L42#2",
      "last_completed_checkpoint": "critique@L41#2",
      "loop_counters": {"main_review_loop": 2},
      "locals": {
        "plan": {"kind": "contract_ref", "producer": "plan", "port": "plan_payload"},
        "revision": null,
        "critique": {"kind": "contract_ref", "producer": "critique", "port": "critique_payload"}
      }
    }
  ],
  "input": null,
  "suspension": null
}
```

Durable file shape for compatibility:

```json
{
  "stage": "gate",
  "resume_cursor": "{\"kind\":\"native_checkpoint\",\"checkpoint\":\"gate@L42#2\"}",
  "kind": "native_checkpoint",
  "phase": "gate",
  "pipeline": "megaplan",
  "pipeline_manifest_hash": "sha256:...",
  "runtime_topology_hash": "sha256:...",
  "frame_stack": [...]
}
```

Rules:

- `stage` remains present for existing resume readers.
- `phase` mirrors `stage` for legacy Megaplan cursors.
- `frame_stack` handles nested subpipelines.
- Loop position is not inferred from stage name; it is stored in `loop_counters` and `next_checkpoint`.
- Locals must be JSON/schema serializable or contract/artifact refs. Non-serializable live locals crossing a checkpoint are a compile-time/runtime error.

Resume algorithm:

1. Read `resume_cursor.json`; if absent, inspect `state["resume_cursor"]`.
2. Rebuild state from `events.ndjson` using `fold_journal(..., kind_filter="state_written", last_state_snapshot_projector)` and overlay `state.json` only as legacy authority where Megaplan requires it.
3. Rehydrate contract refs from `__contract_results__`, artifacts, and typed payload envelopes.
4. Jump to `next_checkpoint`; completed checkpoint IDs are not re-run.

**3. Handoff / Contract Enforcement**

Native phases still declare `produces: tuple[Port]` and `consumes: tuple[PortRef]`.

At compile time:

- Build a derived `Pipeline` with stages/edges/checkpoint nodes.
- Run `contracts.bind(stages, edges, typed_ports=True)`.
- Store `binding_map` on `NativePipelineDef`.

At runtime:

- Producer return values are normalized to `ContractResult`.
- For Megaplan planning payloads, continue using `produce_payload_result()` / `with_stage_payload_result()` from `pipeline_contracts.py`.
- Before a consumer phase receives a value, call `evaluate_step_io_handoff()` with the resolved seam, producer port, consumer port, policy from `resolve_megaplan_step_io_policy()`, and telemetry path `step_io_telemetry`.
- Enforcement blocks before local assignment/state merge, matching `arnold.pipeline.executor` and Megaplan `_evaluate_cursor_handoff`.

**4. Override Injection**

`@decision` phases are intercepted before the decision body runs.

```python
async def await_decision(checkpoint, phase, args):
    override = override_policy.next_applicable(state, phase)
    if override:
        return synthesize_decision_result(override)
    return await run_phase_body(...)
```

For Megaplan:

- Read `state["meta"]["overrides"]` and the operation catalog from `planning.operations.override_catalog()`.
- Normalize CLI spelling with `routing.cli_to_internal_override()`.
- Emit `override_applied` exactly through existing observability helpers.
- Return a verdict with `override="force_proceed"` / `override="abort"` so routing priority matches `resolve_edge`: halt, override, decision, normal.
- The phase body is skipped for true control overrides; `add-note`, `set-model`, etc. remain state/config mutations consumed by later phase bodies.

**5. Subloops / Nested Pipelines**

`run_subpipeline(child, inputs, promote=..., artifact_subdir=...)` creates a child frame:

- artifact root: `parent_plan_dir / artifact_subdir`
- state: shallow copy of parent state
- envelope: child `RunEnvelope`, joined back after completion
- contract registry: inherited
- event journal: child writes under child root unless configured to also emit parent-scoped summary events

Child state never mutates parent directly. Promotion returns a `ChildRunResult` and a parent `StateDelta`, preserving current `SubloopStep` behavior:

- `subloop:<name>:state`
- `subloop:<name>:recommendation`
- optional `subloop:<name>:resume_cursor`

If child suspends, parent suspends with either the child cursor or a composite cursor:

```json
{
  "kind": "composite_suspension",
  "version": 1,
  "phase": "tiebreaker",
  "children": {"tiebreaker": {...}},
  "pending_suspensions": [...]
}
```

**6. Event Journal And State Persistence**

Native runtime writes the same files:

- `state.json`
- `events.ndjson`
- `resume_cursor.json`
- artifacts under per-phase directories

Use existing writers:

- `write_plan_state(..., mode="executor-key-merge", executor_owned_keys=...)`
- `observability.events.emit_state_written(...)`
- `EventKind.PHASE_START`, `PHASE_END`, `STATE_WRITTEN`, `ACTIVATION_TRANSITIONED`, `OVERRIDE_APPLIED`
- `RuntimeEnvelope._to_jsonable()` in `state["runtime_envelope"]`

Each phase boundary persists:

```json
{
  "_pipeline_name": "megaplan",
  "_pipeline_manifest_hash": "...",
  "runtime_envelope": {...},
  "__contract_results__": {...},
  "resume_cursor": {...},
  "...existing Megaplan state keys...": "..."
}
```

Order:

1. phase result produced or suspension result synthesized,
2. contract result stored,
3. envelope joined,
4. suspension cursor persisted if needed,
5. state merged to disk,
6. `state_written` WAL event emitted.

**7. Graph Derivation**

`arnold.pipeline.native.graph.derive_pipeline(native_def)` returns a normal `Pipeline`.

Inputs:

- decorator metadata for phase names, ports, vocabularies,
- AST control-flow pass for `if`, `while`, `break`, `continue`, `run_subpipeline`,
- observed runtime topology for dynamic branches.

For Megaplan, derived graph must match current nine-stage layout:

`prep → plan → critique → gate → revise/finalize/tiebreaker/escalate → execute → review`.

Projection must be accepted by `validator.validate_control_flow()` and compatible with `runtime_topology_projection_for_pipeline()`:

- stages include phase/checkpoint names,
- edges include `kind="decision"` / `kind="override"`,
- ports and `binding_map` match current `Port`/`PortRef` contracts,
- topology hash uses the same canonical JSON approach as `behavioral_manifest.py`.

Static graph is “possible topology”; runtime graph is “observed topology”. Capsules use static behavioral hash plus runtime topology hash as today.

**8. Migration Strategy**

Phase 0: Build parity corpus. Capture current Megaplan traces: stage sequence, `state.json`, `events.ndjson` fold, cursors, artifacts, topology hash.

Phase 1: Add native decorators and graph projection only. No native execution yet. `build_pipeline()` still returns graph.

Phase 2: Implement native runtime behind feature flag for test-only pipelines.

Phase 3: Port a small Megaplan pipeline. Prove event/state/cursor parity.

Phase 4: Implement Megaplan native hooks: state merge, override policy, step-IO policy, envelope join, suspension lift.

Phase 5: Port main Megaplan pipeline but default existing runs to old graph executor. New runs may opt into native.

Phase 6: In-flight compatibility. If `state.json.runtime_envelope.runtime == "graph"` or cursor lacks `kind="native_checkpoint"`, resume with legacy executor. Native may also accept `{"stage": "gate"}` by mapping stage to the first checkpoint for that phase, but old graph fallback is safer.

Phase 7: Flip default for new runs. Keep legacy executor read-only for old plans until a deprecation window passes.

Phase 8: Remove graph execution only after all active plans either finish or migrate through an explicit cursor-upgrade command.

**9. Risks And Mitigations**

Biggest risk: resumable Python locals. Mitigation: AST state-machine lowering, no frame pickling, strict serializable-locals check.

Semantic drift from graph executor. Mitigation: parity tests for every phase boundary and WAL fold.

Dynamic topology lying to dashboards. Mitigation: separate static possible graph from observed runtime graph; hash both explicitly.

Override ordering. Mitigation: intercept before `@decision` body and route through `verdict.override`, matching resolver priority.

Subloop suspension loss. Mitigation: frame-stack cursors and composite cursor writer.

Contract bypass. Mitigation: all phase returns become `ContractResult`; enforce before consumer assignment.

In-flight breakage. Mitigation: keep legacy graph runner for graph-born runs.

**10. Effort Estimate**

Large: roughly 8-12 engineering weeks for a production-grade first version, more if parallel panels are included.

What makes it large: durable Python state-machine compilation, exact WAL/state parity, contract enforcement outside edge traversal, nested suspension semantics, topology hashing, and compatibility with existing active plans. The implementation is effectively a second executor plus a graph projection layer.
