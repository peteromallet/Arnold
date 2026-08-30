# Immutable receipt — Grok 4.6 Oracle gate NBF-01 / Batch 1 rework 4

- Oracle: Grok 4.6
- Reviewer count: exactly one independent review (GPT-5.6 Luna at high reasoning)
- Binary token: `ACCEPTED_ISSUES`
- Repository: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- Candidate branch: `megado-nbf-guard-0826`
- Candidate HEAD at gate execution: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source / origin/main / merge-base: `798c50619204010ed3f4297fbb57988fe9381924`
- Owned production diff SHA-256: `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41`
- North Star SHA-256: `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e`
- Plan v8 SHA-256: `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1`
- Frozen tasklist SHA-256: `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589`
- Custody SHA-256: `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0`
- Agent goal SHA-256: `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864`
- Model-policy receipt SHA-256: `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064`
- Tasklist-freeze receipt SHA-256: `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24`
- Attempt-4 packet SHA-256: `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534`
- Attempt-4 triage brief SHA-256: `d6c559d694c006d4fd310ae706779604ebe228f713a27a40669d6c5c1c040c0f`
- Attempt-4 triage receipt SHA-256: `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c`
- Attempt-4 execution brief SHA-256: `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d`
- Attempt-4 executor finding SHA-256: `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1`
- Attempt-4 executor receipt SHA-256: `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f`
- Gate brief SHA-256: `01cf0e10566043085028bc3c31a19c687b76aca0f12e917489e80013e631af8a`
- Luna review brief SHA-256: `901efaafab9af281c1e9e847b0790cd334ca436b9109890d33a8e0097ceb9096`
- Luna review check-in: `.oracle/checkins/batch-1-rework4-luna.md`
- Luna review check-in SHA-256: `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c`
- Luna review receipt: `.oracle/receipts/oracle-nbf01-rework4-luna.md`
- Luna review receipt SHA-256: `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee`
- Grok check-in: `.oracle/checkins/batch-1-rework4-grok.md`
- Grok check-in SHA-256 after write: `5d4a18cf08a6d40a375300071fbe7c350d809db02fc0cb08258b9b7632b1c06f`
- Isolated Luna review root: `/tmp/oracle-nbf01-rework4-luna-review/`
- Isolated Oracle probe root: `/tmp/oracle-nbf01-rework4-grok/`
- Isolated executor evidence root: `/tmp/oracle-nbf01-rework4-luna/`

## Historical attempt-3 identities (labeled historical)

- Gate brief SHA-256: `5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01`
- Packet SHA-256: `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779`
- Triage receipt SHA-256: `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b`
- Executor finding SHA-256: `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f`
- Executor receipt SHA-256: `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f`
- Luna review check-in SHA-256: `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd`
- Luna review receipt SHA-256: `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425`
- Grok check-in SHA-256: `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02`
- Grok receipt SHA-256: `95ec60c0f981217500b9922ac86ffb95d6c60036d39ea32d07761731716c3a30`
- Attempt-3 production diff SHA-256: `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`

## Luna launch

Actual command:

```text
python /Users/peteromalley/.claude/skills/subagent-launcher/launch_hermes_agent.py \
  --model="codex:gpt-5.6-luna:high" \
  --query-file=/Users/peteromalley/Documents/Arnold-oracle-nbf/.oracle/briefs/oracle-nbf01-rework4-luna-review.md \
  --project-dir=/Users/peteromalley/Documents/Arnold-oracle-nbf \
  --timeout=3600 \
  --metadata-file=/tmp/oracle-nbf01-rework4-gate/luna_launch.meta.json
```

- Requested model: `codex:gpt-5.6-luna:high`
- Resolved model: `openai-codex/gpt-5.6-luna`
- Thinking: `high`
- Start UTC: `2026-08-30T03:13:33Z`
- End UTC: `2026-08-30T03:33:29Z`
- Elapsed seconds: `1196.497`
- Launcher exit: `0`
- Metadata SHA-256 of `/tmp/oracle-nbf01-rework4-gate/luna_launch.meta.json`: `b33366927441ad078062438852f4a29e74a42554786beb1659903cd77715923a`. File records `status=completed`, `exit_code=0`, `elapsed_seconds=1196.497`.
- Recommendation printed on stdout: `RECOMMEND_ACCEPTED_ISSUES`

There was no second reviewer, fan-out, parallel review, tiebreaker, or
replacement reviewer.

## Path/hash inventory (Oracle-verified MATCH)

| Artifact | Expected SHA-256 | Result |
| --- | --- | --- |
| `.oracle/tasklist.md` | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` | MATCH |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` | MATCH |
| `.oracle/plan.md` | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` | MATCH |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` | MATCH |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` | MATCH |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` | MATCH |
| `.oracle/receipts/tasklist-freeze-v8.md` | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` | MATCH |
| `.oracle/rework/batch-1-attempt-4.md` | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` | MATCH |
| `.oracle/briefs/oracle-nbf01-rework4-triage-grok.md` | `d6c559d694c006d4fd310ae706779604ebe228f713a27a40669d6c5c1c040c0f` | MATCH |
| `.oracle/receipts/rework-triage-batch-1-attempt-4-grok.md` | `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c` | MATCH |
| `.oracle/briefs/execution-nbf01-rework4-luna.md` | `25b981e7e20cda6e7aff2027074631dc3b713ec11b0015df81238138e484c79d` | MATCH |
| `.oracle/findings/execution-nbf01-rework4-luna.md` | `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1` | MATCH |
| `.oracle/receipts/execution-nbf01-rework4-luna.md` | `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f` | MATCH |
| `git diff origin/main --` five tracked production files | `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41` | MATCH |

Owned-file SHA-256 / git-blob identities all MATCH the executor inventory,
including `incident/disposition.py` SHA-256
`8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` / blob
`74d640b20fe1b4c8edc58cbafd5d3d5756712ec3`. Unchanged
`test_incident_ledger.py` SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` / blob
`44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`.

## Oracle-independent command transcripts

Cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`. Empty stderr SHA-256 is
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

| Command | Exit | stdout SHA-256 | stderr SHA-256 |
| --- | ---: | --- | --- |
| focused nine-module pytest | 0; `121 passed in 18.90s` | `4ecfb82fa61de97c12206a89fc3d64df05dbfd2e97d54ee97ce6341e22810edf` | empty |
| legacy four-module pytest | 0; `78 passed in 1.33s` | `8e785d2cefb3d1fa5ef35d4b67eb50c15777ef055b2393bfde2d150058e18b8e` | empty |
| RW4-01 coherent-forgery/reader subset | 0; `3 passed, 5 deselected in 0.23s` | `4542eeb8daee912403117d8bc47349aa027385f7ef468728397fb9d94a2e69f7` | empty |
| RW4-05 confirmation-only pytest | 0; `7 passed in 0.27s` | `3b699c09a131f6fce9f8c5f77719de7f8be6f3d226bd0fbfbe7c408b1742ff02` | empty |
| `python -m py_compile` owned production modules | 0 | empty | empty |
| `git diff --check` | 0 | empty | empty |

Executor stream SHA-256 values independently reproduced, including focused
`1f01445f45b658375e82f8d266eabe7313865719db122c33c2cb662c1ad28019`, legacy
`db85410b01611725bec965e80009492342796bc42dc7b8ce17f65bafb28bd372`, RW4-01
`12892781cd69a69f7898391ccbf529aa47762cc0ad42d40b434ef5752e4dbc64`,
confirmation-only
`3b699c09a131f6fce9f8c5f77719de7f8be6f3d226bd0fbfbe7c408b1742ff02`, and broad
`8fb59a66f2a82c1b28b58912dce97aecc50c5511677ea3bd9a034b4081646c5c`.

## Independent probe transcripts

| Probe | SHA-256 | Result |
| --- | --- | --- |
| `/tmp/oracle-nbf01-rework4-grok/independent_probes.json` | `c6d9bb96ab7ce0fe467bffc20cd2a538066492fb94f2ab474d3f2326c01a5a8f` | public `from_dict`/append/consume reject; valid reader appends and consumes once |
| `/tmp/oracle-nbf01-rework4-grok/bypass_probes.json` | `10902f023236bf899323a23588f7ce0c6afa59e0b5fd50a1b66906f391649602` | `validate_nbf_event` and `_append_nbf` accept coherent forgery; event projects |
| `/tmp/oracle-nbf01-rework4-grok/authz_probes.json` | `ee31dfee57767a322fe590b3f23a4b8a457eb55ece221179913fc9f708839a1d` | `reserve()` accepts the projected forged change |
| Luna `wire_forgery_probe.stdout` | `4a292ceb0c1dff3ce9d26125ab82293e6bf5f2013cc8e77be48bec111aabd6aa` | `validate_nbf_event` accepted; `_append_nbf` accepted; forged projected |
| Luna `wire_forgery_probe.json` | `eb992fd4f35ac4c810cd45da987d55b2064f1b1f93fb75d2c5ed4d045dbf6a92` | same probe metadata |

## CLI subprocess digests

Executor CLI JSON hashes independently reproduced. Status 0 stdout SHA-256
`de85b9592423e61ef59c4a860ba75e55ed618dd8934da164df3f802f16b71e85`; statuses
2/3/4/5 have empty stdout SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Status 4
stderr SHA-256
`d66b73aa1cfb355b1e8200db1049053773e16bc3f484309fcc4c397db5e69a3f`. Status 0
emitted one JSON acknowledgement and did not signal.

Luna independently reproduced status 0/2/4/5 stream hashes. Luna's
check-in/receipt transcribe status-2 schema-invalid stderr as
`2525d332bcb4199a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee`; the
isolated file is
`2525d332bcb419a8f494836678960e858520cbd1e7242cac45f889b0cc7992ee`. Receipt
transcription error only.

## Preservation and mutation statement

Oracle did not implement, repair, stage, commit, push, merge, rebase, reset,
clean, edit production/tests/plans/frozen tasklists/North Star/custody/
historical evidence, start Batch 2, fan out another review, or issue
`PASS_BATCH_1`. Temporary probes and transcripts live only under
`/tmp/oracle-nbf01-rework4-grok/` and `/tmp/oracle-nbf01-rework4-gate/`. The
only authorized worktree writes by this Oracle turn are the Luna review brief
plus the two Grok artifacts. After candidate identity and owned-file/diff
digests were captured, no candidate production or test content was mutated.

## Recommendation

```text
ACCEPTED_ISSUES
```
