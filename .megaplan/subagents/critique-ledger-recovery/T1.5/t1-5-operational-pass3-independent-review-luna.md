# HARD FAIL — T1.5 operational pass 3 independent Luna review

## Verdict

**HARD FAIL.**

The HMAC receipt design correctly rejects coordinated substitution while the
attempt/claim/effect projections remain present. The required forged-success,
wrong-key, cross-occurrence transplant, receipt deletion/corruption, and fresh
process probes all pass. The key is not stored in SQLite or added to the fixed
production owner client, and the resident provenance path is unchanged.

However, all `attempts`, `claims`, and `simulated_effects` rows are explicitly
attacker-mutable projections. Coordinated erasure of those rows removes the only
durable indication that an occurrence already consumed its one attempt. The
owner then treats the occurrence as never attempted, creates a new claim and
attempt, and invokes the effect again. This reproduces both after
`after_effect_ambiguity_commit` and after a completed success, without the HMAC
key. The candidate therefore does not meet missing-proof => typed UNKNOWN/no
redispatch or exactly-one-effect semantics.

This is an independent local verdict for the exact bounded candidate only. It
is not a formal T1.5 completion claim, deployed-owner verdict, or production
incident disposition.

## Exact candidate and review admission

- Worktree:
  `/private/tmp/arnold-critique-recovery-t1-5-operational-pass3-20260802`
- Commit: `9642193a063d91a6be364f2d11a04b221eae30cf`
- Tree: `27a3d61dff39a4c1a26a8a736dc85ce727c57b7c`
- Parent: `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`
- Commit subject: `fix(recovery): authenticate effect replay receipts`
- Implementer result SHA-256 independently verified as
  `98f72d62a9855ec28c4183f6a4699408d6c789ec70de3f51fc4c5740af7f5b47`.
- Worktree was clean before and after review.
- `git diff-tree` confirmed exactly two changed files:
  `arnold/recovery/simple_fixer.py` and
  `tests/cloud/test_simple_fixer.py`.
- Diff size: 843 insertions and 39 deletions: 501/37 in the hermetic owner
  implementation and 342/2 in its focused tests.

No candidate source, Git ref, cloud/provider state, production socket/owner,
deployed runtime, checklist, or incident state was mutated. All hostile probes
used disposable temporary directories.

## Decisive blocker

### B1 — coordinated projection erasure permits redispatch and a second effect

`TestOnlyHermeticRecoveryOwner._stored_result()` reads only the mutable
`attempts` and `claims` projections. At
`arnold/recovery/simple_fixer.py:1250-1260`, an absent attempt returns `None`
when the claim is also absent or is `HELD`. That return value is interpreted as
“no stored result.”

`run()` then creates a new claim at `:1627-1645`, creates a new attempt at
`:1674-1682`, commits a fresh ambiguity marker, and invokes `_simulate_effect()`
at `:1713-1726`. No authenticated external occurrence-level tombstone,
one-attempt grant consumption record, provider-idempotency record, or owner/WBC
query distinguishes “never attempted” from “attacker erased the projections.”
HMAC authenticates present bytes but cannot authenticate their absence.

#### Fresh completed-success erasure probe

The probe performed one valid successful effect, then in one SQLite transaction
deleted the occurrence's `simulated_effects`, `attempts`, and `claims` rows. It
reopened the owner with the unchanged legitimate key and ordinary owner record,
tracked `_simulate_effect()`, and called the normal reconciler path.

Observed:

```json
{"attempt_changed":true,"effect_invocations_after_total_projection_erasure":1,"first_status":"SUCCEEDED","second_status":"SUCCEEDED"}
```

The first effect was already successful. After erasure, the candidate minted a
different attempt and invoked the effect a second time, returning a second
authenticated success. This uses no HMAC key and no source/global mutation.

#### Fresh ambiguity-marker erasure probe

The probe injected `after_effect_ambiguity_commit`; `_simulate_effect()` had not
run and the durable attempt was `EFFECT_POSSIBLY_APPLIED`. It then deleted only
the `attempts` and `claims` projections, reopened with the unchanged legitimate
key/owner record, and called the reconciler.

Observed:

```json
{"attempt_changed":true,"effect_invocations_after_ambiguous_tombstone_erasure":1,"raw_effects_before_erasure":0,"replay_status":"SUCCEEDED"}
```

Instead of typed UNKNOWN/INDETERMINATE with no redispatch, the missing ambiguity
proof was treated as a new occurrence and the effect was dispatched.

This is within the frozen pass-3 threat statement: the attempt/result/claim/
effect tables are mutable projections, missing proof must be UNKNOWN or
INDETERMINATE, and exactly one attempt/effect is allowed. The checked-in deletion
tests remove a single effect proof while retaining the terminal attempt and
claim tombstones, so they do not cover coordinated erasure of all projections
that encode prior dispatch.

### Required correction

The one-attempt/ambiguity fact needs an independently authoritative monotonic
anchor outside these attacker-writable SQLite projections—for example the fixed
effect-owner/WBC service's occurrence-scoped consumed-grant/idempotency state.
Reconciliation must query or verify that state before treating missing local
claim/attempt rows as “never dispatched.” A keyed receipt stored only in the
same deletable database cannot prove absence or prevent replay after erasure.

## Challenge matrix

| Challenge | Result | Independent evidence |
|---|---|---|
| Exact coordinated success fabrication after ambiguity marker | PASS for the checked shape | Zero-tag mutually consistent effect/result/claim fabrication is rejected; no effect invocation |
| HMAC key absent from SQLite and production caller surface | PASS within bounded model | Key appears only in the test-only owner instance/constructor; SQLite scan passes; fixed `OwnerServiceClient` AST/signature is unchanged |
| Fresh-process replay with right key | PASS | Spawned-process exact byte replay passes |
| Wrong key | PASS | Typed `RESULT_RECONCILIATION_UNKNOWN`; no redispatch |
| Cross-occurrence transplant | PASS | Receipt binding mismatch; no new attempt/effect |
| Single-row effect-proof deletion/corruption | PASS | Typed UNKNOWN with retained terminal tombstones |
| Coordinated deletion of all dispatch projections | **FAIL** | New attempt and effect are created; completed success can execute twice |
| Exactly one attempt/no second effect | **FAIL** | Both independent erasure probes mint a different attempt and invoke the effect |
| Resident provenance path | PASS | Method AST is byte-semantically unchanged; focused dedupe/quiet-path test passes |
| Exact two-file scope | PASS | `git diff-tree` lists exactly the two allowed files |
| 843-line delta proportionality | PASS with scope caveat | Large but explainable by exact canonical binding/verification plus hostile tests; no unrelated production client/provenance changes |
| Circular/self-authentication | No direct HMAC forge found | Test-only owner both simulates and signs as allowed by the brief; verification uses an injected key outside SQLite. The remaining defect is unauthenticated absence, not tag forgery |

The static test key is intentionally visible fixture material and models an
external test owner key; it is not production evidence. This review validates
only that the fixed production client did not gain a caller key parameter—not
that any deployed owner implements equivalent receipts.

## Commands and results

Identity, scope, and report admission:

```text
git rev-parse HEAD HEAD^{tree} HEAD^
git status --porcelain=v1
git diff-tree --no-commit-id --name-status -r 9642193a...
shasum -a 256 t1-5-operational-pass3-sol-result.md
```

Observed exact commit/tree/parent above, clean status, exactly two changed
files, and implementer-report digest
`98f72d62a9855ec28c4183f6a4699408d6c789ec70de3f51fc4c5740af7f5b47`.

Required hostile/replay subset:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -p no:cacheprovider -q tests/cloud/test_simple_fixer.py \
  -k 'authenticated_success_replays_exactly_in_fresh_process or \
  wrong_effect_receipt_key or cross_occurrence_effect_receipt_transplant or \
  coordinated_sqlite_success_fabrication or \
  effect_receipt_deletion_or_corruption'

6 passed, 32 deselected in 1.07s
```

Full bounded module:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -p no:cacheprovider -q tests/cloud/test_simple_fixer.py

38 passed in 2.99s
```

Resident provenance and fresh-process replay selection:

```text
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
python -m pytest -p no:cacheprovider -q tests/cloud/test_simple_fixer.py \
  -k 'delegation_provenance_v2 or \
  authenticated_success_replays_exactly_in_fresh_process'

2 passed, 36 deselected in 0.99s
```

Static checks:

```text
python -m ruff check arnold/recovery/simple_fixer.py \
  tests/cloud/test_simple_fixer.py
All checks passed!

in-memory compile: passed
git diff --check ea7fb2a... 9642193... -- <two allowed files>
passed
```

AST comparison independently showed `OwnerServiceClient` and
`TestOnlyHermeticRecoveryOwner.record_delegation_provenance_error` unchanged
from the parent commit. Final worktree status remained clean.

## Acceptance scope and limitations

The keyed receipt is a meaningful repair of coordinated result/receipt
substitution and should be preserved. It is insufficient as the sole replay
authority because every record of prior dispatch remains deletable in the same
SQLite store.

No broad/cloud/wheel suite was run; the bounded prompt prohibited that work.
No production owner/socket was contacted, so this review does not validate a
deployed external key, receipt issuer, occurrence-scoped idempotency state,
peer credentials, or production replay. Generic pass-2 B7 inventory/historical
coverage debt remains outside this exact operational pass and is not part of
this verdict.
