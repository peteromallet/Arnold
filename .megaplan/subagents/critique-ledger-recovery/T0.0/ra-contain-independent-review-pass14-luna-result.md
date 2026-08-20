# RA-CONTAIN independent review pass 14 — GPT-5.6 Luna

Date: 2026-08-02  
Verdict: **PASS (local exact-candidate eligibility only)**

## Exact subject and custody

Reviewed frozen worktree
`/private/tmp/arnold-critique-recovery-ra-contain-20260802`:

```text
HEAD    48e13e1bcbc6769aff753270331d52ac1c148125
tree    550421e34c1e789e31d173fdf35fdd7fd55ce287
parent  88393e2d0da80d76205ba03ddabf7577d864306b
status  clean before and after review
```

The commit changes exactly:

```text
M arnold_pipelines/run_authority/containment.py
M tests/arnold_pipelines/run_authority/test_containment.py
```

The supplied repair report SHA-256 independently matched
`0b56860c96cdde292998d6338b2d73e92876e0f794c6c5c1a930d42bd413181e`.
I treated it only as a lead and independently inspected the diff, implementation,
tests and exact commands.

Changed-file SHA-256 values independently matched:

```text
f54adbe847e2dc936b0a288d65e96d58c1adedb7306a3044160cd85170d6183b  arnold_pipelines/run_authority/containment.py
1049b1ca0178001f9b9ce12c741253d8b47c1e9334d1372e3d941cdadd07188e  tests/arnold_pipelines/run_authority/test_containment.py
```

## Six-item finite matrix

| # | Verdict | Independent basis |
|---|---|---|
| 1. Durable backend nonce/identity is canonical proof | **PASS** | Both ordinary replay and initial durable proof include the exact request-scoped SQLite nonce projection (`containment.py:1250-1261,1398-1411,1584-1597`). The backend requires exactly `{request nonce: request digest}` and equality with its materialized nonce authority (`:580-603`). Delete, wrong digest and extra same-request alias fail across restart (`test_containment.py:1480-1527`). |
| 2. Pre-existing backend instance becomes stale after anchor mutation | **PASS** | Construction and every file-backed use go through the process lock and `_reload`; missing/partial/replaced anchor, key or receipt identity clears cached state and raises typed `CorruptAnchor` (`containment.py:649-660,706-790`). The six delete/replace cases exercise the same already-created store/backend (`test_containment.py:1529-1562`). |
| 3. Issue/reconcile/replay return one complete canonical receipt | **PASS** | `_complete_operation_receipt` binds request, subject/target, policy, identities, journal, backend head/receipt, owner and result with a bundle hash (`containment.py:1263-1324`). Reconcile first run, durable resume and replay return `_returned_operation_receipt`, not the mutable result projection (`:1794-1810,1891-1939`). First/replay/restart byte equality and side-row corruption are covered at `test_containment.py:1565-1673`; ordinary issue/replay coverage remains at `:1344-1436`. |
| 4. Linearization semantics | **PASS** | Proof linearizes inside the SQLite writer transaction and materialized backend process lock; the receipt pins that revision (`containment.py:1557-1565`). A peer landing before proof yields typed indeterminate/storage failure (`test_containment.py:1438-1477`). A legitimate signed peer terminate after proof but before the first caller returns is accepted as later history; the original receipt remains replayable while current status advances (`:1676-1760`). This correctly avoids an impossible no-future-writer invariant. |
| 5. Hostile deletion/replacement, stale identities, concurrency, response loss, replay and observers | **PASS** | The exact containment suite, 27-case preservation selection, 39-case hostile selection, separate-process races, response-loss cases and 200-observer closure tests all pass. No reviewed path converts corruption, stale CAS, unknown completion or conflicting replay into success. |
| 6. Production remains unavailable without owner-installed backend | **PASS** | Both construction and provisioning unconditionally raise `ReleaseAuthorityUnavailable` for `mode='production'`; test mode requires the named test backend (`containment.py:894-923`). Production rejection and self-minted/caller-selected backend cases are exercised at `test_containment.py:76-157`. Local SQLite cannot mint T0.0 authority. |

## Commands and exact results

All pytest runs used:

```text
PYTHONDONTWRITEBYTECODE=1
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
-p no:cacheprovider
```

Containment suite:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py
```

Result: `89 passed in 2.99s`.

Exact blocker and linearization selection:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py \
  -k 'backend_nonce_authority or stale_materialized_instance or reconcile_returns_one_complete or before_linearization or after_linearization'
```

Result: `12 passed, 77 deselected in 0.45s`.

Replay/final-CAS/marker/expiry/process preservation selection:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py \
  -k 'ordinary_replay or complete_receipt or materialized_commit_proof or backend_nonce_authority or stale_materialized_instance or reconcile_returns_one_complete or after_linearization or exact_authenticated_final_cas_noop or final_stalecas or marker_race or ttl_boundary or expired_candidate or separate_process_races'
```

Result: `27 passed, 62 deselected in 0.86s`.

Full Run Authority and closure suite:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority \
  tests/run_authority/test_dependency_closure.py \
  tests/cloud/test_m1_containment_acceptance.py
```

Result: `130 passed in 12.13s`.

Independent broad hostile preservation selection:

```text
python -m pytest -p no:cacheprovider -q \
  tests/arnold_pipelines/run_authority/test_containment.py \
  -k 'unauthorized or delete or replace or stale or response_loss or replay or separate_process or observer or production'
```

Result: `39 passed, 50 deselected in 1.36s`.

Read-only syntax parsing of both changed Python files: PASS.  
`git diff --check HEAD^`: PASS.  
Final `git status --porcelain=v1`: empty.

## Independent code assessment

The nonce fix closes both halves of the prior split-brain: SQLite must contain
one exact nonce row for the request, and the materialized backend must contain
the same request-scoped projection. An unrelated nonce remains valid history;
an extra nonce bound to this request is corruption. That is the correct scope.

The stale-instance fix does not rely on constructor-time caching. `_reload`
validates an exact `{head, nonces}` document, private key and pinned receipt
identity under the shared process lock at point of use. A missing anchor is
accepted only for a genuinely pristine never-materialized instance. Once any
material exists or cached authority existed, deletion is corruption.

The receipt fix preserves the semantic result inside the journal record while
returning its complete authenticated operation bundle. Reconcile replay first
checks identities, durable record, result equality, owner head and stored
complete receipt before returning. A mutable result-side row therefore cannot
substitute for the receipt.

The linearization test exercises the important ordering rather than caller
return order. The first operation has already durably proved its exact revision
before the outer caller pauses. The second signed CAS is therefore later valid
history. Requiring the first receipt to equal current status would incorrectly
ban every future writer and is not imposed.

## Limits and authority boundary

- This is a local review of the exact frozen candidate only.
- The local backend is explicitly test-only.
- No owner-installed production `ReleaseAuthorityBackend`, production decision,
  grant, fence, incident disposition or accepted receipt exists here.
- No cloud/provider endpoint or production store was contacted.
- No production adapter behavior was inferred from SQLite.
- This PASS makes commit `48e13e1...` eligible for clean-lineage integration;
  any conflict resolution or later semantic change requires rerun/review.
- T0.0 remains formally incomplete until the owner-installed decision and
  receipt exist. This report does not authorize T0.1 or checklist completion.

## Mutation statement

No candidate/code/Git/cloud/provider/process/production-owner/checklist state
was mutated. Test artifacts were confined to pytest temporary directories;
bytecode and pytest cache writes were disabled. The only persistent write is
this review report.

## Final verdict

**PASS (local exact-candidate eligibility only).** All six frozen pass-13
counterexample classes pass independently, including the correct before/after
linearization distinction. No new blocker was found within the finite review
scope. Formal T0.0 remains open pending owner-installed production authority.

The SHA-256 of this report is recorded externally after finalization to avoid a
self-referential digest.
