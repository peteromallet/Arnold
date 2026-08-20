# T0.0 RA-CONTAIN final independent review — pass 4

Verdict: **FAIL**

Reviewed read-only at exact commit `e019cf4519f2e54aea7164390e4e5c11e5ad5517` (`HEAD` matched exactly). No repository, cloud, deployment, or commit state was changed. The report itself is the only written artifact.

## Release blockers

### 1. A valid-prefix rollback resurrects authority after termination

`ContainmentStore._replay()` accepts any valid journal prefix and has no durable external tail/revision anchor (`containment.py:70-97`). After issuing and terminating, I truncated the file to the original valid `issue` line. The remaining hash chain is internally valid, so `status()` reported `active` and `check(..., "observe")` returned `ALLOWED`.

Minimal reproduction:

```python
r = s.issue(exact_tuple=SCOPE, expected_cursor=0,
            expected_revision="0" * 64, issuer="owner", reason="x")
st = s.status()
s.terminate(decision_id=r["decision_id"], expected_cursor=st["cursor"],
            expected_revision=st["journal_digest"], issuer="owner", reason="done")
p.write_text(p.read_text().splitlines()[0] + "\n")
assert s.check(SCOPE, "observe").decision == "ALLOWED"  # unexpected
```

Observed result: `truncated_after_termination: ALLOWED`.

This violates current-state-only authority and the explicit requirement to refuse journal tampering. The implementation needs a tamper/rollback-detectable owner state anchor (or equivalent durable authority record); a hash chain alone cannot detect truncation to a valid prefix.

### 2. Divergent explicit-ID duplicates are accepted

At `containment.py:120-122`, an existing matching `decision_id` is treated as idempotent when only `exact_tuple` matches. Issuer, reason, TTL, termination policy, and the requested CAS are not compared.

```python
s.issue(exact_tuple=SCOPE, expected_cursor=0, expected_revision="0" * 64,
        issuer="owner", reason="one", decision_id="same")
s.issue(exact_tuple=SCOPE, expected_cursor=999, expected_revision="f" * 64,
        issuer="attacker", reason="changed", decision_id="same")
```

Observed result: `RETURNED_SUCCESS`; it returned the original receipt. Required result is typed `DuplicateConflict` for a divergent duplicate. This directly fails the requested CAS/idempotency contract.

### 3. Replayed receipt schema is not validated; malformed expiry can authorize

Replay checks only `state == "active"` and `content_hash` (`containment.py:85-91`). `check()` validates the content hash but not the receipt schema, denied-effect list, revision shape, issuer, termination policy, or required decision ID (`containment.py:140-149`). A caller able to alter and rehash a record can set `ttl_seconds` to the string `"nan"`; `float("nan")` makes the expiry comparison false, so observation remains allowed indefinitely:

Observed result: `nan_ttl_check: ALLOWED` even with `now` advanced by `10**9` seconds.

The same gap accepts a malformed terminate record with only `op` and `decision_id` (missing issuer/reason), replaying it as `terminated` rather than refusing: `malformed_terminate_replay: terminated`.

The receipt's `revision` can likewise be replaced with a non-64-hex value and rehashed; replay/check accepts it. Required change: one strict receipt/record schema validator used during replay and current-state checks, including finite positive TTL, exact lowercase 64-hex revisions, required fields/types, fixed policy values, and per-operation field sets.

### 4. Malformed current receipt data still escapes the real CLI

Removing `decision_id` from an otherwise content-hash-consistent active receipt causes `check()` to reach `receipt["decision_id"]` (`containment.py:149`) and raise `KeyError`. The CLI catch at `containment.py:174` does not include `KeyError`.

Observed command result: return code `1`, empty stdout, traceback on stderr ending in `KeyError: 'decision_id'`. This violates machine-readable typed refusal and confirms the earlier malformed-CLI finding is only partially closed. Malformed `created_at` values can similarly raise uncaught `AttributeError` at `containment.py:147`.

### 5. Durability ambiguity can be converted into clean success

The first `os.fsync()` was monkeypatched to raise after the journal bytes had been appended. The original call correctly raised `StorageError`, but a retry with the same request returned the receipt through the idempotency branch at `containment.py:120-122`:

```text
first = StorageError storage_error ... durability is uncertain
bytes_after_first = 1015
retry = { ... active receipt ... }
```

The requirement says ambiguity after bytes may have been appended must refuse rather than claim clean success. The store needs an ambiguity state/anchor that prevents a later retry from silently converting uncertain persistence into success.

### 6. Owner identity is recorded, not enforced

`issue()` accepts an arbitrary issuer and writes an active receipt (`containment.py:113-127`); there is no owner identity/authentication or non-empty issuer validation. A direct call with `issuer="attacker"` produced `arbitrary_issuer: active`. If “owner-issued” is a security boundary (not merely an audit string), this is independently non-conforming. The minimal interface needs an explicit trusted-owner issuance boundary or a documented owner-authenticated caller contract enforced by the API.

## What passed

- Exact tuple input binding is strict: exactly the seven named fields and non-empty strings (`containment.py:13, 32-37`). Unknown effects refuse; all six required effects are denied by the fixed set (`containment.py:14, 135-149`). My harness observed `resume`, `repair`, `execute`, `publish`, `notify`, and `deployment` all `DENIED`, and `ship` raised `UnknownEffect/unknown_effect`.
- No `verify_containment` definition or reference exists: `rg -n --hidden --glob '!.git/**' 'verify_containment' .` returned no matches. `run_authority/__init__.py:38-45` does not export it; importing it raised `AttributeError`.
- Hash-chain byte tampering, unknown operation, torn records, and bad transitions are rejected by the tested paths (`containment.py:75-96`; `tests/arnold_pipelines/run_authority/test_containment.py:41-45`). This does not cover valid-prefix rollback or semantically malformed-but-rehashed records above.
- CAS validation now rejects bool/negative/non-integer cursors and anything other than lowercase 64-hex revisions (`containment.py:151-155`). The targeted tests cover both issue and terminate (`test_containment.py:25-39`).
- Identical concurrent requests converge to one issue record and identical receipt; divergent requests produce one accepted writer and one typed loser. The repository race test passed 20/20 independent repetitions. The test itself is at `test_containment.py:87-116`.
- Fault injection for mkdir, lock open/flock/close, journal read/open/write/flush/close, journal fsync, parent-directory open/fsync/close all produced typed `StorageError` with no traceback. The corresponding handling is at `containment.py:55-69, 70-73, 98-110`.
- Initial TTL validation is finite-positive and rejects bool/non-finite/non-positive CLI values (`containment.py:113-116`; `test_containment.py:129-134`). Persisted malformed expiry is not fail-closed, as described above.
- Commands run:

  ```text
  pytest -q tests/arnold_pipelines/run_authority/test_containment.py
  ............................................. [100%] 45 passed in 1.44s

  pytest -q tests/arnold_pipelines/run_authority
  ............................................................... [100%] 63 passed in 1.57s

  20 repetitions of:
  pytest -q tests/arnold_pipelines/run_authority/test_containment.py::test_separate_process_identical_and_divergent_issue_races
  20/20 race repetitions passed

  git diff --check e019cf4519f2e54aea7164390e4e5c11e5ad5517^ e019cf4519f2e54aea7164390e4e5c11e5ad5517
  passed
  ```

- Scope inspection found exactly three changed files in the pinned commit: `containment.py`, `run_authority/__init__.py`, and `test_containment.py`. No shell/tmux/marker/queue/cloud/deployment operation was introduced by this commit. `containment.py:159-175` is the real JSON CLI and uses no fallback authority path.

## Prior findings closure

Revision CAS, deployment denial, unknown journal ops, bool cursor rejection, swallowed race-loser classification, storage error wrapping, finite input TTL, and the requested process-race coverage are closed by source and tests. Receipt byte-integrity checking and removal of the receipt-only `verify_containment` helper are also closed for their narrow cases. They are not sufficient for release because semantic receipt validation, rollback detection, divergent duplicate handling, malformed-current-state CLI behavior, and post-append ambiguity remain open.

Required disposition: do not accept or release this commit for T0.0. Fix the blockers above, add regressions for each reproducer, and rerun the adversarial review.

Residual limitation even after code repair: this local interface is not itself a live cloud containment decision. T0.0 remains incomplete until installed through the accepted Release Authority and used by the owner.
