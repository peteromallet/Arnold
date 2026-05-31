# Shared Substrate Interface Feasibility: planning (graph/subprocess) vs resident (loop/async-API)

Decisive question for M2: can ONE interface each for **dispatch / emit / store** serve BOTH drivers, or are
they irreconcilable? Verdict per axis, then the altitude call.

Files read side by side:
- DISPATCH: `megaplan/workers/_impl.py` (`run_step_with_worker` L2478, `resolve_agent_mode` L2313, `run_command`
  L322, stall/heartbeat L390-577, codex retry L2584-2627) vs `megaplan/resident/agent_loop.py`
  (`OpenAICompatibleAgentRunner.run` L169, `AgentRequest` L19, `AgentRunner` Protocol L34) +
  `megaplan/resident/tool_registry.py`, `megaplan/resident/runtime.py`.
- EMIT: `megaplan/observability/events.py` (`emit` L276, `EventWriter.emit` L150, `EventKind` L31) vs
  `megaplan/store/base.py` (`record_epic_event` L443, `append_progress_event` L1295) +
  `megaplan/orchestration/progress.py` (`ProgressEmitter.emit` L139, `ProgressContext` L29).
- STORE/STATE: `megaplan/_core/state.py` (`plan_state_lock` L234, `save_state` L210, write modes L214) +
  `megaplan/store/plan_repository.py` (`load_state` L174 = bare `read_json`) vs `megaplan/store/base.py`
  Store protocol (revisioned/leased/idempotent) + `megaplan/resident/runtime.py` usage.

---

## 1. DISPATCH

### Candidate unified interface

```python
class Driver(Protocol):
    async def run(self, request: DispatchRequest, tools: Toolset) -> DispatchResult: ...

@dataclass
class DispatchRequest:
    role: str                      # step name | "resident_turn"
    agent: str                     # claude|codex|hermes|shannon|openai-compat
    model: str | None
    messages: tuple[dict, ...] | None   # resident
    prompt: str | None                  # planning (rendered template)
    session_ref: str | None             # codex session id | conversation_id
    output_schema: dict | None          # planning: JSON-schema-constrained
    hot_context: dict
    deadline_s: float

@dataclass
class DispatchResult:
    payload: dict | None           # planning structured output
    final_text: str | None         # resident
    tool_calls: tuple[...]         # resident audit records
    session_ref: str | None
    cost_usd: float; tokens: Usage
```

Both sides genuinely DO share a thin core: "given a model + an instruction + a toolset/schema, run the model,
let it act, return a typed result plus cost/usage." `WorkerResult` (L187-199) and `AgentResponse` (L27-32) are
the same idea (payload/text + cost + tokens + session id). A `Driver.run` protocol over a `DispatchRequest`
could nominally hold both.

### Hard irreconcilable points

1. **Sync subprocess vs async in-process tool loop.** Planning dispatch is a *blocking subprocess*:
   `run_command` (`_impl.py` L322) is fully synchronous — `subprocess.run`, raw threads for readers/heartbeat
   (L426-452), `process.wait` slices (L483). The model's tool use (file edits, shell) happens *inside the child
   CLI process* (claude/codex/shannon); megaplan never sees individual tool calls — it only parses the final
   stdout envelope (`parse_claude_envelope` L1140). Resident is the opposite: `OpenAICompatibleAgentRunner.run`
   (L169) is `async`, owns the tool-call loop itself (L175-215), and dispatches each tool **in-process** via
   `_execute_registered_tool` (L250) against a pydantic `ToolRegistry`. **The unit of dispatch is different**:
   planning = one opaque external turn; resident = an internal multi-step loop where megaplan is the
   orchestrator. There is no "toolset" object that both consume — planning has none (tools are the CLI's), and
   resident's `ToolRegistry` (handlers are `async` Python callables) cannot be handed to a codex subprocess.

2. **Liveness/stall model is structurally opposite.** Planning needs an idle-output watchdog + pre-first-byte
   wedge detector + tmux heartbeat (`_impl.py` L390-535, L854-897 sandbox fingerprint, L2584-2627 codex
   session-resume retry) because the worker is a black-box CLI that can wedge silently. Resident relies on a
   single `asyncio.wait_for(timeout=model_timeout_s)` (L176-185) — there is no stall machinery, no session
   resume, no sandbox, because it owns the loop. None of planning's most load-bearing dispatch code has any
   resident analogue.

3. **session_ref means two different things.** Planning's `session_id` is a *codex rollout file on disk*
   (`_codex_session_jsonl_path` L942) used to resume a CLI thread and to read cumulative token usage
   (`_codex_step_cost` L1035). Resident's `conversation_id` (`AgentRequest` L21) is a *Store row* whose history
   is reconstructed from messages by the runtime, not the model client. Collapsing them forces one side to fake
   the other.

### Verdict — **not without forcing one side.** Feasible only as a *very thin* `Driver.run(request)->result`
boundary that returns a typed result; everything that makes each dispatch correct (subprocess stall/sandbox/
session-resume vs async in-process tool loop) lives strictly *below* that line and cannot be shared. A "unified
dispatch interface" that tries to also own tool execution / liveness is **not reconcilable** — it would force
the resident's in-process async loop into a subprocess shape or vice versa. Share the *request/result shape*,
not the mechanism.

---

## 2. EMIT

### Candidate unified interface

```python
class EventSink(Protocol):
    def emit(self, kind: str, *, summary: str, payload: dict,
             phase: str | None = None,
             idempotency_key: str | None = None) -> None: ...
```

Both are append-an-event-with-a-kind-and-payload. `events.ndjson` `emit(kind, plan_dir, phase, payload)`
(`events.py` L276) and `ProgressEmitter.emit(kind, summary, details=...)` (`progress.py` L139) are
near-isomorphic at the call site. `ProgressEmitter` already abstracts a *Store-backed* sink behind the same
verb, with a `disabled()` no-op (L129). A common `EventSink` is the **most feasible of the three** — the planning
NDJSON writer and the Store progress emitter are two implementations of one publish verb.

### Hard irreconcilable points

1. **Scope key: `plan_dir` (a filesystem path) vs `epic_id`/`plan_id` (Store row identity).** `events.py` is
   hard-scoped to a directory: the writer keyed by `plan_dir.resolve()` (L262-273), the seq counter
   `.events.seq`, the ndjson file all live *in the plan dir*. `ProgressEmitter` is scoped to
   `epic_id`+`plan_id`+`sprint_id` (`progress.py` L151-159) and **requires `target_epic_id` or it silently
   no-ops** (L152). Resident has no plan_dir at all; planning has no epic_id in the common case. A unified sink
   must carry an opaque `scope` token and let each impl interpret it — workable, but it is the real seam.

2. **Pull (durable journal, replayed) vs push (event row, consumed).** `events.ndjson` is an *append-only audit
   journal* read back by `read_events`/`iter_events` (L294-357) with a monotonic flock'd seq (L188-218) — it
   exists to be re-scanned. The Store path splits into two distinct write verbs with different intents:
   `record_epic_event` (`base.py` L443) is *transactional state-transition history* (pre/post state hashes,
   `transaction_id`, replayable — L473), while `append_progress_event` (L1295) is a *progress feed*. NDJSON has
   no transaction_id / pre-post-state concept; `record_epic_event` has no free-form ndjson payload + sidecar
   seq. They are not the same event taxonomy: planning's 25 `EventKind`s (L31-74) are *runtime/observability*;
   the Store's epic events are *domain mutations*. A single `emit` can carry both, but the journal-vs-mutation
   semantics don't merge.

3. **Process-safety mechanism differs.** NDJSON guarantees ordering with `fcntl.flock` on a sidecar across OS
   processes (parent driver + subprocess workers, L188). The Store uses idempotency keys + (for DB) row
   identity. A unified sink can't promise both "monotonic seq across forked subprocesses" and "idempotent row
   upsert" with one mechanism.

### Verdict — **feasible with an adapter.** A shared `EventSink.emit(kind, summary, payload, scope,
idempotency_key)` is genuinely viable and is the cleanest of the three; `ProgressEmitter` already proves the
shape. Two concrete sinks (NDJSON-journal, Store-progress) sit behind it. But the *taxonomies* (observability
EventKind vs domain epic-events) and the scope token (`plan_dir` vs `epic_id`) stay impl-specific — the
interface unifies the *verb*, not the event model. Do not try to fold `record_epic_event` (transactional,
pre/post-state) into the same call as observability emit.

---

## 3. STORE / STATE

### Candidate unified interface

The resident `Store` Protocol (`base.py` L252) is already the candidate — a rich, idempotent, revisioned,
leased contract. The question is whether planning's `state.json` can live behind it (e.g. `load_state` /
`save_state` / artifact read-write as Store methods, which `PlanRepository` partially mirrors).

### Hard irreconcilable points

1. **Last-writer-wins file blob vs optimistic-concurrency revisioned rows.** This is the hardest point in the
   entire substrate. Planning state is a *single JSON document* mutated under a coarse advisory file lock:
   `plan_state_lock` is a blocking `fcntl.flock` around a read-modify-write (`state.py` L234-245), and
   `PlanRepository.load_state` is a bare `read_json(plan_dir/"state.json")` (`plan_repository.py` L174) with no
   revision at all. The whole-document write modes (`PlanStateWriteMode` L214: replace / patch-key /
   merge-meta-list / heartbeat) are *blob surgery*. The Store contract is the opposite philosophy: every mutator
   takes `expected_revision` and raises `RevisionConflict` (`base.py` L89, `update_epic` L280, `update_plan`
   L1059), normalized rows, idempotency keys on *every* write, and `ExecutionLease`/`EpicLock` leasing
   (L1099-1140). You cannot express "patch one key of state.json under flock, last writer wins" through a
   revisioned-row API without either (a) bolting a fake monotonic revision onto the blob, or (b) shredding
   state.json into rows — i.e. forcing one side.

2. **No identity correspondence.** Planning addresses state by `plan_dir` (a path); the Store addresses by
   `plan_id`/`epic_id` (synthetic ids) and a plan only exists as a row via `create_plan` (`base.py` L1044) with
   a parent `sprint_id`/`epic_id`. Planning plans have *no epic and no sprint* in the common standalone case.
   Mapping a free-floating plan_dir into the Store's epic→sprint→plan hierarchy requires inventing parents.

3. **Transaction boundary.** The Store exposes `transaction(epic_id)` (L261) and the resident wraps multi-row
   writes (turn + messages + tool_calls + conversation cursor, `runtime.py` L142-220) in store-consistent units.
   Planning has *no transaction*: it has a per-plan flock and atomic file replace (`save_state` L210). A
   `transaction()` that means "ACID across rows" cannot be the same primitive as "exclusive flock on one file".

### Verdict — **not without forcing one side.** The two stores encode opposite consistency philosophies
(last-writer-wins blob under advisory lock vs idempotent, revisioned, leased, transactional rows). A single
Store interface that planning's `state.json` satisfies would either degrade the Store contract (make
`expected_revision`/leases optional and meaningless for planning) or force planning state into normalized rows
(a migration, not an interface). Sharing is feasible only at the **artifact-blob altitude** — `read_plan_artifact`
/ `write_plan_artifact` (`base.py` L1078-1090), which is already a byte-blob get/put and which `PlanRepository`
already mirrors. Keep `state.json` as a planning-owned artifact-shaped store; do NOT make planning implement the
full revisioned/leased Store.

---

## OVERALL CALL

**A unified substrate IS feasible, but only at a deliberately LOW altitude — the request/result and
publish-verb boundary — and explicitly NOT at the orchestration/consistency altitude.**

- **DISPATCH:** thin `run(request) -> result` shape only; mechanism (subprocess stall/sandbox/session vs async
  in-process tool loop) stays per-driver. *Not* a unified tool-execution or liveness layer.
- **EMIT:** genuinely unifiable as `EventSink.emit(...)` with two concrete sinks; the cleanest win. Keep the
  event *taxonomy* and `record_epic_event`'s transactional pre/post-state path separate.
- **STORE:** unify only the **artifact byte-blob** get/put. The revisioned/leased/transactional Store and
  planning's flock'd last-writer-wins `state.json` are irreconcilable as one mutating contract.

**Recommendation for M2:** Design the shared interfaces at the *result-shape + publish-verb + artifact-blob*
altitude (`DispatchRequest/Result`, `EventSink`, artifact read/write). Do **not** design a single Store mutating
contract or a single tool-execution/dispatch engine — that requires forcing one driver into the other's shape.
M2 is sound **if and only if** it is scoped to those three thin boundaries; an "altitude-too-high" M2 that tries
to unify state mutation or the dispatch loop itself should be rejected, and those should stay per-driver with
only the thin sharing above.
