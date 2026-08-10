# F6 — Prove production semantics, recovery and quiet UX

## Outcome

Run hostile production acceptance scenarios against the exact deployed product
and independently accept it after the declared canary window.

## Scope

Implements T7.4 and T7.5.

## Locked decisions

- Valid critics produce exact-set findings or no-findings; failed critics block
  clean critique.
- Findings and dispositions persist and replay exactly once across rounds and
  restart.
- One induced eligible failure creates one `simple_fixer` occurrence.
- Two hundred unchanged observations create no duplicate notification.
- Provider ambiguity and ENOSPC fail closed without resend or lost authority.

## Open questions

- What canary duration and traffic/sample boundary was accepted by the product
  Release Authority?

## Constraints

Use owner records and raw evidence. Status prose, process liveness and bot
messages are not acceptance evidence.

## Done criteria

- All semantic, restart, replay, reconciliation, recovery, notification,
  ambiguity and ENOSPC scenarios pass on the attested generation.
- The canary window has no old writer/effect path, duplicate incident, stalled
  authority, projection disagreement or storage reserve breach.
- Independent production verifier issues an exact accepted decision.

## Touchpoints

Production owner stores, Critique Ledger runtime, notification custody,
telemetry/projections and `evidence/critique-ledger-recovery/T7.4-T7.5/`.

## Anti-scope

Do not waive a failed scenario or infer health from silence.
