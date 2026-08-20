# T1.8 GEN-DEPLOY bounded repair pass 3 — implementation result

## Scope and status

The two pass-3 semantic blockers were repaired in the bounded local hermetic
release-authority implementation, and the independent installed-wheel evidence
gap was closed with the unchanged test suite using existing package caches.

This is a local implementation/evidence record only. It is **not** a formal
T1.8, release, deployment, production-availability, or production-custody
completion claim. A new independent Sol-high review and later owner/deployed
evidence remain required.

## Frozen input identity

```text
requested base commit: 148465a109ade4318e4cb9ae13a83645a4bf2934
requested base tree:   505b8104ba4fc5298e8efde384551e2310ec81e4
base parent:           dae901e9bf2ecf289ad0aa201c50116f8bf1f899
pass-3 report SHA-256: bff46dc2b888e989ae9099d6270f4a4dac0c37dbdaf80e1fd1eba43fdf9b887a
```

The starting worktree was clean and matched all requested identities and the
report hash before inspection or mutation.

## Committed candidate identity

```text
commit: 26d240339e0911a0e7347fc7849c8e151ab92111
tree:   b8e5e1bc50f04942d21d71458260d94594e11e69
parent: 148465a109ade4318e4cb9ae13a83645a4bf2934
subject: Fix exact recovery generation and writer lineage
```

Post-commit `git status --porcelain=v1 --untracked-files=all` produced no
output. `git diff --check HEAD^ HEAD` also produced no output.

## Exact changed files

```text
arnold_pipelines/release_authority/contracts.py
arnold_pipelines/release_authority/executor.py
arnold_pipelines/release_authority/store.py
arnold_pipelines/release_authority/verifier.py
tests/arnold_pipelines/release_authority/test_repair_pass2.py
tests/arnold_pipelines/release_authority/test_repair_regressions.py
tests/arnold_pipelines/release_authority/test_security_durability.py
```

Diff summary: 7 files changed, 704 insertions, 69 deletions.

## Repair A — exact signed live generation

- Rollback execution now parses the generation stored under the signed key,
  recomputes its canonical `GenerationVector` digest, and requires exact equality
  with the owner-signed rollback generation before materialization or runtime
  activation.
- One shared exact observation path recomputes the live generation vector,
  securely reads and independently parses exact canonical manifest bytes, checks
  target identity, reconstructs the complete process/service attestation, and
  compares all observed generation digests to the signed expected digest.
- Recovery receipts bind the prior generation, observed runtime generation,
  independently parsed manifest generation, complete installed-attestation
  digest, and migration evidence. Reconciliation and independent verification
  recompute those values rather than trusting selector strings, attested labels,
  map keys, or cached receipt consistency.
- Missing, malformed, unsafe, noncanonical, truncated, corrupt, and substituted
  vector/manifest evidence fails closed through typed errors or `UNKNOWN`
  reconciliation.
- The exact counterexample was added to the compatible rollback regression: the
  restored source commit is replaced with forty zeroes, matching canonical
  manifest bytes are rewritten beneath the original signed digest key, and
  independent verification rejects with
  `recovery_signed_observed_generation_digest_mismatch`.

## Forward migration material

- A strict owner-signed `RecoveryMigrationArtifact` now binds the exact source
  backup-state digest, target generation digest, target state-vector digest, and
  the bounded executable operation
  `restore-signed-backup-and-activate-generation`.
- A bare `migration_digest` is rejected by contract validation.
- Forward-fix execution applies the signed backup restoration, activates the
  signed target generation, and persists the exact canonical execution record.
  Receipt, reconciliation, and independent observation require the artifact
  digest and complete source/target execution lineage.
- A post-fix adversarial review found that a truncated execution record initially
  remained acceptable. The predicate was tightened to exact full-record
  equality, and a regression now deletes all three source/target lineage fields
  and proves verification fails closed.

## Repair B — durable displaced-writer lineage

- The owner-signed recovery-resolution subject now contains the observed
  pre-effect generation and exact ordered displaced-writer identities in addition
  to the existing selector and revision.
- Before first dispatch, the adapter checks the signed tuple against the live
  selector/generation/process identities. The complete tuple and both decision
  digests are journaled in durable intent before target mutation; exact replay
  compares the complete canonical intent.
- Recovery execution derives displaced/rejected identities only from the signed,
  durable pre-effect set. It no longer recomputes them from the newly active
  runtime.
- The canonical target receipt is persisted atomically with selector/runtime CAS
  state. If the signed result is active without valid durable evidence, execution
  returns indeterminate and never redispatches the effect.
- Independent verification proves receipt writers equal the signed/durable
  pre-effect set and that current runtime writers do not intersect the rejected
  set.
- The exact `after-recovery-selector-cas` regression now crashes, reopens a fresh
  store and adapter, rejects any second runtime/CAS dispatch, proves receipt-byte
  stability, proves original writer preservation, proves new writer exclusion,
  proves current process stability, performs a second exact replay with the same
  canonical result, and verifies independently.

## Evidence matrix

All commands used `PYTHONDONTWRITEBYTECODE=1`, redirected bytecode/temp output to
`/private/tmp/gen-deploy-pass3-evidence`, and disabled pytest cache writes.

### Full release-authority source suite

```text
.venv/bin/pytest -q -p no:cacheprovider tests/arnold_pipelines/release_authority
185 passed in 16.01s
```

### Import / CLI / bypass suite

```text
.venv/bin/pytest -q -p no:cacheprovider \
  tests/characterization/test_import_surface.py \
  tests/test_pipeline_run_cli.py \
  tests/cloud/test_wrapper_authority_bypass_gating.py
84 passed in 11.43s
```

### Installed wheel / minimum / locked / entrypoint suite, single-flight

The unchanged suite was run with:

```text
UV_CACHE_DIR=/Users/peteromalley/.cache/uv
PIP_CACHE_DIR=/Users/peteromalley/Library/Caches/pip
TMPDIR=/private/tmp/gen-deploy-pass3-evidence/tmp
.venv/bin/pytest -q -p no:cacheprovider \
  tests/installed_wheel/test_release_authority_entrypoint.py
11 passed in 79.96s
```

This run built and installed the candidate wheel, exercised minimum Pydantic
2.11.0 and locked Pydantic 2.12.5 environments, checked entrypoints and ancestor
probes, and passed detached source/wheel and minimum/locked byte parity. No
fixture, constraint, hash, minimum version, or assertion was weakened.

An earlier pre-final run reached the suite and reported 8 passed / 3 failed. One
failure correctly showed that byte-parity archives use the staged candidate tree;
two showed the installed test's shared recovery fixture needed to reconstruct its
pinned adapter when called without an in-process adapter. Both causes were fixed;
the final unchanged 11-test run above is the candidate evidence.

### Exact bounded semantic / custody slice

```text
23 passed in 4.01s
```

The slice included accepted-active rollback and forward-fix, bare-migration
rejection, coherent substituted rollback material, post-CAS fresh-process replay,
all five bad-backup cases, response-loss reconciliation, protected-ancestor
replacement, two-process/lock replacement, and production fail-closed paths.

An additional focused exact repair slice covering migration-record corruption,
forward-fix execution, coherent rollback substitution, and post-CAS writer replay
returned `4 passed in 0.56s`.

### Static, compile, dependency, and diff gates

```text
ruff check <release-authority source/tests and installed probes>
All checks passed!

python -m compileall -q <release-authority source/tests and installed probes>
exit 0

uv lock --check
Resolved 84 packages in 25ms

uv pip check --python .venv/bin/python
Checked 76 packages in 6ms
All installed packages are compatible

git diff --cached --check
exit 0

git diff --check HEAD^ HEAD
exit 0
```

## Limitations and remaining external evidence

- The installed evidence gap from pass 3 is closed locally by the final 11/11
  run using already-present package caches. No external network fetch was needed.
- No cloud/provider API, credential, process, Git ref outside this worktree,
  production generation, production owner state, checklist state, mount, or
  privileged production namespace was touched.
- No production adapter, privileged descriptor/mount custody, real production
  cutover, owner executor/observer/custody receipt, or deployed old-writer
  rejection proof was exercised.
- The namespace architecture and authority capability model were not broadened.
- A new independent Sol-high review of commit
  `26d240339e0911a0e7347fc7849c8e151ab92111` is required before any clean-lineage
  integration decision. Owner/deployed evidence is required afterward before any
  formal T1.8/release/deploy completion claim.
