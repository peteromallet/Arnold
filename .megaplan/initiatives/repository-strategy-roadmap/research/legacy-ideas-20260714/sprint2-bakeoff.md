# Sprint 2 — Multi-profile bake-off (concurrent, worktree-isolated, audit-merged)

## Goal

Add a `megaplan bakeoff` subcommand that runs the same idea through N profiles **concurrently**, each inside its own git worktree, then a new comparison/selection step chooses one to keep. Final merge is **asymmetric**: code changes from one chosen profile, evaluation data from all profiles.

**Prerequisite**: Sprint 1 (step receipts + canonical prompt hash + scope-drift first-class metric + global audit log). This sprint depends on receipts being in place — both for the comparison step's inputs and for the audit records that get merged back.

## Why

Single-profile runs give us one data point. To answer "which profile does this kind of task best" and "which model is scope-disciplined at execute" we need side-by-side runs on identical inputs. Worktrees make the runs truly independent (no shared git state, no crossed-stream executor output). Concurrency makes the wall time bearable.

## Scope

### 1. Worktree lifecycle

- Worktrees live **sibling to the repo**, not inside `.megaplan/`. Path: `<repo-parent>/.megaplan-worktrees/<exp-id>/<profile>/`. This avoids the circular-recursion risk where megaplan's plan-dir discovery (`rglob(".megaplan")`) would otherwise walk into the worktrees.
- Each worktree is created with `git worktree add --detach <path> <base-sha>`. `base-sha` is captured once at bake-off start; every profile demonstrably starts from the same commit.
- **Detached HEADs** are deliberate — we don't want N profile branches polluting `git branch`.
- Cleanup is **explicit and deferred**: on successful completion, artifacts are copied back first, then `git worktree remove --force`. On crash, worktrees are left in place with a `BAKEOFF_CRASHED` marker file so forensic diffs survive. `megaplan bakeoff abandon <exp-id>` offers explicit cleanup later.

### 2. Concurrent execution

- The orchestrator launches N `megaplan auto` subprocesses (one per worktree, `cwd=<worktree>`) with per-profile logs redirected to `.megaplan/bakeoffs/<exp-id>/<profile>/auto.log`. **Do not interleave to a shared stderr** — that's unreadable at N≥3 and destroys post-mortem value.
- Use `asyncio.create_subprocess_exec` (not threads — signal handling is cleaner with subprocesses, and auto-driver already shells out per phase).
- Observability:
  - `megaplan bakeoff status [--exp <id>]` — compact table `profile | state | phase | iter | age | cost`.
  - `megaplan bakeoff tail --exp <id> [--profile X]` — either tail one log or multiplex all with `[profile]` prefixes. Unified tail is a convenience; per-profile log files remain canonical.

### 3. Comparison / selection step

A **standalone subcommand**, not an auto-integrated phase. Invoked separately so it can be re-run with a different judge, resumed, or retried after the bake-off completes.

`megaplan bakeoff compare --exp <id> [--judge <model>]`

**Inputs** per profile:
- `state.json` (final state, iteration counts, rework cycles, escalations)
- All step receipts (from Sprint 1) — the primary source of structured metrics
- Phase artifacts (`plan_v1.md`, `critique_v*.json`, `execution.json`, `review_output.json`)
- `git diff <base-sha>..HEAD` from the worktree
- Auto-driver's final `DriverOutcome` JSON

**Decision tier** — three layers, advisory-then-authoritative:
1. **Auto-computed metrics** — always produced. Diff stats, test pass/fail, rework cycle count, escalations, review outcome, duration, tokens, scope-drift severity per phase.
2. **LLM judge** — configurable model (default: a model *not* present as an executor in any profile being compared — e.g., if the profiles use kimi and glm, judge with claude or gpt-5). Pairwise structured prompt: "Given these two bundles of artifacts, rank them and flag any scope drift, quality concerns, or missed requirements." Advisory only.
3. **Human pick** — `megaplan bakeoff pick --exp <id> --profile <name> [--rationale ...]` records the final selection. If the human agrees with the judge, one command.

**Output**: `.megaplan/bakeoffs/<exp-id>/comparison.json` + a readable `comparison.md`.

### 4. Comparison schema (load-bearing)

This schema is the thing that accumulates across runs into a dataset. Version it explicitly (`schema_version: 1`). Write the same fields even when a profile failed early (use nulls + flags, never missing keys).

Minimum fields:
- `experiment_id`, `base_sha`, `idea_hash` (canonical hash of the idea input)
- `profiles[]`:
  - `name`, `worktree_path`, `plan_id`, `outcome_status` (done / stalled / failed / escalated / aborted)
  - `metrics`: `duration_s`, `cost_usd`, `rework_cycles`, `escalations`, `review_verdict`, `diff_lines`, `tests_added`, `scope_drift_severity_by_phase`
  - `receipts_ref` — relative path list to the receipts that belong to this profile
- `judge_verdict`: `{ judge_model, rank[], rationale_per_profile, scope_drift_flags, concerns[] }`
- `human_decision`: `{ chosen_profile, rationale, decided_at }` (populated by `bakeoff pick`)

### 5. Merge mechanics (asymmetric)

`megaplan bakeoff merge --exp <id>` applies:

- **Code half** (from one chosen worktree): `git diff <base-sha>..<chosen-worktree-HEAD>` piped to `git apply` in the main tree. Not `git merge` — we don't want throwaway-branch commit history. `git apply` fails loudly on conflicts with any main-tree work done in parallel, which is the right behavior.
- **Evaluation half** (from *all* worktrees): copy `.megaplan/bakeoffs/<exp-id>/<profile>/` trees back. Paths are profile-namespaced by construction — no collision.
- **Chosen plan dir**: the winning profile's `.megaplan/plans/<plan-id>/` is copied into the main tree's `.megaplan/plans/` so follow-up work can reference it. Losing profiles' plan dirs remain only in the bake-off archive, not in the live plan list.

Gotcha to solve explicitly: `state.json.config.project_dir` contains absolute paths from the worktree. The merge step either rewrites those paths to the main-tree path or marks archived plan dirs as read-only forensic data that must not be loaded by live commands.

### 6. Failure & partial success

- Each profile exits with a `DriverOutcome.status` in `{done, stalled, escalated, failed, aborted, cap, blocked, awaiting_human, tiebreaker_*}`.
- The bake-off treats anything other than `done` as a non-winner candidate but **still surfaces it to compare** — a profile stalling at gate is valuable evaluation data ("this profile can't plan this kind of idea").
- `megaplan bakeoff resume <exp-id>` checks each profile's state, relaunches auto only for profiles that haven't reached terminal, leaves winners alone.

### 7. CLI surface

```
megaplan bakeoff run --idea-file <path> --profiles A B C [--mode code] [--exp-id <name>]
megaplan bakeoff status [--exp <id>]
megaplan bakeoff tail --exp <id> [--profile X]
megaplan bakeoff compare --exp <id> [--judge <model>]
megaplan bakeoff pick --exp <id> --profile <name> [--rationale <text>]
megaplan bakeoff merge --exp <id>
megaplan bakeoff resume --exp <id>
megaplan bakeoff abandon --exp <id>
```

### 8. State

One top-level bake-off state at `.megaplan/bakeoffs/<exp-id>/bakeoff.json`:
- `experiment_id`, `base_sha`, `idea_hash`, `idea_path`
- `profiles[].{name, worktree, plan_id, pid, launched_at, outcome}`
- `chosen_profile`, `merged_at`, `phase` (running / compared / picked / merged / abandoned)

This is a thin coordination layer. The per-profile `state.json` inside each worktree remains the authoritative per-run record.

### 9. Out of scope

- LLM-judge prompt-calibration fixtures and human-calibration set (Sprint 3 or later).
- Isolated-phase replay (enabled by Sprint 1 canonical hashes, but separate UX).
- Automatic judge scheduling post-run (keep `bakeoff compare` explicit for v1 — auto-running doubles cost for rarely-queried data).

## Success criteria

1. `megaplan bakeoff run --idea-file foo.md --profiles standard all-open all-kimi` launches three concurrent autos, each in its own worktree, with independent per-profile logs.
2. `bakeoff status` shows an accurate live table while runs are in flight.
3. After all profiles reach terminal state, `bakeoff compare` produces a `comparison.json` conforming to the documented schema — with receipts-based metrics for every completed profile and graceful nulls for failed profiles.
4. `bakeoff pick` records a human selection; `bakeoff merge` applies exactly the chosen profile's diff to the main tree and copies all profiles' audit data into `.megaplan/bakeoffs/<exp-id>/`.
5. Crashing one profile mid-run does not prevent the others from completing or the comparison from running.
6. A resumed bake-off (`bakeoff resume`) does not re-run already-completed profiles.
7. Worktrees are fully removed after a successful merge; retained (with crash marker) after a crash.
