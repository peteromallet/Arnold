# T1.10 implementation brief — quiet, durable incident notification UX

You are the implementation owner for task T1.10 in the Critique Ledger recovery.
Use GPT-5.6 Luna judgment. Work only in:

`/private/tmp/arnold-critique-recovery-notification-ux-20260802`

Do not mutate any cloud machine, external service, Discord, or the user's dirty main checkout.
Do not merge or push. You may commit your isolated branch when complete.

## Required outcome

Repair the incident/diagnostic/notification control flow at its root so that repeated
observation cannot create repeated external notifications. Implement production-grade
code and adversarial tests, not a narrow mock.

The known deterministic loop is:

1. watchdog observes the same `manual_review/gated` state;
2. it unconditionally appends `opened`;
3. diagnostic launch resolves resident provenance before durable identity/state;
4. missing provenance raises `DelegationProvenanceError`;
5. handler returns blank escalation/state coordinates and requests fallback delivery;
6. fallback Discord send succeeds but cannot be durably reconciled;
7. next tick repeats.

Relevant starting points include:

- `arnold_pipelines/megaplan/cloud/human_review_diagnostic.py`
- `arnold_pipelines/megaplan/cloud/human_blockers.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
- notification/WBC outbox/custody modules and their tests

## Binding acceptance requirements

1. Create a stable incident occurrence and diagnostic-attempt identity/state before
   resident-provenance validation. Missing provenance must be one durable terminal
   diagnostic result; blank IDs/paths are illegal.
2. Repeated observation is idempotent. `opened` or equivalent is a transition, not an
   unconditional append.
3. Observer/watchdog code may observe and enqueue; it must not directly call Discord or
   any provider, including a fallback path.
4. Every notification effect is admitted through the repository's canonical durable
   WBC/outbox custody. It has a stable identity derived from the incident occurrence,
   state version, recipient, notification kind, and payload digest/child chunk identity.
5. Atomically persist the meaningful incident transition and its notification intent, or
   fail closed before any provider call. No synthetic/shadow/local authorization in a
   production path.
6. Provider ambiguity is `INDETERMINATE` and prohibits blind redispatch. Persist attempts
   and provider receipts. Do not convert unknown application into ordinary failure.
7. Produce one machine-readable current incident-card projection containing at least:
   state, owner, last accepted transition, diagnostic/fixer result, ambiguity, storage
   health, runtime generation, next action, acknowledgement/resolution authority state.
8. Acknowledge/resolve are authority-backed transitions, not UI booleans.
9. Replace unsafe whole-file JSONL rewrite/length sequencing for the authority path with
   a process-safe durable mechanism or use the existing accepted canonical journal/WBC
   primitives. Preserve compatibility only where it does not preserve the bug.
10. Tests must prove two concurrent observers plus 200 identical scans produce at most one
    accepted notification outcome and one stable occurrence. Include provenance failure,
    process/thread concurrency, crash boundaries, and ENOSPC/persistence refusal before
    effect dispatch. Prove no provider call on failed durable intent.
11. Existing relevant tests must pass. Add installed-entrypoint/runtime-surface tests if
    this changes shipped behavior.
12. CLI/process errors must be traceback-free machine-readable failures where applicable.

## Engineering posture

- Inspect current code and loose fixes, but do not assume any historical commit is sound.
- Prefer a small coherent state machine over scattered dedupe flags.
- Do not claim this task complete merely because notifications are muted. The durable
  transition/effect relationship and useful operator projection are required.
- Do not alter unrelated files.
- Run targeted tests and a proportionate broader regression suite.
- Record exact commands/results and unresolved concerns in your final response.
- Commit only after tests pass, with an intentional message.

Before finishing, inspect your own diff adversarially for direct provider calls, blank
identity fallbacks, read-before-write races, replay after crash, duplicate effects across
processes, and false-success outcomes.
