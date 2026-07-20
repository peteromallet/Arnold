# Implementation brief: durable repair-goal owner handoff

Work only in `/workspace/arnold-superfixer-owner-handoff-20260715`, branch
`fix/superfixer-owner-handoff-20260715`, based at
`ce409346426f774b7c2a579d20cdbf05ddbabb86`. Do not edit either launch checkout,
integrate, push, deploy, restart, or touch live session state. Use `apply_patch`
for edits. Run focused tests and leave the worktree clean only if you commit;
otherwise leave a reviewable diff. The root agent owns final review, commit, and
integration.

## Root cause to fix

The active repair goal `repair-goal-570fda35570797c632f75703` survived, but its
process owners did not. `managed_agent.run_managed_command` only treats an
active goal as incomplete when a worker exits 0; a nonzero child terminalizes
without an atomic durable ownership handoff. Resident Codex supervisor
`resident/subagent.py::_run_codex_manifest` has no repair-goal lifecycle check.
The prior runner-enforced resident owner created/reused the repair goal from
inside its session, but the goal was never linked back into the resident
manifest, so the Git-custody rejection correctly failed the resident run while
leaving the active goal with only terminal automatic owners. The watchdog/L3
could rediscover this later, but not atomically at terminalization.

Separately, watchdog `check_meta_repair_recursion_guard` calls
`check_meta_repair_recursion` without the blocker ID, even though the policy and
meta-repair wrapper support blocker scoping. It also reads blocker ID only after
the pre-dispatch check. `meta_repair_policy` scans `meta_repair_verdict.json` as
if it were another attempt, inflating the three-record decision. Recursion is a
safety gate and must remain; scope/count it correctly and preserve concrete
handoff/escalation evidence.

L3 already gathers a linked repair goal and emits `repair_goal_owner_missing`
when the goal is active and no owner is live (`arnold-progress-auditor` around
lines 1340-1450). Preserve and test this; do not claim it is structurally blind.

## Required behavior

Implement the narrowest coherent lifecycle contract so a runner-enforced
repair goal cannot become unowned merely because:

1. an automatic repair child exhausts or exits nonzero;
2. meta-repair recursion protection fires; or
3. resident Git-custody rejects an otherwise-zero worker completion.

The durable goal must retain or atomically transfer custody to a durable
reassignment/backstop state with concrete failed-probe evidence. It must remain
active until authoritative success, an actual approval/authorization gate, or
an explicitly bounded terminal-exhaustion contract. Do not weaken checkpoint,
runner-liveness, beyond-review, fresh-progress, bounded-followup, or Git gates.

Preferred shape (adapt if a smaller existing seam is stronger):

- Extend repair-goal state with an explicit durable custody/handoff projection.
  Attaching an owner marks owned custody. Recording terminal owner failure marks
  a watchdog/backstop-owned `reassignment_pending`/equivalent state, including
  predecessor, reason, phase, and last failed probe. This is not semantic
  completion and must remain dispatchable.
- At managed-agent terminalization, if a linked goal is active, record that
  terminal failure/handoff for both zero and nonzero child exits (excluding
  internal `automatic_repair_retry` children where the enclosing L1 owner still
  owns custody). Keep existing return-code semantics.
- Give resident-managed runner owners a reliable binding seam. A goal created
  or reused from inside a resident session must be able to link itself to the
  resident manifest before the resident exits. Prefer automatic environment
  provenance plus a repair-goal bind helper invoked by the canonical repair
  trigger/goal creation seam, not prompt parsing. The resident supervisor must
  then record an active-goal terminal handoff when Git custody rejects or the
  worker otherwise terminalizes before semantic success.
- Pass the current blocker ID into the watchdog pre-dispatch recursion guard,
  reading it before the check. Do not count `meta_repair_verdict.json` as an
  attempt. If recursion genuinely fires, retain concrete durable escalation or
  reassignment evidence and allow the existing bounded L1 fallback / human
  backstop contract.
- Preserve L3 owner-missing detection and add an explicit regression showing it
  catches an active goal whose last owner terminalized via recursion/Git/child
  failure handoff.

Avoid schema churn beyond additive fields. Reuse locking and atomic writers.
Be careful not to make a virtual custodian look like a live mutating process in
`repair_goal_watchdog_status`; pending handoff must trigger reassignment rather
than suppress it.

## Evidence and tests

Add regressions spanning the three failure classes above. Relevant suites:

- `tests/cloud/test_repair_goal.py`
- `tests/test_managed_agent.py`
- `tests/resident/test_launch_subagent.py`
- `tests/cloud/test_watchdog_wrappers.py`
- `tests/cloud/test_progress_auditor.py`
- meta-repair policy tests

Run focused tests for changed modules and at least the relevant watchdog and
repair-loop test selections. Review `git diff --check` and summarize exact
files, behavior, tests, and any unresolved concern. Do not modify acceptance
fixtures merely to make them green.
