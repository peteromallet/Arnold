# M1 — plan-all-first: two-pass plumbing + durability

Sprint 1 of the plan-all-first epic. Design of record:
`briefs/plan-all-first-epic-mode.md` (4-lens sense-checked; see its "Review
findings" section for corrections C1–C4 and the build order — this sprint is
build-order steps 1–2). Sizing: `partnered`, `full`, depth `medium`.

## Outcome
Add an **opt-in** way to run a `megaplan chain` epic in two passes: a **planning
pass** that drives every milestone to `finalized` (no execution) and stops, and a
separate **execute pass** that resumes those finalized plans to `done` in listed
order. This sprint delivers the plumbing + durability only; cross-milestone
contracts, the review surface, and the reground gate are M2. A reviewer checks:
`chain plan` produces finalized plans without executing; `chain execute` then runs
them; default `chain start` is unchanged.

## Scope (IN)
- A `plan_only` mode for the chain: plan each milestone to `STATE_FINALIZED`, then
  **advance to the next milestone without executing**.
- A first-class **`finalized` SUCCESS outcome** from `auto.drive`, wired through
  `DriverOutcome`/`_outcome` and the chain's `_handle_outcome` so a finalized-stop
  maps to **"advance"** — NOT into the failure ladder (this is correction C2: today
  `_handle_outcome` routes anything ≠ `"done"` into `on_failure_policy`).
- `auto.drive` honors a stop-at-finalized signal (`state.config.plan_only` and/or a
  drive parameter) and returns the finalized success outcome instead of proceeding
  into `execute`. (`STATE_FINALIZED` is not in `AUTOMATION_TERMINAL_STATES`, so the
  loop runs into execute by default unless this check is added.)
- CLI surface: **`megaplan chain plan --spec …`** (planning pass) and
  **`megaplan chain execute --spec …`** (execute pass). Subcommands, not flags —
  this resolves the operator-UX ambiguity; do NOT add `--then-execute` /
  `--execute-pending`.
- **Durability (C1):** the planning pass **force-adds** (`git add -f`) each
  milestone's immutable plan artifacts (`final.md`, `finalize.json`, the idea file)
  to **`base_branch`**, because `.megaplan/` is gitignored (`.gitignore:3`) and the
  chain's plain `git add -A` silently skips ignored paths. Commit to `base_branch`,
  NOT a side "planning branch" — a side branch would not be present on the
  per-milestone checkout the execute pass stands on.
- **Fresh approval on execute (C3):** the execute pass must require a fresh gate
  approval and must NOT silently carry pass-1's `user_approved_gate` /
  `auto_approve`. The whole premise is "review before spend".
- **`merge_policy: review` handling (C4):** under per-milestone branches, N+1 only
  sees N's code once N's PR merges. The execute pass must respect the existing
  awaiting-merge halt and resume correctly.
- `chain status` surfaces, per milestone: planned vs executed, and which branch
  holds the persisted plans.

## Locked decisions
- Stop point is `STATE_FINALIZED`; `final.md` is the review artifact. Resume into
  execute is free at the state-machine level (verified: `workflow_next(finalized)`
  → `execute`; `handlers/execute.py:98` accepts `STATE_FINALIZED`).
- Subcommands `chain plan` / `chain execute` (not flags).
- Force-add artifacts to `base_branch` (not a side branch).
- Default `chain start` behavior is unchanged; the mode is purely additive.

## Open questions (planner resolves)
- The concrete representation of the finalized success outcome — a new
  `DriverOutcome.status` value vs a flag — and exactly how `_handle_outcome`
  distinguishes it from a failure to route it to "advance" while skipping the
  execution commit/merge/PR block (`chain/__init__.py:~1949-1986`).
- Whether `chain execute` re-derives the milestone list from `chain.yaml` or from
  persisted chain state, and how it discovers the finalized plans (chain state
  records `{label, plan, status}` per milestone in `.megaplan/plans/.chains/`).
- What ladder-`retry` means in the execute pass: it must **re-execute the existing
  finalized plan**, NOT re-init/re-plan and discard the reviewed plan (do not null
  `current_plan_name`).
- Whether to force-add via a new helper or by extending `_commit_and_push_phase`.

## Constraints
- Strictly additive + opt-in: default `megaplan chain start` must be byte-for-byte
  unchanged in behavior (regression-tested).
- Backward-compatible `chain.yaml`: existing specs run identically.
- The execute pass must be safe on a fresh checkout / different machine — durability
  is the point of the force-add.

## Done criteria
- `megaplan chain plan --spec <2-milestone fixture>` drives both milestones to
  `finalized`, force-commits their `final.md` to `base_branch`, and stops without
  executing; `chain status` shows both planned, none executed.
- `megaplan chain execute --spec <same>` resumes both finalized plans and executes
  them in listed order, requiring a fresh gate approval (not carried from pass 1).
- A test asserts a finalized-stop is recorded as success/advance, NOT a
  failure-ladder event.
- A test asserts the force-added `final.md` is visible on `base_branch` (i.e. would
  survive a fresh checkout).
- A test exercises `merge_policy: review` halt/resume across the execute pass.
- Default `chain start` regression test passes unchanged.

## Touchpoints
- `megaplan/chain/__init__.py`: milestone loop (~1751); `_handle_outcome`
  (~1499-1510); `_init_plan` (~1034); `ChainSpec`/`from_dict` (~407/436);
  `_drive_plan` (~1122); advance/commit/PR block (~1949-1986); chain state record
  (~2000-2008).
- `megaplan/chain/git_ops.py`: `_commit_and_push_phase` (~632/652);
  `_claimed_root_paths` (~341) — add a force-add path for plan artifacts.
- `megaplan/auto.py`: drive loop + terminal-state check (~1543);
  `DriverOutcome`/`_outcome`.
- `megaplan/types.py`: `AUTOMATION_TERMINAL_STATES` (~74); state constants.
- `megaplan/handlers/execute.py`: state guard (~98); approval gate (~108-116) —
  fresh-approval logic.
- `megaplan/handlers/init.py`: `_build_state_config` — persist `plan_only`.
- `megaplan/cli/__init__.py`: chain subcommand registration (~1545) — add `plan` /
  `execute`.
- `.gitignore:3` (`.megaplan/`) — context for the force-add.

## Anti-scope
- Do NOT build the Provides/Assumes contract, `review.md`, prompt conditioning, or
  the reground gate — those are M2.
- Do NOT change default (non-`plan_only`) chain behavior.
- Do NOT touch plan/critique/execute model routing or tiers.
- Do NOT redesign chain state schema beyond what's needed to record
  finalized/plan-only status.
