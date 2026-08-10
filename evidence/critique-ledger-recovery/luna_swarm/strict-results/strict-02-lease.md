Lease failure can be swallowed at the cloud launch-verification boundary:

- `_run_chain_launch_verification` treats tmux-session presence plus state/plan advancement as evidence of launch. Neither proves lease acquisition or a live, correctly identified worker.
- `_run_watchdog_tracking_verification` reports `"tracked"` from marker, workspace, and remote-spec checks בלבד; marker metadata is not lease/process liveness.
- Therefore a launcher exception, failed lease startup, stale marker, or dead process can still appear as launch success or tracked execution.

The required fail-closed boundary is immediately after lease acquisition and before any dispatch-success state, marker, or recovery transition is published. Require all of:

1. A newly issued lease ID.
2. A live process whose PID/start identity matches that lease.
3. Matching command, pinned runtime/source revision, and job/session identity.
4. Successful, parseable verification within a deadline.

Any launcher exception, lease error, timeout, unreadable result, stale marker, tmux-only signal, or identity mismatch must produce explicit `dispatch_failed` / `not_live`, and must not advance the plan.

Four acceptance tests:

1. **Swallowed launcher failure:** force lease startup to raise or return failure; assert dispatch fails explicitly and no launch-success marker/state is emitted.

2. **Marker/tmux false positive:** provide a valid marker and live tmux session but no fresh lease-bound process; assert liveness is unhealthy/not live.

3. **Identity mismatch:** launch a process with the wrong PID, command, runtime hash, revision, or session; assert verification fails closed before dispatch.

4. **Fresh success path:** issue a fresh lease and matching process identity, then assert—and only then—that dispatch is reported successful and watchdog liveness becomes healthy.

These should extend the existing liveness coverage, especially `test_host_watchdog_ensure_starts_shell_wrapped_watchdog_and_verifies_liveness`, `test_watchdog_liveness_is_scoped_to_marked_chain_spec`, and `test_watchdog_treats_supervisor_retry_before_process_liveness_as_unhealthy`.
