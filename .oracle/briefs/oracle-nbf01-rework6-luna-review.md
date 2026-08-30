# Independent Batch 1 rework-6 review — NBF-01 (GPT-5.6 Luna)

You are the **independent Batch 1 rework-6 reviewer**, not the executor and not
the Oracle. You are GPT-5.6 Luna at high reasoning. Your job is one complete,
evidence-cited full review of the post-attempt-6 NBF-01 candidate against the
frozen contract and the supplemental attempt-6 rework packet. This is not a
smoke-test rerun and not a restatement of the executor narrative. Do not reuse
any attempt-1 through attempt-5 command transcript, probe, ledger root, or
conclusion as current evidence. Attempt-5 and earlier artifacts are historical
context only, except where this brief requires you to prove that the named
tests fail on the attempt-5 candidate for the old gap.

Do not implement, repair, stage, commit, push, merge, rebase, reset, clean, or
edit production, test, plan, frozen tasklist, North Star, custody, historical
Batch-1 / attempt-1 through attempt-5 receipts/findings/check-ins, the attempt-6
packet, executor finding/receipt, or any other rework packet. Do not start
Batch 2. Do not fan out a second review. Do not self-issue `PASS_BATCH_1` or
`ACCEPTED_ISSUES`. Those Oracle tokens are reserved for Grok. Your binary
recommendation tokens are only `RECOMMEND_PASS_BATCH_1` or
`RECOMMEND_ACCEPTED_ISSUES`.

Worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
Branch: `megado-nbf-guard-0826`
Python: prefer `PYENV_VERSION=3.11.11 python` or the repo venv if present.
Write pytest/CLI/probe transcripts only under `/tmp/oracle-nbf01-rework6-luna-review/`.
Temporary probes and ledgers must live under that isolated root or a fresh
temporary child path, never in the repository. Do not overwrite the executor
transcripts already at `/tmp/oracle-nbf01-rework6-luna/` or any earlier review
or executor directories.
The only worktree writes authorized are the two output files named below.

## Complete North Star (mandatory; judge alignment explicitly)

# North Star — Arnold self-healing supervision

**End state:** An agent harness where no worker can be launched onto a spec that
isn't live, a box that won't survive it, or a seed bound to the wrong interpreter —
and where every worker death carries its killer's identity in a typed record that
the recovery loop consumes before it ever retries the same fingerprint.

**Enduring principles**
- One door per invariant: admission, dispatch, and death are each enforced at
  exactly one place; duplicate preflights are deleted, not patched around.
- Deaths speak: SIGKILL, timeout, terminate, restack — every termination emits
  `{killer, signal, elapsed_s}` into the failure ledger. Silent death is a bug.
- Models are admitted, not assumed: a model id must resolve against catalog,
  prefix map, family classifier, and live provider membership at dispatch time,
  typedly rejecting expired or unknown ids.
- Fixes ship on main through the fixer contract; hotfixes that live only as
  deployed-but-uncommitted files do not exist.

**Anti-patterns to avoid**
- Single-scan verdicts treated as sustained truth (wedge kills, restacks).
- Anonymous integer exit codes where a disposition belongs.
- Judgment-based "healthy" claims without positive proof (live pid + advancing seq).
- Redispatch of an identical failure fingerprint without a changed precondition.

**Aligned progress feels like:** fewer incident classes over time, each new stall
arriving with evidence attached and leaving with a root fix on main.

Advance that end state without widening `.oracle/agent_goal.md`. Critique for
elegance: KISS, YAGNI, cut scope that isn't pulling its weight; flag
overengineering, not just bugs. Explicitly assess one door per invariant, typed
deaths/evidence, live admission boundaries as deferred scope, and no
identical-fingerprint redispatch without changed precondition. Flag incidental
test proof, duplicate preflights, speculative authority/framework machinery,
second stores, and any unnecessary production surface.

## Independence and source identity

Evaluate the candidate actually on disk, not the executor narrative.

Oracle independently verified these identities immediately before this brief.
Re-verify each with `shasum -a 256` / `git rev-parse` / `git hash-object`. A
mismatch is an evidence-integrity issue, not permission to continue as if bound.

| Artifact | Expected identity |
| --- | --- |
| Repository | `/Users/peteromalley/Documents/Arnold-oracle-nbf` |
| Candidate branch | `megado-nbf-guard-0826` |
| Candidate HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Source and merge-base | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| `.oracle/custody.md` | `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |
| `.oracle/agent_goal.md` | `2299daefc4b48f361baf5dbe3811d935fe25b5a44adc66bb14b2fbff5a158864` |
| Model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Tasklist freeze v8 receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |
| Attempt-6 packet `.oracle/rework/batch-1-attempt-6.md` | `b776d6cc5b090fb4cbb278ec5fff265cb5cf92896c22c0fe0fed066713609b83` |
| Attempt-6 triage receipt | `88a0c2b76663cf63a32129296a74a610d01a4bedf66aef04dbaec570979bbcc8` |
| Attempt-6 execution brief | `c193077b92f94b55e3dc8f4bf3353ec5318e7e745d0e6aff950c373472e96fb6` |
| Attempt-6 executor finding | `a28a0ff726cccbc00806a44c7f8c7d305019491cf37656b6ad91769250806c44` |
| Attempt-6 executor receipt | `48d3988675ad1002000f193b915470391c83632bfc815fff2c35d8bd50a937e6` |
| Attempt-6 production diff SHA-256 | `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e` |
| Attempt-6 completion manifest SHA-256 | `c602969e318ca705f240cd1fcd90c2017f791110d92c7f163378852d0648b2ef` |
| Attempt-5 production baseline SHA-256 | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` |

Attempt-5 gate context, immutable and ending in `ACCEPTED_ISSUES` (label
historical; verify hashes only as context; do not treat as current proof):

| Historical artifact | SHA-256 |
| --- | --- |
| Attempt-5 Luna check-in | `670dbde42ab483ac36e08f2d1222d83b80a42248c6036d47cbeb77459649a8a6` |
| Attempt-5 Luna receipt | `4d96b1922cb6dca3b79c5d414092cb0407f49c32c95236e54fb08530994cc143` |
| Attempt-5 Grok check-in | `49c7bb1e94f828536be0800372d06aca55388667730870e1d5ee7e0efdf42aa6` |
| Attempt-5 Grok receipt | `537225951f608611b290c413a8e133a1a897f911c3ee49be9f13ea3bd03670ef` |
| Attempt-5 packet | `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7` |
| Attempt-5 triage receipt | `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a` |
| Attempt-5 execution brief | `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a` |
| Attempt-5 executor finding | `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197` |
| Attempt-5 executor receipt | `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160` |
| Attempt-5 production diff | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` |

Historical attempt-4 accepted-issues context (label historical):

| Historical artifact | SHA-256 |
| --- | --- |
| Attempt-4 Luna check-in | `01b8f596c33342fd3529f3982c9bba2605cd3fa41c44d36a0091b3dd8330972c` |
| Attempt-4 Luna receipt | `de0c6265e58a477b120f944740d5b88ba1834347ae3829d3def4517922e345ee` |
| Attempt-4 Grok check-in | `81a0018acd1d61835988bcc623d265376ec2a3ec8cac8634a902199b750936cf` |
| Attempt-4 Grok receipt | `dfba88485d5e101e86aaec541131a22312bbebe1b910b90455c53545fe90a607` |
| Attempt-4 packet | `4df7024a285e3d0c373278dbd72aed98a0d5af26b05f1f880cf64e9f20a2d534` |
| Attempt-4 triage receipt | `3d20f7bc585e5b5495a38b7a2a26caf1050c90f6dc14f719a95d3203516cfa2c` |
| Attempt-4 executor finding | `b277eced2d19b92a1a70a5496c40a75a19fc7e14aa116678dfad865aeef4d6c1` |
| Attempt-4 executor receipt | `8739b5ebf73d2d4bdb9d9c089e7da80b3005f230794c0fe2fae306428f1a247f` |
| Attempt-4 production diff | `aaaa86ba2de9775df83d9a35f561b5fdcb8428a448f3e561937f00edf85a6e41` |

Historical attempt-1/2/3 context remains historical and must stay labeled
historical:

- start-gate 52→61 observation
- unreproducible `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`
- failed-handoff `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`
- attempt-1 78/78 and `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`
- attempt-2 production digest `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`
- attempt-3 production digest `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`

Executor claimed post-attempt-6 tracked production diff digest (must independently
reproduce with the exact command below):

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/disposition.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Claimed output: `ab2b9cb2743a2cc9d73e0f5cbffb650a313da60833500217dd7db5aa13e2bd2e`

Also reproduce the five-file tracked-production command used historically:

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Oracle independently hashed every owned production/test file immediately before
this brief. If the tree you inspect differs, stop and recommend
`RECOMMEND_ACCEPTED_ISSUES` for a moving candidate; do not silently review a
different tree.

| Owned file | SHA-256 | git blob |
| --- | --- | --- |
| `incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `incident/ledger.py` | `5506175a236792607aee13a0adc403e536d3c2076c391391cc9ed3f1fbe317f9` | `192f68694ad7cd29c1d28f74539fc7b9f2a82734` |
| `incident/schema.py` | `8acb8563adac794d3dc66e39d8db1d12d499207cb5e1b297a395c0a14f640a9d` | `032162bf0efc7b8e14414cd7d6b0738bdf83a613` |
| `orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `incident/disposition.py` | `8edad79ca55a3e999ab325158f7ce4f2c247b8f9698b4f2677b1c05d57512cf5` | `74d640b20fe1b4c8edc58cbafd5d3d5756712ec3` |
| `test_changed_precondition_producers.py` | `89b6e14ea7a1180b9c809cbae0d29d1461806f4a02254b6fa4a992594e67a215` | `0773a0f629712065d4f410502b316155f4b8cf89` |
| `test_incident_ledger_transactions.py` | `118f174629869fb9aa4a7dbe6cfa127d317d71f2bfb90b10dcdbd353e7e837f8` | `c91963087ae35fce9f50ae322663825e4642bb59` |
| `test_provider_route_projection.py` | `6d036f349fa14cf31f585996ca67033aeaa7b131b591958dcde1632cb656a949` | `6de73b1e16d59ade8c22c5428dfdad5b660b072c` |
| `test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `test_supervision_confirmation.py` | `cc3648f366d4ed884f93de426182df3bcbd5f5146628fec0e80c36a68074f50c` | `2a5a3a88cbae92d69260c93525246846adeb3547` |
| `test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `test_worker_disposition.py` | `20f60bc664bebe59d9c50a19b6a4fb389cfa4ea54c101bfef6d138f05750aa41` | `59d6ae5a39659fd5858ba10991b702f0396a8cb0` |

`tests/arnold_pipelines/megaplan/test_incident_ledger.py` must remain unchanged
versus `origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`).

If any frozen identity mismatches, record it as an issue.

## Required reads (complete, not summaries)

Read every file completely before judging:

1. `.oracle/northstar.md`
2. `.oracle/agent_goal.md`
3. `.oracle/custody.md`
4. `.oracle/receipts/model-policy-grok-switch.md`
5. `.oracle/plan.md` — complete settled plan v8, especially §§4.4–4.13, §4.16,
   §§4.19–4.21
6. `.oracle/tasklist.md` — complete NBF-01 section, frozen dispatch/terminal
   semantics, Batch 1 checkpoint
7. `.oracle/receipts/tasklist-freeze-v8.md`
8. `.oracle/rework/batch-1-attempt-6.md` (current packet)
9. `.oracle/receipts/rework-triage-batch-1-attempt-6-grok.md`
10. Attempt-6 executor finding and receipt bound above
11. Historical attempt-5 Luna/Grok check-ins/receipts labeled historical
12. Every owned production and test file listed below

Do not treat the executor receipt as proof. Reproduce the diff, named tests,
CLI statuses, required behavioral names, and independent probes yourself under
`/tmp/oracle-nbf01-rework6-luna-review/`.

## Owned candidate paths (NBF-01 only)

Production (may be modified vs `origin/main`):

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
- `arnold_pipelines/megaplan/orchestration/phase_result_classify.py`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
- `arnold_pipelines/megaplan/incident/disposition.py` (new/untracked)
- `arnold_pipelines/megaplan/incident/__init__.py` (exports only; confirm no extra behavior)

Tests:

- `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
- `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`
- `tests/arnold_pipelines/megaplan/test_provider_route_projection.py`
- `tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py`
- `tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py`
- `tests/arnold_pipelines/megaplan/test_terminal_outcomes.py`
- `tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py`
- `tests/arnold_pipelines/megaplan/test_supervision_confirmation.py`
- existing `tests/arnold_pipelines/megaplan/test_incident_ledger.py` (must remain unchanged)

Any change outside this set, or any later-batch behavior inside it (admission
callers, scheduling loops, T7 waits, T8 thresholds/policy, physical-door
wiring, controlled launch execution, signal-site wiring, provider fallback
decisions, second journal/store/scheduler/rotator), is out of NBF-01 scope.

RW-CUSTODY is already MET. Do not edit `.oracle/custody.md`. Keep
`f8725af516da8d4249eb0d63563c37776d80daf8` historical and
`origin/main@798c50619204010ed3f4297fbb57988fe9381924` current.

## Serial scope to validate

The attempt-6 packet's serial scope is RW6-01, followed by this independent
review and a later Grok Oracle gate. Re-review **every** frozen NBF-01
criterion C01–C41 and checkpoint CP01–CP11, not merely RW6-01. Check that
prior-MET work was not regressed. A green aggregate count never substitutes
for a required behavioral door or complete evidence.

### RW6-01 / C02 / C13 — complete named four-door / six-kind matrix

This is the surviving attempt-5 issue. Verify the final named tests use
structurally complete `DispatchOutcome` and terminal records, not partial
dictionaries. Confirm every one of the six incompatible payload combinations
is exercised through:

1. direct construction;
2. `from_dict` decode;
3. `validate_nbf_event`; and
4. real public locked `append_terminal_outcome` and `append_disposition`.

Assert the intended payload-family error or scheduling-terminal error, not an
incidental missing-field/unknown-field failure. Confirm complete typed worker,
observed-death, and non-worker identity mismatch coverage at every applicable
door, including missing, fabricated, bare-string, wrong-version, incomplete,
wrong-type, non-positive PID, mismatched host/PID/boot identity, victim/killer,
subject/cause, and lifecycle cases. Confirm legal OOM, unknown-death,
non-worker, worker-disposition, no-launch, unresolved, success, ordinary, and
provider-positive records remain legal.

Do not accept a source-only probe as named proof. Ensure the tests fail on the
attempt-5 candidate for the old gap and pass on attempt 6. Confirm any
production change was strictly necessary for a correctly shaped case; reject
speculative validator changes or scope expansion.

Executor claimed one minimal production correction in
`ObservedProcessDeath.__post_init__`: `victim_identity_evidence` must be a
mapping. Independently confirm that this was required by a correctly shaped
case, that empty mappings retain the required-evidence rejection, and that no
other production seam changed.

Named tests to inspect in place:

- `test_dispatch_outcome_incompatible_payload_matrix`
- `test_incompatible_matrix_rejects_at_public_terminal_append`
- `test_typed_identity_matrix_rejects_missing_and_fabricated_worker_at_all_doors`
- `test_worker_disposition_rejects_success_payload_at_append`
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`

### Closed obligations that must remain closed

Recheck, without reopening or weakening:

- C19–C21/RW5-01 coherent changed-precondition forgery rejection at decode,
  validation, private/canonical append, projection, and `reserve()`, while a
  legitimate reason-specific reader still supports valid replay and consume
  once;
- C39/RW5-03 confirmation equality, including wrong/omitted evidence digest,
  restart, replacement, expiry, and one-consumer semantics;
- keyed provider streak and recovery/probe lease isolation;
- terminal linkage race, composite pre/post-append crash/reopen and replay;
- C41 CLI status 0/2/3/4/5 and typed dispositions;
- one journal/lock and all prior C/CP MET results.

Independently reproduce the prior coherent changed-precondition attack. Rebuild
all caller-visible serializable fields—including before/after snapshots,
content IDs, evidence digest, provider-failure keys, and event ID—then probe
`from_dict`, `validate_nbf_event`, canonical/private `_append_nbf` and locked
append, projection, and `reserve()` authorization. A coherent recomputation or
re-signing by an untrusted caller must not regain authority.

Independently test wrong and omitted `second_evidence`/`second_evidence_digest`,
not only PID/start/progress/incarnation/cause. Verify restart, replacement,
expiration, reopen, expiry-after-consume, and locked one-consumer semantics.
Re-run CLI statuses 0/2/3/4/5 only as a regression; do not redesign the CLI.

Do not reopen C36–C38, C01 overweight `PhaseResult.from_dict`, C40 cache
matrix, T8 policy, admission/scheduler/physical doors, signal/fallback/family
leases/rotators, broad missing modules, custody, historical evidence, second
store/journal/projection, or Batch 2. Any broad-suite missing-module result is
authoritative `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` context, not a waiver or
implementation issue; prefer no broad rerun unless a truly new in-scope reason
is documented.

## Capture the exact candidate

From the worktree root:

```bash
git rev-parse HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
git rev-parse --abbrev-ref HEAD
git status --short --branch
git ls-files --others --exclude-standard -- arnold_pipelines tests
```

Record every owned production/test SHA-256 and git blob. Reproduce the six-file
and five-file production diffs. Inventory `git diff --name-only origin/main --
arnold_pipelines tests` and confirm no later-batch source/test file entered.

## Exact validation commands

Use a fresh isolated evidence/transcript directory
`/tmp/oracle-nbf01-rework6-luna-review/`. Every command must record literal
argv, cwd, UTC start/end, exit status, complete stdout/stderr or immutable
transcript path, and full SHA-256 digests for each stream and structured
transcript. Empty streams must use
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.

Run from `/Users/peteromalley/Documents/Arnold-oracle-nbf`:

```bash
python -m pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py -k "incompatible_matrix or observed_and_non_worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_terminal_outcomes.py -k "append or disposition or worker"
python -m pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py tests/arnold_pipelines/megaplan/test_provider_route_projection.py tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py tests/arnold_pipelines/megaplan/test_scheduling_conditions.py tests/arnold_pipelines/megaplan/test_supervision_confirmation.py tests/arnold_pipelines/megaplan/test_terminal_outcomes.py tests/arnold_pipelines/megaplan/test_worker_disposition.py tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger.py
python -m pytest -q tests/arnold_pipelines/megaplan/test_incident_projection.py tests/arnold_pipelines/megaplan/test_incident_summaries.py tests/arnold_pipelines/megaplan/test_incident_bridge.py tests/arnold_pipelines/megaplan/test_phase_result_classify.py
python -m py_compile arnold_pipelines/megaplan/incident/__init__.py arnold_pipelines/megaplan/incident/ledger.py arnold_pipelines/megaplan/incident/schema.py arnold_pipelines/megaplan/incident/disposition.py arnold_pipelines/megaplan/orchestration/phase_result.py arnold_pipelines/megaplan/orchestration/phase_result_classify.py
git diff --check
```

Do **not** rerun `python -m pytest -q tests/arnold_pipelines/megaplan` unless a
truly new in-scope reason is documented. The attempt-6 packet already has an
authoritative pre-existing collection-blocker result. Do not repair or
reclassify its missing modules. If you do rerun C41 CLI, use the existing real
subprocess command and record all 0/2/3/4/5 cases without redesign.

Test counts are observations, not waivers or targets. Historical 52→61, 78/78,
123 passed, and the current focused count must remain labeled observations.

## Attempt-5 fail / attempt-6 pass proof

Prove the named tests fail on the attempt-5 candidate for the old gap and pass
on attempt 6. Isolate attempt-5 copies of `schema.py` and
`test_worker_disposition.py` under the review tmp root; do not mutate the live
candidate. Attempt-5 identities:

- `schema.py` SHA-256 `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1` blob `eedfad759321236ed217cc71943227a7cd122bca`
- `test_worker_disposition.py` SHA-256 `61d85e93036f00426a857136dc3ca10a01b233128b8984b0cc02b75dfaa28a84` blob `45b23313a67229de5d3bbb1c896ab7729b4d09da`

A source-only probe that the current validators reject illegal pairings is not
named proof. The named tests themselves must reach the intended payload-family
or identity errors.

## Independent probes required

Independently, not by quoting the executor:

1. Drive all six incompatible payload combinations through construction,
   `from_dict` of complete `to_dict()` records, `validate_nbf_event` of complete
   terminal records, public `append_terminal_outcome`, and public
   `append_disposition`. Record the exact error family per door.
2. Drive missing/fabricated/bare/wrong-version/incomplete/wrong-type/
   non-positive PID/mismatched host/PID/boot worker identities, plus
   observed-death victim/killer/subject/cause and non-worker lifecycle cases,
   at every applicable door.
3. Confirm legal OOM, unknown-death, non-worker, worker-disposition, no-launch,
   unresolved, success, ordinary, and provider-positive records remain legal.
4. Reproduce the coherent changed-precondition forgery at every RW5-01 door.
5. Reproduce confirmation evidence equality (wrong/omitted digest) and
   consume-once.
6. Confirm the production `schema.py` change is limited to typed mapping
   enforcement of `victim_identity_evidence` and is required by a correctly
   shaped observed-death case.

## Output files (exactly these two)

Write:

1. `.oracle/checkins/batch-1-rework6-luna.md`
2. `.oracle/receipts/oracle-nbf01-rework6-luna.md`

The check-in must begin with exactly `RECOMMEND_PASS_BATCH_1` or
`RECOMMEND_ACCEPTED_ISSUES`, then give candidate identity, independent
probes, full C01–C41 and CP01–CP11 dispositions, RW6-01 / RW5-01 / RW5-03
status, North Star/KISS/YAGNI assessment, preservation proof, and the
smallest next action if blocked. Do not issue Oracle tokens.

The receipt must contain full review commands/results, candidate and artifact
identities, exact transcripts/digests, model spec `codex:gpt-5.6-luna` at high
reasoning, launcher/cwd/UTC timestamps/exit, complete stdout/stderr/transcript
SHA-256s, and all criterion dispositions. State explicitly that no
production/test/plan/custody/history edit, commit, stage, push, merge, rebase,
reset, clean, Batch-2 start, or second review was performed.

## Criterion table required

Disposition every frozen C01–C41 and CP01–CP11 as `MET`, `NOT_MET`, or
`UNEVIDENCED` with evidence. Keep C01 and C40 `UNEVIDENCED` unless the packet
reopened them (it did not). Keep C36–C38 MET and not reopened. Test counts
never convert `NOT_MET` named-proof holes into `MET`.

## Integrity

Do not commit. Do not start Batch 2. Do not edit source or tests. Do not
rewrite historical artifacts. Do not fan out. One review, two files.
