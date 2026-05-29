# U2 — Adversarial second-opinion review

**Author:** adversarial senior architect (second opinion). **Date:** 2026-05-28.
**Inputs:** the 2026-05-23 brief (`briefs/pipeline-unification-planning-as-pack.md`) and the
eight validation findings (`c1`–`c7`, `u1`). I reason from the *validated* code state, not the
brief's stale framing. Strong positions, no hedging.

---

## 0. The one-sentence verdict

The brief is a genuinely excellent *diagnosis* attached to a *2–3-month rewrite the diagnosis does
not justify*. The four pillars are not one architecture — they are four independent bets with wildly
different value-per-risk, and the brief's "full scope holds" decision bundles a high-value bug-fix
(state/emission), a medium-value reorganization (pack-ify), a deep-rewrite-masquerading-as-a-dataclass
(HandlerContext), and a confirmed-YAGNI (Realizer) into one serial spine. **Unbundle them.** The Arnold
product direction raises the ceiling on pack-ification's value but does **not** rescue HandlerContext or
the Realizer Protocol — those are internal-elegance bets whose cost is paid against `auto.py`, the one
piece of code nobody has touched and everybody is afraid of.

---

## 1. Are the four pillars well-engineered, or over-engineered? Ranked by value-per-risk

### Pillar A — Single execution path
**Over-engineered as stated; the honest version is much smaller.** The brief frames "single execution
path" as "everything enters `run_pipeline(_with_policy)`." C1 demolishes this: `run_pipeline_with_policy`
is **dead in production** (gated behind `MEGAPLAN_PIPELINE_AUTO`, which has zero readers, behind
`run_pipeline_by_name`, which has zero production callers), it is a strict *subset* of `run_pipeline`
(drops override-edge dispatch entirely, has a dead `abort` branch), and the real engine — `auto.py`'s
~2500-line subprocess loop — **never touches the executor at all**. So "unify on the policy path" would
ship users the override-edge drop on day one. The genuine, defensible core here is *not* "one function"
— it is "stop the two engines from silently diverging," and that is a **parity-gate** problem, not a
merge problem. Value: high (drift is real per c1/§1). Risk: the `auto.py` port is the single
highest-risk item in the entire plan (~2500 LOC, zero direct tests, and the subprocess boundary IS the
isolation boundary). **Value-per-risk: MEDIUM**, and only if scoped to "characterize + merge the two
*executor* functions + parity-gate auto," NOT "port auto.py into the executor."

### Pillar B — Pack-ification (planning → `pipelines/planning/`, drop `_BUILTIN_NAMES`)
**Right-sized, and the Arnold direction is exactly what justifies it.** Per u1, the *pattern* is already
proven: `6ec0f27e` pack-ified creative/doc into `steps.py` + `prompts/__init__.py`, shrank
`_pipeline/planning.py` 233→122 LOC into a pure `compile_planning_pipeline()`, and `96b5e66b` formalized
`patterns.py` into a real capability library. The migration template the brief wanted **now exists in
the tree.** This is the one pillar where the product story ("megaplan is the first tool among many") makes
generalization *load-bearing rather than decorative*: if Arnold ships a second tenant, planning-as-a-pack
is the seam that makes it cheap. The brief's own self-criticism (§12: "deleting `_BUILTIN_NAMES` then
re-adding a discovery guard is deleting a privilege and rebuilding it as an assertion") is correct but
*cheap to accept* — a one-line CI assertion is a fine price for symmetry. **Value-per-risk: HIGH.** This
is the pillar to actually build.

### Pillar C — HandlerContext (typed config bus, `(root, state, hctx)`)
**The worst value-per-risk in the plan. A deep rewrite masquerading as a dataclass swap.** C4 is
devastating and I fully endorse it: (1) handlers don't become pure — `handle_gate` keeps its reprompt
loop + tiebreaker cascade + auto-downgrade + worker spawns; "pure-ish" is fiction. (2) The `args`
mutation is *load-bearing*: `apply_profile_expansion` writes `args.profile`,
`args._live_phase_model_steps`, `args.phase_model` and uses `_profile_applied` to stay idempotent across
~N call sites — a frozen `hctx` collides head-on with this and forces a rewrite of the routing pipeline.
(3) The real config surface is 80+ fields plus ambient `load_config()` + ~20 `MEGAPLAN_*` env reads, not
"~17 stable fields." (4) `handle_*` are in two `__all__` blocks — a signature change is a public-API
break. And the killer, surfaced by C4's unknown-unknown: **`auto.py` spawns each phase as a fresh
subprocess that reconstitutes config from `state["config"]` + profile expansion.** A "build hctx once,
thread it" design has *no home* in a multi-process engine — the context must be re-derived from state on
every subprocess boundary anyway. HandlerContext is solving a real problem (untyped `getattr` sprawl) with
a 1-month call-graph refactor whose premise (one in-process context) contradicts the actual execution
model. **Value-per-risk: LOW.** The high-ROI subset (a typed `RunConfig` for the worker/receipt read
surface + hoisting ambient reads) is ~20% of the work for ~80% of the value — do that, drop the rest.

### Pillar D — Pluggable Realizer Protocol
**Confirmed YAGNI. Cut it.** C5 is unambiguous: the "universal DAG-runner" half is ~80% already done
(`compute_task_batches` in `_core/io.py` is a pure, mode-free Kahn topo-sort), so extracting it is
low-value churn. The genuinely mode-entangled part is the per-task execute-and-evidence step, and only
**two** evidence shapes exist (git-diff vs `sections_written`) — and they're *asymmetric* (prose has
`assemble`, code doesn't; code has git evidence, prose doesn't). Forcing both into a symmetric 5-method
Protocol invents structure neither side uses; `assemble` would be a stub on code. The May 24–28 refactor
already produced the cheap version: `quality.py`'s `_check_done_task_evidence_by_kind` is a kind-keyed
quality gate with overrides, and `merge.py`'s `required_fields` fork is an evidence contract. **No third
backend is on the roadmap** — and the brief's own honesty note (§2 "still a bet, architecture taste") plus
C5's "build the seam, skip the Protocol" converge. There's also an unreconciled *architecture smell* (C5
unknown-unknown #1): the Realizer would be a second pluggability axis crossing the `_pipeline` registry
axis — two orthogonal plugin systems the brief never reconciles. **Value-per-risk: LOWEST.** Consolidate
the 18 scattered `is_prose_mode` branches into one injected evidence-strategy object if you must; do not
erect the Protocol.

### Ranked

| Rank | Pillar | Value | Risk | Verdict |
|---|---|---|---|---|
| 1 | **B — Pack-ification** | High (Arnold makes it load-bearing) | Low–Med (pattern already proven in-tree) | **BUILD** |
| 2 | **A — Single path** (scoped: parity-gate + merge 2 executor fns) | High (drift is real) | High (auto.py port) | **BUILD the parity gate; defer/avoid the auto.py port** |
| 3 | **C — HandlerContext** | Med (real debt) | High (call-graph rewrite vs subprocess model) | **CUT to typed RunConfig subset** |
| 4 | **D — Realizer Protocol** | Low (2 asymmetric modes, no 3rd) | Med (churns freshly-stabilized code) | **CUT** |

---

## 2. The honest minimal viable path to "planning is one pack among many"

The brief's own skeptics (§12) and the validation fleet converge on a much smaller spine. Given that
auto.py is the real engine *outside* the executor, **full unification is NOT necessary for the product
goal.** The product goal ("planning is one pack among many, so a second Arnold tenant is cheap") is
satisfied the moment planning is *discovered like a pack and a second pack can actually dispatch a model*.
That does **not** require killing `COMMAND_HANDLERS`, rewriting `auto.py`, or building HandlerContext or
Realizer. The 80/20:

1. **Finish Phase 0 properly (highest value, lowest risk, partly built).** The parity gate exists but is
   a single happy-path test (u1) — add `extract_decision_fields` + `make_worker_sequence` overrides
   covering reprompt/downgrade/tiebreaker. Add the discovery-integrity CI assertion. This kills the drift
   risk *permanently and on its own merits*, independent of everything else.

2. **Make profiles genuinely pack-agnostic (the real F3 blocker, ~2–3.5 days per C6).** This is the one
   foundation item the brief *under*-weighted relative to its importance: today any non-planning pack that
   actually dispatches a model hits `VALID_PHASE_KEYS` rejection + a bare `DEFAULT_AGENT_ROUTING[step]`
   KeyError. The demo packs are a **false proof of genericity** — they never resolve a model. *This, not
   HandlerContext, is what blocks "any pack."* Decouple `VALID_PHASE_KEYS`, make dispatch slot-resolution
   fail-typed not KeyError, and ship one real pack that dispatches.

3. **Pack-ify planning into `pipelines/planning/` using the now-proven creative/doc template.** Keep
   `InProcessHandlerStep` and `COMMAND_HANDLERS` — the Steps stay thin callers. Write the prompts bridge,
   author SKILL.md, declare the config schema, drop `_BUILTIN_NAMES` behind the discovery guard. This is
   "move files + write a bridge" against a green parity gate — mechanical and reversible.

4. **Land the targeted state fixes from C2 — NOT a state-write foundation phase.** The "four divergent
   writers" hazard is already *closed* (`write_plan_state(mode=...)` unified it, locked + atomic). The
   real residual is small: add `schema_version` + a load validator, and convert the two lock-free
   `mode="replace"` external writers (`resume_plan`, `record_lifecycle_failure`) to locked R-M-W. Half a
   day, not a month.

5. **Consolidate emission into one shared hook (already a down-payment per c3/u1).** Emission already
   exists on every production path — execute/review emit inline, `_finish_step` emits for planning phases.
   `a59e5495` already extracted `_emit_receipt`/`_write_gate_json` into `shared.py`. Finish the dedup so
   there's one emission contract; this is advisable-not-required and rides alongside pack-ification.

6. **Leave `auto.py` alone unless/until an Arnold tenant proves it needs in-process drive.** Pin the
   `megaplan status` JSON as a stable contract (the cloud-over-SSH boundary depends on it) and write
   `test_auto_drive.py` as a characterization oracle. Do **not** port it into the executor as part of this
   work — that is a separate, optional, high-risk project that delivers no pack-ification value.

**Net: the product goal is reachable in ~2–3 weeks (items 1–3 + 4–5 riding alongside), not 2–3 months.**
The two engines coexisting is *fine* — "single execution path" is internal elegance, not a product
requirement. Arnold needs *discovered packs that can dispatch*, which is items 1–3.

---

## 3. The single biggest unknown-unknown / sequencing trap

**The auto.py subprocess-reconstitution model is structurally incompatible with three of the four pillars
at once, and nobody has costed the collision.** Each validation report found a *facet* of this; none
named it as the unifying trap:

- C4: HandlerContext built once in-process has no home — config is re-derived from `state["config"]` on
  every subprocess boundary.
- C1: auto.py never touches the executor; "single path" requires porting ~2500 untested LOC whose
  subprocess boundary IS the isolation/timeout/stall boundary.
- C3 / brief hazard 4: `auto_approve` is injected via subprocess flags (`--user-approved`); an in-process
  rewrite that drops the signal silently halts every `auto_approve=False` plan at execute.

The trap is this: **the plan sequences HandlerContext (Body 1b) and CLI-rewire (Body 2) *before* the
auto.py rewrite (Body 2 step 6), but the auto.py subprocess model is what determines whether
HandlerContext can exist at all.** You would build a typed in-process config bus, rewire the CLI onto it,
and *then* discover at the auto.py step that every phase is still a fresh subprocess reconstituting config
from state — so the context you threaded must be (de)serializable from `state.json` anyway, which means it
was never an in-process object, which means the 1-month HandlerContext refactor was solving a problem the
execution model forbids. **The sequencing must be inverted: settle the auto.py execution model FIRST (or
decide deliberately to keep it subprocess-based forever), because it is the constraint that decides
whether HandlerContext and single-path are even coherent.** Building Body 1b before resolving auto.py is
building on a foundation you haven't inspected.

Secondary trap (u1): the post-brief work added a **second human-gate surface** (`STATE_AWAITING_HUMAN` +
prep-clarification, a 9th override action `resume-clarify`). The hazard-5 resume analysis was written
against *one* human-gate convergence point (`awaiting_user.json::stage`); there are now two, and the
resume-migration shim must reconcile both. This is a live, growing surface — the legacy-path debt the plan
targets is *increasing faster than the plan would pay it down*.

---

## 4. Cut-list vs load-bearing

### CUT entirely
- **The Realizer Protocol (Pillar D, §5).** Confirmed YAGNI (c5). Two asymmetric modes, no third on the
  roadmap, DAG-runner already exists, refactor already paid down the value. At most: consolidate
  `is_prose_mode` into one evidence-strategy object — and even that only if it stops causing bugs.
- **HandlerContext as scoped (Pillar C, §A3/hazard 7).** A call-graph rewrite that contradicts the
  subprocess model (c4). Replace with the narrow typed-`RunConfig` subset + ambient-read hoisting.
- **The `auto.py` in-process port (Body 2 step 6) as part of *this* effort.** Highest-risk item, zero
  pack-ification value, blocks nothing the product needs. Spin it out as an independent, optional project
  gated on a real second tenant demanding it.
- **"Unify on `run_pipeline_with_policy`."** It's a dead, lossy subset (c1). If anything is unified, merge
  the two *executor* functions taking `run_pipeline`'s override-complete dispatch as canonical — but this
  is not on the product critical path.
- **The §6 "state-write foundation phase" as a phase.** Already mostly solved (c2); demote to a half-day
  targeted fix (`schema_version` + two lock-free replace paths).
- **Body 3's "extract DAG-runner / formalise patterns.py" as work items.** Already done in-tree
  (`6e69814c`, `96b5e66b` per u1). Re-scope Body 3 to nothing but the optional `capabilities` tuple.

### Genuinely load-bearing (KEEP)
- **The parity gate, finished properly + kept as permanent CI.** This is the single most valuable item
  in the entire brief and it's the one the skeptics, the brief's own §12, and u1 all agree on. It kills
  drift for real and de-risks every other move. Build it first.
- **Profile pack-agnosticism (c6).** The *actual* "any pack" blocker, under-weighted by the brief
  relative to HandlerContext. ~2–3.5 days. Without it, "planning is one pack among many" is a stub-backed
  illusion (creative/doc never dispatch a model).
- **Pack-ifying planning into `pipelines/planning/`.** The product-load-bearing pillar; pattern proven.
- **The discovery-integrity guard.** Cheap insurance that makes dropping `_BUILTIN_NAMES` safe.
- **`schema_version` + load validator** and the two lock-free `replace`-path fixes (c2).
- **Emission-hook consolidation** (down-payment exists; finish for one contract).
- **Pinning the `megaplan status` JSON contract** (cloud-over-SSH depends on it; cheap, high-blast-radius).
- **PR #43 as a *reference artifact only*** (c7): CLOSED, branch deleted on origin, recoverable from
  `refs/pull/43/head` @ `4ef36402`. ~30% lift-and-shift (`worktrees/` package), ~70% re-implementation
  against main's new batch/`current_state` contract. Do NOT rebase. Only relevant if/when CodeRealizer is
  ever built — i.e. probably never, given the cut above.

### The meta-point
The brief decided "full scope holds" for *platform/maintainability* reasons and accepted the 2–3-month
price honestly. But the validation fleet has since shown that (a) the mechanical decomposition the brief
budgeted weeks for is *already done*, (b) two of the four pillars (HandlerContext, Realizer) are
contradicted or YAGNI'd by the validated code, and (c) the real "any pack" blocker is profiles, which the
brief under-weighted. The Arnold direction strengthens *exactly one* pillar (pack-ification) and is
neutral-to-negative on the other three (a second tenant makes the subprocess-model collision *worse*, not
better, for HandlerContext). The decision to hold full scope should be **reopened**: the product goal is a
2–3-week subset, and the rest is elegance bought at the price of touching the scariest, least-tested code
in the repo.
