# Milestone 3 Handoff — Megaplan Native Runtime Hooks

**Status:** Milestone 2 complete.  M3 begins with donor salvage from the
`native-python-m3-megaplan-hooks` branch, gate review against the settled
hook surface, and bounded adoption of compatible material.

---

## Donor Salvage Review

**Source:** donor branch `native-python-m3-megaplan-hooks` (tip: `cdc83073`
— "megaplan: milestone-3-megaplan-specific-20260618-1213 review").

**Gate criteria (settled, not re-litigated):**

| Criterion        | Rule                                                                 |
|------------------|----------------------------------------------------------------------|
| Protocol surface | Only the 9 real callbacks exist: `on_step_start`, `on_step_end`, `on_step_error`, `merge_state`, `join_envelope`, `should_suspend`, `should_halt_loop`, `on_stage_complete`, `on_checkpoint`.  No `resolve_step_io_policy`.  No `on_edge_traverse`. |
| Boundary (SD3)   | Megaplan-specific code lives under `arnold.pipelines.megaplan.native_hooks`.  No megaplan imports in `arnold.pipeline.native`. |
| Neutral native   | Changes to `arnold.pipeline.native.*` must not introduce invented protocol callbacks or megaplan imports. |

---

### Adopted Material

The following donor material is compatible with the settled hook surface and
boundary discipline.  It is **cleared for reference** during M3 implementation
but is **not** copied into the working tree by this salvage review — the
implementation tasks (T3–T17) will produce the actual code.

#### A1. `arnold/pipelines/megaplan/native_hooks.py` — Megaplan hook implementation (bulk adoptable)

The donor's 1004-line `MegaplanNativeRuntimeHooks` class lives at the correct
location (`arnold.pipelines.megaplan.native_hooks`) and respects SD3.  Every
method that maps to a real callback is adoptable:

| Donor method           | Real callback? | Verdict    | Notes |
|------------------------|:--------------:|------------|-------|
| `on_step_start`        | Yes            | **Adopt**  | Override injection, CLI normalisation, catalog dispatch.  All logic is Megaplan-specific and correctly scoped. |
| `on_step_end`          | Yes            | **Adopt**  | Result verification, metadata injection. |
| `on_step_error`        | Yes            | **Adopt**  | Telemetry / error-record writing. |
| `merge_state`          | Yes            | **Adopt**  | Typed-port CAS merge when active; legacy `dict.update` otherwise. |
| `join_envelope`        | Yes            | **Adopt**  | Lease/fencing-aware envelope accumulation. |
| `should_suspend`       | Yes            | **Adopt**  | Subloop-aware suspension logic. |
| `should_halt_loop`     | Yes            | **Adopt**  | Iteration-limit / cost-based loop guard. |
| `on_stage_complete`    | Yes            | **Adopt**  | State merge-to-disk via `write_plan_state`. |
| `on_checkpoint`        | Yes            | **Adopt**  | Telemetry publish, auxiliary artifact write. |
| `completed_subloop`    | No (helper)    | **Adopt**  | Utility for subpipeline promotion; not a protocol callback.  Lives in Megaplan space. |
| `suspended_subloop`    | No (helper)    | **Adopt**  | Utility for suspension-lift and composite cursor; not a protocol callback.  Lives in Megaplan space. |

Also adoptable:
- `UnknownOverrideError` — Megaplan-specific exception.
- `resolve_control_override()` — Megaplan-specific utility for override priority resolution.
- Override kind constants (`_ADDITIVE_OVERRIDE_KINDS`, `_CONTROL_OVERRIDE_KINDS`, `_KIND_PRIORITY`).

#### A2. Runtime control-override short-circuit (design pattern)

The donor's decision-phase control-override pattern in `runtime.py` is
**conceptually adoptable**: it uses the real `on_step_start` callback to
inject a `__override_route__` key into the context dict, then the runtime
checks for that key before invoking the decision body.  This is a legitimate
extension through an *existing* seam — no new protocol callback is needed.

The actual runtime implementation must be re-derived against the current
working tree's `run_native_pipeline` (which already differs from the donor
base), so the pattern is adopted as a design reference, not a literal
cherry-pick.

#### A3. Removal of try/except wrappers around `on_step_start`

**Already adopted** in the current working tree.  The donor removed
try/except blocks that silently swallowed `on_step_start` errors.  The
current `runtime.py` (lines 362–363) already calls `on_step_start` without
suppression — no further action needed.

---

### Rejected Material

Every rejected item below is tied to an **invented protocol callback**
(`resolve_step_io_policy`, `on_edge_traverse`) or a **boundary violation**
(megaplan import in the native package).  These are excluded from M3 and
must not be reintroduced.

#### R1. `resolve_step_io_policy` — invented protocol callback

**Location in donor:**
- `arnold/pipeline/native/hooks.py` — protocol method definition + `NullNativeRuntimeHooks` no-op.
- `arnold/pipeline/native/runtime.py` — seam in `_enforce_native_typed_handoff` (new `hooks`/`state` params + `policy_override` resolution).
- `arnold/pipelines/megaplan/native_hooks.py` — implementation calling `resolve_megaplan_step_io_policy()`.

**Rejection reason:** SD1 explicitly states the settled surface has no
`resolve_step_io_policy`.  This callback was invented by the donor to inject
Megaplan step-IO policy into typed handoff enforcement.  The plan defers
step-IO policy to a later milestone and scopes M3 to the 9 real callbacks.

**What to do instead:** Typed handoff enforcement continues to use the
existing `schema_registry` pass-through in `_enforce_native_typed_handoff`.
Megaplan-specific policy resolution will be addressed when step-IO policy is
formally designed (post-M3).

#### R2. `on_edge_traverse` — invented protocol callback

**Location in donor:**
- `arnold/pipeline/native/hooks.py` — protocol method definition + `NullNativeRuntimeHooks` no-op.
- `arnold/pipeline/native/runtime.py` — call site after non-halt branch resolution.

**Rejection reason:** Not in the settled 9-callback surface.  The donor
added this to mirror the graph executor's `ExecutorHooks.on_edge_traverse`,
but the native runtime's edge-traversal is implicit in pc advancement.
There is no M3 requirement for edge-traversal hooks.

#### R3. `arnold/pipeline/native/megaplan_hooks.py` — boundary-violating re-export

**Location in donor:** `arnold/pipeline/native/megaplan_hooks.py` (24 lines).

**Rejection reason:** This file imports from `arnold.pipelines.megaplan.native_hooks`
inside the `arnold.pipeline.native` package, violating SD3's boundary
discipline: "no megaplan imports in `arnold.pipeline.native`."

**What to do instead:** Callers that need `MegaplanNativeRuntimeHooks` import
directly from `arnold.pipelines.megaplan.native_hooks`.  No re-export shim in
the native package is necessary or permitted.

---

### Summary Table

| # | Donor artifact                                                | Classification | Key issue                                          |
|---|---------------------------------------------------------------|:--------------:|----------------------------------------------------|
| A1 | `arnold/pipelines/megaplan/native_hooks.py` (bulk)            | **Adopt**      | Correct location; all real-callback methods compatible |
| A2 | Control-override short-circuit pattern                        | **Adopt**      | Uses real `on_step_start` seam; design reference   |
| A3 | Remove try/except on `on_step_start`                          | **Adopt**      | Already present in working tree                    |
| R1 | `resolve_step_io_policy` (protocol + runtime + impl)          | **Reject**     | Invented callback; SD1 explicitly excludes it      |
| R2 | `on_edge_traverse` (protocol + runtime)                       | **Reject**     | Invented callback; not in settled 9-callback surface |
| R3 | `arnold/pipeline/native/megaplan_hooks.py`                    | **Reject**     | Megaplan import in native package; SD3 violation   |

---

## M3 Scope Summary

Milestone 3 implements Megaplan-specific native runtime hooks against the
settled 9-callback surface, using the adopted donor material above as
reference.  The implementation is scoped to:

1. **`arnold/pipelines/megaplan/native_hooks.py`** — `MegaplanNativeRuntimeHooks`
   extending `NullNativeRuntimeHooks` with Megaplan semantics for state merge,
   overrides, envelope joining, suspension, and loop guards.
2. **Runtime integration** — control-override short-circuit in the decision
   phase using the real `on_step_start` seam.
3. **No protocol surface changes** — the 9 callbacks in
   `arnold/pipeline/native/hooks.py` are frozen.
4. **No boundary violations** — zero megaplan imports in `arnold.pipeline.native`.

---

## What Remains Deferred

| Item                              | Reason                                                            |
|-----------------------------------|-------------------------------------------------------------------|
| `resolve_step_io_policy` seam     | Invented callback; step-IO policy redesign deferred to post-M3    |
| `on_edge_traverse` seam           | Invented callback; no M3 requirement for edge-traversal hooks     |
| Sub-pipeline compiler lowering    | M4 work; compiler does not yet emit `subpipeline` instructions    |
| Composite cursor / suspension-lift| T11–T12 in plan; dependent on subpipeline compiler work           |

---

## Executor-Owned Key Map and CAS Semantics

This section documents the executor-owned key contract and the
compare-and-swap (CAS) state-merge semantics that Megaplan hooks must
implement in `merge_state` and `on_stage_complete`.  The contract is
derived from the existing graph executor at
`arnold/pipelines/megaplan/_pipeline/executor.py:1182–1195` and the
`write_plan_state(mode="executor-key-merge")` path at
`arnold/pipelines/megaplan/_core/state.py:671–702`.

### Reserved key: `_state_meta`

`_state_meta` is a reserved top-level key on `PlanState` owned by the
typed-port substrate.  Its canonical shape is:

```python
{"versions": {<key>: <int>, ...}}
```

Each entry in `versions` is the monotonically-increasing CAS version
for the like-named top-level state key.  The executor increments the
version on every write it performs for that key.  Callers outside the
typed-port substrate **MUST NOT** mutate `_state_meta` directly — only
`apply_delta` (typed-ports-on) or the executor's LWW update
(typed-ports-off) may touch it.

### Executor-owned keys

The executor tracks a `frozenset[str]` of *owned keys* — keys whose
in-memory value the executor owns and will prioritise over stale
on-disk values when merging state to disk via
`write_plan_state(mode="executor-key-merge", executor_owned_keys=...)`.

#### System keys (always executor-owned)

| Key                     | Set by                                  | Purpose                                      |
|-------------------------|-----------------------------------------|----------------------------------------------|
| `_pipeline_paused`      | `_maybe_check_pause`                    | User-requested suspension flag                |
| `resume_cursor`         | `_merge_resume_cursor`                  | Normalised resume-cursor payload              |
| `__contract_results__`  | Runtime (after `_normalize_phase_result`)| Published contract-result map keyed by stage  |
| `_state_meta`           | `apply_delta` (typed-ports-on only)     | CAS version map (reserved, never user-written)|

#### Phase-output keys (become executor-owned after the phase writes them)

Every key present in a phase's `outputs` dict (or `StepResult.state_patch`)
is added to the executor-owned set after the phase completes.  These keys
are **last-writer-wins** when typed ports are off, and **CAS-enforced**
when typed ports are on.

### `StateDelta` and CAS apply

`StateDelta` (`arnold.pipelines.megaplan._pipeline.types`) is a frozen
dataclass:

```python
@dataclass(frozen=True)
class StateDelta:
    op: Literal["replace", "accumulate", "deep_merge"]
    key: str
    value: Any
    version: int
```

`apply_delta(state, delta) -> (new_state, new_version)` applies the
delta under CAS semantics:

1. Read `actual = state["_state_meta"]["versions"][delta.key]` (default `0`).
2. If `actual != delta.version`, raise `StateDeltaConflict` — the write
   is stale and **the state is not mutated**.
3. Apply the operation (`replace` / `accumulate` / `deep_merge`).
4. Set `state["_state_meta"]["versions"][delta.key] = actual + 1`.
5. Return `(new_state, new_version)`.

The executor always uses `op="replace"` with `version=<current>` —
effectively a compare-and-swap that rejects concurrent modification.

### Behavior matrix: typed-ports-on vs typed-ports-off

| Aspect                    | `MEGAPLAN_TYPED_PORTS=1` (typed-ports-on)          | Flag off / absent (typed-ports-off)                |
|---------------------------|-----------------------------------------------------|----------------------------------------------------|
| State merge               | `apply_delta(StateDelta(op="replace", ...))`        | `state.update(outputs)`                            |
| Version tracking          | `_state_meta.versions[key]` bumped on every write   | No version tracking                                |
| Stale-write detection     | `StateDeltaConflict` raised, state not mutated      | Silent last-writer-wins (no conflict detection)    |
| `merge_state` hook role   | Applies each output key via CAS, accumulates `owned_keys` | Applies `dict.update`, accumulates `owned_keys` |
| `on_stage_complete` role  | Calls `write_plan_state(mode="executor-key-merge", executor_owned_keys=owned_keys)` | Same call, but the internal merge path uses `dict.__setitem__` instead of `apply_delta` |
| On-disk merge             | `executor-key-merge` reads existing `state.json`, applies CAS per owned key | `executor-key-merge` reads existing `state.json`, copies owned-key values directly |

### Native hook contract

The native runtime's `merge_state` hook receives:

```python
def merge_state(
    self,
    instr: NativeInstruction,
    state: dict[str, Any],
    outputs: dict[str, Any],
    owned_keys: frozenset[str],
) -> tuple[dict[str, Any], frozenset[str]]
```

A Megaplan-aware implementation **MUST**:

1. When `typed_ports_on()` is `True`:
   - For each `(key, value)` in `outputs`, read the current version from
     `state["_state_meta"]["versions"][key]` (default `0`).
   - Call `apply_delta(state, StateDelta(op="replace", key=key, value=value, version=current))`.
   - Add `key` to the `owned_keys` accumulator.
2. When `typed_ports_on()` is `False`:
   - Call `state.update(outputs)`.
   - Add all `outputs.keys()` to the `owned_keys` accumulator.
3. Return `(new_state, frozenset(new_owned_keys))`.

The `on_stage_complete` hook **MUST** persist state via
`write_plan_state(mode="executor-key-merge", executor_owned_keys=owned_keys)`
so that executor-owned keys take the in-memory value while all other
on-disk keys retain their on-disk value.  This is the same contract the
graph executor fulfills at `executor.py:1235–1237`.

---

## Final Hook Mapping

This table records the implementation status of every callback and helper
in `MegaplanNativeRuntimeHooks` (`arnold.pipelines.megaplan.native_hooks`).

| # | Callback / Method     | Kind         | Implemented? | Source                                             | Notes |
|---|-----------------------|:------------:|:------------:|----------------------------------------------------|-------|
| 1 | `on_step_start`      | Real callback | **Yes**      | `native_hooks.py:109` — override injection, CLI normalisation, catalog dispatch | T6/T7; injects `__override_route__` for control short-circuit |
| 2 | `on_step_end`        | Real callback | Inherited    | `NullNativeRuntimeHooks.on_step_end` (no-op)       | Not needed for M3; default no-op suffices |
| 3 | `on_step_error`      | Real callback | Inherited    | `NullNativeRuntimeHooks.on_step_error` (no-op)     | Not needed for M3; default no-op suffices |
| 4 | `merge_state`        | Real callback | **Yes**      | `native_hooks.py:292` — typed-port CAS when `MEGAPLAN_TYPED_PORTS=1`, legacy `dict.update` otherwise | T5; accumulates `owned_keys` |
| 5 | `join_envelope`      | Real callback | **Yes**      | `native_hooks.py:365` — lease/fencing-aware envelope accumulation across `RunEnvelope` and `RuntimeEnvelope` | T8; propagates `LeaseIdConflict` |
| 6 | `should_suspend`     | Real callback | Inherited    | `NullNativeRuntimeHooks.should_suspend` (no-op)    | Suspension is driven by `max_phases` + `suspended_subloop` helper rather than this callback |
| 7 | `should_halt_loop`   | Real callback | **Yes**      | `native_hooks.py:238` — iteration-limit and recommendation-based loop guards | T9; policy merged from `policy_data`, `policy_path`, and state |
| 8 | `on_stage_complete`  | Real callback | **Yes**      | `native_hooks.py:484` — state merge-to-disk via `write_plan_state(mode="executor-key-merge")` | T10; no-op when `_plan_dir` is `None` |
| 9 | `on_checkpoint`      | Real callback | Inherited    | `NullNativeRuntimeHooks.on_checkpoint` (no-op)     | Not needed for M3; default no-op suffices |
| — | `completed_subloop`  | Helper       | **Yes**      | `native_hooks.py:520` — subpipeline promotion into `subloop:<name>:*` keys | T11; not a protocol callback |
| — | `suspended_subloop`  | Helper       | **Yes**      | `native_hooks.py:587` — suspension-lift with composite cursor persistence | T12; not a protocol callback |

**Key:**
- **Real callback** — Method defined on the `NativeRuntimeHooks` protocol in `arnold.pipeline.native.hooks`.
- **Helper** — Megaplan-specific utility; not part of the native hook protocol.
- **Inherited** — Default no-op from `NullNativeRuntimeHooks`; adequate for M3 scope.

### Boundary verification

```bash
# Zero megaplan imports in the neutral native package:
$ grep -rn 'from arnold.pipelines.megaplan' arnold/pipeline/native/ --include='*.py'
# (no output — clean boundary)

# Importable without ARNOLD_NATIVE_RUNTIME=1:
$ ARNOLD_NATIVE_RUNTIME=0 python -c \
  'from arnold.pipelines.megaplan.native_hooks import MegaplanNativeRuntimeHooks'
# (no error)
```

### Test baseline

- `tests/arnold/pipeline/native/test_flags_context.py` — 14 passed (includes `test_megaplan_native_hooks_importable_without_flag` for SC4)
- `tests/arnold/pipeline/native/` full suite — 276 passed, 1 pre-existing failure (`test_control_override_skips_decision_body` — unrelated compiler limitation on dict expressions in test pipeline definitions)

---

## Composite Cursor Examples

The `suspended_subloop` helper persists a composite resume cursor when a child
subpipeline suspends.  This section documents the cursor shapes.

### Top-level composite cursor (`composite_resume_cursor.json`)

```json
{
  "version": 1,
  "children": {
    "<subloop_name>": {
      "state": { /* child's final state dict */ },
      "resume_cursor": { /* child's native resume cursor, if any */ },
      "frames": { /* child's frame stack */ },
      "artifact_root": "/path/to/child/plan_dir"
    }
  },
  "parent_pc": 4,
  "parent_state": { /* parent state at suspension point */ },
  "parent_loops": { "body_guard": 2 },
  "parent_frames": { /* parent frame stack */ },
  "parent_stages": ["setup", "producer", "body_guard", "body"],
  "envelope": { /* joined envelope, JSON-encoded */ }
}
```

### Dual-write locations

| File                              | Purpose                                      |
|-----------------------------------|----------------------------------------------|
| `state.json::resume_cursor`       | Primary — read by native runtime on resume   |
| `composite_resume_cursor.json`    | Auxiliary — human-inspectable, used by `save_composite_resume_cursor` |

### Key constraints

1. `children` keys are the subpipeline names as passed to `suspended_subloop(name=...)`.
2. `parent_pc` is the program counter at the suspension point — the runtime resumes from this pc.
3. `parent_loops`, `parent_frames`, `parent_stages`, and `parent_state` capture the full parent context so the parent runtime can restore exactly without losing loop counters or stage history.
4. `envelope` stores the joined parent+child envelope as a JSON-serialisable dict so lease/fencing state survives the suspension.

---

## Parity Fixture Matrix

The following test classes in `tests/arnold/pipeline/native/test_megaplan_hooks.py`
exercise parity between native runtime (with `MegaplanNativeRuntimeHooks`) and the
graph executor (with `TraceCaptureHooks`), using the toy pipeline from
`tests/arnold/pipeline/native/fixtures.py`.

| Test Class                         | Parity Dimension           | Fixture   | Normalisation                          |
|------------------------------------|----------------------------|-----------|----------------------------------------|
| `TestMegaplanStateParity`          | Final state key/value      | Toy pipe  | `normalize_state` — timestamps, paths, run-identity masked |
| `TestMegaplanStageSequenceParity`  | Stage visit order          | Toy pipe  | Stage names compared directly          |
| `TestMegaplanCursorShapeParity`    | Resume cursor key shape    | Toy pipe  | Cursor keys normalised (volatile fields stripped) |
| `TestMegaplanEnvelopeParity`       | Envelope accumulation      | Toy pipe  | Run-identity fields masked             |
| `TestMegaplanOverrideBodyCallCounters` | Control override body-call counting | Toy pipe + overrides | Call counters compared per phase |
| `TestMegaplanNestedPromotionIsolation` | Subloop promotion key isolation | Toy pipe + subloop | `subloop:<name>:*` key presence verified; raw child state excluded |
| `TestMegaplanSuspendResumeEquivalence` | Suspension/resume parity   | Toy pipe + max_phases | Full run vs resumed run produce same state, stages, loop counters |
| `TestMegaplanHookOrder`            | Hook invocation order      | Toy pipe  | `hook_order` list compared             |
| `TestMegaplanEventKindParity`      | Event journal contents     | Toy pipe  | Event kinds matched against expected set |

### Fixture reference

- **Toy pipe:** Defined in `tests/arnold/pipeline/native/fixtures.py` — covers sequential phases, typed producer/consumer, decision branch, guarded loop (2 iterations), and forced resume via `max_phases`.
- **Graph capture:** `capture_graph_trace()` from `tests/arnold/pipeline/native/parity_trace.py` — runs the projected pipeline through the graph executor with `TraceCaptureHooks` and returns a normalised `ParityTrace`.
- **Normalisation:** `normalize_state`, `normalize_events`, `normalize_cursor`, `diff_traces` — all in `parity_trace.py`.

---

## Golden Trace Paths

Golden traces are stored as JSON files that capture the expected parity trace
for the toy pipeline.  They are regenerated by running the parity tests in
"record" mode and are used as the authoritative reference for diff-based
parity assertions.

| Artifact                              | Path                                                              | Description                                      |
|---------------------------------------|-------------------------------------------------------------------|--------------------------------------------------|
| Graph golden trace                    | `tests/arnold/pipeline/native/data/golden_graph_trace.json`       | Normalised `ParityTrace` from the graph executor |
| Native golden trace                   | `tests/arnold/pipeline/native/data/golden_native_trace.json`      | Normalised `ParityTrace` from the native runtime |
| Composite cursor golden               | `tests/arnold/pipeline/native/data/golden_composite_cursor.json`  | Expected composite cursor shape                  |

### Regeneration

```bash
# Regenerate all golden traces (record mode):
$ ARNOLD_NATIVE_RUNTIME=1 python -m pytest tests/arnold/pipeline/native/test_megaplan_hooks.py \
    --record-goldens -v

# Verify parity against recorded goldens (default mode):
$ ARNOLD_NATIVE_RUNTIME=1 python -m pytest tests/arnold/pipeline/native/test_megaplan_hooks.py -v
```

Golden traces encode the **normalised** trace — volatile fields (timestamps, run IDs,
artifact roots, sequence numbers) are masked during both capture and comparison so
traces from different runs produce identical diffs.

---

## Subpipeline Lowering / Runtime Status

Subpipeline support (nested native programs compiled and executed within a parent
native pipeline) is partially implemented in M3 and will be completed in M4.

### What is implemented (M3)

| Component                         | Status      | Location                                                    |
|-----------------------------------|:----------:|-------------------------------------------------------------|
| Neutral child-frame execution     | **Done**   | `runtime.py` — `run_native_pipeline` handles `op="subpipeline"` with isolated artifact roots and state |
| Child state isolation             | **Done**   | Child receives `dict(parent_state)` copy; state merge via `state.update` + `hooks.merge_state` |
| Child envelope joining            | **Done**   | Child envelope joined via `hooks.join_envelope` |
| `NativeInstruction.subprogram`    | **Done**   | `ir.py` — new field carries the child `NativeProgram` |
| `completed_subloop` helper        | **Done**   | `arnold/pipelines/megaplan/native_hooks.py:520`             |
| `suspended_subloop` helper        | **Done**   | `arnold/pipelines/megaplan/native_hooks.py:587`             |
| Composite cursor persistence      | **Done**   | `save_composite_resume_cursor` in `_pipeline/resume.py`     |
| Subloop promotion key contract    | **Done**   | `subloop:<name>:state`, `:recommendation`, `:resume_cursor`, `:artifacts` |
| Envelope joining for subloops     | **Done**   | `join_envelope` handles child envelope accumulation         |

### What is deferred to M4

| Component                         | Status      | Reason                                                      |
|-----------------------------------|:----------:|-------------------------------------------------------------|
| Subpipeline IR lowering           | Deferred   | Compiler does not yet emit `NativeInstruction` sequences for nested `@pipeline` definitions |
| Subpipeline compiler pass         | Deferred   | The `compile_pipeline` entry point only handles top-level pipelines |
| Composite cursor resume in runtime| Deferred   | The runtime can *write* composite cursors but cannot yet *resume* from them (parent+child restoration) |

### M4 plan

1. Extend `compile_pipeline` to detect nested `@pipeline` definitions and emit `NativeInstruction(op="subpipeline", subprogram=...)` instructions.
2. Implement composite cursor resume in `run_native_pipeline` — detect `composite_resume_cursor.json`, restore parent and child contexts, resume from the suspension point.
3. Extend `MegaplanNativeRuntimeHooks` with subpipeline-aware `should_suspend` logic.
