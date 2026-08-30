# Independent Batch 1 rework-5 review — NBF-01 (GPT-5.6 Luna)

You are the **independent Batch 1 rework-5 reviewer**, not the executor and not
the Oracle. You are GPT-5.6 Luna at high reasoning. Your job is one complete,
evidence-cited full review of the post-attempt-5 NBF-01 candidate against the
frozen contract and the supplemental attempt-5 rework packet. This is not a
smoke-test rerun and not a restatement of the executor narrative. Do not reuse
any attempt-1, attempt-2, attempt-3, or attempt-4 command transcript, probe,
ledger root, or conclusion as current evidence. Attempt-4 and earlier artifacts
are historical context only.

Do not implement, repair, stage, commit, push, merge, rebase, reset, clean, or
edit production, test, plan, frozen tasklist, North Star, custody, historical
Batch-1 / attempt-1 / attempt-2 / attempt-3 / attempt-4 receipts/findings/
check-ins, or any rework packet. Do not start Batch 2. Do not fan out a second
review. Do not self-issue `PASS_BATCH_1` or `ACCEPTED_ISSUES`. Those Oracle
tokens are reserved for Grok. Your binary recommendation tokens are only
`RECOMMEND_PASS_BATCH_1` or `RECOMMEND_ACCEPTED_ISSUES`.

Worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
Branch: `megado-nbf-guard-0826`
Python: prefer `PYENV_VERSION=3.11.11 python` or the repo venv if present.
Write pytest/CLI/probe transcripts only under `/tmp/oracle-nbf01-rework5-luna-review/`.
Temporary probes and ledgers must live under that isolated root or a fresh
temporary child path, never in the repository. Do not overwrite the executor
transcripts already at `/tmp/oracle-nbf01-rework5-luna/` or any attempt-4
review/executor directories.
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
overengineering, not just bugs.

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
| Attempt-5 packet `.oracle/rework/batch-1-attempt-5.md` | `f2c2224d6b46eda303b1768a4a2e520fc08224eef9c93e506daa14ea3b2042d7` |
| Attempt-5 triage receipt | `dedf5870dc889b137484202290925482b4813a742414233dc83ecd7c5fa18b5a` |
| Attempt-5 execution brief | `78db1ef340df0dd87e8ab40ee31aa801eb163008ec7deb1247efdbefe343f13a` |
| Attempt-5 executor finding | `8cf68b20bb089f98639787c6aa1ad23d1ad24701843d802c4f79aa67eb77c197` |
| Attempt-5 executor receipt | `4acbb75c4bc9526265bf14438d194288bdf4aaf79cc63525f729830c6f93f160` |
| Post-attempt-5 production diff SHA-256 | `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411` |

Historical attempt-4 accepted-issues context (label historical; verify hashes
only as context; do not treat as current proof):

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

Executor claimed post-attempt-5 tracked production diff digest (must independently
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

Claimed output: `7b46da5cdc7f030c45a5775bad2951281cf8e3597835e18c15500e084414e411`

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
| `incident/schema.py` | `5c150cdc5a55769a209f216ea7954831f76f8aae64606bf36a14a003312a27b1` | `eedfad759321236ed217cc71943227a7cd122bca` |
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
| `test_worker_disposition.py` | `61d85e93036f00426a857136dc3ca10a01b233128b8984b0cc02b75dfaa28a84` | `45b23313a67229de5d3bbb1c896ab7729b4d09da` |

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
8. `.oracle/rework/batch-1-attempt-5.md` (current packet)
9. `.oracle/receipts/rework-triage-batch-1-attempt-5-grok.md`
10. Attempt-5 executor finding and receipt bound above
11. Historical attempt-4 Luna/Grok check-ins/receipts labeled historical
12. Every owned production and test file listed below

Do not treat the executor receipt as proof. Reproduce the diff, named tests,
CLI statuses, required behavioral names, and independent probes yourself under
`/tmp/oracle-nbf01-rework5-luna-review/`.

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

The attempt-5 packet's serial scope is RW5-01 → RW5-02 → RW5-03, followed by
this independent review and a later Grok Oracle gate. Re-review **every**
frozen NBF-01 criterion C01–C41 and checkpoint CP01–CP11, not merely the three
attempt-5 obligations. Check that prior-MET work was not regressed. A green
aggregate count never substitutes for a required behavioral door or complete
evidence.

### RW5-01 / C19–C21 / RW4-01 / A3-03 — authority closure

Independently reproduce the prior coherent changed-precondition attack. Rebuild
all caller-visible serializable fields—including before/after snapshots,
content IDs, evidence digest, provider-failure keys, and event ID—then probe
`from_dict`, `validate_nbf_event`, canonical/private `_append_nbf` and locked
append, projection, and `reserve()` authorization. A coherent recomputation or
re-signing by an untrusted caller must not regain authority. Confirm that:

- every allowlisted reason-specific producer requires its typed authoritative
  source handle/reader;
- producer identity, reason, subject, source version, cited persisted evidence,
  evidence digest, canonical before/after content, and provider-key derivation
  are bound at every relevant decode/append/consume door;
- forged events neither persist/project nor authorize reservation;
- valid reason-specific reader events still append, project, replay as required,
  and consume exactly once under the existing journal lock.

This is the primary security gate. Reject content-address self-consistency as
proof of provenance. Verify no second authority store, signing framework,
generic bypass, or second journal was introduced.

### RW5-02 / C02/C13 / RW4-02 / A3-02 — complete matrix

Verify the existing named behavioral tests cover all six incompatible
outcome/payload kinds through direct construction, `from_dict`,
`validate_nbf_event`, and real public locked append doors, including public
`append_terminal_outcome` and `append_disposition`, rather than only a private
append or one worker-success pairing. Verify missing/fabricated typed worker,
observed-death, and non-worker identities at each applicable door, while legal
OOM, unknown-death, and non-worker positive paths remain valid. Confirm no
overweight C01 `PhaseResult.from_dict` expansion was smuggled in.

### RW5-03 / C39 / RW4-05 / A3-07 — confirmation evidence equality

Verify every required confirmation identity, timing, evidence, TTL/expiry,
scan separation, policy, and version field is persisted and compared. In
particular, independently test wrong and omitted `second_evidence`/
`second_evidence_digest`, not only PID/start/progress/incarnation/cause. Verify
restart, replacement, expiration, reopen, expiry-after-consume, and locked
one-consumer semantics remain intact. Re-run CLI statuses 0/2/3/4/5 only as a
regression; do not redesign the CLI.

### Preserved Batch-1 invariants and scope

Check keyed provider streak/recovery/probe lease behavior, non-latest key
isolation, terminal linkage race, post-append and pre-append composite crash
recovery, deterministic replay, one journal/lock, typed dispositions, no-launch
and unresolved distinctions, route-child wrapper deletion, and all prior-MET
C/CP behavior. Verify no admission/scheduler/physical-door/signal/T8/fallback/
family-lease/rotator/policy work entered the candidate. Broad missing-module
collection failures remain `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only if absent
on candidate and source; they are not a waiver or triage issue.

Do not reopen C36–C38, overweight C01, expand C40, or pursue T8 policy,
environment repair, custody/history/admission/scheduler/physical-door/launch,
signal, fallback, or other excluded work.

## Capture the exact candidate

From the worktree root:

```bash
git rev-parse HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
git status --porcelain=v1
git diff --name-status origin/main -- arnold_pipelines tests
git ls-files --others --exclude-standard -- arnold_pipelines tests
```

Record SHA-256 of the exact production diff command above and of each owned
untracked file. Record changed-file scope. Unrelated dirty `.oracle` planning
artifacts are not Batch 1 acceptance evidence; note them only as non-owned
noise. Do not claim a clean tree by ignoring protected artifacts.

If source or tests differ from the Oracle-bound hashes above, do not silently
review a moving tree: recommend `RECOMMEND_ACCEPTED_ISSUES` and require fresh
executor evidence for the exact tree.

## Reproduce every named command (necessary, not sufficient)

Write transcripts to `/tmp/oracle-nbf01-rework5-luna-review/` only. Record full
argv, cwd, exit status, verbatim stdout and stderr, and SHA-256 of stdout bytes
and stderr bytes for each. Do not abbreviate pytest output to a count. Empty
stdout/stderr SHA-256, when truly empty, is the full 64-hex
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
Never truncate it.

Focused (frozen nine-module command):

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  tests/arnold_pipelines/megaplan/test_reservation_reconciliation.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py \
  tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

Legacy:

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_incident_projection.py \
  tests/arnold_pipelines/megaplan/test_incident_summaries.py \
  tests/arnold_pipelines/megaplan/test_incident_bridge.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py
```

Packet-required subsets (reproduce independently; do not reuse executor
transcripts as your transcripts):

```bash
pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py
pytest -q tests/arnold_pipelines/megaplan/test_changed_precondition_producers.py \
  -k "coherent_forged or valid_reason_specific_source_reader or forged or producer or authoritative"
pytest -q tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_terminal_outcomes.py
pytest -q tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  -k "incompatible_payload or observed_and_non_worker or legal_positive_oom or legal_unknown_death or worker_disposition_rejects_success"
pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py
pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py::test_confirmation_compares_pid_start_progress_incarnation_cause
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention"
```

Compile and whitespace:

```bash
python -m py_compile \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/disposition.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py
git diff --check
```

Required broad sweep exactly once:

```bash
pytest -q tests/arnold_pipelines/megaplan
```

Preserve its complete collection output. Classify absent
`arnold.agent.costing.model_resource_capabilities` and
`tools.environments.singularity` imports as
`PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` only if independently confirmed absent at
candidate and source. Do not repair them.

Independently re-run CLI statuses 0/2/3/4/5, including expired and already-consumed
matching replay, as separate subprocesses of:

```bash
python -m arnold_pipelines.megaplan.incident.disposition record --ledger-root <root> --json-stdin
```

Record exact payload, ledger root, argv, status, stdout/stderr, and stream
digests. Status 0 must emit one JSON acknowledgement on stdout and diagnostics
only on stderr for failures. Do not signal from the CLI and do not redesign it.

## Independent probes (required)

Do not treat green tests as proof of the three attempt-5 holes. Independently
probe at least:

1. **Coherent changed-precondition attack.** Mint a valid reason-specific
   reader event, copy `to_dict()`, mutate before/after snapshots and both
   provider keys, recompute every serializable hash/ID (`before_content_id`,
   `after_content_id`, `evidence_digest`, `provider_failure_key_*`, `event_id`),
   then call `from_dict`, `validate_nbf_event`, `_append_nbf`,
   `_append_nbf_locked` if reachable, projection, and `reserve()`. Record
   accept/reject at each door. A forged event must neither persist nor
   authorize reservation. A valid reader event must still append, project,
   replay, and consume once.

2. **Six-kind four-door payload matrix.** For all six incompatible
   outcome/payload kinds, independently construct and send through
   construction, `from_dict`, `validate_nbf_event`, and public
   `append_terminal_outcome` / `append_disposition`. Also probe missing and
   fabricated typed worker / observed-death / non-worker identities at each
   applicable door. Confirm legal OOM, unknown-death, and non-worker positives
   remain valid.

3. **Confirmation evidence equality.** Independently mutate or omit
   `second_evidence` / `second_evidence_digest` and prove rejection, while
   matching evidence still consumes once. Confirm restart/replacement/
   expiration/reopen/expiry-after-consume/locked one-consumer remain intact.

Write probe transcripts as JSON under the isolated review root, with complete
stdout/stderr SHA-256.

## Criterion classification contract

Classify every C01–C41 and CP01–CP11 as `MET` | `NOT_MET` | `UNEVIDENCED` with
source and behavioral evidence. Also classify RW5-01, RW5-02, RW5-03, RW4-01
through RW4-06 (historical), A3-01 through A3-09, and RW-CUSTODY.

C01 and C40 remain unevidenced context unless this candidate independently
closes them without overweight expansion. Do not expand them. Do not treat
green 123/78 as a waiver.

## Required outputs

Write exactly these two files and no others in the worktree:

- `.oracle/checkins/batch-1-rework5-luna.md`
- `.oracle/receipts/oracle-nbf01-rework5-luna.md`

The check-in must contain:

- model, date, identities, production diff, isolated transcript root
- owned-file SHA-256 inventory
- independent command transcripts with exact argv, cwd, exit, stdout SHA-256,
  stderr SHA-256
- independent CLI matrix
- complete C01–C41, CP01–CP11, RW5, RW4 historical, and A3 tables
- independent probe results for RW5-01/RW5-02/RW5-03
- broad-suite classification
- preserved prior-MET result
- North Star alignment
- KISS/YAGNI/scope assessment
- residual issues if any
- final recommendation token `RECOMMEND_PASS_BATCH_1` or
  `RECOMMEND_ACCEPTED_ISSUES`

Do **not** put `PASS_BATCH_1` or `ACCEPTED_ISSUES` in the Luna check-in.

The receipt must contain complete path/hash inventories, candidate
HEAD/source/tasklist/North Star identities, production diff identity, actual
model/commands/timestamps/exit statuses, full transcript and separate
stdout/stderr digests, exact test commands/results, and any broad collection
blocker classification.

Capture actual model specification and reasoning level, launcher command if
known, UTC timestamps, cwd, exit status, complete transcript paths, and full
stdout/stderr/transcript SHA-256 digests. Validate all output paths and hashes
after writing.

Do not commit. Do not start Batch 2.
