# M5 - Worker Fleet Supervision And Cancellation

## Objective

Run many projects safely by adding leases, heartbeats, progress supervision,
concurrency gates, cancellation, poison-project quarantine, and staggered
restart. The system should distinguish dead, idle, healthy, and stuck-but-alive
runs.

## Files To Change And Instructions

- Worker/supervisor modules
  Add project leasing with atomic claim, `owner_id`, `lease_expires_at`,
  `last_heartbeat`, and status fields.
- Native runtime
  Honor the cancellation hook point between steps and child workflow boundaries.
- Trace/audit query layer
  Expose progress signals: current path, stage/path advancement, token or cost
  deltas where available, and last meaningful event.
- Scheduler/concurrency layer
  Gate concurrent heavy work such as test runs and provider calls.
- Restart logic
  Add poison-project circuit breaker, stuck-run escalation, and staggered
  restart behavior.
- Tests
  Cover lease claim, expired lease takeover, double-run prevention,
  graceful cancel, hard cancel recovery, stuck-loop signal, poison quarantine,
  and staggered restart ordering.

## Verifiable Completion Criterion

- Two workers cannot own the same project/worktree simultaneously under normal
  lease rules.
- A project with an expired lease can be safely claimed by another worker after
  reconcile-on-resume.
- Graceful cancellation stops at a step boundary, releases ownership, and
  records status.
- Stuck-but-alive runs can be detected from progress signals.
- A simulated stuck-but-alive run triggers the configured escalation path:
  warn/notify, checkpoint restart where safe, or cancel and flag for human
  review.
- Concurrency gates prevent configured heavy operations from exceeding capacity
  and record the reason work was delayed.
- Crash-looping projects are quarantined instead of restarted forever.

## Risks And Blockers

- Worktree ownership and reconcile from M1 are prerequisites; without them,
  lease takeover is unsafe.
- Progress signals should be rate-based, not only total token/stage counts.
- Cancellation must not corrupt in-flight side effects.

## Dependencies

- Depends on M4.
