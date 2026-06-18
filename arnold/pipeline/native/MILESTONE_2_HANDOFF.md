# Milestone 2 Handoff — Native Pipeline Runtime Foundation

**Status:** Milestone 1 complete.  All `must` success criteria are green
(218 native tests + 150 adjacent tests passing, zero regressions).
The native runtime is a pure-library, opt-in foundation ready for its
first production pilot in Milestone 2.

---

## Recommended first pilot: `vibecomfy_executor`

**Recommendation:** Start Milestone 2 by converting
`arnold/pipelines/vibecomfy_executor/pipelines.py` to the native runtime.

### Why vibecomfy_executor is the right choice

| Property                   | vibecomfy_executor                                |
|----------------------------|---------------------------------------------------|
| Pipeline topology          | Linear chain of 4 phases (classify → research → implement → reply).  No branching, no loops. |
| Builder                    | `PipelineBuilder` with typed `Port`/`PortRef` declarations.  Already neutral-neutral — the builder graph is separable from the Megaplan conversion shim `_to_megaplan_pipeline`. |
| Phase complexity           | Each phase calls an agent and returns `StepResult`.  Normalisation path through `_normalize_phase_result` is already exercised by parity tests. |
| Typed handoff              | Four typed ports: `plan` (json), `research_summary` (markdown), `implementation` (markdown), `reply` (markdown).  Step-IO enforcement is wired in the native runtime and passes parity. |
| Checkpoint surface         | No mutable loop state.  Resume-cursor frames and `__state__` persistence are the right fit for a linear pipeline. |
| Risk surface               | Minimal — no decisions, no loops, no vocabulary routing.  The simplest possible integration target. |

The conversion path is:

1. Copy the four step classes into a native-decorated module with
   `@phase` annotations.
2. Replace the `PipelineBuilder` assembly with a `@pipeline` generator
   function that `yield`s each phase.
3. Remove the `_to_megaplan_pipeline` shim — the native runtime replaces
   the Megaplan executor entirely for this pipeline.
4. Wire `run_native_pipeline(compile_pipeline(my_pipeline), ...)` at the
   CLI entrypoint, gated behind `ARNOLD_NATIVE_RUNTIME`.

---

## Why Megaplan-backed pilots remain out of scope

The following pipelines are **not** suitable for native-runtime conversion
in Milestone 2:

| Pipeline             | Blocking reason                                                                                                                                                     |
|----------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `folder_audit`       | Depends on `folder_audit/skills/` which embed `megaplan` executor internals (`plan_dir`, `profile`, activity-tracking helpers).  Those semantics do not exist in the native context dict. |
| `jokes`              | Configures `deliberation`/`evidence_pack`/`megaplan` sub-pipelines that invoke Megaplan orchestration.  The native runtime has no sub-pipeline dispatch or `megaplan` step wiring. |
| `megaplan` itself    | Pulls the full Megaplan pipeline tree (`planning`, `handlers/finalize.py`, `skills/`, live-supervisor routing).  Every one of those modules imports Megaplan-specific `StepContext` fields. |
| `creative`           | Uses `deliberation/skills/` and `megaplan/skills/` — same Megaplan dependency chain.                                                                                |
| `epic_blitz`         | Invokes `megaplan` sub-pipelines through Megaplan orchestration paths.                                                                                              |
| `live_supervisor`    | Depends on `megaplan` agent dispatch and profile resolution.                                                                                                        |
| `writing_panel_strict` | Uses `simplify_writing` and `deliberation/skills/` — same Megaplan dependencies.                                                                                  |

**The fundamental blocker:** all of these pipelines exercise Megaplan
semantics that the native runtime does not provide:

- `plan_dir` / `profile` / `activity` context fields
- Sub-pipeline dispatch (calling `run_pipeline` / `run_pipeline_resume`
  inside a running pipeline)
- Megaplan-specific `StepContext` attributes (`task`, `skills_dir`,
  `suggested_handoff`, etc.)

Until the native runtime grows a mechanism for injecting these semantics
(planned for M3's hook and envelope seams — see below), converting any
Megaplan-backed pipeline would require forking the pipeline definition
into a "native-only" variant, defeating the single-source-of-truth goal.

---

## M2 scope summary (narrowed)

Milestone 2 is deliberately conservative:

1. **Single production pilot** — `vibecomfy_executor` only.
2. **No sub-pipeline dispatch** — the native runtime walks a single
   flat `NativeProgram`.
3. **No Megaplan context injection** — hooks may rewrite the context
   dict, but no `plan_dir`/`profile`/`task` fields are provided by
   the runtime itself.
4. **No event-journal parity** — the native runtime does not emit
   `events.ndjson`.  Parity is verified through hook traces.
5. **No artifact-reference checkpoint frames** — only
   JSON-serializable values in `frames`.

Anything beyond these boundaries is deferred to M3+.

---

## Checkpoint and grammar risks

### Grammar risk

The M1 compiler recognises this grammar:

```
@phase / @decision → yield <phase>(ctx)
                   | if <decision>(ctx): ... [else: ...]
                   | while <guard>(ctx): ...  # guard is a @decision
```

**Known limitations (rejected with `NativeCompileError`):**

- `ast.Attribute` calls (e.g. `yield self.do_work(ctx)`)
- Bare `yield` without a value
- `yield` of a non-`@phase` callable
- `if`/`while` tests that are not `@decision` calls
- Unsupported statement types (`For`, `With`, `Try`, `ClassDef`, etc.)
- State mutation between checkpoints that isn't captured in phase outputs

**Mitigation for M2:** `vibecomfy_executor` uses none of these
constructs.  It's a linear `yield` chain.  The grammar risk is zero for
this pilot.

**Long-term:** The compiler must grow support for attribute calls and
nested pipeline dispatch before Megaplan-backed pilots can be compiled.
That work is planned for M3.

### Checkpoint risk

The native cursor adds a `"native"` key to `resume_cursor.json`:

```json
{
  "stage": "my_pipe__do_work__pc0",
  "resume_cursor": null,
  "stages": ["..."],
  "loops": {},
  "frames": {"__state__": {...}, "__envelope__": ...},
  "native": {
    "pc": 1,
    "version": 1
  }
}
```

**Risks:**

- **Schema evolution:** The `native.version` field allows future readers
  to detect drift.  Bump `NATIVE_CURSOR_VERSION` on every
  backward-incompatible change to the pc/instruction model.
- **`__state__` deserialisation:** Working state is stored in `frames["__state__"]`.
  If state contains non-JSON-serializable values, `persist_native_cursor`
  will fail silently (best-effort).  Phase authors must ensure their
  outputs are JSON-safe.
- **`__envelope__` key collision:** If a pipeline phase writes a key
  named `__envelope__` into state, it will collide with the envelope
  persistence convention.  This is a known loophole; a future cursor
  version may namespace internal keys (e.g. `__native__`).

**Mitigation for M2:** `vibecomfy_executor` phases return `StepResult`
objects whose `outputs` are always JSON-safe dicts with well-known keys.
No collision risk.

---

## M3 seams: hooks, envelope, contract, checkpoint

The native runtime exposes five extension seams that M3 will use to
bridge the gap between the native runtime and Megaplan semantics:

### 1. `NativeRuntimeHooks` (8 callbacks)

```python
class NativeRuntimeHooks(Protocol):
    on_step_start(instr, ctx) -> ctx          # rewrite context before invocation
    on_step_end(instr, ctx, result) -> result # rewrite result after invocation
    on_step_error(instr, ctx, exc) -> None    # telemetry on exception
    merge_state(instr, state, outputs, owned_keys) -> (state, owned_keys)  # custom state merge
    join_envelope(instr, current, step) -> envelope  # custom envelope accumulation
    should_suspend(instr, state, result) -> (bool, reason)  # terminal exit at step
    should_halt_loop(instr, state, iteration) -> (bool, reason)  # loop abort
    on_stage_complete(instr, ctx, result, state, owned_keys) -> None  # post-stage hook
    on_checkpoint(cursor, state) -> None      # post-persistence notification
```

**M3 injection points:**

- `on_step_start` → inject `plan_dir`, `profile`, `activity`, and
  `contract_results` into the context dict so Megaplan phases see the
  same environment they get from the graph executor's `_build_ctx`.
- `on_step_end` → verify outputs against Megaplan contracts
  (schema validation, artifact provenance).
- `merge_state` → track owned keys per the Megaplan state-ownership model.
- `should_suspend` / `should_halt_loop` → cost-based and
  iteration-limit abort (currently handled by Megaplan's executor).
- `on_checkpoint` → publish telemetry events, write auxiliary artifacts,
  and notify the activity tracker when a durable checkpoint is written.

### 2. Envelope propagation

The native runtime accumulates an `envelope` value across all steps via
`hooks.join_envelope`.  Phases can attach envelope data by returning an
object with an `.envelope` attribute or a dict with an `"envelope"` key.

**M3 injection:** Megaplan's executor maintains a rich envelope
structure (session metadata, cost totals, token counts).  A
Megaplan-aware hooks implementation can populate this envelope from
phase return values and finalize it at pipeline completion.

### 3. Schema-registry-backed contract handoff

The native runtime's `_enforce_native_typed_handoff` already calls
`evaluate_step_io_handoff` with a `StepIOContractContext` when a
`schema_registry` is provided.  This is a direct pass-through to the
existing graph executor's contract validation path.

**M3 injection:** Pass the Megaplan schema registry (built from
`contracts/` directories) to `run_native_pipeline(schema_registry=...)`.
No new code needed — the seam is already wired.

### 4. Checkpoint callback

`hooks.on_checkpoint(cursor, state)` fires after every durable cursor
write (both suspension and clean completion).  The cursor dict matches
the on-disk `resume_cursor.json` shape exactly.

**M3 injection:** Megaplan's activity tracker and telemetry publisher
can subscribe to `on_checkpoint` to log phase completions, update
progress indicators, and write auxiliary artifacts without the native
runtime importing Megaplan code.

### 5. `run_native_pipeline` parameters

The function signature already accepts the key integration points:

```python
def run_native_pipeline(
    program: NativeProgram,
    *,
    artifact_root: str | Path = ".",
    initial_state: dict[str, Any] | None = None,
    max_phases: int | None = None,
    resume: bool = False,
    hooks: NativeRuntimeHooks | None = None,
    schema_registry: Any = None,
    telemetry_path: str | Path | None = None,
    initial_envelope: Any = None,
) -> NativeExecutionResult:
```

**M3 injection:** Megaplan's CLI entrypoint will call
`run_native_pipeline` with a Megaplan-aware hooks instance, the schema
registry, and the telemetry path — no runtime changes required.

---

## What M1 delivered (by module)

| Module                | Responsibility                                                                |
|-----------------------|-------------------------------------------------------------------------------|
| `decorators.py`       | `@pipeline`, `@phase`, `@decision` decorators + metadata accessors            |
| `ir.py`               | `NativePhase`, `NativeDecision`, `NativeLoopGuard`, `NativePipeline`, `NativeInstruction`, `NativeProgram` frozen dataclasses |
| `compiler.py`         | AST-to-`NativeProgram` lowering for the milestone grammar.  Rejects unsupported constructs with `NativeCompileError`. |
| `graph_projection.py` | Converts `NativeProgram` → `Pipeline` (neutral types).  Validates through `arnold.pipeline.validator.validate()`.  Parity-confirmed against hand-built reference graphs. |
| `runtime.py`          | Sequential state-machine executor with pc-based walk loop.  Handles phases, decisions, jumps, halts, typed handoff enforcement, envelope propagation, max_phases suspension, and resume. |
| `checkpoint.py`       | Thin wrappers around `arnold.pipeline.resume` with additive `"native"` key.  Cursor schema: `NATIVE_CURSOR_VERSION = 1`. |
| `hooks.py`            | `NativeRuntimeHooks` Protocol (9 callbacks) + `NullNativeRuntimeHooks` no-op default.  Extension surface for M3+ Megaplan injection. |
| `context.py`          | `require_native_runtime()` guard + `NativeRuntimeDisabledError`.               |
| `flags.py`            | `native_runtime_enabled()` — single-source-of-truth for `ARNOLD_NATIVE_RUNTIME`. |
| `__init__.py`         | Public re-export of all symbols.                                               |

---

## Test baseline (M1 exit)

```
218 tests in tests/arnold/pipeline/native/      — all passing
150 adjacent tests                               — all passing
  (test_resume, test_step_io_handoff, test_validator, test_executor,
   test_graph_projection_parity)
  0 regressions
```

---

## Next steps (recommended order for M2)

1. **Convert vibecomfy_executor to native runtime** — `@phase` decorate
   each step, `@pipeline` the assembly, remove `_to_megaplan_pipeline`.
2. **Add `ARNOLD_NATIVE_RUNTIME=1` gating at the CLI entrypoint** so the
   native path is opt-in and the existing Megaplan path remains the
   default.
3. **Run parity** — confirm that vibecomfy_executor's native execution
   produces the same outputs as the Megaplan executor path.
4. **Begin M3 Megaplan hooks implementation** — build a
   `MegaplanNativeHooks` class that implements `NativeRuntimeHooks` and
   injects `plan_dir`/`profile`/`activity` into the context dict via
   `on_step_start`.
5. **Add sub-pipeline dispatch to the compiler/runtime** — enable
   `folder_audit`, `jokes`, and eventually `megaplan` to migrate.

---

# Milestone 2 Actuals — What shipped

**Status:** Milestone 2 complete.  The native runtime executed its first
production pilot (`folder_audit`) end-to-end, with parity-trace emission,
cursor enrichment, and a two-gate opt-in model.  The prior handoff
recommendation of `vibecomfy_executor` was intentionally set aside per
the milestone brief (see §Pilot pivot below).

---

## Pilot pivot: `folder_audit` instead of `vibecomfy_executor`

The M1→M2 handoff above recommended `vibecomfy_executor` as the safest
first pilot — a linear chain with no Megaplan dependencies.  The M2
milestone brief explicitly locked in `folder_audit` instead
([SD1 — settled decision](#execution-context)):

> SD1: Proceed with folder_audit as the M2 pilot despite the existing
> M2 handoff recommending vibecomfy_executor. The milestone brief
> explicitly locks in folder_audit.

The pivot was intentional: `folder_audit` exercises the context-bridge
pattern (native dict → `StepContext`) that every Megaplan-backed pipeline
will need in M3, making it a more informative stress test than a
zero-dependency pipeline would have been.  The price was that
`folder_audit` required a `StepContext` adapter, which exposed the
limitations documented in §Context-bridge limitations below.

---

## Cursor-schema additions (since M1)

The M1 cursor carried `pc` and `version` under the `native` key.  M2
added two backward-compatible fields:

### `cursor_id`
A stable UUID4 hex string generated once per pipeline execution and
reused across all checkpoint/suspension events.  Allows external
tooling to correlate multiple cursor writes from the same run.
Stored at the top level of `resume_cursor.json`.  Old cursors without
this field normalise to `None` on read — no migration required.

### `stage_reentry_points`
A mapping of `phase_name → stable_stage_id` (e.g.
`{"ingest": "ingest__pc0"}`).  Enables external tooling to locate
reentry targets without parsing the `stages` list.  Old cursors
without this field normalise to `{}` on read.

Full cursor shape (additive — existing readers are unaffected):

```json
{
  "stage": "folder_audit__ingest__pc0",
  "resume_cursor": null,
  "stages": ["folder_audit__ingest__pc0", "folder_audit__audit__pc1"],
  "loops": {},
  "frames": {"__state__": {...}, "__envelope__": ...},
  "native": {
    "pc": 2,
    "version": 1
  },
  "cursor_id": "a1b2c3d4e5f6...",
  "stage_reentry_points": {
    "ingest": "folder_audit__ingest__pc0",
    "audit": "folder_audit__audit__pc1"
  }
}
```

The `native.version` field remains at `1` — M2's additions are purely
additive and do not break existing readers.

---

## Trace emission contract

M2 introduced `NativeTraceHooks` (`arnold/pipeline/native/trace.py`),
a `NativeRuntimeHooks` wrapper that emits parity-trace artifacts to a
`trace_dir` when set.  When `trace_dir` is `None` (the default), the
wrapper is a pure pass-through with zero allocation overhead beyond a
few attribute accesses — no files are opened, no events are written.

### Trace directory layout

```
<trace_dir>/
    state.json          # snapshot after each stage + final
    events.ndjson       # NdjsonEventJournal-compatible event stream
    stages.json         # ordered stage sequence
    artifacts.json      # content-hash inventory of output files
    checkpoint.json     # final checkpoint notification
```

### Event journal contract

Events are written through `NdjsonEventJournal` with the canonical
shape `{seq, kind, payload, ts_utc}` — matching the current executor's
output format.  The legacy `ts/evt/sid/pid/data` format is NOT used
([SD3 — settled decision](#execution-context)):

> SD3: Use the current NdjsonEventJournal shape (seq, kind, payload,
> ts_utc) as the canonical events.ndjson format for parity traces.

### Event kinds emitted

| Hook                  | Event kind        | Payload                                  |
|-----------------------|-------------------|------------------------------------------|
| `__init__`            | `pipeline.init`   | `{"status": "started"}`                  |
| `on_step_start`       | `phase.start`     | `{"phase": name, "pc": n}`               |
| `on_step_end`         | `phase.end`       | `{"phase": name, "pc": n}`               |
| `on_step_error`       | `error`           | `{"phase": name, "pc": n, "error_type": …, "error_message": …}` |
| `on_stage_complete`   | `stage.complete`  | `{"stage": id, "pc": n}`                 |
| `on_checkpoint`       | `checkpoint`      | `{"final": bool, "stage_count": n}`      |

### Integration path

`run_native_pipeline()` accepts a `trace_dir` parameter.  When set, the
runtime wraps the caller's hooks (or `NullNativeRuntimeHooks`) in
`NativeTraceHooks` before execution begins.  The `folder_audit`
entrypoint `run_native()` forwards `trace_dir` through to
`run_native_pipeline()`.

---

## Opt-in behavior

Native execution requires **two gates**, both of which must be
satisfied:

### Gate 1: Environment flag (`ARNOLD_NATIVE_RUNTIME=1`)

Enforced inside `run_native_pipeline()` via `require_native_runtime()`.
Without this flag, any call to `run_native_pipeline()` raises
`NativeRuntimeDisabledError`.  Compiler, graph-projection, and IR
imports are NOT gated — they remain usable in unit tests without the
flag.

### Gate 2: Per-call opt-in

The `folder_audit` pipeline exposes a dedicated `run_native()` function
in `arnold/pipelines/folder_audit/native.py`.  Graph execution via
`build_pipeline()` remains the default path regardless of the
environment flag.  There is no accidental native path — callers must
deliberately invoke `run_native()`.

### What is NOT affected by the flag

- `build_pipeline()` works identically with or without the flag.
- Package metadata (`driver`, `entrypoint`) always advertises graph
  execution.
- The native `@phase` adapters can be imported and tested without the
  flag.
- The compiler and graph-projection modules never consult the flag.

---

## `folder_audit` context-bridge limitations

The `folder_audit` native adapter (`native.py`) bridges the native
runtime's lightweight dict context into the Megaplan `StepContext`
that `IngestStep`/`AuditStep`/`EmitStep` expect.  The bridge is
implemented in `_build_step_ctx()`:

```python
def _build_step_ctx(native_ctx: dict[str, Any]) -> StepContext:
    state = dict(native_ctx.get("state", {}))
    raw_inputs = dict(native_ctx.get("inputs", state))
    artifact_root = native_ctx.get("artifact_root", ".")
    return StepContext(
        plan_dir=Path(artifact_root),
        state=state,
        inputs=raw_inputs,
        profile=state.get("profile"),
        mode=str(state.get("mode", "default")),
    )
```

### What the bridge provides

| `StepContext` field | Bridged from                         |
|---------------------|--------------------------------------|
| `plan_dir`          | `ctx["artifact_root"]`               |
| `state`             | `ctx["state"]` (the working state)   |
| `inputs`            | `ctx.get("inputs", ctx["state"])`    |
| `profile`           | `state.get("profile")`               |
| `mode`              | `state.get("mode", "default")`       |

### What the bridge does NOT provide

These `StepContext` fields are left at their type-defaults (usually
`None` or empty) because the native runtime has no mechanism to populate
them:

| Missing field      | Impact on `folder_audit`                                    |
|--------------------|-------------------------------------------------------------|
| `task`             | Not read by any folder_audit step — no impact.              |
| `skills_dir`       | Not read by any folder_audit step — no impact.              |
| `suggested_handoff`| Not read by any folder_audit step — no impact.              |
| `budget`           | Not read by any folder_audit step — no impact.              |
| `deliberation`     | Not read by any folder_audit step — no impact.              |
| `contract_results` | Not read by any folder_audit step — no impact.              |

**Key insight:** `folder_audit` happens to read only `plan_dir`,
`state`, `inputs`, `profile`, and `mode` — fields the bridge
provides.  This made it a feasible M2 pilot.  Pipelines that read
`task`, `skills_dir`, or `contract_results` will require the M3 hook
injection seam to populate those fields via `on_step_start`.

### Artifact serialisation

`StepResult.outputs` may contain `Path` objects (e.g. `EmitStep`
returns `audit_json` and `audit_md` as `Path` instances).  The adapter
stringifies these in `_step_result_to_dict()` so the working state
remains JSON-serializable for cursor persistence.  This is a pragmatic
compromise — the original `Path` objects are lost, but the string
representations are sufficient for all downstream consumers.

### Worker callable resolution

`AuditStep` requires a `_worker` callable.  The native adapter resolves
this from `ctx["state"]["_worker"]` when present, otherwise falls back
to `_default_worker` — matching `build_pipeline()` behaviour.  The
caller passes the worker through `run_native(worker=...)`.

---

## Topology hashing

M2 added `compute_topology_hash()` in `arnold/pipeline/topology.py`
([SD2 — settled decision](#execution-context)).  The hash is a
`sha256:<hex>` digest of a canonical sorted-JSON projection of:

- Stage names (sorted)
- Entry stage
- Per-stage edges (label, target, kind; sorted)
- Per-stage decision / override vocabularies
- Per-stage declared ports (produces / consumes; sorted, empty omitted)
- Binding map (if present; keys sorted)

Callable references (`step`, `loop_condition`, `join`, etc.) are
deliberately excluded — they are not structural graph fields.  This
ensures that two `build_pipeline()` calls with different `_worker`
instances produce the same hash, while any change to edges,
vocabularies, ports, or stage names produces a different hash.

---

## Graph trace capture and diffing

`tests/arnold/pipeline/native/parity_trace.py` provides the canonical
trace infrastructure used throughout M2 parity tests:

- **`TraceCaptureHooks`** — graph executor hooks that capture stage
  sequence, final state, hook order, envelope, and artifact inventory.
- **`ParityTrace`** — normalized trace dataclass with all volatile
  fields (timestamps, run IDs, absolute paths, sequence numbers)
  masked.
- **`capture_graph_trace()`** — convenience wrapper that runs a
  pipeline through the graph executor and returns a normalized trace.
- **`diff_traces()`** — surface-localized difference report comparing
  native vs graph traces across seven surfaces: `topology_hash`,
  `stage_sequence`, `final_state`, `events`, `cursor`, `artifacts`,
  `hook_order`.

This infrastructure is the foundation for automated parity verification
between native and graph execution paths.

---

## M2 module inventory (additions since M1)

| Module                | Status  | Responsibility                                                    |
|-----------------------|---------|-------------------------------------------------------------------|
| `trace.py`            | **New** | `NativeTraceHooks` — parity-trace emission to `trace_dir`         |
| `topology.py`         | **New** | `compute_topology_hash()` — canonical graph fingerprint           |
| `checkpoint.py`       | Updated | Added `cursor_id` and `stage_reentry_points` to cursor schema     |
| `runtime.py`          | Updated | Added `trace_dir` parameter and `NativeTraceHooks` wrapping       |
| `__init__.py`         | Updated | Re-exports `NativeTraceHooks`                                     |
| `arnold/pipelines/`   |         |                                                                   |
| `folder_audit/native.py` | **New** | `@phase` adapters, `@pipeline` generator, `run_native()` entry   |
| `tests/arnold/pipeline/`|        |                                                                   |
| `test_topology_hash.py`| **New** | Topology hash stability and sensitivity tests                     |
| `native/parity_trace.py`| **New** | Graph trace capture, normalization, and diffing infrastructure   |
| `tests/pipelines/`    |         |                                                                   |
| `test_folder_audit.py`| Updated | Added native pipeline tests (compilation, opt-in, flag gating)    |

---

## What remains deferred to M3

The following M1→M2 handoff recommendations remain deferred:

1. **Sub-pipeline dispatch** — the native runtime walks a single flat
   `NativeProgram`.  No nested `run_pipeline()` calls inside a running
   pipeline.  Blocks: `jokes`, `creative`, `epic_blitz`,
   `live_supervisor`, `writing_panel_strict`, `megaplan` itself.

2. **Megaplan context injection via hooks** — the M2 handoff described
   injecting `plan_dir`/`profile`/`activity`/`contract_results` through
   `on_step_start`.  `folder_audit` worked around this with
   `_build_step_ctx()`, but a general solution (a `MegaplanNativeHooks`
   class) is M3 work.

3. **Artifact-reference checkpoint frames** — only JSON-serializable
   values in `frames`.  Large artifacts are not referenced by hash.

4. **Grammar expansion** — `ast.Attribute` calls, nested pipeline
   dispatch, `For`/`With`/`Try` support remain rejected with
   `NativeCompileError`.

5. **Event-journal parity for Megaplan pipelines** — the native trace
   emits `events.ndjson` with the canonical `NdjsonEventJournal` shape,
   but parity with the full Megaplan event journal (which carries
   session metadata, token counts, cost tracking) is not yet verified
   for Megaplan-backed pipelines.

---

## M3 recommended order

1. **Build `MegaplanNativeHooks`** — implement `NativeRuntimeHooks` with
   `on_step_start` injecting `plan_dir`, `profile`, `activity`, and
   `contract_results` into the context dict.  This unlocks all
   Megaplan-backed pipelines that only need context fields (no sub-pipeline
   dispatch).

2. **Add sub-pipeline dispatch to compiler/runtime** — enable `yield`
   of compiled sub-pipelines within `@pipeline` generators.  This is the
   hard blocker for `jokes`, `creative`, `epic_blitz`, and `megaplan`.

3. **Convert a second pipeline** — with hooks and sub-pipeline dispatch,
   `vibecomfy_executor` (the original M2 recommendation) becomes the
   natural second pilot — it exercises typed ports, typed handoff, and
   the hook injection seam without sub-pipeline complexity.

4. **Full event-journal parity** — verify that native-traced
   `events.ndjson` for Megaplan-backed pipelines matches the graph
   executor's journal in kind sequence, payload keys, and state
   transitions.

