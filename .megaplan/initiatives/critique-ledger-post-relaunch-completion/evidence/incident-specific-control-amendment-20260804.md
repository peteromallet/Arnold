# Incident-specific control amendment — 2026-08-04

Amendment ID: `incident-specific-control-amendment.v1`

This amendment turns the relaunch incident into explicit, auditable follow-up
acceptance criteria. It is a post-canary hardening obligation: it must not be
used to weaken the bounded v3 canary or to manufacture a T6.2 acceptance.

## Required controls

1. **P1 entry-point containment.** Cloud `exec`, force-proceed, unsafe
   adopt-execution, bootstrap, epic-chain refresh, and AgentBox replay must
   all pass the same admission boundary. Direct invocation is denied by
   default; any break-glass path is bounded, occurrence-bound, and durably
   audited. No entry point may create an alternate launch or effect authority.

2. **One non-bearer admission receipt.** A launch, resume, override, or adoption
   receives one content-addressed reference to the canonical action envelope.
   Every action rereads the current Run Authority grant/fence and Custody
   lease/epoch, then checks the exact WBC boundary evidence. The receipt binds
   attempt, occurrence, generation, source, runtime, lease and effect scope but
   cannot grant authority by itself. A second authority ledger is forbidden.

3. **Occurrence/generation recovery.** Every failure, receipt, phase result,
   recovery mutation, lease, and notification carries the exact occurrence,
   attempt, fingerprint, and generation. Stale or replayed evidence is
   rejected before mutation, including after restart, rollback, deletion, or
   process replacement.

4. **Provider-route and credential attestation.** Orchestration, task, and validation
   providers resolve through one role-scoped resolver, with authentication and
   capability preflight before lease acquisition and again on resume. Every
   resident, repair, sidecar, and replay process uses the same host-managed
   credential bootstrap; missing credentials fail closed and emit one
   deduplicated incident. The accepted profile bytes and resolved model map
   are attested, so a stale overlay cannot silently route a phase elsewhere.
   These facts are admission evidence; they never mint positive authority.

5. **Runtime command integrity.** Generated cloud commands must use the
   configured pinned `runtime_python` for every Python/pip operation. Bare
   interpreter or mutating editable-install fallbacks are forbidden in a
   relaunch path. Installed source, revision, worktree, interpreter, and test
   identity must be attested before mutation.

6. **Snapshot-first observation and notification custody.** Status reads use a
   durable snapshot first, then a bounded live fallback correlated to the same
   attempt/generation. Projection cursor mismatch, corruption, or storage
   failure is visible and fail-closed rather than reported as healthy. Incident
   and notification effects are durably deduplicated by occurrence/version;
   unchanged polling cannot resend the same message.

7. **Legacy-session classification and takeover.** A legacy or ambiguous
   session is classified as stale/unknown and fenced before any resume or
   notification. Takeover is human-gated, exact-occurrence-bound, and requires
   fresh source/runtime/profile/lease attestation. No diagnostic, Kimi, meta,
   watchdog, or fallback launcher may be revived implicitly.

## Acceptance evidence

The implementation is accepted only with source, installed-runtime,
crash/restart, hostile-replay, and exact-receipt evidence covering every
control above. The evidence must name the one authoritative writer for each
execution/effect state and prove that all other entry points are denied or
audited break-glass paths.
