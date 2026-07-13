# C2: Kernel Attempt Ledger, Durable Findings, And Immediate Repair

## Outcome

The shared kernel gains the C1 execution-attempt ledger and durable payload/
reference storage contract. Boundary mismatches become durable, deduplicated
semantic evidence and can be observed immediately after a producer boundary
without creating a second authority, repair, lifecycle, or workflow runtime.

The evaluator emits WBC-owned `SemanticFinding` evidence, maps it into the
Maintenance-owned detection/occurrence and central repair-request contracts,
and lets Maintenance-owned attempts and independent verification retain
custody. Shared mutation remains default-off until negative controls and shadow
parity pass, then advances automatically only for the scope whose declared
gate matrix is green; no operator approval is requested.

## Entry Gate

C1 acceptance evidence is complete and pinned. In particular, actual producer
paths, ownership, prerequisite schema versions, compatibility fixtures, and the
canonical queue root are known. If any has drifted, return to C1.

## Mutation Class

This is the first milestone allowed to change producer completion seams,
watchdog observation, repair-request enqueue, or repair-loop context. All new
paths start in observe-only/shadow mode and remain dominated by Maintenance's
master and path-specific mutation gates.

## Scope

IN:

- Implement the append-only, schema-versioned attempt stream using Run
  Authority grant/attempt/decision identities and Maintenance transition refs.
  Enforce immutable provenance, idempotency keys, per-attempt monotonic sequence,
  causal links, durable append positions, and linked new attempts for retries.
- Implement required started/completed/failed/retry-scheduled/suspended/resumed/
  cancelled and effect-intent/effect-outcome events. Terminal events carry or
  durably reference results, verdicts, state deltas, artifacts, checkpoints,
  errors/cancellation authority, and external-effect outcomes.
- Implement `wbc.inline.v1` and `wbc.retention.v1` from the unattended-defaults
  decision. Large/sensitive data uses a
  retrievable durable object with digest and governance metadata; secret values
  are rejected. Hash-only records cannot satisfy result-preservation checks.
- Make start append durable before dispatch. Couple internal result/state/
  terminal publication transactionally or through a durable outbox/prepare-
  commit protocol. Fence external effects with a durable pre-effect intent and
  idempotency key, followed by outcome or explicit unknown.
- Make every persistence error typed and observable through APIs, logs, status
  inputs, findings, and audit. Start failures fail closed; terminal/result
  failures never return success or advance authority, and enter recoverable
  `persistence_failed`/`indeterminate` quarantine with explicit reconciliation.
- Provide authorized point and range query APIs by workflow/run/step/attempt,
  event kind, causal parent, authority decision, artifact/effect ref, and time/
  append position, with pagination and stable ordering.
- Define a serializable semantic finding payload with stable contract,
  boundary, invocation, evaluator, kind, severity, repair-domain, evidence-ref,
  and human-summary fields.
- Keep stable problem identity independent of timestamps and changing rich
  evidence; use Maintenance occurrence identity so a verified later recurrence
  can dispatch again.
- Store rich evidence by durable ref outside prompt-only fields and preserve the
  newest evidence for a coalesced signature.
- Map findings to the canonical versioned detection event and central repair
  request; do not create a WBC queue root or parallel attempt lifecycle.
- Add a scoped parent/controller post-boundary verifier that re-reads durable
  state, evaluates only the just-finished applicable boundary, and never trusts
  the producer's in-memory view.
- Make completion ordering explicit: required receipt/evidence verification
  failure cannot be silently swallowed after lifecycle advancement. Use the
  prerequisite-owned transition/CAS path for any blocked completion outcome.
- Handle atomic-write/read stability, temporary files, bounded transient JSON
  retry, fresh in-progress witnesses, current invocation identity, and abandoned
  plan suppression.
- Add narrow watchdog observation for missed immediate checks and repair-loop
  context ingestion without requiring `latest_failure`.
- Prove observe and dispatch are independent controls and all dispatch remains
  under the master mutation gate.

OUT:

- Whole-plan scans on every hot producer path.
- Hand-editing or reconciling lifecycle state in the evaluator.
- New repair attempt, verification, closure, reopen, status, or custody enums.
- Broad cloud custody, chain/PR, generic template, or non-Megaplan coverage.
- Migrating all runtime producers; C2 proves the kernel through reference/fault
  harnesses and the immediate completion seam, while C3-C6 complete adoption.

## Locked Ownership

- WBC evaluators emit findings and later prove contract satisfaction.
- Maintenance owns detection occurrence, request/claim/attempt, independent
  verification, closure/reopen, queue location, and all mutation gates.
- Run Authority decisions and views supply authority/custody evidence; a
  finding does not override them.
- Repair code cannot clear a finding by claiming success. Clearance evidence is
  produced by a fresh evaluator observation and consumed by independent
  verification.

## Compatibility Fixtures

- Legacy prep/state divergence with artifacts present, state still initialized,
  missing history, and missing/stale phase result.
- Current healthy and broken producer completions carrying prerequisite
  observation/decision identities.
- Repeated same signature with fresher evidence.
- Verified closure followed by a new occurrence.
- Fresh active work, abandoned plan, transient partial write, and disabled
  dispatch negative controls.

## Required Acceptance Evidence

1. Finding serialization and signature tests pass for both fixture generations.
2. Findings map losslessly to canonical detection/request records; newer
   evidence remains discoverable without changing stable identity.
3. Immediate verification catches a broken completion before it is reported as
   coherently complete and enqueues nothing for a healthy completion.
4. Watchdog and immediate verification dedupe through one occurrence/request
   path and cannot strand requests outside the watched queue.
5. Repair-loop context includes the structured finding without
   `latest_failure` and preserves its authority/observation refs.
6. Master gate off proves zero lifecycle, queue-claim, source, install, commit,
   or push mutation while findings remain observable.
7. Shadow parity reports denominators, false positives, suppressions, and
   unexplained differences before any dispatch flag can be enabled.
8. Golden schema/round-trip tests cover every event and payload/ref mode;
   mutation/tamper tests reject identity, provenance, ordering, or digest drift.
9. Crash/fault injection at every C1 atomicity-table point proves no execution
   without a durable start, no false success, no swallowed write failure, no
   duplicate unfenced effect, and deterministic recovery of prepared records.
10. Retention/redaction/security tests prove ACL isolation, secret rejection,
    access audit, authorized tombstoning, expired-payload behavior, and retained
    causal metadata without disclosing removed values.
11. Query tests reconstruct a complete ordered attempt trace and discover all
    referenced result data or an explicit policy-governed unavailable state.

## Automatic Failure Conditions

Fail validation and abort through `stop_chain` if implementation requires a second queue root, a second attempt/custody
lifecycle, direct plan/chain mutation, weakening a prerequisite guard, treating
incoherent observations as dispatchable, or swallowing required receipt failure
after transition. Also fail if a writer can execute before durable start, report
success after terminal persistence failure, or treat a digest as stored result
data.

Every failure emits a stable diagnostic and evidence ref; it must not suspend
for a design or rollout decision.

## Likely Touchpoints

- existing semantic-health and receipt modules
- parent/controller phase completion seam
- Maintenance detection, repair-request, feature-gate, and verification APIs
- watchdog observation and repair-loop context adapters
- focused producer, repair-request, watchdog, and negative-control tests
