# Canonical Run-State Resolver

## Problem

The current superfixer stack has too many independent readers of run state.
Watchdog, cloud status, Discord summaries, repair-data, repair-loop prompts,
chain guards, and progress auditor gather code each infer their own answer from
overlapping artifacts.

That makes the system circular:

1. A nuanced execution outcome happens: budget exhausted, deferred baseline,
   stale merged PR, prerequisite-blocked task, stale needs-human marker, or a
   live worker attached after a brief manual-review gap.
2. One layer projects that nuance into a blunt terminal label such as
   `blocked`, `failed`, `manual_review`, or `no_next_step`.
3. Another layer treats that label as authoritative without re-reading fresher
   evidence.
4. Discord reports the stale/derived label, the repair-loop patches one narrow
   guard, and the same state shape reappears through another path.

The deep root is not a single prompt failure. It is a distributed state machine
with inconsistent readers.

## Goal

Introduce one authority:

```python
resolve_run_state(session: str | RunIdentity) -> CanonicalRunState
```

Every layer should consume this normalized result instead of independently
classifying raw artifacts.

## Ground-Truth Order

The resolver should read evidence in this order, because fresher operational
truth must dominate stale derived summaries:

1. Live process table and worker liveness.
2. Plan `state.json`, especially `active_step`, `latest_failure`, and
   `resume_cursor`.
3. Latest execute/finalize/review artifacts.
4. Chain state JSON.
5. Repair-data JSON and repair-loop attempt reports.
6. Watchdog marker/report.
7. External state such as PR/CI only when the plan or chain references it.

Repair-data and Discord/status output are never primary truth. They are
diagnostic context.

## Canonical States

The resolver should return a small enum, not raw plan labels:

```text
RUNNING
REPAIRING
RETRYABLE_EXECUTION_BLOCK
REAL_IMPLEMENTATION_BLOCK
HUMAN_ACTION_REQUIRED
COMPLETED
STALE_DERIVED_STATE
BROKEN_STATE_MACHINE
UNKNOWN
```

Suggested payload:

```json
{
  "canonical_state": "RETRYABLE_EXECUTION_BLOCK",
  "confidence": "high",
  "source_of_truth": ["plan_state", "execute_artifact"],
  "stale_sources": ["repair_data", "watchdog_report"],
  "human_required": false,
  "repairable": true,
  "running": false,
  "next_action": "dispatch_repair",
  "reason": "execute budget exhausted with no completed-work claim; requeue task T7",
  "evidence": [
    {
      "kind": "latest_failure",
      "path": ".megaplan/plans/<plan>/state.json",
      "summary": "execution_blocked / budget exhausted / no files modified"
    }
  ]
}
```

## Core Rules

- Live beats stale. If `active_step` is recent or the worker process is alive,
  status and Discord cannot say `needs human`.
- Evidence beats labels. `manual_review`, `blocked`, and `failed` are labels,
  not decisions.
- Human means human. Only unresolved user action records, policy approval,
  externally missing credentials/accounts/quota, or explicitly human-only
  verification should become `HUMAN_ACTION_REQUIRED`.
- Implementation blockers stay machine-actionable. Route-binding gaps, fixture
  refreshes, stale assertions, and task budget exhaustion are not human gates.
- Retry exhaustion is not the same as human need. It can mean the repair policy
  needs escalation, replan, or a stronger model.
- Repair-data is advisory and can be stale. It should not override fresher plan
  state, process liveness, or execution artifacts.
- Every terminal projection must be reversible through canonicalization before
  chain guards, watchdog dispatch, or Discord summaries act.

## Failure Shapes To Canonicalize

The initial resolver must cover the shapes seen in the July 2026 incidents:

- `manual_review` with `state=finalized` and no `latest_failure`, followed by a
  live execute worker.
- `execution_blocked` where the executor exhausted budget, modified no files,
  and explicitly asked to requeue.
- `execution_blocked` with concrete implementation prerequisites, such as
  `AWF018_ROUTE_METADATA_MISMATCH` from missing route bindings.
- `failed/no_next_step` after a blocked execute where authority artifacts show
  all real work complete and only a deferred baseline/checkpoint remains.
- Merged PR plus stale failed plan state where the chain guard refuses to
  advance despite terminal-success evidence.
- Stale `needs-human` marker or repair-data outcome after the plan has recovered
  or advanced.
- Live initialized plan whose `active_step` is present while chain status still
  says initialized/unknown.
- Cloud-worker task that tries impossible SSH back into the host despite local
  container evidence being available.

## Integration Points

All of these should call the resolver or consume its persisted output:

- `arnold_pipelines.megaplan.cloud.status_snapshot`
- `arnold_pipelines.megaplan.cloud.status_format`
- Discord bot status/follow-up summarization path
- `arnold-watchdog`
- `arnold-repair-loop`
- repair dispatch classifier
- needs-human classifier and marker lifecycle
- `arnold_pipelines.megaplan.auto`
- chain completion/progression guards in `arnold_pipelines.megaplan.chain`
- progress auditor gather stage
- meta-repair gather stage

The resolver should be pure and fixture-testable. Deployment code can then
persist its output into status snapshots, repair-data, and Discord responses.

## Design Shape

Create a small module, likely:

```text
arnold_pipelines/megaplan/run_state/
  __init__.py
  model.py
  resolver.py
  evidence.py
  classifiers.py
```

`evidence.py` gathers and timestamps raw facts. `classifiers.py` contains the
ordered rules. `resolver.py` produces the canonical answer and records which raw
sources were stale or contradictory.

The first implementation should be conservative: centralize the known rules and
replace the most dangerous call sites first, rather than rewriting the whole
cloud stack.

## Migration Plan

1. Build the resolver behind tests using fixture snapshots from the incidents.
2. Wire Discord/status to display canonical state and stale-source warnings.
3. Wire watchdog to suppress needs-human if canonical state is running,
   repairing, retryable, or real implementation block.
4. Wire repair-loop prompt generation to include canonical state, stale sources,
   and exact next action.
5. Wire chain guards to canonicalize terminal-looking states before refusing to
   advance.
6. Wire progress auditor gather to include the canonical output and assert that
   stale/contradictory state is surfaced as a deterministic reason.

## Regression Fixtures Required

Each fixture should contain only enough files to reproduce the classification:

- agent-ui recovered-to-finalized plus live execute worker.
- agent-ui budget-exhausted T7 with no files modified.
- megaplan-native AWF018 route-binding implementation block.
- progress-auditor failed/no_next_step plus deferred baseline.
- progress-auditor merged PR plus stale failed state.
- stale needs-human marker after recovered plan.
- initialized plan with live active_step.
- cloud-worker impossible SSH prerequisite.

## Non-Goals

- Do not make status optimistic. If implementation is really blocked, say so.
- Do not hide human gates. Make them rarer and more precise.
- Do not let the resolver mutate plan state directly. It decides; handlers act.
- Do not touch profile routing as part of this fix.

## Success Criteria

- Discord and CLI status cannot report `needs human` while the resolver sees a
  recent live worker.
- Repair-loop cannot count a generic engine patch as success when the canonical
  state says target implementation remains unattempted.
- Watchdog cannot preserve a stale needs-human marker when fresh state is
  retryable or running.
- Chain guards cannot reject `failed/no_next_step` before checking execute
  authority and merged PR evidence.
- Progress auditor reports contradictory/stale state as a deterministic gather
  reason.
- All known July 2026 incident shapes have fixture tests.
