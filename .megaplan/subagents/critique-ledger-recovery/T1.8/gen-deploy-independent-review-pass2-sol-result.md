# T1.8 GEN-DEPLOY independent completion review — pass 2b

## Overall verdict: HARD FAIL

Both questioned findings are real. Either is sufficient to prevent local T1.8
acceptance:

1. replacing the ancestor directory of an actively held hermetic lock creates a
   second exclusion domain and permits overlapping holders; and
2. backup/restore is represented by signed digest strings but is never executed,
   while recovery cannot repair an accepted active generation whose installed
   generation becomes unavailable.

These violate T1.8's concurrency/cutover and backup-restore/
rollback-or-forward-fix/installed-vector requirements. Green focused and wheel
tests do not override the semantic counterexamples.

## Candidate identity and review inputs

- Worktree: `/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`
- Commit: `dae901e9bf2ecf289ad0aa201c50116f8bf1f899`
- Tree: `ba7662aa9b0174084ee9436c90f1ebab60a3976f`
- Parent: `69be00087f0d469b1e551fa8617c257f28783b7a`
- Subject: `repair GEN-DEPLOY authority boundaries`
- Initial and final `git status --short`: empty (clean)

Commands/results:

```text
$ git status --short
<no output>
$ git rev-parse HEAD
dae901e9bf2ecf289ad0aa201c50116f8bf1f899
$ git rev-parse HEAD^{tree}
ba7662aa9b0174084ee9436c90f1ebab60a3976f
```

The exact prior implementation result and review briefs were inspected:

```text
893b60efdc8e57ace1b7ca1b7a55038148c3d81598f07835e5113ffd992317ce  gen-deploy-repair-pass1-sol-result.md
2d104f94595106fd9cfe2663816b41b3885144526334ce1d3f5ea659aa60fefb  gen-deploy-independent-review-pass2-sol-brief.md
0861f0d0895518af27178dc50cec9e6cdd6da8cbd6e418fefbe38d9446f2ef82  gen-deploy-independent-review-pass2b-sol-brief.md
```

The implementation result's item 8 claims a stable parent-directory lock,
active-holder replacement defense, and two-process exclusion. It correctly
limits this to hermetic defense and says production requires privileged
descriptor custody and complete-session ancestor/object replacement prevention.
The pass-2 brief explicitly requires attacks on ancestor replacement,
backup/restore, rollback/forward-fix, and installed-vector parity.

The earlier stopped review's supplied results are accepted as established and
were not needlessly rerun here: focused runtime `143` tests plus `2` subtests;
installed-wheel `5/5` at Pydantic 2.11.0 and locked 2.12.5; detached Git-archive
wheel `5/5`; and byte identity for all 11 shipped Release Authority Python
files. This review minimally reproduced only the two unresolved findings.

## Finding 1 — ancestor replacement splits the execution-lock domain

Severity: blocking.

`DeploymentStore.__init__` learns `_lock_parent_identity` independently for
each new instance from the current pathname (`store.py:140-146`).
`execution_lock()` later opens and locks that current parent inode
(`store.py:366-422`). If the parent/ancestor is renamed and the canonical path is
recreated, the original holder retains locks on displaced inodes while a fresh
store learns and locks the replacement inodes. Exit revalidation
(`store.py:423-430`) detects the change only after the protected body and its
effects have already run.

The existing active-holder test (`test_repair_regressions.py:918-968`) replaces
only `authority.lock`. Its unchanged parent-directory lock serializes that case
and therefore does not cover ancestor replacement.

### Minimal disposable reproduction

The probe used `tempfile.TemporaryDirectory`, the real `AuthorityAnchor`, and
the real `DeploymentStore`. Process A acquired `execution_lock`; the parent
renamed its containing directory, recreated the canonical directory, and
constructed a second store from the same anchor; process B acquired the new
lock before A was released.

Command shape:

```text
$ uv run python - <<'PY'
# create a hermetic anchor/store under TemporaryDirectory
# fork holder A and wait until A is inside store.execution_lock(...)
# os.rename(live, displaced); live.mkdir(); construct DeploymentStore at live
# enter B's execution_lock while A's release event remains unset
PY
```

Exact result:

```text
second_acquired_while_first_held=True
first_exit=hermetic_lock_identity_changed child_exitcode=0
```

The late error does not roll back or neutralize effects already performed in
A's protected body. Two fencing/CAS/recovery effect streams can therefore
overlap. This is a direct T1.8 concurrency and cutover violation and also
intersects T1.7 owner-store concurrency. Byte-identical wheel/source parity
only proves that the installed wheel contains the same behavior.

The four existing nearby tests still pass:

```text
$ uv run pytest -q \
  tests/arnold_pipelines/release_authority/test_repair_regressions.py::test_hermetic_rejects_hardlinks_and_lock_replacement \
  tests/arnold_pipelines/release_authority/test_repair_regressions.py::test_hermetic_rejects_symlink_and_hardlink_lock_aliases \
  tests/arnold_pipelines/release_authority/test_repair_regressions.py::test_two_processes_share_one_stable_lock_inode \
  tests/arnold_pipelines/release_authority/test_repair_regressions.py::test_lock_replacement_during_active_holder_never_creates_concurrent_domain
....                                                                     [100%]
4 passed in 6.31s
```

### Smallest root repair

Do not learn the trusted exclusion-domain identity afresh in each constructor.
Provision one custody root whose object identity and complete protected
directory ancestry are durably and cryptographically bound to the authority
anchor/store genesis. Every opener must validate that pre-existing identity
before SQLite access or lock acquisition. Resolve the store, lock, WAL/SHM, and
target relative to retained no-follow descriptors, retain the serialization
descriptor for the entire operation, and revalidate before each effect and at
exit. Recreating the canonical pathname must fail closed; it must never create
a new authority or exclusion domain for the same signed anchor/store.

Production still needs the privileged venue promised by `production.py:149-152`
to prevent rename/unlink/replacement of every protected ancestor/object for the
complete descriptor lifetime. A Python pathname check is not a substitute.

### Exact required tests

1. `test_fresh_store_cannot_repin_recreated_lock_parent`: replace the parent,
   clone/reopen the initialized store, and prove the same anchor rejects the new
   ancestry instead of learning it.
2. `test_ancestor_replacement_during_active_holder_never_creates_concurrent_domain`:
   the two-process reproduction above; B must never enter through the
   unauthorized replacement tree, before or after A releases.
3. `test_each_protected_ancestor_replacement_fails_closed`: parameterize the
   immediate parent and every higher protected ancestor for store, lock,
   WAL/SHM, and target root.
4. `test_ancestor_replacement_during_cutover_cannot_duplicate_effect_or_cas`:
   place barriers inside real deployment/CAS execution and prove at most one
   effect stream and one accepted selector transition.
5. Repeat the ancestor-race test through an isolated installed wheel, outside
   the source checkout.

## Finding 2 — backup/restore is digest echo, not executable recovery

Severity: blocking.

The recovery contract contains only `strategy`, `backup_digest`,
`compatibility_digest`, and `restore_test_digest` (`contracts.py:347-351`). The
recovery receipt repeats those strings (`contracts.py:852-858`). Receipt
validation only compares the echoed strings with the signed decision
(`executor.py:359-377`). `HermeticAdapter.verify_recovery()` records the
decision digest and returns the same three caller-authorized digest fields
without opening a backup or restoring anything (`executor.py:949-963`).

The recovery-resolution contract likewise contains selector/revision/effect
metadata but no backup locator, restored state/vector, or observed restored-byte
evidence (`contracts.py:419-427`, `518-539`). Hermetic forward-fix selects,
starts, and attests already-recorded fake metadata (`executor.py:1235-1259`);
rollback only rewrites selector/runtime JSON (`executor.py:1260-1278`). Neither
restores missing or damaged bytes. Independent recovery verification compares
the receipt with the same adapter projection and, only for forward-fix, its
synthetic installed attestation (`verifier.py:61-190`).

Static inventory confirms there is no Release Authority backup/restore
implementation or executable test: 

```text
$ rg -n -i "backup|restore|restore_test|compatibility" \
    arnold_pipelines/release_authority \
    tests/arnold_pipelines/release_authority --glob '*.py'
```

The matches are limited to the contract/receipt fields, echo/comparison sites,
the rollback-incompatibility negative test, and arbitrary repeated-character
digest fixtures. There is no backup creation/open, isolated restore, restored
byte/vector comparison, or damage-and-recover exercise.

### Minimal disposable reproduction

The probe used the real fixture, store, adapter, and recovery entrypoint in a
`TemporaryDirectory`. It completed a deployment, removed the selected
generation from the adapter's available generation data, confirmed generation
verification now failed, and tried both signed recovery strategies.

Command shape:

```text
$ uv run python - <<'PY'
# build tests/.../conftest.py::authority in TemporaryDirectory
# execute_deployment(...)
# remove active generation digest from HermeticAdapter state['available']
# adapter.verify_generation(...)
# execute_recovery_resolution(...) for rollback and forward-fix
PY
```

Exact result:

```text
initial_outcome deploy-accepted
damaged_active True
verify_generation_after_damage generation_unavailable
rollback recovery_result indeterminate_deployment_missing
forward-fix recovery_result indeterminate_deployment_missing
generation_restored False
selector_unchanged True 1
```

Recovery resolution is limited to an unresolved `deploy-indeterminate`
deployment (`store.py:1114-1125`). It cannot recover a damaged accepted active
generation. The authoritative selector can continue to claim the generation at
revision 1 while generation verification says it is unavailable.

This violates the explicit T1.8 requirement to test backup restore and a
migration-compatible rollback or forward-fix, the permanent-prevention rule
that backup restore must be tested and incompatible rollback must forward-fix,
the P3 exit criterion that backup restoration and rollback/forward-fix are
tested, the go/no-go migration/backup/recovery gate, and the mandatory named
equivalent `test_backup_restore_and_forward_fix_are_executable`. It also leaves
the post-recovery installed-vector invariant unproved.

### Smallest root repair

Replace digest echo with an executable, independently observable recovery
contract:

- bind a content-addressed backup artifact/locator, source state and schema
  vector, expected restored vector, and compatibility decision into the signed
  recovery authority;
- before cutover, actually open and authenticate the artifact, restore it into
  an isolated location, and prove restored bytes/state/vector equal the signed
  expectation; derive the receipt from observed results, not supplied digest
  labels;
- make rollback actually restore the exact compatible prior generation and
  state under fence, or make forward-fix materialize, migrate/repair, verify,
  select, start, and attest a separately signed immutable generation;
- support fenced recovery of a damaged accepted active generation, not only an
  indeterminate deployment; and
- preserve the existing durable-intent, exact-idempotency, response-loss,
  reconciliation, crash, and independent-observation rules for every restore
  effect.

### Exact required tests

1. `test_backup_restore_and_forward_fix_are_executable`: create a real backup,
   damage active bytes/state, restore, and compare the complete result byte for
   byte with the expected installed/state vector.
2. Missing, corrupt, truncated, wrong-digest, wrong-locator, path-substitution,
   and non-restorable backups must fail before selector CAS and leave the target
   unchanged.
3. `test_migration_then_binary_failure_obeys_rollback_compatibility`: compatible
   state performs real binary rollback; incompatible state rejects rollback and
   executes a separately signed/materialized forward-fix generation.
4. Damage an accepted active generation and prove the fenced recovery API can
   restore or forward-fix it; `indeterminate_deployment_missing` is not an
   acceptable terminal answer.
5. Inject crash before/after restore intent, backup read, restore write, fsync,
   selector CAS, runtime start, and receipt commit; also inject
   effect-then-error and invalid/missing receipt. Exact replay must converge or
   remain fenced/indeterminate without duplicate effects.
6. Independent verification must reject digest-only, forged, stale/replayed,
   wrong-restored-byte, wrong-schema/state-vector, selector, writer, and runtime
   evidence.
7. Repeat the executable backup/damage/rollback/forward-fix and negative cases
   through isolated installed-wheel CLI/API entrypoints at supported dependency
   vectors, outside the source tree.

## Requirement decision

| Finding | T1.8 concurrency/cutover | Backup restore | Rollback/forward-fix | Installed vector | Decision |
| --- | --- | --- | --- | --- | --- |
| Ancestor replacement | Violated: two live exclusion domains permit overlapping fence/CAS/effects | — | Recovery can overlap too | Wheel ships same defect | Blocking |
| Digest-only recovery | Cutover accepts an unexecuted recovery prerequisite | Violated | Violated; accepted damage is not recoverable | Post-recovery byte/vector proof absent | Blocking |

## Limitations and completion boundary

- No source, test, commit, checklist, or evidence file was modified. The only
  durable write is this result artifact.
- No external system/provider was contacted and no deployment or cloud mutation
  was attempted.
- Disposable local paths were used for the two reproductions.
- The earlier focused/wheel/archive results were treated as established; this
  pass did not repeat those expensive suites because the two counterexamples
  already force `HARD FAIL`.
- Hermetic fixes and locally green tests cannot establish the production
  descriptor/observer/executor guarantees promised by the data-only production
  contract.

Local acceptance cannot complete T1.8 without owner-installed production
adapters, generation selection/cutover, and accepted receipts. Even after the
two root repairs above, formal completion still requires those owner-installed
production integrations and independently accepted installed-generation and
recovery receipts.
