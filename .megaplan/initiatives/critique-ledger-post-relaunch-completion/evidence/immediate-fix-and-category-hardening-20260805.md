# Immediate fix and category-wide hardening handoff

Date: 2026-08-05

Incident: `critique-ledger-accountability-v3-r5-20260803`

Blocked occurrence: VJ24 / plan `cl2-wbc-backed-ledger-20260803-1357`
Owning epic: `critique-ledger-post-relaunch-completion`

This is the canonical handoff produced by the evidence-first
`superfixer-debug` process. It joins the immediate route to recover safely with
the longer route that closes this category of failure. It is planning input, not
permission to launch.

## Evidence and judgement

Primary evidence:

- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage2.md`
- `.megaplan/incident-ledger/evidence/luna/critique-v3-r5-vj24-20260805/README.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-host-preflight.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-follow-up-crosswalk.md`
- `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-launch-cutline.md`

The first broken contract is the selector/task-output contract: VJ24 could not
resolve a selector that earlier plan metadata treated as a prospective T18
output. T18 never produced an accepted result. The evidence cannot yet safely
distinguish a declaration-reader bug, stale declaration, or plan/runtime
revision split.

The deeper failure is the absence of one immutable occurrence-bound causal
history joining execution evidence, runtime/chain binding, repair custody,
observation, and effects. This is both an adherence failure and a missing
structure; it is not fixed by editing `state.json`, creating the selector by
hand, or restarting a runner.

The launch-cutline review also rejects the current selector patch as sufficient
by itself: its 43-test receipt does not exercise the live VJ24 missing-selector
path, and automatically widening `write_set.paths` can grant inferred write
authority. The immediate fix must use the explicit-declaration/deferred-output
rule and post-task rerun; the full cross-consumer selector schema remains F2.

## Immediate route — get the work moving safely

Current r5 remains quarantined. The host preflight found a stale box snapshot,
dead/blocked process evidence, duplicate legacy projections, and no accepted
migration receipt. Therefore:

1. Capture a fresh host/provider-authoritative snapshot and the complete identity
   tuple: run/revision, occurrence/fingerprint, plan/chain/selector hashes,
   source/tree, runtime/import/interpreter, validator/wrapper/config/schema,
   Run Authority fence, Custody lease/epoch, WBC attempt/effect, repair request,
   and notification intent/effect/`INDETERMINATE` state.
2. Resolve the selector using the pinned VJ19/VJ24 readers and one normalized,
   content-addressed selector-to-producer map. Classify it as legitimate
   prospective output, stale declaration, revision split, or `INDETERMINATE`.
3. If identities crossed an unaccepted binding, preserve r5 and create an
   authority-approved migrated child run revision. The migration receipt must
   link VJ24 as parent and establish a fresh Run Authority fence, Custody epoch,
   and WBC attempt.
4. Submit exactly one occurrence-bound repair request through
   `request → Run Authority decision → Custody claim/epoch → WBC attempt/effect
   → verification`, using deterministic idempotency/CAS.
5. Use only the supported migration/new-attempt lifecycle operation after all
   gates pass. A generic resume, `chain start`, `--fresh`, marker edit, watchdog
   action, or launch acknowledgement is not an accepted recovery.
6. Prove the original occurrence is immutable/quarantined, the migration receipt
   is accepted, and the CAS cursor advances under the new lineage. The fresh
   child then produces the accepted VJ24 result and T18/T23 envelopes; those are
   post-launch evidence for the T6.2 handoff, not prerequisites for launching
   the child.

If the host snapshot, authority, identity, or migration operation remains
unavailable, the correct outcome is `INDETERMINATE` and the run stays gated.

## Category-wide solution — update this epic to close the class

The owning epic must treat this handoff as a required planning input and update
its existing F1/F2 milestones (not create another authority or silently drop
unfinished work):

- F1 must integrate occurrence-bound repair through Run Authority-owned
  grant/CAS/idempotency, Custody-owned occurrence/lease/epoch and WBC-owned
  attempt/effect evidence; bind exact wrapper and runtime/source/test identities;
  and persist notification intent/effect evidence. A fixed-socket component is
  an adapter, not a fourth owner.
- WBC owns the versioned `selector_task_output_contract.v1` declaration/evidence;
  F1 binds its exact digest into migration/repair lineage and F2 enforces that
  same hash plus accepted result envelopes across every consumer.
- F2 must enforce one non-bearer canonical action-envelope receipt and one role-scoped provider resolver at
  every launch/resume/override/adoption/replay entry point; shared credential
  bootstrap and redacted capability attestation must run before lease and on
  resume; provider facts are admission evidence only, and marker/PID/tmux-only
  liveness must fail closed.
- F1/F2 must add host-side snapshot-first observation with bounded live fallback,
  projection/attempt/generation reconciliation, legacy-session classification,
  and durable notification deduplication.
- Every load-bearing category contract and retained state-mutating entry point/
  effect class must have source, installed-generation, crash/restart,
  hostile-replay, migration, and exact-once regression evidence; retired or
  disabled routes need denial/no-capability proof. The mandatory
  VJ24 replay must yield one repair request, one Custody claim, one WBC attempt,
  one notification intent, and at most one provider effect.
- F3–F8 remain responsible for ordinary CL2/CL3/CL5 completion, release,
  production acceptance, incident closeout, and 24h/72h/7d durability. None may
  claim the category fixed merely because a canary advances.

The category is closed only when the durable contract, immutable identity/history,
canonical custody path, observer/effect controls, and retroactive regression
proof pass across every retained state-mutating Critique entry point/effect
class, with all unproven surfaces denied. A single successful r5 relaunch is not
sufficient. Broad historical platform storage, retirement, key-policy and
unrelated release-matrix work remains explicitly deferred to the Custody Control
Plane and is not an immediate relaunch or ordinary Critique cutline.

## Epic update and launch posture

This handoff is linked from the initiative README and F1/F2 briefs. The epic
remains intentionally launch-gated until the committed T6.2 safe-v3 handoff and
acceptance manifest exist. That handoff must embed a content-addressed accepted
r5 migration/recovery receipt: immutable quarantined parent, explicit
same-occurrence prohibition, causally linked child/new attempt, fresh Run
Authority/Custody/WBC identities, selector-contract proof, and CAS cursor
advance. The later accepted VJ24 and T18/T23 envelopes are attached to the
same T6.2 handoff only after the migrated child runs. Updating these planning
artifacts does not mutate cloud state or authorize a relaunch.

Status at handoff: `r5=BLOCKED/QUARANTINED`; `follow-up epic=DEFINED BUT NOT
LAUNCH-READY`.
