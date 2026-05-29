# Interrogation — Where planning RESISTS becoming a module

**Lens:** the hardest extractions; what they force the abstraction to absorb. Assume we WILL do
all of M1–M6 at full ambition. Findings recommend what to ADD / re-sequence / abstract differently,
never scope reduction.

**Grounded against current main, 2026-05-29.** Key code reads:
- `megaplan/_core/workflow_data.py:91` `_ROBUSTNESS_OVERRIDES` — per-level *topology rewrite*, not config.
- `megaplan/_pipeline/types.py:31` — `Pipeline` is a static `stages`/`edges` map.
- `megaplan/_pipeline/{executor,runtime,builder}.py` — **zero** refs to `robustness`/`with_prep`/`with_feedback`.
- `megaplan/_core/workflow.py:184,212,282` — `_workflow_for_robustness` / `_transition_matches` / `workflow_next`.
- `megaplan/handlers/override.py:399` `_BLOCKED_RECOVERY_STATES`, `:297` `build_gate_artifact`, `:898` `_OVERRIDE_ACTIONS`.
- `megaplan/_pipeline/stages/inprocess_step.py:141,192` `_label_for`/`_gate_next_step`.

---

## TOP BITE 1 — Robustness-reshapes-the-graph forces a graph-rewriting / meta-driver layer the plan has not named (CRITICAL)

This is the single planning feature that **most forces a new top-level abstraction**, and the plan
papers over it as "parameterize-graph-by-config" (EPIC §51, m3) — which is a category error.

The evidence is unambiguous in `_ROBUSTNESS_OVERRIDES` (`workflow_data.py:91`):
- `light`: `STATE_CRITIQUED: [Transition("revise", STATE_GATED)]` **and** `STATE_EXECUTED: []`. The
  second entry *deletes* an outgoing edge — review is removed from the topology, not skipped at runtime.
- `bare`: `STATE_PLANNED: [Transition("finalize", STATE_GATED)]` — collapses plan→critique→gate→finalize
  into plan→finalize, i.e. **removes nodes** (critique, gate).
- `full`/`light`/`bare` layer cumulatively via `_ROBUSTNESS_WORKFLOW_LEVELS` (`workflow_data.py:~120`):
  `bare = ("full","light","bare")`. The realized graph is a *fold* over an ordered override stack.

This is **graph rewriting**, not parameter binding. The plan's framing has three internally-inconsistent
positions and none of them is the real mechanism:
1. EPIC §36 puts "robustness levels" in the App/domain-local column (planning content).
2. EPIC §51 / m3 calls it "parameterize-graph-by-config."
3. migration-fit e1 (the doc m5 is told to honor) explicitly says it is **"neither a node nor a driver
   feature… a graph-construction policy with no home. Biggest gap."**

You cannot satisfy all three. If robustness is "just planning content" (1), then the SDK's `graph` driver
must accept a package-supplied function `(base_graph, config) -> realized_graph` and run it *before*
edge-walking — which means the driver's contract is no longer "here is a static `Pipeline`," it is "here
is a graph **builder** that closes over run state." That is a real new seam, and **M6's acceptance test #1
will not exercise it**: a `select`-tournament / `snapshot-restore` / `bisect` toy is forward-only and
single-topology; it never reshapes its own graph. So the load-bearing proof is structurally blind to the
hardest thing planning does. The plan can ship all of M1–M6 green and *still* not have proven the graph
driver can host planning's topology mutation.

**What it forces the plan to ADD (not reduce):** a named **graph-construction / rewrite stage** in the
driver contract — a first-class `realize(graph, run_config) -> graph` hook (an ordered list of rewrites,
matching the cumulative `_ROBUSTNESS_WORKFLOW_LEVELS` fold), executed deterministically at run-init and
re-runnable mid-flight (because `set-robustness` mutates it live — see Bite 3). And M6/M2 must add a
**second acceptance toy that reshapes its own topology by config** (e.g. an "optional-stage" pipeline with
a fast/thorough mode), or the generality claim for this dimension is asserted, not proven.

---

## TOP BITE 2 — `workflow_next` is not 1 of 3 encodings to collapse; it is a robustness-resolving PROJECTION the static graph cannot produce, and the graph routes back INTO the control plane (CRITICAL)

M6 §3 says "make the graph the single source of truth; `workflow_next` survives only as a thin projection
layer." a3 already weakened this to "safe only if retained as a state-derived projection." But the code
shows the projection is **not thin**, and worse, the three encodings are **not three views of one truth** —
they disagree by construction, and one of them points *out of the graph entirely*:

- `_gate_next_step` (`inprocess_step.py:192`) hardcodes `escalate -> "override force-proceed"`. The
  in-graph routing layer's terminal edge is **a control-plane command string**, not a stage. So encoding
  (b) literally embeds the F7 control plane as a graph edge. You cannot "collapse onto the graph" when the
  graph's own next-step table already dereferences into override.py.
- `workflow_next` (`workflow.py:282`) must (i) fold the robustness override stack, (ii) evaluate 7
  `_transition_matches` gate predicates against `state.last_gate`, and (iii) append a synthetic `"step"`
  pseudo-target that **exists in no edge** (a3 §1, `_STEP_CONTEXT_STATES`). A "thin projection over edges"
  cannot manufacture a target that has no edge; the structural-edit escape hatch (`step-add/-remove/-move`)
  is advertised *only* here.
- The static `Pipeline` (`types.py:31`) is robustness-blind and collapses gate verdicts to 3 `kind="gate"`
  edges, losing `gate_proceed` vs `gate_proceed_blocked` vs `gate_proceed_agent_availability_blocked` —
  the exact predicate `force-proceed`-from-blocked depends on (a3 §3).

So the "collapse 3 next-step encodings" task (M6 §3, EPIC §114) is mis-sized. The honest shape is: the
graph is the **edge inventory**, but the source of truth for *next step* is a **robustness-resolved +
gate-predicate-filtered + control-aware projection** that consumes the realized graph from Bite 1. M6's
open question "where does `workflow_next`'s projection physically live" (m6 §77) is the tell: it can't live
in the planning binding (override/status/doctor/introspect all import it), and it can't live in the SDK
graph driver (it carries planning's 7-predicate verdict vocabulary and the `"step"` affordance). It needs a
home the 4-layer model doesn't have.

**What it forces:** name the projection as a first-class SDK concept — a **`next_step` view over the
realized graph, parameterized by (a) the rewrite result and (b) a binding-supplied predicate/edge-metadata
set**. Enrich `Edge` with the full predicate vocabulary as metadata (a3 §4.2) so the projection filters
edges instead of re-deriving them from a parallel dict. And the parity test (m5 constraints, a3 §4.4) must
gate this — but note it only covers planning's cross-product; it does not prove a *non-planning* package
can author its own predicate set, which is the actual generality claim.

---

## TOP BITE 3 — The control/override plane + supervisor tier are two NEW top-level abstractions, and they are coupled (the live-reconfigure path) in a way no milestone owns (HIGH)

migration-fit names two homeless tiers: a **control/override service** (e3) and a **supervisor/meta-driver
tier** (e4/e5/e6). m5 dutifully lists them as F7 and F8. But the plan treats them as "extract feature →
piece + binding" like F1–F6, and they are not that shape — they are **architectural tiers above the
driver**, and they interact:

- F7 control plane: `_OVERRIDE_ACTIONS` (`override.py:898`) are out-of-band mutations injected *between*
  phase subprocesses. `set-robustness`/`set-profile`/`set-model` mutate `state.config` "to take effect next
  phase" (m5 F7). That means a control action **re-triggers the Bite-1 graph rewrite mid-run**: change
  robustness → the realized topology must be recomputed → the resume cursor must still be valid against the
  *new* graph. The plan never states that control-plane reconfigure and graph-rewrite are the same
  mechanism viewed from two sides. This is the densest unknown m5 already flags (m5 Open Q1) — but it is
  flagged as "where is the seam," not as "these two named pieces share one mechanism."
- `recover-blocked` / `resume_plan` are **reverse projections** with no forward edge (a3 §2.5, §3). a3's
  fix ("derive the 3 phase↔state maps from one graph relation; reverse = predecessor-of-stage") only works
  *after* Bite 1 — you can't take the predecessor of a stage on a graph that hasn't been realized for this
  run's robustness. On a `bare` plan, `critique`/`gate` stages don't exist, so the reverse map must be
  computed over the *rewritten* graph, not the base one. So `recover-blocked` correctness **transitively
  depends on the graph-rewrite layer being live and re-runnable**, chaining Bite 3 → Bite 1.
- F8 supervisor tier: chain (`chain/__init__.py`, 1,820 LOC) + bakeoff drive a *graph of runs*. The plan
  correctly calls this "a whole new tier" (m5 F8, migration-fit e4). But cloud (e5) wraps `auto`+`chain` as
  the deployed process — m5 punts the boundary to its Open Q2 ("does the supervisor tier subsume cloud's
  operator loop?") and M6 keeps resident-adopts-pieces but says nothing about cloud. **A whole production
  surface (cloud) sits above an unbuilt tier and no milestone owns where it attaches.**

**What it forces:** the plan must promote "control plane" and "supervisor tier" from *features* to **named
top-level abstractions in the layer model** (the model is currently "4 layers / 2 drivers / 5 services" —
migration-fit's verdict is it has no slot for either), AND it must add an explicit statement that
**control-plane reconfigure == graph-rewrite re-invocation**, with a single owner for the realized-graph +
resume-cursor invariant. Without that, F7 and Bite 1 will be built by two different milestone agents with
two different mental models and the live `set-robustness` path will silently desync.

---

## Single biggest MISSING ABSTRACTION

A **realized-graph / graph-rewrite layer** (call it the *topology realizer* or *graph-construction stage*),
sitting between the static package-declared `Pipeline` and the driver's edge-walk, with three obligations
the plan currently scatters across "config," "content," and "no home": (1) deterministically fold an
ordered stack of config-driven rewrites into the run's actual graph (the `_ROBUSTNESS_OVERRIDES` /
`_ROBUSTNESS_WORKFLOW_LEVELS` fold, `workflow_data.py:91`); (2) be the **single source** that both the
`next_step` projection (Bite 2) and the reverse-recovery maps (Bite 3) query — killing the 3-copies problem
at its actual root, which is not "3 encodings" but "no realized graph to project from"; (3) be
**re-invocable mid-run** so the control plane's `set-robustness`/`set-profile` can mutate topology with a
still-valid resume cursor. The EPIC's "parameterize-graph-by-config" (§51) names a *parameter*; the real
thing is a *rewrite function in the driver contract* plus an acceptance toy that exercises it. This is the
abstraction planning forces that the plan has not named.

## Single biggest OVER-SIMPLIFICATION

"Collapse ALL THREE next-step encodings onto the graph/driver as the single source of truth" (M6 §3,
EPIC §114). The three encodings are not redundant views to merge — they are at different altitudes and one
(`_gate_next_step`, `inprocess_step.py:192`) routes *into* the control plane (`escalate -> "override
force-proceed"`), one (`workflow_next`) manufactures a target (`"step"`) that has no edge, and the static
graph cannot express either robustness or the fine gate predicates. "Single source of truth" is achievable
only if "the graph" means *the realized graph plus a stateful projection*, which is two new things, not a
collapse. Treating it as deletion-of-duplication will delete the robustness projection and the `"step"`
escape hatch and print wrong recovery commands to a stuck operator (a3 §2.1–2.2) — the maximally painful
failure.

## Single biggest OVER-COMPLICATION

None that recommends cutting scope — but one genuine mis-factoring: the plan keeps the
**reverse-recovery maps as a hand-derived "queryable API"** (m5 F7 binding, a3 §4.3 "the derived maps must
still exist as a queryable API"). Given Bite 1's realized-graph layer, the reverse map is *not a separate
artifact to maintain or query* — it is `predecessors(stage)` on the realized graph, computed on demand.
Building/persisting a derived map (even "derived from one relation") re-introduces a fourth copy that can
drift from the realized graph after a mid-run `set-robustness`. The simpler correct design is: no stored
recovery map at all; recovery handlers ask the realized-graph layer for predecessors of the current stage.
The plan over-builds here by preserving the map-as-API shape out of back-compat caution when the
realized-graph layer makes it free.
