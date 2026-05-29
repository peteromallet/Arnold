# Interrogation — Over-Simplification lens

**Lens:** Where does "general piece + THIN planning binding" assume a clean split reality won't honor?
Where will the binding NOT be thin, or domain logic LEAK back into the shared piece?

**Posture:** Full ambition is assumed. Nothing below recommends scope reduction. Every finding names what
the plan must ADD, fix, re-sequence, or abstract differently to make the thin-binding story actually hold.

**Grounded against:** `briefs/pipeline-unification-EPIC.md`, `briefs/epic-pipeline-unification/m5-extract-features.md`
(F1–F9), `m6-megaplan-as-module.md`, `briefs/validation/decision/migration-fit.md` (e1–e7),
`briefs/validation/confidence/a3-human-recovery.md`, and live code: `megaplan/handlers/override.py`,
`megaplan/_core/workflow.py` (`workflow_next`, `_workflow_for_robustness`, `_ROBUSTNESS_OVERRIDES`).

---

## The core over-simplification: "binding = content only"

The EPIC's load-bearing claim (§52–54, m5 §14–18, m5 "Locked decisions") is that after extraction,
**planning keeps ONLY content** — "prompts, rubrics, the 4 verdict labels, the 1–5 tier map, the
robustness presets, the 9-action semantics." The word doing all the work is *content*: a binding is
supposed to be passive data the general piece consumes.

Three of the eight m5 features falsify this directly. Their "binding" is not content — it is **mechanism
expressed in planning's private state vocabulary**, and the general piece cannot consume it without either
(a) growing a planning-shaped extension point, or (b) the binding re-implementing routing logic that the
piece was supposed to own. The split is real for F1/F2/F3/F4/F9; it is wishful for **F7 (control plane),
e1 (robustness-reshapes-the-graph), F8 (supervisor tier), and partially F5 (execute DAG)**.

---

## BITE 1 — F7 control plane: the "binding" is a second state machine, not content

**Where:** `megaplan/handlers/override.py` (whole file), m5 §154–174 + Open-Q #1, a3 §1.

The brief calls the 9 override actions "bindings of the general operations
(`force-advance`, `re-route`, `recover-from-stuck`, `reconfigure`, `annotate`, `abort`)." Reality from the
code:

- `override.py` contains **44 `STATE_*` literal usages**. `force-proceed` alone
  (`override.py:242–349`) does NOT "force-advance a generic run." It: branches on three specific source
  states (`STATE_EXECUTED`, `STATE_BLOCKED`, `STATE_CRITIQUED`), runs `run_gate_checks`, **manufactures a
  PROCEED gate artifact via `build_gate_artifact`** (`:297`), writes `gate.json` (`:308`), folds unresolved
  flags into the **debt registry** (`:312–320`), clears `state.last_gate`, and force-sets `next_step="finalize"`
  (`:344`). Every one of those is planning-pipeline knowledge.
- `recover-blocked` owns `_BLOCKED_RECOVERY_STATES` (`override.py:399`), a hand-maintained **phase→recovered-
  state reverse map** — a3 §1 confirms this is a *second copy* of the workflow's reverse edges, with
  `_RESUME_ACTIVE_STATES` (`workflow.py:326`) a third copy.
- a3 §2/§3 proves the general control operations can express only the **forward-progress half**
  (force-proceed/replan/resume-clarify map to existing transitions *once robustness-resolved*).
  `recover-blocked` and `resume_plan` are **reverse projections with no forward edge** — the graph
  literally cannot route out of `STATE_BLOCKED` (a3 §2.5: `workflow_next` returns `[]` for blocked).

**Why this bites:** a control service whose "binding" must (1) synthesize a domain artifact (`gate.json`),
(2) write to a domain registry (debt), (3) carry its own reverse-edge map, and (4) branch on 44 domain
state literals is not consuming *content* — it is the **entire control logic**, and the "general service"
is reduced to an event-emitter + a `valid_next` projection call. The thin-binding story inverts: the
binding is fat, the piece is thin. Worse, a *second* builder adopting the control service gets nothing
reusable except "emit a control event + call your own `workflow_next`" — i.e. the discipline test ("would
an unrelated builder want this?") yields almost nothing transferable.

**What it forces (do not defer):**
1. m5 must define the **control-operation interface as a `(read_valid_targets, apply_transition, synthesize_artifacts)`
   trio the binding implements**, and explicitly accept that the binding owns the transition+artifact logic.
   Stop calling it "content." The general piece owns only: out-of-band invocation, event emission, the
   versioned-mutation envelope (m3 state-evolution), and the `valid_next` projection contract (a3 §4).
2. The reverse-edge maps (`_BLOCKED_RECOVERY_STATES`, `_RESUME_ACTIVE_STATES`, forward transitions) MUST be
   derived from one graph relation and **exposed as a queryable API the binding calls** (a3 §4.3) — this is
   the only part that is genuinely general. Sequence it as its own sub-milestone (m5 already ranks F7 the
   #1 split candidate, §289 — promote that to a hard "F7 ships separately, last" decision, not a "candidate").
3. Add an acceptance test that a **non-planning control binding** (e.g. the bisect toy's "skip/mark-bad"
   operations) rides the same control service. If only planning can express a control binding, the piece
   failed the discipline test and is mis-abstracted.

**Severity: critical.** This is the densest planning-vocabulary coupling in the codebase (a3 §1, m5 §174)
and the EPIC's own "9 override actions" line item in the Discipline table (§37) is filed under
*App/domain-local* — yet m5 promises it as a general piece. That internal tension is unresolved.

---

## BITE 2 — e1 robustness-reshapes-the-graph: "robustness presets" is not data, it's a topology rewrite

**Where:** `megaplan/_core/workflow.py:166–289` (`_resolve_overrides`, `_workflow_for_robustness`,
`_ROBUSTNESS_OVERRIDES`, `with_prep`/`with_feedback`/`creative`), migration-fit e1 ("Biggest gap"),
a3 §1 "Robustness/feature-flag coupling".

The Discipline table (EPIC §38) and m5 §16 list "robustness presets" as planning *content* the binding
supplies. But `_workflow_for_robustness` (`workflow.py:184`) does not *parameterize* a fixed graph — it
**mutates the node/edge set per run**: `bare` drops critique+gate, `light` collapses critique→gate,
`with_feedback` rewires execute→review→feedback (migration-fit e1). `workflow_next` (`:282`) re-resolves
this subgraph *at every call* from `state.config`.

**Why this bites:** A "preset" that adds/removes nodes and rewrites edges is **graph-construction policy**,
not config the driver reads. migration-fit e1 names this explicitly: "neither a node nor a driver feature
as specified — a graph-construction policy with no home." The EPIC's answer (§51, "parameterize-graph-by-
config") is asserted, not designed. There are two failure modes if it stays under-specified:
- **Leak-up:** the general graph driver grows a planning-shaped "topology mutation" hook that only
  planning's robustness levels exercise → domain logic in the shared piece.
- **Fat binding + broken projection:** if the binding builds the graph but `workflow_next` becomes "a thin
  projection over the static graph" (m6 §3), the projection lies on reduced-robustness plans — a3 §2.1
  proves static edges say `CRITIQUED → {critique, gate, revise, …}` when a `light` plan must route
  `revise → GATED`. The maximally-painful failure: telling a stuck operator to run a phase the harness will
  reject (a3 §2.1). The gate→TIEBREAKER→ITERATE silent-downgrade memory is this class already biting.

**What it forces:**
1. The "graph-builder-from-config" hook (migration-fit e1) must be a **first-class, designed piece in m3**,
   not an emergent m5 detail. The driver must accept a `build_topology(config) → Graph` callable; planning's
   binding supplies one that runs `_workflow_for_robustness`. This is the *interface* that keeps the binding
   thin — but it means the SDK admits "the graph is dynamic per run," which contradicts migration-fit's note
   that the graph driver's `Pipeline` is a *static* `stages`/`edges` map (e1). **m3 must reconcile this
   before m5/m6 depend on it** — re-sequence so the dynamic-topology contract lands in m3, not implicitly
   in m6's "collapse onto the graph."
2. The a3 §4.4 parity test (`workflow_next` ≡ legacy across {5 robustness}×{with_prep,with_feedback}×
   {states}×{verdicts}) must be a **m3 gate**, not an m5 afterthought, because m6's single-source-of-truth
   collapse is unsafe until the dynamic projection is proven faithful.

**Severity: critical.** migration-fit's "Biggest gap"; if "robustness preset = content" is taken at face
value the whole single-source-of-truth collapse (m6 §3) is built on a static-graph assumption the
production path violates.

---

## BITE 3 — F8 supervisor tier: chain/bakeoff bindings carry planning's recovery vocabulary up a level

**Where:** `chain/__init__.py` (1,820 LOC), m5 §176–192, migration-fit e4/e6.

The brief says "the supervisor tier itself knows nothing about planning phases" (m5 §192) and the binding is
"the milestone-chain YAML schema + `auto_drive` integration … escalate-action vocabulary." But the
`ESCALATE_ACTIONS` (`chain/__init__.py:396`) and `on_failure`/`on_escalate` semantics (`:347`) are defined
in terms of **the same override actions** (default `force-proceed`, m5 §191) — i.e. the supervisor tier's
failure policy *invokes planning's control-plane vocabulary*. F8's binding therefore depends on F7's binding
being clean. And the chain decides "advance to next milestone" by reading a run's **terminal state** — which
is planning's `STATE_DONE`/`STATE_FAILED`/`STATE_BLOCKED` vocabulary, the exact thing m2 tried to evict.

**Why this bites:** The supervisor's "general" contract — "advance a graph of runs by per-run
failure/escalate policy" — needs a **run-outcome vocabulary** to branch on. If that vocabulary is planning's
state names, the supervisor is not planning-agnostic; if it's a new general `{succeeded, failed, escalated,
blocked}` enum, then *every* run-type (including planning) needs a binding that maps its terminal states onto
it — which is real work the brief assumes away with "knows nothing about planning phases." This is the
4-verdict-enum-leak problem (EPIC §63, `JoinFn → GateRecommendation`) recurring at **run granularity**.

**What it forces:**
1. m5 must define a **general run-outcome type** (succeeded/failed/escalated/blocked/needs-human) and require
   *each* run-type to supply a terminal-state→outcome mapping. Planning's `STATE_*` → outcome map is the
   binding. Without this, the supervisor inherits planning's state enum exactly as `JoinFn` inherited
   `GateRecommendation` — the bite the EPIC already diagnosed, now one tier up.
2. F8's escalate policy must invoke the **general control operations** (BITE 1's interface), not
   planning's `force-proceed` by name. Re-sequence: F8 cannot be cleanly extracted before F7's general
   control interface exists — make F8 depend on F7 explicitly (today m5 lists them as peers).

**Severity: high.** Real, in-production, and it re-creates the headline leak (app-enum in a general type)
at a tier the abstraction-stress-test never sketched.

---

## BITE 4 — F5 execute DAG: "decomposition rule is the binding" hides blocked/deviation classification leaking into the general reducer

**Where:** `execute/batch.py` (1,529 LOC), m5 §122–136.

m5 says the general piece is a "produce+process-driver scheduler (batch/dependency walk)" and "blocked/
deviation classification is a general `process`-result reducer" (§133), while the binding is "the
decomposition rule + max_tasks_per_batch + per-batch tier→model + sense-check content."

**Why this bites:** Calling blocked/deviation classification *general* is the over-simplification.
`_run_and_merge_batch` (`batch.py:264`) classifies results into **planning's** `blocked`/`deviation`
categories that feed straight back into the control plane (a blocked batch → `STATE_BLOCKED` →
`recover-blocked`'s reverse map, BITE 1). "Blocked" is not a general scheduler outcome; it is a planning
verdict about a unit of work, coupled to the override/debt machinery. If the general reducer encodes
`blocked`/`deviation`, planning's execute-result vocabulary leaks into the shared scheduler exactly like
the 4-verdict enum leaked into `JoinFn`.

**What it forces:** the `process`-result reducer must return a **structured, app-defined outcome** (m2's
`Reduce[T]` discipline applied to execute results), and planning's `blocked`/`deviation` classification is
a binding-supplied reducer the scheduler merely invokes (m5 Open-Q #3 leans this way for F2 — apply the
same ruling to F5 explicitly). Otherwise the scheduler is planning-shaped.

**Severity: high.**

---

## Single biggest items

### Missing abstraction
A **general run-outcome / control-target vocabulary** — one typed surface
`{succeeded, failed, escalated, blocked, awaiting_human}` plus a queryable `valid_targets(state)` /
`recover_targets(state)` projection — that BOTH the control plane (F7) and the supervisor tier (F8) branch
on, and that every run-type (planning included) maps its private `STATE_*` onto via a binding. The EPIC
evicts the 4-verdict enum from `JoinFn` (§63) but never evicts planning's `STATE_*` enum from the control
plane or the supervisor's failure policy. Without this abstraction, F7 and F8 bindings are forced to carry
planning's full state vocabulary as mechanism, and "binding = content" is false for the two hardest
features. This is the same disease the stress-test found, untreated one layer up (control/supervision)
where the EPIC stopped looking.

### Over-complication
None material through this lens. (The plan is, if anything, under-specified rather than over-built on the
binding seam. The state-evolution axis and gate-consequence parameterization are justified by the
stress-test's 5 sketches; not gold-plating.)

### Over-simplification (the single biggest)
**"Planning keeps ONLY content" (EPIC §52–54, m5 §14–18).** For F7 (control plane), e1 (robustness),
F8 (supervisor), and F5 (execute classification), the "binding" is **mechanism in planning's private state
vocabulary**, not passive content. The plan must replace the word *content* with an explicit
**binding-implements-interface** contract for these four: the binding supplies *behavior* (transition logic,
topology construction, terminal-state mapping, result classification) against a general interface, while the
SDK piece owns only the invocation envelope, event emission, versioned-mutation, and projection contracts.
This is not scope reduction — it is honest naming of what each binding must implement so the general piece
stays general and the binding stays auditable.
