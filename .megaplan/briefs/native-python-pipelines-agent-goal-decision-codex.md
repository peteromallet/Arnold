I prefer **Option C**, with a non-negotiable end state: **native Python becomes the runtime; graph execution is the compatibility bridge and observability projection, not the final source of truth.**

Option A is the safest migration path, but it caps composability. Agents will still be writing to a graph-shaped subset of Python. Option B is the right architecture for the goal, but switching directly would risk duplicating subtle Megaplan semantics badly. So the correct architecture is staged: prove parity through graph compilation first, then move execution under the native state-machine runtime while continuing to derive graph views for `check`, dashboards, capsules, and external hosts.

Agents most need these primitives:

- `@pipeline`: an ordinary Python function as the workflow boundary.
- `@phase` / `@decision`: explicit checkpoint, contract, override, and observability boundaries.
- `await phase(...)`: phase call as resumable execution, not graph construction.
- `run_subpipeline(...)`: nested pipeline with isolated state/artifacts and explicit promotion.
- `parallel(...)`: bounded fan-out/fan-in with typed collection contracts.
- Typed payload models: dataclass/Pydantic contracts as the author-facing shape, lowered to `Port` / `PortRef`.
- `ctx`: minimal runtime access for artifacts, memory, model profile, trust tier, and overrides, without making authors manually manage state.
- `inspect_pipeline(...)`: derived possible topology plus observed runtime topology.

Option C provides these without making agents understand `Stage`, `Edge`, `Pipeline`, resume cursors, WAL, or hook lifecycles.

What it makes harder: you are effectively building a second executor. Durable Python resume requires AST/state-machine lowering, serializable locals, frame-stack cursors, idempotent checkpoint IDs, WAL parity, contract enforcement outside edge traversal, override interception, and nested suspension semantics. Graph projection can also lie if the supported Python subset is too broad. This is harder than Option A and more operationally complex than pure Option B.

Minimum viable first milestone:

Build **native decorators plus graph projection plus a test-only native runtime behind a feature flag**. Do not convert live Megaplan yet.

The proving pipeline should include:

`prep -> plan -> critique -> decision -> revise loop -> finalize`, plus one nested subpipeline and one human/override decision.

It must prove:

- bridge-derived graph passes existing validation;
- native execution emits the same phase sequence as graph execution;
- `state.json`, `events.ndjson` fold, contract results, artifact layout, runtime envelope, and resume cursor semantics match;
- old graph-born runs still resume on the legacy executor;
- native-born runs resume from a native checkpoint cursor.

Guardrails for agent-authored pipelines:

- Only `await` decorated phases, decisions, `parallel`, and `run_subpipeline` may cross checkpoints.
- Locals live across checkpoints must be JSON-serializable or typed contract/artifact refs.
- No hidden global mutation across phases.
- No dynamic imports, reflection-based phase calls, monkeypatching, or runtime-generated functions in pipeline control flow.
- Loops require explicit names and max/halting policies.
- Dynamic fan-out requires bounded cardinality.
- Decisions must declare vocabulary and override vocabulary.
- Every phase declares consumed/produced contracts.
- Graph projection failure is a hard `arnold pipelines check` failure for deployable pipelines.
- Native runtime and graph projection must share the same contract, WAL, envelope, and observability adapters.

The position: **ship through Option C, but design toward Option B.** Option A is scaffolding. The product should be ordinary Python pipelines executed as resumable Python-shaped programs, with graphs as derived infrastructure views.
tokens used
68,534
I prefer **Option C**, with a non-negotiable end state: **native Python becomes the runtime; graph execution is the compatibility bridge and observability projection, not the final source of truth.**

Option A is the safest migration path, but it caps composability. Agents will still be writing to a graph-shaped subset of Python. Option B is the right architecture for the goal, but switching directly would risk duplicating subtle Megaplan semantics badly. So the correct architecture is staged: prove parity through graph compilation first, then move execution under the native state-machine runtime while continuing to derive graph views for `check`, dashboards, capsules, and external hosts.

Agents most need these primitives:

- `@pipeline`: an ordinary Python function as the workflow boundary.
- `@phase` / `@decision`: explicit checkpoint, contract, override, and observability boundaries.
- `await phase(...)`: phase call as resumable execution, not graph construction.
- `run_subpipeline(...)`: nested pipeline with isolated state/artifacts and explicit promotion.
- `parallel(...)`: bounded fan-out/fan-in with typed collection contracts.
- Typed payload models: dataclass/Pydantic contracts as the author-facing shape, lowered to `Port` / `PortRef`.
- `ctx`: minimal runtime access for artifacts, memory, model profile, trust tier, and overrides, without making authors manually manage state.
- `inspect_pipeline(...)`: derived possible topology plus observed runtime topology.

Option C provides these without making agents understand `Stage`, `Edge`, `Pipeline`, resume cursors, WAL, or hook lifecycles.

What it makes harder: you are effectively building a second executor. Durable Python resume requires AST/state-machine lowering, serializable locals, frame-stack cursors, idempotent checkpoint IDs, WAL parity, contract enforcement outside edge traversal, override interception, and nested suspension semantics. Graph projection can also lie if the supported Python subset is too broad. This is harder than Option A and more operationally complex than pure Option B.

Minimum viable first milestone:

Build **native decorators plus graph projection plus a test-only native runtime behind a feature flag**. Do not convert live Megaplan yet.

The proving pipeline should include:

`prep -> plan -> critique -> decision -> revise loop -> finalize`, plus one nested subpipeline and one human/override decision.

It must prove:

- bridge-derived graph passes existing validation;
- native execution emits the same phase sequence as graph execution;
- `state.json`, `events.ndjson` fold, contract results, artifact layout, runtime envelope, and resume cursor semantics match;
- old graph-born runs still resume on the legacy executor;
- native-born runs resume from a native checkpoint cursor.

Guardrails for agent-authored pipelines:

- Only `await` decorated phases, decisions, `parallel`, and `run_subpipeline` may cross checkpoints.
- Locals live across checkpoints must be JSON-serializable or typed contract/artifact refs.
- No hidden global mutation across phases.
- No dynamic imports, reflection-based phase calls, monkeypatching, or runtime-generated functions in pipeline control flow.
- Loops require explicit names and max/halting policies.
- Dynamic fan-out requires bounded cardinality.
- Decisions must declare vocabulary and override vocabulary.
- Every phase declares consumed/produced contracts.
- Graph projection failure is a hard `arnold pipelines check` failure for deployable pipelines.
- Native runtime and graph projection must share the same contract, WAL, envelope, and observability adapters.

The position: **ship through Option C, but design toward Option B.** Option A is scaffolding. The product should be ordinary Python pipelines executed as resumable Python-shaped programs, with graphs as derived infrastructure views.
