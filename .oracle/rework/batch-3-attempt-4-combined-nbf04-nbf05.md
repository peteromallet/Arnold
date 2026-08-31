# Batch 3 combined NBF-04/NBF-05 candidate — attempt 4 final freeze

## Freeze and authority boundary

This packet freezes the current shared dirty-tree candidate on branch
`reconcile/nbf-attempt4-2297` against base/head
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`.  It covers NBF-04 typed
disposition/confirmation, WBC custody, native supervision, and terminal
reconciliation, plus NBF-05 marker/bootstrap authority, non-worker locking,
shell bridges, tmux identity, and signal inventory.  It is a candidate freeze
for review only: no commit, push, merge, deployment, `main` mutation, or epic
launch was performed.

NBF-06 provider policy and NBF-08 definitive chain-control implementation are
out of scope.  The NBF08 suffix-rebind record is planning authority only and is
not in the candidate manifest or framed diff.

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

Accepted NBF-04 attempt-11 evidence remains linked, not re-authored:
packet `83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071`,
review brief `ad421a2b79ed87a8da418495d30b6fc9ef814cf7d3df023ed2560b279cd33c75`,
25-path manifest `c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`,
and framed aggregate
`b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`.

## Exact candidate manifest and framed diff

The explicit manifest is
`.oracle/rework/batch-3-attempt-2.manifest.tsv`, SHA-256
`632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`,
3100 bytes.  It has 49 sorted, unique existing paths: 23 NBF-04 and 26
NBF-05.  Every changed in-scope source/test path is present; Oracle planning
and evidence artifacts, historical Batch-2 material,
`evidence/m11-recovery-topology-surfaces.json`, `babysitter-runs/`, and demo
receipts are excluded.  No NBF-06 or NBF-08 implementation path is included.

The deterministic Oracle-only framing tool is
`.oracle/rework/nbf_batch3_attempt4_diff_v1.py`, SHA-256
`daecdd4508a04f28a491786034aa9f649105d090bb7bd775a8bd6daf28aa49bc`.
It uses fixed Git configuration, tracked `--binary --full-index` diffs,
`/dev/null` framing for untracked paths, uint64 big-endian path/status/diff
length fields, and fail-closed absolute-header checks.  It does not walk
outside the manifest.

The primary output is
`.oracle/evidence/batch-3-attempt-4-framed-diff.json`, SHA-256
`058377715f7360217bafe629daa6ed95b3dc78985821cdadcc3129c7672f4263`,
13088 bytes.  The second output
`.oracle/evidence/batch-3-attempt-4-framed-diff-rerun.json` has the same SHA
and byte-for-byte comparison succeeds.  Both record 49 paths (33 tracked,
16 untracked), 758196 raw diff bytes, and aggregate
`a12004073f638fe16813ce532efd2a3c779a34372d74943c945a6cc982e4db9a`.

For an independent source-stability check, each manifest path was framed as
`uint64_be(path length), path, uint64_be(classification length),
classification, uint64_be(file length), SHA-256(file bytes)` in sorted order.
The resulting snapshot digest was
`4b6df7f96661d551a88b9ed253d68a6260ca193c67e2938b37700d768b5fb24c` before
and after both framing runs.  The source candidate therefore did not mutate
during sealing.

## Implementation and validation evidence

The attempt-4 Python validation evidence is
`.oracle/evidence/batch-3-attempt-4-python-validation.md`, SHA-256
`16f567743b7556419c580d764286133ed1ef84754a6bb6602e6db1f77df42b72`.
It binds HEAD, tasklist, and the final inventory and records the prior
candidate integration (471 passes), controlled-launch/race (42), final
inventory/fan (30), disposition-wrapper (18), and watchdog-wrapper (266)
lanes, with overlapping counts explicitly not summed.  It also records the
project Python 3.11 safepath check as 1/1 PASS.

The stripped Homebrew Python 3.14 optional-fire safepath invocation failed
because the optional `fire` dependency is absent.  That interpreter-only
baseline is outside the 49-path candidate and receives neither candidate pass
credit nor candidate failure credit.

The static/runtime evidence is
`.oracle/evidence/batch-3-attempt-4-static-runtime-validation.md`, SHA-256
`4fcfca894edcaf1ef8734b8f5ca71715c38d8f54b681eb83b23f29318a7d8715`.
It records deterministic generator and `--check` runs, 30 static/inventory
checks, 38 compile checks, six wrapper `bash -n` checks, four direct symbol
checks, and `git diff --check` PASS.  Inventory identity is
`docs/nbf-signal-inventory.json` SHA-256
`44331a169f8f8b4d5ae6141c5fe905cd79691e404bdaaa0fbe72c16c45525bf1`, 122
entries, source-input digest
`60d5d933e722d8f49905b534866e1a2bdb6d0c7766103f3176adacd7cd33a958`,
generator `nbf05-signal-inventory-v1`, discovery rules
`nbf05-discovery-rules-v1`, and source-digest version
`nbf05-source-inputs-v2`.

The post-Sol Luna review chain was recorded as three PASS outcomes in the
Oracle history: settled-plan `PASS_LUNA_V8`, Batch-2's five-independent-Luna
PASS receipt, and the final pre-execution Luna PASS.  Their source artifacts
are respectively `.oracle/receipts/plan-settled-W8-luna.md` (SHA-256
`2691b341c030e51056987f1aeb02fa130af75f22a901d5847cdf1c94b2d0f2f6`),
`.oracle/receipts/batch-2-attempt-18-five-luna-pass.md` (SHA-256
`6c4603778bce4fb7384332361df237367a77f1c1241e9d5747226a8fd247c1ed`), and
`.oracle/findings/preexecution-review-luna.txt` (SHA-256
`3f15a11ca44e9c60dc413298278066974c256a96f5c9b72336ae9e160566c8`).
These are review-history evidence, not substitutes for the fresh review of
this packet.

## Sol finding/fix history and residual classifications

The Sol-directed NBF-04 findings drove the native timeout confirmation and
custody fixes, then the cross-reservation/unresolved and retained-handle
guards.  The final post-Sol checks confirmed: a wrong supplied process handle
for admitted child A produces typed unresolved with zero poll/signal and zero
dispositions in both `signal_ladder` and `immediate_timeout`; the correct
admitted child remains functional; operator/fan controls use the canonical
workspace ledger and locked PID/start preflight; and worker TERM/KILL stages
retain distinct durable claims with replay-safe ordering.  The historical
attempts 1–3 are superseded by this seal.

No unresolved candidate blocker is claimed.  The only known non-candidate
anomaly is the stripped Python 3.14 optional-fire baseline described above.
The contaminated historical `174 passed / 9 failed / 187 temporary-directory
errors` run is quarantined and not used as evidence.  Overlapping validation
counts are not additive.

## Review handoff

The candidate is ready for the independent Luna review bound to this packet,
manifest, script, two identical outputs, evidence identities, and aggregate.
The reviewer must judge NBF-04/NBF-05 only, including record-before-signal,
distinct TERM/KILL confirmation and replay, PID/start fencing, WBC/native
custody, marker/bootstrap and one-lock revalidation, exact tmux socket/session/
pane identity, shell fail-closed behavior, and inventory completeness.
Any later source or test mutation invalidates this seal and requires a new
framing run.  No launch, deploy, commit, push, merge, `main` change, NBF-06
execution, or NBF-08 implementation is authorized by this packet.
