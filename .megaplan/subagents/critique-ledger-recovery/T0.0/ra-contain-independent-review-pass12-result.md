# RA-CONTAIN independent review — pass 12

## Verdict

**HARD FAIL.**

The exact candidate is a clean descendant of the pass-11 recovery lineage and
the four pass-11 probes are substantially improved, but the candidate still has
an exploitable false-success replay path and a materialized-adapter durable-proof
race. It therefore cannot be locally accepted. Formal T0.0 is also not complete:
the plan still marks T0.0/RA-CONTAIN blocked, and this checkout contains no
owner-installed production boundary or accepted containment decision/receipt.

## Exact target and lineage

- Worktree: `/private/tmp/arnold-critique-recovery-ra-contain-20260802`
- Reviewed commit: `78641320e491a0f173efbba9e69b7981dd11e260`
- Tree: `9f0b8460b053eeafca037cba27e0415f2fcd8e3a`
- Parent: `6ec8066041687fa45c3e2b71760ec7874f8d027a` (pass-11 target)
- `git merge-base --is-ancestor 6ec8066041... HEAD`: exit 0
- `git merge-base --is-ancestor 6787d6363e HEAD`: exit 0
- `git status --porcelain=v1 --untracked-files=all`: empty before and after
- Candidate diff from pass 11: only `containment.py` and
  `test_containment.py`; `git diff --check HEAD^ HEAD`: clean.

## Commands and results

```text
PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority/test_containment.py
PASS: 68 passed

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority tests/run_authority/test_dependency_closure.py
PASS: 99 passed

PYTHONDONTWRITEBYTECODE=1 pytest -q -p no:cacheprovider \
  tests/arnold_pipelines/run_authority/test_containment.py -k \
  'final_cas or stalecas or rollback or wrong_target or state_specific or response_loss or external_anchor_uncertainty or expired_candidate or unknown or receipt or nonce or identity or restart'
PASS: 45 passed, 23 deselected
```

Disposable inline Python probes used only `tempfile.TemporaryDirectory`; scratch
paths were removed automatically. The exact outputs below are the important
results.

## Findings

### 1. Critical — ordinary replay accepts incomplete or forged local provenance

Location: `arnold_pipelines/run_authority/containment.py:1198-1233`, replay
call at `1470-1476` and `issue()` return at `1612-1614`.

`_lookup_identities()` collects only identity rows that happen to exist. It
returns the common result when at least one row remains; it does not require the
complete expected nonce/idempotency/operation identity set, does not verify the
`used_nonces` row when identities are found, and does not require or compare the
stored `requests` row. `_state()` validates the journal/head but none of these
side tables.

Probe: issue one valid envelope, then on a disposable SQLite journal delete the
operation identity, delete the nonce row, delete the request row, or delete the
nonce and idempotency identities. Replaying the exact signed envelope returned
`ACCEPTED True` in every case. A wrong nonce binding plus an extra identity also
returned `True`. The same missing-operation-identity replay was accepted after
constructing a fresh `LocalTestOwnerAnchorBackend` and `ContainmentStore`, so it
survives restart/materialization.

This violates the required complete decision/request/nonce/identity/journal
binding across replay and permits a corrupted or locally forged side bundle to
produce a positive containment result. The pass-11 stale-CAS tests do not cover
this ordinary replay branch.

### 2. Critical — materialized durable proof is not process-atomic

Locations: `LocalTestOwnerAnchorBackend.compare_and_swap()` and
`record_indeterminate()` wrappers at `719-729`; inherited
`verify_durable_commit()`/`verify_indeterminate()` at `575-596`.

The file-backed adapter reloads and takes the process lock for reads/CAS/marker
writes, but not for either durable verification operation. The inherited proof
uses the instance's in-memory `_head`. A disposable probe used a second
file-backed backend as a peer writer between final CAS and
`verify_durable_commit()`. The first backend's stale in-memory head was returned
as an apparently exact proof; `issue()` returned `active`, while the next
`status()` observed the peer's unresolved child and raised `IndeterminateState`.
Observed output:

```text
issue active
status_error IndeterminateState
```

This falsifies the repair report's claim that the local materialized adapter
provides an atomic durable proof and violates installed/materialized parity. An
accepted production adapter must implement the proof atomically, but none is
installed here. The same missing process-safe verification boundary exists for
the marker post-ack proof, although that path currently fails closed rather than
returning a positive result.

### 3. High — returned containment receipts are not complete decision bundles

Location: receipt construction at `1619-1620`; journal/request/identity storage
at `1241-1254`.

The returned receipt contains policy, target, decision, TTL, issuer, path, and
content hashes, but not the signed request digest/material, nonce, idempotency or
operation identity, journal record/hash-chain binding, backend domain/receipt,
or owner/backend authority identity. Those facts are split across mutable SQLite
side tables and the external head and are not included in the receipt returned
to the caller. Probe output showed the receipt omitted `nonce`, `idempotency_key`,
`operation`, `request_digest`, `journal_digest`, `record_hash`, `domain_id`, and
`backend_receipt` among others.

The final-CAS `_durable_bundle()` checks many of these facts at that instant, but
that is not a durable self-contained receipt and does not cure the replay gap in
Finding 1. This fails the pass-12 requirement that receipts pin decision,
target, effect, request, nonce, identity, journal, backend, and content across
crash/restart/replay.

## Pass-11 blocker disposition

- Exact authenticated final response without mutation: rejected by the new
  in-memory no-op regression, but not safe in the materialized adapter (Finding
  2).
- Indeterminate marking overwriting a concurrent child: exact-head marker CAS
  probes passed for the in-memory backend; the materialized post-ack proof is
  still not process-atomic.
- Stale-success reconciliation: complete nonce/identity/record/receipt
  corruption probes passed through `_accept_already_committed_cas()` and
  `_durable_bundle()`; the separate normal replay path remains broken (Finding
  1).
- Receipt pinning: backend key/byte substitution and restart-pinning tests
  passed locally, but complete receipt contents and replay binding fail (Finding
  3).

## Expiry, authority, and bypass checks

The focused expiry suite passed: an authenticated expired candidate can be
adopted as historical state, and later `check()` refuses it. Signed-envelope
expiry is rechecked after lock acquisition. The seven effect classes remain
observe-allowed and six mutation/effect classes denied on the tested happy path.
Wrong target, operation, tuple, malformed head, fork/truncation, response loss,
and ordinary two-process CAS race tests passed.

No production Run Authority/Custody/WBC/epoch/fence integration is present to
verify admission authority, stale leases, owner absence, actual installed parity,
200-observer behavior, cloud/provider ambiguity, or production legacy bypasses.
The plan explicitly requires an accepted owner-installed RA-CONTAIN boundary and
an actual decision/receipt; the implementation deliberately rejects production
construction at `851-853`, `865-875`, and the CLI rejects the absent production
backend at `1761-1763`. The T0.0 plan remains `[ ]`/`BLOCKED` at plan lines
200-207, with the current next action still obtaining the named interface.
This is fail-closed absence, not formal completion.

No code, commit, deploy, cloud state, or non-scratch path was mutated by this
review. The only requested write is this result artifact.
