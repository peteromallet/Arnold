# M4: Cloud Supervisor And Docs

## Outcome

Make cloud chain supervision first-class: a supervisor can observe a chain, make safe progress decisions, and report what happened without hand-reading process lists, logs, and plan state.

## Scope

IN: a `cloud supervise --chain` command shape, one-shot/tick behavior, canonical runner/log/session naming, stale runner detection, branch/PR sync before policy decisions, status/tick report artifacts, and operator docs/runbook updates.

OUT: provider-specific watchdog slot allocation and multi-repo worker path hardening.

## Locked Decisions

The supervisor may restart missing runners and surface recoverable blockers, but it must not invent human approvals or force destructive git operations. Branch/PR synchronization is an operational state that must be refreshed before applying review policy.

## Done Criteria

Supervisor status explains runner liveness, current milestone/plan state, last log activity, sync state, next action, and any conservative reason it refused to act. Docs describe how to run, inspect, and stop it.
