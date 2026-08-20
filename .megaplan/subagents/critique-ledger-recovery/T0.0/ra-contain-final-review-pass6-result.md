FAIL

# RA-CONTAIN adversarial review pass 6

Reviewed exact commit `611321c79c70d3ec75cf6f7be6ba3df275eb5e81` in
`/private/tmp/arnold-critique-recovery-ra-contain-20260802`. The local
cryptographic checks and journal/anchor comparison are directionally sound,
but the commit has correctness defects and does not provide an accepted
production owner backend. Formal T0.0 therefore remains incomplete.

## Findings

### 1. CRITICAL — no usable production authority, and the generic production path is self-authorizing

Locations: `arnold_pipelines/run_authority/containment.py:344-356`,
`:363-367`, `:486-487`, `:603-643`, and CLI `:981-988`.

The only implementations in the tree are `InMemoryOwnerAnchorBackend` and
`LocalTestOwnerAnchorBackend`; both set `production_capable = False`. The
production constructor/provisioner only checks a caller-controlled boolean
attribute and rejects the two named test modes. The CLI unconditionally
rejects production at line 985 and only constructs the local test backend.
There is no accepted Release/Run Authority adapter or deployment/decision
that supplies an owner-controlled monotonic anchor.

More seriously, the generic API accepts the caller's `OwnerTrustBundle`,
provisioning envelope, domain string, and backend object. `_verify_envelope`
verifies a signature against the public key supplied in that same trust
bundle; it does not authenticate that trust bundle against an external owner
root. `_validate_head` delegates backend receipt verification, while the
in-memory receipt embeds its own public key in the untrusted head. The
protocol does not enforce monotonicity, non-equivocation, rollback resistance,
or a pinned backend identity.

Reproduction (a caller-created subclass is accepted as “production”):

```text
python - <<'PY'
import tempfile
from pathlib import Path
from arnold_pipelines.run_authority.containment import *
S={k:k+'-v' for k in ('selection_session','spec','workspace','plan','branch','profile','runtime')}
class CallerChosen(InMemoryOwnerAnchorBackend):
    production_capable=True
    mode='external'
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'j.sqlite'; b=CallerChosen('caller-chosen-domain')
    s=OwnerSigner('caller-chosen-owner'); t=s.trust_bundle()
    e=s.sign_provisioning(journal_path=str(p), anchor_domain=b.domain_id,
                          target=S, mode='production')
    st=ContainmentStore.provision(p,b,t,e,mode='production')
    print(st.status()['owner_id'], st.status()['anchor_domain'])
PY
```

Observed: `caller-chosen-owner caller-chosen-domain`.

Minimum root fix: provide and accept a real external owner adapter whose
domain, owner identity, trust root, backend signing key, sequence, and CAS
semantics are provisioned out-of-band and cannot be selected by the caller.
Verify heads against a pinned backend/owner key and make the adapter itself
enforce monotonic durable CAS and fork/rollback detection. Wire the accepted
adapter into production construction and deployment, or explicitly keep T0.0
blocked; a duck-typed `production_capable` flag is not an authority boundary.

### 2. HIGH — reconciliation can return success while committing an invalid history

Locations: `_finish_pending` at `containment.py:860-870`,
`reconcile` at `:908-926`, and the semantic check at `:788-794`.

`_finish_pending` copies `pending` into `committed` without changing
`operation` to `"reconcile"`, even though it appends a journal record whose
`op` is `"reconcile"` at line 921. The next status/check compares the anchor
operation with the last journal operation and rejects the recovered state.

Reproduction with a response failure after the second CAS:

```text
python - <<'PY'
# Same setup as the repository's CommitTimeoutBackend test, but after
# reconcile also call status(). The result is:
# issue: StorageError
# reconcile: active
# status: AuthorityMismatch owner head operation is not bound to the canonical journal record
PY
```

The full probe used an `InMemoryOwnerAnchorBackend` subclass that raises after
its second `compare_and_swap` commit; it produced exactly the output above.
With a failure after the first pending CAS (`fail_next("cas_response")`),
`_mark_unknown` records an indeterminate head carrying `operation="genesis"`.
Reconciliation then attempts to commit a non-genesis sequence with genesis
operation and fails `CorruptAnchor` (“genesis owner anchor invariants are
invalid”). Thus both pending-CAS and final-CAS uncertainty paths can leave
reconciliation unable to produce a valid state.

Minimum root fix: construct the reconciliation committed head explicitly with
`operation="reconcile"`, the reconciliation request digest, and the exact
reconciliation record hash; preserve the prior/candidate data only as
validated transition evidence. Define and validate the indeterminate-head
operation semantics, then require a post-commit authenticated replay before
returning success. Add a regression that calls `status()` and `check()` after
every successful reconciliation.

### 3. HIGH — rolling back both local journal and local anchor resurrects authority

Locations: `LocalTestOwnerAnchorBackend` at `containment.py:486-537`,
especially `_persist` at `:504-518`; local construction is permitted by
`:615-616` and used by the CLI at `:986-991`.

The local anchor is an adjacent JSON file. Restoring both that file and the
SQLite journal to a previously active snapshot restores an active authority;
the backend receipt is valid because the restored head and its test key are
also restored.

Fresh reproduction:

```text
python - <<'PY'
# Provision LocalTestOwnerAnchorBackend, issue an active receipt, save both
# journal.sqlite and anchor.json, terminate, restore both saved files, create
# a fresh LocalTestOwnerAnchorBackend, and call status/check.
# Observed: paired rollback status: committed ALLOWED DENIED
PY
```

The restored state therefore authorizes observation against the old active
receipt; the external owner head has not detected the rollback. The existing
test only rolls back the journal while leaving the in-memory external head in
place, so it does not cover this case.

Minimum root fix: do not use local files as the authority for any accepted
production or security claim. Use an owner-controlled monotonic anchor outside
the rollback domain, and make the local adapter an explicitly non-authorizing
fixture. If local mode is retained for tests, add a paired-rollback test that
expects refusal rather than treating the adapter as a proof of containment.

### 4. HIGH — decision and idempotency identities are not globally conflict-fenced

Locations: `issue` at `containment.py:878-893`, `terminate` at `:895-906`,
and nonce/journal handling at `:809-817` and `:453-457`.

The implementation checks only whether the current receipt is active. After
termination, it does not search the append-only history for the same
`decision_id`, and it never consults the persisted `used_nonces` request
digest. The external backend reserves only the nonce, not the signed
`idempotency_key` or decision identity. Consequently, a reused decision ID
and idempotency key with a new nonce and divergent target/reason is accepted
as a new issue.

Fresh reproduction observed:

```text
divergent duplicate accepted: D different two
```

The probe issued `decision_id="D", idempotency_key="K"`, terminated it, then
issued a second signed request with the same `D` and `K`, a new nonce, a
different workspace, and reason `two`. It was accepted.

Minimum root fix: persist an authenticated mapping from every operation and
decision identity to its canonical request digest (and relevant result),
atomically with the journal transition and owner head. Exact replay must be
handled deterministically; any same-ID/different-content request must raise a
typed conflict, including after termination and across restart/path changes.

### 5. HIGH — CLI `check` cannot accept or enforce the requested effect

Locations: subparser construction at `containment.py:973-976`, hard-coded
calls at `:995` and `:1001`.

The CLI defines only `check --tuple`; it has no effect argument. Both check
paths call `store.check(..., "observe")`, so the installed interface cannot
query `execute`, `deployment`, or any other denied effect. The library method
does correctly deny those effects, but that does not satisfy the CLI contract.

Reproduction:

```text
python -m arnold_pipelines.run_authority.containment --help
```

The help output shows `check` but no `--effect`. Passing `--effect execute`
is an unrecognized argument. The prior test that exercised
`--effect deployment` was removed in this commit.

Minimum root fix: make `--effect` required (or define an unambiguous effect
positional), validate it through `store.check`, and remove both hard-coded
`"observe"` calls. Add CLI tests for every denied effect and observe.

### 6. MEDIUM — malformed CLI backend descriptors still produce tracebacks

Location: `containment.py:986-988`; the catch at `:1003-1004` does not catch
`KeyError`.

With a valid trust-bundle file and an anchor descriptor containing only
`{"kind":"test/local"}`, the CLI executes `descriptor["path"]` and exits
with return code 1 plus a traceback ending in `KeyError: 'path'`, instead of
the promised machine-readable JSON error.

Minimum root fix: validate the descriptor's exact field set before indexing,
convert missing/invalid fields to `ContainmentError`/`UnauthorizedOwner`, and
make the CLI boundary catch all expected schema/lookup failures without
catching `BaseException`.

### 7. MEDIUM — the independence test was weakened rather than scoped correctly

Location: `tests/arnold_pipelines/run_authority/test_contracts.py:236-243`.

The commit removes `"pathlib"` and `"sqlite"` from the forbidden terms while
continuing to scan every `*.py` file in the entire `run_authority` package.
That makes the test pass if persistence imports appear in the generic
contracts/reducer/current-source layer. The current `contracts.py` happens to
remain persistence-neutral, but the change is a binding-test weakening, not
an architectural proof. Persistence belongs in the containment adapter; the
test should scan `contracts.py` (and explicitly assert its import boundary),
not whitelist persistence terms for the whole package.

Minimum root fix: restore the forbidden terms for the persistence-neutral
contract module, or change the test scope to the exact modules that define the
generic contract boundary and add a separate allowed-adapter test.

## Checks that held in the local substrate

These are not a production-authority proof: a single-journal rollback with
the owner backend left intact was rejected; malformed stored receipts with
unknown fields, boolean/NaN TTLs, boolean cursors, and invalid cursor
relationships raised `CorruptJournal`; an owner-key mismatch with the same
`owner_id` raised `UnauthorizedOwner`; a signed envelope for a different
journal path raised `UnauthorizedOwner`; TTL expiry at the exact boundary
raised `PolicyRefusal`; and eight threaded issue attempts produced one valid
record and seven `StaleCAS` outcomes. These passing cases do not cure the
paired local rollback, recovery, replay, CLI, or production-adapter failures
above.

## Re-tested behavior and commands

Commands run against the pinned checkout:

```text
python -m pytest -q tests/arnold_pipelines/run_authority/test_containment.py tests/arnold_pipelines/run_authority/test_contracts.py
# 18 passed

python -m pytest -q tests/arnold_pipelines/run_authority/test_containment.py tests/arnold_pipelines/run_authority/test_contracts.py tests/run_authority/test_dependency_closure.py
# 30 passed

git diff --check 611321c79c70d3ec75cf6f7be6ba3df275eb5e81^ 611321c79c70d3ec75cf6f7be6ba3df275eb5e81
rg -n 'production_capable|class .*OwnerAnchorBackend|mode = "external"|Release Authority' arnold_pipelines tests
```

The malformed-receipt cases were run by an inline `python - <<'PY'` probe
against a freshly provisioned store; unknown fields, boolean/NaN TTL, boolean
cursor, and an invalid cursor relationship all raised `CorruptJournal`.

Additional ephemeral probes covered paired local rollback, duplicate
decision/idempotency replay, both reconciliation uncertainty boundaries,
caller-chosen “production” construction, the malformed CLI descriptor,
and eight concurrent in-process issue attempts. The concurrency probe yielded
one `accepted`, seven `StaleCAS`, and one valid journal record. That result is
useful for the local lock path but does not establish the missing external
backend's process-level CAS, rollback, or fork guarantees.

The repository worktree was not edited by this review; its pre-existing
`uv.lock` modification remained untouched.
