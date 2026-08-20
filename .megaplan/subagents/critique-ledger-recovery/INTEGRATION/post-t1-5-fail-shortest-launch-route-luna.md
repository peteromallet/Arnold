# Post-T1.5-fail shortest safe Critique Ledger v3 launch route — Luna

Date: 2026-08-02  
Posture: read-only route adjudication; no cloud/provider/source/Git/owner mutation

## Verdict

**T1.5's production-grade external monotonic exactly-once anchor is not a
prelaunch dependency for a supervised finite canary only if fixer and
notification are removed from the canary's executable capability graph.**

The current T1.5 candidate remains HARD FAIL and must not be integrated,
described as accepted, or used as a production recovery owner. Its defect is
deletion/rollback resistance, not HMAC forgery resistance: present receipts are
cryptographically bound, but erasing all mutable attempt/claim/effect
projections permits another attempt and effect.

That defect has no canary consumer if the canary has:

- `fixer=0` and `notification=0` in the owner-signed effect budget;
- no recovery/notification child GLEKs or provider credentials;
- no repair, watchdog, diagnostic, notification worker, direct Discord, or
  exception-fallback process/entrypoint;
- a finite-runner failure branch that durably fences/stops through T1.9 and
  makes zero T1.5/T1.10 calls; and
- a manual observer that is read-only and cannot relaunch.

Under that exact profile, the T1.5 anchor moves to the post-canary follow-up
epic and becomes mandatory before any automatic fixer or notification effect,
ordinary execution, or publication authority is enabled.

**Cloud mutation is still NO-GO now.** The supported current status path is
blocked by a present but non-exec-able container, T1.9 is still a specification
rather than installed code, no clean integrated/package candidate exists, and
the old v2 effect fence and fresh v3 launch envelope do not exist.

## Controlling evidence

- T1.9 finite launcher specification:
  `T1.9/t1-9-stage-a-implementation-delta-v2-sol.md`, SHA-256
  `9a604b05637d2f9eba54db6a6f42e488e2d2979105a6b0d1d6dcb5665688ad11`.
- Independent T1.9 specification PASS:
  `T1.9/t1-9-stage-a-independent-review-v2-luna.md`, SHA-256
  `c3378830a6866ebaedb618a0a466bd6198900f7c74523596f925a25e60c39669`.
- Current-cloud ledger:
  `INCIDENT/current-cloud-ledger-luna.md`, SHA-256
  `a66791f36217afa0360d879e988f8feda6f879e618a46569380a22664f00915d`.
- Provider blocker diagnosis:
  `INCIDENT/cloud-observation-provider-failure-sol.md`, SHA-256
  `1ba237da632e0c909337b6a58edfe249441d6396d020682e7b02f45d4081ebd4`.
- Follow-up epic README:
  `.megaplan/initiatives/critique-ledger-post-relaunch-completion/README.md`,
  SHA-256
  `3fca0c72a00764600316f3e3a9aef9b735d1514f3a6dd4f5f574fca6f179e7f0`.
- Exact quiet-path implementation map:
  `T1.4/incident-stall-notify-exact-implementation-map-luna.md`, SHA-256
  `fd83c969cd8c2ffa45819aa5d23d098974bbd2aab2b37259f48f919beada1213`.
- T1.5 pass-3 independent HARD FAIL:
  `T1.5/t1-5-operational-pass3-independent-review-luna.md`.

The current ledger says live cursor/process truth is UNKNOWN because supported
status cannot enter the container. Historical evidence shows the v2 chain
stalled at `gated/finalize/manual_review`, no durable diagnostic launch, and a
missing `resident_delegation` envelope followed by an uncustodied fallback that
produced 201 delivered Discord DMs. The provider diagnosis narrows the current
container to present but non-running/non-exec-able and requires a supported
host-side inspection path before deployment.

## Why this deferral is sound—and where it stops

### HMAC forgery resistance already passes

With attempt/claim/effect rows present, T1.5 verifies keyed effect and result
receipts across fresh processes; wrong keys, cross-occurrence transplants,
coordinated forged success, and individual proof deletion/corruption fail
closed. This is useful follow-up substrate.

### Deletion/rollback resistance fails

The HMAC key cannot prove that a deleted row once existed. T1.5 has no external
monotonic occurrence-scoped consumed-attempt record. Coordinated projection
erasure therefore recreates apparent virgin state and permits another effect.
This remains a hard blocker for every enabled fixer effect.

### Zero capability removes the vulnerable consumer

An unavailable effect cannot be duplicated. The safe recut is not “trust the
broken fixer because a human is watching”; it is “the installed canary cannot
name, reserve, start, or call a fixer/notification effect at all.” Failure is a
T1.9 launch outcome followed by denial and stop, not a recovery occurrence.

This deferral does **not** apply to exercised upload/start/model/stop effects.
T1.9 and the narrow WBC dispatcher must still provide deletion/rollback-safe,
exact operation receipts and never redispatch a `STARTED` child. Manual
supervision is not an exactly-once mechanism.

## Required bounded change to the T1.9 profile

The accepted v2 specification currently budgets `fixer<=1` and
`notification-initial<=1`, requires a T1.5/T1.10 failure canary in the
`StageAProductionGoManifest`, and lets an eligible finite-runner failure report
through T1.5. A bounded implementation profile must explicitly replace those
positive capabilities; silently omitting their receipts would violate the
specification.

For `operational_canary_zero_recovery_v1`:

1. `BuildInterfaceManifest` records T1.5 and T1.10 as
   `NOT_CONSUMED_OPERATIONAL_CANARY`, not accepted dependencies.
2. `StageAProductionGoManifest` carries owner-signed deny receipts and exact
   zero budgets for `fixer`, `notification`, reminder, chunk, diagnostic,
   resident child, watchdog repair, and every direct-provider fallback.
3. No parent/child GLEK is derivable for those families. Capability lookup
   returns typed `UNAVAILABLE_IN_GENERATION` before filesystem, process, socket,
   or provider entry.
4. The finite runner's eligible-failure path records launch failure,
   `FENCE_INTENT_DURABLE`, WBC deny, and the pre-issued stop saga. It never
   imports or calls the recovery or notification adapter.
5. `SUCCEEDED_CLOSED` requires zero fixer/notification intents, calls, workers,
   and provider receipts. It does not claim recovery or notification success.
6. Installed reachability tests cover public imports, direct modules, CLIs,
   wrappers, systemd units, exception fallbacks, Discord/AgentBox adapters and
   old watchdog/repair entrypoints. Every one makes zero effects.
7. Independent review must accept this profile change before it can issue a
   launch handle.

The positive one-fixer/one-send canary remains deferred with T1.5/T1.10. It
must not be reinterpreted as passing because the counts are zero.

## Shortest safe causal launch gate

### Gate 1 — restore supported observation before any cloud mutation

Land and independently accept the bounded provider/preflight commit already
identified by the incident diagnosis:

- preserve redacted SSH return code, stderr **and stdout** on failure;
- add allowlisted host-side container inspection returning
  `running|stopped|paused|restarting|missing|unknown`, image/exit/OOM identity,
  and exact `/workspace` bind source; and
- add host-side bound-workspace bytes/inodes/quota/fsync/WAL/receipt-reserve
  preflight.

Run it through the supported provider. Any `unknown`, unreadable mount, bind
mismatch, or reserve shortfall is NO-GO. Legacy deploy cannot be the first
diagnostic because it would replace the stopped container and destroy the
required pre-cutover observation.

### Gate 2 — freeze one clean zero-recovery integration candidate

Build one clean exact commit/tree/wheel containing only the exercised route:

- accepted RA containment and the exact v2 fence interface;
- accepted T1.8 generation selection/attestation plus its actual fixed
  production deploy/observer composition;
- the provider/preflight repair;
- bounded T1.9 launch/stop implementation under the zero-recovery profile;
- the narrow WBC capabilities for exact upload/start/observe/stop and the one
  pinned model route; and
- accepted T1.3 transport authority for any model result consumed by the
  finite slice, plus route-local terminal-attempt and graph-reject-to-stop
  guards if the canary will claim a cursor transition.

If the immediate goal is only `RUNNER_STARTED_AND_STOPPED`, semantic admission
work may remain deferred and no cursor/T6.2 claim is allowed. If the canary runs
`plan -> critique -> gate -> finalize` and claims movement past the old cursor,
the exercised T1.2/T1.3/scoped-T1.4 checks are causal prerequisites; supervision
cannot turn failed or unauthenticated model output into an accepted transition.

No T1.5 pass-3 code or stall/notification implementation is part of this
candidate. The clean integration manifest binds that exclusion and the exact
follow-up location.

### Gate 3 — prove installed fail-closure locally

Before a deploy decision, source, wheel, installed `python -P`, fixed CLIs,
materialized wrappers, service units and capability-registry digests must agree.
The finite matrix must prove:

- two and 200 concurrent execute/reconcile calls produce one reservation, one
  upload, one runner slot/start and one exact stop;
- response loss, crash, ENOSPC, expiry, PID reuse and observer disagreement
  never redispatch a `STARTED` upload/start/stop;
- every finite-runner failure performs exact fence/stop and produces zero
  fixer, diagnostic, resident-agent and notification effects;
- 200 unchanged observations perform zero provider calls;
- raw `--fresh`, resume, tmux, watchdog, repair, notification and direct
  provider aliases reject before mutation; and
- execute, Git/PR publication, product deploy and every unlisted effect family
  are unavailable.

A scoped Release Authority decision then binds candidate/generation, provider
route, zero-recovery effect allowlist, tests, current owner heads, expiry,
capacity requirement, rollback/forward-fix and typed deferred obligations.

### Gate 4 — fence spam and v2 effects before starting any new process

After Gate 1's current observation and just-in-time capacity recheck:

1. preserve the stopped v2 container/evidence identity;
2. revoke old v2 `resume/repair/notify/model/deploy` grants and every legacy
   notification/fixer GLEK;
3. advance the v2 Custody epoch/tombstone and CAS selection away from v2;
4. prove the old container is not restarted and no old watchdog/repair/
   notification unit is active; and
5. keep all old or ambiguous provider effects terminal or sticky
   non-redispatchable.

Only then may T1.8 install/select the exact candidate. Two independent live
observers must match bytes, interpreter, process births, wrappers, services,
owner endpoints, fixed configuration and zero-recovery capability registry.

### Gate 5 — issue one finite launch and supervise read-only

Issue one signed, expiring v3 seed/envelope with fresh collision-reserved
identities, one upload, one runner slot/start, finite phase/cursor budget and a
longer-lived cleanup-only stop capability. T1.9 is the sole launch surface.

The supervisor may query only authenticated owner receipts and the supported
read-only process observer. Logs/status are diagnostics, not authority. On any
failure or uncertainty, T1.9 denies further effects and advances the exact stop
saga. No Discord or automatic fixer path exists.

### Gate 6 — manual relaunch means a new authority transaction

Human observation does not authorize retry. A second canary may be considered
only after the first has an exact `STOPPED_FENCED`, `FAILED_FENCED`, or
equivalent independently verified terminal record, current RA/Custody/WBC/
Release/process heads agree, and all prior upload/start/stop operation truths
are exact. Any `UNKNOWN`, possible running process, ambiguous provider result,
or incomplete stop receipt means **no relaunch**.

A later run requires a fresh owner decision, fresh signed envelope, fresh
identity/slot reservations and explicit evidence review. It cannot reuse or
reset the first envelope, GLEKs, attempt, marker, names, or response-loss state.

## Notification-spam prevention during the canary

The safest canary notification count is exactly zero:

- old v2 notification grants/GLEKs are revoked before deploy;
- the old container is never restarted as a diagnostic;
- no notification/repair/watchdog/diagnostic worker or timer is installed;
- the canary capability registry has no notification/fixer operation;
- direct Discord, AgentBox, webhook and exception fallback entrypoints are
  installed fail-closed tombstones;
- no Discord notification credential/provider binding is present in the
  canary generation;
- an eligible failure records only launch-owner failure/fence/stop evidence;
- 200 observations are read-only and make zero provider calls; and
- operators inspect the authenticated owner ledger directly rather than asking
  the runtime to send a message.

This closes the causal mechanism behind the historical 201 DMs: unchanged
polling has no send-capable edge at all. It does not claim the future one-send
outbox is complete.

## What moves to the follow-up epic

The current follow-up README assumes an “accepted T1.5 operational fixer” in
its four-commit handoff. That premise is stale after the independent HARD FAIL
and must be recut before any T6.2 handoff.

F1 must explicitly inherit:

- a production external monotonic occurrence/effect anchor that survives local
  SQLite deletion, rollback, corruption and process restart;
- one-attempt provider idempotency and reconciliation under that anchor;
- the exact gated-stall owner handoff, quiet provenance transition and
  owner-controlled due reconciliation;
- an accepted notification outbox with identity-before-provenance, sticky
  ambiguity and one-send/200-silent proof;
- full installed recovery/direct-writer retirement and honest disposition of
  the 741 historical cases; and
- the already-listed generic owner/store and T1.10 hardening.

The operational canary and its T6.2 handoff record T1.5/T1.10 as
`NOT_CONSUMED_OPERATIONAL_CANARY`, with exact deny receipts and preserved
HARD-FAIL evidence. They cannot be cited as T1.5/T1.10 completion. F1 must close
before fixer/notification capabilities, ordinary v3 execution, publication or
product authority are enabled.

### Smallest sound T1.5 follow-up interface

The minimum repair is an effect-owner/WBC operation outside the mutable local
projection store:

```text
reserve_once(occurrence_id, effect_family, canonical_request_digest)
  -> operation_id + monotonic owner receipt

read_operation(operation_id)
  -> UNUSED | STARTED | APPLIED | NOT_APPLIED | INDETERMINATE
     + exact canonical owner receipt
```

Required invariants:

- reserve/consume is an owner-local CAS and is monotonic;
- `operation_id` and provider idempotency identity are occurrence/effect scoped
  and cannot change merely because a local attempt row vanished;
- `STARTED` is never dispatched again;
- the owner receipt survives or is independently queryable after deletion,
  rollback or replacement of the local SQLite database;
- local absence always triggers owner reconciliation, never virgin-state
  inference; and
- unknown, corrupt, unavailable or conflicting owner truth produces terminal
  no-redispatch, not a replacement attempt.

HMAC-authenticated local receipts may cache that truth but cannot replace this
monotonic owner interface.

## Final adjudication

The efficient route is therefore:

```text
provider observation/preflight repair
-> clean zero-recovery T1.9 integration + installed fail-closure
-> current capacity observation
-> old v2 fixer/notification/launch fence
-> exact generation deploy + two-observer attestation
-> one signed finite v3 launch
-> read-only supervision
-> exact stop/fence
```

Do not spend the prelaunch critical path repairing T1.5 if no canary capability
can reach it. Do not weaken T1.9's own monotonic launch/start/stop requirements,
do not install dormant direct fallbacks, and do not call a human-triggered retry
safe while any prior effect truth is unknown.

No code, Git, cloud/provider, owner, checklist, process, session, existing
report, or follow-up epic was mutated. This adjudication report is the sole
write.
