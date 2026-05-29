# P5 — Pre-mortem: YAGNI / over-engineering lens

**Author:** the pragmatist, 6 months on. **Date written:** 2026-05-28 (as a pre-mortem set in ~Nov 2026).
**Inputs:** `briefs/pipeline-unification-EPIC.md`, all six milestone briefs (`m1`–`m6`), the validation
fleet (`c1`–`c7`, `u1`, `u2`). Builds on `u2-adversarial.md` and goes further on the *specific pieces*.

---

## The pre-mortem scene

It is November 2026. The epic shipped all six milestones. It took ~2.5x the planned time — the m3
auto.py in-process port alone ate two-thirds of the schedule and a quarter of it is still behind a
default-OFF toggle nobody has flipped in prod. megaplan still runs exactly one real pipeline that
dispatches models (planning). There are two demo packs (creative/doc) that still don't dispatch a
model, plus one new "reference pack" m2 forced into existence to satisfy its own acceptance test —
which no user has touched since. The team maintains: an EvidenceRealizer indirection with exactly two
implementations and no third on the horizon; a `HandlerContext` typed bus whose `services` half is
genuinely used and whose `config` half is a 81-field escape-hatch grab-bag that everyone still
`getattr`s through; a `capabilities` tuple that one function reads to pick between the two realizers;
and an in-process auto driver that re-derives config from `state["config"]` on every stage anyway —
exactly the thing c4 warned made the typed-context premise incoherent.

The diagnosis was excellent. The scoping discipline ("dependency ordering, not scope-trimming") was the
wrong knob. u2 already said: unbundle, the product goal is a 2–3 week subset. Peter chose FULL because
"don't be lazy." This pre-mortem honors that — the goal is not "cut everything," it's to separate the
pieces that **earn the second tenant (Arnold)** from the pieces that are **internal aesthetics** the
Arnold story does not pay for.

---

## The Arnold goal, stated precisely

> megaplan is Arnold's *first tool of several*. A second tool/tenant should be cheap to add.

The product test for every suspect: **does a hypothetical second Arnold tool actually consume this, or
does it only make megaplan's internals prettier?** A second tool needs to (1) be *discovered* like a
pack, (2) *declare its own slots and dispatch a model* under the shared profile contract, (3) prove its
work without hand-editing core. That's it. Nothing in the Arnold goal requires one execution function,
a typed in-process config object, a symmetric realizer protocol, or planning losing its built-in name.

---

## Suspect-by-suspect

### 1. `capabilities: tuple[str, ...]` pack metadata (m6 scope item 4) — **SPECULATIVE**

**What it is.** A new metadata key on packs (`registry.py:343`) whose declared value (`"git-evidence"`,
`"prose-assembly"`) is read once at execute entry to *derive which realizer to use* (m6 locked
decision, "capability-derives-realizer binding").

**Real second consumer?** No. The only reader is the realizer selector. And the realizer selector
already has a perfectly good key: `mode` (`_core/modes.py:38`, `is_prose_mode = {doc,joke,creative}`).
m6's own decision says `mode=code → CodeRealizer`, `mode in {doc,joke,creative} → ProseRealizer` — i.e.
*the mode already determines the realizer*. `capabilities` adds an indirection layer
(pack → capability string → realizer) over a mapping that is already 1:1 with `mode`. The justification
("prevents a pack declaring topology and evidence as two drifting facts") is solving a drift problem
that doesn't exist yet because there are two realizers and the mode already binds them.

**Cheapest version that still serves Arnold.** Nothing now. If/when a third evidence shape appears, add
the `capabilities` key *then* — it is a one-key addition to `_module_metadata`, demonstrably cheap to
defer (c5 §133 confirms no third mode on the roadmap). Pure speculative generality. **CUT.**

### 2. EvidenceRealizer abstraction (m6 scope items 2–3) — **PARTIALLY JUSTIFIED, over-built as scoped**

**What it is.** Consolidate ~20 scattered `is_prose_mode` branches across `execute/batch.py`,
`timeout.py`, `aggregation.py`, `merge.py`, `finalize.py` into one injected evidence-strategy object.

**Real second consumer?** The *consolidation* is justified on maintenance grounds alone: 20 scattered
mode-forks in freshly-stabilized code is a genuine smell, and a single selection point reduces the
"forgot one branch" bug class. That part is fair — and m6 already (correctly, per c5) refuses the
symmetric 5-method Protocol, choosing a "union of what the branches call" seam. Good.

**But:** even the seam has only two implementations, asymmetric (prose has `assemble`; code has git
evidence; neither shares the other's surface), and **no third on the roadmap** (c5 §133, m6 Open Q1).
The risk is that "inject a strategy" quietly grows toward the Protocol it disavowed — the union surface
(`capture_pre_state`, `collect_evidence_deviations`, `required_fields`, `check_done_evidence`,
`finalize_tasks`, prose-only `assemble`) is already 6 methods, two of which (`required_fields`,
`check_done_evidence`) are *already* pluggable in-tree (`merge.py:390` fork; `quality.py:150`
`_check_done_task_evidence_by_kind` with `code_*` overrides). c5: "the May 24–28 refactor already paid
down most of its value."

**Cheapest version that still serves Arnold.** Arnold does **not** need this — a second *code* tool
reuses CodeRealizer untouched; a second *prose* tool reuses ProseRealizer. The realizer earns its keep
only as a *local cleanup*, not as a platform seam. So: keep the consolidation **iff** it's a same-file,
behavior-identical de-duplication that strictly reduces branch count — cap it at consuming the two
already-pluggable hooks (`quality.py`, `merge.py`) plus one `mode`-keyed dispatcher. Do **not** build it
as an injected, capability-derived, m5-`hctx`-threaded "backend." Demote from "platform payoff
milestone" to a half-day in-place cleanup. The `assemble`-on-prose / git-on-code asymmetry is the tell
that no symmetric abstraction is warranted.

### 3. HandlerContext "pure handlers" ambition (m5) — **JUSTIFIED in half, SPECULATIVE in half**

**What it is.** Replace `handle_*(root, args)` (`argparse.Namespace` bus) with `(root, state, hctx)`
where `hctx = {config, services}`; hoist 26 env reads + `~/.megaplan/config.json` + the in-place
`apply_profile_expansion` mutation onto a typed surface; "handlers are pure-ish functions."

**Real second consumer?** Split it:
- **`services` injection (worker_runner, progress_emitter, event sink)** — **JUSTIFIED.** This is the
  seam a second tool *and* the realizer *and* tests all genuinely consume; injecting a fake
  `worker_runner` is real value. Keep.
- **The typed `config` surface** — **SPECULATIVE as scoped.** c4 measured **81 distinct fields**; m5
  concedes it will type only the "threaded core subset" and keep a "typed escape hatch" for the other
  ~64. An escape-hatch over 64 fields *is the* `getattr` *bag with a new name*. The "pure handlers"
  framing is fiction the brief itself retracts (m5 "Honest framing": gate keeps its tiebreaker/reprompt/
  auto-downgrade cascade; execute stays a multi-batch driver). No second tool needs handlers to be pure;
  it needs them to *dispatch under a typed config it can populate* — which the threaded-core subset +
  services already gives.
- **The killer (c4 Unknown-unknown, u2 §3):** even after m3 goes in-process, m3's own locked decision
  keeps config **reconstituted from `state["config"]` per stage**. So `hctx` is re-derived from state
  anyway — "build once, thread it" never materializes. The premise that motivates the typed bus is
  contradicted by the execution model it sits on.

**Cheapest version that still serves Arnold.** c4's verdict verbatim: ship (a) a typed `RunConfig` over
the *threaded* read surface (worker/receipt/profile/agent resolution — the subset that actually flows
down), and (b) the `services` bundle. Drop the "pure handlers" goal, drop the ambition to type all 81
fields, drop the deprecation-shim dance for both `__all__`s *if* you keep `(root, args)` and pass `hctx`
as an added kwarg instead of a signature break. ~20% of the work, ~80% of the value.

### 4. auto.py in-process port (m3) — **SPECULATIVE for Arnold; the single biggest over-build**

**What it is.** Port the ~2,500-LOC subprocess-driving `drive()` loop onto the executor as in-process
`RuntimePolicy` hooks, removing the per-phase subprocess (the isolation/timeout/crash boundary).

**Real second consumer?** **No.** This is the clearest YAGNI-vs-elegance case in the epic. m3's own brief
admits "extreme/max," "the riskiest milestone," and that the subprocess gave three things for free
(kill-able timeout, state isolation, crash containment) that *all must be re-engineered* in-process
(m3 Constraints #1, Open Q1/Q3). u2 §1/§3 is unambiguous: auto.py never touches the executor, "single
execution path" is internal elegance, two engines coexisting is *fine*, and porting it delivers **zero
pack-ification value**. Worse: a second Arnold tenant makes the subprocess-collision *worse*, not better
(more concurrent drives racing the in-process lock — m3 Open Q4). The product goal ("discovered packs
that dispatch") is reached without ever touching auto.py.

And the downstream damage: **m4 and m5 both list m3 as a hard dependency.** m4's routing collapse is
gated on "auto.py runs in-process" (m4 Constraints); m5 "cannot start until m3 is done." So the single
riskiest, lowest-product-value milestone is wedged *upstream* of the two genuinely useful ones. That is
the sequencing trap u2 §3 named — built anyway under "dependency ordering."

**Cheapest version that still serves Arnold.** Keep two engines. Do the *valuable, low-risk* slice of m3
on its own: write `test_auto_drive.py` as a characterization oracle (real value — auto.py has zero
direct tests), pin the `megaplan status` JSON contract (m1), and re-point the cloud SSH coupling onto
it. **Do not port the loop.** Unblock m4/m5 by severing their false m3 dependency: pack-ification and a
typed RunConfig do not actually require in-process drive — they require the executor and the parity
gate, both of which exist after m1. The "single path" is the abstraction layer nobody needed.

### 5. Discovery-integrity guard elaborateness (m1 W5) — **JUSTIFIED, but watch the gold-plating**

**What it is.** A guard so a module that *looks like* a pack but fails to import / lacks `build_pipeline`
fails loud instead of silently returning `None` (`registry.py:301–340, 360`).

**Real second consumer?** Yes — this is cheap, real insurance that directly enables suspect #6 (dropping
`_BUILTIN_NAMES`): without it, a planning that fails to import becomes a silent "no pipeline named
'planning'." A second tool genuinely benefits from "broken pack = loud error." **KEEP** — but at the
*assertion* altitude u2 §B endorses ("a one-line CI assertion is a fine price for symmetry"), not as an
elaborate report-vs-raise policy engine. m1's own Open Questions already wobble on hard-raise vs
collect-and-report vs user-dir special-casing — that wobble is the gold-plating risk. **Cheapest
version:** distinguish "not a pack" from "broken pack," raise on broken in-tree packs, log-loud on
broken user-dir packs. One function, ~15 lines. Resist the policy matrix.

### 6. Dropping `_BUILTIN_NAMES` / pack-ifying planning (m4) — **JUSTIFIED (the load-bearing pillar)**

**What it is.** Relocate planning to `pipelines/planning/`, remove its `_BUILTIN_NAMES={"planning"}`
privilege (`registry.py:53`), let it be discovered like creative/doc; collapse the split-brain routing.

**Real second consumer?** Yes — **this is the one pillar the Arnold story makes load-bearing** (u2 §B,
the unanimous keep). If planning is a privileged special case, every second tool is a second special
case; if planning is "just a discovered pack," the second tool is cheap. The symmetry here is *not*
aesthetics — it is the literal mechanism by which "first of several" becomes true. u2's own self-critique
("deleting a privilege and rebuilding it as an assertion") is correct but cheap to accept: the assertion
(suspect #5) is the price, and it's a line of CI.

**One caution — the routing collapse rider.** m4 bundles "retire `_label_for`/`_gate_next_step`" (the
split-brain routing). c1/m4 confirm `_gate_next_step`'s output is *already dead* for gate dispatch (the
`PipelineVerdict` wins). Good — that's a real dedup. But it's gated on m3 (m4 Constraints: "the collapse
is only safe once auto.py runs in-process"). Sever that: the routing collapse needs *one execution path
through the executor*, which m1 provides — not the auto.py port. **KEEP m4; cut its m3 dependency.**

### 7. (bonus) m2 profile pack-agnosticism — **JUSTIFIED, under-weighted by the epic**

Not on the suspect list but the inverse case: c6/u2 show this is the *actual* "any pack" blocker
(`VALID_PHASE_KEYS` rejects non-planning slots; `resolve_agent_mode` KeyErrors on unknown packs). The
demo packs are a "false proof of genericity" — they never dispatch a model. This is ~2–3.5 days and is
the thing a second tool truly cannot live without. The over-engineering critique is *not* "this is too
much" — it's that the epic spent its risk budget on m3/m5/m6 while m2 (the real enabler) is the small,
unglamorous, must-build piece. **Build this; it's the cheap path to the product goal.**

---

## Verdict table

| Suspect | Real 2nd consumer? | Verdict |
|---|---|---|
| 1. `capabilities` tuple | No — `mode` already binds the realizer 1:1 | **SPECULATIVE — cut; add when a 3rd shape ships** |
| 2. EvidenceRealizer | Maintenance only; 2 asymmetric modes, no 3rd | **PARTIAL — keep as in-place cleanup, not a platform seam** |
| 3. HandlerContext | `services` yes; typed-config/"pure" no (81 fields, re-derived per stage) | **HALF — ship RunConfig+services, drop purity & full-typing** |
| 4. auto.py in-process port | No — two engines is fine; zero pack value; highest risk | **SPECULATIVE — keep 2 engines; do oracle+contract only** |
| 5. Discovery-integrity guard | Yes — enables #6 cheaply | **JUSTIFIED — but as a ~15-line assertion, not a policy engine** |
| 6. Drop `_BUILTIN_NAMES` / pack-ify planning | Yes — *the* Arnold mechanism | **JUSTIFIED — keep; sever its m3 dependency** |
| 7. m2 profile agnosticism (inverse) | Yes — the real "any pack" blocker | **JUSTIFIED & under-weighted — build it** |

## The single leanest path that still achieves the product goal

1. **m1** as written *minus* gold-plating: parity gate finished + permanent CI, `schema_version` +
   validator, pinned `status` JSON contract, the two lock-free state fixes, the **assertion-grade**
   discovery guard, and **merge the two executor functions** (kill the lossy `run_pipeline_with_policy`
   subset). *Skip the `MEGAPLAN_UNIFIED_DISPATCH`/`dispatch_path` toggle's reason-for-being* — it exists
   only to cut over auto.py (#4), which we aren't doing.
2. **m2** in full — profile pack-agnosticism + one real pack that *actually dispatches a model*. This is
   the product goal's true gate.
3. **m4** — pack-ify planning, drop `_BUILTIN_NAMES`, collapse the dead routing. **Re-point its
   dependency from m3 → m1** (it needs one executor path, not in-process auto).
4. **A thin slice of m5** — typed `RunConfig` over the threaded-core read surface + the `services`
   bundle, passed as an added kwarg (no `(root,args)` signature break, no shim dance). Drop "pure
   handlers," drop typing all 81 fields, drop the m3 dependency (re-derive-from-state is fine).
5. **A half-day of m6** — consolidate the `is_prose_mode` forks in-place behind a `mode`-keyed
   dispatcher consuming the existing `quality.py`/`merge.py` hooks. No injected backend, no
   `capabilities`, no symmetric protocol, no PR #43 re-home (CodeRealizer is YAGNI until a code-evidence
   *second tool* asks for it).
6. **Drop m3's port entirely**; keep its *oracle* (`test_auto_drive.py`) and *contract re-point* as a
   standalone, optional ticket gated on a real tenant demanding in-process drive. Two engines coexisting
   is the cheapest thing that ships.

Net: the Arnold goal — discovered packs that dispatch under one profile contract — lands in **~2–3
weeks** (m1-lean + m2 + m4 + thin m5/m6), not the ~2.5x-overrun the full six-milestone serial spine
produced. Everything cut is internal elegance the second tool never touches; everything kept is the
mechanism by which "first of several" becomes literally true.
