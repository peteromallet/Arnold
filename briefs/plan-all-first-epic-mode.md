# Brief: Plan-all-first epic mode (opt-in)

**Status:** design / discussion. Not yet scheduled into the pipeline-unification epic.
**Owner:** Peter. **Drafted:** 2026-05-29.

## What we want

An **opt-in** way to run an epic that plans *every* milestone up front — prep →
plan → critique → revision → finalize for all of them — **without executing any
of them**, then stop so a human can review the whole epic's plan as a coherent
set, and kick off execution as a **separate pass** later.

Default behaviour is unchanged: `megaplan chain start` still plans-and-executes
each milestone serially. This is purely additive and never the default.

Motivation: review the epic's shape and milestone-boundary coherence *before*
spending execution money; catch interface/contract mismatches between milestones
early; iterate cheaply on the program. The pipeline-unification epic is the first
candidate (plan all of M0–M7 in advance, eyeball the seams, then run).

## How the pipeline works today (the relevant parts)

A single milestone is a state machine (`megaplan/_core/workflow_data.py`):

```
initialized → prepped → planned → critiqued → gated │ → finalized → executed → reviewed → done
   └────────────── PLANNING ──────────────────────┘ │ └──────── EXECUTION ────────┘
```

- `auto.drive` (`megaplan/auto.py`) polls state and derives the next step purely
  from `workflow_next()` (`_core/workflow.py:282`); handlers can't redirect it.
- The planning→execution seam is `gated → finalized → execute`. **`final.md`**
  (`.megaplan/plans/<name>/final.md`, written by `handlers/finalize.py:613`) is
  the human-readable finalized plan — the review artifact and the thing a
  downstream milestone should *read* to understand what an upstream one will build.

An epic (`megaplan/chain/__init__.py`) is a serial loop: for each milestone,
`_init_plan` (`megaplan init` with the milestone's **idea file** as the *only*
input, `:1034`) → `_drive_plan` (= `auto.drive`, runs the full pipeline through
`done`) → commit/merge the milestone branch → next.

Two facts that make this feasible:

1. **Milestones are already planned independently.** `_init_plan` passes only the
   idea file — no prior plan, no prior context (`chain/__init__.py:1857`).
   `depends_on` is **validation-only** (asserts listing order; not a scheduler/gate).
   Nothing in the harness *hard-requires* milestone N to be executed before N+1
   can be planned.
2. **The dependency on upstream milestones is implicit, not enforced.** All
   milestones share one worktree, so a milestone planned *after* its predecessors
   executed can read their committed code, and idea files are written assuming
   that ("assumes m5-eval's output is in the codebase").

Fact 2 is the crux of this feature: if we plan everything up front, that code
does **not** exist yet at plan time.

## The design

### Stop point: `finalized`

Each milestone drives to `STATE_FINALIZED` and stops. `final.md` is the review
artifact. Verified clean: `auto.drive` on a plan already at `finalized` returns
`execute` from `workflow_next()`, and `handlers/execute.py:98` accepts
`STATE_FINALIZED` — **so the later execute pass needs no new resume machinery; we
just stop the first pass at finalized and let the second pass continue.**

### Two flags, layered

- `mode: plan_all_first` (chain.yaml `driver:`) / `megaplan chain start --plan-only`
  — the planning sweep. Off by default.
- Optional `--then-execute` — auto-roll into execution without the review pause.
  Off by default; the default *within* plan-only is stop-after-planning.
- Execute pass — `megaplan chain start --execute-pending` (or the chain detects
  all milestones are finalized-not-executed). Reuses chain state, which already
  records `{label, plan, status}` per milestone.

A per-milestone `plan_only` is persisted in `state.config` (via
`handlers/init.py` `_build_state_config`) so `auto.drive` returns at
`STATE_FINALIZED` (one check near the terminal-state test, `auto.py:~1543`).

### Cross-milestone context = pointers, not inlined plans

When planning milestone N, the chain hands its prep + plan steps the **locations**
of all preceding milestones' plan dirs (each holds `final.md`). The chain already
knows every `plan_name` (chain state `completed[]`), so assembling the pointer
list is trivial — write it to a context file / pass via `megaplan init`.

The planner's tools can search/read those plans on demand; the **prep triage step
decides** whether it needs to pull more in (dovetails with the prep-fanout /
research-dossier direction — prior `final.md`s become research inputs). We do
*not* stuff full plans into the prompt.

Required framing line in that context: *"Preceding milestones are planned but not
yet built. Treat their `final.md` as the spec for the assumed end-state — read
them to understand the interfaces/artifacts you'll build against; do not expect
their code to be present in the tree."* This is the prompt change — telling the
planner the previous step isn't done, so read its plan, not its code.

### Branch / persistence model

`.megaplan/` is **gitignored**; plan artifacts only get committed when the chain
runs with `use_pr=True` (`chain/git_ops.py:632`, via per-phase `git add -A`).
Consequence: plan-all-then-execute-later has a persistence hole — on a fresh
checkout / cloud box / after `git reset --hard`, the finalized plans vanish.

Decision: **the planning pass commits all milestone plan artifacts** (their
`final.md` etc.) to a single **planning branch** (not per-milestone execution
branches). The execute pass then branches + PRs per milestone for the *code* as
today. This keeps PR-per-milestone code isolation intact while making the plans
durable for the second pass. (For a same-machine/same-dir run this is optional;
make it mandatory whenever the execute pass could happen on a different checkout.)

### The central risk: plan-time vs execute-time worktree mismatch

At plan time, downstream code doesn't exist; N+1 was planned against N's *plan*.
At execute time (serial, same worktree) N's code *is* committed before N+1 runs —
so execution **ordering** is sound. But execution always diverges from the plan,
so N+1's finalized plan may reference interfaces/paths that don't match N's
*actual* output.

There is **no existing reground mechanism** (verified: no reground/refresh/
revalidate handler; `override replan` is a full rewind to `planned` that reruns
the whole plan phase). Options, tied to robustness:

- **MVP / lower robustness:** ship plan-all + execute-later with *no* reground.
  Accept that the operator may manually `override replan` a milestone if its
  upstream diverged materially. Honest framing: the plan-all output is a *coherent
  epic draft for review*, not a frozen contract.
- **Hardening / higher robustness:** add a lightweight **reground gate** at the
  start of each milestone's execute pass — re-read the current tree, check the
  plan's key assumptions, and on material drift auto-trigger `override replan` for
  that one milestone (reusing the existing transition; we'd build only the
  *detection*, not a new replan path).

Recommendation: build the MVP first, treat the reground gate as a follow-on tied
to robustness level (avoid over-building the detector before we've felt the drift
in a real run).

### Failure semantics

In plan-only, only **planning** can fail; the autonomy ladder
(`on_failure: retry → bump_profile → abort`) applies to planning only. Simpler
than the full run.

## Touch points (precise)

- `ChainSpec` / `from_dict` (`chain/__init__.py:407,436`) — parse `mode` / `--plan-only` / `--then-execute` / `--execute-pending`.
- Milestone loop (`chain/__init__.py:1751`) — plan-only branch: drive to finalized, advance on finalized (not done), skip execution commit/merge/PR, write prior-plan pointers, commit plan artifacts to the planning branch.
- `_init_plan` (`chain/__init__.py:1034`) — accept + forward prior-plan-dir pointers to `megaplan init`.
- `handlers/init.py` `_build_state_config` — persist `plan_only` in `state.config`.
- `auto.py` drive loop (`~:1543`) — terminate at `STATE_FINALIZED` when `plan_only`.
- prep + plan prompt assembly — inject pointer list + "planned-not-built" framing. (Locate the prep/plan prompt builders; not yet pinned.)
- Execute pass — drive each existing finalized plan finalized→done in listed order (no resume flag needed; reuses chain state `completed[]`).
- (Hardening) reground gate before each milestone's execute — new detector + reuse `override replan`.

## Open questions

1. Planning branch naming / layout — one branch with all plan dirs, or plans
   committed under the base branch in a subdir? (Affects how the execute pass
   discovers them.)
2. Should the prep/plan pointer list be *all* prior milestones or filtered (e.g.
   ordered by `depends_on`)? Peter's call: hand all, let triage decide — confirm
   that's still right at scale (M0–M7 is 8+ `final.md`s).
3. Does the reground gate belong in this brief's scope or a separate hardening
   ticket?
4. `--then-execute` + cloud: if auto-continuing, do we still need the planning
   branch commit, or only when there's a review gap between passes?
