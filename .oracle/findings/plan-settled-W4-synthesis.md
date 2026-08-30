# Settled-plan sense-check W4 synthesis

- Immutable plan: `19d37c43207e116877ba0f3b5391fdfd1cf55f8cffda3d11e9869feb8ba734db`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Reviewers: three independent GPT-5.6 Luna normal-task critics
- Result: **material but bounded correction required; STILL_FORMING**
- No new exploration, store, service, or `[XHARD]` task is justified.

## Accepted findings

1. **Derived child receipt identity (SIMP4-1).** Remove the circular
   `child_admission_receipt_id` input from the composite event. Derive the
   receipt ID deterministically from committed composite event ID + child identity;
   replay must reproduce it byte-for-byte.

2. **Truthful no-launch outcome (SIMP4-2 / CONTRACT4-1 / SEQ4-1).** Add a distinct
   typed `no_launch` outcome with `launch_state=not_started`. It may cross
   PhaseResult but creates no worker terminal event/fingerprint and no breaker
   accounting. The controlled adapter persists explicit not-started/entered
   sequencing around every launch-capable operation. Missing or contradictory
   evidence is `unresolved_launch`, never released. Reconciliation precedes
   consumer projection; test identical redispatch and restart.

3. **Close no-WBC production bypass (CONTRACT4-2).** Every production
   `run_step_with_worker` call enters `dispatch_with_admission`; construct the
   WBC adapter internally or reject `wbc_dispatch=None` under production intent.
   Add a negative structural scenario.

4. **Canonical terminal outcome event (CONTRACT4-3).** Freeze one strict event for
   every non-scheduling terminal result after launch acceptance, containing the
   semantic fingerprint and disposition/context links. Projection and redispatch
   CAS consume it before reservation closure. Provider exhaustion remains typed
   input to the T8 scheduler and must not be double-recorded as an ordinary failure.

5. **Canonical changed-precondition producers (CONTRACT4-4).** Reason-specific
   producers derive content identities from authoritative state/evidence. CAS
   validates evidence-to-identity binding and atomically consumes the event. Reject
   caller-forged unequal IDs.

6. **T8 dependency barrier (SEQ4-2).** NBF-06 depends on NBF-01 through NBF-05.
   Batch ordering alone is not the contract; T8 starts only after shared
   disposition/signal interfaces and their gates pass.

7. **Durable two-scan confirmation schema (SEQ4-3).** Freeze the confirmation
   record key, owner, atomic replacement, TTL, expiry, restart, and reset rules
   over victim PID + process-start + progress + watchdog/container incarnation.
   Test restart, PID reuse, progress advance, and incarnation change.

8. **Targeted authority-bypass checker (SEQ4-4).** Add a small AST/static checker
   covering forbidden authority calls and launch construction across three doors
   plus chain origins. Run it in NBF-03 and NBF-07; keep the existing grep only as
   a readable secondary check.

## Oracle constraints on the revision

- Keep one composite event, not a prepare/commit protocol.
- Keep one canonical terminal-outcome writer and one signal helper.
- Do not turn no-launch into worker death or provider failure.
- Do not add another scheduler, journal, store, or route controller.
- Preserve all-normal/Luna classifications; no finding meets `[XHARD]`.
- Apply corrections to design, ownership, dependencies, focused tests, and final
  matrix. A fresh complete Luna wave remains mandatory.
