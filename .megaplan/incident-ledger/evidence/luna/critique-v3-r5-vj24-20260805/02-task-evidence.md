# L2 — task evidence, writes, budgets, attribution

## Verdict

Prior inconsistencies are not merely confidence-reducing: they invalidate the earlier execution history as recovery authority, although the append-only historical records should be preserved and quarantined rather than deleted.

Classification: `supported`.

## Scope and artifact inventory

Local cwd: `/Users/peteromalley/Documents/Arnold`. The required `00-common.md` was searched under the workspace and `/private/tmp`; it was absent.

Local files inspected included:

- [`execute/batch.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/execute/batch.py) — batch merge, persistence, audit, head stamping.
- [`execute/quality.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/execute/quality.py) — git/content-hash observation and attribution.
- [`orchestration/execution_evidence.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/orchestration/execution_evidence.py) — claimed/observed path checks.
- [`orchestration/authority_readers.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/orchestration/authority_readers.py) — authority-corroborated task completion.
- [`orchestration/task_satisfaction.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/orchestration/task_satisfaction.py) — declared-output/evidence matching and freshness.
- [`orchestration/evidence_contract.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/orchestration/evidence_contract.py).
- [`orchestration/completion_contract.py`](/Users/peteromalley/Documents/Arnold/arnold_pipelines/megaplan/orchestration/completion_contract.py) — shadow completion policy.
- `execute/merge.py` and `execute/_binding/reducer.py`.

Local evidence SHA-256:

| Artifact | Size | Mtime | SHA-256 |
|---|---:|---|---|
| `critique-v3-r5-vj24-20260805.md` | 9,722 | 2026-08-05 09:12:23Z | `5553df7b…df21b4a` |
| `critique-v3-r5-vj24-20260805-sol-stage1.md` | 8,483 | 2026-08-05 09:17:55Z | `b0c0c358…384fa6a` |
| `execute/batch.py` | 137,358 | 2026-07-16 16:05:32Z | `2b6a18c8…34b8efd` |
| `execute/quality.py` | 28,141 | 2026-06-25 18:13:00Z | `6bdcfe62…414d3c6` |
| `orchestration/execution_evidence.py` | 16,466 | 2026-07-09 13:22:15Z | `f741bb1c…090d4b1` |
| `orchestration/authority_readers.py` | 46,747 | 2026-07-05 09:19:33Z | `505eb0a0…7e8ae88` |

Local checkout HEAD is `9bf8e0556752233e6ab47e71552c1552c69b1de2` and is dirty. It is not the remote source head `c116f38cc83de11a1a508eff6153205504d1ba5a`.

Remote paths from the evidence pack:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/{execution.json,execution_audit.json,plan_v1.meta.json,plan_v2.meta.json,plan_v2.md,execute_v2_raw.txt}`
- `/workspace/.../verification/validation_VJ19_deferred.json`
- `/workspace/.../execute_batch_15_output.json`
- `/workspace/.../execute_batches/batch_15/tasks_35a34c851b8f.json`
- `/workspace/.../verification/validation_VJ24*.json` — absent.
- `/workspace/.../tests/arnold/critique_ledger/test_replay_v2.py` — absent.
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/` — no r5 request; r5 dispatch absent/empty.
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`
- `/workspace/watchdog-report.json`
- `.megaplan/cloud-chain-critique-ledger-accountability-v3-r5-20260803.log`

Remote artifact sizes, mtimes, and individual SHA-256 values are not supplied in the evidence pack, so they are not inferred.

## Local contract trace

The local executor:

- normalizes task updates to `status`, `executor_notes`, `files_changed`, `commands_run`, and `evidence_files`;
- merges task and sense-check acknowledgements;
- persists `execution_batch_N.json`, `execution.json`, and `execution_audit.json`;
- captures git status/content hashes before and after execution;
- compares claimed paths to observed paths;
- stamps `head_sha` onto task records containing output evidence;
- requires authority-corroborated evidence before scheduler completion.

Important raw excerpts:

```text
raw "done"/"skipped" labels are never success authority here
```

`authority_readers.py:85-88`

```text
Currently warn/enforce behave like shadow + a logged WARNING.
```

`completion_contract.py:88-91`

```text
Every non-audit task needs a complete planned write set or a typed
write_set_unknown blocker. Actual undeclared writes block merge...
```

`task-sizing-dependency-test-budget-investigation-20260715.md:311-315`

However, the executable local source contains no `write_set`, `narrow_tests`, `batch_scope`, `dispatch_identity`, `result_envelopes`, `task_test_budget_exhausted`, or `task_test_budget_exceeded` symbols. The search exited `1`. Thus the v2 write-set/test-budget/WBC envelope contract is documented but not adopted in this checkout.

The local audit also explicitly marks claim/diff mismatches as advisory in several paths. Completion-contract shadow mode can report unsatisfied evidence without making it a fail-closed execution admission decision.

## Representative evidence table

The evidence pack does not identify one exact earlier batch number, so the first row is the aggregate earlier-batch evidence.

| Slice | Declared writes | Observed writes | Claimed writes | Tests/budget | Sense checks | Acceptance |
|---|---|---|---|---|---|---|
| Earlier batches | Exact declarations unavailable; undeclared write-set paths reported | Source/test files claimed by workers absent from git status/content-hash deltas; unrelated `arnold_pipelines/megaplan/*` changes unclaimed | Worker claims existed but did not reconcile to observed deltas | `task_test_budget_exhausted`; exact selectors, admitted counts, durations, and attempts unavailable | Many acknowledgements absent; audit labels these advisory | No supplied accepted WBC envelope or authoritative attempt record |
| Batch 15 / VJ24 tail | Scope only: `T18`, `T23`, `SC18`, `SC23`; empty result envelope has no write declaration | No batch-15 output; both tasks remained `pending` | None in `tasks_35a34c851b8f.json`; `result_envelopes=[]` | No T18/T23 test was attempted. VJ19 deferred `tests/arnold/critique_ledger/test_replay_v2.py`; VJ24 stopped on that selector before dispatch | `SC18` and `SC23` had no executor acknowledgement | No VJ24 result artifact, no accepted envelope, and no accepted task result |

VJ19’s deferred record is explicitly not a passing test:

```text
status=deferred_task_output
task_id=T18
missing_selectors=[tests/arnold/critique_ledger/test_replay_v2.py]
reason=selector_is_declared_task_output
```

VJ24’s only raw output was:

```text
validation job VJ24 references missing selectors that are not declared task outputs
```

## Commands and raw results

All commands were read-only, run from `/Users/peteromalley/Documents/Arnold`.

```sh
sed -n '1,260p' .megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md
sed -n '1,260p' .megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md
```

Exit `0`; confirmed blocked state, empty batch-15 envelope, missing VJ24 artifact, absent replay selector, and runtime/observer drift.

```sh
find /Users/peteromalley -name 00-common.md -type f -print 2>/dev/null
```

Exit `0`; no output.

```sh
rg -n -i '(^|[^[:alnum:]_])(write_set|narrow_tests|task_test_budget_exhausted|task_test_budget_exceeded|batch_scope|dispatch_identity|result_envelopes)([^[:alnum:]_]|$)' arnold_pipelines tests --glob '*.py'
```

Exit `1`; no executable local implementation of those controls.

```sh
rg -n 'validate_execution_evidence|_observe_git_changes|_stamp_head_sha_on_task_records|effective_execute_completed_task_ids|is_task_satisfied|execution_audit|execution_batch_' arnold_pipelines/megaplan/{execute,orchestration} --glob '*.py'
```

Exit `0`; found the legacy batch/audit/content-hash/authority paths described above.

## UTC timeline and identities

- `2026-08-03T15:40:52Z`: r5 watchdog reported `alive_sessions=0`, `repair_unavailable`; no claimed repair request.
- `2026-08-03T17:52:40Z`: generic watchdog reported stale `alive`; evidence pack marks it stale.
- `2026-08-04T10:24:44Z`, `10:24:54Z`: VJ2 exited `None`.
- `2026-08-04T11:27:18Z`: persistent execute attempt blocked after model work, batches 2–5 using GLM 5.2.
- `2026-08-04T15:21:17Z`: VJ8 exited `1`.
- `2026-08-04T16:42:29Z`, `16:44:34Z`: DeepSeek credential failure.
- `2026-08-04T16:59:49Z`: VJ9 exited `1`.
- `2026-08-04T19:35:41Z`: primary marker last updated; retained stale `should_run=true`.
- `2026-08-04T20:30:48Z`: VJ24 rejected the missing task-output selector.
- `2026-08-05`: evidence captured; plan state was `blocked`, active step `null`.

Joinable identities:

- Session: `critique-ledger-accountability-v3-r5-20260803`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain state: `chain-a5c760402ea2.json`
- Source head: `c116f38cc83de11a1a508eff6153205504d1ba5a`
- Runtime: `/workspace/runtime-candidates/arnold-wbc-full-20260804`
- Runtime content SHA: `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`
- Lease: `...liveness-lease.json`, PID `610293`, fence `11`, status `stopped`
- Tasks: `T18`, `T23`
- Sense checks: `SC18`, `SC23`
- Validations: `VJ2`, `VJ8`, `VJ9`, `VJ19`, `VJ24`
- Batch envelope identity: `tasks_35a34c851b8f.json`
- Runtime drift identities: expected/active `e5de49a5ead7/117b71d9caf9`, `117b71d9caf9/cb6afb801753`, and `d0fa249a1310/bf86f59d7417`.

No VJ24 occurrence ID/fingerprint, immutable run revision, repair request/claim/attempt ID, WBC attempt/effect ID, notification ID, or accepted custody claim ID is present in the supplied pack. They must not be fabricated.

## Positive and bounded negative evidence

Positive evidence:

- VJ24 was a deterministic pre-dispatch validator stop.
- T18/T23 never executed; batch 15 has no accepted result envelope.
- Earlier execution contains broad claim/status/content-hash mismatches.
- Test-budget, write-set, and acknowledgement defects were allowed to coexist with execution evidence.
- Local policy confirms completion auditing was shadow/advisory rather than a complete fail-closed v2 admission path.
- Authority readers correctly refuse to treat raw task labels as success, but no WBC acceptance record exists to satisfy them.

Bounded negative search scope:

- Local source and tests under `arnold_pipelines/` and `tests/`, excluding worktrees, were searched for the named v2/WBC symbols.
- Required local evidence and `/private/tmp` were searched for `00-common.md`.
- Remote negatives are only those explicitly summarized in the evidence pack: no VJ24 artifact, no r5 repair request/dispatch, empty batch-15 envelope, absent replay selector, and no live chain process.

This does not prove that no such implementation exists elsewhere in the remote runtime.

## Alternative and falsifier

Strongest alternative: VJ24 is only a stale selector or plan/worktree revision mismatch, while earlier batches are otherwise recoverable.

Falsifier: a fresh, immutable comparison showing identical normalized VJ19/VJ24 selector maps and validator source hashes, plus accepted per-batch envelopes containing complete write-set, test-budget, acknowledgement, repository-delta, and authority evidence for all earlier batches.

## Confidence

Medium. The conclusion is strongly supported by the evidence pack and local code trace, but remote source and raw `execution*.json` contents were not directly readable, and `00-common.md` was unavailable.

## Contract classification

`both`:

1. Existing contract present but not adopted: local execution-evidence, authority-reader, and content-hash contracts exist, but completion auditing is shadow/advisory and earlier mismatches could persist without fail-closed admission.
2. Required canonical structure absent: the v2 planned write-set/test-budget/validation-job structure and WBC batch-scope/result-envelope acceptance path are absent from the local executable source and absent from the batch-15 envelope.

Baseline named for this classification:

- [`custody-control-plane/NORTHSTAR.md`](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/NORTHSTAR.md)
- [`m11-conformance-and-legacy-retirement.md`](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/briefs/m11-conformance-and-legacy-retirement.md)
- [`task-sizing-dependency-test-budget-investigation-20260715.md`](/Users/peteromalley/Documents/Arnold/.megaplan/initiatives/custody-control-plane/research/task-sizing-dependency-test-budget-investigation-20260715.md)

## Recovery decision

For Sol’s immediate recovery, treat earlier task completion claims as non-authoritative and require quarantine/re-establishment of execution evidence before reuse. Do not fabricate `test_replay_v2.py`, infer a VJ24 pass, or resume from the empty batch-15 envelope.

For durable architecture, adopt one machine-readable v2 task contract consumed by finalization, executor, validator, repository auditor, and authority reader; make write-set/test-budget violations and missing envelopes fail closed; and bind accepted results to immutable task, attempt, tree/content hash, runtime, fence, and occurrence identities.