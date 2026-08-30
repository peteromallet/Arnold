# NBF-02/NBF-03 Luna v3 executor findings

This is executor evidence, not a review, Oracle judgment, or verdict. It records the continuation boundary, implementation carried in the dirty tree, and the validation results observed locally.

Evidence-integrity seal note: the pre-seal artifact SHA-256 was
`bca08adddd08eb1b05c0b411871eb8c214cf9cf50eaed420dd0dbc9cf546bc42`.
The seal corrects the launcher provenance, adds the untracked-inclusive
candidate digest, preserves intermediate failures, and records capture limits.
It does not change an implementation or test result.

## Immutable bindings

- Candidate HEAD: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Branch: `megado-nbf-guard-0826`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Extracted North Star block SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`; byte comparison: equal.
- Batch-1 PASS checkpoint: `878a9b2980f0eab6642ed51c30e687903a7213b9`
- `.oracle/plan.md`: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- `.oracle/agent_goal.md`: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- `.oracle/custody.md`: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`

## Prior immutable artifacts and defects

- First brief: `.oracle/briefs/execution-nbf02-nbf03-luna.md`, `938f61b1ccaa06ea9cd7e428b184d02143f9e87accf96eeb95ec8b0e70797003`; North Star heading was lowered from `#` to `##`.
- First finding: `.oracle/findings/execution-nbf02-nbf03-luna.md`, `9c8e6b7db2a104056c9843ffad59b04234e2dc904a8898858d049fdaf0ed1ff0`; historical v2 binding `77831c...` was abbreviated/incorrect.
- First receipt: `.oracle/receipts/execution-nbf02-nbf03-luna.md`, `b957f16fab1aa5502440434b1c51931b584b2321fc7be1c88af0ce7797367b07`.
- Corrected v2 brief: `.oracle/briefs/execution-nbf02-nbf03-luna-v2.md`, `f6daf95f6b7ff91c0840170a98e3d8263e56faf28c64a4d3acd0535cdb1f2e6e`; it used an abbreviated diff binding and omitted explicit `:high`.
- v2 timeout receipt: `.oracle/receipts/execution-nbf02-nbf03-luna-v2-timeout.md`, `e8c4f572ed34bda80fdebf9307c856bb336037de54ef32e26b33ec202a5c66e4`; session `88209`, PIDs `74894/74917`, wrapper result `124` after default `1800s`, with no v2 finding/receipt.
- Timeout-audit tracked worktree diff: `e945526a223f4c03f866d892d4ab5be70c189d7fbcfb9c70552f06bf68b3f6fd`.

## Implemented continuation surface

The carried dirty implementation contains typed admission request/receipt/refusal/context, bounded OMP membership resolution, native liveness proof, reservation/fingerprint admission, controlled launch state, generic scheduling/T7 cooldown, reconciliation, linked-child construction, typed terminal transport, three-door wiring, and the targeted authority checker. The large accidental test deletions were restored before validation; the only additional v3 test repair was restoring the missing `pytest` and classifier imports in `test_phase_result_classify.py`.

## Validation evidence

Evidence root: `/tmp/oracle-nbf02-nbf03-luna-v3-0830/`.

1. Frozen NBF-02 command, exact paths and ordering: exit `0`; `242 passed in 303.69s (0:05:03)`. stdout SHA-256 `e21f0bf0c9c0c932bfc94cdb941c9091240eb6f5fbb686e7dbd6e94615d30c37`; stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
2. Frozen NBF-03 command, exact paths and ordering: exit `1`; `41 passed, 4 failed in 19.97s`. stdout SHA-256 `5796652fad5e3cf4e8ac4eb80a4e8f2b371120c3c10ef72b8f12088ed63166a9`; stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
3. Authority checker `python scripts/check_worker_admission_authority.py --check`: exit `0`; stdout SHA-256 `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2`; stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
4. Required raw-symbol scan using the exact `rg` expression: exit `0`, no output.
5. Changed-file `python -m py_compile`: exit `0`, no output.
6. `git diff --check`: exit `0`, no output.

### Preserved intermediate attempts and capture audit

- The first NBF-02 attempt (`nbf02.*`, `2026-08-30T07:51:40Z` through
  `07:52:06Z`) exited `2` during collection because the restored test file was
  missing `pytest`; stdout SHA-256
  `f09d594765f4043d735c5d8ccabe6ec1919eef6ef8f7fa0b194eaf97674176e7`.
- The next exact NBF-02 attempt (`nbf02-rerun.*`, `07:52:42Z` through
  `07:59:20Z`) exited `1` with `237 passed, 5 failed`; all five failures were
  missing `classify_dispatch_outcome` imports. Its stdout SHA-256 is
  `fee5689e8507dea7de2effe47bab8a46dbf28708f3e14932a139fe68356d4f47`.
  The repaired final exact run is the 242-pass result above.
- `raw-scan.*` preserves an initial direct `rg` no-match exit `1` with empty
  streams. `raw-scan-final.*` captures the required shell wrapper, where no
  matches correctly yields wrapper exit `0`. Both empty streams hash to
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
- The final checker, compile, and raw-scan runs have start/end/exit and complete
  streams. `git-diff-check.*` has exit and complete empty streams but no
  separately captured start/end files. The isolated baseline run has exit and
  complete streams but no separately captured literal command/start/end files.
  These are evidence-capture limitations, not retroactively invented data.
- The exact NBF-02 argv/path ordering was independently observed in the live
  pytest process and matches the frozen brief/tasklist byte-for-byte. The
  NBF-03 exact path ordering is attested by this executor finding and its output
  names all four failures from the two expected babysitter modules, but no
  standalone argv file was captured. The checker and raw-scan literal commands
  are the frozen commands in the bound v3 brief. The compile transcript proves
  exit `0`, but its standalone argv/file list was not captured.

### NBF-03 four failures

The four failures are pre-existing against the source checkpoint, not introduced by the NBF-02/NBF-03 dirty production diff. An isolated `git archive HEAD` copy ran the exact two babysitter modules with the same four failures and `12 passed in 19.93s`; baseline stdout SHA-256 `f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c`; stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

The isolated files were verified byte-for-byte against candidate `HEAD`:
`test_babysitter_routing.py`
`ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`,
`test_babysitter_goal.py`
`4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`,
`cloud/babysitter/routing.py`
`285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`,
and `skills/babysitter/scripts/render_babysitter_goal.py`
`8e781247c8e8de436bb78dba3e55e799b6e2300c6f72f623866477c01e26aa3d`.

The failures are the existing default babysitter route expecting `legacy` while it resolves `omp`, legacy managed-spec Hermes expectation, and two babysitter-goal renderer contract assertions. `routing.py`, the babysitter goal renderer, and those tests are unchanged by the candidate diff. They are retained as honest baseline blockers rather than silently waived or broadened into this batch.

## Launcher record

Exact authorized command:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-nbf02-nbf03-luna-v3.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

- Requested model: `codex:gpt-5.6-luna:high`
- Resolved model: `openai-codex/gpt-5.6-luna`
- CWD: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Launcher PID: `80650`; OMP child PID: `80680`
- UTC start inferred from process start `Sun Aug 30 09:39:45 +0200`: `2026-08-30T07:39:45Z`
- Independent process snapshots showed PID `80650` argv with
  `--model=codex:gpt-5.6-luna:high` and `--timeout=3600`; PID `80680` argv
  resolved `openai-codex/gpt-5.6-luna --thinking high`. This is the valid proof
  of explicit Luna/high routing.
- No complete stdout/stderr or exit marker for the top-level launcher was saved
  in the v3 evidence root. It was observed alive through validation and absent
  by the seal audit, but its final exit status is unavailable and is not
  inferred.
- The `launcher/` files under the evidence root belong to a prohibited nested
  same-model launch, not PID `80650`: stdout was empty, stderr SHA-256 was
  `85698e77f9b1432affc7506c45d7f5038e80f284ae42d37c083ccef694770d59`,
  it ended `2026-08-30T07:44:31.624259000Z` with exit `143`, and it produced no
  final output. It does not count as separate executor or review evidence.
- Full incident receipt:
  `.oracle/receipts/batch-2-premature-gate-and-v3-nested-launch.md`, SHA-256
  `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d`.

## Final diff identities

- Production plus focused-test diff against `origin/main` (tracked diff bytes): `bf07bc4ab75cacd1d7db795706afa0ea37b8b157179f4a34fb927fea1399d839`.
- Tracked worktree diff against candidate HEAD (tracked diff bytes): `a58df4f62067af701c298f4fc80047394b1f0f8a757e46bc6fa460c052efc192`.
- Canonical production-plus-test candidate digest including untracked files:
  `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`.
  It hashes one byte stream composed of (1)
  `git diff --binary --full-index origin/main -- arnold_pipelines scripts tests`
  followed by (2), in lexical path order, each untracked file's
  `git diff --binary --full-index --no-index /dev/null <path>` output. The
  full-index tracked component alone hashes to
  `31dff1ad82dc0491fcc42fb7aa04c60f0f9f0088db8387f84b53521249a3d8c4`.
- Timeout-audit pre-v3 tracked worktree diff: `e945526a223f4c03f866d892d4ab5be70c189d7fbcfb9c70552f06bf68b3f6fd`.
- The 12 untracked paths incorporated in the canonical digest are
  `cloud/controlled_final_launch.py`, `cloud/worker_dispatch.py`, the authority
  checker, the cloud dispatch helper, and the eight new focused cloud tests
  listed in the owned-path inventory below.
- Restoration proof against candidate HEAD is additions-only:
  `test_phase_result_classify.py` is `17/0` added/deleted lines and
  `test_plan_circuit.py` is `6/0`; no pre-existing test line remains deleted.
- No commit, stage, push, merge, rebase, reset, clean, Batch 3, status/goal/custody/frozen-file, live-box, or chain mutation was performed.

## Owned path hashes

```text
arnold_pipelines/megaplan/auto.py 5ca83372c4dc5780c5ddebe09730ff3b318d73ea10a6ba113bf920c4f9e6d1e9
arnold_pipelines/megaplan/cloud/babysitter/launch.py c7eb3d3aa2554afd6d5422771f84c9a20d5fed298e4d8dc248d0bc5599fddab6
arnold_pipelines/megaplan/cloud/controlled_final_launch.py b346b6aa5adaccccf0a509b8b4c715a63612668c6a968883e50fc3e6984fe9f6
arnold_pipelines/megaplan/cloud/runtime_attestation.py e08038afb5d7783d3e56f7ac1a02aa1edfd5a72bb7b7197f1b62360d7e441eca
arnold_pipelines/megaplan/cloud/worker_dispatch.py f9e1def2c27df8fcac43a50d3ba75c8bd79107c7ae4f8127b8af7caa0ca0caf9
arnold_pipelines/megaplan/handlers/shared.py 37893b31fe969ce5576abec522c983f38a1553eb6c2756c1434a730fd7e50ecd
arnold_pipelines/megaplan/incident/schema.py 0de97f63dd2534e7d6fd66dccfcb869bea0ee236241063c5a750b02ac400c5a0
arnold_pipelines/megaplan/orchestration/phase_result.py e67c5ee53f14e6fee413796be8cdac84a4eccdd90a5b9b5111ea54430310b860
arnold_pipelines/megaplan/orchestration/recovery_policy.py 01ec09e3acab06a7392fb2dd015f2930de7287c65fb4efe10b6788806a0e2ece
arnold_pipelines/megaplan/orchestration/phase_result_classify.py a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641
arnold_pipelines/megaplan/workers/_impl.py 58e0bf2160a390d015b0a2f10c5bcb92952e7e7be152c8e7a786635ac7631d21
arnold_pipelines/megaplan/workers/omp.py 2a024bd99dc6bbdc2151ea63a7d337a5929357dd869a552ac15de77a7a514767
scripts/check_worker_admission_authority.py 8cd06621669a24f72dfb40242d71c65556683fc5b1574b6b20d382af34c329fd
tests/__init__.py dcd7f82a00ec26a2767168bbf833e21705e158c6fcbd2fcae799fc43836d768a
tests/cloud/__init__.py fc06f4e823a5b115c7fdc798c8dbcce91f3cf7f006bdeced4cadde1499f5a0c2
tests/cloud/dispatch_test_helpers.py 8bfa1fc03b73fab99431ef2647195f319bfb23020eb7112b6856c4be02ca0052
tests/cloud/test_chain_admission.py 917984ff014a5b07b1302ad13eda06227013550585fe20936ef4dbca56c6f753
tests/cloud/test_controlled_final_launch.py 0511b2d502cdbe79ea91c878ea13eed57ecef6b51e6142fcc59104d2155c6120
tests/cloud/test_dispatch_reconciliation.py 75586a4cced570ab3e7f9404bc7928ae4d7a54980ace6ec62f2e1bb2f7556a31
tests/cloud/test_dispatch_with_admission.py 98b9aa185d8f676f0e46304af396483be1fa5066b597c9c1d05a5af84011cc45
tests/cloud/test_worker_admission_authority.py 31706c4163ad39beb975e48eee4207326f518fec320008d789e026bc178c7f5d
tests/cloud/test_worker_dispatch_admission.py fbd3a28680e344290954fd4c409f2345eeae533afc2f309964ff1c0cd78342dc
tests/cloud/test_worker_dispatch_context.py ca3e9d0441ffb4426e27942c33403c5be1947ac400ef32b56d9919b55eb172d8
tests/cloud/test_worker_dispatch_spy.py b8f33cd57d09eea6e7e9a98e29c4d2d490e643ec9c4b67eda40ea9307a21a9a0
tests/arnold_pipelines/megaplan/test_phase_result_classify.py b7a3e3e286533f2b298038726993a4a2c31361e4a1fa2602656e2fe00ffb7a83
tests/arnold_pipelines/megaplan/test_plan_circuit.py 48170e380cdcb288edf3e65c93ba9250d81a548b1b7c538786e0179090fe186b
```
