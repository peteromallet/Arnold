# Independent Sol-high adjudication — shortest safe Critique Ledger v3 relaunch

Date: 2026-08-02  
Reviewer posture: independent, read-only sequencing and safety adjudication  
Decision: **NO-GO now; GO after the finite Stage A predicate in this report**

## Executive verdict

Root's narrow cut is directionally right and materially closer to the user's
outcome than Luna's all-T0/T1/T2 cut. Luna's cut inflates the canary gate by
requiring platform-wide owner-store adoption, every configured model route,
every production effect family, the complete installed fault suite, and full
release-ticket closure before the bounded recovery path uses most of them.
Those obligations are real, but most belong in Stage B.

The narrow proposal still needs two corrections.

First, it omits three exercised-path controls: raw CL1 admission (T1.1), typed
critic-attempt completeness (T1.2), and deterministic graph-rejection routing
(a scoped T1.4). Without them, v3 can reproduce the original false admission,
turn failed critics into a clean round, or fall back into the same broad retry
loop before it passes the old stall.

Second, a literal envelope allowing only one transition in total cannot start a
fresh successor and prove movement beyond v2's `gated/finalize` cursor. The
shortest honest envelope is a **finite phase slice**: initialize fresh v3, run
ordinary plan -> critique -> gate -> finalize using an exact allowlist of
effects, then expire immediately after the first Run Authority-accepted
transition whose cursor is strictly beyond v2's last accepted cursor. The exact
target should be frozen from the installed state schema; normally this is
`gated/finalize -> finalized` (or its schema-equivalent accepted transition).
It does not authorize execution, Git publication, PR creation, product deploy,
or a second milestone.

Current state is unambiguously NO-GO. Only T0.2 and T0.4 have accepted formal
evidence. There is no integrated candidate, production owner composition,
installed generation, v2 fence, accepted CL1 handoff, v3 launch envelope, or
cloud receipt. T1.3 and T1.5 have reproduced ordinary-path hard failures;
T1.1 and T1.8 remain unaccepted; T1.2, T1.4, T1.6, and T1.9 do not yet have
accepted implementations; T1.10 retains live direct writers; and T5.1 still
has four pending owner decisions.

## What Stage A must prove

Stage A succeeds only when all of the following are true together:

1. One exact clean integration descendant of
   `6787d6363e8fc0603092913ae877db14f3b9fff8` is locally accepted for the
   exercised route.
2. One rollback-compatible or explicitly forward-fix-capable generation of
   that exact tree is installed through an owner-installed Release Authority,
   and independent live observation matches the tested vector byte for byte.
3. The entire v2 tuple is permanently denied for mutation/effects, its Custody
   epoch is advanced, its GLEKs are terminal or sticky non-redispatchable, and
   chain selection is CAS-moved away without editing the marker.
4. Raw CL1 evidence and the necessary human/domain decisions recompute to a
   true, target-bound v3 prerequisite.
5. The installed launch owner reserves fresh identities, starts at most one
   exact runner, and reconciles response loss without another upload/start.
6. The selected model route produces owner-bound raw transport evidence; critic
   failures cannot become `NO_FINDING`; graph rejection can only stop or consume
   the one bounded repair authority.
7. One eligible failure maps to one canonical fixer occurrence and at most one
   initial notification; unchanged observation is silent. A controlled
   installed-production canary may prove this branch before v3 launch rather
   than deliberately failing the real successor.
8. Independent owner queries—not status, marker, process liveness, logs, or bot
   prose—prove the exact v3 transition past the old `gated/finalize` cursor.

## Exact intended production path

| Step | Authoritative path and consumer | Concrete failure if absent |
| --- | --- | --- |
| 1. Freeze source | Integrator creates one clean descendant of `6787d636...`, records commit/tree, candidate component commits, contract/help/schema digests, changed-surface inventory, and test manifest. | Mixed candidates or dirty main can make locally tested code differ from deployed code. |
| 2. Route-scoped acceptance | Independent verifier runs the exact admission, transport, attempt, graph, recovery, notification, launch/stop, response-loss, and installed-package matrices. Release Authority issues a canary-scoped deploy decision. | A local green lane can hide an integration bypass or incompatible owner port. |
| 3. Capacity admission | Cloud-storage owner proves bytes, inodes, WAL/checkpoint, and receipt reserve sufficient for deploy + fence + bounded canary. | ENOSPC can lose intent/receipt after an external effect and enable resend or unverifiable authority. |
| 4. Generation cutover | T3.1 recheck -> T3.2 old-generation writer/effect fence -> T3.3 generation CAS -> T3.4 two-observer live-vector attestation -> scoped T3.5 recovery/rollback canaries. | An old writer or substituted installed vector can falsely attest success or corrupt the new owner records. |
| 5. Permanent v2 fence | Run Authority quarantines the exact tuple; revokes `resume/repair/execute/publish/notify/model/deploy`; Custody advances epoch; WBC makes all old GLEKs terminal or sticky non-redispatchable; selection owner CAS-deselects v2. | A late v2 writer, fallback DM, watchdog, or old GLEK can mutate or notify beside v3. |
| 6. v3 admission | T5.1 owner decisions close the real CL1 blockers; T5.2 recomputes raw evidence under fence through T1.1; T5.3-T5.5 bind fresh spec, workspace, session, plan, occurrence, branch/worktree, and preflight. | A stored `accepted_for_cl2=true`, copied state, or collision can recreate the false predecessor premise or duplicate identity. |
| 7. Launch preparation | T5.6 produces a signed, expiring finite-slice envelope and pre-issued exact stop capability. T1.9 transactionally reserves names, persists parent/child WBC intents, uploads exact bytes, and starts one exact process under T1.8 attestation. | Raw `cloud chain --fresh`, tmux, marker, or response-loss retry can reset a collision or start twice. |
| 8. First model attempt | Frozen one-route allowlist -> T1.6 WBC start -> owner-authenticated transport receipt -> T1.3 immutable bundle/raw bytes -> T1.2 terminal attempt health -> semantic result only after `SUCCEEDED`. | The public `capture_transport` bypass can self-attest a route; a failed critic can again become clean; timeout/ACK loss can be resent. |
| 9. Gate/finalize | Exact selected-lens completeness is admitted; finalizer graph is checked. T1.4 either admits it, performs one pointer/field-bounded repair under the same fingerprint/occurrence, or stops terminally. | Broad retry, model swap, restart, or prose drift can reset the budget and repeat the old stall. |
| 10. Failure branch | A typed eligible failure creates one T1.5 occurrence. Immediate trigger and reconciler contend for the same claim. T1.10 creates incident/diagnostic identity before provenance checks and asks T1.6 to deliver one canonical notification GLEK. | Missing provenance can again generate a blank diagnostic state and repeated fallback DMs; legacy repair routes can create parallel effects. |
| 11. Acceptance | Independent verifier queries Run Authority, Custody, WBC, model-attempt, recovery, notification, and generation owners. It accepts only one exact runner and an accepted v3 transition beyond v2's cursor; the envelope then expires/stops. | A marker, bot message, or changing log can be mistaken for durable movement. |

The definitive Stage A ledger is the content-addressed join of these owner
records. It need not wait for one universal storage implementation, but every
owner used above must be transactional, fail closed on read/corruption, expose a
current cursor/incarnation, and preserve sticky indeterminacy. The incident
projector may join them; it may not authorize them.

## Shortest critical path, ordered and parallelized

### Wave A — freeze the finite integration contract

Run four bounded lanes against the common clean ancestor; interface digests are
frozen before dependent lanes integrate:

- **Authority/admission lane:** integrate locally accepted RA-CONTAIN
  `48e13e1bcbc6769aff753270331d52ac1c148125`; repair and independently accept
  T1.1 `3ed353f8aa3d0df450c563c3cb8d76c87349e32d` for a sealed production owner
  backend, positive owner lookup/reconciliation, and incident-required
  prerequisite. Platform-wide root-milestone policy and a wholesale ChainState
  rewrite are deferred if the v3 spec and all raw launch aliases cannot bypass
  this exact owner.
- **Model/semantic lane:** repair T1.3
  `4099225612f7f0b9bcc57be07c7a77c59a933234` so ordinary callers cannot mint an
  authenticated `ProviderTranscript`; then implement route-scoped T1.2 and the
  fail-closed/one-repair slice of T1.4 for the exact v3 plan, critique, and
  finalizer seams.
- **Recovery/effect/UX lane:** accept the bounded T1.5 repair only after all
  normally importable/direct-module launch, copy, goal, child, caller-authority,
  stored-result, and provenance-detail amplification paths either delegate to
  the canonical owner or hard-deny. Implement T1.6 for only the Stage A effect
  families (model call, spec upload, process start/stop, fixer effect, one
  notification); integrate a T1.10 route slice that removes direct Discord and
  exception fallthrough and binds the installed owner/runtime.
- **Release lane:** independently review T1.8
  `26d240339e0911a0e7347fc7849c8e151ab92111`; accept it only if the repaired
  signed-generation recomputation and displaced-writer lineage survive exact
  crash/replay probes. Any new reproduced semantic defect gets one bounded
  repair. No production claim follows from local PASS.

After those interfaces freeze, implement T1.9 on their exact integrated ports.
Do not wait for generic T1.7 adoption; use only owner stores on this route that
pass the same crash, concurrency, corruption, reserve, and response-loss
properties. Build one clean integration commit, never dirty/diverged main.

### Wave B — route-scoped preproduction proof

In parallel where independent:

- run exact source/wheel/installed/materialized parity and the route-scoped
  replay/fault matrix;
- configure exactly one physical model route, one credential-set ID, one tool
  mode, no fallback, and prove its live installed transport/termination/raw
  receipt under WBC;
- run isolated T2.3 `admit/run/verify` for the finite slice;
- close T5.1's verifier defect and obtain the four real owner decisions, then
  generate T5.2/T5.3 inputs;
- prepare the exact capacity cleanup/reserve manifest, without broad cleanup.

Join on an independent canary deploy decision binding the integration
commit/tree, package/generation, allowed route/effects, tests, owner heads,
expiry, rollback/forward-fix, and explicit exclusions. This is not a full
platform “zero debt” or ticket-closure claim.

### Wave C — serialize production authority changes

1. Execute exact T0.3 capacity work and T3.1 atomic recheck.
2. T3.2 fence old-generation writers/effects.
3. T3.3 install/CAS the exact generation through `GEN-DEPLOY`.
4. T3.4 independently attest the live vector with two observers.
5. Run scoped T3.5 canaries: rollback/forward-fix; post-CAS response loss; one
   failure -> one fixer occurrence; one initial notification -> 200 unchanged
   observations with no second send; exact stop capability.
6. Issue the exact installed canary release receipt. Administrative closure of
   the two broad release tickets is deferred.
7. Execute T4.1-T4.5 as one ordered cross-owner saga. T0.0's production
   containment decision is satisfied by the T4.1 quarantine decision, and
   T0.1's effect freeze is satisfied by T3.2 + T4.2; do not issue duplicate
   authorities merely to preserve old task boundaries.
8. Finish T5.4-T5.6 and independently verify the collision-free finite-slice
   launch envelope.
9. T6.1 launches through the installed T1.9 surface.
10. Run only the bounded T6.3 plan/critique/gate/finalize slice. T6.2 accepts
    only the first exact transition past the prior stall, then authority expires
    or the pre-issued stop/fence closes the slice.

## Smallest coherent integration set

| Component | Exact current input | Stage A disposition |
| --- | --- | --- |
| Run Authority containment | `48e13e1b...` local independent PASS | Integrate; production adapter, install, decision, and receipt still required. |
| Raw admission | `3ed353f8...` implementation candidate | Bounded repair/review required: seal nonproduction backend seam; add owner-installed lookup/reconciliation; require the v3 root policy. Revisionless projection may remain non-authoritative. |
| Contract bundles | `40992256...` HARD FAIL | Bounded repair required: transport/adapter owner or capability signs raw digest + physical provider/model/session/attempt/channel/runtime; binder verifies pinned trust root. |
| Attempt health | preparation only | Implement the six terminal states and exact selected-set reducer only on the Stage A model seams; failed/unknown attempts cannot produce semantics or gate admission. |
| Graph rejection | preparation only | Implement stable fingerprint and either terminal stop or one exact narrow repair for the v3 finalizer path. Disable broad retry/reset aliases. |
| `simple_fixer` | `4bfd5fb2...` evidence head HARD FAIL; bounded repair active | Accept only after B1-B7 normal-path counterexamples are closed and live retired routes are dynamically denied. |
| Effect custody | preparation only | Implement exclusive WBC dispatch for Stage A model/upload/start/stop/fixer/notification effects. All unused mutation families are explicitly unavailable in this generation. |
| Generic owner store | implementation active, no accepted candidate | Not in the integration set as a platform migration. Route owners must individually pass equivalent properties. |
| Release generation | `26d24033...` under review | Integrate only after independent PASS; then supply production executor/observer, rollback/forward-fix, and installed receipts. |
| Launch/stop transaction | preparation only | Implement after T1.1/T1.5/T1.6/T1.8 ports freeze. Fixed production endpoint; no caller-selected socket/root/provider/callback. |
| Notification UX | `0c3d662...` HARD FAIL | Take only the canonical occurrence/outbox/rebuild core after repairing direct writers, package/runtime binding, owner composition, and one-message route. Full rotation/reminder/chunk design follows. |
| CL1 resolution | `7c254f7...` HARD FAIL; four owner decisions pending | Repair exact candidate identity verification and obtain owner decisions. Evidence alone cannot turn the predicate true. |

Required integrated tests are finite: the named counterexamples above; exact
owner/head/cursor substitution; two and 200 concurrent launches/observations;
crash/response loss before/after every Stage A WBC call and owner commit;
provider applied/ACK lost with no resend; targeted result/receipt corruption;
old writer/old GLEK rejection; collision preservation; installed/source/wrapper
parity; one configured model route; one fixer occurrence; one notification;
and exact stop. Full Git/PR/product-deploy and unrelated pipeline matrices are
not Stage A tests because those effects are unavailable.

## All-task classification

Classification is against the bounded Stage A outcome, not against eventual
incident completion. “Route slice” means only the named portion blocks Stage A;
the unexercised remainder is explicitly assigned to the follow-up map below and
does not count as completion of the full original task.

| Task | Class | Exact Stage A consumer / disposition |
| --- | --- | --- |
| T0.0 | `REDUNDANT_OR_MERGE` | Production containment decision is fully merged into T4.1 quarantine; `48e13e1...` remains required implementation substrate. |
| T0.1 | `REDUNDANT_OR_MERGE` | Effect freeze is fully merged into T3.2 temporary cutover fence plus T4.2 permanent tuple revocation. |
| T0.2 | `MUST_BEFORE_LAUNCH` | Accepted; preserves evidence before capacity/fence work. |
| T0.3 | `MUST_BEFORE_LAUNCH` | Route-sized byte/inode/WAL/receipt reserve and approved cleanup only. Broad capacity migration follows. |
| T0.4 | `MUST_BEFORE_LAUNCH` | Accepted; supplies exact v2 targets and unresolved rows for T4. |
| T1.1 | `MUST_BEFORE_LAUNCH` | Installed v3 raw-evidence admission and production owner lookup; prevents false CL1 admission. |
| T1.2 | `MUST_BEFORE_LAUNCH` | Installed on the first model/critique route; prevents failed critics becoming clean. Production proof completes during the canary. |
| T1.3 | `MUST_BEFORE_LAUNCH` | First model attempt consumes authenticated raw route evidence; current public self-attestation is blocking. |
| T1.4 | `MUST_BEFORE_LAUNCH` | Route slice only: deterministic finalizer rejection must stop or use one stable-fingerprint repair; no broad retry. |
| T1.5 | `MUST_BEFORE_LAUNCH` | Route slice only: one owner-backed occurrence, one claim, validated replay, and no live alternate recovery route. |
| T1.6 | `MUST_BEFORE_LAUNCH` | Route slice only: exclusive WBC for model/upload/start/stop/fixer/notification. All other effects disabled. |
| T1.7 | `FOLLOW_UP_EPIC` | Generic all-owner adoption is not consumed. Equivalent durability is mandatory in each Stage A owner and tested under T1.5/T1.6/T1.8/T1.9. |
| T1.8 | `MUST_BEFORE_LAUNCH` | Exact installed generation, writer fence, attestation, backup and rollback/forward-fix. |
| T1.9 | `MUST_BEFORE_LAUNCH` | Sole authorized upload/start/stop transaction. |
| T1.10 | `MUST_BEFORE_LAUNCH` | Route slice only: canonical identity before provenance, one initial send, silent unchanged scans, sticky ambiguity, no direct fallback. |
| T2.1 | `REDUNDANT_OR_MERGE` | Prior M11 invalidation is fully included in the append-only T4.1 quarantine/T4.2 revocation and scoped Release Authority decision. |
| T2.2 | `FOLLOW_UP_EPIC` | Full no-debt ticket corpus is broader than Stage A. A smaller exact canary integration manifest is mandatory but does not claim T2.2 complete. |
| T2.3 | `MUST_BEFORE_LAUNCH` | Route-scoped isolated `admit/run/verify` for the exact finite slice. Full ticket lifecycle remains follow-up. |
| T2.4 | `FOLLOW_UP_EPIC` | Complete installed suite includes Git/PR/product/unconfigured paths. Exact Stage A fault subset is mandatory in component/T3.5 evidence. |
| T2.5 | `MUST_BEFORE_LAUNCH` | Configure and prove exactly one physical canary route with no fallback. Platform-wide route inventory/conformance follows. |
| T2.6 | `FOLLOW_UP_EPIC` | Full zero-debt approval is too broad. Stage A needs a distinct scoped canary deploy decision; do not mislabel it T2.6 completion. |
| T3.1 | `MUST_BEFORE_LAUNCH` | Atomic just-in-time capacity, owner-head, evidence and vector recheck. |
| T3.2 | `MUST_BEFORE_LAUNCH` | Prevents old-generation writes during generation CAS. |
| T3.3 | `MUST_BEFORE_LAUNCH` | Installs exact tested generation through owner authority. |
| T3.4 | `MUST_BEFORE_LAUNCH` | Two-observer proof that live bytes/processes equal tested vector. |
| T3.5 | `MUST_BEFORE_LAUNCH` | Stage A recovery, rollback/forward-fix, fixer, notification, and stop canaries; broad residue follows. |
| T3.6 | `FOLLOW_UP_EPIC` | Full task includes closing both broad tickets. Stage A exact installed release receipt is mandatory; administrative/full-ticket closure follows. |
| T4.1 | `MUST_BEFORE_LAUNCH` | Exact v2 tuple quarantine and merged T0.0 decision. |
| T4.2 | `MUST_BEFORE_LAUNCH` | Denies every v2 effect/admission operation and merged T0.1 freeze. |
| T4.3 | `MUST_BEFORE_LAUNCH` | Advanced epoch/tombstone makes late writers and ABA reuse reject. |
| T4.4 | `MUST_BEFORE_LAUNCH` | All inventoried v2 GLEKs are terminal or sticky non-redispatchable; unresolved provider truth may remain explicit. |
| T4.5 | `MUST_BEFORE_LAUNCH` | CAS selection away from v2; marker remains byte-identical. |
| T4.6 | `FOLLOW_UP_EPIC` | T0.2 plus deny/fence preserves safety; archival/WORM/read-only resource freeze can follow T6.2. |
| T5.1 | `MUST_BEFORE_LAUNCH` | Real reviewer/coherence/proof/ownership/portfolio decisions must resolve; four are currently pending. |
| T5.2 | `MUST_BEFORE_LAUNCH` | Target-bound predicate is recomputed from raw evidence under fence. |
| T5.3 | `MUST_BEFORE_LAUNCH` | Defines fresh v3 subject and finite completion preconditions. |
| T5.4 | `MUST_BEFORE_LAUNCH` | Fresh noncolliding owner/publication identities; publication remains disabled. |
| T5.5 | `MUST_BEFORE_LAUNCH` | Exact installed local and read-only remote preflight. |
| T5.6 | `MUST_BEFORE_LAUNCH` | Finite-slice TTL, target transition, exact stop, owner queries and verifier challenge. |
| T6.1 | `MUST_BEFORE_FIRST_TRANSITION_ACCEPTANCE` | The authorized launch action itself. |
| T6.2 | `MUST_BEFORE_FIRST_TRANSITION_ACCEPTANCE` | Independent acceptance must be tightened to the transition past v2's stall, not mere initialization. |
| T6.3 | `MUST_BEFORE_FIRST_TRANSITION_ACCEPTANCE` | The bounded plan/critique/gate/finalize slice is necessary to reach and cross the old stall. |
| T6.4 | `FOLLOW_UP_EPIC` | Real CL2 feature execution follows the accepted bounded slice. |
| T6.5 | `FOLLOW_UP_EPIC` | Git/PR publication is not authorized in Stage A. |
| T6.6 | `FOLLOW_UP_EPIC` | CL3-CL5 ordinary completion. |
| T7.1 | `FOLLOW_UP_EPIC` | Accept/merge successor PR. |
| T7.2 | `FOLLOW_UP_EPIC` | Build product generation. |
| T7.3 | `FOLLOW_UP_EPIC` | Product-authorized deployment. |
| T7.4 | `FOLLOW_UP_EPIC` | Full production semantic/recovery scenarios. |
| T7.5 | `FOLLOW_UP_EPIC` | Product canary-window acceptance. |
| T8.1 | `FOLLOW_UP_EPIC` | Final completion manifest/proof map. |
| T8.2 | `FOLLOW_UP_EPIC` | Incident resolution after v3/product acceptance. |
| T8.3 | `FOLLOW_UP_EPIC` | Permanent release replay gate. |
| T8.4 | `FOLLOW_UP_EPIC` | Final operator card/runbook/policy. Stage A quiet-send mechanism is already required. |
| T8.5 | `FOLLOW_UP_EPIC` | Real 24h/72h/7d observation. |

## Explicit adjudication of disputed tasks

- **T1.1 blocks, but only the v3 path.** Seal/remove the public test-backend
  selector in production, provide positive owner lookup by intended plan ID,
  and require this v3 root's raw predicate. A platform-wide root-milestone
  allowlist and wholesale revisioned ChainState migration can follow if raw
  launch aliases are already denied and projections cannot grant.
- **T1.2 blocks.** The canary necessarily runs critics before it can cross the
  old finalizer stall. Its selected occurrences must have immutable attempt
  health and exact-set reduction. This is not optional platform hardening.
- **T1.4 blocks only as a route safety rule.** A rejection may terminally stop;
  success does not require a generalized repair platform. If a repair is
  enabled, it is one exact fingerprint/object/bundle occurrence. Every broad
  retry/reset path is denied.
- **T1.6 blocks only for the five Stage A effect families.** Git/PR, product
  deploy, unrelated pipeline/model, webhook, and generic subprocess adoption
  can follow because the Stage A generation makes them unavailable.
- **T1.7 does not block as a generic migration.** No Stage A owner may use
  corrupt-to-empty, unlocked rewrite, or non-durable sequence logic; that
  property can be established in the local owner implementations without
  adopting one generic store everywhere.
- **T1.9 fully blocks.** It is the only legitimate launch/stop authority and
  currently exists only as preparation.
- **T2.1 is merged**, not independently sequenced. One append-only quarantine,
  revocation and scoped release decision removes stale M11 authority; a second
  ceremonial invalidation adds no safety.
- **T2.2 does not block in full.** Exact route-scoped integration evidence does.
- **T2.3 blocks in its finite-slice form.** It proves the actual contract before
  production.
- **T2.4 does not block in full.** The subset capable of false success,
  duplicate effect, unsafe retry, lost evidence, notification amplification or
  broken fence on Stage A is mandatory and enumerated above.
- **T2.5 blocks only for the allowed route set.** Minimize the set to one exact
  physical route and zero fallback. Expanding the allowlist later requires its
  own canary.
- **T2.6 does not block as written.** A narrower owner-signed deploy decision is
  mandatory; the full zero-debt decision remains a Stage B obligation.

### T1.5's 741 skipped assertions

The canary does not need all 741 historical assertions re-enabled. It does need
an exact generated and runtime inventory proving that every normally callable
public/import/direct-module/internal alias on the installed generation that can
repair, copy, create a goal, launch a child, or cause an effect either reaches
the canonical owner or fails before mutation. The reproduced
`repair_source_initiative`, `repair_goal ensure`, managed-agent internal launch,
caller-minted authority/fix-the-fixer, forged stored-result replay, and
provenance-detail amplification cases all block.

Blanket module skips are unacceptable evidence while their subjects remain
live. Assertions solely about removed/tombstoned code may be archived with a
replacement dynamic denial test. Exhaustive historical cleanup, test
reorganization, and unrelated retired modules belong in Stage B.

### T1.10 key rotation, reminders and child chunks

For Stage A, use one pinned, unexpired owner/provider key whose validity exceeds
the generation decision, launch TTL, canary and reconciliation window. Expiry or
revocation fails closed. A full signed key-rotation protocol is follow-up.

Disable reminders and payload chunking in the canary generation. One message
must fit one provider request and one GLEK; an oversized message fails without a
provider call. Therefore reminder buckets and child chunk GLEKs are not Stage A
requirements. They become mandatory before those features are enabled. The
currently reproduced direct Discord/AgentBox/exception-fallback writers,
unbound runtime, absent production owner/supervision, and duplicate/ambiguity
paths do block Stage A.

## Required owner and deployed evidence

Local implementation acceptance, integration acceptance, deployment, and
production acceptance are separate gates:

| Level | Minimum evidence |
| --- | --- |
| Local component | Exact commit/tree/parent; clean worktree; finite counterexample matrix; source + wheel/import parity; independent decision. |
| Integration | One descendant of `6787d636...`; component ancestry and conflict manifest; frozen owner/schema/help/contract digests; exact configured route/effect allowlists; installed-package build; integrated bypass/fault tests. |
| Deploy eligibility | Owner-signed, expiring canary decision binding candidate, generation, capacity receipt, rollback/forward-fix, route/effect allowlists, tests, owner heads and exclusions. |
| Installed generation | GEN-DEPLOY intent/CAS/receipt; exact prior/new selector; process-birth and writer identities; backup/migration; two independent live-vector observations; old-writer rejection. |
| v2 retirement | Run Authority quarantine/revocation heads; Custody advanced epoch/tombstone; WBC per-GLEK terminal/indeterminate no-redispatch report; selection CAS; unchanged marker hash. |
| v3 admission/launch | Accepted raw CL1 predicate; fresh identity inventory; collision reservations; signed finite-slice envelope; WBC parent/child intents; exact upload/start receipts; one runner; pre-issued stop. |
| First-transition acceptance | Attempt/raw-route/bundle/semantic receipts; exact critique completeness; graph admission/repair receipt; Run Authority transition past old cursor; current Custody/WBC/generation heads; no duplicate fixer/notification; independent verifier decision. |

## Launch GO/NO-GO predicate

### GO to issue T6.1 only if

All predicates below are true, current, unexpired, nonrevoked and bound to the
same integration commit/tree and installed generation:

1. T0.2/T0.4 rehash; route-sized storage reserve; exact owner heads readable.
2. Independent local/integration acceptance of the finite candidate, with no
   unresolved reproduced ordinary-path counterexample in the Stage A surfaces.
3. Production RA, Custody, WBC, Release, Launch, Recovery, Notification and
   observer endpoints are installed and cannot be caller-selected or replaced
   by a hermetic backend.
4. Live-vector attestation and rollback/forward-fix canaries are accepted.
5. V2 quarantine, effect deny, advanced epoch, no-redispatch GLEKs and selection
   CAS are independently current.
6. CL1 predicate is true from raw target-bound evidence and all required owner
   decisions; v3 identity set is fresh and transactionally reserved.
7. Exactly one physical model route is enabled and has an installed live
   canary; all fallbacks and unproved effect families are unavailable.
8. The exact launch/stop contract, finite phase/cursor budget, TTL, WBC child
   manifest and verifier query are signed and independently recomputed.
9. The production failure canary proves one occurrence/claim/fixer result, one
   initial notification outcome, 200 silent unchanged observations, and sticky
   provider ambiguity with no resend.

Any `UNKNOWN`, missing row, stale head, owner disagreement, capacity shortfall,
route mismatch, collision, old-writer success, or absent stop capability is
NO-GO. No status projection may repair the predicate.

### Accept T6.2 only if

- owner records prove one exact v3 runner and no duplicate launch/effect;
- every mandatory critic occurrence has one accepted succeeded attempt/result,
  or the canary has stopped without false success;
- the graph is admitted under the frozen bundle or consumed its one authorized
  narrow repair;
- Run Authority records a transition strictly beyond v2's last accepted
  `gated/finalize` cursor, with current Custody and WBC joins;
- no v2 writer/effect is accepted, no notification is repeated, and owner
  projections independently agree; and
- the envelope has expired or the verifier has invoked/confirmed the exact
  stop/fence before any execution/publication authority is available.

If the finalizer fails safely, Stage A has proved safety but has **not** achieved
the requested transition; T6.2 remains unaccepted. A new attempt requires a new
owner decision/envelope after evidence review, never an automatic relaunch.

## Finite reviewer stop rule

Freeze the candidate identity, Stage A surface inventory, effect allowlist,
model route, state target, counterexample matrix and evidence schema before the
authoritative integration run. Once every GO predicate above has exact accepted
evidence, review stops and launch may proceed.

A later finding may reopen the launch gate only if it provides one of:

1. a reproducible ordinary public/import/direct-module/installed path on the
   exact candidate or deployed generation that can create false success,
   caller-minted authority, duplicate launch/effect/notification, blind resend,
   lost/corrupt owner evidence, unsafe response-loss reconciliation, or broken
   v2/generation fence on the Stage A route;
2. an exact mismatch, revocation, expiry, collision, capacity failure or owner
   disagreement in a GO receipt; or
3. proof that a supposedly disabled surface remains reachable from the Stage A
   installed entrypoints.

The gate does not reopen for an unexercised pipeline/effect/route, a speculative
refactor, arbitrary interpreter/code-object takeover, platform-wide
consistency, archival/docs work, long observation, key rotation while the
pinned key remains valid, or tests of a feature that is demonstrably absent and
hard-denied. Such findings enter the follow-up epic unless they produce one of
the concrete counterexamples above.

## Recut follow-up epic

The current six-milestone draft is **missing deferred prelaunch hardening**. Its
M1 begins ordinary CL2 completion immediately after T6.2, while its proof map
contains only T6.3-T8.5 plus deferred T3.6/T4.6. It omits the deferred residue of
T0.3; T1.1-T1.7, T1.9-T1.10; T2.2/T2.4-T2.6; and scoped T3.5. That debt must be
explicit and must close before authority expands from the bounded canary to
ordinary execution/publication.

Recommended eight milestones:

| Milestone | Outcome and preserved obligations | Expansion rule |
| --- | --- | --- |
| F1. Owner/storage/recovery hardening | Complete T0.3 residue; platform owner-store T1.7 adoption; full T1.5 legacy retirement and honest disposition of 741 assertions; full T1.10 key rotation/reminders/chunk GLEKs; remaining T1.8/T1.9 owner/store generalization; T4.6 may prepare but not rewrite evidence. | No v3 execution or publication authority yet. |
| F2. Admission/model/effect release closure | Generalize T1.1-T1.4; migrate every production effect family under T1.6; complete platform T2.2, full T2.4, all configured T2.5 routes, full T2.6 zero-debt decision, broad T3.5 canaries, and close the two T3.6 release tickets. Permanent exact incident replay becomes a required candidate test. | Only after F1/F2 may authority expand beyond the accepted finalize canary. |
| F3. CL2 real work and publication | T6.4 executes real feature work; T6.5 creates exactly one publication outcome. Any remaining ordinary T6.3 evidence is consolidated here without re-running the accepted canary. | Requires F1/F2 completion manifests and current generation attestation. |
| F4. CL3-CL5 epic completion | T6.6 advances every milestone from exact predecessor manifests with ordinary critique/execution/publication receipts. | No product deployment yet. |
| F5. Product merge/build/deploy | T7.1-T7.3: merge, content-addressed product generation, explicit product Release Authority, rollback/forward-fix and fenced deploy. | Production canary authority only. |
| F6. Product production acceptance | T7.4-T7.5 hostile semantic, restart, recovery, notification, ambiguity and ENOSPC scenarios plus declared canary window. | Incident remains open until accepted. |
| F7. Evidence and incident institutionalization | T4.6 final freeze; T8.1-T8.4 completion/proof map, v2 resolution without rewrite, permanent release gate, operator card/runbook/policy. | Does not claim durability window. |
| F8. Real durability windows | T8.5 signed observations at 24h, 72h and 7d against the same accepted generation; reset the window on ownership/generation change. | Final closure only after 7d independent acceptance. |

F1 and F2 may run in parallel on disjoint owners but must join before F3. This
keeps broad platform perfection off the one-transition canary without allowing
the deferred defects to disappear or trail behind broad production authority.

## Progress estimate

- **Toward issuing the bounded launch:** **18-28%** evidence-weighted complete.
- **Toward independently accepting the transition past the old stall:**
  **12-22%** evidence-weighted complete.

The lower second range reflects the absence of accepted T1.2/T1.4/model-route
integration and any real T6.3 execution. The launch range credits accepted
T0.2/T0.4, the locally accepted RA-CONTAIN substrate, substantial but unaccepted
T1.1/T1.8 candidates, prepared T2-T5 matrices, and the clean common ancestor.
It heavily discounts active or hard-failed candidates, gives zero credit for
production owner receipts, deployment, v2 fencing, v3 admission/launch, and
does not count preparation prose as execution.

These ranges are neither equal-task completion, calendar estimates, nor
probabilities of success. The formal checklist remains 2/55 accepted. They
measure how much evidence-bearing work on the **shortened Stage A critical
path** exists today; Stage B product completion and observation are outside both
ranges.

## Disagreements

### With Luna

Luna is correct that T4.6 and T6.4 onward should not block the canary, and that
local code is not production authority. Luna is too broad in requiring all of
T1.7, T2.2, T2.4, T2.5, T2.6 and full T3.6 before launch. Their unexercised
platform portions have no Stage A consumer. Luna also puts all T6.3 after T6.2;
that would accept an initialization transition without proving movement beyond
the actual v2 stall. The bounded T6.3 finalize slice must precede acceptance.

### With root

Root correctly narrows owner-store adoption, cross-pipeline conformance,
archival and observation. Root is too narrow if its six bullets omit T1.1,
T1.2 and the route-safe T1.4 behavior. It is also unsafe to read “one-transition
envelope” literally from a fresh start. The envelope must authorize the finite
prerequisite phase slice and exactly one target acceptance past the old cursor,
then stop. Root's notification and fixer bullet must include the reproduced
ordinary import/direct-module bypasses and owner-bound replay; dedupe alone is
not sufficient.

## Mutation statement and report digest

No code, Git, checklist, cloud/provider state, owners, markers, plans, processes,
deployments, or existing reports were changed. This result report is the only
write.

Canonical report SHA-256 (computed over the UTF-8 file with the 64 hexadecimal
characters on the next line replaced by 64 ASCII zeroes):

`6d4feeadeb123c500d98f855537d5af997fb5b631b30712bd54e6338a334dfa6`
