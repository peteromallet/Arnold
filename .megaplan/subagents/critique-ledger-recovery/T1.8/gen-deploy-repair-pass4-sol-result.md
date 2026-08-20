# T1.8 GEN-DEPLOY bounded repair pass 4 result

## Scope and outcome

The single pass-4 wrong-target rollback blocker is repaired in the bounded
hermetic release-authority implementation. A recovery bound to
`hermetic:control-plane` now rejects a digest-coherent backup whose canonical
state selects a `GenerationVector` naming `hermetic:wrong-target` before a
durable recovery intent, restore proof, manifest materialization, runtime
activation, selector observation/CAS, receipt, or deployment resolution.

This is not a T1.8 completion, release, deployment, production-custody, or
production-availability claim. A new independent Sol-high review of this exact
candidate and later installed production-owner receipts remain required.

## Frozen input

```text
required starting commit: 26d240339e0911a0e7347fc7849c8e151ab92111
required starting tree:   b8e5e1bc50f04942d21d71458260d94594e11e69
pass-4 review SHA-256:     8cef8bb86ec12bb88eb79f9bf37a936bb4aeba2c1ef42449a64daa17e25ff54b
```

The worktree was clean at that exact commit/tree before the repair.

## Committed candidate identity

```text
commit: 06d41e6b7148db4e5b464131762d63fd697db056
tree:   a8a67b2e01b9129673afdc7931cb3ffdce03a2de
parent: 26d240339e0911a0e7347fc7849c8e151ab92111
subject: Bind rollback recovery to authoritative target
```

The commit changes exactly these eight files:

```text
arnold_pipelines/release_authority/contracts.py
arnold_pipelines/release_authority/executor.py
arnold_pipelines/release_authority/store.py
arnold_pipelines/release_authority/verifier.py
tests/arnold_pipelines/release_authority/conftest.py
tests/arnold_pipelines/release_authority/test_repair_pass2.py
tests/arnold_pipelines/release_authority/test_repair_regressions.py
tests/arnold_pipelines/release_authority/test_security_durability.py
```

No dependency or lock file changed.

## Bounded correction

- `RecoveryPayload` now signs `backup_target_id`; `RecoveryResolutionPayload`
  now signs `target_id`; strict decision validators bind both fields, both
  bindings, and any forward-fix generation to one authoritative target.
- Canonical hermetic state now names its target. A read-only backup preflight
  validates exact signed bytes/digests, canonical-state target identity, and
  every embedded generation target before `_begin_recovery_execution` can
  journal intent or advance the store fence. The restore path repeats the same
  validation before its scratch restore proof, closing the execution-time gap.
- The durable intent records and exact-replay checks include authoritative and
  backup target identities. The signed executor receipt records
  `restored_target_id`, includes it in its independent observation digest, and
  rebinds it during completion.
- Reconciliation revalidates the exact backup target and passes the resolution
  binding target into installed-generation observation. It no longer
  self-compares with the restored generation's own target. Independent
  verification validates the same contract, intent, receipt, and authoritative
  live-observation target.
- Exact successful replay/response-loss/fresh-process behavior and the prior
  generation/manifest/migration, displaced-writer, crash-cut, selector-fence,
  installed-parity, and production-fail-closed closures remain green.

## Committed regression

`test_digest_coherent_wrong_target_rollback_is_zero_effect_fail_closed` is the
reviewer's reproduced shape:

- accept the real signed `hermetic:control-plane` generation;
- create a fresh in-root generation whose only wrong identity is
  `target_id="hermetic:wrong-target"`;
- keep the canonical backup-state target authoritative as
  `hermetic:control-plane`, select the wrong-target generation, and recompute
  backup bytes plus backup/state/schema/vector/generation digests;
- sign rollback recovery and resolution decisions still bound to
  `hermetic:control-plane`;
- require typed `recovery_target_mismatch` on initial execution and exact replay
  with a response-loss-capable adapter, plus a spawned fresh-process replay;
- require direct reconciliation to return `UNKNOWN` and independent
  verification to find no accepted custody lineage; and
- byte-compare target files and compare store status/events/deployment before
  and after, while instrumenting resolve, state write, manifest, runtime,
  selector observation, and restore-test calls as zero.

The regression also proves intrinsic model validation rejects internally
inconsistent RecoveryDecision and RecoveryResolution target claims.

## Finite evidence

All pytest commands used `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR=/private/tmp`, and
`-p no:cacheprovider`. Suites ran sequentially; the installed-wheel suite was
single-flight.

### Exact blocker slice

```text
$ .venv/bin/pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_digest_coherent_wrong_target_rollback_is_zero_effect_fail_closed \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_compatible_rollback_materializes_exact_prior_generation \
  'tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_crash_at_each_restore_forward_fix_edge_replays[after-recovery-selector-cas]' \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_backup_restore_and_forward_fix_are_executable \
  tests/arnold_pipelines/release_authority/test_repair_pass2.py::test_independent_recovery_observation_rejects_wrong_materialized_evidence
9 passed in 1.13s
```

The count is nine because the independent wrong-materialized-evidence node
expands to five cases.

### Full release-authority suite

```text
$ .venv/bin/pytest -q -p no:cacheprovider tests/arnold_pipelines/release_authority
186 passed in 11.12s
```

### Import/CLI/wrapper closure suite

```text
$ .venv/bin/pytest -q -p no:cacheprovider \
  tests/characterization/test_import_surface.py \
  tests/test_pipeline_run_cli.py \
  tests/cloud/test_wrapper_authority_bypass_gating.py
84 passed in 4.49s
```

### Installed wheel/source/minimum/locked parity

Run after the repair commit so the suite's detached `git write-tree` archive
and working-tree source were intentionally the same candidate:

```text
$ UV_CACHE_DIR=/Users/peteromalley/.cache/uv \
  PIP_CACHE_DIR=/Users/peteromalley/Library/Caches/pip \
  .venv/bin/pytest -q -p no:cacheprovider \
  tests/installed_wheel/test_release_authority_entrypoint.py
11 passed in 64.88s
```

For completeness, one precommit invocation produced `10 passed, 1 failed`
solely at `test_detached_archive_source_and_wheel_release_authority_bytes_match`:
the test archives `git write-tree`, which still named the frozen parent while
the repair was unstaged, then compared it to modified working-tree bytes. The
post-commit single-flight run above passed all 11 tests against the exact
reported candidate.

### Static, compile, dependency, and diff gates

```text
$ uv run ruff check arnold_pipelines/release_authority \
  tests/arnold_pipelines/release_authority \
  tests/installed_wheel/test_release_authority_entrypoint.py \
  tests/installed_wheel/release_authority_ancestor_probe.py
All checks passed!

$ PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m compileall -q \
  arnold_pipelines/release_authority \
  tests/arnold_pipelines/release_authority \
  tests/installed_wheel/test_release_authority_entrypoint.py \
  tests/installed_wheel/release_authority_ancestor_probe.py
exit 0

$ uv lock --check
Resolved 84 packages in 3ms

$ uv pip check --python .venv/bin/python
Checked 76 packages in 1ms
All installed packages are compatible

$ git diff --check HEAD^ HEAD
exit 0

$ git diff --name-only HEAD^ HEAD -- pyproject.toml uv.lock
no output
```

A separate read-only adversarial review of the final diff found the live
wrong-target activation/reconciliation/replay path closed and returned a merge
verdict for the two reviewed implementation/test gaps. It is not the required
new independent Sol-high candidate review.

## Cleanliness and limitations

`git status --porcelain=v1 --untracked-files=all` produced no output after the
commit, post-commit wheel suite, and final checks.

No cloud/provider API, credential, production owner state, production target,
selector, marker, plan, checklist, or Git ref outside this worktree was touched.
No privileged production adapter/observer, real production cutover, owner
custody receipt, or deployed old-writer rejection proof was exercised. Those
external evidentiary limits remain unchanged and are not promoted into local
architecture work.
