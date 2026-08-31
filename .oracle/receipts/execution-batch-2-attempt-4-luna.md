# Batch-2 attempt-4 Luna execution receipt

## Receipt scope

Executor: GPT-5.6 Luna, one writer, strict serial order
`R3-NATIVE-001 → R3-TERM-002 → R3-LIFE-003 → R3-AUTH-004`.
This receipt records implementation and validation evidence only; it is not a
review, judgment, or batch verdict.

Packet `.oracle/rework/batch-2-attempt-4.md` SHA-256:
`888467b711d8c4de2de0ecfedab7245e0bad3af398e45f0c530dfb089749f078`.
Repository/branch: `/Users/peteromalley/Documents/Arnold-oracle-nbf`,
`megado-nbf-guard-0826`. HEAD:
`2297fb330cdb375b4e5bd048f0d5c37d0e06db30`. Base `origin/main`:
`798c50619204010ed3f4297fbb57988fe9381924`. Candidate:
`5da26ec5be4d13559948fe4256a114ad7626482b`; parent
`19deab5bb407273e7e82d40a66fc06d17af93ad4`; candidate tree
`e3d0376482154c4f95d2ec5809d630c4a0c32e69`; pre-edit source/test diff
`acb8ca400c1b0874cea1f030630ba2f186f16cd22ceedfc2a33fe7ab592a19ec`.

Frozen and source evidence rehashes:

| artifact | SHA-256 |
|---|---|
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| Sol check-in | `f48bffe73211a01ec8a95acb1a1cde99fc9ce6276165d64fac32b302609a27ad` |
| Sol receipt | `4dad76f10aaf0a3407ecaff7948ec09d1f07457bf2d04afb683a076cef719759` |
| sealed manifest | `2c60512f34311883849d1530af4c5b719cab7bb29434087985905c36b2573cbf` |
| review-policy override | `1e22ec54c1c1afb33e3d1faf81d2e49b8b540f6f62dbd7e0b264249716c4bccc` |

The packet North Star block exactly matched `.oracle/northstar.md` including
final newline, with computed SHA-256
`d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`.

## Delivered changes

1. Native admission uses authoritative construction-seam proof, exact positive
   constructability, recomputed proof content/generation/digest, route/family
   binding, freshness, and native model catalog checks. Refusal occurs before
   reservation/construction; valid seam construction is single-use.
2. Physical terminal transport is lossless across native, OMP, and managed
   paths. Receipt/dispatch/phase/spec/fingerprint identities are compared,
   typed death remains a worker disposition, phase transport carries the
   canonical outcome, and terminal append failure returns context-bearing
   unresolved state without releasing the reservation.
3. Controlled-door persisted histories are validated globally under the ledger
   lock. Backward, stale, closed-first, accepted-before-entered, mixed-door,
   and contradictory histories are rejected; reopen validates full projection.
   Commit-before-projection and no-launch replay remain intact.
4. OMP receives the canonical WBC adapter and refuses before admission when it
   is absent. The authority checker resolves qualified/import/module,
   assignment, and callable aliases; scans arbitrary fixture door symbols;
   diagnoses falsey/reversed/multiline absent-WBC forms and contextual raw
   process/launch/admission/order categories.

## Command ledger

Evidence root: `/tmp/arnold-b2-attempt4-luna-evidence`. Every JSON record stores
literal argv, cwd, UTC start/end, exit, separate stdout/stderr byte counts and
SHA-256, pre/post porcelain, and changed-path hashes. The sorted 90-file
external evidence manifest hashes to
`e1e935082721b2cd157a4ba1948574e5e76e0153f179f27e08cbdff8e55c11c4`.
All captured stderr streams were 0 bytes, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| literal command label | exit | stdout bytes / SHA-256 | result |
|---|---:|---|---|
| R3-NATIVE-001 packet pytest | 0 | 98 / `d07a1be384f84d9d95b6d48bfc797264bdf209a84dca560c1775e944c8887ef5` | 4 passed |
| R3-TERM-002 packet pytest | 0 | 98 / `3de0922879cc7b6509a3ad1ea40ed1f93b71bfe1a47df2a0588277d5be9a14dd` | 5 passed |
| R3-LIFE-003 packet pytest | 0 | 98 / `5c9258a0de83f38243aa16ddbdf4932629810a56e692fb8852a52f3a6f665024` | 5 passed |
| R3-AUTH-004 packet pytest | 0 | 98 / `bba54d0d911e4f4b3ff7099be56f23a579126dd0cbb36d88eb246b10ef320d5b` | 5 passed |
| full authority module | 0 | 99 / `da19776f28c1d566682bf8257b6879a72a4ccf5caa24bff0c678991f96a3bb16` | 14 passed |
| preserved suite 1 | 0 | 100 / `16fd66e8725a47f4e13b9f2756c1cbf43df83ba1cd247170daf16004601c1102` | 59 passed |
| preserved suite 2 | 0 | 99 / `89bb8a17243781f072bd93286127e374f77a0118bad47dec5c7b836a85c2b16` | 53 passed |
| preserved suite 3 | 0 | 180 / `e8e7512bc6d609785e712b176bac3bc6602c533ad6f0e19d5f879df42234e96f` | 90 passed |
| preserved suite 4 | 0 | 179 / `7de2705dd0aa804ddef0b0a64440eec5a1023df15248c21732fe0318b725a2fd` | 74 passed |
| frozen NBF-02 first run | 1 | 5896 / `63d44d4b18d52cb4a235d339b7d0d1efa5f1686e501e3d061f02ff8d821d0cd7` | 254 passed, 3 pre-existing unresolved-payload assertions exposed |
| frozen NBF-02 corrected rerun | 0 | 351 / `6e2c89136aad208ce1257bf041f973a48847437294d81af7198eaf21061cbe0e` | 257 passed |
| frozen NBF-03 | 1 | 7033 / `02cb9731768e9b95f63acaab44ed16ca5cbd439bc28c269ca20cd1753a2a13ff` | 60 passed, 4 unchanged babysitter baseline failures |
| baseline preservation diff | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | clean baseline paths unchanged |
| checker `--check` | 0 | 213 / `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | `ok: true`, no diagnostics |
| compileall | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | success |
| `git diff --check` | 0 | 0 / `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | success |

The NBF-02 first-run failures were corrected by restoring the existing frozen
unresolved-payload invariant; the corrected exact gate is the authoritative
result. NBF-03's four failures are unchanged baseline failures: routing default
and legacy managed controller expectations plus the two single-flash renderer
expectations. The exact parent diff over the four preserved paths was clean;
parent/HEAD renderer absence checks were both exit 0.

The independent raw-symbol scan for
`refresh_runtime_launch_seed_for_worker_dispatch` and
`require_configured_runtime_launch` over all three configured doors returned no
matches via the specialized repository search tool. The packet's shell `rg`
form was not invoked because the runtime tool policy requires the specialized
search tool.

## Final identity and diff evidence

- branch identity stdout: `megado-nbf-guard-0826`; HEAD stdout:
  `2297fb330cdb375b4e5bd048f0d5c37d0e06db30`; origin/main stdout:
  `798c50619204010ed3f4297fbb57988fe9381924`.
- candidate `git show -s --format=%H%n%P%n%T` matched candidate, parent, and tree
  identities above.
- full source/test diff from candidate: 153829 bytes,
  `67ddac58cab14775fc375504d340b9afe5c41fb7ae612c10df32fd31482d3163`.
- production-only diff (`arnold_pipelines scripts`): 109379 bytes,
  `009aeb36e1ba2d2812e8c89a792845333acc90ede57b9361e4e79bda9db67d32`.
- final inventory: 21 modified tracked source/test paths, 0 untracked paths under
  `arnold_pipelines scripts tests`; all per-path hashes are in the captured
  inventory JSON and every command's changed-path hash map.

## Non-actions and custody

No commit, stage, push, merge, reset, history rewrite, nested model, reviewer,
verdict, Batch 3, or mutation of `.oracle/tasklist.md`, `.oracle/northstar.md`,
`.oracle/plan.md`, `.oracle/agent_goal.md`, `.oracle/custody.md`,
`.oracle/status.md`, execution history, or prior artifacts occurred. Existing
run dirt was preserved. This receipt and its paired finding are the only new
versioned executor artifacts created by this execution.
