# Immutable receipt — Grok 4.6 Oracle NBF-01 rework-6 gate

## Review identity

- Model: Grok 4.6 (`grok-4.6`), high reasoning
- Role: Oracle / manager-validator only; not executor
- Gate date: 2026-08-30 UTC
- Gate completion timestamp: `2026-08-30T06:21:00Z` (artifact write window)
- Repository/cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Branch: `megado-nbf-guard-0826`
- Candidate HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source ref and merge-base: `origin/main@798c50619204010ed3f4297fbb57988fe9381924`
- Isolated Oracle probe root: `/tmp/oracle-nbf01-rework6-grok-gate/`
- Isolated Luna review root: `/tmp/oracle-nbf01-rework6-luna-review/`
- Empty-stream SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Verdict token: `PASS_BATCH_1`
- No production/test/plan/custody/history/status/goal/frozen-tasklist edit,
  commit, stage, push, merge, rebase, reset, clean, Batch-2 start, or second
  review was performed by this Oracle.

## Exactly-one independent review dispatch

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="codex:gpt-5.6-luna:high" \
  --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework6-luna-review.md \
  --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf \
  --timeout=3600 \
  --metadata-file=/tmp/oracle-nbf01-rework6-gate/luna_launch.meta.json
```

Hub process name `luna-rework6-review`, pid `2846`, cwd
`/Users/peteromalley/Documents/Arnold-oracle-nbf`. Environment
`PYENV_VERSION=3.11.11`. Hub start `2026-08-30T05:56:08Z`. Process exit 0
after `22m26s` wall / launcher `1346.191s`.

Launcher metadata SHA-256
`21a58a4fb452ca293ec71b62c9147ae59426019d3d96b3a39137b2dddf16f7b0`:

```json
{
  "elapsed_seconds": 1346.191,
  "exit_code": 0,
  "max_tokens": 65536,
  "model": "codex:gpt-5.6-luna:high",
  "resolved_model": "openai-codex/gpt-5.6-luna",
  "status": "completed",
  "toolsets": ["file", "web"]
}
```

Luna stdout recommendation (launcher final text, truncated in hub logs)
begins `Completed the independent Batch 1 rework-6 review.` and names
`RECOMMEND_PASS_BATCH_1`. No second reviewer was launched.

Luna brief SHA-256
`4d84369890661e68450a6ae3bff1ffb22681cd9c6a5b1824ce7d9e1dc83dae38`.
Gate brief SHA-256
`2f9c8e074d4b9ae083ae110ff83bd646937eb57fc32175c586acb5a28dc15275`.

## Bound artifact identities

| Artifact | SHA-256 | Result |
|---|---|---|
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` | MATCH |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | MATCH |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | MATCH |
| `.oracle/plan.md` settled v8 | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | MATCH |
| `.oracle/tasklist.md` frozen | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` | MATCH |
| `.oracle/status.md` | `bbcf8bc7f5a0688e136f16f6e63dc80240eb85856be7dc4d1d829b860f585dfc` | MATCH unchanged |
| model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` | MATCH |
| tasklist-freeze receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` | MATCH |
| attempt-6 packet | `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83` | MATCH |
| attempt-6 triage receipt | `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8` | MATCH |
| attempt-6 execution brief | `c193077b92f94b55e3dc8f4bf3353ec5318e7e745d0e6aff950c373472e96fb6` | MATCH |
| attempt-6 executor finding | `a28a0ff726cccbc00806a44c7f8c7d305019491cf37656b6ad91769250806c44` | MATCH |
| attempt-6 executor receipt | `48d3988675ad1002000f193b915470391c83632bfc815fff2c35d8bd50a937e6` | MATCH |
| attempt-6 completion manifest | `c602969e318ca705f240cd1fcd90c2017f791110d92c7f163378852d0648b2ef` | MATCH as historical executor artifact |
| attempt-6 production diff | `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e` | MATCH |
| attempt-5 production baseline | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` | MATCH as historical |
| attempt-5 Luna check-in | `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6` | MATCH historical |
| attempt-5 Luna receipt | `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143` | MATCH historical |
| attempt-5 Grok check-in | `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6` | MATCH historical |
| attempt-5 Grok receipt | `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef` | MATCH historical |
| attempt-5 packet | `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7` | MATCH historical |
| attempt-4 Luna check-in | `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c` | MATCH historical |
| attempt-4 Luna receipt | `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee` | MATCH historical |
| attempt-4 Grok check-in | `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf` | MATCH historical |
| attempt-4 Grok receipt | `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607` | MATCH historical |
| attempt-4 packet | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` | MATCH historical |
| this Luna check-in | `de278150f2245ce7330694470f5b474788aaf1e234c712a5099dfbda2aeef850` | written by Luna |
| this Luna receipt | `ce5136fde4af45a8d64f372b733ae1868c4b718258177bff88e6f262527ca4ba` | written by Luna |

Candidate identity commands independently returned HEAD, origin/main, and
merge-base exactly as above. Worktree status is dirty with owned candidate
changes and unrelated `.oracle` noise; no clean-tree claim is made.

## Complete owned path/hash inventory

| Path | SHA-256 | git blob |
|---|---|---|
| `arnold_pipelines/megaplan/incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `arnold_pipelines/megaplan/incident/ledger.py` | `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9` | `192f68694ad7cd29c1d28f74539fc7b9f2a82734` |
| `arnold_pipelines/megaplan/incident/schema.py` | `8acb8563adac794d3dc66e39d8db1d12d499207cb5e1b297a395c0a14f640a9d` | `032162bf0efc7b8e14414cd7d6b0738bdf83a613` |
| `arnold_pipelines/megaplan/incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `arnold_pipelines/megaplan/orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `arnold_pipelines/megaplan/orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `tests/.../test_changed_precondition_producers.py` | `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215` | `0773a0f629712065d4f410502b316155f4b8cf89` |
| `tests/.../test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `tests/.../test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `tests/.../test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `tests/.../test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `tests/.../test_supervision_confirmation.py` | `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c` | `2a5a3a88cbae92d69260c93525246846adeb3547` |
| `tests/.../test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `tests/.../test_worker_disposition.py` | `20f60bc664bebe59d9c50a19b6a4fb389cfa4ea54c101bfef6d138f05750aa41` | `59d6ae5a39659fd5858ba10991b702f0396a8cb0` |
| `tests/.../test_incident_ledger.py` | `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` | `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |

`test_incident_ledger.py` matches `origin/main` and remains unchanged.

## Oracle independent command records

Cwd for every command: `/Users/peteromalley/Documents/Arnold-oracle-nbf`.
Manifest: `/tmp/oracle-nbf01-rework6-grok-gate/validation/command-manifest.json`
SHA-256 `9dc159520377ca88b7ae5a9f34fd049fb687a325a2d4de8ea5d3672d22d3bd30`.

| Label | Exact argv | Exit/result | stdout SHA-256 | stderr SHA-256 |
|---|---|---:|---|---|
| named-three | `python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py` | 0; `28 passed in 14.10s` | `bc83eff88d9120124438c684700ad4dec1162f74fd9d943fedcffe10453f04e3` | empty |
| worker-filter | `python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"` | 0; `2 passed, 22 deselected in 0.23s` | `df729e108deb1085c25e36bd45cb46097faba6eddc117b1ffa731afc4a4a841a` | empty |
| terminal-filter | `python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"` | 0; `1 passed, 1 deselected in 0.20s` | `cbef2dd0385da86eece360e3d0ee595e1117d4e9248047b20d4985e9a3ecff97` | empty |
| focused-nine | exact nine-module frozen suite | 0; `124 passed in 15.40s` | `4af247d492a8d696b50ec5676c6da406718caee4f0dff24aa55385d321415dc8` | empty |
| legacy-ledger | `python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py` | 0; `42 passed in 0.39s` | `4061f41c09f3127a2af2a21fc0d63d814ad749628bd1c10594a02bfc2a80ba6d` | empty |
| legacy-modules | exact four-module legacy suite | 0; `78 passed in 1.23s` | `57c0c53f35c958bc21b56b3815fba4dd35c438a8fbb0e0db78cd2b3a72d4859c` | empty |
| py-compile | exact six-file `python -m py_compile` | 0 | empty | empty |
| diff-check | `git diff --check` | 0 | empty | empty |

UTC windows for the validation batch: named-three elapsed `16.749s` through
diff-check elapsed `0.037s` inside `2026-08-30T06:02Z`–`2026-08-30T06:04Z`.
Complete per-command JSON transcripts live beside the streams under
`/tmp/oracle-nbf01-rework6-grok-gate/validation/`.

Independent probe script
`/tmp/oracle-nbf01-rework6-grok-gate/rw6_independent_probe.py`
SHA-256 `1865c0397f832a09fe097d614515bda25fa85ecef0dd7173d9ab8afc81a93f34`.
Probe result JSON SHA-256
`dc2fdfcc6703b2584b98b229057434de57ff026307111671da4bf5947d6dd55a`.
Attempt-5 incomplete-dict reconstruction SHA-256
`5907d4f7978b43674c99e6b2879f94542502618c250bf2a87ec7d1c7b657b53e`.

Luna independent payload probe stdout SHA-256
`03eb77863ca365119b2e3cf9cbcfc21ae637de279f5b7c668f74bc7bb8dcf9c6`
(result JSON SHA-256 `e9015c90060c67a7a495aabba9f0768da66d4ccd75c1d06aa1046b6ed3877b96`).
Luna CLI matrix stdout SHA-256
`b2d687aa21c9f18f0d9d497cbdcdd6dc93469ad25c11cdf97ecbd03af9b3ac14`.

Production-diff command independently reproduced:

```text
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/disposition.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Output: `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`.
The five-file historical command returns the same digest because
`incident/disposition.py` is untracked.

## Criterion dispositions

Full tables live in `.oracle/checkins/batch-1-rework6-grok.md`. Summary:

- C01, C40: `UNEVIDENCED` by explicit exclusion.
- C02, C13: `MET` as named four-door proof plus independent probes.
- C03–C12, C14–C39, C41: `MET`.
- CP01–CP11: `MET`.
- RW6-01, RW5-01, RW5-02, RW5-03, RW4-01 through RW4-06, RW-CUSTODY, A3-01
  through A3-09: `MET`.
- Broad missing modules remain `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER`.
- Broad suite was not rerun.

## Explicit non-actions

No source, test, frozen tasklist, settled plan, North Star, custody, status,
agent goal, historical receipt/finding/check-in, or rework-packet mutation
occurred in this Oracle turn other than writing:

- `.oracle/briefs/oracle-nbf01-rework6-luna-review.md` (review brief)
- `.oracle/checkins/batch-1-rework6-grok.md` (this gate check-in)
- `.oracle/receipts/oracle-nbf01-rework6-grok.md` (this receipt)

Luna independently wrote only:

- `.oracle/checkins/batch-1-rework6-luna.md`
- `.oracle/receipts/oracle-nbf01-rework6-luna.md`

No commit, stage, push, merge, rebase, reset, clean, or Batch 2 start
occurred. Temporary probes exist only under
`/tmp/oracle-nbf01-rework6-grok-gate/` and
`/tmp/oracle-nbf01-rework6-luna-review/`.
