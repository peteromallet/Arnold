# GEN-DEPLOY repair pass 2 — GPT-5.6 Sol-high result

Date: 2026-08-02

## Result

Repaired exact clean candidate `dae901e9bf2ecf289ad0aa201c50116f8bf1f899`
in `/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`.

- Commit: `148465a109ade4318e4cb9ae13a83645a4bf2934`
- Tree: `505b8104ba4fc5298e8efde384551e2310ec81e4`
- Commit subject: `fix(release-authority): fence recovery and owner-root custody`
- Final worktree: clean
- Cloud/provider contact, deployment, real-generation switching, and owner-state mutation: none

This is a repair result, not a claim of formal T1.8 completion.

## Root repairs

### 1. Stable exclusion identity across ancestor replacement

Hermetic authority anchors now carry an owner-captured `HermeticNamespaceIdentity`
containing device/inode identities for the owner root and every protected directory
ancestor used by the store, lock, target, and backup paths. The store:

- opens and retains no-follow directory descriptors before any SQLite access;
- persists the namespace, store-file, and lock-file identities in store genesis;
- locks the retained owner-root inode, lock-parent inode, and lock-file inode for the
  entire target transaction;
- opens the lock relative to the retained parent descriptor;
- revalidates the full namespace, database, and lock identity before/after exclusion
  and before irreversible execution boundaries;
- revalidates immediately after SQLite opens the database inode and before a WAL-
  creating PRAGMA;
- never recaptures a recreated pathname as a new authority or lock domain.

The hermetic adapter constructor is now non-mutating. `bind_anchor` must first acquire
and validate signed target/backup directory capabilities. Target state, backups,
restore scratch, and generation manifests are read/written relative to retained
no-follow descriptors. State replacement uses exclusive unpredictable temporary
names, file fsync, descriptor-relative replace, and target-directory fsync.

Consequently, ancestor/lock-parent/lock-file/database/selector/target/backup-root
replacement, symlink and hardlink aliases, rename/recreate, stale descriptors, and a
fresh process attempting to repin a signed anchor fail closed. A two-process test and
an installed-wheel two-process probe prove that a new process cannot enter a split
lock domain while the displaced holder is still live. A cutover barrier test proves
that replacement cannot reach selector CAS or duplicate the effect stream.

Owner-installed mode still rejects local construction and mutation before store or
target access. The local descriptor defense is explicitly hermetic and is not treated
as production authority.

### 2. Executable backup/restore and real recovery

Recovery decisions now sign a concrete backup locator and expected backup bytes,
state, schema, selected generation, and complete vector, plus explicit rollback
compatibility. An incompatible state requires a separately signed forward-fix
generation and migration digest.

Before materialization, the hermetic executor now:

- journals operation intent;
- creates the exact backup with exclusive/no-follow semantics;
- fsyncs backup bytes and the retained backup directory;
- reopens and compares the durable bytes with the signed digest;
- restores into isolated descriptor-relative scratch;
- fsyncs and rereads restored bytes;
- derives state/schema/generation/vector receipts from observations; and
- removes restore scratch after capturing the proof.

Recovery can name either an unresolved indeterminate deployment or a damaged accepted
active deployment. Compatible rollback restores the backed-up state and exact prior
generation, materializes/verifies its manifest, starts its runtime, advances selector
revision monotonically, and fences/rejects displaced writers. Incompatible rollback
is invalid; forward-fix must materialize a distinct signed generation, start its exact
role/runtime vector, CAS the selector, and reject displaced writers.

Recovery intent, effect, selector CAS, runtime start, receipt materialization, custody
commit, response-loss reconciliation, exact idempotent replay, and no-redispatch
behavior remain separated. Independent recovery verification rereads the backup and
current materialized manifest, full generation vector, schema/state lineage,
role-process vector, services, selector/fence, and runtime. Cached receipts cannot
override damaged target evidence.

## Files changed

1. `arnold_pipelines/release_authority/__init__.py`
2. `arnold_pipelines/release_authority/cli.py`
3. `arnold_pipelines/release_authority/contracts.py`
4. `arnold_pipelines/release_authority/executor.py`
5. `arnold_pipelines/release_authority/store.py`
6. `arnold_pipelines/release_authority/verifier.py`
7. `docs/arnold/gen-deploy-release-authority.md`
8. `tests/arnold_pipelines/release_authority/conftest.py`
9. `tests/arnold_pipelines/release_authority/test_repair_pass2.py`
10. `tests/arnold_pipelines/release_authority/test_repair_regressions.py`
11. `tests/arnold_pipelines/release_authority/test_security_durability.py`
12. `tests/installed_wheel/release_authority_ancestor_probe.py`
13. `tests/installed_wheel/test_release_authority_entrypoint.py`

## Exact validation

### Release-authority source/API suite

Command:

```text
uv run pytest -q tests/arnold_pipelines/release_authority
```

Result:

```text
183 passed in 11.19s
```

The new pass-2 suite contains the exact independent-review tests:

- `test_fresh_store_cannot_repin_recreated_lock_parent`
- `test_ancestor_replacement_during_active_holder_never_creates_concurrent_domain`
- `test_each_protected_ancestor_replacement_fails_closed`
- `test_ancestor_replacement_during_cutover_cannot_duplicate_effect_or_cas`
- `test_backup_restore_and_forward_fix_are_executable`
- `test_migration_then_binary_failure_obeys_rollback_compatibility`

It additionally covers constructor forgery, symlink-shaped stale owner roots,
selector symlink/hardlink aliases, accepted-active damage, exact compatible-prior
rollback, distinct incompatible forward-fix, missing/corrupt/truncated/substituted/
non-restorable backups, wrong materialized bytes/schema/vector/runtime, and crashes
at backup read/write/fsync, state read/write/fsync/replace, restore write/fsync,
runtime start, selector CAS, receipt commit, and recovery custody edges. Existing
response-loss, replay, no-redispatch, writer-fence, exact-vector, custody, temporal,
terminal, production-absence, constructor/binding forgery, dependency-failure, and
bypass regressions remain green.

### Broad import/CLI/bypass suite

Command:

```text
uv run pytest -q tests/characterization/test_import_surface.py tests/test_pipeline_run_cli.py tests/cloud/test_wrapper_authority_bypass_gating.py
```

Result:

```text
84 passed in 3.65s
```

### Installed wheel, dependencies, detached archive, and wrapper parity

One single-flight command:

```text
uv run pytest -q tests/installed_wheel/test_release_authority_entrypoint.py
```

Result:

```text
11 passed in 59.95s
```

This built one wheel with the hash-constrained locked build backend; installed it in
isolated minimum-Pydantic-2.11.0 and locked dependency environments; ran `pip check`;
proved installed API and CLI behavior; ran accepted-active forward-fix through both
installed CLIs; ran the two-process ancestor-replacement probe through both installed
interpreters; compared canonical bytes, schemas, signatures, module origins, and
round trips; compared every shipped release-authority byte across the detached staged
Git tree, checkout, and wheel; and compared both materialized `arnold-gen-deploy`
wrapper bodies with the wheel entry-point declaration.

The committed tree exactly matched the staged tree used by the detached-archive test.
The reproducible 847 MiB wheel scratch at
`/private/var/folders/_w/b3tthv192m77c760dbyzvk200000gn/T/pytest-of-peteromalley/pytest-30`
was removed after the result was captured and its absence was verified.

### Static/dependency controls

```text
uv run ruff check arnold_pipelines/release_authority tests/arnold_pipelines/release_authority tests/installed_wheel/test_release_authority_entrypoint.py tests/installed_wheel/release_authority_ancestor_probe.py
All checks passed!

python -m compileall -q arnold_pipelines/release_authority tests/arnold_pipelines/release_authority tests/installed_wheel/release_authority_ancestor_probe.py tests/installed_wheel/test_release_authority_entrypoint.py
passed

uv lock --check
Resolved 84 packages in 5ms

uv pip check
Checked 76 packages in 2ms
All installed packages are compatible

git diff --check
passed
```

Post-commit checks also proved `git write-tree == HEAD^{tree}`, an empty
`git status --porcelain`, and absence of the large wheel scratch.

## Preserved properties

The repair retains the pass-1 signed-authority, custody-root, exact-vector,
response-loss indeterminacy, selector-CAS, writer-fence, runtime-start,
generation-lineage, terminal payload, wheel/dependency, fail-before-touch, and
fail-closed properties. No ambiguous recovery evidence is converted into acceptance,
no response-loss path redispatches under a different decision, and no local hermetic
receipt is accepted as production custody.

## Limitations and external work

This commit does **not** complete formal T1.8. The following remain external by the
task contract:

- owner-installed privileged production executor and observer adapters;
- privileged descriptor custody and mount/namespace replacement prevention for the
  complete production session;
- real production generation selection and cutover;
- production-accepted executor/observer/custody receipts and acceptance evidence.

No real mount operation was performed in the hermetic suite. Mount-shaped namespace
change is exercised through the same signed device/inode mismatch, replacement, and
stale-descriptor gates; actual mount prevention and privileged custody belong to the
external owner-installed adapter. No cloud/provider or live owner state was touched.
