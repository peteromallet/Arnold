# RA-CONTAIN repair pass 13 — implementation result

## Scope and disposition

Implemented the three authorized pass-13 repairs in the frozen local RA-CONTAIN worktree. This is not a formal T0.0 completion claim, an owner-installed production boundary, or cloud/provider/owner/checklist evidence.

- Worktree: `/private/tmp/arnold-critique-recovery-ra-contain-20260802`
- Exact clean base: `88393e2d0da80d76205ba03ddabf7577d864306b`
- Repair commit: `48e13e1bcbc6769aff753270331d52ac1c148125`
- Tree: `550421e34c1e789e31d173fdf35fdd7fd55ce287`
- Commit subject: `Close RA containment durable proof gaps`
- Final worktree status: clean

## Implemented repairs

### 1. Materialized backend nonce authority is part of durable proof

Every ordinary commit/replay proof now carries the exact request-scoped projection of SQLite's durable nonce authority. The backend requires the materialized nonce entries bearing that request digest to be exactly `{request nonce: request digest}` and independently requires the same nonce binding in the identity bundle.

Consequently, deleting the materialized request nonce, substituting its digest, or adding a forked nonce alias for the same request fails with typed `CorruptAnchor`, including after backend/store restart. Unrelated previously reserved nonces remain valid history rather than being confused with the current operation's nonce authority.

### 2. File-backed state cannot fall back to stale memory

`LocalTestOwnerAnchorBackend` construction now locks and reloads any partially or fully materialized state. Every existing file-backed read, CAS, nonce reservation, indeterminate write, provisioning, and durable-proof path continues to use the common process lock and now reloads an exact `{head, nonces}` document plus the private key and pinned receipt-authority identity.

A missing anchor is accepted only for a genuinely pristine, never-materialized instance. Deletion, partial loss, replacement, malformed fields, non-string nonce state, missing/replaced key, or missing/replaced receipt-authority identity clears cached `_head`/`_used_nonces` and raises typed corruption. A stale instance can no longer return its old head after authoritative files disappear.

### 3. Reconcile returns the canonical complete operation receipt

Fresh reconcile, durable reconcile resumption, committed reconcile replay, and restart replay now all return the finalized canonical operation receipt from `operation_receipts`, exactly as issue and terminate do. The receipt binds:

- signed request, digest, nonce, idempotency key, and exact operation identity;
- all identity bindings;
- target and effect policy;
- journal record, cursor, prior hash, record hash, and journal digest;
- backend domain, pinned receipt identity, committed head, and backend receipt;
- owner/capability/trust identity;
- exact decision/result content and complete bundle hash.

The semantic reconcile result remains durably nested in `journal_record.result`; mutable identity result rows are independently checked against that record and cannot substitute for the returned receipt.

### 4. Linearization adjudication preserved

The code now documents the exact linearization point: successful atomic backend durable proof while the SQLite writer transaction and materialized backend process lock protect the exact journal/request/nonce/identity bundle. The complete receipt pins that committed backend revision.

The existing before-proof test remains fail-closed when a test-only direct backend peer lands first. A new after-linearization test pauses only the outer caller after the operation has linearized, then completes a legitimate signed terminate through a second `ContainmentStore`, with its own nonce, journal record, backend transition, and complete receipt. The original issue caller then returns its original receipt; exact issue replay still returns that historical receipt while current status correctly reports the later terminated state. Thus later authorized history is not treated as retroactive failure.

## Changed files and hashes

- `arnold_pipelines/run_authority/containment.py`
  - SHA-256: `f54adbe847e2dc936b0a288d65e96d58c1adedb7306a3044160cd85170d6183b`
- `tests/arnold_pipelines/run_authority/test_containment.py`
  - SHA-256: `1049b1ca0178001f9b9ce12c741253d8b47c1e9334d1372e3d941cdadd07188e`

Only these two files are present in the repair commit.

## Regression evidence

New exact coverage includes:

- materialized backend nonce deletion, wrong digest, and forked extra alias across restart;
- stale instance after anchor, key, or receipt-authority identity deletion and replacement;
- reconcile first-run, same-process replay, restart replay, complete field/hash receipt checks, and mutable result-side-row corruption;
- peer mutation before the durable-proof linearization point;
- legitimate authorized peer transition after linearization but before the original outer caller returns.

All commands used `PYTHONDONTWRITEBYTECODE=1`; pytest commands also used `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` and `-p no:cacheprovider`.

Containment suite:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py

89 passed in 4.06s
```

Exact new/blocker selection:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py \
  -k 'backend_nonce_authority or stale_materialized_instance or reconcile_returns_one_complete or before_linearization or after_linearization'

12 passed, 77 deselected in 0.59s
```

Replay/final-CAS/marker/expiry/process preservation selection:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py \
  -k 'ordinary_replay or complete_receipt or materialized_commit_proof or backend_nonce_authority or stale_materialized_instance or reconcile_returns_one_complete or after_linearization or exact_authenticated_final_cas_noop or final_stalecas or marker_race or ttl_boundary or expired_candidate or separate_process_races'

27 passed, 62 deselected in 0.92s
```

Full Run Authority and closure matrix, rerun after the final code/documentation change:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority \
  tests/run_authority/test_dependency_closure.py \
  tests/cloud/test_m1_containment_acceptance.py

130 passed in 13.33s
```

Static/diff evidence:

- `python -m py_compile` on both changed Python files: passed.
- `git diff --check`: passed.
- Ruff: 63 findings, exactly matching the pass-12 documented repository baseline (compact one-line style, two existing unused imports, and one existing unused test local); no new pass-13 finding.
- Mypy: nine findings, exactly matching the pass-12 documented baseline (eight in `contracts.py`, one existing `ArgumentParser.error` override in `containment.py`); no new pass-13 finding.

## Explicit limitations

- No cloud, provider, installed production owner, remote store, owner decision, checklist, or completion state was contacted or mutated.
- The local backend remains visibly test-only and is still rejected by production mode.
- No accepted production `ReleaseAuthorityBackend` is installed in this checkout; production fencing/lease/epoch and owner acceptance evidence remain external prerequisites.
- Formal T0.0 completion requires a fresh independent review plus release-owner/integration evidence.
