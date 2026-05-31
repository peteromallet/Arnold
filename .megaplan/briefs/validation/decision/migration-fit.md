# Planning migration-fit map — services/drivers/packages model

Tested against the v3 umbrella model (`.megaplan/briefs/pipeline-unification-EPIC.md`): shared
SERVICES (dispatch/store/emit/evidence/config) injected by an Arnold parent; DRIVERS
(graph/loop/oneshot) = how a package runs; NODE library (`patterns.py`); PACKAGES =
manifest + driver + domain code.

Classification key: (a) SHARED SERVICE · (b) NODE/capability · (c) DRIVER feature
(graph-runtime) · (d) PACKAGE-LOCAL domain · (e) NO HOME / ill-fitting.

## The structural reality the model must absorb

The PRODUCTION planning path is **not** the `_pipeline` graph executor. It is a
**state-machine driven by subprocess-per-phase**:
- `_core/workflow.py` `WORKFLOW` dict + `_ROBUSTNESS_OVERRIDES` + `_transition_matches`
  decides the next phase from `state["current_state"]` + `last_gate.recommendation`.
- `auto.py` (2,468 LOC) is the real driver: it loops `status → next_step`, **spawns each
  phase as a fresh `python -m megaplan <phase>` subprocess** (`runtime/process.spawn`),
  watches phase_result.json/state.json mtime for liveness, and applies retry/escalate
  policy. Each handler is a CLI entrypoint that loads state, runs one worker, writes
  state.json + artifacts + phase_result.json + receipt, exits.
- `_pipeline/executor.py` (in-process DAG walk, `SubloopStep`, `FaultRegistry`,
  `HumanDecisionStep`, `run_pipeline_with_policy`) is a **parallel, largely-unwired
  Sprint-1..5 reimplementation** used by jokes/doc demos and tests — NOT the path real
  plans run through. So "planning becomes a graph-driver package" is not a rename; it is
  a port from a subprocess state-machine onto an in-process DAG that does not yet carry
  planning's real semantics.

## Feature inventory

### Cleanly SHARED SERVICE (a)
- **Store / state durability** — `store/` Protocol already shared by `plan_repository` +
  resident. Canonical. ✔
- **Worker dispatch core** — `workers/run_step_with_worker` (subprocess + stream parse +
  key-pool `runtime/key_pool`) and resident's async runner do collapse to one `dispatch`
  contract. ✔
- **Cost attribution / receipts** — `receipts/`, `pricing/`, `history[].cost_usd`. Pure
  cross-cutting; rides on dispatch. ✔ (canonical.py/drift.py are planning-schema-shaped →
  (d) tail.)
- **Emit / events** — `observability/events` ndjson + Store `EpicEvent`; the model's
  stated M4 merge. ✔
- **Config base** — args bus / `ResidentConfig` → base config a package extends. ✔
- **Profiles / tiers / agent routing** — `profiles/`, `DEFAULT_AGENT_ROUTING`,
  tier-spec resolution. Shared resolver, package supplies the phase-name vocabulary. ✔

### NODE / capability (b)
- `patterns.py` (`critique_revise_gate_loop`, `panel_parallel`, `dynamic_fanout`,
  `majority_vote`, `phase_zero_gate`, `escalate_if`, `iterate_until_consensus`,
  `paired_round`) + step kinds produce/judge/decide. ✔ Already this layer.
- `prep_research` scatter-gather fan-out (`_core/hermes_fanout.scatter_gather`) +
  `parallel_critique` — generic read+write fan-out primitives. ✔
- `FaultRegistry` — generic judge-side finding tracker. ✔
- `HumanDecisionStep` / `awaiting_user.json` pause-resume — generic node. ✔ (but see e3)

### DRIVER feature — graph-runtime (c)
- In-process DAG walk, edge dispatch (gate/normal/override edges), parallel-stage thread
  isolation, output verification, `run_pipeline_with_policy` (stall/cost/escalate hooks).
- `SubloopStep` as the executor primitive behind tiebreaker. ✔ (the *child pipeline* is (d))

### PACKAGE-LOCAL domain (d)
- All prompts (`prompts/`), output schema (`schemas/`), the 4-verdict gate vocabulary
  (PROCEED/ITERATE/TIEBREAKER/ESCALATE), criteria, plan-structure validation,
  `parallel_critique` lens selection, tiebreaker child-pipeline (researcher→challenger→
  synthesis), per-phase prompt builders, verifiability/criteria checks.
- Complexity adjudication (`finalize.py` tier 1-5 + justification hard-reject;
  `execute/batch.py` per-batch tier→model). Domain rule, rides on dispatch+profiles. ✔

## (e) NO-HOME / ill-fitting — the gaps that force the model to change

1. **The phase state-machine + robustness-reshapes-the-graph.** `WORKFLOW` +
   `_ROBUSTNESS_OVERRIDES` + `with_prep`/`with_feedback`/`creative` don't just *configure*
   a graph — they **rewrite the node/edge set per run** (bare drops critique+gate; light
   collapses critique→gate; feedback rewires execute→review→feedback). The graph driver's
   `Pipeline` is a *static* `stages`/`edges` map; nothing in the model expresses
   "robustness/flags mutate the topology at init from stored config." This is neither a
   node nor a driver feature as specified — it is a **graph-construction policy** with no
   home. The model needs a package-local *graph-builder-from-config* hook the driver
   honors, or robustness must be elevated to a first-class driver input. **Biggest gap.**

2. **`auto.py` as subprocess orchestrator vs. graph as in-process walk.** The real driver
   spawns isolated per-phase processes for crash/context/stall isolation, OOM survival,
   and `--clean-worktree`. The `graph` driver runs stages in-process. These are *different
   execution substrates*, not one driver with config. The model has no "each node is its
   own OS process" driver variant; collapsing them risks losing context-exhaustion retry,
   per-phase idle-timeout kill, and worktree isolation. Either `auto`'s subprocess loop is
   a **third driver shape** (the model says "no speculative shapes" — but this one is real
   and load-bearing) or the graph driver must grow a process-isolation mode. No home today.

3. **Cross-cutting human-gate / resume / blocked state spanning the whole machine.**
   `STATE_AWAITING_HUMAN`, `STATE_AWAITING_HUMAN_VERIFY`, `STATE_BLOCKED`, `resume_cursor`,
   and the 9 override actions (`force-proceed`, `replan`, `recover-blocked`,
   `resume-clarify`, `set-robustness`, `set-profile`, `set-model`, `abort`, `add-note`)
   are **out-of-band state transitions** injected between phase subprocesses — they mutate
   `current_state`, gate.json, debt registry, phase_model. The graph executor's
   `HumanDecisionStep` only models a single in-graph pause/resume choice; it cannot express
   "an external operator re-points robustness/profile/model or recovers a blocked phase
   mid-run." Override is a **control plane over the driver**, not a node. No home — needs a
   shared `control`/override service the model currently omits from its 5.

4. **Chain/epic orchestration spanning packages.** `chain/__init__.py` (1,820 LOC) drives
   N milestone plans, each via `auto_drive`, with git branch/worktree ops, dependency
   ordering, `on_failure`/`on_escalate` semantics, `.chains/` progress. This orchestrates
   *across* package runs — it is neither a service, node, driver, nor package. It is a
   **meta-driver / supervisor tier** the four-layer model has no slot for.

5. **Cloud wraps the whole process, not a package.** `cloud/` + `mp-supervise` +
   `supervise.py` provision a container and run `megaplan auto`/`chain` as the entrypoint,
   tick an operator loop, manage extra_repos + chain_session multi-tenancy. Cloud assumes
   "the unit deployed is a long-lived process running the subprocess driver," which the
   in-process services/drivers model dissolves. Coupled to auto+chain (the (e2)/(e4) gaps).
   No home — sits *above* the umbrella.

6. **Bakeoff = parallel package-runs + blind compare/merge.** `bakeoff/` spins multiple
   worktrees, runs the same plan under different profiles, blind-judges, merges a winner.
   Another **across-runs supervisor**, same missing tier as chain.

7. **Two next-step encodings that must stay in sync.** `workflow_next` (state-machine) and
   the graph's `edges` are independent encodings of "what runs next"; the model's "keep
   `workflow_next` as a thin projection over edges" assumes (e1) is solved. Until topology-
   from-config has a home, this projection cannot be faithful (proven by the
   gate→TIEBREAKER→ITERATE silent-downgrade memory: schema/encoding drift already bites).

## Verdict

**YES-WITH-ADDITIONS** (leaning toward needs-rework on the biggest two).

The five services + graph/loop drivers + node library + packages genuinely absorb the
*majority* of planning's surface: dispatch, store, emit, cost, profiles, patterns,
fan-out, fault tracking, and all prompt/schema/verdict domain logic map cleanly. The model
is directionally right.

But it is **not sufficient as written**. Four real, load-bearing features have no slot and
would force additions, not just authoring:
- a **graph-construction-from-config** mechanism (robustness/flags reshaping topology) — e1;
- a **process-isolation driver mode** to preserve what `auto.py` buys (e2);
- a **control/override service** for out-of-band human-gate/blocked/resume/re-route (e3);
- a **supervisor/meta-driver tier** above the umbrella for chain, bakeoff, and cloud
  (e4/e5/e6).

None are speculative — all are in production today. The model accommodates full migration
only if it adds these; the "four layers, two drivers, five services" framing as currently
bounded leaves the orchestration-above-a-run and reshape-a-run dimensions homeless.
