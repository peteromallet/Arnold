# M5c — Control plane: run-outcome vocabulary + the control interface (F6 → F7; F7 ships LAST)

**Epic:** Pipeline Unification. **Milestone of record:** PROGRAM.md M5c (§255–268) — *last and hardest of the
value layer (T2)*. **Tier/robustness:** premium · thorough/high. **Sequencing:** F6 (halt-and-wait) lands
first; **F7 (the operator action that mutates and un-halts) ships separately, LAST in the M5 group.**
**Depends on:** **M4** (PROGRAM §261 — fires the RecoveryPolicy spine `classify(error)→{retry|escalate|halt}`),
**M5b** (maps execute outcomes into the run-outcome vocabulary), **M3** (the **realized graph** — `recover` =
`predecessors(stage)`, NOT a persisted map; mid-run `set-robustness` re-realizes the topology; the versioned-
mutation envelope: mutation = a CAS event, not LWW), **M2** (typed Ports + StateDelta — control mutations are
versioned port/state writes), **M5a** (the node library that hosts the `clarify` node).
**Grounded:** 2026-05-29 against current `main`. **Authorities:** SYNTHESIS missing-abstraction #4 (the control
interface); SYNTHESIS Theme-D / over-complication §216–219 (no persisted 4th copy); `a3-human-recovery`
(the `workflow_next` projection contract; forward-vs-reverse split). **Blockers resolved:** REGISTER §2 rows
(clarify/verify-human/the-9-actions/recover-blocked/`ChainSpec.escalate_action`) + §3 M5c defaults.

> **Locked framing.** The control plane is the canonical case where **"planning keeps only content" is FALSE**
> (SYNTHESIS Theme D). The SDK owns a thin **control interface**; planning's `STATE_*`, its 9 override actions,
> `build_gate_artifact`, and the reverse-recovery maps become a planning **BINDING that IMPLEMENTS** that
> interface — exactly as the 4-verdict enum was evicted from `JoinFn` in M2.

---

## Outcome

A general **run-outcome / control vocabulary** + a control interface any run-type implements, planning re-expressed
as the first binding, and the per-run inspectors reading the general vocabulary instead of planning's `STATE_*`:

1. **The run-outcome enum** `{succeeded, failed, escalated, blocked, awaiting_human}` — the SDK-owned terminal/
   pausable vocabulary both F7 (control) and (later) F8 (supervisor, M5d) branch on. Replaces branching on
   planning's terminal `STATE_*` literals.
2. **Queryable projections** — `valid_targets(state)` (forward) and `recover_targets(state)` (reverse), both
   **computed on demand from M3's realized graph** (`recover_targets` = `predecessors(stage)`), NOT a fourth
   persisted copy that drifts after a mid-run `set-robustness`.
3. **The control interface** — a `(read_valid_targets, apply_transition, synthesize_artifacts)` trio the binding
   IMPLEMENTS. The SDK owns ONLY: invocation, event emission, the **versioned-mutation envelope** (M3 — mutation
   = a CAS event, not LWW), and the **projection** (queried from the realized graph). Everything domain-shaped
   lives in the binding.
4. **F6 — `clarify` / human-gate**: a general `clarify` node (ask → block → resume on answer) + a driver-level
   pause/resume hook persisting a resume cursor (`awaiting_user.json`). Planning's prep-clarification +
   `STATE_AWAITING_HUMAN` / `STATE_AWAITING_HUMAN_VERIFY` semantics are the binding.
5. **F7 — the control/override plane**: planning's `_OVERRIDE_ACTIONS` (the 9 actions) become bindings of general
   control ops; **no planning mechanism survives in the shared layer.**
6. **Per-run inspectors de-planning-ized**: `status`/`introspect`/`cost`/`trace` read the general run-outcome
   vocabulary + the projection, not `state["current_state"]` `STATE_*` literals directly.

**Acceptance (load-bearing):** the CI grep gate forbids `STATE_*` as **mechanism** in SDK modules (the mirror of
M2's `GateRecommendation` gate). The three phase↔state maps collapse to ONE realized-graph relation.

---

## Scope (piece + binding + current code, file:line verified on main)

### F6 — `clarify` / human-gate (lands first)
- **Current code.** Halt surface = `STATE_AWAITING_HUMAN` (imported `override.py:12`; `resume-clarify` gate
  `override.py:851`, `source=="prep"→STATE_PREPPED` `override.py:854`). Pause file `awaiting_user.json` written
  on `halt_reason=="awaiting_user"` (`_pipeline/executor.py:264,376`), read by `check_awaiting_user`
  (`_pipeline/resume.py:104`) and reloaded by `_pipeline/run_cli.py:271`. `verify-human` requires
  `STATE_AWAITING_HUMAN_VERIFY → STATE_DONE` (`handlers/verifiability.py:215,275`).
- **Piece (general, SDK).** (i) a `clarify` node in the M5a library (ask → block → resume); (ii) a driver
  pause/resume hook — "halt for external input, persist a resume cursor, resume from cursor" — riding M3's
  loop/process hook. F6 is **halt-and-wait**; F7 is **the operator action that mutates and un-halts**.
- **Binding (planning).** prep's clarification content + `clarification.source` discrimination; the criteria-
  verification gate content; `STATE_AWAITING_HUMAN` / `_VERIFY` mapped onto the general `awaiting_human` outcome.

### F7 — the control/override plane (ships LAST — densest coupling in the codebase)
- **Current code.** `handlers/override.py` carries **39 `STATE_*` references** (verified) and **9 actions**
  (`_OVERRIDE_ACTIONS`, `override.py:898`): `add-note`, `abort`, `force-proceed`, `replan`, `recover-blocked`,
  `resume-clarify`, `set-robustness`, `set-profile`, `set-model`.
  - `force-proceed` **synthesizes a gate artifact** via `build_gate_artifact(...)` (`override.py:297`),
    `recommendation="PROCEED"`, writes `gate.json`, flips `STATE_CRITIQUED/BLOCKED → STATE_GATED`.
  - `recover-blocked` owns `_BLOCKED_RECOVERY_STATES` (`override.py:399–409`) — a reverse-edge map with **no
    forward edge** (realized graph returns `[]` for blocked). A *second* copy of the workflow's reverse edges;
    `_RESUME_ACTIVE_STATES` (`workflow.py:326`) + `resume_plan` (`workflow.py:339,364`) is a *third*.
  - `set-robustness`/`set-profile`/`set-model` mutate `state.config` to take effect next phase.
- **Piece (general, SDK).** The **control service**: typed out-of-band ops (`force-advance`, `re-route`,
  `recover-from-stuck`, `reconfigure`, `annotate`, `abort`) over a running driver, each mutating persisted state
  through the **versioned-mutation envelope** (M3) + emitting a **control event**, independent of in-graph flow.
  It consumes `workflow_next`'s **dynamic, state-derived projection** (`workflow.py:282`) for valid-next hints —
  NOT static graph edges (would print wrong recovery commands on reduced-robustness plans, a3 §2.1).
- **Binding (planning).** All 9 actions implement the interface in planning's vocabulary: the `STATE_*` names,
  `build_gate_artifact` mechanics, the three reverse-recovery maps (now derived from the realized graph's
  `predecessors()`, exposed as a queryable API), the strict-notes invariant, the 1–5/profile/model reconfig
  semantics. **The binding is BEHAVIOR, not content.**

### Per-run inspectors — de-planning-ized HERE
- `cli/status_view.py` reads `STATE_BLOCKED` (`:271,749`), raw `current_state` (`:774,792`), and
  `awaiting_human_verify` (`:892`) directly → re-route through the run-outcome vocabulary + the projection.
- `observability/introspect.py` computes `block_details`/`recoverable_via` from `workflow_next` (`:373`) and raw
  `current_state` (`:349`) → consume `recover_targets(state)` and the `blocked` run-outcome, not planning literals.

---

## Locked decisions

- The vocabulary `{succeeded, failed, escalated, blocked, awaiting_human}` + `valid_targets`/`recover_targets` is
  SDK-owned; the `(read_valid_targets, apply_transition, synthesize_artifacts)` trio is the interface the binding
  IMPLEMENTS. SDK owns ONLY invocation + event-emission + versioned-mutation envelope + the projection.
- **The projection is QUERIED from M3's realized graph, never persisted.** Forward = `valid_targets` via
  `workflow_next`'s projection; reverse = `predecessors(stage)` on demand. **No fourth persisted copy** — persisting
  it (even "derived from one relation") reintroduces a copy that drifts after mid-run `set-robustness` (SYNTHESIS
  §216–219). The three current phase↔state maps (`_BLOCKED_RECOVERY_STATES`, `_RESUME_ACTIVE_STATES`,
  `workflow_next`) collapse to ONE realized-graph relation.
- **a3's split is the design constraint:** only the **forward-progress** half (`force-proceed` along the
  critiqued/executed path, `replan`, `resume-clarify`) maps cleanly to general transitions; **`recover-blocked`
  and `resume_plan` are reverse projections with no forward edge** — handle via `predecessors()`, NOT a 4th
  persisted copy and NOT a forward-edge fiction.
- `STATE_*`, the 9 actions, `build_gate_artifact`, the reverse maps are **planning's BINDING**. Evict `STATE_*`
  from the shared layer exactly as the 4-verdict enum was evicted from `JoinFn`.
- F6 ships first (halt-and-wait); **F7 ships separately, LAST** in the M5 group.
- Control mutations write through the M3 versioned-mutation envelope (and the M4 config-precedence resolver where
  it lands) — not blind `state.config` pokes.
- **Strangler discipline (PROGRAM §362–389):** the new control interface lands `{old-path default-ON, new-path
  default-OFF behind a flag}` — `STATE_*`-machine override stays live and authoritative; the new control service
  runs BESIDE it with back-compat aliases. **No organ-swap + old-path-deletion in one PR.** The old `STATE_*`
  state machine is retired ONLY after **≥1 full milestone of dual-run green AND** the milestone's oracle (the full
  recovery/escalate/blocked matrix replay, below) is green — the **behavioral-replay oracle is the sole retirement
  authority, never the happy-path parity gate.** (Actual deletion of `_BUILTIN_NAMES`/relocation is M6, not here.)

## Open questions (each RESOLVED to its default — zero human blockers; REGISTER §3 M5c)

1. **Where does "general control op" end and "planning transition semantics" begin?** (REGISTER's single biggest
   M5c seam.) **RESOLVED:** `apply_transition` is general (move state X→Y + emit event); `synthesize_artifacts` is
   the binding hook `force-advance` calls so the SDK never knows what a `gate.json` is. The *act* of forcing-advance
   is general; the *artifact* is wholly binding. Resolution recorded in this brief; no human touch.
2. **Does `recover_targets` need a typed reverse-edge variant on the realized graph?** **RESOLVED:** raw
   `predecessors()` is enough (blocked/failed return `[]` — off-graph outcomes); upgrade to a typed reverse-edge
   variant ONLY if a parity/characterization test demonstrably needs it (machine-gate decides, not a person).
3. **Granularity of the gate predicates** (the graph has 3 coarse `kind="gate"` edges; force-proceed-from-blocked
   needs the fine `gate_proceed_agent_availability_blocked` distinction). **RESOLVED:** the predicates live as
   **binding-side resolvers the projection invokes**; the SDK keeps the 3 coarse gate edges. No edge-metadata
   bloat on the SDK graph.

## Constraints

- **Parity (a3 §4.4):** `workflow_next` over the graph-backed projection must equal the legacy dict-backed impl
  across `{5 robustness} × {with_prep, with_feedback} × {all states} × {all gate recommendations}`. Recovery hints
  must not silently drift (the gate TIEBREAKER→ITERATE auto-downgrade is this class already biting — MEMORY
  `gate_tiebreaker_downgrade`). **Parity is necessary but NOT the retirement gate.**
- **All 9 override actions behave identically post-extraction** — characterization tests over `override.py`
  (`tests/test_override_strict_notes.py` + new), incl. the `force-proceed` ESCALATE strict-notes guard; no silent
  gate auto-downgrade regressions.
- **Recovery branches are first-class in the oracle.** Per PROGRAM open-risk #2, the behavioral-replay corpus MUST
  include recorded recovery/escalate/**blocked-retry-then-resume** traces (the exact class recurring in MEMORY:
  execute-stall, shannon-stream-stall, chain-blocked-retry); the matrix-oracle replays them through the new control
  path. (MEMORY `chain_blocked_retry`: the hardcoded `max_blocked_retries=1` regression — the recover-blocked
  binding must honor a retry budget `>1`.)
- **Zero-human-blocker control flow (REGISTER §2):** the 9 actions are auto-fired by M4's RecoveryPolicy spine via
  `classify→{retry,escalate,halt}` (named actions stay human-available but never required); `force-proceed`
  strict-notes default-off for autonomous runs; recover-blocked auto-generates reason+classification (else falls
  into chain policy); `awaiting_human` auto-resolves via brief/prep-research → stronger model → best-guess+flag,
  never indefinitely parks; `STATE_TIEBREAKER_PENDING` auto-invokes `tiebreaker-run`. Escalation ladder (REGISTER
  §3 chain.yaml): retry ×2 → bump profile/robustness one tier → `stop_chain` + auto-ticket. No park on a human.
- Back-compat: `extra="ignore"`; `handle_*` `__all__` shims; preserve `MEGAPLAN_*`; keep planning state names valid
  in profiles. Don't dogfood off an editable install (pinned engine); schema report-only until the last milestone.

## Done criteria (testable; incl. the oracle gate)

- [ ] The run-outcome enum `{succeeded, failed, escalated, blocked, awaiting_human}` + `valid_targets` /
      `recover_targets` ship as an SDK piece; `recover_targets` reads M3's realized graph (`predecessors`), with
      **no persisted 4th map** (asserted: grep finds no new persisted recovery dict in SDK modules).
- [ ] The `(read_valid_targets, apply_transition, synthesize_artifacts)` control interface exists; planning
      implements it as a binding; `synthesize_artifacts` is the only path that knows `gate.json` (unit-asserted).
- [ ] F6: a `clarify` node + driver pause/resume hook land; `STATE_AWAITING_HUMAN(_VERIFY)` map onto the general
      `awaiting_human` outcome; the `awaiting_user.json` resume cursor round-trips (executor → resume → run_cli).
- [ ] F7: all 9 actions re-expressed as bindings of general control ops; `build_gate_artifact` + the reverse maps
      live in the binding; characterization tests prove byte-identical behavior incl. strict-notes + escalate guard.
- [ ] Per-run inspectors (`status`/`introspect`/`cost`/`trace`) read the run-outcome vocabulary + the projection,
      not planning `STATE_*` literals (`status_view.py`, `introspect.py` cleaned; grep-asserted).
- [ ] **GREP GATE:** NO non-planning (SDK) module carries `STATE_*` as mechanism (CI gate, mirror of M2's
      `GateRecommendation` gate). The three phase↔state maps derive from ONE realized-graph relation.
- [ ] **PARITY:** the a3 §4.4 `workflow_next` parity test is green across the full `{robustness}×{prep,feedback}×
      {states}×{gate recs}` matrix.
- [ ] **ORACLE GATE (sole retirement authority):** the behavioral-replay oracle replays recorded REAL-run
      recovery/escalate/**blocked-retry-then-resume** traces through the new control path and matches; old `STATE_*`
      machine retired only after this is green AND ≥1 full dual-run-green milestone (strangler discipline). Dual-run
      green: OLD `STATE_*` override still drives a throwaway plan AND a planning-shaped plan runs the new control
      interface behind the default-OFF flag.

## Touchpoints

`megaplan/handlers/override.py` (F7 — 9 actions `_OVERRIDE_ACTIONS:898`, 39 `STATE_*`, `build_gate_artifact:297`,
`_BLOCKED_RECOVERY_STATES:399`); `megaplan/_core/workflow.py` (`workflow_next:282`, `resume_plan:339,364`,
`_RESUME_ACTIVE_STATES:326`); `megaplan/_core/workflow_data.py` (`WORKFLOW`/`_ROBUSTNESS_OVERRIDES` — realized-graph
projection input); `megaplan/handlers/verifiability.py` (`verify-human`, `STATE_AWAITING_HUMAN_VERIFY:215`, F6);
`megaplan/_pipeline/resume.py:104` (`check_awaiting_user`) + `megaplan/_pipeline/executor.py:264,376`
(`halt_reason=="awaiting_user"`) + `megaplan/_pipeline/run_cli.py:271` (resume cursor reload, F6); the M3
realized-graph module (`predecessors()` source). Inspectors: `megaplan/cli/status_view.py` (`STATE_BLOCKED:271,749`),
`megaplan/observability/introspect.py` (`workflow_next:373`, `current_state:349`). Tests:
`tests/test_override_strict_notes.py`, the characterization import-surface test, the a3 §4.4 parity suite.

## Anti-scope

- **F8 / supervisor tier (M5d)** — invokes general control ops (not "force-proceed" by name); depends on M6 + the
  process driver. M5c only ships the vocabulary F8 branches on (incl. `awaiting_human` for the PR-merge wait).
- **The M3 realized-graph layer itself** — M5c CONSUMES it (`predecessors`, the projection); does not build it.
- **The M6 relocation** (planning → discovered pack, drop `_BUILTIN_NAMES`, `arnold` namespace, the actual deletion
  of the old `STATE_*` machine root) — M5c makes the control plane composable; M6 makes planning discovered. **No
  organ-swap + old-path-deletion lands in M5c.**
- **Cloud's operator loop** (`cloud/cli.py::_phase_command`) — wraps the supervisor tier; not M5c.
- **F1–F5** (node-library macros, fan_out, escalate, tiering, execute task-DAG) — M5a/M5b.
- **New verbs / re-tuning planning's prompts** — decoupling only; content moves verbatim.
