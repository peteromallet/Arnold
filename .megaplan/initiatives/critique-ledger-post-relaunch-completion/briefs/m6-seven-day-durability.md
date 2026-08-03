# F8 — Verify 24-hour, 72-hour and 7-day durability

## Outcome

Observe the accepted production generation at 24 hours, 72 hours and 7 days and
close T8.5 only if every window remains regression-free.

## Scope

T8.5 only. Use a durable recurring monitor that reads owner evidence and emits
one deduplicated incident only on a genuine decision-requiring transition.

## Locked decisions

- Real elapsed windows are mandatory; do not simulate or backdate them.
- Each observation binds installed generation, owner revisions/fences, v2 deny
  state, notification occurrence counts, storage reserves and projections.
- UNKNOWN or missing evidence keeps the task open and non-actionable effects
  no-redispatchable.

## Open questions

- None unless production ownership changes; any change invalidates the window
  and requires an owner decision.

## Constraints

No polling notification spam, inferred success from quiet logs, or manual
timestamp edits.

## Done criteria

- Signed observations at 24h, 72h and 7d bind the same accepted generation.
- No old writer/effect, duplicate incident/notification, stalled authority,
  projection disagreement, corrupt/lost evidence or reserve breach occurred.
- Independent verifier accepts the complete window and the epic emits its final
  completion manifest.

## Touchpoints

Production owner records, notification occurrence ledger, capacity/storage
telemetry, permanent replay gate and `evidence/critique-ledger-recovery/T8.5/`.

## Anti-scope

Do not introduce new product features or broaden authority during observation.
