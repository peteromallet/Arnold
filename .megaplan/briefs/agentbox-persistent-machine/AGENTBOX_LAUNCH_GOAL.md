/goal

Wait for python-shaped workflow-authoring M3, then launch and drive the **whole AgentBox epic** to completion.

Be aggressive about forward progress: unblock root causes, fix the harness when it breaks, deploy Codex subagents freely, and do not stop at status-reporting. Every check-in should either wait on the M3 gate, launch the chain, move the epic forward, or fix the thing preventing progress.

Set a scheduled check-in every **5 minutes**. On each fire, run:

```bash
cd /Users/peteromalley/Documents/megaplan
.megaplan/briefs/agentbox-persistent-machine/launch-after-python-shaped-m3.sh
```

If the launcher refuses because PR #98 is not ready, record the reason and re-arm the 5-minute check-in. Do **not** launch AgentBox manually.

The launcher may start AgentBox only when PR #98 is merged, non-draft, based on `python-shaped-workflow-authoring-cleanup`, and contained in `origin/python-shaped-workflow-authoring-cleanup`.

Once the launcher starts the chain, stop the wait loop and actively babysit the AgentBox epic until every milestone is complete.

## Critical constraints

Work in a **new git worktree**. Do not implement directly in the existing checkout.

Do **not** change profile model selections.

Do **not** make AgentBox depend on python-shaped workflow internals, generated DSL internals, M4 authored-workflow migration surfaces, or Megaplan planning topology files.

Unblock root causes. If the blocker is in Megaplan/Arnold machinery or the editable install, fix it with tests and continue. Use Codex subagents where useful.

## Chain

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/chain.yaml
```

Base branch:

```text
python-shaped-workflow-authoring-cleanup
```

Source plan:

```text
/Users/peteromalley/Documents/megaplan/docs/agentbox-persistent-machine-plan.md
```

## Milestones

### M1 — Arnold Runtime Core

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m1-arnold-runtime-core.md
```

### M2 — AgentBox Host Provider

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m2-agentbox-host-provider.md
```

### M3 — Megaplan Chain Adapter

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m3-megaplan-chain-adapter.md
```

### M4 — Discord Thin Path

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m4-discord-thin-path.md
```

### M5 — Guardian V0

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m5-guardian-v0.md
```

### M6 — Credentials Preflight

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m6-credentials-preflight.md
```

### M7 — Completion, GitHub, And Cleanup

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m7-completion-github-cleanup.md
```

### M8 — Bootstrap And Day-2 Operations

```text
/Users/peteromalley/Documents/megaplan/.megaplan/briefs/agentbox-persistent-machine/m8-bootstrap-day2.md
```

## Completion standard

Start from the chain file, inspect the milestone briefs, create the worktree, wait for the M3 gate, launch through the wrapper, then drive the full sequence to completion.

If anything blocks the run, inspect docs, logs, chain state, plan state, PR state, GitHub checks, and editable install state. Fix the root cause and continue.

When AgentBox starts, capture the post-M3 base SHA from chain state. Stop only when every AgentBox milestone is complete and verified.
