# Batch 3 attempt 4 — Python validation evidence

Validation snapshot: 2026-08-31T18:42:39Z  
Candidate source snapshot (`HEAD`): `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`  
Tasklist SHA-256: `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73`

## Final inventory binding

- Artifact: `docs/nbf-signal-inventory.json`
- SHA-256: `44331a169f8f8b4d5ae6141c5fe905cd79691e404bdaaa0fbe72c16c45525bf1`
- Entries: `122`
- `source_inputs_sha256`:
  `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`
- `discovery_rules_version`: `nbf05-discovery-rules-v1`

## Validation lanes

The recorded lane results are:

- Prior candidate integration: **471 passed**. One unrelated stripped-
  environment optional-`fire` failure is excluded from candidate results.
- Focused controlled-launch/race suite: **42 passed**.
- Final inventory/fan suite: **30 passed**.
- Disposition-wrapper suite: **18 passed**.
- Watchdog-wrapper suite: **266 passed**.

These scopes overlap intentionally and are not summed into an artificial total.

The previously observed Homebrew Python 3.14 stripped-environment failure was
resolved as environmental: the explicit project Python 3.11 command

```text
PYTHONDONTWRITEBYTECODE=1 python3.11 -m pytest -q -p no:cacheprovider \
  tests/cloud/test_fan_safepath_import.py
```

passed **1/1** in 0.22s. The failure under the stripped Python 3.14 process
reported `error: this script requires \`fire\``; it was outside the 49-path
candidate manifest and does not represent a candidate regression.

## Evidence boundary

Inventory freshness, deterministic source framing, rules-content mutation
staleness, row test-symbol resolution, fan-kill non-worker classification,
record-before-signal ordering, PID/start identity fencing, replay, and
wrong-handle zero-signal behavior were independently checked in the preceding
review lane. No source, inventory, tasklist, Oracle, NBF08, or deployment files
were edited for this evidence artifact. Counts above remain explicitly
overlap-aware.
