# M3b — Custody-bound repair promotion transaction

## Outcome

Close the delivery gap in the unified fixer seam. After a repair author has
diagnosed, implemented, and committed a repair and an independent verifier has
reviewed that exact commit, one dedicated delivery principal can publish the
manifest-bound repair, promote a content-addressed runtime, atomically rebind all
runtime consumers, and resume the same occurrence without handing delivery back
to the main agent. Terminal closure remains the responsibility of the independent
verifier established by M3.

## Scope (about one sprint; no more than two weeks)

Implement a policy-scoped orchestration layer over the existing guarded Git,
runtime, occurrence, and launch-binding primitives. It must consume the canonical
M2/M3 occurrence, custody lease/epoch, Run Authority grant/fence, attempt identity,
repair manifest, and independent review receipt. It must not invent parallel
authority or weaken any existing CAS guard.

The delivery transaction has exactly these capabilities:

1. Push only the repair branch named by the repair manifest and only when its tip
   is the exact full Git commit recorded in the independent review receipt. Refuse
   ref substitution, a moved tip, an unreviewed commit, non-fast-forward ambiguity,
   or publication outside the occurrence-scoped grant.
2. Build a fresh immutable runtime/dependency generation from that exact commit,
   record its content-addressed identity and provenance, and validate that the
   installed/imported source resolves exclusively to the promoted generation.
3. Run the dependency-import gate and the public-import-cycle gate against the
   built generation before any authoritative binding moves. Gate failure leaves
   the prior runtime and every authoritative binding active.
4. CAS-update the runtime manifest, cloud/session marker, chain runtime binding,
   plan/project-source binding, and canonical launch seed as one recoverable
   transaction. Every participant must be guarded by its freshly reread expected
   digest; partial application must deterministically roll back or replay forward
   to one coherent generation, never expose a mixed binding vector, and emit a
   durable transaction receipt.
5. Preserve the original occurrence identity, claim, custody lease epoch, Run
   Authority fence, repair identity, coordinator attempt, and retry/attempt
   lineage across publication and cutover. Promotion creates delivery events and
   receipts, not a replacement occurrence or synthetic authority history.
6. Resume or retrigger that same occurrence through its canonical resume strategy,
   using the newly validated launch seed and runtime identity. Crash/retry must
   adopt or reconcile the same promotion transaction and must not enqueue a second
   repair or mint a second claim.
7. Hand post-resume observation and terminal closure to the M3 independent
   verifier. The delivery principal may record delivery success and schedule
   verification, but it cannot author terminal verification or close custody.

## Delivery principal and grant contract

The delivery principal is a dedicated role distinct from both the repair author
and the independent verifier. A principal may act only with a durable,
occurrence-scoped delivery grant issued through the existing Run Authority and
custody policy. The grant binds at minimum the occurrence/repair identity, claim,
lease epoch, fence, attempt lineage, repair-manifest digest, source branch, exact
reviewed commit, review-receipt digest, permitted target repository/ref, expected
pre-cutover CAS vector, allowed action sequence, expiry, and idempotency key.

Each authority-increasing edge must freshly reread and validate the grant, current
lease/epoch/fence, manifest and review receipt, and current CAS vector. Expired,
revoked, stale, broadened, or mismatched grants fail closed before mutation. The
grant authorizes only this bounded delivery transaction; it grants no general Git,
operator, chain-editing, runtime-administration, waiver, or terminal-verification
power. The repair author and verifier must be rejected if either attempts to use
the delivery grant.

## Existing modules and seams to wire

- `arnold_pipelines/megaplan/chain/target_rebind.py`: reuse its exact-SHA/ref,
  clean-worktree, pause/pre-execution, plan/chain binding, publication, locking,
  and recovery guards. Extend or compose its public boundary so a validated
  occurrence-scoped delivery grant—not a generic operator identity—can authorize
  only the manifest-bound branch and reviewed commit.
- `arnold_pipelines/megaplan/cloud/runtime_cutover.py`: reuse its normalized runtime
  identity, marker digest checks, relaunch-command binding, atomic replacement,
  and cutover event. Incorporate marker mutation into the wider transaction rather
  than treating marker success as proof that all bindings moved.
- `arnold_pipelines/megaplan/chain/occurrence_adopt.py`: reuse its exact occurrence
  CAS vector, six-root runtime checks, deterministic repair identity, claim,
  durable receipts, and replay behavior. It is currently operator-only; add a
  narrow policy path that accepts the delivery principal only when its validated
  grant names this exact occurrence and operation. Retain the operator path and
  fail closed for all other actors or scopes.
- Reuse the canonical runtime manifest, execution-binding, runtime-attestation,
  and launch-seed builders/validators already called by these seams. Do not create
  alternate manifest, marker, binding, seed, or identity formats.

The orchestration layer owns transaction preparation, ordered effects,
compensation/replay, and one durable outcome receipt. Underlying modules retain
their existing validation ownership. Define explicit prepared, committing,
committed, rolled-back, and reconciliation-required states so a crash at every
effect boundary has one deterministic continuation.

## Success criteria and review gates

- An end-to-end fixer run diagnoses, implements, commits, obtains independent
  review, ships the exact repair branch/commit, builds and validates an immutable
  runtime generation, rebinds every declared consumer, and resumes the same
  occurrence autonomously with no main-agent or operator hand-back.
- The dependency-import gate proves all required runtime dependencies import from
  the promoted generation. The public-import-cycle gate proves supported public
  entry points import in clean interpreters without a newly introduced cycle.
  Either gate failing produces zero authoritative cutover.
- CAS integrity tests cover concurrent marker/manifest/chain/plan/seed changes and
  crash injection before and after every write. A transaction ends with all
  bindings on the old generation or all on the new generation; repair/replay is
  idempotent and no mixed generation can launch.
- Lineage assertions before and after promotion show the same occurrence, claim,
  lease epoch, fence, repair identity, coordinator attempt, and attempt ancestry.
  Stale lease/fence/grant or mismatched review/commit/branch evidence produces zero
  mutation and a truthful refusal receipt.
- Resume/retrigger evidence identifies the same occurrence and the promoted launch
  seed. Duplicate delivery requests converge on one transaction and one resume
  effect.
- The delivery principal cannot self-review or terminally verify. A distinct M3
  verifier performs direct owner-source checks after resume and alone records
  blocker-cleared closure; failed or unknown verification keeps custody open.
- A controlled fault matrix covers rejected publication, build failure, both
  import gates, every CAS participant, process crash/restart, rollback/replay,
  duplicate requests, stale grants/leases/fences, resume failure, and verifier
  handoff. Receipts make every attempted and completed effect auditable.

## Out of scope

No new ledger, authority store, custody model, lease/epoch/fence system, repair
queue, transition writer, occurrence type, manifest format, runtime identity, or
launch-seed format. No broad operator impersonation, protected-branch bypass,
force push, force-proceed/waiver, arbitrary branch publication, new repair class,
profile/budget change, active-chain redesign, rollout policy, six-hour detection
logic, daily analytics, or terminal self-verification. This milestone implements
the bounded delivery seam consumed by M4; it does not implement M4's operational
loop.

## Handoff to M4

Provide one stable occurrence-bound delivery API and receipt schema that M4 can
invoke after an allowlisted repair is independently reviewed. The handoff must
expose deterministic status for prepared/committing/committed/reconciled delivery,
the promoted runtime and launch-seed identities, the preserved lineage vector,
the resume receipt, and the independent-verification request—without giving M4
direct Git, binding, marker, seed, or terminal-closure authority.
