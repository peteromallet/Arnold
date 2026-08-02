# F7 — Freeze evidence and close the incident responsibly

## Outcome

Complete deferred administrative/evidence obligations, generate the final
successor proof, resolve the v2 incident without rewriting history, and publish
the permanent replay gate and operator UX.

## Scope

Completes the ticket-closing subeffect of T3.6, T4.6, and T8.1–T8.4.

## Locked decisions

- The launch-critical T3.6 release receipt is a future prerequisite bound by the
  independently accepted T6.2 handoff; it does not exist at epic-authoring time.
  Close its two tickets only after re-deriving their production obligations
  from frozen owner evidence.
- Preserve v2 as immutable evidence; never mark it completed.
- The final successor manifest hashes explicit proof-map artifacts.
- The incident replay remains a permanent release gate.
- Operator UX is one card and one genuine-decision notification with visible
  indeterminacy, named owner and precise next action.

## Open questions

- Which archival/WORM mechanism is accepted for the exact v2 evidence tuple?

## Constraints

Archival cannot alter authority, clear ambiguity, invent completion or delete
evidence. Documentation cannot substitute for executable gates.

## Done criteria

- Both release tickets are closed from exact accepted evidence.
- Old workspace/branch/worktree/plan/artifacts are read-only and hash-attested.
- Final v3/product completion manifest and proof map reproduce.
- Incident is resolved only after production acceptance, with v2 immutable.
- Permanent replay test and operator incident card/notification policy ship.

## Touchpoints

Release tickets, v2 archives, completion manifest/proof map, release gates,
runbooks and `evidence/critique-ledger-recovery/T4.6,T8.1-T8.4/`.

## Anti-scope

Do not claim the 7-day durability window in this milestone.
