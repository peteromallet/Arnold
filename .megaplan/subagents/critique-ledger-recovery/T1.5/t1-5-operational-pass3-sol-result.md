# T1.5 operational pass 3 — authenticated effect receipt implementation result

## Disposition

The coordinated SQLite result/receipt replay defect is repaired in the exact
two-file scope. This is an implementation result only. It does not claim T1.5
acceptance, production-owner acceptance, deployed-runtime acceptance, or incident
advancement; an independent reviewer follows.

No cloud/provider call, production owner/socket interaction, deploy, restart,
push, inventory change, historical-test change, wrapper change, packaging change,
or broad/cloud/wheel suite was performed.

## Frozen input and committed output

- Worktree:
  `/private/tmp/arnold-critique-recovery-t1-5-operational-pass3-20260802`
- Frozen base commit:
  `ea7fb2aacb6622a7e18ea4a579019ae271aa52ec`
- Frozen base tree:
  `5077ceff4e9ccd8958051acd999fb86172233f8f`
- Implementation commit:
  `9642193a063d91a6be364f2d11a04b221eae30cf`
- Implementation tree:
  `27a3d61dff39a4c1a26a8a736dc85ce727c57b7c`
- Commit subject:
  `fix(recovery): authenticate effect replay receipts`
- Worktree after commit: clean on branch
  `fix/critique-recovery-t1-5-operational-pass3-20260802`.

## Exact bounded changes

Only these files changed:

- `arnold/recovery/simple_fixer.py`
- `tests/cloud/test_simple_fixer.py`

The test-only hermetic owner now requires an explicit HMAC-SHA256 key of at
least 256 bits at construction and every reopen. The key is held only in the
test owner instance, is never persisted in SQLite, and is not added to the
production fixed-owner client or caller protocol.

`_simulate_effect()` now creates an authenticated effect-owner/WBC proof. The
proof binds the exact occurrence and attempt, canonical intent digest, claim
ID/epoch/fence, authority digest/revision/fence, owner record digest/revision/
fence, WBC GLEK, effect request digest, provider outcome, and provider/effect ID.
The terminal result receipt is separately authenticated and binds those facts,
the effect-proof digest when an effect exists, and the exact result digest.

Replay verifies both keyed receipts against current owner/WBC bindings and the
canonical intent/result. `SUCCEEDED` and `FAILED` cannot replay without a valid
effect proof. Missing, corrupt, transplanted, wrong-key, or unverifiable proof
raises typed `RESULT_RECONCILIATION_UNKNOWN` before any new claim, attempt, or
effect. A no-proof ambiguity may only become authenticated
`INDETERMINATE_NON_REDISPATCHABLE`.

The `simulated_effects` count exposed by the test owner now counts authenticated
effect proofs, not untrusted projection rows. This lets the exact fabrication
probe insert a counterfeit effect row while the authoritative effect count stays
zero.

## Required hostile and replay evidence

The new focused cases prove:

- valid success replays byte-for-byte in a newly spawned process with the same
  independently injected key;
- a fresh owner with the wrong key returns typed UNKNOWN and does not redispatch;
- a valid effect proof transplanted across occurrences is rejected;
- effect-proof deletion and corruption return typed UNKNOWN without a second
  attempt/effect;
- the exact `after_effect_ambiguity_commit` attack starts with
  `EFFECT_POSSIBLY_APPLIED`, observes zero `_simulate_effect()` invocations,
  fabricates a mutually consistent effect row, success result/receipt, and
  released claim in one SQLite transaction using deterministic public data, and
  is rejected after a fresh legitimate-key reopen. The authenticated effect
  count and `_simulate_effect()` invocation count remain zero; the raw forged row
  and sole attempt remain one, proving no redispatch.

Exact required-case command:

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/cloud/test_simple_fixer.py \
  -k 'authenticated_success_replays_exactly_in_fresh_process or \
  wrong_effect_receipt_key or cross_occurrence_effect_receipt_transplant or \
  coordinated_sqlite_success_fabrication or \
  effect_receipt_deletion_or_corruption'
6 passed, 32 deselected in 1.41s
```

## Focused validation

```text
PYTHONDONTWRITEBYTECODE=1 python -m pytest -p no:cacheprovider -q \
  tests/cloud/test_simple_fixer.py
38 passed in 3.29s

ruff check arnold/recovery/simple_fixer.py tests/cloud/test_simple_fixer.py
All checks passed!

PYTHONDONTWRITEBYTECODE=1 python -m py_compile \
  arnold/recovery/simple_fixer.py tests/cloud/test_simple_fixer.py
passed

git diff --check -- \
  arnold/recovery/simple_fixer.py tests/cloud/test_simple_fixer.py
passed
```

The changed-file scope gate confirmed the diff contained exactly the two allowed
files. The committed worktree is clean. No inventory, historical, broad cloud,
wheel, packaging, or runtime test was run or changed.

## Limitation and next authority

This validates the local test-only HMAC model and leaves the production caller
surface on the authenticated fixed owner service. No production receipt or
deployed owner was available or contacted. Independent review of the exact
commit/tree above is the next authority; this report intentionally makes no
acceptance claim.
