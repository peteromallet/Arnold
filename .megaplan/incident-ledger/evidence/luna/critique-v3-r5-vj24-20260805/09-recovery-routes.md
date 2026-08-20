# L9 — legal non-mutating recovery routes

**Verdict:** Sol may authorize read-only inspection now; an actual recovery is legal only after an occurrence-bound Run Authority + Custody + WBC handoff is independently proven, which this evidence pack does not establish.

**Classification:** `undetermined`

`00-common.md` was searched first but is absent from the Arnold workspace. I therefore used the supplied evidence pack and stage-1 scope, plus the local contracts listed below.

## Scope and artifacts

Local checkout is dirty and is not assumed identical to the pinned remote runtime.

| Local path | Result | SHA256 | mtime UTC |
|---|---|---|---|
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805.md` | exists | `5553df7bc6d6782014fdbcfd3788ca5d9b2a7f31382ab0a77e1c3370bdf21b4a` | `2026-08-05T11:12:23Z` |
| `.megaplan/incident-ledger/evidence/critique-v3-r5-vj24-20260805-sol-stage1.md` | exists | `b0c0c358f853726848e477b8ae4ea19a34ef0142fbf57610b11f39408384fa6a` | `2026-08-05T11:17:55Z` |
| `arnold_pipelines/megaplan/handlers/override.py` | exists | `39371dbdddab675912b16ec415b52285b2705ef64726e846fbd8f0a9455f61ae` | `2026-07-28T07:13:42Z` |
| `arnold_pipelines/megaplan/cloud/cli.py` | exists | `c383e7d91812e4caf648ea78fcb62f1d52e10512cfbb5420209971fc1a1295e4` | `2026-08-04T18:48:55Z` |
| `arnold_pipelines/megaplan/cloud/repair_contract.py` | exists | `bb4a9e8f2537aad9a289f661c5342d7c2e3b4b7584641b8c3f03b6de77f2872f` | `2026-07-10T03:32:56Z` |
| `arnold_pipelines/megaplan/cloud/repair_requests.py` | exists | `a9e6f5feb41bf6ddb7aaf9ed22aa22806255ea615a606962a13bb4b3adc0deae` | `2026-07-09T15:22:15Z` |
| `arnold_pipelines/megaplan/_core/workflow_data.py` | exists | `778c07395e2e6d8eb51dcda08f66b52a17019cd5b2adc04d7d5a551bd134243` | `2026-06-30T01:46:55Z` |
| `.tmp_remote_r5/recovery.patch` | exists, untracked proposal | `e6a4ae2e3e261454ce6510e5663e0472b500e6b299d320149ab4e180f1efaf8b` | `2026-08-04T18:14:31Z` |

Other local code inspected: `cli/__init__.py`, `auto.py`, `_core/topology.py`, `runtime/resume.py`, `planning/state.py`, `cloud/repair_lock.py`, `control_interface.py`, `workflows/override_matrix.py`, `planning/control_binding.py`, `resident/cli.py`, `cloud/supervise.py`, and `watchdog/repair_runner.py`.

Remote paths reported by the evidence pack:

- Workspace: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- Plan state: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357/state.json`
- Chain spec: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/initiatives/critique-ledger/chain.yaml`
- Chain state: `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold/.megaplan/plans/.chains/chain-a5c760402ea2.json`
- VJ24 raw execution: `.../cl2-wbc-backed-ledger-20260803-1357/execute_v2_raw.txt` — exists; contains only the selector error.
- `verification/validation_VJ24*.json` — absent.
- `verification/validation_VJ19_deferred.json` — exists; deferred, not pass.
- `execute_batch_15_output.json` and `execute_batches/batch_15/tasks_35a34c851b8f.json` — exist; empty result envelopes and pending task updates.
- `execution.json`, `execution_audit.json` — exist; T18/T23 remained pending.
- `tests/arnold/critique_ledger/test_replay_v2.py` — absent although declared by plan metadata.
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json` — exists; `status=stopped`, PID `610293`, runner fence `11`.
- `/workspace/.megaplan/cloud-sessions/repair-data/` — no r5 repair request/dispatch reported.
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json` — exists; `status=repair_unavailable`.
- `/workspace/watchdog-report.json` — exists but stale/contradictory.

The evidence pack provides no SHA256 or mtime for these remote artifacts. Remote source contents were not available; the pack only reports source head `c116f38cc83de11a1a508eff6153205504d1ba5a` and pinned runtime content SHA `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`.

## Read-only commands

CWD for all local commands: `/Users/peteromalley/Documents/Arnold`.

| Command | Exit | Relevant result |
|---|---:|---|
| `find . -name '00-common.md' -print` | 0 | no output; file absent within `.` |
| `rg -n --glob '*.py' --glob '*.md' 'repair_validation_failure\|pre_dispatch_validation_failed\|validation_job_failed' arnold_pipelines 2>/dev/null` | 1 | no matches in local `arnold_pipelines` |
| `rg -n --glob '*.py' 'recover-blocked\|resume-clarify\|retry-blocked-tasks\|def predecessors\|STATE_BLOCKED' arnold_pipelines/megaplan \| sed -n '1,220p'` | 0 | found generic recover/resume/execute routes |
| `git status --short --branch; git rev-parse HEAD` | 0, with macOS xcrun warnings | dirty local checkout; HEAD `9bf8e0556752233e6ab47e71552c1552c69b1de2` |

No remote command was invoked.

Relevant local excerpts:

```text
handlers/override.py:1224-1255
  recover-blocked requires current_state == blocked,
  a reason, and resume_cursor.phase.
  It derives a predecessor recovery state.

handlers/override.py:1256-1275
  authority_divergence raises rerun_phase_required.

handlers/override.py:1302-1306
  missing phase_result.json is an error.

handlers/override.py:1338-1355
  recovery writes current_state and removes latest_failure
  and active_step from live state.

_core/workflow_data.py:45-82
  blocked has only the generic force-proceed -> finalized route;
  no repair_validation_failure transition is defined.

auto.py:1218-1231
  execute is generated with --retry-blocked-tasks.
```

Remote raw excerpts:

```text
execute_v2_raw.txt:
validation job VJ24 references missing selectors that are not declared task outputs

validation_VJ19_deferred.json:
status=deferred_task_output
task_id=T18
missing_selectors=[tests/arnold/critique_ledger/test_replay_v2.py]
reason=selector_is_declared_task_output
```

## Joinable identities

| Identity type | Known value |
|---|---|
| Session | `critique-ledger-accountability-v3-r5-20260803` |
| Plan | `cl2-wbc-backed-ledger-20260803-1357` |
| Chain state | `chain-a5c760402ea2` |
| Remote source revision | `c116f38cc83de11a1a508eff6153205504d1ba5a` |
| Pinned runtime | `/workspace/runtime-candidates/arnold-wbc-full-20260804` |
| Runtime content SHA | `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d` |
| Validation jobs | `VJ19`, `VJ24` |
| Tasks | `T18`, `T23` |
| Sense checks | `SC18`, `SC23` |
| Batch task identity | `35a34c851b8f` |
| Liveness lease | filename above; stopped; PID `610293`; runner fence `11` |
| Chain binding drift tokens | `e5de49a5ead7 → 117b71d9caf9`; `117b71d9caf9 → cb6afb801753`; `d0fa249a1310 → bf86f59d7417` |

Not supplied: `run_id`, `run_revision`, occurrence ID/fingerprint, attempt IDs, repair request ID, claim ID, Custody lease ID, Custody epoch, current Run Authority grant/coordinator fence, WBC attempt/effect IDs, and notification IDs. Runner fence `11` is not evidence of a Custody epoch or current RA fence.

## UTC timeline

- `2026-08-03T15:40:52Z` — r5 watchdog: `repair_unavailable`; required claimed repair request before relaunch.
- `2026-08-03T17:52:40Z` — generic watchdog reported alive, but `codex_repair_enabled=false` and `push_repairs_enabled=false`.
- `2026-08-04T10:24:44Z`, `10:24:54Z` — VJ2 exited `None`, expected `[0]`.
- `2026-08-04T11:27:18Z` — persistent execute attempt blocked after model work.
- `2026-08-04T15:21:17Z` — VJ8 exited `1`.
- `2026-08-04T16:42:29Z`, `16:44:34Z` — DeepSeek repair attempts unavailable because `DEEPSEEK_API_KEY` was missing.
- `2026-08-04T16:59:49Z` — VJ9 exited `1`.
- `2026-08-04T19:35:41Z` — stale `should_run=true` marker updated.
- `2026-08-04T20:30:48Z` — VJ24 stopped before dispatch due to undeclared selectors.
- `2026-08-05T11:12:23Z` / `11:17:55Z` — local evidence pack and Sol stage-1 scope captured.

## Possible routes

| Route | Legal status and requirements | Artifacts/proof |
|---|---|---|
| Read-only status/log/chain/health inspection | Legal now. Requires no action authority. | Preserves everything; proves only observed state and artifact absence. |
| Canonical occurrence-bound repair | The only potentially legal recovery route. Requires current RA grant, coordinator fence, Custody lease and epoch, WBC attempt/contract, exact occurrence tuple, immutable source/runtime/plan binding, selector-contract evidence, independent validation, and an occurrence-scoped idempotency key/CAS. | Preserve VJ24 raw output, VJ19 deferred output, batch 15, and pending state. Add a child repair attempt; do not overwrite. Would prove the exact VJ24 occurrence was repaired and authoritative progress advanced. Current pack does not show this handoff. |
| `override recover-blocked` | Existing local route, but not legal for this occurrence on current evidence. It requires `phase_result.json`, and its implementation removes `latest_failure` and `active_step` from live state. | Could preserve historical files but erase the live failure marker. It would not prove RA/Custody/WBC authorization or VJ24 repair. |
| `resume` or `execute --retry-blocked-tasks` | Supported generic commands, but unsafe here without the missing authority and occurrence binding. | May create a new execution/batch and fork lineage. Proves only that a command ran. |
| Cloud `resume`, `supervise`, `chain start`, or arbitrary `cloud exec` | Projection/operator wrappers; no evidence they can establish current RA/Custody/WBC authority. | May relaunch or mutate remotely while leaving the failed occurrence unresolved. No valid proof of recovery. |
| `force-proceed`, `--fresh`, manual state editing, fabricated validation JSON | Not legal. | Erases or forks the failed occurrence; cannot prove validation. |
| New plan/revision | Potentially legal only as a clearly new run after quarantining the failed occurrence and establishing fresh bindings/authority. | Preserves old artifacts and proves a new run, not recovery of VJ24. |

## Positive and bounded negative evidence

Positive evidence:

- The remote plan is `blocked` with cursor `phase=execute` and `retry_strategy=repair_validation_failure`.
- VJ24 failed deterministically before worker dispatch because its selectors were not declared task outputs.
- The selector was declared in plan metadata but absent from the remote workspace.
- No VJ24 validation result exists; VJ19 was explicitly deferred, not successful.
- No durable r5 repair request/dispatch is reported.
- Remote liveness is stopped/stale and chain/runtime binding drift was recorded.

Bounded negatives:

- Local search scope: `arnold_pipelines/**/*.py` and `arnold_pipelines/**/*.md`, for the exact route/failure tokens above. It does not prove the pinned remote runtime lacks the route.
- Remote negatives are limited to the artifacts enumerated by the evidence pack. No remote checkout, ledger database, or authoritative control-plane state was directly read.
- Missing IDs may reflect evidence-pack omission rather than actual nonexistence.

## Alternative explanation

The strongest alternative is that the pinned remote runtime contains a newer, occurrence-bound VJ24 repair implementation and the evidence pack omitted its request/claim/lease records.

One falsifying observation would be an authoritative remote record joining VJ24 to the exact run/revision/occurrence, current RA grant/fence, Custody lease/epoch, WBC attempt/effect, accepted repair result, idempotency key, and post-repair cursor CAS.

## Confidence

**Low-to-medium.** Confidence is high that the supplied evidence does not prove a legal recovery handoff and that the local checkout lacks the exact route token. It is limited because the pinned remote source and authoritative ledgers were not directly available.

## Baseline classification

**`both` — existing contract present but not adopted, and required canonical structure absent.**

Baseline contracts: `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md`, `decisions/single-authoritative-runtime-history.md`, `briefs/m10-safe-retry-recovery-and-effects.md`, and `briefs/m11-conformance-and-legacy-retirement.md`. They require conjunctive Run Authority + Custody + WBC control, immutable occurrence identity, append-only evidence, and independent verification. The supplied run instead exposes generic projection-driven routes and lacks the required VJ24 repair structure.

## Decision for Sol

**Immediate recovery:** authorize only read-only reconciliation. Keep the occurrence blocked/quarantined. Do not authorize `resume`, `recover-blocked`, execute retry, supervisor/chain restart, `force-proceed`, `--fresh`, manual edits, or arbitrary remote execution. A repair may be authorized only if the canonical RA/Custody/WBC evidence bundle is produced first; otherwise escalate as a typed unrecoverable/indeterminate control-plane case.

**Durable architecture:** adopt one canonical occurrence-bound repair owner and make all legacy wrappers adapters to it. Require exact selector-contract/version evidence, RA fence + Custody epoch validation, WBC receipts, idempotent CAS, append-only lineage, independent verification, and explicit separation of any new plan revision from the failed VJ24 occurrence.