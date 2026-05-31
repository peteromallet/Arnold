# Arnold SDK — the EDGE MAP (definitive enumeration of every boundary/seam)

**Status:** validation artifact, 2026-05-29. Derived from `.megaplan/briefs/pipeline-unification-EPIC.md`
("Structural pieces", "Resolved over-builds") + `.megaplan/briefs/validation/interrogation/SYNTHESIS.md`
(every theme is an edge being violated), grounded in code.

## Framing — what an "edge" is and why enumerate them

The EPIC defines *abstractions* (Port, realized-graph, policy spine, run-outcome vocabulary, trust
boundary, contract-checker) but never enumerates its **boundaries** as one coherent set. An edge is
a seam where a value of a declared type crosses between two owners under a contract. Leaks and
ambiguity live exactly where an edge is asserted but not given (a) a name, (b) an owner, (c) a typed
payload, and (d) a fail-loud check. The single deepest finding of the interrogation — `STATE_*`
leaking across the SDK-surface/app edge at the control plane — is precisely an edge with no contract.
The list below is the holistic answer to "what are the EDGES?"

Each edge: **definition · owner · what crosses (type) · where it is FUZZY/VIOLATED (file:line) ·
what the plan must do · CRISP-or-FUZZY today.**

---

## 1. Namespace edge — `arnold` (umbrella) | module (planning/resident/jokes) | SDK library

- **Definition.** Three distinct identities: the `arnold` umbrella (the product/CLI brand and
  cross-module orchestration), a *module* (a domain app: planning, resident, jokes — manifest +
  driver + bindings + SKILL.md), and the *SDK library* (the general pieces/nodes a builder composes:
  `patterns.py`, Port, drivers, dispatch/emit/evidence, run-outcome vocab). The distinction: SDK =
  "would an unrelated builder want this?"; module = domain content; umbrella = the shell that
  discovers and runs modules.
- **Owner.** The epic / namespace authority (M6). No module owns the umbrella; no SDK piece owns a
  module's content.
- **What crosses.** A module name + manifest metadata flows *up* to the umbrella's registry; the SDK
  pieces flow *down* into a module as imported library symbols.
- **FUZZY / VIOLATED.** There is no `arnold` namespace yet — everything lives under `megaplan.*`, and
  planning is privileged by name: `_BUILTIN_NAMES = frozenset({"planning"})` (`registry.py:53`,
  consulted `:154`, `:382`). Planning is not discovered as a module; it is hardcoded. The SDK library
  itself lives under a private `_pipeline` prefix (`megaplan/_pipeline/*`), signalling "internal,"
  which contradicts it being the *public* builder surface.
- **Plan must.** M6: introduce the `arnold` namespace, relocate planning to a discovered module, drop
  `_BUILTIN_NAMES`, and promote the builder surface out of `_pipeline` privacy into a named public
  package. The three identities must be nameable in import paths.
- **Verdict: FUZZY.** Covered by M6 but M6 is the *last* milestone; the namespace split is asserted,
  not yet designed as a boundary. Adequately owned (M6) — does NOT need its own milestone.

## 2. Command edge — umbrella commands (any module/run) vs module commands (a module's domain)

- **Definition.** Umbrella commands operate on *any* run regardless of module (`status`, `chain`,
  `cost`, `pipelines check/doctor/new`, control ops). Module commands express a module's domain (the
  9 planning override actions; chain/epic/bakeoff orchestration is a *supervisor*-tier umbrella
  concern but today reads as planning-specific).
- **Owner.** Umbrella CLI (`megaplan/cli/parser.py`) for the first set; the module binding for the
  second.
- **What crosses.** A parsed subcommand + args dispatched to either a generic handler or a module
  binding's control interface.
- **FUZZY / VIOLATED.** The CLI is monolithic under `megaplan/cli/` with no umbrella/module split; the
  override handler (`handlers/override.py`) is planning-domain logic addressed as if it were a generic
  command. The run-outcome vocabulary that would let an umbrella command target *any* module's state
  does not exist (see edge 9a). Cross-ref `.megaplan/briefs/cli-spec-model-override.md`.
- **Plan must.** Define which verbs are umbrella (operate via the run-outcome `(read_valid_targets,
  apply_transition, synthesize_artifacts)` trio) vs module-local. The supervisor tier (M5d) must
  invoke *general* control ops, not "force-proceed" by name.
- **Verdict: FUZZY.** Partially covered by M5c/M5d + the run-outcome vocab; the umbrella/module command
  taxonomy itself is unstated.

## 3. SDK-surface vs app edge — pieces/nodes (general) vs a module's bindings — **THE most-violated edge**

- **Definition.** The boundary between general SDK pieces (`patterns.py` nodes, `JoinFn`, `Reduce[T]`,
  the executor, the control interface, the supervisor) and a module's bindings (prompts, rubrics,
  verdict→consequence mappings, `STATE_*` phase vocabulary). Test: a general piece must carry **zero**
  app vocabulary.
- **Owner.** The SDK owns the piece; the module owns the binding. The SDK owns *invocation, emission,
  versioned-mutation envelope, and the projection*; the binding *implements* the interface.
- **What crosses.** A binding registers callables/content with a general piece; a general piece calls
  back into a binding via a typed interface (reducer→app outcome, control trio).
- **FUZZY / VIOLATED (this is the leak hotspot).**
  - 4-verdict enum leaking into a general join: `JoinFn = Callable[..., StepResult]` is OK but
    `PromoteFn = Callable[[dict], GateRecommendation]` (`pattern_types.py:16`) hard-codes planning's
    4-verdict enum into a general signature. `GateRecommendation = Literal["proceed","iterate",
    "tiebreaker","escalate"]` is baked into `types.py:76` and threaded through `Edge.recommendation`
    (`types.py:104`), `StepResult`/`PipelineVerdict.recommendation` (`types.py:129`).
  - `STATE_*` leaking into the control plane / supervisor: **39 `STATE_*` references** in
    `handlers/override.py`, `build_gate_artifact` synthesizing a planning artifact
    (`handlers/override.py:297`), and `_BLOCKED_RECOVERY_STATES` — a reverse-edge map keyed on
    planning phases (`handlers/override.py:399`, consumed `:456`). This is the JoinFn→enum leak
    *recurring one tier up*, at run granularity, where the stress-test never looked.
- **Plan must.** M2 CI grep gate: ZERO `GateRecommendation` in SDK modules (partial conversion is
  worse than none). M5c: evict `STATE_*` from the control plane & supervisor exactly as the 4-verdict
  enum was evicted from `JoinFn`; planning's `STATE_*` *binds onto* the run-outcome vocabulary, never
  rides through a general piece. Acceptance: no non-planning binding carries `STATE_*` as mechanism.
- **Verdict: FUZZY (worst-served).** The verb side (M2) is crisp; the *run-granularity* side (M5c/M5d)
  is named but is the hardest, last, and least-designed. Needs the run-outcome vocabulary as its own
  designed piece (M5c) — see edge 9a.

## 4. Data edge — the typed Port between composed steps (kind/schema/cardinality/version)

- **Definition.** The channel one Step's output crosses to become another Step's input. Should be a
  `Port = (name, kind: artifact|value|stream, schema, cardinality, version)` resolved `consumes`↔
  `produces` at build time and bound at runtime.
- **Owner.** The builder owns build-time resolution; the executor owns runtime binding.
- **What crosses.** A typed value/artifact reference from upstream `produces` to downstream `consumes`.
- **FUZZY / VIOLATED (filesystem convention + silent fallback).** The Port does not exist. The Step
  protocol carries nothing about what it consumes/produces (`types.py:168` `class Step`; the inter-
  step surface is `outputs: Mapping[str, Path]` + `state_patch: Mapping[str, Any]` + `next: NextEdge =
  str`, `types.py:161-164`). The executor **never binds inputs from predecessor outputs** — it only
  existence-checks via `_verify_outputs` (`executor.py:137`, called `:255`/`:361`); inputs are frozen
  at pipeline entry. Resolution is by path convention with a **silent fallback to a file that may not
  exist**: `resolved[ref] = ctx.plan_dir / ref / "v1.md"` (`step_helpers.py:104`). Mis-wiring is caught
  only at runtime after dispatch + LLM cost (`LookupError` at `executor.py:299`/`:401`). The builder's
  advertised `inputs=[...]` DSL is stashed and never validated.
- **Plan must.** M2: land the typed Port + binder; `consumes`/`produces` on the Step protocol; fail
  `build()` on missing/typo'd/mistyped dep; executor binds ports at runtime; delete the `v1.md`
  fallback. `last_fanout_results` becomes a typed Port the fan-out join writes (it exists nowhere
  today). Acceptance: NO toy hand-rolls inter-step plumbing.
- **Verdict: FUZZY (2nd worst-served by blast radius).** Named for M2 but currently a fiction;
  retrofit touches executor, builder, step_helpers, subloop, every M5 binding. Covered by M2 — does
  not need its own milestone but is the M2 keystone.

## 5. State edge — durable Store vs transient working state; StateDelta; evolution split; restorable_boundary

- **Definition.** The boundary between durable persisted Store and transient in-memory working state,
  and the cross-transport merge (`StateDelta`: replace|accumulate|deep-merge + version, CAS). Plus the
  state-evolution axis (forward-only | reversible(snapshot/restore) | event-sourced) and the
  `restorable_boundary` — what is inside the snapshot blob vs the world side-effects outside it.
- **Owner.** The Store backend owns durability + merge contract; the driver owns snapshot/restore; the
  binding owns what its state schema contains.
- **What crosses.** A `StateDelta` from a Step into the Store; a snapshot blob out / restore in.
- **FUZZY / VIOLATED.** The cross-transport bridge is a **flat-key last-writer-wins merge** with no
  revision and no nesting: `executor_owned_keys` (`state.py:337`, applied `:364-373`) — the same
  lost-update class on the core composition path. No `StateDelta`, no CAS, no `version`. The
  snapshot/restore boundary is undefined: whole-blob restore rolls back the *record* but not the
  *world* (file edits, git checkout); M3's reversible toys mutate a world outside the blob, and
  `run(cmd)` (the only real undo) is deferred to M4. EPIC §36 "one Store" vs M4:39 "irreconcilable"
  contradiction is unresolved in writing.
- **Plan must.** M2: revision-aware CAS `StateDelta` replacing `executor_owned_keys` BEFORE the
  process driver + versioned Store land. M3: two honest evolution values (forward-only; reversible =
  forward + snapshot/restore) + an explicit `restorable_boundary` that fails LOUD under process/fan-
  out; event-sourced as a SEPARATE backend with its own contract. Amend EPIC §36 in writing.
- **Verdict: FUZZY.** StateDelta named for M2, restorable_boundary for M3; the world-vs-blob boundary
  is the subtle leak. Covered by M2+M3.

## 6. Trust edge — in-tree | blessed | quarantined; the import seam (exec_module = ACE); arnold_api_version; per-package quota/tenant

- **Definition.** The boundary at the package edge where untrusted external code enters the process,
  and the operator trust decision (in-tree / blessed / quarantined) gating it; plus the SDK-assigned
  `tenant_id` + per-package quota sub-budget, and `arnold_api_version` checked at discovery.
- **Owner.** The discovery/registry layer + an operator trust policy; the broker owns per-tenant quota.
- **What crosses.** Untrusted module code (the most dangerous payload in the system); a static
  manifest (name/driver/entrypoint/capabilities/SKILL/`arnold_api_version`) should cross *before*
  code.
- **FUZZY / VIOLATED (the security edge).** Discovery is **eager and executing**:
  `spec.loader.exec_module(module)` then `except Exception: return None` (`registry.py:336-339`,
  `# noqa: BLE001`). On M6 success, "drop a community package in `~/.megaplan/pipelines`" =
  **arbitrary code execution** of the author's top-level imports on the next `megaplan` command (the
  user scan root is `Path.home() / ".megaplan" / "pipelines"`, `registry.py:375`). Any import error /
  typo'd entrypoint makes a package **vanish with no error, warning, or log**. No `arnold_api_version`,
  no `tenant_id`, no per-package quota exist anywhere (grep-confirmed). a5 analysed only the runtime
  dispatch sandbox, never the import seam.
- **Plan must.** M6 (re-open a5 first): manifest-first **non-executing** discovery; defer `exec_module`
  to selected-to-run gated on operator trust tier; SDK-assigned `tenant_id` (not self-declared); per-
  package quota sub-budget reserved in the ledger schema NOW; `arnold_api_version` on the manifest.
- **Verdict: FUZZY (3rd worst-served).** Named for M6 but the import seam was explicitly out of a5's
  scope; this is a genuine ACE risk that the plan currently defers to the last milestone. Strong case
  for promoting the *non-executing manifest read* earlier or giving it its own design pass.

## 7. Substrate edge — `in_process` vs `subprocess_isolated` (kill/OOM/crash-isolation boundary)

- **Definition.** The isolation boundary: whether a Step runs in the host interpreter (`in_process`)
  or in a separate OS process (`subprocess_isolated`) that contains a mid-run kill / OOM / crash.
  Orthogonal to topology (graph; loop-control as a node) — NOT a flat 4-value driver enum.
- **Owner.** The driver tier (M3).
- **What crosses.** A dispatch request across the process boundary (today planning forks subprocess
  CLI; resident dispatches async-api in-process).
- **FUZZY / VIOLATED.** No driver/substrate concept exists in the pipeline layer (grep:
  `in_process`/`subprocess_isolated`/`oneshot`/`driver` return nothing in `types.py`/`builder.py`).
  The two real substrates live in separate worlds: planning's subprocess loop in `auto.py`; resident's
  async runner (`resident/agent_loop.py:5` asyncio, `:122` `asyncio.wait_for`). `oneshot` is a phantom
  (named in briefs, zero spec/user). The crash-isolation guarantee (process driver contains a kill;
  in-process loop does not) is untested.
- **Plan must.** M3: 2-axis driver model (substrate × topology); loop-control as a composable node;
  delete `oneshot` or give it a real contract. Elevate the crash-isolation done-criterion to an
  epic-level substrate-swap oracle. The cloud `_phase_command` shim is born here with the process
  driver.
- **Verdict: FUZZY.** Cleanly named and owned by M3; the over-build (4-value enum) is resolved in
  writing. Covered by M3.

## 8. Version/stability edge — stable | provisional | internal node tiers; compat contract vs reshapeable

- **Definition.** The boundary between what carries a SemVer compat contract (stable nodes,
  `arnold_api_version`) and what the epic may keep reshaping freely (provisional/internal). M5 calls
  `patterns.py` "public, documented, stable signatures" while the EPIC's whole purpose is to keep
  reshaping those types.
- **Owner.** The SDK release/versioning authority.
- **What crosses.** A version assertion at discovery; a node's stability tier on its declaration.
- **FUZZY / VIOLATED.** No stability tier and no `arnold_api_version` exist (grep-confirmed). Fixing
  `JoinFn`-returns-`GateRecommendation` is a free refactor *today*; post-M6-success it is an
  ecosystem-breaking change with no version gate to even detect the break. The
  contract-vs-reshapeable line is asserted (M5 "stable") and contradicted (EPIC "keep reshaping")
  simultaneously.
- **Plan must.** Reserve `arnold_api_version` + per-node-library stability tier
  (`stable|provisional|internal`) + deprecation/alias policy NOW, so the epic keeps reshaping
  provisional types while stable ones carry a contract. Tier each `patterns.py` node honestly.
- **Verdict: FUZZY.** "Reserve room" item; cheap now, a migration later. Covered as a cross-cutting
  reservation, not a milestone — but it directly contradicts M5's "stable" claim and needs that
  contradiction resolved in writing.

## 9. Edges the code/plan IMPLIES but did not name

### 9a. Control / run-outcome edge (the seam between a run's private state and any controller)
- **Definition.** The boundary where an umbrella controller (CLI, F7 control plane, F8 supervisor)
  acts on *any* run via a general vocabulary `{succeeded, failed, escalated, blocked, awaiting_human}`
  + `valid_targets(state)` / `recover_targets(state)`, with each module mapping its `STATE_*` onto it.
- **Owner.** SDK owns the vocabulary + projection + versioned-mutation envelope; the binding
  *implements* `(read_valid_targets, apply_transition, synthesize_artifacts)`.
- **VIOLATED.** Does not exist; controllers branch directly on planning `STATE_*` (39 refs,
  `handlers/override.py`). This is the *contract* edge 3 is missing at run granularity.
- **Plan must.** M5c design it as a first-class trio the binding implements. **This edge needs M5c as
  effectively its own milestone.** FUZZY.

### 9b. Policy-spine edge (driver ↔ recovery/budget/observability)
- **Definition.** The horizontal seam where the driver consults an injected `RecoveryPolicy`
  (`classify(error)→{retry_fresh|retry_transient|escalate|halt}`), ONE live budget authority (folding
  across fan-out shards), an N-layer config-precedence resolver, and a backend-agnostic observability
  event contract.
- **Owner.** The driver tier (M4).
- **VIOLATED.** auto.py is the de-facto policy spine but is never extracted ("retry" appears
  **104×** in `auto.py`); money lives in three uncoordinated ledgers with no single live authority;
  the dispatch request becomes a god-object carrying liveness+cost+brokers+shim.
- **Plan must.** M4: extract `RecoveryPolicy`, one budget authority (home = the key/rate broker — rate
  and spend are one shared-depletable-resource problem), config-precedence resolver, observability
  contract. FUZZY. Covered by M4.

### 9c. Routing edge (Step → next stage)
- **Definition.** The seam where a Step's outcome selects an outgoing edge. Should be ONE model: Step
  emits a routing key; a binding maps key→consequence; edges declared by key.
- **VIOLATED (over-complicated).** THREE concepts today: `Edge.label`+`StepResult.next` (normal,
  `types.py:88`/`:101`), `Edge.recommendation`+`verdict.recommendation` (gate, `types.py:90`/`:104`),
  plus M3's separate consequence map. `restore_and_diverge` is the only genuinely new one.
- **Plan must.** Collapse to one routing-key model; add `restore_and_diverge` as ONE new
  `kind='restore'` edge, not a parallel vocabulary. FUZZY. Covered by M2/M3.

### 9d. Realized-graph edge (static Pipeline ↔ the graph the driver walks)
- **Definition.** The boundary between the package-declared static `Pipeline` and the
  robustness-realized graph the driver actually walks; `build_topology(run_config)->Graph`,
  re-invocable mid-run, the SINGLE source for `next_step` projection AND `predecessors(stage)` recovery.
- **VIOLATED.** No realized graph exists. `_ROBUSTNESS_OVERRIDES` does true node/edge **rewriting**
  (`workflow_data.py:91`; `bare` deletes critique+gate, `with_feedback` rewires), folding cumulatively
  via `_ROBUSTNESS_WORKFLOW_LEVELS` (`workflow_data.py:116`). `workflow_next` (`workflow.py:282`) folds
  the stack, evaluates gate predicates, AND manufactures a synthetic `step` target in no edge — a thin
  edge-projection cannot produce that. Root cause of "3 next-step encodings" is the *absence* of a
  realized graph to project from.
- **Plan must.** M3: design the realized-graph as a first-class piece with the {5 robustness}×{prep,
  feedback}×{states}×{verdicts} parity test as an M3 GATE. FUZZY. Needs explicit M3 design.

### 9e. Strangler / old-engine ↔ new-engine edge
- **Definition.** The standing boundary (every milestone) where the OLD engine still boots + drives a
  throwaway plan AND a planning-shaped plan runs on the NEW pieces — guarded by a behavioral-replay
  oracle and substrate-swap oracles.
- **VIOLATED.** chain.yaml encodes the stale May-28 4-milestone v1 — the executable artifact points at
  the wrong map; happy-path parity gates are structurally blind to the substrate swaps they guard.
- **Plan must.** Regenerate chain.yaml as one triple with EPIC+briefs; add substrate-swap oracles
  (resume-across-versions, crash-isolation, version-skew). FUZZY. Standing gate, not a milestone.

---

## Summary table — owner · CRISP/FUZZY · the key leak

| # | Edge | Owner | Crisp? | Key leak |
|---|------|-------|--------|----------|
| 1 | Namespace (arnold/module/SDK) | M6 / namespace authority | FUZZY | planning hardcoded `_BUILTIN_NAMES`; SDK hidden under `_pipeline` |
| 2 | Command (umbrella vs module) | umbrella CLI / binding | FUZZY | no umbrella/module split; override is domain logic as generic cmd |
| 3 | SDK-surface vs app | SDK piece / module binding | FUZZY | **39 `STATE_*` + GateRecommendation in general pieces — most-violated** |
| 4 | Data / Port | builder / executor | FUZZY | no Port; `v1.md` silent fallback `step_helpers.py:104`; inputs never bound |
| 5 | State (Store/StateDelta/restorable) | Store / driver / binding | FUZZY | flat-key LWW `executor_owned_keys` state.py:337; world-vs-blob undefined |
| 6 | Trust (import seam/tiers/version) | discovery / operator policy | FUZZY | `exec_module` = ACE registry.py:336; silent vanish; no api_version/tenant |
| 7 | Substrate (in_process/subprocess) | driver tier (M3) | FUZZY | no driver concept; 2 substrates in separate worlds; oneshot phantom |
| 8 | Version/stability tier | SDK release authority | FUZZY | no api_version/tier; M5 "stable" contradicts EPIC "keep reshaping" |
| 9a | Control/run-outcome | SDK vocab / binding impl | FUZZY | controllers branch on planning STATE_* directly |
| 9b | Policy spine | driver tier (M4) | FUZZY | auto.py "retry"×104 never extracted; 3 money ledgers; god-object request |
| 9c | Routing | executor / binding | FUZZY | 3 routing concepts for 1 gate |
| 9d | Realized-graph | M3 | FUZZY | no realized graph; robustness REWRITES the graph (workflow_data.py:91) |
| 9e | Strangler old/new | standing gate | FUZZY | chain.yaml points at stale map; happy-path gate blind to substrate swap |

**No edge is fully CRISP today.** The closest-to-crisp (clean name + clear owner + over-build resolved
in writing) are **7 (substrate)** and **9c (routing)** — both fully owned by M3/M2 with their
contradictions already settled. Everything else is named but not yet given a fail-loud contract.

## The 2-3 edges most UNDER-SERVED by the current plan

1. **Edge 3 / 9a — SDK-surface↔app at the control plane (the `STATE_*` leak).** The most-violated edge
   and the one the plan treats most softly: M5c is named but is the last, hardest seam, and "planning
   keeps only content" is *false* here. Needs the run-outcome vocabulary designed as its own piece with
   an acceptance check that no binding carries `STATE_*` as mechanism. **Effectively needs M5c as its
   own milestone.**
2. **Edge 4 — the data Port.** Sold as "composition" but is a filesystem convention with a silent
   `v1.md` fallback; every acceptance toy passes green by hand-wiring it. Highest blast radius
   (executor/builder/step_helpers/subloop/every binding). Must land in M2 or it becomes a rewrite of
   M5 code.
3. **Edge 6 — the trust/import seam.** A real ACE on the first community package; a5 explicitly never
   examined the import seam, yet the plan defers the whole trust boundary to the *last* milestone (M6).
   The non-executing manifest read deserves promotion earlier or a dedicated design pass before M6.
