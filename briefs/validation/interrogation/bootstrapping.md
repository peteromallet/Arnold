# Interrogation — Ship-of-Theseus / Bootstrapping lens

**Lens:** We rebuild planning ON the Arnold SDK while USING planning (and this repo's own chain/auto/state
tooling) to drive the rebuild. The deliverable *is the engine*, and the engine is being swapped underneath
the flight that builds it. Ambition is fixed (full extraction, no privilege); the question is only what the
plan must ADD/fix/re-sequence to survive flying-while-rebuilt.

Premortem `p3-self-reference.md` already nails the M1→M3 schema/seam deadlock. This interrogation does NOT
restate it — it extends past where p3 stops, to three things p3 under-weights: (1) the executable artifact
(`chain.yaml`) currently drives a DIFFERENT, stale milestone program than the design of record; (2) the true
ship-of-Theseus killzone is M5, not M3, because M5 extracts the *supervisor tier itself* — the chain/epic
loop that is driving the epic; (3) the plan never names the discipline (strangler-fig + dual-engine) that
makes "rebuild the driver while it drives" survivable, and the parity gate as scoped cannot see the swap.

All code claims verified against the live tree (`__version__ 0.23.0`, editable install confirmed:
`Editable project location: /Users/peteromalley/Documents/megaplan`).

---

## B1 (CRITICAL) — The executable artifact drives a STALE, incompatible milestone program

The design of record (`pipeline-unification-EPIC.md:91-114`) defines a **6-milestone full-extraction**
program: m1-foundation, m2-deplanning-types, m3-drivers-state, m4-services, m5-extract-features,
m6-megaplan-as-module. The May-29 briefs (`m1-foundation.md`, `m2-deplanning-types.md`, `m3-drivers-state.md`,
`m4-services.md`, `m5-extract-features.md`, `m6-megaplan-as-module.md`) match it.

But `briefs/epic-pipeline-unification/chain.yaml` — the thing `megaplan chain` actually EXECUTES — still
points at the **stale May-28 4-milestone "v1" set**:

```
m1-foundation        -> m1-foundation.md            (ok, shared name, but the May-29 content)
m2-dispatch-service  -> m2-dispatch-service.md       (STALE — superseded by m2-deplanning-types)
m3-planning-as-pack  -> m3-planning-as-pack.md       (STALE — m6 work; planning relocation is now LAST)
m4-shared-substrate  -> m4-shared-substrate.md        (STALE — superseded by m4-services)
```

These are not cosmetic renames. The stale chain.yaml **inverts the most safety-critical sequencing decision
in the whole epic**: it makes "planning as a discovered pack" (drop `_BUILTIN_NAMES`, relocate) land at
**M3**, whereas the design of record and p3's recommendation deliberately push planning relocation to the
**LAST** milestone (M6) precisely so the flagship/dogfood engine stays intact until everything underneath it
is proven. If someone runs `megaplan chain` off this chain.yaml, the chain will:
  - load `m3-planning-as-pack.md` and try to relocate planning + drop the builtin at milestone 3,
  - while the *driving* chain process is still mid-flight using `_BUILTIN_NAMES={"planning"}`
    (`registry.py:53`, verified) and `from megaplan.auto import drive as auto_drive` bound in-memory
    (`chain/__init__.py:65,73`, verified),
  - i.e. it executes the single most dangerous self-reference change (H6 in p3) THREE milestones too early
    and with no m4/m5 pieces under it.

**What it forces:** chain.yaml MUST be regenerated to the 6-milestone May-29 program before any run, and the
stale May-28 briefs (`m2-dispatch-service`, `m3-planning-as-pack`, `m4-shared-substrate`) must be moved to
`deferred/` or deleted so an operator cannot point the chain at them. Add a discipline: the EPIC doc, the
brief set, and chain.yaml are ONE artifact triple that must be regenerated together; a CI/lint check that the
chain.yaml `idea:` paths and milestone count match the EPIC's milestone program. This is a pure
ship-of-Theseus failure: the map we steer by has been edited out from under the territory.

---

## B2 (CRITICAL) — M5, not M3, is the ship-of-Theseus killzone: the epic extracts its OWN supervisor

p3 worked backward to "around m3" because that is where the schema landmine (H1) detonates and the subprocess
seam (H2) is removed. That is correct but incomplete. The deeper paradox is in **M5**:
`m5-extract-features.md:42-44` extracts feature **F8 — "the chain/epic/bakeoff SUPERVISOR TIER" into a general
cross-run orchestration tier**, planning's milestone-chain + bakeoff become "bindings."

The chain/epic supervisor IS the thing driving this epic. `megaplan chain` → `run_chain`
(`chain/__init__.py:1132`) is the single long-lived process executing the milestones; it binds `auto_drive`
in-memory and shells phases as subprocesses. M5 reaches in and re-expresses that exact loop as an SDK piece
+ binding. So at M5 we are **rebuilding the supervisor while the supervisor runs the rebuild** — the purest
form of "swap the wings mid-flight." Two concrete failure modes the plan does not address:

1. **The driving chain is pinned/frozen (per p3 rec #1), but M5's acceptance is that the NEW supervisor tier
   works.** If you freeze the engine (correct), then M5's new supervisor tier is *never exercised by the epic
   itself* — it's validated only on throwaway plans. So the epic's own dogfood (the strongest test we have)
   structurally cannot cover the highest-risk extraction. The plan claims dogfooding as the proof of "others
   can build," but for F8 specifically the proof is unreachable while frozen. The plan must name a **deliberate
   second, throwaway epic** that runs ON the new supervisor tier (a "canary epic": 2-3 trivial milestones)
   as F8's acceptance, since the real epic cannot.

2. **M5 also extracts F7 "the control/override plane" and F6 "clarify/human-gate / pause-resume hook"
   (`m5-extract-features.md:38-41`).** The override plane + the `merge_policy: review` pause-resume seam
   (`chain:1397-1413`, the STATE_AWAITING_PR_MERGE exit) are the human-recovery levers the operator uses to
   un-wedge the epic when it stalls. M5 is rebuilding the recovery mechanism at the same time it's most likely
   to be needed. If the half-built control plane mis-handles an override mid-M5, the operator's escape hatch is
   the thing under construction. p3's "frozen engine" discipline covers auto/state/dispatch but NOT the
   override/control plane — which is in-process in the driver and equally being swapped.

**What it forces:** (a) re-sequence so the supervisor-tier extraction (F8) and control-plane extraction (F7)
are the LAST sub-features of M5, behind a default-off flag, never adopted by the driving chain; (b) add a
named **canary epic** as F8's only honest acceptance; (c) extend the freeze list from "auto/state/dispatch" to
explicitly include the chain supervisor loop AND the override/control plane for the epic's full duration.

---

## B3 (HIGH) — No strangler-fig discipline is named; "pinned engine" alone is insufficient and contradicts dogfood

p3 recommends a pinned/frozen engine + frozen schema + default-off m3 toggle + no mid-epic `git pull`. Those
are necessary but the EPIC doc itself only says (`:127`) "don't dogfood off an editable install (pinned
engine, schema report-only till last)" — a one-liner, not a discipline, and it is in tension with the
project's whole dogfood ethos (MEMORY `project_dogfood_engine_shadow_and_openrouter`). Two gaps:

1. **The plan never names strangler-fig / dual-run as the governing pattern.** "Rebuild the engine while
   flying it" has exactly one safe shape: the new pieces grow *alongside* the old engine behind a flag, every
   extraction lands as `{old path default-on, new path default-off}`, and the old path is deleted only after
   the new path has soaked on real traffic. The briefs gesture at this per-milestone (m3's
   `MEGAPLAN_UNIFIED_DISPATCH` off; m1's report-only schema) but there is **no epic-level invariant** that
   *every* milestone must preserve a runnable old path until M6. Without that invariant, the cumulative effect
   of m2 (types) + m3 (drivers/state) + m4 (services) + m5 (features) is that by the time you reach M5 the old
   path may already be half-deleted across four milestones with no single gate enforcing "old engine still
   boots and drives a plan." The strangler must be a stated, gated epic invariant, not an emergent per-PR habit.

2. **The pinned engine defeats the dogfood signal — and the plan doesn't reconcile this.** The strongest
   evidence that the SDK works is planning running on it. But the freeze (correctly) means the engine driving
   the epic is the OLD engine, so the epic never exercises the new SDK on itself until M6's final re-launch.
   That is a multi-month window (m2→m5) where planning-on-Arnold is built but NEVER self-hosts — the exact
   "half-extracted and degraded" window the lens asks about. The discipline that resolves it is **dual-engine
   bring-up**: at each milestone, after merging, run a *throwaway* plan on the NEW pieces (the milestone's
   non-planning acceptance toy is necessary but not sufficient — it must ALSO be a planning-shaped plan on the
   new pieces) so the self-hosting path is continuously smoke-tested off to the side, even though the
   load-bearing epic stays on the frozen engine. The plan has the non-planning acceptance toys but NOT a
   "planning runs on the new pieces" smoke test per milestone — so the self-host regression is invisible until
   M6, the worst possible place to discover it.

**What it forces:** Add an epic-level invariant (gated in every milestone's done-criteria): "the OLD engine
still boots and drives a 1-milestone throwaway plan AND a planning-shaped plan runs on the NEW pieces." Name
strangler-fig + dual-engine as the governing discipline in the EPIC doc, not a one-line aside.

---

## B4 (HIGH) — The parity gate guards behavior but is structurally blind to the engine swap underneath it

The EPIC leans on the parity gate as the behavior guardrail (`:128`, m1 W6). But m1 explicitly scopes the
gate to **"control-flow / artifact parity on the fixtured happy path"** and declares
**"Subprocess-vs-in-process, routing, timing, cost, emission parity are explicitly out of M1"**
(`m1-foundation.md:67-68,82-83`). Through the ship-of-Theseus lens this is the central blind spot: the gate
compares OUTPUTS of two code paths, but the thing being swapped is the SUBSTRATE — subprocess→in-process
(m3), last-writer-wins JSON→leased/versioned Store (m3), `events.ndjson`→`EpicEvent` emit (m4), the dispatch
backend (m4). A parity gate that SHA256-compares 10 deliverable artifacts on one happy path
(`test_pipeline_parity.py`, `_PARITY_ARTIFACTS`) will stay GREEN while the executor, state model, and
dispatch underneath are entirely replaced — because those produce the same artifacts on the happy path. The
gate proves the new wing has the same shape; it cannot detect that the new wing is made of different metal and
fails under load (concurrency, crash-isolation, resume-after-merge, version-skew) — exactly the failure axes
p3's H1/H2 live on. The plan even says "honest label — not drift provably zero," which is honest, but it does
not then ADD the missing oracles for the swapped substrate as a gated requirement.

**What it forces:** The epic needs a **swap-detecting oracle suite** that the happy-path parity gate cannot
provide, gated per milestone where the swap happens: (a) a resume-across-versions oracle (write state on old
engine, resume on new — directly tests H1); (b) a crash-isolation oracle (kill a step mid-run, assert the
process driver contains it but the in-process loop driver does NOT — proves the substrate trade is real, m3
done-criteria #2 gestures at this but it must be an EPIC-level gate, not a milestone-local test); (c) a
self-host oracle (planning drives a throwaway plan on the new pieces, B3). "Behavioral parity is proven
per-milestone by named oracles" is asserted in m1 (`:67`) but the oracles for the *substrate swap
specifically* are not enumerated anywhere — they must be.

---

## Cross-cutting verdict

The verbs of the plan are right and the p3 premortem is genuinely strong on the M1→M3 deadlock. What the plan
is missing through THIS lens is (1) artifact hygiene — the executable chain.yaml has drifted off the design of
record and inverts the safest sequencing (B1); (2) recognition that M5, where the supervisor/control plane is
extracted, is a second and arguably worse killzone than M3 because it rebuilds the recovery mechanism and the
driving loop itself (B2); (3) a NAMED discipline — strangler-fig + dual-engine bring-up + an epic-level
"old-boots / new-self-hosts" invariant — rather than scattered per-milestone flags (B3); and (4) a
swap-detecting oracle suite, since the happy-path parity gate is structurally blind to a substrate swap (B4).
None of these reduce ambition; they are the scaffolding full ambition requires to not saw off the branch it
is standing on.
