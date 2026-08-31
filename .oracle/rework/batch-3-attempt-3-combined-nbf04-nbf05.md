# Batch 3 combined NBF-04/NBF-05 candidate — attempt 3

## Freeze and scope

This packet freezes the current shared dirty-tree candidate on branch
`reconcile/nbf-attempt4-2297`, against base/head
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`. It combines NBF-04 typed
disposition, confirmation, WBC custody, native supervision, and terminal
reconciliation with NBF-05 marker/bootstrap authority, non-worker locking,
shell bridges, tmux identity, and signal inventory. NBF06/provider work,
NBF08 implementation, deployment, commit/push/merge, `main`, and epic launch
are excluded.

The NBF08 suffix-rebind record is planning authority only and is excluded from
the candidate manifest and framed diff.

## Frozen identities

| Input | SHA-256 / value |
|---|---|
| Base/head checkpoint | `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` |
| `.oracle/tasklist.md` | `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| NBF08 suffix-rebind record | `b2c09eee42da4e1fb251315773ca527aa31cb0e8159bc6b08901ffec59048723` |

Accepted NBF-04 attempt-11 evidence remains linked:
packet `83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071`,
review brief `ad421a2b79ed87a8da418495d30b6fc9ef814cf7d3df023ed2560b279cd33c75`,
25-path manifest `c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`,
and framed aggregate `b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.

## Manifest and framing

The candidate manifest remains
`.oracle/rework/batch-3-attempt-2.manifest.tsv`, with 49 unique sorted
paths: 23 NBF04 and 26 NBF05. It is unchanged and its SHA-256 is
`632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`.
All 49 paths exist; current candidate comparison found no new or missing
source/test path. Oracle artifacts, historical evidence, `babysitter-runs/`,
demo receipts, and `evidence/m11-recovery-topology-surfaces.json` remain
excluded.

The Oracle-only deterministic framing script is
`.oracle/rework/nbf_batch3_attempt3_diff_v1.py`, SHA-256
`a0b9cb88e60310486e09d5096c115550d4e4e7b41a8626dcd4ac270f85913bbb`.
It uses fixed Git configuration, tracked `--binary --full-index` diffs,
`/dev/null` framing for untracked files, uint64 big-endian path/status/diff
length fields, and fail-closed absolute-header checks.

The primary framed output is
`.oracle/evidence/batch-3-attempt-3-framed-diff.json`, SHA-256
`5aa29092a49e6d4920798db46c217c2d64a3a3bff1ca2a8d97f20e49e09c713a`.
The independent rerun has the identical SHA-256. It records 49 paths (33
tracked, 16 untracked), 751422 raw diff bytes, and aggregate
`f28e039c23b74b37b752ef4527ef1d8878953f21537ca9b23d1c2f1f21686991`.
The manifest is 3100 bytes. A content snapshot over all manifest paths was
stable during both framing runs at
`a0b6e1db59f0dffc539c1c0569e7a41121559134a2f47ed19113aa67f4d6c1ef`.

## Validation

Python evidence `.oracle/evidence/batch-3-attempt-3-python-validation.md`
has SHA-256
`403d1bd3cafb9008a58b348a6c5f5fc16b7621d03b967f8770d3a3fde3d7b35d`.
It records 471 candidate passes, with one explicitly excluded stripped-env
baseline failure because optional `fire` is unavailable, plus 42 focused
post-fix controlled-launch/ladders passes. Counts overlap and are not summed.

Static/runtime evidence `.oracle/evidence/batch-3-attempt-3-static-runtime-validation.md`
has SHA-256
`12a5f51a7554e6668de82545a08f466a0ae6a4aa4f8f098956dc8b6d7a99ebc6`.
It records inventory/generator checks, 18 static/inventory checks, 18
disposition-wrapper passes, 266 watchdog-wrapper passes, six shell syntax
checks, 37 Python compiles, and `git diff --check` PASS.

Additional independent review checks after the handle guard: 8 targeted
controlled-launch tests, 27 operator/fan tests, and 48 NBF04 authority
subset tests passed. A real harmless wrong-handle probe showed both
`signal_ladder` and `immediate_timeout` return typed unresolved with zero
dispositions and zero physical callbacks. The admitted-child path remains
functional.

The final inventory is `docs/nbf-signal-inventory.json`, SHA-256
`d8052e72a4c6f43d8f164d2de5524a9eae7fd8ee9dfe2ab06fce2042e9fe2e1d`, with
122 entries and source-input SHA
`5318df4442550596e09b7200b76f2171106a926bee93834790dbe55466849033`.

## Review conclusions and exclusions

The operator and fan controls now bind the canonical workspace ledger, reject
missing/wrong authority, and perform final locked pidfile/cmdline/group/start
preflight. Worker TERM/KILL callbacks use distinct durable claims and ordered
replay-safe ladder stages. The controlled-launch wrong-handle guard fences
both ladder and explicit immediate-timeout paths before polling or signaling.

The sole excluded Python failure is the optional-`fire` stripped-environment
baseline in `test_fan_safepath_import.py`; it is outside the 49-path candidate
and does not indicate a signal/custody regression. Prior contaminated 174/9/187
temporary-directory runs, historical Batch2 artifacts, NBF08 planning files,
and old inventory identities are not acceptance evidence. No source content
mutated during framing; no launch, deployment, commit, push, merge, main
change, NBF06 work, or NBF08 implementation was performed.
