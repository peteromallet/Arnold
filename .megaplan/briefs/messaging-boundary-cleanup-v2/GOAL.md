# /goal

## Rules

* Drive this **whole epic** to completion. Do not treat it as a partial implementation, exploration, or best-effort cleanup. Keep going until the epic is complete, validated, and no known blockers remain.

* Work in a **new git worktree** for this epic. Do not do this work directly in the existing checkout.

* Always use Codex subagents, via the subagent launcher, to explore and fix issues. Use them to investigate failures, inspect relevant code, repair broken behavior, update tests, validate fixes, and resolve anything blocking progress.

* Unblock and fix whatever gets in the way. If the harness, editable install, local environment, tests, scripts, chain runner, target project, docs, or supporting code are broken, inspect the failure, fix the root cause, and continue.

* Do **not** change the models used in the profiles. Preserve existing profile model selections exactly. Do not upgrade, simplify, swap, normalize, or otherwise alter model choices while completing the epic.

* Preserve the North Star anchor. Use it as durable alignment context for prep, planning, critique, execution, and review. Do not narrow milestone scope in a way that contradicts the North Star.

## Megaplan Prep Setup

Overall plan difficulty: 5/5; selected profile: `partnered-5`; because a bad plan could pass local tests while preserving a leaky user-facing/internal execution boundary.

Planning complexity: `full`; because the work crosses frontend state, browser rendering, backend/session projection, compatibility ledgers, and regression tests, but the desired architecture is now specific enough that `thorough` is not the default.

Depth: `high`; because each milestone needs substantial repository reading and structural reasoning across existing panel modules and tests.

Venue: run the epic inside a subagent and use Codex subagents aggressively for investigation and fixes. Keep the main thread for supervision and status.

## Epic Chain File

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/messaging-boundary-cleanup-v2/chain.yaml
```

## North Star Anchor

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/messaging-boundary-cleanup-v2/NORTHSTAR.md
```

## Plans Referenced Inside The Chain

### M1 - State Compartments And Selectors

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/messaging-boundary-cleanup-v2/m1-state-compartments.md
```

### M2 - Render Boundary Hardening

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/messaging-boundary-cleanup-v2/m2-render-boundary.md
```

### M3 - Rehydrate Projection

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/messaging-boundary-cleanup-v2/m3-rehydrate-projection.md
```

### M4 - Guardrails And Merge Hygiene

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/messaging-boundary-cleanup-v2/m4-guardrails-validation.md
```

## Execution

* Start from the chain file.
* Inspect the referenced milestone plans and `NORTHSTAR.md`.
* Create a new git worktree for this epic from current `origin/main`.
* Ensure the new worktree has the setup branch's `.megaplan/briefs/messaging-boundary-cleanup-v2` files available, or merge `origin/epic/fresh-cleanup-epics-setup` first.
* Launch the chain from that worktree using `--require-anchor`.
* Use `documents/megaplan` and the Megaplan skills as needed to understand how to launch, run, debug, resume, and complete the chain.
* Use the editable Arnold/Megaplan checkout first on `PYTHONPATH`:

```bash
export PYTHONPATH=/Users/peteromalley/Documents/Arnold${PYTHONPATH:+:$PYTHONPATH}
```

* Verify the launcher before start:

```bash
/Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python -m arnold_pipelines.megaplan config show
```

* Start command:

```bash
PYTHONPATH=/Users/peteromalley/Documents/megaplan \
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python -m arnold_pipelines.megaplan chain start \
  --project-dir "$PWD" \
  --require-anchor \
  --spec .megaplan/briefs/messaging-boundary-cleanup-v2/chain.yaml
```

* If anything blocks the run, inspect the relevant files, docs, logs, tests, scripts, chain state, and editable install state. Fix the root cause and continue.
* Do not stop until the epic is complete and validated.
