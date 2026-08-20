# GPT-5.6 Sol Adversarial Review — Critique Ledger Incident Plan

**Date:** 2026-08-02

**Reviewer:** `gpt-5.6-sol`, reasoning effort `high`

**Review mode:** read-only repository and Git-history inspection

**Reviewed draft:** `docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`

**Verdict:** **NO-GO for mutating cloud action until the corrections below are implemented and proven.**

## Executive assessment

The draft identifies the correct incident class: model failures were real, but
they were not the root cause. The control plane admitted poisoned predecessor
evidence, collapsed attempt failures into clean-looking critique results, and
split repair and effect custody across records that did not guarantee a lawful
continuation.

The draft was nevertheless unsound as a recovery design in three important
ways:

1. it proposed L2/meta-fixer and watchdog recovery even though binding M11
   retired that topology;
2. it claimed cross-system atomicity and exactly-once terminal outcomes that
   Run Authority, Custody, WBC, provider, and incident stores cannot jointly
   guarantee;
3. it relied on WBC before eliminating direct effect fallthrough, shadow
   authorization, synthetic identities, and ambiguous provider outcomes.

These are release blockers, not editorial concerns.

## What the draft got right

- The finalizer model is not the root cause. Deterministic graph rejection was
  useful safety behavior.
- Transport, parser, producer-contract, sandbox, and provider failure must be
  represented separately from semantic critique results.
- Critique admission needs exact-set completeness and target-bound evidence.
- Graph rejection should admit only a narrow, authority-approved structural
  repair; it must never fall through to execution.
- Runtime adoption must bind a complete installed vector rather than infer
  deployment from a commit.
- A fresh successor is directionally safer than resuming the old CL2 plan, but
  only after the old plan's authority, leases, effects, and publication paths
  are fenced.

## Required P0 corrections

### 1. Use the binding M11 recovery topology

The binding contract is
`.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md`.
It requires:

- one immediate non-agent event trigger;
- one singleton `simple_fixer` operator;
- at most one canonical target runner;
- one three-hour missed-event reconciler invoking the same implementation and
  sharing the same occurrence claim.

It explicitly prohibits watchdog, L1/L2/L3 investigator, repair-loop,
meta-repair, periodic audit-agent, and managed-child fanout as recovery
topology. Missing or invalid identity is terminal, non-claimable intake. It
creates a linked recovery obligation consumed by the singleton
`simple_fixer`; fixer failure terminalizes and requires a separately authorized
release actor or human decision.

### 2. Invalidate the prior M11 completion/promotion claim

Commit `d10b0fef2b6` claims M11 completion, but the inspected implementation
still contains effect bypasses and shadow authorization. The binding runtime
decision remains `proposed-human-gate`, and the ownership decision record still
contains blockers. Run Authority must append a superseding decision that
quarantines the prior completion/promotion evidence. A new zero-blocker
ownership decision, complete portfolio, approval, full cross-contract/M11
suite, and production-vector canary are required before recovery mutation.

### 3. Replace cross-owner atomicity with a fail-closed saga

Atomicity is enforceable only within each authoritative owner store. The
cross-owner sequence must be explicit:

1. read coherent Run Authority and Custody cursors;
2. validate grant, fence, lease, epoch, subject, and runtime at the boundary;
3. durably reserve/start the WBC attempt;
4. perform the effect;
5. persist the WBC outcome;
6. reread and reconcile authoritative owner records.

Any torn, stale, ambiguous, or unreadable state becomes `PENDING`,
`INCOHERENT`, or `INDETERMINATE` and prohibits redispatch. The defensible
guarantee is at most one accepted terminal outcome per WBC attempt/GLEK. An
external provider may apply an effect before its acknowledgement is durably
recorded; that occurrence can remain permanently indeterminate.

### 4. Eliminate every effect bypass before relying on WBC

The inspected runtime contains an optional Discord adapter with direct-POST
fallback, and delivery authorization can degrade to shadow/synthetic forms.
Production effects must require a real current Run Authority grant/fence,
current Custody lease/epoch, and canonical WBC GLEK. Missing adapter or
authorization, synthetic/shadow identity, fake success, and local exceptions
must fail closed with zero provider calls. Ambiguous provider application is
`INDETERMINATE`, not `FAILED` followed by resend.

Notification addressing is request material, not an independent idempotency
authority. Chunked messages require stable child GLEKs derived from the parent
GLEK, chunk index, and digest.

### 5. Derive admission from raw evidence

The deployed chain used generic admission, had no domain predicate for the CL1
handoff, and enabled auto-approval even though the handoff recorded
`accepted_for_cl2=false` and unresolved blockers. A versioned, allowlisted
domain predicate must independently derive its result from raw, hashed
evidence. Its receipt must bind predicate/version, predecessor commit/tree,
artifact digests, target milestone/brief/spec/base commit, runtime generation,
and evaluation time.

Missing, unknown, stale, mismatched, or throwing predicates reject. Admission
must be re-evaluated immediately before plan creation. Run Authority grants or
quarantines initialization under fence/CAS; Custody owns the initialization
occurrence; WBC owns effects. Auto-approval applies only to a closed set of
human decision classes and can never turn a failed machine prerequisite into
an assumption.

### 6. Put storage admission before dispatch

The deployed escalation JSONL path rewrites the whole file, has no process-safe
claim, treats read errors dangerously, and derives sequence from current
length. Reserve byte and inode capacity on an isolated or quota-controlled
volume. Watermarks must cover worst-case owner transaction, WAL/fsync,
checkpoint, and rebuild. Stop execution and external effects before durable
intent or receipt persistence becomes unsafe.

Canonical owner stores must survive logs, artifacts, and projections.
Projections are disposable and may be stale; sequence gaps are legal. Evidence
cleanup requires an off-volume, content-addressed manifest first. “Zero
unreceipted effects under disk full” is not enforceable after provider dispatch;
the correct rule is durable intent before effect and `INDETERMINATE` when an
acknowledgement cannot be persisted.

## Required P1 corrections

### Two-axis critique model

Attempt status and semantic result must be distinct.

Attempt status:

- `SUCCEEDED`
- `PROVIDER_FAILED`
- `PRODUCER_CONTRACT_FAILED`
- `PARSER_FAILED`
- `SANDBOX_FAILED`
- `CANCELLED`

Semantic result exists only after `SUCCEEDED`:

- `FINDING`
- `NO_FINDING`
- policy-scoped `EXTERNAL_UNVERIFIABLE`

Wrong or multiple IDs, field rewriting, flag coercion, missing output, and
prose inference are contract failures. Thorough/high robustness requires every
mandatory lens to succeed. The selection manifest binds lens occurrence, plan
hash, contract-bundle hash, and attempt/result receipts. External
unverifiability is never evidence of a clean critique.

### Preserve existing ownership; do not add a global retry owner

- domain policy owns graph fingerprints and repair budgets;
- Custody owns occurrences, leases, and reclaim;
- WBC owns effect attempts and budget evidence;
- Run Authority accepts repair, replan, quarantine, or supersession.

### Bind immutable contract bundles

A registry is discovery metadata, not authority. Each release uses an immutable
content-addressed contract bundle binding prompt, capture/transport schema,
parser ABI, normalizer, semantic validator, fixtures, and provider assumptions.
There is no mutable `latest`. Required fields cannot be synthesized or
discarded. Structural repair is limited to invalid pointers in the same object
and bundle followed by full revalidation. Semantic infeasibility is not a
structural repair.

### Release by fenced generation migration

The generation manifest binds source tree, image/base, interpreter/venv,
locks, installed provenance, `.pth`/imports, wrappers, services, environment
policy, schemas/migrations, contract bundle, and routes. Fence old writers and
effects before a CAS generation switch, then attest live process IDs,
executables, imports, and configuration. Binary rollback is legal only when the
old generation can read post-migration state; otherwise use forward-fix.
Backup restoration must be tested.

The interim changes `a7565c2e`, `70cae1d6ad`, and `c5b613a441` are descendants
of deployed `c7bcb06af536`; their existence does not prove deployment.

### Fence before creating the successor

Run Authority must supersede/quarantine the old revision and revoke its grants;
Custody must fence/release its leases; WBC must reconcile old GLEKs to terminal
or indeterminate; and chain selection must CAS to the successor. The successor
receives new plan/revision, subject attempt, Custody/WBC, branch/worktree, and
PR identities. It inherits no gate/finalizer state, retry budget, notification
identity, or mutable artifact. Old artifacts remain read-only evidence.

## Evidence qualification

Remote counts, volume saturation, zero-byte artifacts, and claims that no
execution or PR occurred require a content-addressed evidence manifest. Each
claim needs a claim ID, URI/path, SHA-256, size, capture time, collector/tool
version, runtime/commit, clock basis, and minimal query/excerpt.

Tests proving that a handoff derives its own boolean do not prove production
admission consumed it. Commits do not prove deployed runtime. Provider behavior
claims must be scoped to the exact provider/model/route/receipt. Floating dirty
paths are not stable citations; use exact commits and blob identities.

## Minimum critical path

1. Freeze all mutation and external effects; capture read-only evidence.
2. Write an off-volume content-addressed evidence manifest; establish isolated
   control capacity; validate owner stores, WAL/indexes, and unknown effects.
3. Have Run Authority invalidate prior M11 completion and the old CL2 revision;
   fence grants/leases, reconcile GLEKs, and CAS-disable old resume.
4. On one clean lineage implement the vertical slice: typed raw-evidence
   admission, two-axis critique/exact completeness, existing-owner graph
   fingerprint/budget, singleton `simple_fixer` immediate plus three-hour path,
   WBC-only effects, and storage backpressure.
5. Run installed-entrypoint negative, crash, concurrency, ENOSPC, ambiguity,
   cross-contract, and M11 tests. Produce a zero-blocker ownership decision and
   new acceptance evidence.
6. Canary one immutable fenced generation. Test backup restore and
   rollback/forward-fix, attest live processes, and prove old writers reject.
7. Resolve the raw CL1 predicates and have Run Authority grant the target-bound
   successor.
8. Create fresh CL2 plan/revision/Custody/WBC/branch/worktree identities. Run
   ordinary plan → critique → gate → finalize. If graph admission rejects,
   permit one authority-approved narrow repair for the same occurrence.
9. Execute, commit, push, and open a PR only through ordinary Run
   Authority/Custody/WBC paths; independently verify chain advancement and the
   publication receipt.

## Go/no-go gate

Current state: **NO-GO**.

Mutation may begin only when all of the following are proven:

- old mutation and effects are stopped and fenced;
- the off-volume evidence manifest verifies;
- byte/inode reserve and authoritative stores/WAL are healthy;
- old grants and leases are revoked, and old provider effects are terminal or
  indeterminate with redispatch prohibited;
- prior M11 promotion is invalidated and a zero-blocker ownership decision is
  approved;
- an immutable recovery generation and production vector exist;
- no direct effect fallthrough, shadow/synthetic authorization, fake success,
  watchdog/L2/meta-repair/managed-child path is reachable;
- installed-entrypoint fault, concurrency, storage, provider, and successor
  tests pass;
- migration, backup, rollback/forward-fix, and old-writer rejection pass;
- old CL2 cannot resume, the CL1 predicate is independently satisfied, and the
  fresh successor grant/lease/WBC start are coherent.

After the gate: staged canary, then one ordinary CL2 action, then independent
verification, then broader execution. Publication is prohibited until
execution receipts and the WBC publication intent are durable.

## Final review conclusion

The root-cause account is usable. The original recovery design was not. Adopt
the corrections above before any cloud mutation. With those corrections, the
plan can prevent this known failure class from being admitted and can contain a
novel failure without duplicate effects or an observation loop. It still
cannot promise that providers, disks, models, or new code never fail; permanent
indeterminacy must remain a first-class, operator-visible terminal condition.
