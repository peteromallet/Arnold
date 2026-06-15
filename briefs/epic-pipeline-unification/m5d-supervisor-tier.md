# M5d — Supervisor tier: general cross-run orchestration

**Epic:** Pipeline Unification (`briefs/pipeline-unification-EPIC.md` — M5d §247, §281–282; "Structural pieces"
#4 §194–197; the supervisor row of the discipline table §120). **Program entry:**
`briefs/validation/sequencing/PROGRAM.md` M5d §291–303 (T3; ∥ the M6 relocation tail / after M6).
**Organ spec:** the **run-outcome / control vocabulary** (SYNTHESIS Part-2 "control" noun; §194–197 EPIC) — M5d
*consumes* it, lands no new organ; it binds the supervisor onto M5c's interface and onto M6's discovered-pack
target. **Tier/robustness:** premium · thorough/high (REGISTER §111: "one supervisor tier / two variants").
**Depends on:** **M6** (orchestrates *discovered* modules — needs the relocation + `arnold` namespace + the
general "run a pack" target), **M5c** (the run-outcome / control ops it invokes), **M3** (the single-planning-run
process driver it sequences runs over). **BACK-EDGE — STATE IT LOUD:** `chain/__init__.py:65–73` imports
`auto_drive` directly; it cannot be cleanly extracted until the thing it drives is a *composed* driver, which is
M6's relocation — so M5d shares M6's prerequisite and lands *after* M6 despite its M5-series name (PROGRAM §296–298).
**Grounded:** 2026-05-29 against current `main` (`chain/__init__.py` is now **1,937 LOC**; line cites below
re-verified).

---

## Outcome

The chain / epic / bakeoff **supervisor tier** — today ~1,937 LOC of `chain/__init__.py` plus the whole
`bakeoff/` package — becomes a **general cross-run orchestration tier** that sequences a *graph of runs*
(dependency ordering, per-run failure/escalate policy, persisted progress) and invokes **general control ops**
drawn from M5c's run-outcome vocabulary. Chain = a sequential dependency DAG of runs; bakeoff = parallel runs +
`select` (M2's primitive, at run granularity) + merge — **one tier, two variants**. Planning's milestone-chain
YAML, its git/worktree isolation policy, its escalate-action vocabulary, and bakeoff's profile-matrix +
blind-judge rubric all become **bindings**. The supervisor knows nothing about planning phases: it consults the
run-outcome interface (`read_valid_targets / apply_transition / synthesize_artifacts`); planning's milestone state
machine is *its binding*, not the supervisor's mechanism. This is the `JoinFn→GateRecommendation` eviction
recurring one tier up — at RUN granularity (SYNTHESIS Theme-D; EPIC §194–197).

The supervisor lands behind a default-OFF flag beside the live `chain/__init__.py` + `bakeoff/` path; the OLD
supervisor remains the engine that drives the epic. Acceptance is a **throwaway canary epic of NON-planning
packs** — never the real epic driving the build, which structurally cannot exercise the new supervisor while it
self-hosts on the frozen old engine.

---

## Scope (work items tied to current file:line)

### A. The leak the tier cures, one tier up (the disease, verified on `main`)

1. **It branches on planning's terminal `STATE_*`.** `chain/__init__.py:84` imports `STATE_AWAITING_PR_MERGE`,
   `STATE_EXECUTED` from `megaplan.types`; `run_chain` branches on them (`:1136` patches
   `current_state=STATE_EXECUTED`; the PR-merge choreography reads/writes `STATE_AWAITING_PR_MERGE` at
   `:1318`, `:1329`, `:1503`, `:1514`). `DriverOutcome.status` (`chain` `:930`, `:1143`, `:1183`; defined
   `auto.py:132`) carries values derived straight from planning's state machine — `auto.py:1446–1449` maps
   `STATE_DONE→"done"`, `STATE_ABORTED→"aborted"`, `STATE_BLOCKED→"blocked"` — and the chain re-branches on
   `"blocked"` (`BLOCKED_EXECUTE_OUTCOME_STATUSES = {"blocked", "worker_blocked"}` `:140`;
   `_recover_blocked_execute_if_tasks_done` `:1141`; `_drive_plan_with_blocked_execute_recovery` `:1176`, called
   `:1266`). `"blocked"` is a **planning verdict** coupled to `STATE_BLOCKED→recover-blocked`, not a general
   run outcome.
2. **It invokes a control op "force-proceed" BY NAME.** `ChainSpec.escalate_action` defaults to `"force-proceed"`
   (`:308`), validated against `ESCALATE_ACTIONS = ("force-proceed", "abort", "fail")` (imported `:72`, defined
   `auto.py:124`), and passed straight into the driver as `on_escalate=spec.escalate_action` (`_drive_plan`
   `:937`). `force-proceed` is one of planning's override actions (`handlers/override.py` — `:247`, `:327`, the
   `force-proceed-from-blocked`/preflight constraints `:262–286`), an operator recovery lever, not a general
   supervisor primitive.

### B. The general piece M5d builds (behind a default-OFF flag, beside A)

- A supervisor tier orchestrating a **graph of runs** of **M6-discovered packs** over the **M3 process driver**,
  invoking **general control ops** via M5c's trio. Its failure policy maps onto the run-outcome set
  `{succeeded, failed, escalated, blocked, awaiting_human}` and general targets
  (`force-advance`, `re-route`, `recover-from-stuck`, `abort`) resolved through `read_valid_targets(run_state)` →
  `apply_transition(target)` — **never** `STATE_*` literals or `"force-proceed"` by name. The
  `BLOCKED_EXECUTE_OUTCOME_STATUSES` branch (`:140`, `:1141–1234`) re-expresses as a branch on the general
  `blocked` run-OUTCOME (REGISTER §75): auto-invoke `recover-from-stuck` with a bounded retry ladder (>1) →
  escalate/abort.
- The literal `escalate_action="force-proceed"` (`:308`) is replaced by a general M5c target via
  the interface method `read_valid_targets(run_state)` + `apply_transition` (the supervisor calls the
  interface method, NOT the planning binding's `valid_targets` directly); default escalate ladder = retry →
  re-route → force-advance → abort (REGISTER §74).
- Bakeoff's "run N profiles → blind-judge → select winner → merge" is the **parallel/compare variant** of the
  same tier (`bakeoff/orchestrator.py` 346 LOC, `judge.py` 256, `merge.py` 167, `worktree.py`); `select` is M2's
  run-granularity primitive (REGISTER §111: "bakeoff's reduce IS M2 select at run granularity").

### C. The binding (planning + bakeoff CONTENT only — moves verbatim)

The milestone-chain YAML schema (`MilestoneSpec` `:171`, `ChainSpec` `:291`), `auto_drive` integration
(`:65–73`, `_drive_plan` `:923`), git/worktree isolation (`chain/git_ops.py`, `_init_plan` `:810`), the
escalate-action vocabulary, the `STATE_AWAITING_PR_MERGE` PR-merge choreography (`:1318–1514`), the
blocked-execute recovery (`:1141–1234`), and bakeoff's profile-matrix + blind-judge rubric. Each maps onto a
general control op via the M5c interface — the chain calls the interface method `read_valid_targets(run_state)`
and `apply_transition(target)` (planning implements `read_valid_targets` AS `valid_targets`/`recover_targets`);
it does not name planning's transitions.

---

## Locked decisions

- **Invoke general control ops, not literals.** The supervisor consults M5c's run-outcome interface; planning's
  `STATE_*` and `"force-proceed"` never appear as mechanism in supervisor-tier code. Planning's milestone
  semantics become *its binding* (EPIC §120, §194–197; SYNTHESIS Part-2 control noun). This is the explicit
  eviction of the enum leak at run granularity.
- **Back-edge: M5d depends on M6** (and M5c, M3). Lands after M6 / ∥ the M6 relocation tail (PROGRAM §291–303).
- **One supervisor tier, two variants:** chain = sequential dependency DAG; bakeoff = parallel runs + `select` +
  merge (REGISTER §111).
- **Preserve what `auto.py`'s subprocess loop buys** — context-exhaustion retry, per-phase idle-timeout kill,
  worktree isolation — via the M3 process driver, with **no regression** (verified by characterization on a real
  recorded run, not asserted).
- **Strangler discipline (machine-gated):** the new tier lands `{old-path default-ON, new-path default-OFF behind
  a flag}`; the OLD `chain/__init__.py` + `bakeoff/` supervisor keeps driving the epic (frozen, pinned external
  engine, schema validator report-only, flag-OFF). The old supervisor is retired ONLY after ≥1 dual-green
  milestone AND its behavioral-replay + substrate-swap oracle passes — and **never in the same PR as the
  organ-swap** (PROGRAM §361–389). M5d is the milestone most likely to break the epic-level liveness invariant,
  because it *rebuilds the strangler's own driver* (see Constraints).
- **Sole retirement authority = the behavioral-replay + substrate-swap oracle**, never the happy-path parity
  gate (PROGRAM §381–389). The canary epic IS that oracle's corpus for this tier.
- **Cloud is anti-scope and sits ABOVE this tier** (locked by Open-Q#1 below).

## Open questions (each RESOLVED to its pre-made default — zero human blockers)

1. **Does the supervisor tier subsume cloud's operator loop, or stay strictly below it?** —
   **RESOLVED (REGISTER §111; m5d Open-Q#1 lean):** the **supervisor tier sits BELOW cloud's operator loop**.
   `cloud/supervise.py` (775 LOC) wraps `megaplan chain start` as a one-shot tick (`_chain_tick_command` `:23`,
   delegating to `cloud/cli.py::_chain_start_command` `:539`) and remains a long-lived host that *ticks* the
   supervisor. M5d **states this boundary in writing** so `cloud/supervise.py` does not break at the seam; it
   does not port the operator loop.
2. **How much of the run-outcome vocabulary does bakeoff need vs. chain?** —
   **RESOLVED (REGISTER §111):** **one supervisor tier covers both**; bakeoff's reduce **IS M2 `select` at run
   granularity** (winner + losers + scores over completed runs), not a distinct supervisor reduce. Chain adds
   sequential dependency + per-run failure policy on the same contract.
3. **Resume cursor across the M3 process boundary (the `STATE_AWAITING_PR_MERGE` out-of-band human pause).** —
   **RESOLVED (REGISTER §73, §111):** the PR-merge wait **binds onto M5c's `awaiting_human` run-outcome; the
   auto-merge-on-green ACTOR is OWNED HERE in M5d** (M5c F6 is halt-only and ships no `gh` auto-merger). The
   supervisor watches CI+gates: green → it fires `gh pr merge` (the run-granularity orchestration over
   `chain/__init__.py`'s existing PR-merge choreography `:1318–1514`); red → auto-escalate via the ladder. It
   is NOT a supervisor-local cursor and NOT a human park. M5c contributes only the `awaiting_human` outcome the
   wait resolves to.

## Constraints

- **The self-reference (the killzone).** M5d rebuilds the operator's own recovery levers while the operator is
  using them — the chain/epic supervisor loop and the override plane it invokes ARE the levers the operator
  reaches for when a run goes sideways (SYNTHESIS bootstrapping risk; PROGRAM §299–303). The EPIC freeze list
  therefore includes the chain supervisor loop + override plane for the whole epic; the OLD engine keeps driving
  runs until M5d's replacement is proven on a throwaway.
- **The real epic cannot self-host its own supervisor mid-rebuild** — it runs on the frozen old engine via a
  pinned external venv, flag-OFF. The canary epic is the only honest acceptance.
- **No new verbs / speculative supervisor shapes** (EPIC §62: decoupling + formalization, not new primitives).
  No arbitrary-graph scheduler beyond what chain (sequential DAG) + bakeoff (parallel + select) need.
- **Autonomy ladder, never a human park** (REGISTER §74, §75, §73): escalate = retry → bump profile/robustness
  one tier → `stop_chain` + auto-ticket; blocked = bounded recover-from-stuck ladder → escalate/abort;
  awaiting-PR-merge = auto-merge-on-green. The standing backstop is `stop_chain` + auto-filed megaplan-ticket.
- **Don't dogfood off an editable install; pinned engine; parity gate honestly labelled** (happy-path
  control-flow/artifact parity, not "drift provably zero").

## Done criteria (testable — incl. the milestone's oracle gate)

- [ ] **The oracle gate (canary epic — the SOLE retirement authority for this tier):** the new supervisor
      orchestrates a **throwaway canary epic** end-to-end — a small **multi-milestone chain of NON-planning
      packs** (M6-discovered; e.g. the EPIC #1 acceptance toy — a `select` tournament or a `run(cmd)` oracle),
      with **≥1 dependency edge** and **≥1 induced per-run failure** exercising the escalate/recover policy. Green
      → auto-proceed; red → auto-halt+revert or the bounded escalation ladder. This is F8's only honest
      acceptance (the real epic cannot self-host its supervisor mid-rebuild).
- [ ] **Grep gate (machine-gated, CI):** no supervisor-tier module imports or branches on planning `STATE_*`
      (the `chain/__init__.py:84` import is gone) and no control op is invoked by literal name (the
      `"force-proceed"` default at `:308` is replaced by a general M5c target). Adds the SYNTHESIS acceptance
      check at run granularity: no binding carries `STATE_*` as mechanism.
- [ ] Chain AND bakeoff both run as **bindings of one supervisor tier**; bakeoff's winner-select is M2 `select`
      at run granularity (`bakeoff/orchestrator.py`, `judge.py`, `merge.py`).
- [ ] **No-regression characterization:** what `auto.py`'s loop buys (context-retry, idle-kill, worktree
      isolation) is preserved via the M3 process driver, verified against a recorded real run (behavioral
      replay — recovery/escalate/blocked traces, not just the happy path).
- [ ] **Strangler dual-run green:** OLD supervisor still drives a throwaway 1-milestone plan AND the new tier
      drives the canary epic behind the default-OFF flag, both green, for ≥1 milestone before any old-path
      deletion is even proposed (and never in this PR).
- [ ] **The cloud boundary (Open-Q#1) is stated in writing** so `cloud/supervise.py` (`_chain_tick_command`
      `:23` → `_chain_start_command` `cli.py:539`) does not break at the seam.
- [ ] **PR-merge choreography (`:1318–1514`) binds onto M5c's `awaiting_human` run-outcome, with the
      auto-merge-on-green actor OWNED HERE in M5d** (green→M5d fires `gh pr merge`, red→auto-escalate); a
      unit/integration test proves no human park. (M5c F6 is halt-only and ships no auto-merger.)

## Touchpoints

`chain/__init__.py` (1,937 LOC: `MilestoneSpec` `:171`, `ChainSpec` `:291`, `escalate_action` default `:308`,
`auto_drive` import `:65–73`, `_init_plan` `:810`, `_drive_plan` `:923`/`on_escalate=spec.escalate_action` `:937`,
`STATE_EXECUTED` patch `:1136`, `BLOCKED_EXECUTE_OUTCOME_STATUSES` `:140`, blocked-execute recovery `:1141–1234`,
PR-merge choreography `:1318–1514`, `run_chain` `:1237`, `run_chain_cli` `:1844`),
`bakeoff/{orchestrator,judge,merge,comparison,worktree,state,lifecycle,handlers,metrics,live_status}.py`.
**Consumes:** M5c run-outcome interface (`read_valid_targets / apply_transition / synthesize_artifacts`), M3
process driver, M6 discovered-pack target. **Boundary doc:** `cloud/supervise.py` (775 LOC, `_chain_tick_command`
`:23`), `cloud/cli.py::_chain_start_command` (`:539`). **Source of leaked symbols:** `auto.py:124`
(`ESCALATE_ACTIONS`), `auto.py:132` (`DriverOutcome`), `auto.py:1446–1449` (`STATE_*`→status map),
`megaplan/types` (`STATE_*`), `handlers/override.py` (`force-proceed` `:247`, `:327`).

## Anti-scope

- **Cloud** (`cloud/`, `mp-supervise`, `supervise.py`) — wraps the supervisor tier as a long-lived process; it
  sits ABOVE this tier (Open-Q#1 RESOLVED). M5d *defines* the boundary; it does not port the operator loop.
- **The M6 relocation itself** — M5d *consumes* M6's discovered-pack target; it does not relocate planning, drop
  `_BUILTIN_NAMES`, or write manifests.
- **New verbs / speculative supervisor shapes** — decoupling + formalization, not new primitives. No
  arbitrary-graph scheduler beyond chain (sequential DAG) + bakeoff (parallel + select).
- **Re-tuning planning's chain YAML schema or bakeoff rubric** — content moves verbatim into bindings.
- **Self-hosting the real Pipeline-Unification epic on the new supervisor** — structurally unreachable
  mid-rebuild; the canary epic is the honest substitute.
- **Building the M5c control interface or the M2 `select` primitive** — consumed here, built upstream.
