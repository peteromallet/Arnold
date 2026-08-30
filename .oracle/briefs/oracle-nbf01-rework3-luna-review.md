# Independent Batch 1 rework-3 review — NBF-01 (GPT-5.6 Luna)

You are the **independent Batch 1 rework-3 reviewer**, not the executor and not
the Oracle. You are GPT-5.6 Luna. Your job is one complete, evidence-cited
full review of the post-attempt-3 NBF-01 candidate against the frozen contract
and the supplemental attempt-3 rework tasklist. This is not a smoke-test rerun
and not a restatement of the executor narrative. Do not reuse any attempt-1 or
attempt-2 command transcript, probe, ledger root, or conclusion as current
evidence.

Do not implement, repair, stage, commit, push, merge, rebase, reset, clean, or
edit production, test, plan, frozen tasklist, North Star, custody, historical
Batch-1 / attempt-1 / attempt-2 receipts/findings/check-ins, or any rework
tasklist. Do not start Batch 2. Do not fan out a second review. Do not
self-issue `PASS_BATCH_1`.

Worktree: `/Users/peteromalley/Documents/Arnold-oracle-nbf`
Branch: `megado-nbf-guard-0826`
Python: prefer `PYENV_VERSION=3.11.11 python` or the repo venv if present.
Write pytest/CLI/probe transcripts only under `/tmp/oracle-nbf01-rework3-luna/`.
Temporary probes and ledgers must live under that isolated root or a fresh
temporary child path, never in the repository.
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
| Attempt-3 packet `.oracle/rework/batch-1-attempt-3.md` | `c4c93f8b14e253060c0a403869e22a23aadc6444e63b32f48fd55cf95b63e779` |
| Attempt-3 triage receipt | `2d025f9614d5dcf3f4e00de881962f1152a8be222b7cb4868055cf5a47856f4b` |
| Attempt-3 executor finding | `4897b2c7484aa7cc221488f7535339b716f780f3e70d62a202096504ac254e9f` |
| Attempt-3 executor receipt | `e34f901febedc434e27d778c3be5e070a6ded93a961a26dc1c4c62577339351f` |
| Attempt-2 rework tasklist | `6d625cc406ff7fe2c8764d6aae813005942a40203a01e346c290a2c6804be721` |
| Attempt-1 rework tasklist | `5149fdcf7fd91a255ec6cfe34f447a9b1eb46bf3b56db92a2e03939fbc9d1d2c` |
| Attempt-2 Grok check-in | `5ceb712841cb02a0abeb5142864b08107f86695020c872861dc1d1b8bc940455` |
| Attempt-2 Luna review | `bfc5e036f7d61827cd77ba4c0349318ce5c6beedfe832b50bfafe9270456668a` |
| Attempt-2 Luna receipt | `53a69d3e8a4a232c63e7f25fcda279b0059162087a7d45244ba0bf8d271f6f2e` |
| Attempt-2 Grok receipt | `622126f1a8ba909a6439a8f012c3e688c7c7bd4afe89ed1580bec1d06bb32e67` |
| Attempt-2 executor finding | `896cc4f1f657e8edb0c197465c14886e8cd08ae3c7e8b718941f560cea06a9bb` |
| Attempt-2 executor receipt | `d03d259725484d4eac22cae1e2582288a85a2d2dbfbbfbba7a2b0878b9b02e51` |
| Model-policy receipt | `0bb386bf6fff5f9a5197a57cea5789ee250231a163dfd01bbe828776e1cc5064` |
| Tasklist freeze v8 receipt | `583955c6996bcc18e8fe05d323c30f5f77e489cdd5a66ecb1783ac42c9d24a24` |

Executor claimed post-attempt-3 tracked production diff digest (must independently
reproduce with the exact command below):

```bash
git diff origin/main -- \
  arnold_pipelines/megaplan/incident/__init__.py \
  arnold_pipelines/megaplan/incident/ledger.py \
  arnold_pipelines/megaplan/incident/schema.py \
  arnold_pipelines/megaplan/orchestration/phase_result.py \
  arnold_pipelines/megaplan/orchestration/phase_result_classify.py \
  | shasum -a 256
```

Claimed output: `8fe64464870d32a2c4f010b98f5c13c16dad0bc479489003b7f1f8466a9ba3a8`

Oracle independently reproduced that digest on the current tree. New production
CLI `arnold_pipelines/megaplan/incident/disposition.py` is expected SHA-256
`2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a` and git blob
`291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1`.

Oracle independently hashed every owned untracked production/test file
immediately before this brief. If the tree you inspect differs, stop and
recommend `RECOMMEND_ACCEPTED_ISSUES` for a moving candidate; do not silently
review a different tree.

| Owned file | SHA-256 | git blob |
| --- | --- | --- |
| `incident/__init__.py` | `8a5afee7861ac777071f355e60627913b9a67a6178375ae141d57f983b75b923` | `e9d4ecd617ae4e7eadf0c0450cba0a73d0720f1b` |
| `incident/ledger.py` | `a70d43e8a30b55c863b0f222cd80025454a1a3c5bd53a18a1b8fbb19d15191d6` | `fa873198e87edae215a29d1638fc7c81c6a0a4da` |
| `incident/schema.py` | `289aea2e2be803c71b82d7f82db3d3f0fefe43809b181613abe22ab3d3a78a25` | `55c3ef49c4f046c0c219fade58c3a40392b8102f` |
| `orchestration/phase_result.py` | `b3621d08c8c0367b65a3d3fbba2abee10d42d90a14896ebd1f9f83e65dfc0d28` | `eb60256d6d4501dc97a37b90fe92191a611878ae` |
| `orchestration/phase_result_classify.py` | `a6a05b2c0689320bf3d2b6df89cc6d140592fbb3afc12702f76a3aff6dd3f641` | `6f14c61e1b95609858dbb7b49a5bfa4b98de1cf5` |
| `incident/disposition.py` | `2a59e440d7bcae53700b7ea63fdd2d15b1b1705eeb6914d24ea4f37300ab505a` | `291c66ed2ac9b984e2c3d1f763bafcf7b86ca1c1` |
| `test_changed_precondition_producers.py` | `5af03e900f4f87c28d761120d3a081761b9584ae58abca563df0e51587f25042` | `21377b6ddaf148bba584240104bde7251e7916da` |
| `test_incident_ledger_transactions.py` | `54a3bbdcb029da6ca31e094742522636c492c1479532eba7b0a9c31409412342` | `2e9e9556dc81777fe1518b51d3a7ea135d77ef79` |
| `test_provider_route_projection.py` | `0ae06f36637368a4963bbd7f43233e6c3748e1d179202ee6e4b0c612c340eeb2` | `3ebfc3516a5a0fe62e6fd4ccb0b33472ac54d99a` |
| `test_reservation_reconciliation.py` | `8f2d756b8b7fd22b1f1c871829f593260e7a374c7b68e55a26c7870eb05f0a0e` | `2d2ec909688040de467fb82f16e0676c1e69e8cd` |
| `test_scheduling_conditions.py` | `2b5663dd1b8f787d74c1482ba88ce1800be1e1066d3778069e8c6a3dbca62eeb` | `fc54999a025f23d89860facda94b260d1d7e5bb3` |
| `test_supervision_confirmation.py` | `110de06726862b86e754347b749a5460f79bc48b1abfa8c7ca10e16794b54034` | `b0d12ac92201438c45bc990cd7b3cbfc8052c22e` |
| `test_terminal_outcomes.py` | `70d05156ff467c79f4ccc55446e7b5d692d1f4d362a8a21021230c22f0e80915` | `1dcb901b9623e320642f4b96dae499e0c8e336a2` |
| `test_worker_disposition.py` | `bad693168f9e31b4c864b7ac0cb72cf24319f5bed2ad82286115a7a991ac7471` | `ce1aa1213e46cb6dab3c0a1f90f2fcc535b8c197` |

`tests/arnold_pipelines/megaplan/test_incident_ledger.py` must remain unchanged
versus `origin/main` (blob `44dc3adb87ad4dd077aed449c2f5ccc3526d8d93`, SHA-256
`83e8464c9dfd289aa08de41d044257936072e29ae1d8648f52b84f441f79a195`).

Do not rewrite historical evidence. Preserve as historical:

- Original start-gate receipt claimed focused **52** passed, later mutated on
  the same path to **61**.
- Unreproducible owned-source digest
  `4aee815d065e6952f1260ef87407c21d40d93eaa70ce232bfea23a15d1519a70`.
- Prior independent Luna failed-handoff digest
  `50c864900a2f9d0fd5b6bc4240d97d365148e4cf2dd511749e9701fa059a09bf`.
- Attempt-1 observation focused **78** / legacy **78** and digest `e060f650...`.
- Attempt-2 owned tracked-production digest
  `16f6f854fcc4430ca09e1a89e34e83bc2641df88e2f86ffe19c1e05518257d1d`.
- Current focused count is an observation, not a target.

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
8. `.oracle/rework/batch-1-attempt-1.md`,
   `.oracle/rework/batch-1-attempt-2.md`,
   `.oracle/rework/batch-1-attempt-3.md`
9. All three Grok triage receipts
10. `.oracle/checkins/batch-1-luna.md`, `.oracle/checkins/batch-1-grok.md`,
    `.oracle/checkins/batch-1-rework1-luna.md`,
    `.oracle/checkins/batch-1-rework1-grok.md`,
    `.oracle/checkins/batch-1-rework2-luna.md`,
    `.oracle/checkins/batch-1-rework2-grok.md`
11. Attempt-3 executor finding and receipt bound above
12. Every owned production and test file listed below

Do not treat the executor receipt as proof. Reproduce the diff, named tests,
CLI statuses, required behavioral names, and the ten attempt-2 failure probes
yourself under `/tmp/oracle-nbf01-rework3-luna/`.

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

Write transcripts to `/tmp/oracle-nbf01-rework3-luna/` only. Record full argv,
cwd, exit status, verbatim stdout and stderr, and SHA-256 of stdout bytes and
stderr bytes for each. Do not abbreviate pytest output to a count. Empty
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

Full megaplan test-directory sweep (required, with relevance protocol below):

```bash
pytest -q tests/arnold_pipelines/megaplan
```

CLI via independent subprocesses (do **not** treat pytest names as a substitute
for these transcripts):

```bash
python -m arnold_pipelines.megaplan.incident.disposition record \
  --ledger-root "$LEDGER_ROOT" \
  --json-stdin
```

Drive statuses **0, 2, 3, 4, 5**. Status 0 must emit one JSON acknowledgement on
stdout, must not signal, and for a worker disposition must prove a consumed
matching confirmation. Status 2 must be reachable with malformed JSON **and**
schema-invalid payloads even when confirmation is missing. Status 3 must be a
lock/append fault at a valid location. Status 4 must be a real
invalid/unavailable ledger-location branch, not collapsed into 3. Status 5 must
cover missing, **expired**, and a **distinct already-consumed matching replay**
(same confirmation, same disposition identity, second CLI invoke).

A green pytest run is **necessary but not sufficient**. If tests are thin,
vacuous, sequential-only, malformed-only, or do not cover a frozen criterion,
that criterion is `NOT_MET` or `UNEVIDENCED` even if pytest is green.

Read every new test module completely. Count collected tests. State how many
are new vs unchanged `test_incident_ledger.py`. Check that each required
behavioral name below exists **and actually exercises the named hole** (not a
renamed happy-path stub). Sequential-only contention is not two-process CAS.
A forged-ID test that mutates a hash to `"a"*64` without recomputing
`event_id` is inconsistent-identity coverage only.

Also judge the attempt-3 executor finding/receipt against RW3-06 / A3-08:
full argv, cwd, exit, stdout, stderr, and stdout/stderr SHA-256 per command;
explicit candidate HEAD; complete changed-file inventory; `git hash-object`
and SHA-256 for disposition.py and the eight new test modules; independent
CLI subprocesses for 0/2/3/4/5. A truncated digest, missing HEAD, missing
per-file test hashes, or pytest-name stand-in for CLI transcripts is an
evidence-integrity issue for RW3-06, not a waiver of the code if the
independent transcripts you capture are complete.

## Broad-suite missing-module relevance protocol

The executor's `pytest -q tests/arnold_pipelines/megaplan` collection stopped on:

- `ModuleNotFoundError: arnold.agent.costing.model_resource_capabilities`
  from `test_cli_check_validator.py`; and
- `ModuleNotFoundError: tools.environments.singularity`
  from `test_key_pool_codex.py`.

Freshly reproduce the sweep. Inspect both import chains. Compare the missing
modules/import sites against `origin/main`. Check whether any owned attempt-3
source/test change introduced, removed, or made either import reachable.
Classify each blocker with evidence as exactly one of:

- `IN_SCOPE_REGRESSION` — caused by or coupled to the NBF candidate; fatal;
- `PRE_EXISTING_OUT_OF_SCOPE_BLOCKER` — reproducible on the source-base tree or
  demonstrably outside owned NBF seams; not itself fatal to frozen NBF-01, but
  recorded as reduced broad-suite coverage and never used to waive an in-scope
  criterion; or
- `UNEVIDENCED_RELEVANCE` — relevance cannot be established; the evidence gate
  remains incomplete and the recommendation is `RECOMMEND_ACCEPTED_ISSUES`.

The collection blocker is not automatically waived and not automatically fatal.
Its consequence comes only from demonstrated relevance to the frozen NBF-01
diff and criteria. Even a proved pre-existing/out-of-scope blocker does not
excuse any missing focused, legacy, adversarial, or direct-probe evidence.

## Required independent probes of attempt-2 holes

Inspect implementations and test bodies for ceremonial coverage. Independently
probe the specific attempt-2 failures against the current candidate under
`/tmp/oracle-nbf01-rework3-luna/`. Transcript each probe with exact argv, cwd,
exit, stdout, stderr, and SHA-256. At minimum:

1. A fully populated terminal without persisted accepted marker, and each
   reservation/marker context mismatch.
2. Every six-kind incompatible payload family at constructor, decode,
   validation, and append; typed worker identity; false/zero/negative OOM;
   legal positive OOM; fabricated killer/signal unknown death; legal unknown.
3. A coherent changed-precondition forgery with all hashes recomputed and a
   valid authoritative producer/consume single-use path.
4. Success/ordinary/disposition targeting a non-latest provider stream across
   fresh replay, with cross-key isolation and no degradation for breaks.
5. Absent/failed/mismatched/replayed/consumed probe/recovery authorization and
   valid one-composite same-route child reservation preserving streak.
6. Fresh-ledger byte-identical composite receipt replay, injected failure at
   the real `_emit_locked` / receipt boundary, and distinct terminal IDs/kinds
   racing from separate OS processes.
7. Every confirmation identity omission/mismatch, TTL/separation/replacement/
   restart/consume/expire edge, including expiry-after-consume rejection.
8. Independent direct CLI subprocess cases for 0, malformed/schema 2, append/
   lock 3, invalid ledger 4, and missing/expired/distinct-already-consumed 5.
9. Absence or justified typed constraint of the unofficial route-child alias
   `reserve_provider_route_child_with_receipt`.
10. Replay failure on invalid schema/projection/cache mismatch and preservation
    of the one-journal/one-lock door.

Prefer `multiprocessing`/`subprocess` against one on-disk ledger (real
`fcntl.flock`) over in-process threading. Use injectable clocks for
TTL/separation. Temporary ledgers live under `/tmp/oracle-nbf01-rework3-luna/`
or a fresh temporary child path, never in the repository.

## Frozen NBF-01 criteria C01–C41 (must classify each)

Preserve Luna numbering from `.oracle/checkins/batch-1-luna.md`. For **each**,
give status `MET` | `NOT_MET` | `UNEVIDENCED`, exact file/symbol, behavioral
test/probe evidence, transcript hashes, and smallest required correction if
not `MET`.

Calibration already settled by the Oracle (do not reopen as a blocker):
do **not** overweight `PhaseResult.from_dict` unknown-field handling as the
C01 door. C01 is the `DispatchOutcome` / `SchedulingCondition` matrix.

Do not fail Batch 1 merely because later-batch wiring (admission callers,
scheduler, T7/T8 policy, physical doors, launch adapters, signal sites,
fallback policy) is correctly absent. Do fail any frozen NBF-01 primitive
criterion that remains unproved or behaviorally false.

C01–C41 mapping to frozen tasklist NBF-01 acceptance bullets:

- **C01** Scheduling / six outcome kinds round-trip strictly; unknown/missing
  fields reject. (`DispatchOutcome` / `SchedulingCondition`, not overweight
  `PhaseResult.from_dict`.)
- **C02** Invalid kind/state/payload combinations reject. Complete six-kind
  incompatibility matrix including `worker_disposition` + `success_payload`
  at constructor, `from_dict`, `validate_nbf_event`, and append.
- **C03** `no_launch` cannot serialize with `launch_state=accepted`.
- **C04** `worker_disposition` requires accepted launch, disposition_id,
  receipt, fingerprint, phase/spec, logical/worker identity, start/finish.
- **C05** Worker disposition cannot carry provider-exhaustion or no-launch
  state. Carrying an applicable `provider_failure_key` identity on a terminal
  payload for keyed-stream targeting is not provider-exhaustion evidence and
  must not reintroduce `provider_evidence` on `worker_disposition`.
- **C06** Maps only to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- **C07** Mapping validates exactly one already-committed matching disposition
  and never re-appends it.
- **C08** Never coerced into ordinary failure.
- **C09** Duplicate linkage idempotent; conflicting linkage/kinds reject.
  Distinct terminal IDs and conflicting kinds racing from two OS processes
  must yield one winner.
- **C10** Reservation closure and terminal-fingerprint projection occur exactly
  once. Requires a persisted receipt-bound accepted `controlled_adapter_state`
  matching reservation/admission/phase/spec/logical/worker/start/physical_door
  before appending any worker terminal. Replay must not self-authorize
  `accepted_launch=True` from the terminal.
- **C11** Worker disposition breaks provider-exhaustion consecutiveness without
  entering degradation, on the **applicable keyed stream**, not latest-stream
  fallback.
- **C12** `no_launch` produces no worker terminal/fingerprint/provider/streak.
- **C13** Worker / observed-death / non-worker schemas reject incomplete or
  fabricated identities. Worker fingerprint is a canonical 64-hex SHA-256.
  Worker identity is a typed required structure, not any nonempty dict or
  bare truthy string.
- **C14** OOM requires positive cgroup evidence (`positive is True` and finite
  `delta > 0`); false/zero/negative reject. Unknown death remains unknown
  (`killer_kind=external_unknown`, `signal is None`,
  `cause_kind=observed_dead_unknown`). Fabricated killer and fabricated
  signal each reject at constructor **and** append.
- **C15** TERM and KILL ladder IDs are distinct.
- **C16** Semantic fingerprint excludes volatile liveness and logical/family IDs.
- **C17** Route-liveness digest absent from fingerprint and provider-failure key.
- **C18** Different logical IDs with same projection key + fingerprint contend
  for one reservation (real two-OS-process race).
- **C19** Only allowlisted reason-specific producers may mint changes. Public
  minting is only the seven producers from settled-plan §4.6. Callers must not
  supply `producer_kind`, `producer_version`, subject, evidence digest,
  before/after content IDs, or provider-failure-key transitions as trusted
  inputs.
- **C20** Producer, evidence, subject, version, before/after, provider-key
  binding validated against authoritative sources.
- **C21** Forged unequal content IDs or provider-failure-key transitions reject
  even when every content hash and `event_id` is coherently recomputed.
- **C22** Valid changed-precondition consumed at most once.
- **C23** `provider_recovery_verified` may authorize one linked same-route
  child without resetting/rekeying. Requires a persisted **passed** canonical
  probe bound to parent/phase/route/provider plus producer-derived recovery
  consumed exactly once inside the one composite append.
- **C24** Other allowlisted change resets/rekeys only when canonical
  before/after keys differ.
- **C25** Ordinary two-process reservation contention yields one winner.
- **C26** `provider_route_child_reserved` is one record and contains no child
  receipt-ID input.
- **C27** Receipt identity derives after append and reproduces byte-for-byte
  after fresh replay of a **real composite** `provider_route_child_reserved`.
- **C28** Torn or failed writes cannot expose partial transitions, receipts, or
  projections. Inject failure at the real `_emit_locked` / receipt boundary of
  a real composite; both-or-neither after restart.
- **C29** Every accepted terminal outcome projects fingerprint state before
  reservation `closed=True`.
- **C30** Matching accepted `provider_exhausted` increments keyed streak.
- **C31** Nonmatching accepted `provider_exhausted` rekeys at one.
- **C32** Accepted worker success resets applicable streak and active key.
  Missing applicable key must **not** fall back to `latest_stream_key`.
- **C33** Intervening ordinary failure or worker disposition breaks
  consecutiveness of the matching stream without becoming degradation.
- **C34** Probe results and `provider_recovery_verified` create/consume preserve
  matching streak.
- **C35** Scheduling, no-launch, unresolved, time, liveness refresh do not
  mutate provider streak.
- **C36** Reconciliation permits only positive `released_no_launch`, recovered
  terminal, or durable ambiguous hold. (Attempt-3 executor was forbidden to
  reopen C36–C38; you must still classify the current primitive honestly.)
- **C37** Recovered worker disposition links one existing canonical disposition
  and never duplicates.
- **C38** Blind release, conflicting reconciliation, and accepted-launch
  release as no-launch reject.
- **C39** Durable two-scan state survives restart; TTL, scan separation,
  identity equality (pid/start/progress/incarnation/cause/evidence/TTL/
  expires_at/scan_interval_s), single consumption, replacement/expiry.
  `expire_confirmation` must reject after consumption. Projection of expiry
  must not overwrite `consumed=True` with `False`.
- **C40** Ledger lock, append, schema, projection-version, and cache failures
  fail closed. Preserve the one-journal/one-lock door. Do not expand
  cache-mismatch as a new attempt-3 invention, but classify current behavior.
- **C41** Disposition CLI schema validation, acknowledgements, and exit codes
  match settled-plan §4.21: 0/2/3/4/5 as specified above; one JSON ack on
  stdout; diagnostics on stderr only; no signalling.

## Batch 1 checkpoint CP01–CP11 (must classify each)

- **CP01** Every NBF-01 focused test passes. Pytest-green is necessary, not
  sufficient for other criteria.
- **CP02** Schema fields and legal transitions match owned §§4.4–4.13, §4.16,
  §§4.19–4.21.
- **CP03** `DispatchOutcome.kind=worker_disposition` is lossless and maps
  exactly once.
- **CP04** One incident-ledger authority. Confirm journal count / lock door.
- **CP05** Accepted exhausted worker outcomes are the only increment inputs.
- **CP06** `provider_recovery_verified` remains single-use retry authorization
  while preserving streak.
- **CP07** Success resets; different-key rekeys at one; ordinary/disposition
  break consecutiveness; only authoritative key change otherwise resets/rekeys.
- **CP08** Composite transition and child reservation remain one append with
  post-commit replay-stable receipt.
- **CP09** No-launch, unresolved, ordinary failure, provider exhaustion, and
  worker disposition are mechanically distinct.
- **CP10** No second journal, store, prepare/commit, scheduler, rotator, or
  policy owner.
- **CP11** Crash, contention, replay, torn-write, linkage, keyed-streak, TTL,
  incarnation, and single-consumption tests pass **and are behavioral**.

## RW3-01 through RW3-06 plus RW3-GATE (classify each)

Classify RW3-01, RW3-02, RW3-03, RW3-04, RW3-05, RW3-06, and RW3-GATE
separately as `MET` | `NOT_MET` | `UNEVIDENCED`, even where A3 items were
packed into one RW3 task.

### RW3-01 foundations (A3-01, A3-02, A3-03)

- Persisted receipt-bound accepted-launch marker required before worker
  terminal append; fully populated terminal without marker rejects; every
  single-field mismatch rejects; matching marker appends exactly one terminal;
  identical replay is idempotent; conflicting kind/linkage rejects; replay
  does not self-authorize `accepted_launch` from the terminal.
- Complete six-kind incompatibility matrix at constructor, decode, validation,
  and append, including `worker_disposition` + `success_payload`.
- Typed worker identity; false/zero/negative OOM reject; legal positive OOM
  appends; fabricated killer and fabricated signal unknown-death reject;
  legal unknown death appends and remains unknown.
- Authoritative reason-specific producers only. Coherent forged
  provider-key / content-ID event with recomputed hashes rejects at
  `from_dict`, append, and consume. Valid producer output is single-use.

### RW3-02 keyed provider projection and evidence-bound recovery (A3-04, A3-05)

- Success for key A after B is most recent resets A and leaves B unchanged.
- Ordinary failure / disposition for a non-latest key breaks only that stream
  and does not create degradation.
- Cross-key isolation holds after restart/replay.
- Missing applicable key mutates no stream (no `latest_stream_key` fallback).
- Matching recovery + passed probe around a live streak leave that streak
  unchanged and allow exactly one matching child.
- Failed, missing, mismatched, replayed, and already-consumed probe/recovery
  evidence reject. A second child without a new unused recovery event rejects.

### RW3-03 real composite replay/crash and distinct-ID terminal race (A3-06)

- Required name `test_fresh_replay_receipt_is_byte_identical` covers a real
  composite and is byte-identical after reopen.
- Injected composite `_emit_locked` / post-append failure yields
  both-or-neither after restart.
- Distinct-ID conflicting-kind two-process terminal race yields one committed
  terminal; replay stays valid.

### RW3-04 confirmation identity/TTL/CLI (A3-07)

- Each identity field mismatch and each omission rejects consume.
- Replacement and expiry are durable; restart preserves original expiry.
- Expiry after consumption rejects; consumed state survives replay.
- Two processes racing consume still yield one consumer.
- Direct non-signalling CLI subprocesses for 0, malformed/schema 2, append/lock
  3, invalid ledger 4, missing/expired/distinct-already-consumed 5.

### RW3-05 unofficial convenience surface (A3-09)

- `hasattr(IncidentLedger, "reserve_provider_route_child_with_receipt")` is
  false, unless a frozen downstream caller is documented with a typed
  constraint. Inspection at triage found no such caller; deletion was required.
- `reserve_provider_route_child` and `derive_receipt` remain.

### RW3-06 exact stable-candidate evidence completeness (A3-08)

- New finding and receipt exist at the attempt-3 paths and are not edits of
  attempt-2 artifacts.
- HEAD is explicit.
- Every required command has argv, cwd, exit, stdout, stderr, and full
  stdout/stderr SHA-256.
- CLI 0/2/3/4/5 are independent subprocess transcripts.
- Historical evidence remains labeled historical.
- Per RW3-06 work item 4: `git hash-object` and SHA-256 for disposition.py
  and the eight new test modules.

### RW3-GATE

You do **not** issue the Oracle verdict. You issue only
`RECOMMEND_PASS_BATCH_1` or `RECOMMEND_ACCEPTED_ISSUES`.

## A3-01 through A3-09 (classify each individually)

Even where packed into one RW3 task, classify A3-01 through A3-09 individually.

- **A3-01** terminal accepted-launch is self-authorized (C10)
- **A3-02** payload and typed identity matrix holes (C02/C13/C14)
- **A3-03** changed-precondition authority remains forgeable (C19–C21)
- **A3-04** applicable provider stream is not selected (C11/C32/C33)
- **A3-05** recovery/child authorization is not evidence-bound (C23/C34)
- **A3-06** composite replay/crash and terminal-race evidence (C27/C28/C09)
- **A3-07** confirmation and CLI evidence remains thin (C39/C41)
- **A3-08** immutable executor evidence protocol incomplete (RW2-04 / RW3-06)
- **A3-09** unofficial convenience surface remains

For each: current status, exact symbols, behavioral evidence, whether the
attempt-3 candidate closed the hole.

## Required named behavioral tests (must exist and be real)

Preserve prior-MET tests. Strengthen thin same-name tests in place; do not
treat deletion as progress. Missing name, sequential-only stand-in, or
ceremonial stub ⇒ the owning criterion is not `MET`.

Present names that must actually exercise the named hole:

- `test_two_process_reservation_contention_one_winner` (already MET; do not regress)
- `test_crash_after_read_before_append_exposes_no_partial_reservation`
- `test_dispatch_outcome_incompatible_payload_matrix` (full six-kind matrix at
  constructor, `from_dict`, `validate_nbf_event`, and append, including
  worker-disposition+`success_payload`)
- `test_no_launch_rejects_accepted_launch_state`
- `test_unresolved_launch_rejects_success_provider_failure_disposition_payloads`
- `test_success_rejects_provider_and_disposition_payloads`
- `test_oom_rejects_falsey_or_negative_cgroup_evidence` (constructor **and** append)
- `test_unknown_death_rejects_fabricated_killer_and_signal` (append both
  fabricated killer and fabricated signal)
- `test_observed_and_non_worker_reject_missing_schema_version_and_identity`
- `test_reason_specific_producers_reject_caller_producer_identity`
- `test_forged_valid_hex_content_ids_reject` (coherent forged event; recompute
  every content hash and `event_id`)
- `test_caller_supplied_provider_key_transition_rejects`
- `test_authoritative_before_after_digests_match_source`
- `test_consumed_change_cannot_authorize_second_reservation`
- `test_two_process_terminal_linkage_is_atomic` (distinct IDs, conflicting
  kinds, two OS processes)
- `test_terminal_rejects_reservation_context_mismatch`
- `test_terminal_requires_persisted_accepted_launch_context` (fully populated
  outcome, no marker, and every single-field mismatch)
- `test_blind_release_and_accepted_launch_release_reject`
- `test_recovered_disposition_links_existing_record_without_duplicate`
- `test_conflicting_reconciliation_rejected_identical_replay_idempotent`
- `test_lock_schema_and_projection_version_mismatch_fail_closed`
- `test_recovery_authorization_single_use_across_different_children`
  (start from a live keyed streak, a passed canonical probe, and a
  producer-derived recovery)
- `test_invalid_replay_record_never_projects`
- `test_provider_streak_is_keyed_not_global` (assert values, not dict length)
- `test_fresh_replay_receipt_is_byte_identical` (composite, not ordinary
  reservation)
- `test_nonmatching_key_rekeys_at_one`
- `test_success_resets_only_applicable_key` (must target the **non-latest**
  stream)
- `test_probe_and_recovery_preserve_streak_and_authorize_one_child`
- `test_key_changing_precondition_rekeys_key_unchanged_does_not`
- `test_disposition_breaks_consecutiveness_without_degradation` (non-latest
  target plus explicit no-degradation assertion)
- `test_confirmation_compares_pid_start_progress_incarnation_cause`
  (every field mismatch and every omission)
- `test_confirmation_replacement_and_expiry_are_durable`
- `test_confirmation_survives_ledger_reopen_with_original_expiry`
- `test_two_process_confirmation_single_consumer`
- `test_cli_status_0_one_json_ack_no_signal`
- `test_cli_status_2_malformed_or_schema`
- `test_cli_status_3_append_or_lock_failure`
- `test_cli_status_4_invalid_ledger_location`
- `test_cli_status_5_missing_and_already_consumed_confirmation`
  (add expired and distinct already-consumed matching replay)
- `test_torn_composite_write_exposes_neither_transition_nor_receipt`
  (real `reserve_provider_route_child` + `_emit_locked` injection)

Attempt-3 required names that must exist and be real:

- `test_terminal_without_accepted_marker_rejects_fully_populated_outcome`
- `test_accepted_marker_single_field_mismatch_rejects`
- `test_legal_positive_oom_appends`
- `test_legal_unknown_death_remains_unknown_after_append`
- `test_worker_disposition_rejects_success_payload_at_append`
- `test_coherent_forged_provider_transition_with_recomputed_ids_rejects`
- `test_success_for_non_latest_key_does_not_reset_latest`
- `test_ordinary_failure_breaks_only_applicable_stream`
- `test_applicable_key_survives_restart_and_replay`
- `test_cross_key_isolation_after_success_and_disposition`
- `test_recovery_requires_passed_canonical_probe`
- `test_failed_absent_mismatched_replayed_consumed_recovery_rejects`
- `test_expire_confirmation_after_consume_rejects`
- `test_cli_status_5_expired_confirmation`
- `test_cli_status_5_distinct_already_consumed_replay`
- `test_unofficial_route_child_with_receipt_surface_absent` (or equivalent
  smallest API-surface assertion)

## Prior-MET behavior that must remain intact

Attempt 2 landed real progress. Confirm these remain `MET` with current
source/test evidence; a regression is a blocker:

- One `_IncidentEventJournal` + sequence-sidecar flock. NBF writes enter
  `_locked` / `_append_nbf_locked`.
- C03 `no_launch` cannot serialize with `launch_state=accepted`.
- C04 worker-disposition required accepted launch, disposition_id, receipt,
  fingerprint, phase/spec, logical/worker identity, start/finish.
- C05 worker disposition cannot carry provider-exhaustion or no-launch state.
- C06 lossless map to `worker_terminal_outcome(outcome_kind=worker_disposition)`.
- C08 never coerced into ordinary failure.
- C12 `no_launch` produces no worker terminal/fingerprint/provider/streak.
- C15 TERM vs KILL ladder IDs remain distinct.
- C16 semantic fingerprint excludes volatile liveness and logical/family IDs.
- C17 route-liveness digest absent from fingerprint and provider-failure key.
- C18 / C25 two-OS-process same-fingerprint reservation contention yields one
  winner (`test_two_process_reservation_contention_one_winner`).
- C22 valid changed-precondition consumed at most once.
- C26 composite child is one record and contains no child receipt-ID input.
- C29 reducer order: provider/fingerprint reduction still runs before
  reservation `closed=True`.
- C30 / C31 for matching streams: matching accepted exhaustion increments
  that key; a first observation of a different key starts that stream at 1.
- C35 scheduling / no-launch / unresolved / time / liveness refresh do not
  mutate provider streak.
- CP04 / CP10: no second journal, store, prepare/commit, scheduler, rotator,
  or family lease.
- CP05: only accepted `provider_exhausted` terminals increment observations.
- RW-CUSTODY: already MET. Do not edit `.oracle/custody.md`.
- Real two-process reservation contention remains a real `fcntl.flock` race.
- Owned source scope: five modified production files, new
  `incident/disposition.py`, eight named new test modules.
  `test_incident_ledger.py` remains unchanged versus `origin/main`.
- Historical evidence stays historical.

Confirm no second journal/store/projection, prepare/commit protocol, admission
caller, scheduler, T7/T8 policy, physical admission/dispatch/death door, launch
adapter, signal-site wiring, fallback policy, family lease, rotator, or
main-merge work entered the candidate.

## Mandatory dispositions

For **each** C01–C41 and CP01–CP11, give:

- status: `MET` | `NOT_MET` | `UNEVIDENCED`
- exact file/symbol or missing symbol
- concrete evidence (test name, code location, command output, probe transcript
  hash)
- smallest required correction if not `MET`

No criterion may be accepted solely from a green legacy suite, source
inspection without a named behavioral test where the frozen contract required
one, narrative claim, or malformed-only test.

Then separately classify RW3-01..RW3-06, RW3-GATE, and A3-01..A3-09.

Inspect source, not only tests. Confirm:

- compares happen **after** the existing sequence-sidecar `fcntl.flock` and
  before emit; no UnitOfWork / two-phase / second journal
- two OS processes, not in-process threads, for contention
- OOM requires typed positive cgroup delta (falsey/negative objects reject)
- unknown death forces `killer_kind=external_unknown`,
  `cause_kind=observed_dead_unknown`, `signal is None`
- producers are reason-specific and derive IDs from authoritative sources
- projection is keyed, not one global streak; success/disposition act on the
  applicable key only
- confirmation compares PID/process-start/progress/incarnation/cause
- CLI does not signal
- unofficial aliases remain deleted:
  `append_worker_disposition`, `write_terminal_outcome`,
  `reserve_admission`, `reconcile`, `replay_projection`,
  `append_provider_probe_result`, `acquire_probe_lease`,
  `append_confirmation`, `append_changed_precondition_event`,
  generic `make_worker_disposition` / `make_observed_process_death` /
  `make_non_worker_disposition`, `WorkerDeathDisposition`,
  `ReservationReconciliation`, generic `**kwargs` producer, and
  `reserve_provider_route_child_with_receipt`

Then separately evidence-cite:

1. North Star four enduring principles (one door; deaths speak; models admitted;
   fixer contract / no deploy-only hotfix). State disposition **explicitly**.
2. Each North Star anti-pattern (single-scan truth; anonymous exits; judgment
   healthy claims; identical-fingerprint redispatch)
3. KISS / YAGNI / scope creep: speculative abstractions, duplicate doors,
   ceremonial validation, generic frameworks, later-batch behavior
4. Evidence integrity: 52-vs-61 mutation, unreproducible `4aee815d...`,
   failed-handoff `50c86490...`, attempt-1 `e060f650...`, and attempt-2
   `16f6f854...` remain historical; new receipt is internally consistent;
   candidate/diff digest and test-transcript digests bind the reviewed candidate
5. Broad-suite relevance classification for each collection blocker
6. Source base, branch, HEAD, executor receipt digest, this check-in path

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
Batch 1 checkpoint bullet, every preserved prior-MET criterion, every
RW3-01…RW3-06 acceptance criterion, A3-01..A3-09, the evidence protocol, and
preservation/scope gates are `MET` with cited behavioral evidence. Green
counts, executor claims, or an out-of-scope test-environment failure cannot
substitute for behavioral proof.

## Output files — write exactly these two

1. Full review:

```text
.oracle/checkins/batch-1-rework3-luna.md
```

Structure:

```markdown
# Luna independent review — NBF-01 / Batch 1 rework 3

- Model: GPT-5.6 Luna
- Date: 2026-08-30
- Source base: origin/main@798c50619204010ed3f4297fbb57988fe9381924
- Branch: megado-nbf-guard-0826
- HEAD: <rev-parse>
- Tasklist SHA-256: ...
- Plan v8 SHA-256: ...
- North Star SHA-256: ...
- Attempt-3 rework tasklist SHA-256: ...
- Executor receipt: .oracle/receipts/execution-nbf01-rework3-luna.md
- Executor receipt SHA-256: ...
- Owned production diff SHA-256: ...
- Focused pytest: exit N, X passed (verbatim summary + stdout sha256)
- Legacy pytest: ...
- Broad-suite sweep: exit, classification of each collection blocker
- CLI statuses: 0/2/3/4/5 with independent subprocess evidence
- py_compile / git diff --check: ...
- Isolated transcript root: /tmp/oracle-nbf01-rework3-luna/

## Scope and diff
## Criterion dispositions (C01–C41, CP01–CP11)
## Rework task dispositions (RW3-01…RW3-06, RW3-GATE, A3-01…A3-09)
## Independent probes of attempt-2 holes
## Broad-suite relevance classification
## Preserved prior-MET result
## North Star
## KISS / YAGNI / scope
## Evidence integrity
## Issues
## Recommendation
RECOMMEND_...
```

2. Immutable review receipt:

```text
.oracle/receipts/oracle-nbf01-rework3-luna.md
```

The receipt must bind: reviewed candidate HEAD, owned production diff digest,
every test-transcript digest, every probe transcript digest, execution receipt
digest, North Star / plan v8 / frozen tasklist / attempt-3 rework-tasklist
digests, check-in path and its SHA-256 after write, isolated transcript root,
reviewer count exactly one, and a statement that you did not mutate the
candidate after those digests.

Also print the recommendation line on stdout as the last line.

Do not write `.oracle/checkins/batch-1-rework3-grok.md` or the Grok Oracle
receipt. Do not commit. Do not start Batch 2.
