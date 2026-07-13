# M9: Chain, PR, And Cloud Boundaries

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

Boundary contracts cover chain milestones, PR-ready/merge transitions, CI/check
evidence, and cloud repair/superfixer boundaries.

The same semantic-health model catches stale or missing authority evidence in
chain/cloud workflows.

## Scope

IN:

- Add contracts for:
  - chain milestone start;
  - milestone completion;
  - PR ready;
  - PR merged;
  - chain complete;
  - cloud repair dispatch;
  - ordinary repair completion;
  - meta-repair completion;
  - 6h auditor completion.
- Add cloud custody contracts for active cloud runs, including accepted repair
  outcomes:
  - managed-running under expected tmux/supervisor/session custody;
  - complete;
  - unmanaged-running with a structured custody warning;
  - blocked with a structured relaunch failure reason;
  - escalated after repeated unchanged custody findings.
- Treat tmux/process/session evidence as resource evidence for a durable cloud
  operation boundary, not as the primary abstraction.
- Model human approval, manual override, force-proceed, blocked/unblocked, and
  resume actions as authority boundaries when they affect chain/cloud state.
- Pin evidence:
  - base/head SHA;
  - PR number/head/merge commit;
  - CI run/check ids;
  - chain state path/fingerprint;
  - repair request id/blocker id;
  - repair-data fingerprint.
  - expected session/tmux/supervisor identity;
  - live process pid/pgid/cmdline fingerprint;
  - `active_step.worker_pid` liveness and invocation/run id;
  - relaunch command/failure reason where applicable.
- Detect:
  - chain advanced without pinned evidence;
  - merged PR does not contain expected branch tip;
  - stale repair data shadowing current chain state;
  - repair record exists but has no verdict/evidence;
  - auditor record exists but gather omitted deterministic suspicious facts.
  - stale `active_step.worker_pid`;
  - live unmanaged process without expected session custody;
  - mechanical relaunch failure hidden behind generic liveness;
  - repair success that did not restore expected custody;
  - watchdog/status disagreement with custody evidence.

OUT:

- Replacing GitHub/CI providers.
- Solving all external service unreliability.

## Locked Decisions

- Chain/cloud evidence cannot rely on branch names or clean worktrees alone.
- Process liveness alone is not cloud run custody.
- Repair completion is not trusted unless it proves the original finding cleared
  or gives a structured no-fix/escalation verdict.
- Superfixer layers must preserve chain of custody upward.
- Repair completion is a boundary outcome only when it proves one of the
  accepted custody/completion/blockage/escalation states.

## Done Criteria

1. Chain milestone advancement has boundary contract evidence.
2. PR merge transition verifies merge commit contains expected tip where
   applicable.
3. Repair-loop and meta-repair records have structured verdict requirements.
4. Auditor gather detects artifact-quality gaps in repair/meta/auditor records.
5. Cloud run custody contracts distinguish managed-running, complete,
   unmanaged-running-with-warning, blocked relaunch failure, and escalated.
6. Tests cover stale PR head, stale repair-data, no-verdict repair artifacts,
   stale active-step worker PID, unmanaged live process, repair success without
   custody, and watchdog/status custody disagreement.

## Touchpoints

- `arnold_pipelines/megaplan/chain/*`
- `arnold_pipelines/megaplan/cloud/*`
- GitHub/CI evidence helpers
- repair and meta-repair wrappers
- progress auditor
- chain completion guard tests
