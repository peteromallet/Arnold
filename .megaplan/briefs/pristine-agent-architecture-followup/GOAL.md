# /goal

## Rules

* Drive this **whole epic** to completion. Do not treat it as a partial implementation, exploration, or best-effort cleanup. Keep going until the epic is complete, validated, and no known blockers remain.

* Work in a **new git worktree** for this epic. Do not do this work directly in the existing checkout.

* Always use Codex subagents, via the subagent launcher, to explore and fix issues. Use them to investigate failures, inspect relevant code, repair broken behavior, update tests, validate fixes, and resolve anything blocking progress.

* Unblock and fix whatever gets in the way. If the harness, editable install, local environment, tests, scripts, chain runner, target project, docs, or supporting code are broken, inspect the failure, fix the root cause, and continue.

* Do **not** change the models used in the profiles. Preserve existing profile model selections exactly. Do not upgrade, simplify, swap, normalize, or otherwise alter model choices while completing the epic.

* Preserve the North Star anchor. Use it as durable alignment context for prep, planning, critique, execution, and review. Do not narrow milestone scope in a way that contradicts the North Star.

## Epic Chain File

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/pristine-agent-architecture-followup/chain.yaml
```

## North Star Anchor

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/pristine-agent-architecture-followup/NORTHSTAR.md
```

## Plans Referenced Inside The Chain

### M1 - Main Preservation Audit

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/pristine-agent-architecture-followup/m1-main-preservation-audit.md
```

### M2 - Contract Guardrail Tightening

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/pristine-agent-architecture-followup/m2-contract-guardrail-tightening.md
```

### M3 - Non-Messaging Boundary Hardening

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/pristine-agent-architecture-followup/m3-non-messaging-boundary-hardening.md
```

### M4 - Doc Artifact Ledger Finalization

```text
/Users/peteromalley/Documents/.megaplan-worktrees/fresh-cleanup-epics-setup/.megaplan/briefs/pristine-agent-architecture-followup/m4-doc-artifact-ledger-finalization.md
```

## Execution

* Start from the chain file.
* Inspect the referenced milestone plans and `NORTHSTAR.md`.
* Create a new git worktree for this epic from current `origin/main`.
* Ensure the new worktree has the setup branch's `.megaplan/briefs/pristine-agent-architecture-followup` files available, or merge `origin/epic/fresh-cleanup-epics-setup` first.
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
PYTHONPATH=/Users/peteromalley/Documents/Arnold \
  /Users/peteromalley/Documents/reigh-workspace/vibecomfy/.venv/bin/python -m arnold_pipelines.megaplan chain start \
  --project-dir "$PWD" \
  --require-anchor \
  --spec .megaplan/briefs/pristine-agent-architecture-followup/chain.yaml
```

* If anything blocks the run, inspect the relevant files, docs, logs, tests, scripts, chain state, and editable install state. Fix the root cause and continue.
* Do not stop until the epic is complete and validated.
