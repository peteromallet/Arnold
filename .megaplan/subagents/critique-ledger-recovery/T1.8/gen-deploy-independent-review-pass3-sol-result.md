# HARD FAIL — T1.8 GEN-DEPLOY independent review pass 3

## Scope and position

**HARD FAIL.** Exact candidate `148465a109ade4318e4cb9ae13a83645a4bf2934`
is not acceptable for clean-lineage integration.

Two independently reproduced semantic counterexamples are blocking:

1. compatible rollback verification accepts a substituted live generation and
   matching substituted manifest without recomputing that material against the
   owner-signed generation digest; and
2. replay after a crash following recovery selector CAS loses the pre-CAS
   displaced-writer identity, derives it from the newly active generation, and
   accepts a receipt that says the current writers were displaced and rejected.

This is a local review of the frozen candidate only. It is not a formal T1.8,
release, production-availability, or deployment-completion claim.

## Frozen identity and inputs

The frozen identity and cleanliness were verified before reviewing code or test
claims.

```text
$ git -C /private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802 rev-parse HEAD HEAD^{tree} HEAD^
148465a109ade4318e4cb9ae13a83645a4bf2934
505b8104ba4fc5298e8efde384551e2310ec81e4
dae901e9bf2ecf289ad0aa201c50116f8bf1f899

$ git -C /private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802 status --porcelain=v1 --untracked-files=all
<no output>
```

The supplied review artifacts also matched their frozen hashes:

```text
$ shasum -a 256 gen-deploy-independent-review-pass2-sol-result.md gen-deploy-repair-pass2-sol-brief.md
3efb46d00b878685becc0ccbe8542a8de6fd35f866a883ce769b0ae0e9968f40  gen-deploy-independent-review-pass2-sol-result.md
6c149307d2a7eb1e86b27356b8d4735d104cb9a58cd06c5223bb8f9c113f0a76  gen-deploy-repair-pass2-sol-brief.md
```

Candidate diff against the exact parent contains 13 files and
`2331 insertions(+), 263 deletions(-)`. The review treated prior reports and
their test assertions only as leads, not evidence.

## Commands and exact results

### Declared source/focused suite

`uv run` could not initialize `/Users/peteromalley/.cache/uv` under the review
sandbox (`Operation not permitted`). The existing candidate virtualenv was
therefore invoked directly, with bytecode and pytest cache output redirected or
disabled so the frozen worktree remained untouched.

```text
$ PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<scratch>/pycache \
    .venv/bin/pytest -q -p no:cacheprovider tests/arnold_pipelines/release_authority
........................................................................ [ 39%]
........................................................................ [ 78%]
.......................................                                  [100%]
183 passed in 14.39s

$ git status --porcelain=v1 --untracked-files=all
<no output>
```

An independent focused slice covering the named ancestor, backup/restore,
rollback, accepted-active recovery, and independent-observation cases also
returned:

```text
17 passed in 1.26s
```

Green tests do not overcome either semantic counterexample below.

### Declared broad import/CLI/bypass suite

```text
$ PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<scratch>/pycache \
    .venv/bin/pytest -q -p no:cacheprovider \
    tests/characterization/test_import_surface.py \
    tests/test_pipeline_run_cli.py \
    tests/cloud/test_wrapper_authority_bypass_gating.py
........................................................................ [ 85%]
............                                                             [100%]
84 passed in 10.86s

$ git status --porcelain=v1 --untracked-files=all
<no output>
```

### Declared installed-wheel suite

The large wheel suite was kept single-flight. It did not reach its candidate
assertions in this review environment:

```text
$ PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=<scratch>/pycache \
    UV_CACHE_DIR=<scratch>/uv-cache TMPDIR=<scratch> \
    .venv/bin/pytest -q -p no:cacheprovider \
    tests/installed_wheel/test_release_authority_entrypoint.py
EEEEEEEEEEE                                                              [100%]
11 errors in 10.99s
```

All 11 errors shared the session fixture failure at
`tests/installed_wheel/conftest.py:148`: `uv build` could not resolve the locked
build backend because outbound DNS/network access was unavailable. Reproducing
the suppressed build command showed:

```text
Failed to fetch: https://pypi.org/simple/hatchling/
client error (Connect)
dns error
failed to lookup address information: nodename nor servname provided, or not known
```

After seeding a disposable cache from already-present local cache content, the
same constrained `uv build` step succeeded and produced
`arnold-0.23.0-py3-none-any.whl`. The complete installed suite was not rerun:
its isolated minimum-Pydantic-2.11.0 installation still required dependency
artifacts unavailable offline. Accordingly, this review does not treat the 11
setup errors as a candidate test failure, but it also does not grant independent
installed/minimum-environment proof.

## Blocking counterexample A — substituted rollback generation verifies

### Reproduction

The disposable probe used the real fixture, store, hermetic adapter, signed
ordinary upgrade, signed compatible rollback, recovery executor, and independent
recovery verifier:

1. accept signed generation `g1`;
2. accept signed generation `g2`, preserving a compatible backup containing
   `g1`;
3. execute the signed compatible rollback to `g1`;
4. replace `state["available"][signed_g1_digest]["source"]["commit"]` with
   forty zeroes;
5. rewrite `g1/manifest.json` to the canonical bytes of that substituted
   generation, making the live state and manifest internally consistent but
   different from the signed `g1` vector; and
6. call `verify_recovery_resolution` with the original signed recovery and
   resolution decisions.

Exact observed output:

```text
signed_generation sha256:2259ad8494172230767aebd81fa98fca2259306a586f68d73826ef8816023289
substituted_source_commit 0000000000000000000000000000000000000000
verified True errors ()
1 passed in 1.33s
```

This is not damage that merely makes verification unavailable. The independently
observed live material is substituted and the verifier returns affirmative
success.

### Root cause

In the rollback branch of `_recovery_receipt_is_current`,
`executor.py:1958-1976` looks up `available[expected_runtime]`, parses whatever
generation object is stored under that caller-independent key, and checks the
manifest against those newly loaded bytes. It never checks
`generation.generation_digest == expected_runtime`. It calls
`observe_installed()` but discards the observed generation digest.

`verifier.py:174-192` performs an explicit installed-generation comparison only
when `receipt.strategy == "forward-fix"`; rollback takes no equivalent check.
Thus the state key and `attested_generation` string retain the signed digest while
the installed vector and manifest underneath that key can be replaced together.

The signed recovery's `migration_digest` is likewise not consumed by executor
materialization: its substantive occurrences are in the contract and tests, while
the forward-fix execution at `executor.py:1809-1833` does not open, execute, or
independently verify a migration artifact. This reinforces that compatibility
and migration evidence are not yet fully materialized authority.

### Violated requirements

This counterexample independently fails matrix items 3, 4, and 5: the recovery
decision/receipt is not bound to the exact independently observed installed
generation vector, deterministic restoration verification accepts substituted
bytes, and a wrong installed artifact returns success rather than a typed
fail-closed result.

## Blocking counterexample B — post-CAS replay loses displaced-writer lineage

### Reproduction

The disposable probe followed the existing crash test's real path at
`tests/arnold_pipelines/release_authority/test_repair_pass2.py:466-517`, adding
only semantic assertions that the committed test omits:

1. accept the original generation and record its two running writer identities;
2. damage the accepted active generation;
3. execute an exact signed forward-fix recovery with a fault at
   `after-recovery-selector-cas`;
4. replay the exact same signed recovery/resolution through a fresh store and
   adapter instance;
5. compare the receipt's displaced/rejected writers with both the pre-CAS writer
   identities and the now-running forward-fix identities; and
6. run `verify_recovery_resolution`.

Exact observed result:

```text
old_lineage_preserved= False
receipt_rejects_current_running= True
store_resolved= RA-active-resolution-writer-lineage-proof
verification= True ()
```

The receipt's `displaced_writer_ids` and `rejected_writer_ids` were the same two
identities as the current forward-fix `role_processes`, not the original two
pre-CAS identities. The store nevertheless resolved under the recovery decision,
and independent verification accepted the receipt.

### Root cause

- `executor.py:1769-1778` derives `displaced` from the adapter's current
  `role_processes` on every call.
- `executor.py:1824-1845` materializes and activates the forward-fix generation,
  writes the new selector/runtime state, and only then reaches the injected
  post-CAS crash.
- `executor.py:1889-1894` would persist the recovery receipt later, so the crash
  leaves applied target state without the receipt.
- `executor.py:1986-2016` reports that partial state as `UNKNOWN`, not as a
  recoverable applied result retaining the original displaced-writer proof.
- `execute_recovery_resolution` at `executor.py:585-652` falls through that
  `UNKNOWN` reconciliation and redispatches the adapter operation. On replay,
  `displaced` is therefore recomputed from the already active forward-fix
  processes.
- `_validate_recovery_resolution_receipt` at `executor.py:217-220` checks only
  that `displaced_writer_ids == rejected_writer_ids`; it does not bind either set
  to the pre-effect observation.
- `verifier.py:174-192` checks receipt equality/current target observation but
  does not prove that rejected identities are the displaced pre-CAS writers or
  that they differ from the current running identities.

The existing test at
`tests/arnold_pipelines/release_authority/test_repair_pass2.py:466-517` asserts
only eventual replay and `report.verified`; it therefore passes while encoding
the false-success path instead of checking preservation of the writer lineage.

### Violated requirements

This counterexample independently fails matrix items 6 and 8. Post-effect /
pre-receipt crash and replay do not converge on one exact authoritative proof:
the replay changes the operation evidence and produces a semantically false yet
accepted receipt. The receipt is therefore not a complete, exact replay of the
original operation proof.

## Finite acceptance matrix

| # | Verdict | Evidence |
|---|---|---|
| 1 | **PASS (local hermetic scope)** | `HermeticNamespaceIdentity` captures owner-root and protected ancestor device/inode identities (`store.py:48-98`); constructors open no-follow retained directory descriptors and compare them with the capture (`store.py:229-317`); execution locks the retained owner-root, lock-parent, and lock identities (`store.py:573-637`). Named fresh-store, active-holder, protected-ancestor, and cutover replacement cases passed. Production namespace custody remains external. |
| 2 | **PASS (local hermetic scope)** | Lock/owner identity is rooted in the signed anchor's captured ancestor identities and retained descriptors (`store.py:185-209,229-317,573-637`). Adapter binding and revalidation use captured target/backup identities (`executor.py:941-1028`). The caller path is equality-checked rather than accepted as a fresh authority root. |
| 3 | **FAIL** | Counterexample A proves rollback verification binds a digest key/string but not the exact live generation vector and manifest to that signed digest (`executor.py:1958-1976`; `verifier.py:174-192`). `migration_digest` is not an executable migration artifact. |
| 4 | **FAIL** | Counterexample A substitutes restored live generation material and its manifest; independent verification still returns `verified True`. Exact independently observed restored bytes/vector are therefore not enforced for compatible rollback. |
| 5 | **FAIL** | The wrong/substituted installed artifact in counterexample A succeeds instead of producing a typed fail-closed result. Other negative backup/schema/vector tests passing does not close this installed-artifact case. |
| 6 | **FAIL** | Counterexample B proves a post-selector-CAS/pre-receipt crash followed by exact replay loses pre-CAS writer lineage, recomputes evidence from the new runtime, and resolves with false success (`executor.py:585-652,1769-1894,1986-2016`). |
| 7 | **FAIL (not independently proven)** | Source and broad suites passed and a constrained wheel could be built from local cache, but the declared installed/minimum/locked suite could not complete offline. The finite contract requires installed entrypoint and minimum/locked equivalence; this review has no independent passing result for that requirement. This is an evidence failure, not attribution of the sandbox DNS error to candidate code. |
| 8 | **FAIL** | Counterexample B produces and verifies a receipt whose displaced/rejected writer subject is the current runtime rather than the original displaced runtime. Equality of the two receipt lists (`executor.py:217-220`) is not complete content/subject binding. |
| 9 | **PASS (local fail-closed claim only)** | Genuine owner-installed construction rejects before path/store access (`store.py:173-184`); owner execution and observation paths remain unavailable without production adapters, and `production.py:188-203` exposes no hermetic-as-production registration. This is not owner-backend evidence. |
| 10 | **PASS** | The release-authority package, bootstrap, and release-authority documentation contain no Megaplan import/reference; contracts use generic target, pipeline, generation, and authority identifiers. The local interface remains pipeline-neutral. |

Items 3-6 and 8 are semantic failures. Item 7 is additionally unproven under the
required independent installed/minimum/locked execution matrix. Either blocking
counterexample is independently sufficient for the overall `HARD FAIL`.

## Limitations and external evidence still required

No cloud/provider API, credential, process, Git ref, production generation,
production owner state, or candidate file was mutated. No real mount operation
or privileged production namespace was exercised.

Even after the local blockers are repaired and independently reviewed, the
following remain external acceptance prerequisites:

- an owner-installed privileged production executor and independent observation
  adapter;
- privileged descriptor/mount/namespace custody for the complete production
  transaction;
- a real production generation selection and fenced cutover;
- accepted owner executor, observer, custody, and deployment receipts;
- production proof that old writers/effects are rejected after switch; and
- an independently completed installed-wheel source/minimum/locked/entrypoint
  equivalence run in an environment containing the locked dependency artifacts.

No formal T1.8 or release completion claim is made. A future local `PASS` would
mean only that an exact corrected candidate is suitable for clean-lineage
integration and later owner/deployed evidence.
