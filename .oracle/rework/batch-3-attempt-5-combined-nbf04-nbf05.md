# Batch 3 combined NBF-04/NBF-05 candidate — attempt 5 final freeze

## Freeze and scope

This packet supersedes attempt 4 and freezes the current shared candidate on
`reconcile/nbf-attempt4-2297`, against base/head
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.  It covers NBF-04 typed
disposition, confirmation, WBC/native custody and terminal reconciliation,
and NBF-05 marker/bootstrap authority, non-worker locking, shell bridges,
tmux identity, and signal inventory.  This is a review handoff only: no
commit, push, merge, deployment, `main` mutation, or epic launch occurred.

NBF-06 provider policy and NBF-08 definitive chain-control implementation are
excluded.  The NBF08 suffix-rebind record is planning authority only and is
excluded from the candidate manifest and framed diff.

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

Accepted NBF-04 attempt-11 remains linked evidence: packet
`83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071`, review
brief `ad421a2b79ed87a8da418495d30b6fc9ef814cf7d3df023ed2560b279cd33c75`,
25-path manifest `c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`,
and aggregate `b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.

## Manifest and deterministic seal

The exact candidate manifest is
`.oracle/rework/batch-3-attempt-2.manifest.tsv`, SHA-256
`632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`,
3100 bytes.  It contains 49 sorted, unique, existing paths: 23 NBF-04 and
26 NBF-05.  Re-derivation against the current worktree found no new or
missing in-scope path.  Historical Oracle evidence, NBF08/tasklist/status
metadata, M11 material, `babysitter-runs/`, demo receipts, and NBF06 are
excluded.

The attempt-5 framing entry point is
`.oracle/rework/nbf_batch3_attempt5_diff_v1.py`, SHA-256
`cfcf70916329ad9301ac70278389f49df9620363606281b715962b5536178cc0`.
It invokes the sealed NBF-BATCH3-DIFF-V1 implementation with fixed Git
configuration, binary/full-index tracked diffs, `/dev/null` untracked
framing, uint64 big-endian length fields, and fail-closed absolute-header
checks.

Primary output `.oracle/evidence/batch-3-attempt-5-framed-diff.json` and its
rerun are both SHA-256
`358bc185d04937b85ee1d886d2fb9e8bbd43b592b663ccf9a3f444c166ae14a3`,
13088 bytes, and compare byte-for-byte equal.  They record 49 paths (33
tracked, 16 untracked), 759851 raw diff bytes, and aggregate
`7f134a29fee76c1f68436798482dca46a301a380456c0793ce3b2b0ecf80c958`.

The independent sorted manifest-path content snapshot uses uint64 big-endian
path/classification/file lengths plus each file SHA-256 and is
`aaf02ae4647481dc2539cfe28bd5f5d37c54623e82791f92563b2dcc3b2740b0` before
and after framing.  Source content was stable throughout sealing.

## Validation and inventory

Python evidence `.oracle/evidence/batch-3-attempt-5-python-validation.md`
has SHA-256
`6ce40640ad901186936285da8861dcefd22d7de4f97985410de3ce726bc3930a`.
It records the final Python authority/disposition/replay/liveness and wrapper
validation after the production safety suites, including the action-aware
inventory correction.  Counts from overlapping suites are not additive.

Static/runtime evidence `.oracle/evidence/batch-3-attempt-5-static-runtime-validation.md`
has SHA-256
`e56ab2c88a21189d05eab78e672462c7dde54b69586ebb744c483a6c1a4808d5`.
It records the generator and `--check` determinism, static/runtime checks,
compile, shell syntax, and diff checks.

The final inventory is `docs/nbf-signal-inventory.json`, SHA-256
`e92b6c90c6adf7c6d5f05a8d10c888f4900b1a2395cf35ce55689323987568da`, with
120 entries.  It binds source-input digest `60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`,
generator/discovery version `nbf05-signal-inventory-v1` /
`nbf05-discovery-rules-v1`, and source-digest version
`nbf05-source-inputs-v2`.

The project Python 3.11 safepath PASS remains the accepted runtime baseline.
The stripped Homebrew Python 3.14 optional-`fire` failure remains an
interpreter-only baseline outside the candidate manifest; it receives neither
candidate pass nor failure credit.

## Review history and handoff

The Sol review history is explicitly rework history: Sol findings identified
the native confirmation/custody, cross-reservation, retained-handle, shell
authority, and action-aware inventory issues; those findings are superseded by
the current candidate and are not silently treated as passes.  Subsequent
Luna review rounds are preserved in the attempt-2, attempt-3, and attempt-4
review briefs, plus the accepted NBF-04 attempt-11 review brief.  The current
fresh Luna review must bind this attempt-5 packet rather than relying on any
prior PASS narrative.

The contaminated historical `174 passed / 9 failed / 187 temporary-directory
errors` run is quarantined.  No residual candidate blocker is claimed beyond
the excluded optional-fire baseline.  Any source/test mutation after this
packet invalidates its seal and requires a new framing run.  Return `PASS` or
`REWORK` with exact file:line evidence.  Do not edit, commit, push, merge,
deploy, touch `main`, execute NBF-06, implement NBF08, or launch the epic.
