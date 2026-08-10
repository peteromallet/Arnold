# Q L1 — VJ24 declaration/task-output path

**Verdict:** VJ19 joined `tests/arnold/critique_ledger/test_replay_v2.py → T18` from plan declarations, while VJ24 had no accepted batch-15 task-output entry for that selector; the exact VJ24 normalized map cannot be proven because its validator source and result artifact are absent.

**Classification:** `undetermined` — the declaration/evidence split is supported, but the exact VJ24 map implementation is not recoverable from the evidence pack.

## Scope and artifact identity

Cwd: `/Users/peteromalley/Documents/Arnold`. No remote commands or mutations were performed.

Local `00-common.md` is absent:

- `find . -name '00-common.md'`: no output, exit `0`.
- `.megaplan/incident-ledger/evidence/00-common.md`: absent, existence exit `1`.

Evidence files:

| Local path | Size / mtime | SHA-256 |
|---|---:|---|
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md` | 9722 / `2026-08-05T11:12:23Z` | `5553df7bc6d6782014fdbcfd3788ca5d9b2a7f31382ab0a77e1c3370bdf21b4a` |
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md` | 8483 / `2026-08-05T11:17:55Z` | `b0c0c358f853726848e477b8ae4ea19a34ef0142fbf57610b11f39408384fa6a` |

Remote paths named in the evidence pack:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/plan_v1.meta.json` — present/listed; SHA/mtime not reported.
- Same path with `plan_v2.meta.json`, `plan_v2.md`, `execute_v2_raw.txt`, `execute_batch_15_output.json`, `execution.json`, `execution_audit.json` — present/listed; SHA/mtime not reported.
- `.../verification/validation_VJ19_deferred.json` — present/listed; content hash field exists, value not reported.
- `.../verification/validation_VJ24*.json` — explicitly absent.
- `.../execute_batches/batch_15/tasks_35a34c851b8f.json` — present/listed; SHA/mtime not reported.
- `/workspace/runtime-candidates/arnold-wbc-full-20260804` — pinned runtime; content SHA `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`.
- Remote source head at launch: `c116f38cc83de11a1a508eff6153205504d1ba5a`; unavailable locally.
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json` — `status=stopped`, PID `610293`, fence `11`.
- `.megaplan/cloud-chain-critique-ledger-accountability-v3-r5-20260803.log` — runtime-binding drift records.

The selector file is absent locally and from the remote r5 workspace. It is also absent from the locally known critique branch `e5e9f2b1c1a7e7779121405fd4801768e1e8a4c2`; branch lookup exited `128`.

## Normalized map and conflict

The strongest evidence-supported maps are:

| Consumer | Evidence-supported normalized selector → task map |
|---|---|
| VJ19 | `{ "tests/arnold/critique_ledger/test_replay_v2.py": ["T18"] }` |
| VJ24 | No serialized map. Batch-15 evidence contains no output, commands, result envelopes, or accepted task update; operationally, the accepted task-output map for `T18/T23` is empty, but this is an inference—not a recovered VJ24 field. |
| Plan declarations | Selector listed in both `plan_v1.meta.json`, `plan_v2.meta.json`, and Step 15 `Files:` in `plan_v2.md`. |

Relevant raw excerpts:

> `validation_VJ19_deferred.json` reports `status=deferred_task_output`, `task_id=T18`, `missing_selectors=[tests/arnold/critique_ledger/test_replay_v2.py]`, `reason=selector_is_declared_task_output`.  
> — evidence pack, line 29

> `execute_batch_15_output.json` has no output, commands, or result envelopes… both task updates remain `pending`.  
> — evidence pack, line 27

> `validation job VJ24 references missing selectors that are not declared task outputs`  
> — evidence pack, lines 24–25

Therefore the selector was not a legitimate T18 output: T18 was never dispatched and no accepted output exists. It is a plan-declared but unproduced selector—possibly stale/unimplemented, with plan/runtime revision split still possible.

## Local contract/code trace

Exact local paths inspected:

- `arnold/pipeline/validator.py`
- `arnold/pipeline/contract_validation.py`
- `arnold_pipelines/megaplan/orchestration/task_satisfaction.py`
- `arnold_pipelines/megaplan/orchestration/authority_readers.py`
- `arnold_pipelines/megaplan/orchestration/evidence_contract.py`
- `arnold_pipelines/megaplan/orchestration/execution_evidence.py`
- `arnold_pipelines/megaplan/orchestration/test_selection.py`
- `arnold_pipelines/megaplan/orchestration/plan_contracts.py`
- `arnold_pipelines/megaplan/handlers/finalize.py`
- `arnold_pipelines/megaplan/handlers/plan.py`
- `arnold_pipelines/megaplan/handlers/execute.py`
- `arnold_pipelines/megaplan/execute/batch.py`
- `arnold_pipelines/megaplan/execute/merge.py`
- `arnold_pipelines/megaplan/execute/aggregation.py`
- `arnold_pipelines/megaplan/execute/quality.py`
- `arnold_pipelines/megaplan/execute/step_edit.py`

Key excerpts:

- `task_satisfaction.py:19–21,38–43`: canonical task-output fields are `files_changed`, `commands_run`, `evidence_files`, `sections_written`.
- `task_satisfaction.py:92–95,255–264`: missing declared outputs make a task unsatisfied.
- `authority_readers.py:715–721`: reported outputs corroborate evidence only for terminal task statuses; pending tasks do not count.
- `test_selection.py:646–680`: plan metadata is read from the latest `plan_v*.meta.json`.
- `test_selection.py:162–217`: nonexistent path selectors are normalized and dropped into `missing_test_selectors`.
- `finalize.py:1262–1362`: task `files_changed` and pytest command paths are separately parsed.
- `finalize.py:1365–1437`: metadata selectors and task declarations are separate fallback sources.
- `batch.py:766–807`: execute updates are normalized into task IDs, statuses, files, and commands.
- `batch.py:1212–1257`: batch evidence is audited and persisted only after execution processing.
- `aggregation.py:61–105`: aggregate task updates/result fields from batch payloads.
- `arnold/pipeline/validator.py:1–24`: local validator is only a compatibility shim to workflow graph validation.

Exact searches:

```sh
rg -n -S 'validation job VJ24 references missing selectors that are not declared task outputs|VJ19|VJ24' arnold arnold_pipelines tests --glob '*.py' --glob '*.md'
```

Cwd as above; exit `1`; no local source match.

```sh
rg -n -S 'validation job VJ24 references missing selectors that are not declared task outputs|VJ19|VJ24' .megaplan/incident-ledger/evidence
```

Exit `0`; matched evidence lines 7, 11, 19, 24–29, 40, 77, 86.

## UTC timeline

- `2026-08-03T13:57Z` — embedded in plan ID `cl2-wbc-backed-ledger-20260803-1357`; not independently an event timestamp.
- `2026-08-03T15:40:52Z` — r5 watchdog: `repair_unavailable`.
- `2026-08-03T17:52:40Z` — older generic watchdog reported stale `alive`.
- `2026-08-04T10:24:44Z`, `10:24:54Z` — VJ2 exited `None`.
- `2026-08-04T11:27:18Z` — persistent execute attempt; GLM 5.2 used for batches 2–5.
- `2026-08-04T15:21:17Z` — VJ8 exited `1`.
- `2026-08-04T16:42:29Z`, `16:44:34Z` — DeepSeek unavailable due missing API key.
- `2026-08-04T16:59:49Z` — VJ9 exited `1`.
- `2026-08-04T19:35:41Z` — stale primary session marker updated.
- `2026-08-04T20:30:48Z` — VJ24 deterministic stop before T18/T23 execution.
- `2026-08-05` — evidence captured; local evidence mtimes above.

## Joinable identities

Known:

- Session: `critique-ledger-accountability-v3-r5-20260803`
- Plan: `cl2-wbc-backed-ledger-20260803-1357`
- Chain state: `chain-a5c760402ea2.json`
- Tasks: `T18`, `T23`
- Sense checks: `SC18`, `SC23`
- Validations: `VJ19`, `VJ24`
- Batch: `15`
- Batch task artifact fingerprint: `35a34c851b8f`
- Runtime: `arnold-wbc-full-20260804`, content SHA above
- Source head: `c116f38…`
- Lease PID/fence: `610293` / `11`
- Runtime-binding identities: `e5de49a5ead7`, `117b71d9caf9`, `cb6afb801753`, `d0fa249a1310`, `bf86f59d7417`

Not supplied by the evidence pack: run ID/revision ID, occurrence ID/fingerprint, attempt ID, request/claim/notification IDs, dispatch-identity value, VJ19 content-evidence hash value, plan metadata hashes, or VJ24 artifact identity.

## Negative evidence scope

The bounded negative search covered:

1. The current local checkout under `.`.
2. All tracked files under `arnold`, `arnold_pipelines`, and `tests`.
3. The locally known critique branch tree.
4. The remote artifacts explicitly summarized in the evidence pack.

Within that scope: no local VJ24 validator string, no `test_replay_v2.py`, no remote VJ24 verification artifact, and no accepted batch-15 result envelope. This does not prove absence outside those scopes.

## Alternative and confidence

Strongest alternative: VJ19 and VJ24 used different source revisions, plan revisions, task scopes, or path normalizers. This is plausible because the remote launch head `c116f38…` is unavailable locally and the runtime binding drifted repeatedly.

One falsifying observation: a VJ24 artifact from the pinned runtime showing the same normalized map, plan hash, validator source identity, and runtime identity as VJ19—while failing only on file existence—would falsify the declaration-map split.

Confidence: **medium**. High confidence that T18 produced no accepted output and VJ19 was deferred, not passed; medium/low confidence on the exact internal VJ24 map because the remote validator source and VJ24 JSON are unavailable.

## Contract classification

**`both`** against the baseline **M1 task-output evidence contract** (`task_satisfaction.py` / `evidence_contract.py`) and the plan metadata contract (`test_selection.py`):

- Existing contract present but not adopted consistently: plan declarations, VJ19, and VJ24 did not share one evidenced declaration source.
- Required canonical structure absent: no persisted, content-addressed selector→task-output map joins plan metadata, validator identity, runtime, and accepted execution evidence.

## Decision for Sol

Immediate recovery must treat `tests/arnold/critique_ledger/test_replay_v2.py` as an absent/unproduced T18 output; `VJ19` is a deferral, not success. Sol’s exact discriminator is:

```text
normalize(selector) =
  posixpath.normpath(selector.replace("\\", "/").lstrip("./")).split("::", 1)[0]

compare:
  VJ19_map,
  VJ24_map,
  plan_v1/v2 hashes,
  validator source identity,
  runtime/source identity,
  accepted task-output artifact hashes
```

Do not resume or fabricate the test until those maps and identities are joined. Durable architecture should require both validators to consume and persist the same canonical map and its content hash.