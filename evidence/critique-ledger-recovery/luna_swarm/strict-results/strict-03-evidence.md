Authoritative ordering contract:

1. Preserve T1–T3/T6 evidence and create an immutable repair identity tied to the VJ8 occurrence, fingerprint, repair revision, and pinned runtime import.
2. Complete the idempotency/outbox contract: identical canonical content deduplicates; divergent same-key content raises `IdempotencyConflictError`; declare the outbox write set and resolve the public helper export.
3. Run one clean ledger + outbox + static-negative suite, including VJ8.
4. Make recovery occurrence-bound: newest `latest_failure` and fingerprint win; stale `phase_result.json` cannot reclassify VJ8 as an external error.
5. Resolve U1 and quality blockers with authoritative evidence—never fabricate resolutions.
6. Acquire a fresh marker-bound fenced lease for the exact PID/start identity/container, then invoke occurrence-scoped `recover-blocked` and resume execute. No force-proceed or blind relaunch.

Remaining stale-evidence gap:

`override.py` still lets stale `phase_result.exit_kind == "external_error"` trigger generic `resume`, even when `state.json.latest_failure` is the newer deterministic VJ8 validation block. Status projection is newer/safer because it checks `latest_failure`, but recovery itself remains vulnerable. Terminal states also need to quarantine stale in-flight LLM telemetry and label stale observer snapshots.

Acceptance tests:

1. Append the same idempotency key with identical canonical content: return the existing event and persist one row. Append the same key with divergent content: raise `IdempotencyConflictError` and persist no duplicate.

2. Run the ledger, outbox, and static-negative suites together under the pinned runtime; require zero failures, successful outbox behavior, declared outbox writes, and the intended public canonicalization export.

3. Construct a newer `pre_dispatch_validation_failed` VJ8 `latest_failure` plus an older external-error `phase_result.json`; require recovery to select VJ8, reject stale evidence, and require matching occurrence/fingerprint/repair identity.

4. Simulate lease acquisition failure and stale ownership; require no `executing` projection, state mutation, or worker dispatch. Require takeover only through fenced CAS, and require valid lease identity before execution.
