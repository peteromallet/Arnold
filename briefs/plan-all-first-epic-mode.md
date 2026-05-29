# Brief: Plan-all-first epic mode (opt-in)

**Status:** design / discussion. Not yet scheduled into the pipeline-unification epic.
**Owner:** Peter. **Drafted:** 2026-05-29.
**⚠️ See "Review findings" at the bottom (4-lens sense-check, 2026-05-29) — it corrects two
factually wrong claims below (persistence + stop-at-finalized) and reframes the scope decision.**

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

---

## Review findings (4-lens sense-check, 2026-05-29)

Sense-checked from four angles: agent-UX + architecture (Claude), operator-UX +
simplicity (DeepSeek). Each lens saw only its own brief. Summary of what they
converged on, what they corrected, and the one decision they fork to.

### Factual corrections (verified against code — these hold regardless of scope)

- **C1 — Persistence is broken as written.** The brief claims `git add -A` commits
  plan artifacts on the planning branch. `.gitignore:3` is `.megaplan/` (whole
  dir) and `git_ops.py:652` uses plain `git add -A`, which **silently skips
  gitignored paths** (no `git add -f` anywhere). So the "planning branch" commit
  would contain *nothing* — plans vanish on any fresh checkout / cloud box. Fix:
  an explicit `git add -f` of only the immutable artifacts (`final.md`,
  `finalize.json`, idea) committed to **`base_branch`** (not a side branch — a
  side branch isn't on the per-milestone checkout, so the execute pass can't find
  the plans).
- **C2 — Stopping at `finalized` is NOT free.** `STATE_FINALIZED` is *not* in
  `AUTOMATION_TERMINAL_STATES` (`types.py:74`), so `auto.drive` runs straight
  through into execute unless the `plan_only` check is added (scoped, fine). The
  deeper miss: the chain's `_handle_outcome` (`chain/__init__.py:~1507`) routes
  **anything that isn't `status=="done"` into the failure ladder** (retry → bump →
  abort). A finalized-stop therefore looks like a *failure* to the chain. Fix: a
  first-class `finalized` **success** outcome wired through `_outcome` +
  `_handle_outcome` → "advance" (skipping the execution commit/merge/PR block).
  Both DeepSeek and Claude independently flagged this; even the "minimal" version
  needs it.
- **C3 — `auto_approve` carry.** Pass-1 finalized plans persist their gate/approval
  state. If pass 2 inherits a `user_approved_gate`, execution could auto-proceed
  without a fresh human gate — defeating the whole "review before spend" premise.
  The execute pass must require a fresh approval, not carry pass-1's.
- **C4 — `merge_policy: review` breaks "serial ordering is sound".** Under per-
  milestone branches, N+1 only sees N's code once N's PR *merges*; with
  `merge_policy: review` the execute pass halts awaiting a human merge after every
  milestone. The two-pass story must state this.

### Strong convergences (independent lenses arriving at the same point)

- **The single highest-leverage addition: a structured Provides/Assumes contract.**
  Agent-UX and operator-UX reached this from opposite ends. `final.md` is loose
  prose; when M4 and M5 both plan against M3's *planned* (not built) interface,
  they invent mutually-incompatible APIs, and the human reviewing 8 separate
  `final.md`s can't see the seams either. Fix solves **both**: add a structured
  **Provides** (interfaces/paths/signatures this milestone commits to create) and
  **Assumes** (upstream interfaces copied verbatim from upstream's Provides) block
  to `final.md`, and emit a chain-level **`review.md`** that tabulates
  Provides→Assumes across milestones and flags mismatches. Siblings agree by
  construction; the human gets a decision surface instead of a file-crawl; and the
  future reground gate gets a machine-comparable thing to diff.
- **The flag surface is too big.** Operator-UX wants subcommands (`megaplan chain
  plan` / `megaplan chain execute`); simplicity wants one flag (`--plan-only`,
  re-run without it to execute). Both agree: **drop `--then-execute` and
  `--execute-pending`.** Resolve the ambiguity (what does a bare re-run against a
  planned chain do?) — subcommands are the cleaner answer.
- **Mode-conditioned prompts are mandatory, not polish.** The existing prep/plan
  prompts are saturated with "inspect the repo / ground against the tree"
  instructions, and `_cross_reference_prep_output` (`prep_research.py:452`)
  auto-flags upstream paths as `missing_files` → every milestone correctly
  referencing upstream gets *penalized*. A single "planned-not-built" framing line
  fights a dozen contrary instructions and loses. Need a `plan_only`-conditioned
  prompt variant + a cross-reference that partitions paths into "exists-now" vs
  "to-be-built-by-<milestone>". Triage's built-in minimization bias also means
  "hand pointers, let triage decide" will systematically *under-read* — force a
  summary of `depends_on` upstreams, offer the rest as optional.

### The central decision they fork to: what is this feature FOR?

The drift risk (plan written against upstream's *plan*, executed against its
*divergent actual output*) is **not uniform** — and it determines scope:

- **Loosely-coupled milestones** (independent work, no shared interface):
  plan-all-first is safe and cheap. The simplicity lens's minimal build wins —
  one `plan_only` field + a `stop_at:finalized` param + the C2 success-outcome
  wiring; drop the planning branch, pointer injection, contract, and reground.
- **Tightly-coupled milestones** (N+1 builds against an interface N defines — i.e.
  the seam-fixing pipeline-unification epic this is *motivated by*): the minimal
  build produces **net-negative** plans (a just-in-time plan against N's real code
  — what default serial mode already does — is strictly more accurate). Here you
  need the Provides/Assumes contract + `review.md` + a reground gate that's
  **MVP-mandatory for any `depends_on` milestone**, not a follow-on.

So: is plan-all-first a cheap *preview* of a loosely-coupled epic's shape, or a
*seam-coherence tool* for a coupled epic? That answer sizes everything else.

### DECISION (Peter, 2026-05-29): full execution-ready plans in advance, both cases

Goal: produce **full plans for the whole epic in advance that are genuinely
executable later** — supporting both loose and coupled milestones. Consequence:
because the motivating epic is coupled and the bar is "executable, not just
reviewable," the contract + reground machinery is **load-bearing, not optional** —
it's what keeps an advance-made plan executable once upstream reality diverges. The
loose case is the same build with empty `Assumes` blocks (no special path).

**Build order (each step independently useful, later steps make plans executable):**

1. **Plumbing (makes the mode exist).** `plan_only` flag → `state.config`;
   `auto.drive` stops at `STATE_FINALIZED`; **first-class `finalized` success
   outcome** through `_outcome`/`_handle_outcome` → advance, skipping the
   exec commit/merge/PR block (C2). Subcommands `chain plan` / `chain execute`;
   drop `--then-execute` / `--execute-pending`. Fresh approval required on the
   execute pass (C3).
2. **Durability.** Force-add (`git add -f`) the immutable artifacts to
   `base_branch` so the execute pass (possibly on another checkout) finds them
   (C1). Handle `merge_policy: review` halts in the execute pass (C4).
3. **Cross-milestone context, structured.** Add **Provides/Assumes** blocks to
   `final.md` (finalize.py); inject upstream Provides into N+1's prep/plan; force a
   `depends_on`-upstream summary (don't leave it to triage's minimization bias).
   Mode-conditioned prep/plan prompts + a cross-reference that partitions
   exists-now vs to-be-built (so upstream paths aren't penalized as missing).
4. **Review surface.** Emit chain-level `review.md` tabulating Provides→Assumes
   across milestones, flagging mismatches — the operator's actual decision surface.
5. **Reground gate (what makes coupled plans executable).** Before each milestone's
   execute pass, diff its `Assumes` against the upstream's *actual* committed
   Provides; on material drift, halt-for-human or auto-`override replan` that one
   milestone. MVP-mandatory for any `depends_on` milestone.

Steps 1–2 are the tiny version (loose epics, reviewable). Steps 3–5 are what make
the plans executable for the coupled epic — the stated goal — so they're in scope,
just sequenced after the plumbing proves out.
