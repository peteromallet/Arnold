# M3: Manifest Runner And Runtime

## Outcome

Build `arnold.execution` and the runtime kernel behavior that executes compiled `WorkflowManifest`s through append-only events, content-addressed artifacts, capability/budget checks, deterministic routing, and manifest-coordinate resume.

The reviewer should be able to run fake-backend workflows for linear, branch, loop, fanout, retry, subpipeline, generic suspension, resume, and replay scenarios without executing Python object graphs or native generator frames.

## Operating Philosophy

M3 turns the manifest into a trustworthy machine. Runtime correctness comes from append-only events, content-addressed artifacts, fail-closed capability/effect dispatch, and replayable cursors, not from old mutable state or Python frames. The runner stays product-blind even when it supports the generic primitives Megaplan needs.

## Scope

IN:

- Create `arnold/execution` modules for runner, backends, routing, resume, state machine/DAG traversal, hooks, topology, testing backend, and effect dispatch.
- Create neutral capability/effect dispatch protocols or registries that `arnold.agent` tool/model adapters can satisfy without `arnold.execution` importing Megaplan product code.
- Execute only `WorkflowManifest` input; DSL objects must compile before runtime.
- Persist append-only events for manifest load/validate, node start/complete/fail/suspend/resume, artifact writes, ref resolution, decisions, loops, fanout children, retry attempts, subpipeline enter/exit, capability/budget checks, generic suspend/resume, and external effects.
- Artifact writes must follow the versioned `vN.<ext>` convention frozen in M1. Runtime writes to `artifact_dir(...)/v{latest+1}.{ext}` and reads resolve the newest versioned path. Legacy flat-directory artifacts are migration input only.
- Derive state from the event journal and artifact store; avoid mutable overwrite-only state as authority.
- Implement manifest-coordinate resume cursors with `manifest_hash`, `reentry_id`, `scope_stack`, `artifact_root`, and `event_sequence`.
- Manifest-coordinate resume must resolve native-first cursors before legacy graph cursors, matching the current mainline evidence-pack fallback order.
- Enforce capability checks, budget caps, retry idempotency, fanout stable child identity, subpipeline scope hashes, and human resume schemas before execution.
- Resolve capabilities and effects through neutral string-keyed registries/contracts. Product packages may register policy-specific handlers, but the runner must not import product policy classes, prompt templates, gate literals, or Megaplan override logic.
- Resolve capabilities, effects, and control transitions through protocol-typed registries. Product packages register handlers at process startup; `arnold.execution` must not call `importlib.import_module` on any manifest field to discover product callables.
- Implement pre-execution budget reservation and settlement: journal `budget_reserved` before capability/effect execution, journal `budget_settled` or release on completion/failure, and block execution when reservation would exceed remaining budget.
- Implement authority-gated resume transitions. When a cursor advances past a mutation boundary such as execute, the runner verifies completion evidence through a product-registered authority contract before clearing the cursor; fake-run coverage must include execute-authority failure.
- Implement generic suspension as a first-class runtime terminal state and resume path. Human gates are one product-facing use of suspension, not the runtime definition of suspension.
- Implement cancellation, node-level timeout, manifest-level deadline/TTL, escalation targets, reducer dispatch, and compensation hooks as generic runtime semantics.
- Preserve generic override edges, fallback edges, dynamic topology overlays, subpipeline promotion contracts, and supervisor event routing as policy-blind primitives needed by Megaplan parity.
- Define the canonical event journal schema and file layout, and map existing trace/event emitters into it. The event journal is the single source of truth for state, cost, trace, and resume; mutable state files are projections.
- Define dynamic topology overlays as manifest amendments or control-transition events. Runtime may apply and record overlays, but must not decide Megaplan override/fallback/supervisor meanings.
- Dynamic topology overlays are control-transition events, not manifest mutations. Runtime records and projects overlays but preserves the canonical manifest hash for replay. Planned variants such as robustness levels and feedback phases arrive as distinct compiled manifests.
- Implement supervisor condition detection as a generic signal API. Product code emits stalled, blocked, orphaned, or idle signals; kernel/execution routes them through registered transition handlers without knowing Megaplan meanings.
- Implement compensation semantics: on a compensation trigger, runtime walks completed steps in the declared scope, executes compensation targets in declared ordering, enforces idempotency, and journals compensation lifecycle events.
- Define old `arnold.runtime` disposition: refactor reusable pieces into `arnold.kernel`/`arnold.execution`, then mark remaining public runtime package surfaces for M6 deletion.
- Produce a runtime salvage/deletion map for old `arnold.pipeline` executor/native/discovery/runtime helpers: each reusable lifecycle, hook, event, oracle, discovery, and replay concept is either refactored into `arnold.kernel`/`arnold.execution` or named as an M6 deletion target. Re-export chokepoints must not be left to accidental compatibility.
- Implement content-type registry enforcement, artifact retention pins, provenance-chain verification, and artifact-root semantics.
- Provide deterministic fake backend tests suitable for later Megaplan parity.

OUT:

- No full Megaplan product migration.
- No deletion of legacy public runtime exports yet.
- No distributed backend beyond fake/in-process certified semantics unless it is tiny and needed for tests.
- No optional restricted-Python runner.

## Locked Decisions

- The manifest is the runtime source of truth.
- Resume/replay uses events, artifact hashes, manifest hashes, and reentry IDs, not Python frames, closures, graph stage names, or `NativeProgram` program counters.
- All side effects flow through capability/effect contracts with idempotency where required.
- Product packages may supply policies and prompts as importable identities; core runtime must stay product-neutral.
- Runtime may import manifest/kernel schema types, but must not import `arnold.workflow`, `arnold.patterns`, or any Megaplan package to execute a manifest.
- Runtime may invoke product behavior only through startup-registered protocol handlers; manifest refs are identifiers, not runtime import instructions.
- Reducer functions, override meanings, fallback meanings, and escalation policies are product-authored importable identities or data. Runtime owns only dispatch contracts, event ordering, and fail-closed behavior.
- Robustness levels and optional feedback phases compile to distinct manifest variants. The runner does not dynamically skip or rewire nodes based on a product robustness string.

## Resolved Execution Decisions

- Existing executor hook lifecycle code is quarry only. Generic lifecycle event ordering, artifact writes, capability checks, and resume/replay concepts may be refactored into `arnold.execution`; product-specific hooks and old public runner APIs are replaced.
- Legacy resume aliases are explicit compatibility records mapping old stage/checkpoint coordinates to manifest hash, reentry ID, scope stack, artifact root, and event sequence. Missing or unsafe aliases quarantine with operator notification.
- The minimum backend interface before M4 is fake/in-process execution with protocol-typed capability/effect handlers, deterministic event journals, artifact writes, suspension/resume, replay, and failure injection.
- Manifest/kernel budget fields cover neutral limits, reservation, settlement, and ledger events. Product-owned cost presentation such as `total_cost_usd` remains policy/projection over the ledger.
- Planned topology variants are product-authored compiled manifests. Runtime overlays are generic control-transition events that preserve the canonical manifest hash.
- `arnold.agent` tools certified in M3 are only those that satisfy neutral adapter protocols without product imports. Deferred adapters are inventoried and blocked from M4/M6 gates until certified or deleted.
- Dynamic import shims in `arnold.agent` and top-level `agent/` are compatibility aliases unless independently re-chartered as neutral adapter surfaces with dynamic-import proof; otherwise they are M6 deletion targets.
- Surviving suspended runs receive explicit manifest-coordinate aliases; all other old suspended runs are quarantined with operator-visible rationale.

## Constraints

- Do not import `arnold_pipelines.megaplan` or `arnold.pipelines.megaplan` from neutral runtime code.
- Event ordering and replay must be deterministic and tested.
- Suspension must exit cleanly and resume through schema-validated payloads.
- External effect nodes must require idempotency policy.
- Keep public API names aligned with `arnold.execution.run(...)` and workflow docs.
- The named M2 canonical Megaplan-shaped fixture must be the M3-to-M4 integration gate: compile, fake-run, replay, and resume it before product migration starts.
- Neutral budget enforcement reads from manifest events and effect ledgers, not from product-owned `state['meta']['total_cost_usd']`.

## Done Criteria

1. Manifest runner executes fake-backend linear, branch, loop, fanout, retry, subpipeline, external-call, and generic suspension workflows.
2. Resume/replay tests verify manifest-hash matching, event sequence replay, artifact hash validation, nested scope cursors, and mismatch quarantine.
3. Capability, budget, and idempotency enforcement fail closed.
4. No runtime path executes DSL Python object graphs directly.
5. `arnold.execution` imports no `arnold.workflow`, `arnold.patterns`, `arnold_pipelines.megaplan`, or `arnold.pipelines.megaplan` modules.
6. A non-human suspend/resume workflow persists `node_suspended`, exits cleanly, resumes with schema-validated payload, and completes.
7. Cancellation, timeout/deadline, escalation-target, reducer-dispatch, and compensation-hook tests pass with fake backends.
8. Provenance-chain verification proves artifacts were produced by the expected node/run/manifest hash.
9. Capability dispatch tests prove `arnold.agent` adapters can be reached through neutral contracts without product imports.
10. The named M2 canonical Megaplan-shaped fixture matrix fake-runs through all required routing families, exercises suspension plus at least one failure/retry path, replays from at least three distinct resume cursors, and quarantines manifest-hash mismatches. M4 may not start until this gate is green.
11. The fixture matrix also exercises at least one override route, fallback route, escalation transition, compensation reversal, supervisor promotion event, dynamic topology overlay event, recursive tiebreaker loop-back, and execute-authority failure.
12. Manifest-version bridging is implemented: replay with original manifest, explicit compatibility aliases, and quarantine/report behavior are all tested.
13. If runtime work discovers manifest/kernel contract changes not reserved by M1, M3 updates M1 contract tests, M2 compiler tests, and `workflow-manifest-amendments.md` before M4 starts.
14. Runtime docs explain event, artifact, resume, suspension, cancellation, timeout/deadline, capability/effect, control-transition, compensation, and backend semantics.
15. Artifact write/read tests cover the M1 versioned `vN.<ext>` convention, newest-version resolution, legacy flat-artifact quarantine or migration input, and native-first versus legacy-fallback resume cursor resolution.

## Touchpoints

- `arnold/execution/`
- `arnold/kernel/events.py`
- `arnold/kernel/journal.py`
- `arnold/kernel/replay.py`
- `arnold/kernel/artifacts.py`
- `arnold/kernel/effect.py`
- `arnold/kernel/capabilities.py`
- `arnold/kernel/suspension.py`
- `arnold/kernel/content_types.py`
- `arnold/kernel/control.py`
- `arnold/kernel/governor.py`
- `arnold/kernel/effect_ledger.py`
- `docs/arnold/event-journal-spec.md`
- `docs/arnold/state-authority-migration.md`
- old `arnold.runtime`, `arnold.pipeline`, `arnold/pipeline/__init__.py`, runtime/oracle/discovery helpers, and agent adapter shims as salvage/deletion inventory inputs
- `tests/arnold/execution/`
- `tests/arnold/kernel/`
- `docs/arnold/workflow-runtime.md`

## Anti-Scope

- Do not preserve `run_pipeline()` as the final public product runner.
- Do not add Megaplan-specific branches to the neutral runner.
- Do not carry over native checkpoint cursors as the final resume shape.
- Do not add bridge shims that will survive the clean break.
- Do not preserve `arnold.runtime` as a second public runtime surface unless a specific module is explicitly re-chartered as neutral API.

## Suggested Run

`partnered-5/thorough/high`

Runtime and resume bugs can pass ordinary tests while corrupting durable workflow state, so this needs the highest planning tier plus thorough critique.
