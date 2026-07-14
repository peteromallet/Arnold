---
type: decision
slug: single-authoritative-runtime-history
status: proposed-human-gate
approval_record: pending
date: 2026-07-13
---

# One authoritative Run Authority contract/runtime

## Decision

Complete pipeline-wide adoption of the existing Run Authority contract/runtime.
Run Authority owns grants, accepted attempts and decisions, fences, quarantine,
and authority-increasing views. WBC owns exact-version boundary declarations,
the durable execution-attempt/effect ledger and payload/reference policy,
semantic findings, and supported-runtime conformance. Custody owns coherent
evidence collection, fail-closed decision policy, recovery custody, residual
adoption, and rebuildable projection convergence.

These contracts are joined by exact identity and causal lineage. They are not a
license to create a new all-purpose ledger, route engine, status authority,
transition writer, repair queue, or lifecycle.

## Ownership split for the prevention extension

- Run Authority owns grants, coordinator/subject attempts, acceptance,
  rejection/quarantine/supersession, fences, dependency acceptance, and the
  pure authoritative reducer.
- TransitionWriter and repair custody own lifecycle CAS plus occurrence-bound
  request/claim/lease/dispatch/terminalization/reopen and independent
  verification scheduling. They cannot accept task claims or self-verify.
- WBC owns exact-version boundary declarations and immutable execution-attempt/
  effect evidence, receipts, payload/reference policy, findings, and supported-
  runtime conformance. It grants no authority and mutates no lifecycle.
- Maintenance owns coherent observation, the six-hour reconciliation backstop,
  daily read-only efficiency analysis, and deterministic finding/ticket-proposal
  policy. It is not a repair actor or active-plan optimizer.
- Megaplan planner/compiler owns dependency semantics, routing groups, critical-
  path/parallelism/turn feasibility, task complexity/splitting, and compiling
  deterministic validation jobs.
- The executor/launcher owns source/runtime preflight, model/import isolation,
  verify-only repair adoption, and bounded timeout/failover/compaction/rework/
  retry circuits.
- Observability owns append-efficient rebuildable projections, the joined work/
  latency ledger, pure operator views, and exact-evidence auditor reasons. It
  cannot refresh liveness or resolve authority independently.

M8A implements the adjacent planner/compiler/executor policy because putting it
in Run Authority would violate the narrow-kernel decision and putting it into
M8 or M10 would make those custody milestones oversized.

## Locked invariants

- Persist authoritative intent/attempt before dispatch and durable outcome
  before success through the prerequisite-owned contracts.
- Bind every decision/effect to exact workflow/contract/code/config version,
  run/attempt, actor, capability grant, coordinator fence, idempotency key, and
  causal parents; never reinterpret an old record through an implicit latest.
- Only registered controlled writers may increase authority. Projection and
  compatibility writers remain downstream and cannot grant authority.
- Coherent evidence is versioned before and after collection. Tearing,
  staleness, missing ownership, or version mismatch returns `UNKNOWN` or
  `INCOHERENT`, emits drift, and performs no action.
- Callers reread authoritative state after transition or effect before
  advancing. Post-mutation retries require current authority and reconciliation.
- A repair actor cannot verify itself. Closure requires an independent negative
  control plus resumed authoritative progress.
- Projections are disposable and reproducible. Rollback never restores a legacy
  writer, erases causal evidence, or converts a projection into authority.
- Legacy bypasses are shadowed, fail closed, then removed only after parity,
  cross-version/replay, zero-reader/writer, and rollback evidence.
- Eligible blocked occurrences reach accepted repair or typed escalation with
  measured p95 under five minutes; the scan and six-hour auditor reconcile
  missed events and never become primary dispatch authority.
- Completion additionally requires captured-incident replay, idle projection
  and planner/executor and repair/worker canaries, installed-runtime provenance,
  one genuine blocked-run recovery, joined productive/replayed evidence, and
  deletion/retirement receipts. Local green tests or nominal manifests do not
  satisfy this decision.

## Approval record required before M7 implementation

The frontmatter approval field remains pending until a human-approved immutable
record pins all of the following:

- M5's three accepted Run Authority receipts, zero-divergence canonical
  verification, regenerated completion-manifest digest, landed revisions,
  proof map, canonical `.megaplan/initiatives/runauthority-epic/.retired`
  marker, and content-addressed retirement attestation;
- validated WBC completion-manifest digest, chain hash, landed revision, and
  proof/support manifests;
- M6's residual surface and controlled-writer inventories with zero unexplained
  or overlapping owner;
- storage, retention, redaction, access, identity/fence, mixed-version, and
  legacy-read policies inherited from prerequisite contracts;
- repair/effect allowlists, canary cohorts, kill switch, promotion/deletion
  authority, rollback owner, and independent verifier;
- confirmation that production enforcement, mutating repair, provider/Git
  effects, deployment, and destructive deletion begin disabled;
- any remaining PC/program-counter/parity-control-plane scope resolution.

M5 may start while this field is pending because it is evidence reconciliation,
not migration implementation. M6 may perform observe-only contract/ownership
inventory and must leave M7 blocked until this record is accepted. Absent that
record, M7-M11 and M8A fail closed. Planning validation, a green test, or a
milestone/chain status is not approval.
