# Batch 3 combined NBF-04/NBF-05 candidate — attempt 2

## Freeze and scope

This packet freezes the current shared dirty-tree candidate on branch
`reconcile/nbf-attempt4-2297`, based on checkpoint
`7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e`. It combines the NBF-04 Python
custody/disposition work with the NBF-05 authority, producer, shell, tmux,
and inventory work. The NBF08 suffix-rebind planning change is separately
authorized metadata and is not candidate implementation content.

NBF-04 owns canonical disposition/confirmation ordering, PID/start fencing,
WBC cleanup custody, terminal reconciliation, and Python worker/native signal
paths. NBF-05 owns marker/bootstrap authority, non-worker revalidation,
record-before-signal locking, liveness/producer bindings, exact tmux
socket/server/owned-pane identity, shell bridges, and repository inventory.
NBF-06/provider resilience, NBF08 implementation, deployment, commit,
push/merge, `main`, and epic launch are excluded.

## Frozen identities

| Input | SHA-256 / value |
|---|---|
| Base/head checkpoint | `7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e` |
| `.oracle/tasklist.md` after authorized suffix rebind | `70a9185d40cf7502a25cbaedd46db3d3bb16ea1f139bc8a8f6b7082c070dbc73` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| NBF08 suffix-rebind record | `b2c09eee42da4e1fb251315773ca527aa31cb0e8159bc6b08901ffec59048723` |

The NBF08 record is a separate planning-authority change. Its files are not
included in the candidate manifest or framed source diff.

## Candidate manifest and deterministic framing

The exact classified manifest is
`.oracle/rework/batch-3-attempt-2.manifest.tsv`. It contains 49 unique,
newline-terminated, bytewise-sorted repository-relative paths: 23 NBF04 and
26 NBF05. Its SHA-256 is
`632acc64daf412220eafeb290f26431122b436a22a5b7aaf1c2a748ce27b2ec0`.

The Oracle-only framing implementation is
`.oracle/rework/nbf_batch3_attempt2_diff_v1.py`, SHA-256
`fd03bfc92561dfe0a648cc79dd48187fddfeae65d8be905469d88a0cf9eadb43`.
It uses fixed Git configuration, tracked `--binary --full-index` diffs,
`/dev/null` framing for untracked paths, uint64 big-endian path/status/diff
length framing, and fail-closed absolute-header checks. Reproduce with:

```bash
python .oracle/rework/nbf_batch3_attempt2_diff_v1.py \
  --base 7453b3e57dbf6a9ddb5e1720aaf8720ee17bd47e \
  --manifest .oracle/rework/batch-3-attempt-2.manifest.tsv \
  --output .oracle/evidence/batch-3-attempt-2-framed-diff.json
```

The deterministic output is
`.oracle/evidence/batch-3-attempt-2-framed-diff.json`, SHA-256
`85d3317efcedbd53bb864f90d93e3bce1c23e87903906af07dd8b81c19766317`.
It records 49 paths (33 tracked, 16 untracked), 714485 raw diff bytes, and
aggregate identity:

`8f732a1984fbcfd7b52aef05e5d33c2baec2802dc3fdb508ec0469694bf66046`

The output was generated twice to
`.oracle/evidence/batch-3-attempt-2-framed-diff-rerun.json`; both output
SHA-256 values are identical. A source/test content snapshot before, between,
and after framing was identical:
`2492e4d2505f062158d2f2f0f29103f6903b61da52e8dc4861b008ca2a78110b`.

## Prior NBF-04 acceptance identity

The accepted NBF-04 attempt-11 packet remains linked evidence:

- packet `.oracle/rework/batch-3-nbf04-attempt-11.md` —
  `83f35cbc29f559d212fd1fc2bad8f8178fabd4d726bb30eafbc3c46a02c83071`;
- Luna brief `.oracle/briefs/review-batch-3-nbf04-attempt-11-luna.md` —
  `ad421a2b79ed87a8da418495d30b6fc9ef814cf7d3df023ed2560b279cd33c75`;
- 25-path manifest `.oracle/scripts/nbf04-attempt-11.manifest` —
  `c6cccbe732ce8b45f65779f95db4b246f0f85a433b0e304a9cb7912b971b9b5e`;
- NBF04 framed aggregate —
  `b3945b43cc62136d463745c2c18e2066ee7b1ff8a4d2d81b3c41b4a2c6963f4b`;
- NBF04 framed output —
  `eb849a52235b2e1d63a7adf995738c5ce33c6271814fb8ecc28caae73a06b342`.

## Validation evidence

The supplied Python validation evidence is
`.oracle/evidence/batch-3-attempt-2-python-validation.md`, SHA-256
`17a04c58d00b0831363e6e8a17b9ec6c602a6cdf2b62f2b6229a38062a31989`. It
records **435/435 passed**: 266 watchdog-wrapper, 26 managed-agent, 129
authority/ledger/operator/custody, and 14 inventory/no-bare checks.

The supplied static/runtime evidence is
`.oracle/evidence/batch-3-attempt-2-static-runtime-validation.md`, SHA-256
`1a9ab22f4b3e48aa8569f3536714dfc5f3fe03bb997940c0eaccc2eaeceb340c`.
It records six wrapper `bash -n` passes, 11 Python compilation passes,
generator/static checks, 14 authority/tmux/operator checks, and final
`git diff --check` PASS.

The generated NBF-05 inventory is
`docs/nbf-signal-inventory.json`, SHA-256
`1d9d9ad599ec4508c728776999e882ea809f5b60d753d1c80b435a2e0b9872be1`;
it contains 123 entries and source-input digest
`cf65ded241e0f06543ed9f6a1c616f15619ebe86ede5ea5a051e7334710e2e75`.
The generator `--check` passed and its deterministic/no-self-digest contract
was verified.

## Exclusions and residual classification

The contaminated historical combined run (`174 passed`, `9 failed`, `187
pytest temporary-directory errors`) is explicitly excluded and contributes no
acceptance credit. Historical manifests, packets, Batch 2 Oracle evidence,
NBF08 briefs/addenda/research/scripts, the tasklist/status suffix metadata,
and the NBF08 rebind record are planning/review provenance outside this code
candidate. `evidence/m11-recovery-topology-surfaces.json` is an unrelated
generated artifact and is quarantined. `babysitter-runs/` and the demo
babysitter receipt JSON files are stale ad hoc outputs and are excluded.

Known stale fixture classifications remain the unrelated runtime-attestation
seed expectation, the former OMP-vs-HERMES fixture expectation (migrated in
the supplied Python evidence), and the old provider-timeout-124 expectation
versus the current cleanup-hold-75 contract. None is NBF04/NBF05 acceptance
evidence or a reason to begin NBF06.

No source content mutated during framing. No commit, push, merge, deployment,
main-branch change, NBF06 launch, NBF08 implementation, or epic launch was
performed.

