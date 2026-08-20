FAIL

# RA-CONTAIN adversarial review pass 7

Reviewed exact commit `25dc026546b9586db63ec0a39e5987321bf4bd0f` in
`/private/tmp/arnold-critique-recovery-ra-contain-20260802`, read the pass-6
FAIL report, and re-ran its findings independently. The local test primitive
is materially improved, but this commit still has recovery/security defects
and formal T0.0 remains blocked on an accepted GEN-DEPLOY owner backend,
cloud installation, and an actual owner decision.

## Findings

### 1. CRITICAL — reconciliation can strand a valid journal after its own final-CAS ambiguity

Locations: `arnold_pipelines/run_authority/containment.py:995-1005`,
`:1028-1038`, and `:1097-1124` (`_mark_unknown`, `_finish_pending`,
`reconcile`).

The ordinary pending-CAS and final-CAS ambiguity paths now recover correctly,
and successful reconciliation does authenticate `status()` plus `observe` and
all six denied effects. However, reconciliation itself is implemented as a
durable journal write followed by a CAS. If that reconciliation CAS commits
but its response is lost, `_mark_unknown(pending, ...)` records an indeterminate
head from the *original* pending transition. The journal already contains the
reconcile record, while the indeterminate head still points at the original
candidate/base cursor and digest. Exact replay calls `_state()` and remains
indeterminate; a new reconcile sees neither exact base nor exact candidate.

Reproduction (ephemeral fault-injection backend):

```text
issue final-CAS response loss -> StorageError; head = indeterminate(issue)
reconcile final-CAS response loss -> StorageError
head = indeterminate(issue), journal records = [issue, reconcile]
same reconcile -> IndeterminateState(owner anchor has an unresolved transition)
fresh reconcile -> IndeterminateState(pending journal is neither exact candidate nor exact base)
status -> IndeterminateState
```

Minimum root fix: give reconciliation its own authenticated transition record
and recovery metadata, or make its final-CAS ambiguity resumable by recognizing
the durable reconcile record and its request/result identity. Every crash
point in reconciliation must permit a later authenticated owner reconciliation
to reach a committed head whose operation, request digest, record hash,
receipt digest, `status()`, and every `check` effect agree.

### 2. HIGH — signed requests can execute after expiry while waiting for the journal lock

Locations: `_request` at `:1040-1044`, and lock acquisition in `issue`,
`terminate`, and `reconcile` at `:1060`, `:1078`, and `:1093`.

Envelope expiry is checked before `_locked()` and never checked again after
the lock is acquired. A valid signed request can therefore expire while
waiting behind another process and still issue, terminate, or reconcile.

Reproduction: sign an issue envelope with `expires_at=time.time()+0.03`,
replace the ephemeral store lock context with one that sleeps `0.08` seconds,
then call `issue`. Observed: `expired-after-wait accepted active`. An already
expired envelope is rejected as `UnauthorizedOwner`, so the defect is the
acceptance-time race rather than signature validation.

Minimum root fix: revalidate the signed envelope, including expiry, after
acquiring the journal lock and immediately before reserving/performing the
operation, using a non-overridable acceptance clock.

### 3. HIGH — provisioning can permanently strand a one-time external genesis

Locations: `ContainmentStore.provision` at `:741-753`.

The code durably reserves the provisioning nonce and calls
`provision_genesis` before creating the SQLite journal and its provisioning
metadata. If the genesis call commits but its response is lost, the owner
anchor is provisioned while the journal does not exist. Retrying the same
provisioning receipt gets `UnauthorizedOwner: owner anchor provisioning is
one-time`; there is no authenticated resume/adoption path.

Reproduction with a backend that calls `super().provision_genesis()` and then
raises `OSError("response after genesis commit")`:

```text
first provision -> OSError; anchor sequence=0; journal_exists=False
retry same receipt -> UnauthorizedOwner(owner anchor provisioning is one-time)
```

Minimum root fix: make provisioning an authenticated, resumable transaction
whose genesis and journal metadata can be adopted/replayed after response
ambiguity, or provide a dedicated owner-authorized recovery path. Do not leave
a valid external genesis with no recoverable canonical journal.

### 4. HIGH — terminate ignores the signed incident tuple

Locations: `terminate` at `:1075-1087`.

The signed terminate request contains `target`, but the implementation checks
only the decision ID against the active receipt. A request signed for a
different exact tuple can terminate the active decision and records no target
binding in the journal.

Reproduction: issue decision `D` for tuple A, then sign terminate with
decision ID `D` and tuple B. Observed: `terminate result ... state='terminated'`;
the tuple-A observation is then refused. The operation should not silently
discard a signed identity field.

Minimum root fix: require `request["target"] == current["exact_tuple"]` before
constructing the terminate candidate, and bind/validate that relationship in
the terminate record and replay checks. Treat a mismatch as a typed conflict
or authorization refusal.

### 5. MEDIUM — sequence-zero heads accept a non-genesis predecessor revision

Location: `_validate_head` at `:644-645` and genesis checks at `:654-656`.

For `sequence == 0`, the code skips validation of `previous_revision` against
`GENESIS_REVISION`. A caller controlling a test backend can set
`previous_revision="f"*64`, recompute the authenticated head revision and
backend receipt, and `status()` accepts the head with cursor zero.

Minimum root fix: require `previous_revision == GENESIS_REVISION` whenever
`sequence == 0`; validate the same invariant in every backend's genesis
provisioning path.

### 6. MEDIUM — pending-head schema admits indeterminate-only fields

Locations: exact-field gate and state branches at `:625-635` and `:651-661`.

`occurrence` is allowed by the global optional-field gate and is only rejected
when non-null on a committed head. A pending head carrying an arbitrary
`occurrence` object passes `_validate_head`; `occurrence` should be exclusive
to an indeterminate head and pending fields should be checked against the
predecessor transition.

Reproduction: construct a pending head with valid sequence/transition digests,
`candidate_record_hash == candidate_digest`, and
`occurrence={"unexpected": true}`, recompute its authenticated revision and
backend receipt, and call `_validate_head`. Observed: `pending-occurrence
accepted`.

Minimum root fix: use exact state-specific field sets; reject `occurrence` on
committed/pending heads and require every indeterminate-only field to be
present and semantically bound only for `indeterminate`.

## Production authority boundary

The new `ReleaseAuthorityBackend` ABC at `:357-388` is a sound unavailable
integration seam in this commit: it has no implementation, and both
`ContainmentStore` production paths at `:716-717` and `:730-734` fail closed
with typed `ReleaseAuthorityUnavailable`. The CLI at `:1193-1196` does the
same. `InMemoryOwnerAnchorBackend`, `LocalTestOwnerAnchorBackend`, caller
subclasses, caller-selected `OwnerTrustBundle`/domain, self-signed heads,
deserialization, and ordinary monkeypatch/subclass attempts therefore do not
create production authority. A paired local journal+anchor+test-key rollback
still restores an active local test state (`cursor=1`, `observe=ALLOWED`), but
constructing it as production returns
`ReleaseAuthorityUnavailable(external_authority_unavailable)`.

This is correct fail-closed behavior, not formal T0.0 completion. Formal
completion still requires the accepted external owner integration with pinned
identity/trust root, monotonic durable CAS, nonce/idempotency fencing,
rollback/fork detection, deployment/cloud installation, and an actual owner
decision.

## Prior pass-6 findings independently re-tested

- Caller-chosen `production_capable`/`mode`/self-signed authority: fixed by
  unconditional typed production unavailability; no production credit granted.
- Pending-CAS and normal final-CAS ambiguity: fixed locally. Reconciliation
  commits `operation="reconcile"`, and its successful path returns only after
  authenticated `status()` and all seven effect checks. Finding 1 above is the
  remaining reconciliation-self-fault gap.
- Decision/idempotency/nonce/operation replay: exact replay is stable across
  restart, termination, and normal reconciliation; divergent identity content
  raises `DuplicateConflict` in the tested paths.
- CLI `check --effect`: `observe` and all six denied effects pass; malformed
  descriptor/JSON/unknown effect/action paths produce no traceback. There is
  no hard-coded observe path.
- Paired local rollback: still possible only inside explicitly named test mode;
  production construction rejects it.
- Strict bool/int, non-finite TTL, unknown journal fields, cursor/hash/receipt
  relationships, TTL boundary, explicit revoke, restart, and fork tests held
  apart from findings 5-6.
- Generic `contracts.py`/`reducer.py` remain persistence-neutral; the focused
  dependency-boundary test is an improvement, not a regression. No required
  prior coverage was deleted; the containment suite expanded from the prior
  12 tests to 29 collected cases.

## Commands and results

```text
pytest -q tests/arnold_pipelines/run_authority/test_containment.py \
  tests/arnold_pipelines/run_authority/test_contracts.py \
  tests/arnold_pipelines/run_authority/test_reducer.py \
  tests/run_authority/test_dependency_closure.py
  60 passed in 2.64s

pytest --collect-only -q tests/arnold_pipelines/run_authority/test_containment.py
  29 cases collected

uv lock --check
  Resolved 81 packages in 30ms; lock consistent

python -m compileall -q arnold_pipelines/run_authority tests/arnold_pipelines/run_authority
  passed

uv build --out-dir <ephemeral temporary directory>
  source distribution and wheel built

<ephemeral venv>/pip install --no-deps <wheel> \
  (with cryptography installed in that venv)
  installed-wheel imports passed from site-packages

git diff --check 25dc026546^ 25dc026546
  clean
git status --short --branch
  clean worktree at the requested commit
```

Additional ephemeral probes covered: both pending-CAS and normal final-CAS
fault families; reconciliation final-CAS response loss; journal-write-after-
commit ambiguity; 8-thread issue race (one accepted, seven `StaleCAS`, one
record); separate-process race (one success, one typed failure); expired
envelope before and after lock wait; paired local rollback; terminate tuple
mismatch; genesis predecessor and pending schema mutation; all CLI effects;
and expired receipt behavior across restart.
