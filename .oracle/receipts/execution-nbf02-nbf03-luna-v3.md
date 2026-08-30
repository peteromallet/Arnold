# NBF-02/NBF-03 Luna v3 executor receipt

Executor receipt only. No Oracle verdict or self-review is asserted.

Evidence-integrity seal note: this receipt's pre-seal SHA-256 was
`4f113c22b015328b09b12f0024a6c9f7c14a7843d49309c37dfe5e5421fea2b5`.
The seal corrects launcher provenance and adds missing incident,
intermediate-attempt, capture-limit, and untracked-diff identities without
changing source, tests, or observed validation outcomes.

## Run identity

- Candidate HEAD: `19deab5bb407273e7e82d40a66fc06d17af93ad4`
- Source/base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Branch: `megado-nbf-guard-0826`
- Evidence root: `/tmp/oracle-nbf02-nbf03-luna-v3-0830/`
- Frozen tasklist: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- North Star: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Extracted North Star block: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`, byte-equal to `.oracle/northstar.md`
- Batch-1 PASS checkpoint: `878a9b2980f0eab6642ed51c30e687903a7213b9`
- Fresh sealed finding artifact: `.oracle/findings/execution-nbf02-nbf03-luna-v3.md`, SHA-256 `c0424a580d08648cdba04d5cf689783bc06179295b62387d7aabaa8830c60ca9`
- Pre-seal finding SHA-256: `bca08adddd08eb1b05c0b411871eb8c214cf9cf50eaed420dd0dbc9cf546bc42`
- Orchestration incident receipt: `.oracle/receipts/batch-2-premature-gate-and-v3-nested-launch.md`, SHA-256 `b9f52bd8c7368f9604140d6021c30a72673992eee0e802bd8430f55b94122b4d`

## Launcher transcript

Exact invocation:

```text
PYENV_VERSION=3.11.11 python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py --model="codex:gpt-5.6-luna:high" --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/execution-nbf02-nbf03-luna-v3.md --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf --timeout=3600
```

Requested model was `codex:gpt-5.6-luna:high`. Independent process snapshots
proved that top-level launcher PID `80650` used that exact selector with
`--timeout=3600`, and OMP child PID `80680` resolved
`openai-codex/gpt-5.6-luna --thinking high`. CWD was
`/Users/peteromalley/Documents/Arnold-oracle-nbf`; process start was
`2026-08-30T07:39:45Z` (system process clock `09:39:45 +0200`). No complete
top-level launcher stdout/stderr or exit marker was saved, so none is claimed.

The evidence-root `launcher/` streams are a different, prohibited nested
same-model launch: stdout bytes `0`, SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`;
stderr bytes `417`, SHA-256
`85698e77f9b1432affc7506c45d7f5038e80f284ae42d37c083ccef694770d59`;
end `2026-08-30T07:44:31.624259000Z`; exit `143`; no final output. It is
quarantined by the incident receipt and does not count as valid executor or
review evidence.

## Command manifest

All commands ran serially from `/Users/peteromalley/Documents/Arnold-oracle-nbf`; complete captured streams are under the evidence root.

| command | exit | UTC timing files | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|---|
| frozen NBF-02 pytest matrix | 0 | `nbf02-final.start`, `nbf02-final.end` | `e21f0bf0c9c0c932bfc94cdb941c9091240eb6f5fbb686e7dbd6e94615d30c37` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| frozen NBF-03 pytest matrix | 1 | `nbf03-final.start`, `nbf03-final.end` | `5796652fad5e3cf4e8ac4eb80a4e8f2b371120c3c10ef72b8f12088ed63166a9` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `python scripts/check_worker_admission_authority.py --check` | 0 | `authority.start`, `authority.end` | `e56d8b9a518cefd21a0aa7da98ed2d0c78b9f0e3a3ce3fcdb4b63f4fa5ae48f2` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| exact raw-symbol `rg` scan | 0 | `raw-scan-final.start`, `raw-scan-final.end` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| changed-file `python -m py_compile` | 0 | `compile-final.start`, `compile-final.end` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `git diff --check` | 0 | `git-diff-check.*` | empty | empty |
| isolated source-checkpoint babysitter modules | 1 | command output captured | `f95a7400938f47c4a8e82b2636fc6f345ba7548a8ecd4bb7f9ec0f677b29f12c` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The frozen NBF-02 matrix reported `242 passed in 303.69s`. The frozen NBF-03 matrix reported `41 passed, 4 failed in 19.97s`. The isolated source-checkpoint run reported `12 passed, 4 failed in 19.93s` with the same four babysitter failures, proving those failures against the source checkpoint.

Preserved attempts preceding the final NBF-02 pass:

| command evidence | exit | result | stdout SHA-256 | stderr SHA-256 |
|---|---:|---|---|---|
| `nbf02.*` | 2 | collection error: missing `pytest` import | `f09d594765f4043d735c5d8ccabe6ec1919eef6ef8f7fa0b194eaf97674176e7` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `nbf02-rerun.*` | 1 | `237 passed, 5 failed`; missing classifier import | `fee5689e8507dea7de2effe47bab8a46dbf28708f3e14932a139fe68356d4f47` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw-scan.*` | 1 | direct `rg` no-match status, empty streams | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `raw-scan-final.*` | 0 | required wrapped no-match success | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

### Exact-command coverage audit

- NBF-02: exact frozen argv and ordering independently observed in the live
  pytest process; complete final streams/timing/exit captured; `242 passed`.
- NBF-03: executor-attested frozen path ordering and complete streams/timing/
  exit captured; no separate argv file; `41 passed, 4 failed`.
- Authority checker: exact frozen command named and complete streams/timing/exit
  captured; pass.
- Raw-symbol scan: exact frozen shell wrapper named and final complete streams/
  timing/exit captured; pass. The earlier direct-`rg` exit `1` is preserved.
- Changed-file compile: final streams/timing/exit captured; pass. The exact
  standalone compiled-file argv was not captured.
- `git diff --check`: exit and complete empty streams captured; pass. Separate
  start/end files were not captured.
- Clean-HEAD reproduction: exit and complete streams captured; same four
  failures. Literal command/start/end were not separately captured. The two
  tests and two load-bearing baseline production files were byte-equal to HEAD.

These stated capture gaps are evidence limitations. No missing argv or timing
is reconstructed as though it had been captured.

## NBF-03 baseline failures

The failures are:

1. `test_babysitter_routing_defaults_to_legacy_deepseek` (`omp` versus expected `legacy`);
2. `test_legacy_managed_spec_keeps_hermes_controller` (Hermes launcher expectation);
3. `test_renderer_requires_single_flash_orchestrator_contract` (missing `codex:gpt-5.6-luna`);
4. `test_renderer_cli_mentions_single_flash_contract` (missing the frozen STEP 1 text).

`routing.py`, the goal renderer, and those tests were unchanged by the candidate diff. The isolated `git archive HEAD` run reproduced all four. These remain baseline blockers; they were not silently waived.

Byte-equality SHA-256 evidence for the isolated files versus `HEAD`:
`test_babysitter_routing.py`
`ba75ceca1f1316864aef83d6f92a81fae2cd4e88c2da0168dac1391d817eb7fa`,
`test_babysitter_goal.py`
`4e85a83fa889640abaea70046d73498a2ed407bccffc3434750c764df2c87153`,
`cloud/babysitter/routing.py`
`285af9a1ac4f2db640d4ca781f426e4c52f2af47203a5deff0f0db805a62f9eb`,
and the goal renderer
`8e781247c8e8de436bb78dba3e55e799b6e2300c6f72f623866477c01e26aa3d`.

## Final repository evidence

- Production-plus-focused-test tracked diff against `origin/main`: `bf07bc4ab75cacd1d7db795706afa0ea37b8b157179f4a34fb927fea1399d839`.
- Tracked worktree diff against HEAD: `a58df4f62067af701c298f4fc80047394b1f0f8a757e46bc6fa460c052efc192`.
- Canonical production-plus-test diff including all 12 untracked candidate
  files: `5586c1861dce44334c3991e997bdc8b90b82d25d2ed8f28bb558b42aae499fd0`.
  Canonical construction is the concatenation of
  `git diff --binary --full-index origin/main -- arnold_pipelines scripts tests`
  and, in lexical order, each untracked path's
  `git diff --binary --full-index --no-index /dev/null <path>` bytes. The
  full-index tracked component is
  `31dff1ad82dc0491fcc42fb7aa04c60f0f9f0088db8387f84b53521249a3d8c4`.
- Timeout-audit prior tracked worktree diff: `e945526a223f4c03f866d892d4ab5be70c189d7fbcfb9c70552f06bf68b3f6fd`.
- Restoration against HEAD is additions-only: `17/0` for
  `test_phase_result_classify.py` and `6/0` for `test_plan_circuit.py`.
- Changed Python files compiled successfully.
- `git diff --check` passed.
- No commit, stage, push, merge, rebase, reset, clean, Batch 3, or protected status/goal/custody/frozen/live-box/chain mutation occurred.

## Prior immutable artifact bindings

- First brief `938f61b1ccaa06ea9cd7e428b184d02143f9e87accf96eeb95ec8b0e70797003`, heading defect recorded in the finding.
- First finding `9c8e6b7db2a104056c9843ffad59b04234e2dc904a8898858d049fdaf0ed1ff0`, abbreviated/incorrect historical binding defect recorded in the finding.
- First receipt `b957f16fab1aa5502440434b1c51931b584b2321fc7be1c88af0ce7797367b07`.
- Corrected v2 brief `f6daf95f6b7ff91c0840170a98e3d8263e56faf28c64a4d3acd0535cdb1f2e6e`, abbreviated diff binding and missing explicit `:high` recorded.
- v2 timeout receipt `e8c4f572ed34bda80fdebf9307c856bb336037de54ef32e26b33ec202a5c66e4`, session `88209`, PIDs `74894/74917`, wrapper exit `124` after default `1800s`, with no v2 finding/receipt.
- `.oracle/plan.md` `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`.
- `.oracle/agent_goal.md` `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`.
- `.oracle/custody.md` `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`.

## Receipt hash

This file's final full SHA-256 is to be recorded by the executor's terminal delivery alongside the finding hash above.
