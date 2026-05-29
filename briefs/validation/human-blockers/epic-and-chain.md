# Human-blocker conversion — Arnold SDK EPIC + chain.yaml

Source docs:
- `briefs/pipeline-unification-EPIC.md`
- `briefs/epic-pipeline-unification/chain.yaml`
- supporting milestone briefs `m1..m7` and `validation/edges/{cli-migration,edges-map}.md`

GOAL: zero human blockers. Every design-time "open question / decide in writing / settled by Mx / flag to
the human" and every runtime "operator / reviewer / human-gate / approval" point is converted to one of:
(a) pre-made DEFAULT, (b) MACHINE-ENFORCED GATE, (c) AUTO-ESCALATION. `must_ask_peter` is false unless a
genuinely irreversible strategy/taste call — there are none here; the strategy call ("full vision, no demand
gate") was already made by Peter on 2026-05-29 and is recorded in the EPIC banner.

Legend: kind = design-time | runtime. mechanism = default | machine-gate | auto-escalation.

---

## A. chain.yaml driver / orchestration blockers (RUNTIME, build-of-the-epic)

### A1. `merge_policy: review` — every milestone PR waits on a human reviewer
- Location: `chain.yaml:77`
- Premade: **DEFAULT → flip to machine-gate.** Replace human review-before-merge with the EPIC's already-required
  machine gates: parity gate green (honestly labelled) + the M1 `pipelines check`/`doctor` graph linter +
  per-milestone strangler/substrate-swap oracles + the chain↔EPIC↔briefs lint. Auto-merge on all-green;
  auto-halt (stop_chain) on any red, which routes to A2/A3.
- Mechanism: machine-gate. Rationale: every milestone already ships its own gate; "review" duplicates that as a
  human wait. Reviewable diff is preserved by running off clean main (memory: worktree-carry breaks PR isolation).
- must_ask_peter: false

### A2. `on_failure: stop_chain` — a milestone failure parks the whole epic on a human
- Location: `chain.yaml:73-74`
- Premade: **AUTO-ESCALATION.** Before stop_chain, apply retry→escalate ladder: retry the failed milestone
  fresh (clean worktree) up to 2x; on persistent failure auto-bump the milestone's profile one tier
  (premium→apex) and re-run once; only then stop_chain AND auto-open a flagged ticket via megaplan-tickets.
  stop_chain stays as the final backstop, not the first response.
- Mechanism: auto-escalation. Rationale: matches the EPIC's own RecoveryPolicy spine (retry_fresh→escalate→halt);
  a bare stop_chain is the un-laddered version of exactly what M4 builds.
- must_ask_peter: false

### A3. `on_escalate: stop_chain` — an escalation halts and waits
- Location: `chain.yaml:75-76`
- Premade: **AUTO-ESCALATION.** On escalate, auto-raise robustness one level (thorough→extreme) and re-drive
  the milestone with the stronger model tier once; persist an escalation event; only stop_chain if the
  escalated re-run also fails. File a ticket on final halt.
- Mechanism: auto-escalation. Rationale: escalation is a signal to spend more compute, not to fetch a human;
  the strongest-model fallback is the platform's own auto-escalation policy.
- must_ask_peter: false

### A4. `driver.auto_approve: true` is set, but `megaplan auto` is known to bypass the approve gate
- Location: `chain.yaml:81` + memory `feedback_auto_gate_bypass`
- Premade: **DEFAULT (confirm no halt).** Keep `auto_approve: true`; it is the correct setting for autonomous
  drive. Per memory, flipping it does NOT actually halt before execute, so there is no hidden human gate here —
  document that auto runs straight through. No action needed beyond asserting the run never parks pre-execute.
- Mechanism: default. Rationale: already autonomous; the only risk was a false belief that it gates.
- must_ask_peter: false

### A5. `# "wait to run": do not chain start yet` — review-only spec, human must trigger start
- Location: `chain.yaml:10`
- Premade: **DEFAULT.** The single human "go" is the start of the autonomous run itself, not a mid-run blocker;
  once the chain↔EPIC↔briefs lint (M1/W8) passes green, the spec is self-certified ready and the chain may be
  started by the orchestrator. Treat lint-green as the auto-arm condition; remove the manual "wait" once lint exists.
- Mechanism: machine-gate. Rationale: "is the spec internally consistent" is exactly what the M1 lint answers;
  gate the start on it instead of a human eyeball.
- must_ask_peter: false

### A6. `base_branch: main` — runs fork main's dirty/untracked state (known false-positive source)
- Location: `chain.yaml:1` + memory `project_worktree_carry_review_falsepositive` / `_breaks_pr_isolation`
- Premade: **MACHINE-GATE.** Pre-run assertion: refuse to start a milestone unless the worktree is forked from a
  clean main (no carried WIP); auto-stash/auto-clean or auto-fail-loud with the recovery command. This prevents
  inherited noise from tripping the review/scope gates (which would otherwise summon a human).
- Mechanism: machine-gate. Rationale: clean-base is checkable; carried WIP is the documented cause of spurious
  review halts.
- must_ask_peter: false

---

## B. EPIC-level standing gates (the GATES are the conversion — confirm they auto-act)

### B1. Strangler boundary (gated EVERY milestone) — could be read as a human checkpoint
- Location: EPIC §199-203
- Premade: **MACHINE-GATE.** Encode as an automated per-milestone CI invariant: OLD engine boots + drives a
  1-milestone throwaway plan AND a planning-shaped plan runs on NEW pieces. Green → auto-proceed; red → A2 ladder.
- Mechanism: machine-gate. Rationale: it is already specified as an invariant; bind it to CI, not an operator.
- must_ask_peter: false

### B2. Behavioral-replay oracle + substrate-swap oracles — recorded-trace comparison
- Location: EPIC §200-202
- Premade: **MACHINE-GATE.** Recorded real-run traces vs each PR; resume-across-versions / crash-isolation /
  version-skew oracles run at the swap milestones (M3/M4/M6). Auto-pass on match, auto-halt+ticket on drift.
- Mechanism: machine-gate. Rationale: this is the whole point of an oracle — a deterministic automated judge.
- must_ask_peter: false

### B3. Parity gate "honestly labelled" — risk a human is asked to interpret partial parity
- Location: EPIC §217, every milestone constraint
- Premade: **DEFAULT.** Locked label: "control-flow/artifact parity on the happy path, NOT drift-provably-zero."
  Where the gate is structurally blind (substrate swap), the per-milestone oracle (B2) is the authority. No human
  interpretation step — the label is fixed text and the substrate fidelity is the oracle's machine verdict.
- Mechanism: default. Rationale: the wording is pre-decided; substrate fidelity is delegated to B2.
- must_ask_peter: false

---

## C. RUNTIME human-gates baked into the PRODUCT (must default-through or auto-escalate)

### C1. `clarify` / human-gate node — `STATE_AWAITING_HUMAN` (ask → block → resume on answer)
- Location: m5c F6 (`m5c-control-plane.md:39-62`); override.py:851; `_pipeline/resume.py:104`
- Premade: **AUTO-ESCALATION + DEFAULT.** The general `clarify` node must support a non-interactive policy:
  on a clarification request, first attempt auto-answer from the brief/context (prep already has the brief),
  then escalate to a stronger model to resolve the ambiguity, then proceed with a documented best-guess default
  and a flag — never block waiting for a person. The `awaiting_human` outcome stays as the *capability* for
  builders who opt in, but planning's default binding is auto-resolve.
- Mechanism: auto-escalation. Rationale: research/clarification is a known plan-quality bottleneck solvable by
  prep-fanout (memory `project_research_bottleneck`); a human answer is replaceable by stronger-model inference.
- must_ask_peter: false

### C2. `verify-human` / `STATE_AWAITING_HUMAN_VERIFY` — human verification gate before DONE
- Location: m5c F6 (`m5c-control-plane.md:56`); `handlers/verifiability.py`; cli-migration.md:75
- Premade: **MACHINE-GATE → AUTO-ESCALATION.** Replace the human verify step with the oracle/`run(cmd)` evidence
  path (M4): run the project's tests/oracle as the verifier; green → auto-advance to DONE; red → auto-escalate
  (retry → stronger model → skip+flag). `verify-human` survives only as an opt-in module binding, not the default.
- Mechanism: machine-gate (with auto-escalation on red). Rationale: "did the change work" is exactly what the
  M4 oracle answers automatically; human verify is the un-automated version.
- must_ask_peter: false

### C3. The 9 override actions (`force-proceed`, `recover-blocked`, `replan`, `resume-clarify`, `abort`, ...)
- Location: m5c F7 (`m5c-control-plane.md:64-83`); `override.py:898-910`
- Premade: **AUTO-ESCALATION.** These are operator levers; the autonomous default is the RecoveryPolicy spine
  (M4) invoking the *general* control ops automatically: a blocked/escalated run auto-fires recover-from-stuck /
  force-advance / reconfigure (set-robustness/profile/model up one tier) per the classify→{retry,escalate,halt}
  policy. The named override actions remain available for a human but are never *required* — the policy fires them.
- Mechanism: auto-escalation. Rationale: the override plane IS the recovery lever; M4's RecoveryPolicy is its
  autonomous driver (EPIC §126; "auto.py's brain, retry ×104, never extracted").
- must_ask_peter: false

### C4. Discovery trust tier — "operator trust decision: in-tree / blessed / quarantined"
- Location: m6 §46-61; edges-map.md:141-159; EPIC §137
- Premade: **DEFAULT (policy, not per-package prompt).** Pre-made trust policy: `in-tree` packages = trusted
  (auto-exec on select); `~/.megaplan/pipelines` and any out-of-tree package = `quarantined` by default,
  importable only inside the dispatch sandbox with the SDK-assigned `tenant_id` + capped quota sub-budget;
  `blessed` is granted only by an explicit allowlist file the operator may pre-populate (default empty). No
  interactive per-package decision — the tier is computed from provenance (path) against a static policy.
- Mechanism: machine-gate (manifest-first non-executing discovery enforces it). Rationale: trust is a function of
  origin, computable without a human; quarantine-by-default is the safe autonomous stance for ACE risk.
- must_ask_peter: false

### C5. `merge_policy: review` at the PRODUCT level (chain/epic supervisor) — runtime human review of child runs
- Location: m5d supervisor tier; cli-migration; same `review` concept the product offers
- Premade: **DEFAULT.** The supervisor's default merge_policy for product runs is `auto` (machine-gated on the
  same parity/oracle/contract checks), mirroring A1. `review` stays a builder-selectable option but is not the
  autonomous default.
- Mechanism: machine-gate. Rationale: consistency with A1; the gates are the reviewer.
- must_ask_peter: false

### C6. PR-merge wait — `STATE_AWAITING_PR_MERGE` (out-of-band human pause at run granularity)
- Location: m5d Open-Q#3 (`m5d-supervisor-tier.md:105-107`); `__init__.py:1213-1409`
- Premade: **AUTO-ESCALATION.** Bind it onto M5c's `awaiting_human` outcome with an auto-merge policy: when CI +
  the milestone gates are green, the supervisor auto-merges the PR (gh CLI) rather than waiting for a human click;
  on red, auto-escalate per A2. The human-click path remains opt-in.
- Mechanism: machine-gate (auto-merge on green) + auto-escalation (on red). Rationale: the merge decision is
  fully determined by the gate verdict already computed.
- must_ask_peter: false

### C7. `on_failure: stop_chain` semantics inside the supervisor tier (product chains)
- Location: m5d; mirrors A2 at product runtime
- Premade: **AUTO-ESCALATION.** Same ladder as A2 baked into the general supervisor's RecoveryPolicy: retry fresh
  → escalate model/robustness → halt+ticket. stop_chain is the floor, not the reflex.
- Mechanism: auto-escalation. Rationale: the supervisor must embody the same no-park-on-human policy it enforces.
- must_ask_peter: false

---

## D. DESIGN-TIME open questions (an executing agent stalls here without a default)

### D1. M1 W8 — does this epic author its own chain.yaml, or ship a lint that fails loud?
- Location: `m1-foundation.md:112-116`
- Premade: **DEFAULT.** Author the canonical chain.yaml under `briefs/epic-pipeline-unification/` (it now exists)
  and lint against it. The brief itself recommends this ("gives the lint a target").
- Mechanism: default. Rationale: a concrete artifact beats a perpetually-red lint; the file already exists.
- must_ask_peter: false

### D2. M1 — DB mirror: add `schema_version` column now or defer?
- Location: `m1-foundation.md` Open-Q (DB mirror); `_db/common.py:29`
- Premade: **DEFAULT.** JSON-path in M1; flag the DB column as a follow-up unless DB plans are in active use
  (the brief's own recommendation). A `grep`/usage check decides "in active use" mechanically.
- Mechanism: default. Rationale: avoids a coordinated migration on the foundation milestone; reversible.
- must_ask_peter: false

### D3. M1 — bare `run_pipeline` has no `max_iterations` cap; add a prod safety cap?
- Location: `m1-foundation.md` Open-Q (infinite-self-loop)
- Premade: **DEFAULT (do NOT smuggle a behavior change).** M1 preserves existing behavior for `policy=None`; a
  prod cap is added later as an explicit, tested change owned by M4's policy spine (per-class budgets), not
  incidentally in M1.
- Mechanism: default. Rationale: M1 is hygiene/foundation; budgets are M4's named job; avoids hidden behavior drift.
- must_ask_peter: false

### D4. M2 Open-Q#1 — how far does Port build-time resolution reach without M3's realized graph?
- Location: `m2-deplanning-types.md:168` (item 1, "the seam most likely to force a redesign")
- Premade: **DEFAULT (the brief's lean).** Check `consumes`↔`produces` against the fully-rewritten graph for each
  robustness level the parity gate exercises; defer mid-run re-realization to M3; rely on a loud runtime bind
  error for rewrite-induced gaps. Plus a machine-gate: a direct unit assertion that an unresolved/mistyped port
  fails build and a CAS conflict is caught.
- Mechanism: default + machine-gate. Rationale: the lean is stated; the unit assertion makes it self-verifying.
- must_ask_peter: false

### D5. M2 Open-Q#2/#3/#4 — aggregate type name; CAS conflict policy; `select` rule enum vs callable
- Location: `m2-deplanning-types.md:168` (items 2-4)
- Premade: **DEFAULT (the briefs' leans):** (2) new frozen `ReduceResult` surfaced as a typed Port;
  (3) fail-loud on CAS collision in-process (single-process optimistic versioning; leased Store is M4);
  (4) `select.rule` is a `Callable` with `top_1|top_k|threshold` named constructors mirroring the join factories.
- Mechanism: default. Rationale: all three have explicit leans and are additive/reversible type choices.
- must_ask_peter: false

### D6. M3 — snapshot granularity (whole-blob vs diff); reversible-snapshot persistence location
- Location: `m3-drivers-state.md:136` (items 1 & 3; marked "Non-blocking — pick whole-blob")
- Premade: **DEFAULT.** Whole-blob copy of `state.json` (matches LWW, honest first cut); persist reversible
  snapshots in a sidecar `.state-versions/<id>.json` under the per-plan `flock`, name-checked against
  `_write_forensic_backup` to avoid collision.
- Mechanism: default. Rationale: brief explicitly says non-blocking, pick whole-blob; sidecar path is specified.
- must_ask_peter: false

### D7. M3 — mid-run re-realization + live cursor: confirm the fold never points at a deleted node
- Location: `m3-drivers-state.md:136` (item 2, "the biggest design unknown")
- Premade: **MACHINE-GATE.** This is settled by the M3 GATE itself: the `{5 robustness}×{prep,feedback}×{states}
  ×{verdicts}` parity test plus a re-realization invariant — after any `set-robustness` rebuild, assert the
  resume cursor resolves to a live stage. Red → block the M3 merge (the collapse is unsafe until proven faithful).
- Mechanism: machine-gate. Rationale: the EPIC already makes the projection-fidelity a hard M3 gate; extend it to
  cursor-survival, no human adjudication.
- must_ask_peter: false

### D8. M3 — budget across fan-out shards (cannot accumulate across siblings)
- Location: `m3-drivers-state.md:136` (item 4, "Flag, don't solve")
- Premade: **DEFAULT.** M3 ships budget single-tenant/in-process; cross-shard folding is explicitly deferred to
  M4's budget authority. The brief says flag-don't-solve — that IS the decision.
- Mechanism: default. Rationale: ownership is already assigned to M4; M3 must not over-claim.
- must_ask_peter: false

### D9. M4 Open-Q#1-5 — RecoveryPolicy granularity; budget-authority home & quota coverage; cost-journal
  reconciliation; non-plan liveness sink; oracle's first real user
- Location: `m4-services.md:49`
- Premade: **DEFAULTS:** (1) `classify` consumes ExitKind/error-layer AND realized-graph position so
  `escalate`/`halt(kind)` can name a target via `predecessors(stage)`, while staying target-agnostic (no `STATE_*`).
  (2) Budget authority lives in `runtime/` next to `key_pool.py`; covers the Hermes/OpenRouter `acquire_key` path;
  Codex/Shannon subscription quotas are a *separate* shared semaphore, out of scope here; spend-folding reads a
  live in-broker accumulator. (3) `CostTracker` cap reads the live authority (plan + non-plan + fan-out); rollup
  is `--dispatch`-flag opt-in (d1 §3). (4) Injected-callback liveness sink (option b) for non-plan tenants —
  sufficient; add a scratch dir only if a tenant demonstrably needs it. (5) Oracle's first user = the `select`-
  tournament acceptance toy (the cleanest branching user). All have stated leans/evidence in the brief.
- Mechanism: default (with machine-gate: characterization-replay against recorded runs proves byte-identical
  single-process behavior). Rationale: each has an evidence-backed lean; replay is the automated guard.
- must_ask_peter: false

### D10. M5a Open-Q#1-3 — tier metadata shape; `PromoteFn` target type; where `arnold_api_version` lives
- Location: `m5a-node-library.md:75`
- Premade: **DEFAULTS:** (1) lightweight registry keyed by export name (no behavior change, readable by the
  non-executing contract-checker); confirm shape against M1's checker mechanically. (2) `PromoteFn` returns the
  M2 routing-key type (re-type against the real M2 surface, not a placeholder). (3) Reserve `arnold_api_version`
  in BOTH a `patterns.py` constant and a manifest field M6 reads — "reserve in both is fine" per the brief.
- Mechanism: default. Rationale: all are stated leans; (1) is checker-verifiable.
- must_ask_peter: false

### D11. M5b Open-Q#1-3 — F5 dependency semantics; reducer→M5c handoff type; `_is_blocking_deviation` location
- Location: `m5b-execute-realm.md:108`
- Premade: **DEFAULTS:** (1) keep the real DAG (`compute_task_batches` / `io.py:58` already does arbitrary
  `depends_on`); don't gold-plate. (2) F5 returns a typed `Reduce[T]` per-batch result; the planning binding maps
  it to `phase_outcome`; M5c re-homes `STATE_*` later (so F5 never imports `STATE_BLOCKED`). (3) merge stays
  mechanical; deviation→outcome classification moves to the reducer (don't weaken the blocking-deviation fidelity,
  just relocate it).
- Mechanism: default (machine-gate: no silent gate/status auto-downgrade regression test — memory
  `project_gate_tiebreaker_downgrade`, `project_complexity_adjudication`). Rationale: stated leans + a
  regression test guards the load-bearing fidelity.
- must_ask_peter: false

### D12. M5c Open-Q#1-3 — general-control-op vs planning-transition boundary; reverse-edge variant;
  gate-predicate granularity
- Location: `m5c-control-plane.md:107` ("the single biggest blocking unknown")
- Premade: **DEFAULTS (the leans):** (1) `apply_transition` is general (move X→Y + emit event);
  `synthesize_artifacts` is the binding hook `force-advance` calls, so the SDK never knows what a `gate.json` is.
  (2) raw `predecessors()` is enough; expose recovery for off-graph outcome states (blocked/failed) via the
  realized-graph API. (3) gate predicates survive as binding-side resolvers the projection invokes, not as edge
  metadata. Guarded by the a3 §4.4 parity gate over the full cross-product.
- Mechanism: default + machine-gate (the cross-product parity test). Rationale: leans are stated; the parity
  test is the automated arbiter of whether the boundary is drawn correctly.
- must_ask_peter: false

### D13. M5d Open-Q#1-3 — supervisor vs cloud operator loop boundary; bakeoff vs chain vocab; PR-merge cursor
- Location: `m5d-supervisor-tier.md:93`
- Premade: **DEFAULTS (the leans):** (1) supervisor tier sits BELOW cloud's operator loop; cloud stays a
  long-lived host that ticks the supervisor (so cloud doesn't break). (2) `select`-at-run-granularity is a
  distinct reduce the supervisor invokes (one contract covers both via the primitive-invokes-binding-reducer
  pattern). (3) PR-merge wait binds onto M5c's `awaiting_human` outcome + F6 pause/resume (see C6 auto-merge).
- Mechanism: default. Rationale: leans are stated; (1) is the boundary that keeps cloud working — verified by the
  canary epic (the M5d done-criterion).
- must_ask_peter: false

### D14. M5d — the canary epic acceptance (its "only honest acceptance is a throwaway canary epic")
- Location: `m5d-supervisor-tier.md` done criteria; EPIC §184
- Premade: **MACHINE-GATE.** The throwaway canary epic runs end-to-end on the new supervisor as the automated
  acceptance; green → M5d accepted, red → A2 ladder. No human sign-off.
- Mechanism: machine-gate. Rationale: it is defined as an executable acceptance, not a review.
- must_ask_peter: false

### D15. M6 Open-Q#1 — which (substrate, topology) pair does planning's manifest name? ("biggest open dependency")
- Location: `m6-megaplan-as-module.md:106-112`
- Premade: **DEFAULT (deferred-to-upstream).** Settled by M3's outcome — M6 reads M3's resolved 2-axis result and
  names the `(subprocess_isolated, graph+loop-node)` pair planning actually used (auto.py's per-phase subprocess
  for execute + in-process DAG elsewhere = compose both). M6 must NOT re-litigate; it consumes M3's artifact.
- Mechanism: default. Rationale: explicitly settled upstream; M6's job is to transcribe, not decide.
- must_ask_peter: false

### D16. M6 Open-Q#2/#3 — where `workflow_next`'s projection lives; replace vs wrap `discover_python_pipelines`
- Location: `m6-megaplan-as-module.md:113-116`
- Premade: **DEFAULTS:** (2) `workflow_next` survives as a thin projection layer over M3's realized graph (the
  EPIC's locked decision: realized graph = single source of truth, `workflow_next` is a projection). (3) the
  `arnold` discovery surface WRAPS `discover_python_pipelines` as one source among drivers+packages (umbrella
  registry, not a rip-and-replace) — back-compat-preserving.
- Mechanism: default. Rationale: both follow directly from EPIC locked decisions (§95-99).
- must_ask_peter: false

### D17. M7 Open-Q — umbrella skill replace vs compose; where module-SKILL ends and umbrella how-to begins
- Location: `m7-builder-docs.md:41`
- Premade: **DEFAULT.** During the rename period the `arnold` umbrella skill COMPOSES with (does not replace) the
  megaplan-decision/observe/epic skills; per-module SKILL.md owns module-specific how-to, the umbrella owns
  cross-module build guidance — boundary enforced by a CI duplication check in the generated reference.
- Mechanism: default + machine-gate (doc-drift CI gate already required by M7). Rationale: compose-not-replace is
  the safe back-compat default; the drift gate keeps the boundary honest.
- must_ask_peter: false

---

## E. The one strategy call — already made, recorded, NOT a live blocker

### E1. Full-vision / no-demand-gate ("build the world, the builders come")
- Location: EPIC §3-21 banner
- Premade: **DEFAULT — already decided by Peter on 2026-05-29** and written into the banner; the unknown-unknowns
  demand findings are consciously set aside, architectural findings taken as redirects. This is the irreversible
  taste/strategy call, and it is DONE, not pending. No agent stalls on it.
- Mechanism: default. Rationale: recorded decision; listed only for completeness.
- must_ask_peter: false (it was already asked-and-answered; nothing remains to ask)

---

## Summary
- Total human-decision points found: 30 (6 chain/orchestration, 3 standing-gate, 7 runtime product gates,
  17 design-time open questions, 1 already-made strategy call — overlapping counts collapse to the 30 entries above).
- must_ask_peter = true: **0.**
- Conversions: defaults dominate the design-time open questions (each brief already states a "lean"); machine-gates
  cover parity/oracle/contract/discovery-trust; auto-escalation covers every runtime human-gate (clarify,
  verify-human, override actions, PR-merge, stop_chain) so failure never parks on a person.
