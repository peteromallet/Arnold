# Immutable receipt — Grok 4.6 Oracle NBF-01 Batch 1 rework-3 gate

- Oracle: Grok 4.6 (manager/validator only; no implementation)
- Date: 2026-08-30
- Role: attempt-3 hard gate after frozen supplemental tasklist `.oracle/rework/batch-1-attempt-3.md`
- Implementation / commit / push / merge / Batch 2 / custody edit / historical-receipt rewrite: **none**
- Reviewers commissioned this turn: **zero** (exactly one independent GPT-5.6 Luna full review already satisfied; no fan-out, helper, or second review)
- Isolated Oracle probe root: `/tmp/oracle-nbf01-rework3-grok/`
- Isolated Luna transcript root (already completed): `/tmp/oracle-nbf01-rework3-luna/`

## Bound identities

| Artifact | SHA-256 / git identity |
| --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| `.oracle/receipts/model-policy-grok-switch.md` | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Attempt-1 rework tasklist | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-2 rework tasklist | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-3 rework tasklist | `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779` |
| Attempt-3 triage receipt | `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b` |
| Gate brief `.oracle/briefs/oracle-nbf01-rework3-grok.md` | `5b062d0ded7552ce01bb7b4a7231a349419102a219c967c9a05cfbf46f2fdc01` |
| Resume brief `.oracle/briefs/oracle-nbf01-rework3-grok-resume.md` | `c5c72d494a581852224a7c65a576fd0505ca91dffbf1284ac7772a27cd66dd3a` |
| Executor finding `.oracle/findings/execution-nbf01-rework3-luna.md` | `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f` |
| Executor receipt `.oracle/receipts/execution-nbf01-rework3-luna.md` | `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f` |
| Luna review brief | `a9210962bb5251585011256942c4c37795c1c444e22d43356eaf9a56a5cea911` |
| Luna review `.oracle/checkins/batch-1-rework3-luna.md` | `573ce524b0c348445c7a0d89ee2a391fc3386135c72a124d09678735e1d727bd` |
| Luna review receipt `.oracle/receipts/oracle-nbf01-rework3-luna.md` | `ad0e4e947a29dc796adf98ed40b04e26b92a6877d6457de98ab2ee3bf897a425` |
| Oracle check-in `.oracle/checkins/batch-1-rework3-grok.md` | `4bd93c1d24e55c1860add92abbce5c44c979c2d0b83dd63b1ceb798db783af02` |
| Immutable source base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Merge-base | `798c50619204010ed3f4297fbb57988fe9381924` |
| Owned tracked-production diff | `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8` |
| `incident/disposition.py` SHA-256 / git blob | `2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a` / `291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1` |
| Unchanged `test_incident_ledger.py` SHA-256 / git blob | `83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195` / `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93` |

## Independent Luna command transcripts

All under `/tmp/oracle-nbf01-rework3-luna/`. Empty-stream SHA-256 is `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Oracle independently rehashed every stream below; they match the isolated JSON transcripts.

| Transcript | Exit | stdout SHA-256 |
| --- | ---: | --- |
| `focused.json` | 0 | `b295944369c7307eae526dbb7f26489f657782bc8f7f7f104a1a5613ebfaaac3` |
| `legacy.json` | 0 | `6bf9fdef28e576401171fa27f28aed01180b01cf2c0864567bc6bc54d21d4f7b` |
| `tx_subset.json` | 0 | `a64d95de6a86d87df3375b0a5fdac47745385bc5dd0622308e19fcdee85dba09` |
| `provider_subset.json` | 0 | `808c3d14219287627b518671c7308d76b836ed617dc7d6e8e463ef82c4169e47` |
| `confirmation_subset.json` | 0 | `35c11cc3672b8bda3b90af5b09f81b95192b96e163255ff89c7c355117ee769d` |
| `compile.json` | 0 | empty |
| `diff_check.json` | 0 | empty |
| `broad.json` | 2 | `602e26d1aaada829260638a8e5c880caa4b0efa7366c8968a7c7df1e489fa096` |
| `collect_new.json` | 0 | `97d1c095a2cdb9587407637a79e5d35baf21a9dc0d1cffd3c742a5016b655c9d` |
| `collect_unchanged.json` | 0 | `208afccf84501ad84544173d54844085406ca307fdd52686e935328bd860c9b3` |
| `independent_probes.json` | 0 | `62fa6b24fdf1db5c4e2e098b757c227384d137d0a3384528c0769835f4e115c1` |
| `recovery_probes.json` | 0 | `89baff32ef176c411763c002b13d1740906510040c68f78013218c1cc9ec43b2` |
| `cli2_0.json` | 0 | `ca0439b771124a8d30d3a105ccf198a91654bd71341b841cd64f49a14e5f26d9` |
| `cli2_2_malformed.json` | 2 | empty |
| `cli2_2_schema.json` | 2 | empty |
| `cli2_3.json` | 3 | empty |
| `cli2_4.json` | 4 | empty |
| `cli2_5_missing.json` | 5 | empty |
| `cli2_5_expired.json` | 5 | empty |
| `cli2_5_same_replay.json` | 5 | empty |
| `cli2_5_distinct.json` | 5 | empty |

Focused observation: `112 passed in 15.31s`. Legacy observation: `78 passed in 1.47s`. Counts are observations, not targets.

Luna check-in/receipt transcribed `collect_unchanged.json` stdout as 63-hex `208afccf84501ad8455173d54844085406ca307fdd52686e935328bd860c9b3`. Oracle uses the independently recomputed 64-hex value above. That is a review-receipt transcription error, not a moving tree.

## Independent Oracle probe

`/tmp/oracle-nbf01-rework3-grok/independent_probes.json`

- cwd: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
- exit: 0
- stdout SHA-256: `0979b341b6f9e933210bed6e992f7dc946a3a09541951388a5f20c4bc343be83`
- stderr SHA-256: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- Result: named-style key-only forge **REJECTED**; coherent snapshot+hash forge **ACCEPTED** at `from_dict`, `append_changed_precondition`, and `consume_changed_precondition`; worker+success constructor **REJECTED**; unofficial alias absent.

Owned untracked/modified production and test SHA-256 independently captured this turn:

| Path | SHA-256 | git hash-object |
| --- | --- | --- |
| `incident/ledger.py` | `a70d43e8a30b55c863b0f222cd80025454a1a3c5bd53a18a1b8fbb19d15191d6` | `fa873198e87edae215a29d1638fc7c81c6a0a4da` |
| `incident/schema.py` | `289aea2e2be803c71b82d7f82db3d3f0fefe43809b181613abe22ab3d3a78a25` | `55c3ef49c4f046c0c219fade58c3a40392b8102f` |
| `incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | — |
| `orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `test_changed_precondition_producers.py` | `5af03e900f4f87c28d761120d3a081761b9584ae58abca563df0e51587f25042` | `21377b6ddaf148bba584240104bde7251e7916da` |
| `test_incident_ledger_transactions.py` | `54a3bbdcb029da6ca31e094742522636c492c1479532eba7b0a9c31409412342` | `2e9e9556dc81777fe1518b51d3a7ea135d77ef79` |
| `test_provider_route_projection.py` | `0ae06f36637368a4963bbd7f43233e6c3748e1d179202ee6e4b0c612c340eeb2` | `3ebfc3516a5a0fe62e6fd4ccb0b33472ac54d99a` |
| `test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `test_supervision_confirmation.py` | `110de06726862b86e754347b749a5460f79bc48b1abfa8c7ca10e16794b54034` | `b0d12ac92201438c45bc990cd7b3cbfc8052c22e` |
| `test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `test_worker_disposition.py` | `bad693168f9e31b4c864b7ac0cb72cf24319f5bed2ad82286115a7a991ac7471` | `ce1aa1213e46cb6dab3c0a1f90f2fcc535b8c197` |

## Disposition summary

C03–C08, C10, C12, C14–C18, C22, C25, C26 shape, C27, C29–C31, C35–C38, C41, CP01 pytest, CP04 journal count, CP05 increment rule, CP09 type/state, CP10, RW3-05, RW-CUSTODY, A3-01, A3-09: **MET**.

C02, C09, C11, C19–C21, C23, C24, C28, C32–C34, C39, CP02/CP03/CP06–CP08/CP11, RW3-01..RW3-04, RW3-06, A3-02..A3-08: **NOT_MET**.

C01, C13, C40: **UNEVIDENCED**.

Broad-suite collection failures: **PRE_EXISTING_OUT_OF_SCOPE_BLOCKER**.

North Star one-door / anti-pattern “identical-fingerprint redispatch”: **NOT_MET** for the Batch 1 primitive because coherent forged changed-preconditions still append and consume. Scope/YAGNI/later-batch absence: **MET**. KISS quality and ceremonial validation: **NOT_MET**.

Custody/history: `f8725af…` remains historical; `798c506…` remains current; 52→61, `4aee815d…`, `50c86490…`, attempt-1 `e060f650…`, attempt-2 `16f6f854…` remain historical observations.

Reviewer count: **exactly one**.

## Integrity statement

This Oracle read the required North Star, agent goal, frozen tasklist, freeze receipt, all three rework tasklists, all three triage receipts, original and rework-1/2 Batch 1 check-ins, model-policy receipt, attempt-3 executor finding/receipt, and the completed Luna review/check-in/receipt. Independently re-hashed frozen identities, the owned production diff, owned untracked files, and Luna isolated transcripts; re-read the cited schema/ledger/test symbols; and independently reproduced the coherent-forgery probe including consume. This turn wrote only the two Oracle output files. The candidate source/test tree was not mutated. Historical evidence was not rewritten.

## Terminal decision

```text
ACCEPTED_ISSUES
```
