# Sol launch cutline — Critique VJ24 recovery

Date: 2026-08-05
Reviewer: GPT-5.6 Sol, high reasoning, read-only
Package reviewed: `.megaplan/initiatives/critique-ledger-post-relaunch-completion/`

## Decision

Current status is **NO-GO**. The safe launch cutline is smaller than the
aborted migration sprint, but larger than commits `7e3dfc0980` and
`b399febc7d`. The original r5/VJ24 occurrence remains immutable and
quarantined; no generic resume or fresh duplicate may be used.

The clean branch's 43-test receipt is not a VJ24 acceptance receipt: it is two
new finalize tests plus 41 existing execute tests. It does not cover the live
missing-selector/defer path. Further, the selector patch automatically widens
`write_set.paths`; a missing selector must not silently become write authority.

The candidate branch has Run Authority contracts/reduction/read logic but no
proven authoritative Run Authority journal writer or atomic compare-and-append
API. The current override WBC path can synthesize grant/fence/lease/outbox
records, and the action validator is shadow/syntax-only by default. Those paths
cannot authorize this migration.

## Minimum launch cutline

### MUST code

1. Shared selector normalization used by Finalize and Execute:
   - existing selector: run it;
   - missing selector explicitly declared in that task's finalized
     `write_set.paths`: persist `DEFERRED_TASK_OUTPUT`;
   - missing undeclared selector: fail finalization/admission;
   - after the task returns an accepted result envelope, rerun the deferred
     validation; continued absence or missing acceptance blocks completion.
2. Port the narrow missing-selector/defer behavior from `c9239cfe79`, including
   the monotonic deadline correction, and add the post-task rerun. The existing
   `task_contract_hash` is sufficient for the first child; the new
   cross-consumer `selector_task_output_contract.v1` belongs in F2.
3. Add a dedicated `occurrence_child_migration.v1` prepare/commit coordinator
   outside the generic override workflow. It coordinates canonical owners and
   emits a non-bearer receipt; it does not create a fourth authority.
4. Provide or prove a real Run Authority owner API:
   `read_view(run_id, revision) -> records + integer journal_cursor` and
   `compare_and_append(run_id, revision, expected_cursor, records)`, atomically
   appending parent quarantine/migration and fresh child grant/fence records.
   This is VERY HARD if no deployed writer exists.
5. Commit effect-free through canonical Custody/WBC owners, with deterministic
   idempotency and crash recovery between each owner write. Reserve one stable
   launch GLEK. No provider call occurs during prepare/commit.
6. Immediately before dispatch, independently reread Run Authority's integer
   journal, Custody lease/epoch, and WBC attempt/GLEK. The receipt alone never
   grants authority.
7. Reject launch/resume targeting quarantined r5 and duplicate child/GLEK.

### MUST evidence/tests

- Exact pinned r5 plan/chain/source/runtime/validator/interpreter/import and
  task-contract identities.
- Authoritative parent Run Authority records and integer journal cursor; never
  a reducer view synthesized from batch artifacts.
- Authoritative Custody/WBC state showing no active parent lease/attempt and no
  ambiguous prior child effect.
- Clean candidate commit/tree, focused test receipt, and host-installed runtime
  attestation.
- Operator migration decision bound to the parent occurrence and deterministic
  child key.
- Missing declared selector defers; missing undeclared selector fails; existing
  selector runs; deferred selector reruns after an accepted task result.
- Empty/missing result envelopes cannot satisfy T18/T23.
- Finalize/Execute normalization and task-contract hash agree; post-finalize
  mutation fails.
- Stale integer cursor rejects with no owner/provider effect; exact migration
  retry is a no-op; divergent same-key retry conflicts.
- Concurrency and crash-after-each-owner-write produce one child, one journal
  append, one Custody lease, one WBC attempt, and one GLEK.
- Generic resume, `--fresh`, `recover-blocked`, raw parent `chain start`, and
  synthesized records remain denied.

### Operator sequence

1. Promote one exact reviewed commit as a content-addressed host runtime.
2. Verify interpreter/import roots, profile, chain bytes, task contract, and
   owner-store endpoints.
3. Reread the parent owner records and integer journal cursor.
4. Call effect-free migration `prepare`.
5. Call idempotent `commit` with the parent cursor.
6. Independently reread all owners and validate the non-bearer receipt/GLEK.
7. Run provider/credential/runtime preflight.
8. Invoke the dedicated migrated-child launch once.
9. Observe canonical child state; PID/tmux/marker/acknowledgement is not proof.

## Follow-up placement

- F1 (`briefs/f1-owner-storage-recovery-hardening.md`): general migration and
  recovery lineage, authoritative CAS rereads, crash recovery, parent fencing,
  host coherent observation, notification custody, and earlier-r5 evidence
  disposition.
- F2 (`briefs/f2-admission-model-effect-release-closure.md`): the full
  `selector_task_output_contract.v1` across Finalize/admission/Execute/auditor/
  VJ19/VJ24, accepted-result enforcement, all retained entry-point containment,
  provider resolver/runtime parity, and exact concurrent VJ24 replay.
- F3–F8: ordinary CL2 work, CL3–CL5, release/deploy, production acceptance,
  closeout, and 24h/72h/7d durability.
- `UNFINISHED_WORK.md` and the Custody Control Plane retain broad retirement,
  storage/ENOSPC, key/reminder policy, and unrelated effect-family work.

## Venue decision

Author and test locally in a clean worktree. Cloud is for exact promotion,
installed-generation verification, authoritative owner reads, migration commit,
and the long-lived child. Do not revive the aborted cloud implementation plan.

## Prelaunch receipt versus T6.2

The prelaunch receipt `arnold.megaplan.r5_vj24_migrated_child_receipt.v1` must
contain immutable parent identity/quarantine, `same_occurrence_resume=false`,
integer parent journal CAS, child Run Authority/Custody/WBC identities,
deterministic key, selector classification/task-contract hash, owner rereads,
`provider_effect_started=false`, and its digest. It must not claim VJ24/T18/T23
success.

T6.2 later adds accepted child VJ24, T18/T23 envelopes, child lifecycle cursor
advance, post-advance owner rereads, and proof of no duplicate effect.

## No-go conditions and duration

Remain `INDETERMINATE` if any owner writer/CAS is missing, the parent cursor is
not authoritative, records are synthesized, selector widening remains, a prior
child/effect is ambiguous, crash recovery can duplicate, installed runtime
differs, or current owner rereads are absent/contradictory.

Estimated duration: about 3 working days if real owner writers already exist;
about 8–12 working days if a general Run Authority journal writer/CAS and
cross-owner crash recovery must be built. The latter is the evidence-supported
default until deployment proves otherwise.
