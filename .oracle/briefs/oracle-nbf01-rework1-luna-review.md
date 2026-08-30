# Independent Batch 1 rework review — NBF-01 (GPT-5.6 Luna)

You are the **independent Batch 1 rework reviewer**, not the executor and not
the Oracle. You are GPT-5.6 Luna. Your job is one complete, evidence-cited
full re-review of the post-rework NBF-01 candidate against the frozen contract
and the supplemental rework tasklist. This is not a smoke-test rerun.

Do not implement, repair, stage, commit, push, merge, rebase, reset, clean, or
edit production, test, plan, frozen tasklist, North Star, custody, historical
Batch-1 receipts/findings/check-ins, or the rework tasklist. Do not start
Batch 2. Do not fan out a second review. Do not self-issue `PASS_BATCH_1`.

Worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
Branch: `megado-nbf-guard-0826`
Python: prefer `PYENV_VERSION=3.11.11 python` or the repo venv if present.
Write pytest/CLI transcripts only under `/tmp/oracle-nbf01-rework1-luna/`.
The only worktree writes authorized are the two output files named below.

## Independence and source identity

Evaluate the candidate actually on disk, not the executor narrative.

Known identities to independently re-verify with `shasum -a 256` / `git rev-parse`:

| Artifact | Expected identity |
| --- | --- |
| `.oracle/northstar.md` | `d75f89f043603b75425096e1c45ef8e11386fa1e5652d752aac64c373c77dd7e` |
| `.oracle/plan.md` (settled v8) | `0ec216cca92a6f99f7d73e78494a46f8acb08e22c506a58948640ea2c57421e1` |
| `.oracle/tasklist.md` (frozen) | `9d206c8ff7d524f7b1247d4879dc3a1a32b0b0d953b49bc57ffe1aee68411589` |
| Immutable source | `origin/main@798c50619204010ed3f4297fbb57988fe9381924` |
| Candidate branch | `megado-nbf-guard-0826` |
| Planning HEAD | `922241d0bdb3e993c3b554cc69f19948adef7bc3` |
| Rework tasklist `.oracle/rework/batch-1-attempt-1.md` | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Prior Batch-1 Luna check-in | `7d19a34bc086df1d383d8083ed07f6214151ec55d3b3317609c4506a7af1ede7` |
| Prior Batch-1 Grok check-in | `916356111c7882e23f00df2bc50d92e533329895760aca3b890d6771fc1c4514` |
| Executor rework receipt | `.oracle/receipts/execution-nbf01-rework1-luna.md` |
| Executor rework findings | `.oracle/findings/execution-nbf01-rework1-luna.md` |
| Custody worker receipt | `.oracle/receipts/rework-nbf01-custody-luna.md` expected SHA-256 `48f540c4bec63ab17949b7a004395057be887f5dc9623cd87832be20ee375cb9` |
| Current custody.md | expected SHA-256 `94df44cca56a51502d8a6ef9d5e99f2f482bda2f6f2cbbc876d234a8fa78d5a0` |

Executor claimed post-rework production diff digest (must independently reproduce):

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Claimed output: `e060f650e112ecc8c73f4f2491e8504f3a1f1c9943b80f4e5aa97590b2925801`

Also independently `git hash-object` and `shasum -a 256` every owned untracked file listed in the executor finding. A mismatch is an evidence-integrity issue, not permission to continue as if bound.

Do not rewrite historical evidence. Preserve as historical:

- Original start-gate receipt claimed focused **52** passed, later mutated on the same path to **61**.
- Unreproducible owned-source digest `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`.
- Prior independent Luna reproduction: focused **61** / legacy **78**, and historical failed-handoff digest `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`.
- Current focused count is an observation, not a target.

If any frozen identity mismatches, record it as an issue.

## Required reads (complete, not summaries)

Read every file completely before judging:

1. `.oracle/northstar.md`
2. `.oracle/agent_goal.md`
3. `.oracle/receipts/model-policy-grok-switch.md`
4. `.oracle/plan.md` — complete settled plan v8, especially §§4.4–4.13, §4.16, §§4.19–4.21
5. `.oracle/tasklist.md` — complete NBF-01 section, frozen dispatch/terminal semantics, Batch 1 checkpoint
6. `.oracle/rework/batch-1-attempt-1.md` — entire supplemental rework tasklist
7. `.oracle/checkins/batch-1-luna.md` and `.oracle/checkins/batch-1-grok.md`
8. `.oracle/receipts/execution-nbf01-luna.md` and `.oracle/findings/execution-nbf01-luna.md` (historical)
9. `.oracle/receipts/execution-nbf01-rework1-luna.md` and `.oracle/findings/execution-nbf01-rework1-luna.md`
10. `.oracle/receipts/rework-nbf01-custody-luna.md` and `.oracle/custody.md`
11. `.oracle/receipts/rework-triage-batch-1-attempt-1-grok.md`
12. Every owned production and test file listed below

Do not treat the executor receipt as proof. Reproduce the diff, named tests, CLI statuses, and required behavioral names yourself.

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

RW-CUSTODY may have edited `.oracle/custody.md` only to label `f8725af...`
historical and keep `798c506...` current.

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

## Reproduce every named command (necessary, not sufficient)

Write transcripts to `/tmp/oracle-nbf01-rework1-luna/` only. Record full argv,
cwd, exit status, verbatim summary, and SHA-256 of stdout bytes for each.

Focused (frozen):

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

Adversarial / named subsets:

```bash
pytest -q tests/arnold_pipelines/megaplan/test_incident_ledger_transactions.py \
  -k "two_process or torn or crash or contention"
pytest -q tests/arnold_pipelines/megaplan/test_provider_route_projection.py \
  -k "replay or receipt or keyed"
pytest -q tests/arnold_pipelines/megaplan/test_supervision_confirmation.py \
  -k "cli or confirmation or incarnation or reopen"
```

Compile and whitespace:

```bash
python -m py_compile \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/disposition.py
git diff --check
```

CLI via `python -m arnold_pipelines.megaplan.incident.disposition record`
for statuses **0, 2, 3, 4, 5**. Status 0 must emit one JSON acknowledgement on
stdout and must not signal. Status 4 must be a real invalid/unavailable
ledger-location branch, not collapsed into 3. Status 5 must cover missing and
already-consumed confirmation.

A green pytest run is **necessary but not sufficient**. If tests are thin,
vacuous, sequential-only, malformed-only, or do not cover a frozen criterion,
that criterion is `NOT_MET` or `UNEVIDENCED` even if pytest is green.

Read every new test module completely. Count collected tests. State how many
are new vs unchanged `test_incident_ledger.py`. Check that each required
behavioral name below exists **and actually exercises the named hole** (not a
renamed happy-path stub). Sequential-only contention is not two-process CAS.
A forged-ID test that mutates a hash to `"x"` is malformed-length coverage
only.

## Required named behavioral tests (must exist and be real)

RW-01:

- `test_two_process_reservation_contention_one_winner`
- `test_two_process_terminal_linkage_is_atomic`
- `test_terminal_rejects_reservation_context_mismatch`
- `test_blind_release_and_accepted_launch_release_reject`
- `test_recovered_disposition_links_existing_record_without_duplicate`
- `test_conflicting_reconciliation_rejected_identical_replay_idempotent`
- `test_crash_after_read_before_append_exposes_no_partial_reservation`
- `test_lock_schema_and_projection_version_mismatch_fail_closed`

RW-02:

- `test_dispatch_outcome_incompatible_payload_matrix`
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_oom_rejects_falsey_or_negative_cgroup_evidence`
- `test_unknown_death_rejects_fabricated_killer_and_signal`
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`

plus append-path variants through `IncidentLedger.append_disposition` /
`validate_nbf_event`.

RW-03:

- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject`
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
- `test_consumed_change_cannot_authorize_second_reservation`

RW-04:

- `test_provider_streak_is_keyed_not_global`
- `test_nonmatching_key_rekeys_at_one`
- `test_success_resets_only_applicable_key`
- `test_probe_and_recovery_preserve_streak_and_authorize_one_child`
- `test_key_changing_precondition_rekeys_key_unchanged_does_not`
- `test_disposition_breaks_consecutiveness_without_degradation`

RW-05:

- `test_confirmation_compares_pid_start_progress_incarnation_cause`
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`

RW-06:

- `test_torn_composite_write_exposes_neither_transition_nor_receipt`
- `test_fresh_replay_receipt_is_byte_identical`

Missing name, sequential-only stand-in, or ceremonial stub ⇒ the owning
criterion is not `MET`.

## Mandatory dispositions

Preserve Luna numbering C01–C41 and CP01–CP11 from
`.oracle/checkins/batch-1-luna.md`. For **each**, give:

- status: `MET` | `NOT_MET` | `UNEVIDENCED`
- exact file/symbol or missing symbol
- concrete evidence (test name, code location, command output)
- smallest required correction if not `MET`

No criterion may be accepted solely from a green legacy suite, source
inspection without a named behavioral test where the frozen contract required
one, narrative claim, or malformed-only test.

Also disposition every rework task:

- RW-01 one journal door lock/read/compare/append + reservation-bound terminal/recon
- RW-02 strict schema and illegal-state matrix
- RW-03 evidence-bound changed-precondition producers
- RW-04 keyed provider replay mechanics (not T8 policy)
- RW-05 durable two-scan confirmation and CLI 0/2/3/4/5
- RW-06 behavioral regressions and immutable evidence protocol
- RW-CUSTODY historical vs current source SHA labeling

Inspect source, not only tests. Confirm:

- compares happen **after** the existing sequence-sidecar `fcntl.flock` and
  before emit; no UnitOfWork / two-phase / second journal
- two OS processes, not in-process threads, for contention
- OOM requires typed positive cgroup delta (falsey/negative objects reject)
- unknown death forces `killer_kind=external_unknown`,
  `cause_kind=observed_dead_unknown`, `signal is None`
- producers are reason-specific and derive IDs from authoritative sources
- projection is keyed, not one global streak
- confirmation compares PID/process-start/progress/incarnation/cause
- CLI does not signal
- aliases `append_worker_disposition`, `write_terminal_outcome`,
  `reserve_admission`, `reconcile`, `replay_projection`, generic `**kwargs`
  producer are deleted unless a frozen symbol requires them

Then separately evidence-cite:

1. North Star four enduring principles (one door; deaths speak; models admitted;
   fixer contract / no deploy-only hotfix). State disposition **explicitly**.
2. Each North Star anti-pattern (single-scan truth; anonymous exits; judgment
   healthy claims; identical-fingerprint redispatch)
3. KISS / YAGNI / scope creep: speculative abstractions, duplicate doors,
   ceremonial validation, generic frameworks, later-batch behavior
4. Evidence integrity: 52-vs-61 mutation and unreproducible `4aee815d...`
   remain historical; new receipt is internally consistent; candidate/diff
   digest and test-transcript digests bind the reviewed candidate
5. Source base, branch, HEAD, executor receipt digest, custody receipt digest,
   this check-in path

Take a position. Do not hedge. Missing, contradictory, stale, or unreviewed
evidence is `UNEVIDENCED` / an issue, not a pass.

## Binary recommendation

End with exactly one of:

```text
RECOMMEND_PASS_BATCH_1
```

or

```text
RECOMMEND_ACCEPTED_ISSUES
```

You may **not** issue `PASS_BATCH_1`. That is Grok Oracle only.

For `RECOMMEND_ACCEPTED_ISSUES`, list each issue with severity
(`blocker` | `major` | `minor`), exact file/symbol or criterion, concrete
evidence, and the smallest required correction. Do not implement corrections.

A recommendation of PASS requires that every NBF-01 must criterion, every
Batch 1 checkpoint bullet, and every RW-01…RW-06 / RW-CUSTODY acceptance
criterion is `MET` with cited behavioral evidence.

## Output files — write exactly these two

1. Full review:

```text
.oracle/checkins/batch-1-rework1-luna.md
```

Structure:

```markdown
# Luna independent review — NBF-01 / Batch 1 rework 1

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: <rev-parse>
- Tasklist SHA-256: ...
- Plan v8 SHA-256: ...
- North Star SHA-256: ...
- Rework tasklist SHA-256: ...
- Executor receipt: .oracle/receipts/execution-nbf01-rework1-luna.md
- Executor receipt SHA-256: ...
- Custody receipt SHA-256: ...
- Owned production diff SHA-256: ...
- Focused pytest: exit N, X passed (verbatim summary + stdout sha256)
- Legacy pytest: ...
- CLI statuses: 0/2/3/4/5 with evidence
- py_compile / git diff --check: ...

## Scope and diff
## Criterion dispositions (C01–C41, CP01–CP11)
## Rework task dispositions (RW-01…RW-06, RW-CUSTODY)
## North Star
## KISS / YAGNI / scope
## Evidence integrity
## Issues
## Recommendation
RECOMMEND_...
```

2. Immutable review receipt:

```text
.oracle/receipts/oracle-nbf01-rework1-luna.md
```

The receipt must bind: reviewed candidate HEAD, owned production diff digest,
every test-transcript digest, execution receipt digest, custody receipt digest,
North Star / plan v8 / frozen tasklist / rework-tasklist digests, check-in path
and its SHA-256 after write, and a statement that you did not mutate the
candidate after those digests.

Also print the recommendation line on stdout as the last line.

Do not write `.oracle/checkins/batch-1-rework1-grok.md` or the Grok Oracle
receipt. Do not commit.
