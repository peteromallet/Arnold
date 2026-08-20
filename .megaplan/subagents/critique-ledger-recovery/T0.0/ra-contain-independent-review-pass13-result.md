# RA-CONTAIN independent review — pass 13

## Verdict

**HARD FAIL.**

The exact pass-12 repair commit closes the three pass-12 findings on the
ordinary SQLite side-table cases and closes the specific peer-before-proof
regression, but the candidate still has false-success and incomplete-receipt
paths.  The local test/materialized boundary is therefore not acceptable.
Formal T0.0 is also incomplete: no owner-installed production boundary or
accepted owner containment decision/receipt exists in this checkout.

## Exact target and lineage

- Worktree: `/private/tmp/arnold-critique-recovery-ra-contain-20260802`
- Commit: `88393e2d0da80d76205ba03ddabf7577d864306b`
- Tree: `757f8522c9fc174718d3b8f45d13808bc1f9b2b4`
- Parent/pass-12 repair base: `78641320e491a0f173efbba9e69b7981dd11e260`
  (tree `9f0b8460b053eeafca037cba27e0415f2fcd8e3a`)
- Pass-11 ancestor: `6ec8066041687fa45c3e2b71760ec7874f8d027a`
- `git merge-base --is-ancestor 78641320e4 HEAD`: exit 0
- `git merge-base --is-ancestor 6ec8066041 HEAD`: exit 0
- Worktree was clean; pass-13 changes are not in the worktree.
- Pass-13 commit diff contains only:
  `arnold_pipelines/run_authority/containment.py` and
  `tests/arnold_pipelines/run_authority/test_containment.py`.

## Commands and results

```text
git rev-parse HEAD HEAD^{tree}
88393e2d0da80d76205ba03ddabf7577d864306b
757f8522c9fc174718d3b8f45d13808bc1f9b2b4

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py \
  tests/cloud/test_m1_containment_acceptance.py
119 passed in 13.01s

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority/test_containment.py
78 passed in 3.12s

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority/test_containment.py -k \
  'ordinary_replay or complete_receipt or materialized_commit_proof or exact_authenticated_final_cas_noop or final_stalecas or marker_race or ttl_boundary or expired_candidate or separate_process_races'
16 passed, 62 deselected in 0.49s

git diff --check 78641320e4..88393e2d0d
PASS (no output)
```

The repository tests reproduce the pass-12 ordinary replay deletions, forged
extra identity, receipt corruption, restart/finalization, and the peer-writer-
before-proof case.  A 200-observer disposable-thread probe also produced
`observers 200 success True` on an intact materialized anchor.

## Findings

### 1. Critical — materialized backend nonce authority is outside the replay proof

Locations: `containment.py:575-592` (`verify_durable_commit`) and
`containment.py:747-762` (`_verify_materialized`).

The SQLite replay branch checks `used_nonces`, but the file-backed owner
backend also persists its authoritative nonce map in the anchor JSON.  The
backend durable proof checks the supplied journal identity map and nonce name,
but never checks `self._used_nonces[nonce] == request_digest` (or requires the
exact backend nonce map).  `_verify_materialized` only proves that the bytes
were stable and equal to the backend instance's in-memory state; it does not
prove that the nonce entry belongs to the request.

Disposable reproduction, including restart:

1. Provision a `LocalTestOwnerAnchorBackend`, issue a signed request, and save
   the successful complete receipt.
2. Delete the request nonce from `anchor.json` (or replace its digest with
   `f` repeated 64 times).
3. Construct a fresh `LocalTestOwnerAnchorBackend` and `ContainmentStore`.
4. Replay the exact original signed envelope.

Observed result: `replay after restart/delete backend nonce True` (and the
wrong-digest substitution likewise returned the original receipt).  This is a
false success after corruption of one of the required nonce/backend-authority
bytes, contrary to the complete exact bundle requirement.  The SQLite nonce
row is not a substitute for the owner backend's persisted nonce authority.

### 2. Critical — stale materialized instance accepts a deleted anchor

Location: `containment.py:705-718`.

`LocalTestOwnerAnchorBackend._reload()` returns without changing state when
`self.path` does not exist.  An already-created backend therefore retains its
old `_head` and `_used_nonces`.  After a valid issue, deleting the anchor file
and calling `store.status()` on that stale instance returned `cursor 1`
instead of failing closed.  The same instance's replay later failed during
durable-proof byte reading, but the positive status already demonstrates that
anchor absence/replacement can be treated as authoritative state.

This directly attacks the requested stale-instance, path replacement, and
partial-loss cases.  A missing authoritative file must clear/reject stale
state, not return the previous in-memory head.

### 3. Critical — proof lock ends before operation success is returned

Locations: `containment.py:747-762`, `1517-1566`, `1622-1625`, and
`1403-1413`.

The repair correctly reloads and process-locks the file during
`_verify_materialized`, and the supplied regression catches a peer that writes
before that proof.  However, the lock is released when `_verify_materialized`
returns.  `_durable_bundle()` then still finalizes the SQLite receipt and the
transition returns through `_returned_operation_receipt()` without another
owner-head proof.

Adversarial reproduction: wrap `verify_durable_commit`; after its original
proof returns (and its process lock has released), use a second
`LocalTestOwnerAnchorBackend` to acquire the normal process lock and write a
valid pending child.  The first `issue()` returned `active` with a complete
bundle, while the immediate subsequent `status()` raised
`IndeterminateState owner anchor has an unresolved transition`.

This is a cooperative peer-writer race after proof and before the caller gets
success, not merely an uncooperative byte hack.  It violates the stated
requirement that peer writer/rename/replacement must never let `issue()` or
replay return success while subsequent status is indeterminate or conflicting.
The same proof boundary is not a linearized transaction over the whole
acceptance/return path.

### 4. High/Critical — reconcile returns an incomplete result, not the canonical receipt

Locations: `containment.py:1758`, `1855-1858`, `1873`, and `1886`.

Issue and terminate now return `_returned_operation_receipt()`, but both fresh
reconcile completion and durable-reconcile replay return `result`/`record["result"]`
directly.  A reproduceable unresolved-issue recovery returned only
`['cursor', 'journal_digest', 'state']` for an empty result and
`'bundle_hash' in output` was false.  Active reconciliation returns the old
containment result fields, also without request, nonce, identity, journal,
backend, owner, and bundle bindings.

The operation receipt is written and finalized in the side table, but the
caller-visible reconcile response is not that receipt.  A mutable side table
cannot fill a missing receipt binding.  The same gap exists on reconcile replay
and after restart, so this is an incomplete returned authority artifact even
though the internal durable commit proof may pass.

## Pass-12 defect disposition

- Ordinary SQLite missing/extra/wrong identity, nonce, request, record, and
  receipt cases: reproduced as fail-closed by the 16-test focused selection;
  the new backend-nonce corruption case remains open.
- Materialized peer writer before durable proof: the new test passes and the
  stale in-memory proof from pass 12 is no longer observed.
- Complete issue/terminate receipt contents, hash, restart replay, later
  history, and receipt-side corruption: pass on the tested branches.
- Complete receipt return for reconcile: not repaired; finding 4.

## Attack matrix and limitations

- Final-CAS lying/unchanged/missing-receipt responses: existing regression
  tests pass; exact authenticated CAS no-op does not return success.
- Exact already-committed adoption and restart: existing stale-CAS tests pass.
- Indeterminate marker race and fake marker acknowledgement: existing tests
  fail closed and do not overwrite a competing head.
- Expiry: existing tests pass the intended distinction: an authenticated
  expired candidate may be adopted as historical state, while later
  `check()` denies its expired active authorization.
- Wrong target/operation/tuple, malformed/forked/reordered journal, corrupt
  anchor/receipt, response loss, and two-process issue race: covered tests
  passed.  Disposable read-error/ENOSPC injections did not return success
  (the earliest ENOSPC at `reserve_nonce` escapes as raw `OSError`, while a
  later ENOSPC fails as `IndeterminateState`); they do not cure the stale-file
  and post-proof races above.
- The 200-observer probe passed only with an intact anchor and does not prove
  production semantics.
- No accepted production `ReleaseAuthorityBackend` implementation is shipped
  or installed.  `ContainmentStore` rejects `mode="production"` at
  `containment.py:880-882` and `provision()` rejects it at `894-903`; the CLI
  rejects absence of the production backend at `1951-1956` and only constructs
  `LocalTestOwnerAnchorBackend` in test mode.  This is correctly fail-closed
  owner absence, not formal T0.0 completion.
- Repo search found no production call site connecting `ContainmentStore` to
  the action/effect paths.  The separate `current_source`/`action_gate`
  implementation evaluates generic grant/fence/decision records and does not
  invoke RA-CONTAIN.  Thus installed/materialized parity, real owner fence/
  epoch/lease semantics, and production direct/legacy bypass closure cannot be
  accepted from this checkout; no cloud or installed-owner inspection was
  performed.
- Local backend methods are intentionally exposed as test adapters and are
  guarded by the production constructor.  No caller-created object was
  accepted in production mode in the tested probes.

No code, commit, cloud state, production owner, or containment decision was
mutated.  Disposable probe files were confined to temporary directories.  The
only durable write from this review is this result artifact.

## Local verdict

**HARD FAIL.**
