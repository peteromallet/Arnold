# P7 — Pre-mortem: sequencing, estimation, merge-drift

Lens: sequencing / estimation / merge-drift. Working backward from a stalled epic 6 months out.
Grounded against `.megaplan/briefs/pipeline-unification-EPIC.md`, `.megaplan/briefs/epic-pipeline-unification/chain.yaml`,
and git history as of 2026-05-28.

## Evidence base (measured, not asserted)

**Repo velocity is very high and bursty.** Commits/week over the trailing 90 days:
W08 73, W09 436, W10 895, W11 627, W12 125, W13 77, W14 40, W15 31, W16 26, W17 11, W18 57,
W19 84, W20 82, W21 85. Even the "quiet" recent weeks run 80+ commits/wk. A 2–3 month epic
therefore lands on top of **~700–1000 commits of main movement**, much of it touching the exact
blast radius.

**Blast-radius churn, trailing 120 days:**
- `megaplan/auto.py` — 2468 LOC, **45 commits**. The hinge file is one of the hottest files in the
  repo. Recent touches: shannon-staleness, prep-clarify, prep 3-step, execute-core split, prompt-shim
  removal. The brief's "no auto.py changes until m3" anti-scope is fighting the river's current.
- `megaplan/handlers/*` — **80 commits**.
- `megaplan/_pipeline/*` — **38 commits** (incl. the M5d `patterns.py` god-file split landed *during*
  this window — exactly the file m1/m6 lean on).
- `megaplan/execute/*` — 32 commits, dominated by `execute/core.py` (**25**), which was itself being
  decomposed into batch/merge/aggregation concurrently (M5c). m1's "override-complete executor" and
  m3's port both sit on top of a contract that was actively moving.
- `megaplan/profiles/__init__.py` (1739 LOC, holds `VALID_PHASE_KEYS`/`DEFAULT_AGENT_ROUTING`) —
  **24 commits**; `megaplan/workers/_impl.py` (2657 LOC, `resolve_agent_mode`) — **24 commits**.
  m2's surfaces are hot, in two huge files.

**Concurrent streams.** The merge log shows many parallel branches landing continuously
(hardening-epic, critique-evaluator, prep-fanout, megaplan-cost, shannon-staleness, cloud-prereq,
subprocess-runtime, variable-profiles…). This is not a repo where you can freeze a foundation for a
quarter; it is a repo where 4–6 feature branches are in flight at any moment, several of them
editing handlers/, execute/, _pipeline/, and auto.py.

## How the epic actually stalls (both failure modes confirmed)

### Mode A — m3 blows its estimate and freezes the back half
m3 is tagged **apex / extreme / max** — the only extreme/max milestone — and is honest that auto.py
"has zero direct tests." The plan is: write `test_auto_drive.py` as a parity oracle FIRST, *then*
port ~2500 LOC of recovery/retry/escalate/`--fresh`/blocked-retry/per-phase-timeout logic in-process,
*then* reconcile three competing resume models (`_pipeline_paused_stage` vs
`current_state`/`next_step`/`resume_cursor` vs `STATE_AWAITING_HUMAN`), *then* re-point the cloud SSH
coupling. That is four hard sub-projects in one milestone, each of which has historically generated
its own bug-and-fix memory entries (execute stall, shannon stream stall, chain-blocked-retry, gate
tiebreaker downgrade, auto-gate bypass). Estimating this as one milestone at the same granularity as
m4/m5/m6 is the estimation error. When m3 slips, `stop_chain` means **m4, m5, m6 never start** — half
the epic is gated behind the single riskiest item, sitting at position 3 of 6.

### Mode B — drift rots the early gates before the late milestones consume them
m1 ships a parity gate as "permanent CI" and a pinned `megaplan status` JSON contract. m2 reshapes
`VALID_PHASE_KEYS`/`resolve_agent_mode`. But over the 2–3 months it takes to reach m5/m6, main lands
45 more auto.py commits and 24 more profiles commits. By m5 (HandlerContext touches the 80+-field
config surface and 26 ambient env reads) and m6 (re-homes PR #43 against a contract that has moved
twice), the m1 parity golden expectations and m2 slot contract are stale. The cross-cutting invariant
"the m1 parity gate stays green through every later milestone" becomes the thing that's perpetually
red because *main* moved the behavior, not the milestone — and every milestone spends its budget
re-baselining the gate instead of building. PR #43 is the canary: it already died once
("blocked on execute-contract reconciliation") because main's batch/`current_state` contract drifted
out from under it. m6 re-homing it 3 months later faces a strictly worse version of the same drift.

## Answers to the five questions

**(1) Strictly serial m1→m6 + `stop_chain` — wrong failure mode for this epic.** stop_chain is correct
*locally* (don't pour m4 on a broken m3), but as the *only* policy across 6 milestones spanning a
quarter, it converts any single stall into a quarter-wide freeze and lets drift accumulate against
gates that can't advance. The chain is also longer than the dependency graph requires: the graph
itself says "m2 is independent of m3–m6." Forcing m2 to wait behind nothing, but blocking m3+ behind
m2's merge, is pure serialization tax with no dependency justification.

**(2) m3 is the hinge AND the apex risk — de-risk with a spike, do NOT move it.** It can't move
earlier (depends on m1's unified executor) or later (m4/m5/m6 all depend on it). The lever is to
*split* it. Pull the test oracle forward as its own landable unit: a **m2.5 "auto.py behavioral
characterization + resume-model audit" spike** that (a) writes `test_auto_drive.py` against
*today's* subprocess auto.py and lands it on main as permanent CI, and (b) produces a written
decision on the one resume model — *before* a line of the in-process port is attempted. This converts
m3 from "test+port+reconcile+cloud, all-or-nothing" into a port executed against a green, already-merged
oracle. It also means the highest-uncertainty discovery (what auto.py actually does) happens on a
cheap spike, not inside the apex milestone where a surprise stalls everything behind it.

**(3) Drift is severe — the early gates will not hold to m5/m6 unmodified.** At measured velocity,
m1's parity golden and m2's slot contract face hundreds of intervening commits. Two structural
defenses are mandatory, not optional: (i) m1's parity gate and status contract must be **landed on
main as standalone PRs the day they pass**, not held in a milestone branch — so the rest of the team's
80-commits/wk runs against them and drift surfaces continuously instead of at integration time;
(ii) every milestone must **rebase onto main weekly** and treat "gate went red because main changed
behavior" as a first-class, separately-committed re-baseline (the brief allows this for behavior
changes but doesn't budget for the volume).

**(4) Mis-ordering: yes, two.** First, **m2 does not depend on m1** in any load-bearing way — m2 is
profile-contract work (`VALID_PHASE_KEYS`, `resolve_agent_mode`, `tier_models`), m1 is parity/state/
status/executor-merge. The graph admits this ("m2 is independent of m3–m6") but the chain still
serializes m1→m2. m2 should run on a **parallel branch off the m1 base**, not behind m1's merge.
Second, the **auto.py characterization** (currently buried as m3's first task) is logically a
prerequisite spike that should precede m3 as its own unit (see #2).

**(5) A single 6-milestone stop_chain chain is the wrong vehicle.** This epic is explicitly
"high-stakes refactor, review each PR" — i.e. each milestone is *already* meant to be a reviewable,
landable PR. A monolithic chain optimizes for unattended sequential execution; this epic needs the
opposite: independently-landable PRs that merge to main as they pass, with dependency edges enforced
by *which base branch each one forks from*, not by a linear chain that freezes on the first stall.
Use the chain only for the genuinely serial spine (m1 → m3-spike → m3-port → m4 → m5 → m6) and run
m2 as a separate parallel plan.

## Recommended restructure

1. **m1** (foundation) — land each deliverable (parity CI, `schema_version`, pinned status contract,
   lock fixes, discovery guard, executor merge) as **separate PRs to main as they pass**, not bundled.
   This is the drift armor; it only works if it's on main early.
2. **m2** (profile-agnosticism) — **parallel branch off the m1 base**, lands independently. Delivers
   Arnold value early and is off the critical path.
3. **NEW m2.5 spike** — auto.py behavioral characterization (`test_auto_drive.py` on the *current*
   engine, merged to main) + a one-page resume-model decision. Gates m3.
4. **m3** (in-process port) — now a port against a green merged oracle + a settled resume model.
   Keep apex/extreme.
5. **m4 → m5 → m6** — serial as before; m6 re-homes PR #43 against the (now in-process, stable)
   contract. Re-home PR #43's `worktrees/` package **early and opportunistically** (it's ~30%,
   low-conflict) rather than letting it drift a third time.

## On stop_chain

Keep `on_failure: stop_chain` for the **serial spine only** (m1→m2.5→m3→m4→m5→m6) — it is the right
local guard against building on a broken foundation. But (a) remove m2 from the chain so its
independence is realized, and (b) the spine's milestones must merge to main as they pass (not live in
a long-lived epic branch), so a stall freezes only *downstream* work, not the already-proven
foundation, and so main's velocity tests the gates continuously instead of all-at-once at the end.
The failure mode to avoid is not "stop on failure" — it's "one linear rope where the riskiest knot
sits at position 3 and the early knots quietly fray while you climb."
