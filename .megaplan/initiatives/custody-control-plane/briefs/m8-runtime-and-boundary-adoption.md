---
type: brief
slug: m8-runtime-and-boundary-adoption
title: Universal WBC producer, runtime, chain, resident, and cloud adoption
epic: custody-control-plane
created_at: '2026-07-13T00:00:00+00:00'
---

# M8 — Universal WBC producer and runtime adoption

## Outcome

Migrate every production boundary producer/writer and every supported runtime,
chain, resident, cloud, child-lineage, repair, publication/delivery, and
compatibility adopter to M6A's transactional WBC API and M7's controlled-writer/
action-validator contract. Every accepted attempt has durable start evidence
before dispatch and exactly one terminal or explicit indeterminate result;
every authoritative action also validates a current Run Authority grant/fence
plus current Custody lease/epoch. A support-manifest label is inventory input,
not proof that a producer is adopted. The milestone fits within two weeks.

## In scope

- Join exact native/workflow manifest, WBC boundary/attempt/effect, Run
  Authority grant/decision/coordinator-fence, Custody occurrence/lease/epoch,
  and projection identities without treating any projection as authorization.
- Migrate admission and common execution seams: init/auto/supervisor admission,
  shared phase worker start/finish, worker/provider commands, subprocesses and
  managed processes. Reservation/start must commit before user code or provider
  dispatch, including early validation failure and signal/crash paths.
- Emit required WBC phase evidence for prep/plan, critique/revise, gate,
  execute/batch/approval/fallback, tiebreaker, review/rework, parent rejoin and
  reducer promotion, finalize, replan, and every operator override. Generic and
  phase-specific receipts must join one attempt and cannot be omitted while
  lifecycle advancement still succeeds.
- Migrate fanout/children/reducers, suspension/resume/cancellation, retry/replay,
  chain/epic/bakeoff/finalize/PR/publication, resident managed children and
  parent aggregation, ordinary/scheduled delivery, cloud/AgentBox/provider
  adapters, watchdog/repair/auditor emissions, and shell/wrapper seams.
- Replace evidence-only, “without raising,” best-effort, warn-and-continue,
  swallowed-exception, shell `|| true`, and mutable-alias WBC writes. A required
  append/query failure blocks dispatch/advance or produces explicit
  indeterminate state and reconciliation work.
- Require exact-version source-record lookup immediately before dispatch,
  repair, completion, cancellation, publication, and delivery; causal start/
  terminal/retry/suspension/effect evidence; and post-transition authoritative
  reread. WBC receipts/findings can block but cannot authorize any of those actions.
- Regenerate `evidence/wbc-boundary-inventory.json` from static discovery and
  captured runtime traces on every change. Each producer row must name the
  implementation commit, start/phase/terminal writers, success/failure/cancel/
  suspend/resume/retry semantics, positive test, negative bypass test, and raw
  runtime trace digest.
- Adopt immutable attempt-scoped artifacts and exact repair/worker identity at
  every residual runtime boundary; a current worker and repair cannot both hold
  accepted custody for the same subject attempt/repair occurrence.
- Establish parent/root custody so child completion cannot independently advance
  or deliver when the parent owns synthesis.

## Out of scope

Changing `.pypeline`/compiler topology, WBC C1-C6 identities or ownership,
Run Authority acceptance semantics, final status UI migration, production
destructive effects, or compatibility deletion.

## Locked decisions

Native source owns topology; WBC owns boundary and attempt/effect evidence; Run
Authority owns capability and accepted claims/decisions; Custody owns exclusive
lease/epoch and recovery. Contract lookup uses the recorded hash/version, never
latest. No supported residual adopter may remain warn-only at milestone acceptance.
Schema-only, declared-only, unknown, manual-fixture-only, best-effort, and
warn-only are all incomplete adoption states.

## Open questions

- Which observed contract IDs or discovered call sites changed at the exact
  final landed WBC revision, and does the generated inventory account for each?
- Which historical-run readers require an expiring read-only adapter?
- Which external-effect and human-approval cases use fakes/fixtures here and
  must remain action-off until M10 or an operational approval?
- Are any resident/cloud paths owned by another active corrective and therefore
  dependencies rather than mutation scope?

## Constraints

Do not edit prerequisite chains, manifests, runtime state, active sessions, or
owned schemas. Preserve installed/editable/runtime source identity. Use fakes,
fixtures, and shadow paths for approvals/provider effects; no real external
effect is authorized by this milestone.

## Done criteria

- The combined support manifest covers every declared supported runtime/adopter
  with no unexplained exemption or duplicate owner, and the independent
  generated inventory has exact set equality across declared contracts,
  semantic call-site discovery, and captured runtime traces.
- Every accepted attempt is queryable before its dispatch and reaches exactly
  one `completed`, `failed`, `cancelled`, or `indeterminate` terminal. Empty,
  missing, duplicate and post-terminal streams fail tests and cannot advance.
- Missing/stale/deleted contract, selector, manifest, parent, or fence rejects
  dispatch before user code/effects and names the exact identity gap.
- A valid WBC receipt without current Run Authority and Custody records rejects;
  a valid Run Authority grant without a current Custody lease rejects; a valid
  lease without a current scoped grant rejects. The same matrix applies to
  repair, complete, cancel, publish, and deliver.
- Every start/terminal/retry/suspend/resume/cancel/effect has joined
  causal evidence and an accepted authoritative reread before advancement.
- All audited contract and operational families in
  `research/wbc-boundary-adoption-matrix.md` have implementation commits,
  static cases, success/failure traces, and bypass-negative tests; schema-only,
  support-manifest-only, manual-emission, or fixture-only evidence cannot pass.
- Parent/root custody and parent-owned delivery aggregation pass duplicate,
  crash, replay, and no-independent-child-delivery tests.
- Static/runtime inventory reports zero authority-increasing compatibility
  reader/writer outside the registered contract.

## Touchpoints

Native manifests/persistence/checkpoints, Megaplan workflows/stages/reducers/
execute/fallback/chain/publication, control bindings, WBC generated interfaces,
Run Authority views, resident provenance/subagents/outbox/delivery, cloud and
AgentBox adapters, provider fakes, wrappers, compatibility paths, and tests.

## Anti-scope

Do not turn WBC contracts into routing/status authority, fork WBC ownership, or
normalize old runs by writing them. Implementing missing producers through the
WBC-owned API is required adoption, not a new Custody ledger. Do not infer authority from a
terminal artifact, receipt, projection, process, marker, child result, provider
status, or prose.

## Stop and rollback conditions

Stop on any supported adopter without exact contract/attempt/fence identity,
post-write reread, unique owner, or read-only historical behavior; also stop on
simultaneous accepted repair/worker authority. Rollback disables adopter
promotion and effects, retains versioned compatibility reads and immutable
evidence, and cannot restore direct-write or implicit-latest authority.

## Handoff and dependencies

Dependencies: M6 generated boundary inventory, M6A transactional WBC substrate,
M7 controlled-writer proof, exact WBC revision and support manifest. Handoff
to M8A: combined adopter support manifest, exact-version and post-reread traces,
boundary/attempt/decision joins, child/root lineage and delivery proof,
compatibility expiry map, and the residual authority-reader registry.

## F01–F17 amendment contract

This milestone owns universal producer/adopter wiring for F02 durable block/exit
facts, F04 attempt/effect history, F17 provenance, and R1's active boundaries.
It consumes rather than redefines M6A storage and M7 custody.

- **Prerequisite:** accepted M6A transactional API and M7 controlled-writer,
  action-validator, occurrence, lease/epoch, and repair-receipt contracts.
- **First safe action:** at one attested vector, regenerate the declared/static/
  runtime boundary inventory with promotion/effects off, then exercise the
  lowest-risk fake adapter before touching broader cohorts.
- **Deliverables:** `evidence/m8-f01-f17-adoption.json`, exact producer and
  adopter traces, block/exit timestamp joins, source/install/wrapper/config/
  process identities, bypass-negative tests, parent/root custody proof, and an
  expiring read-only compatibility map.
- **Acceptance evidence:** exact set equality across declarations, semantic
  call sites, and captured traces; every dispatch has durable start and one
  terminal/indeterminate result; every action class rejects missing/stale Run
  Authority or Custody input; every supported F02/F04/F17 producer is traced.
- **Component-versus-wiring safeguard:** manifests, schemas, manual emitters,
  fixtures, and isolated adapters do not establish adoption. A row moves only
  with implementation commit, positive/negative trace, exact runtime vector,
  and owner acceptance.

## Profile rationale

Difficulty 5/5; `partnered-5/thorough/high @codex`. Cross-runtime semantics and
hidden compatibility paths can preserve a globally split authority even when
each producer's local conformance suite passes.
