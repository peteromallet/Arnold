# Batch 3 attempt 5 — Python validation evidence

Validation snapshot: 2026-08-31T19:24:21Z  
Candidate source snapshot (`HEAD`): `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`  
Tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`

## Final inventory binding

- Artifact: `docs/nbf-signal-inventory.json`
- SHA-256: `e92b6c90c6adf7c6d5f05a8d10c888f4900b1a2395cf35ce55689323987568da`
- Entries: `120`
- `source_inputs_sha256`:
  `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`
- `discovery_rules_version`: `nbf05-discovery-rules-v1`

## Primary acceptance lanes

The final implementation evidence is clean across **31/31 primary checks**.
The recorded lane results are:

- Production candidate integration: **471 passed**.
- Controlled custody/race suite: **42 passed**.
- Final inventory/fan/no-bare suite: **31 passed**.
- Disposition-wrapper suite: **18 passed**.
- Watchdog-wrapper suite: **266 passed**.
- Project Python 3.11 safepath check: **1 passed**.

These scopes overlap intentionally and are not summed into an artificial total.
The earlier stripped Homebrew Python 3.14 optional-`fire` diagnostic failure
was environmental and outside the candidate manifest; project Python 3.11
passed the same safepath test.

Two focused inventory runs encountered ENOSPC while printing an already-known
diagnostic (`fresh inventory` or `stale inventory`). Those were nonsemantic
environment failures, not implementation failures; the underlying freshness
and rules-drift assertions passed independently. The primary evidence remains
the clean 31/31 result above.

## Independent Luna review accounting

Three final Luna inventory reviews were completed separately from acceptance
totals. They verified the final inventory identity and rules/source digest,
action-aware helper classifications, absence of declaration-only rows, exact
fan-kill non-worker lifecycle routing, probe/wait/tmux classifications,
referenced test-symbol resolution, and no scope leakage. Reviewer reruns are
not counted as additional acceptance tests.

## Evidence boundary

No source, inventory, tasklist, Oracle, NBF08, or deployment files were edited
for this evidence artifact. Counts above remain explicitly overlap-aware, and
the candidate remains bound to the HEAD and tasklist identities stated above.
