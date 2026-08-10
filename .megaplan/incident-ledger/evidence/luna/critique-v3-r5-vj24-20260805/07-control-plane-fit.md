# Q L7 — Run Authority/WBC/Custody adherence

**Verdict:** The incident does not demonstrate canonical Run Authority/WBC/Custody adherence; recovery custody was not durably joined to the VJ24 occurrence, while legacy queue/lock/sidecar paths remained the effective repair boundary.

**Classification:** `refuted`  
**Adherence classification:** `both` — existing contract bypassed/not adopted, and the canonical implementation surface is absent from the inspected local checkout.

**Confidence:** Medium. The remote source checkout was not available and was not fetched; however, the evidence pack directly records no occurrence-bound repair request/dispatch and the local implementation lacks the named canonical owners.

## Baseline contract

Baseline used:

- `.megaplan/initiatives/custody-control-plane/NORTHSTAR.md`
- `.megaplan/initiatives/custody-control-plane/decisions/single-authoritative-runtime-history.md`
- `.megaplan/initiatives/custody-control-plane/decisions/m10-m11-structural-conformance-closure-20260723.md`, especially C05, C06, C12, C14, C16, C20.
- `.megaplan/initiatives/critique-ledger-post-relaunch-completion/evidence/architecture-fit-and-minimality-gate-20260804.md`
- `.megaplan/initiatives/custody-control-plane/research/wbc-boundary-adoption-matrix.md`

The baseline requires Run Authority grants/fences, WBC attempt/effect evidence, and Custody occurrence/lease/epoch to be conjunctively validated before repair or other authoritative effects. C12 requires:

> `request→decision→claim→lease→attempt→effect→terminal/indeterminate→independent verification`

The architecture gate explicitly forbids a second authority ledger, fixer framework, recovery queue, or positive authority from projections.

## Scope and artifact inventory

Local checkout:

- Root: `/Users/peteromalley/Documents/Arnold`
- `HEAD`: `9bf8e0556752233e6ab47e71552c1552c69b1de2`
- HEAD time: `2026-08-04T22:06:30+02:00`
- Working tree: materially dirty; local files are not treated as the remote runtime.
- `00-common.md`: absent; `find . -type f -name '00-common.md'` returned no path.
- Canonical paths absent locally:
  - `arnold_pipelines/run_authority`
  - `arnold/workflow/wbc_queries.py`
  - `arnold/workflow/execution_attempt_ledger.py`
  - `arnold_pipelines/megaplan/custody`

Inspected local implementation paths include:

- `arnold_pipelines/megaplan/run_state/{model.py,resolver.py}`
- `arnold_pipelines/megaplan/cloud/{repair_requests.py,repair_contract.py,repair_lock.py,status_snapshot.py,incident_bridge.py,meta_repair.py}`
- `arnold_pipelines/megaplan/cloud/wrappers/{arnold-watchdog,arnold-repair-trigger,arnold-repair-loop}`
- `arnold_pipelines/megaplan/incident/{ledger.py,schema.py}`
- `arnold_pipelines/megaplan/observability/effect_ledger.py`
- `arnold_pipelines/megaplan/auto.py`
- `arnold/pipeline/steps/human_gate.py`
- `arnold_pipelines/megaplan/cloud/{source_initiative_repair.py,dependency_manifest_repair.py}`

Key local hashes/mtimes:

| Path | SHA-256 | mtime UTC |
|---|---|---|
| `NORTHSTAR.md` | `1c2904bde9f4bea5370c141772a135363c5a0d242b9a9f4eb8462be1905f2d6f` | `2026-07-23T21:02:53Z` |
| `single-authoritative-runtime-history.md` | `332208b824ffc0b8b98cfa7e6bcb5a4e04646b891316081b0ea731d3ee758540` | `2026-07-16T12:56:06Z` |
| `m10-m11-structural-conformance-closure-20260723.md` | `f79b717bd012b792d81e5e90e1faaba88da1f7c2f3cfad2e93576fd0d396da1c` | `2026-07-23T21:02:53Z` |
| `wbc-boundary-adoption-matrix.md` | `8b61be979b0b8502286aaa6fe366e8a0cdda8abfd6966d06fa7bd42238e7b489` | `2026-07-28T12:27:15Z` |
| `repair_requests.py` | `a9e6f5feb41bf6ddb7aaf9ed22aa22806255ea615a606962a13bb4b3adc0deae` | `2026-07-09T15:22:15Z` |
| `repair_contract.py` | `bb4a9e8f2537aad9a289f661c5342d7c2e3b4b7584641b8c3f03b6de77f2872f` | `2026-07-10T03:32:56Z` |
| `repair_lock.py` | `d367ec049f76a5c28ef9d58dc4cddcac4a53300dcd12ebd8bf8a3f0c432334f4` | `2026-07-09T15:22:15Z` |
| `status_snapshot.py` | `3a26435027fb3f24ea5a543986a06fbf73ca412831a887fc09277bb5e159b688` | `2026-07-09T22:32:17Z` |
| `incident_bridge.py` | `c2bc1801b754cdb8437b895f830648a9a5cf4d1bf34019e7e290348694a34a3b` | `2026-07-09T15:22:15Z` |

Remote paths supplied by the evidence pack:

- `/workspace/critique-ledger-accountability-v3-r5-20260803/Arnold`
- `/workspace/.../Arnold/.megaplan/initiatives/critique-ledger/chain.yaml`
- `/workspace/.../Arnold/.megaplan/plans/cl2-wbc-backed-ledger-20260803-1357`
- `/workspace/.../Arnold/.megaplan/plans/.chains/chain-a5c760402ea2.json`
- `/workspace/runtime-candidates/arnold-wbc-full-20260804`
- `/workspace/.../execute_v2_raw.txt`
- `/workspace/.../verification/validation_VJ24*.json` — absent
- `/workspace/.../verification/validation_VJ19_deferred.json`
- `/workspace/.../execute_batch_15_output.json`
- `/workspace/.../execute_batches/batch_15/tasks_35a34c851b8f.json`
- `/workspace/.megaplan/cloud-sessions/critique-ledger-accountability-v3-r5-20260803.liveness-lease.json`
- `/workspace/r5-watchdog-scope-c3b0be1398/watchdog-report.json`
- `/workspace/watchdog-report.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/` — no r5 repair-data request
- r5 dispatch file — absent/empty; filename not stated in the pack
- `.megaplan/cloud-chain-critique-ledger-accountability-v3-r5-20260803.log` — relative remote path only

Remote SHA available: pinned runtime content SHA `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d`. Remote source head: `c116f38cc83de11a1a508eff6153205504d1ba5a`. Remote artifact mtimes/SHA-256 were otherwise not supplied.

## Read-only commands and raw evidence

All commands ran with cwd `/Users/peteromalley/Documents/Arnold`; no mutation, network access, SSH, refresh, restart, or agent launch occurred.

```sh
find . -type f -name '00-common.md' -print
```

Exit `0`; stdout empty.

```sh
for p in arnold_pipelines/run_authority \
  arnold/workflow/wbc_queries.py \
  arnold/workflow/execution_attempt_ledger.py \
  arnold_pipelines/megaplan/custody; do
  if test -e "$p"; then echo "PRESENT $p"; else echo "ABSENT $p"; fi
done
```

Exit `0`; raw result: all four paths `ABSENT`.

```sh
rg -n 'enqueue_repair_request|claim_active_repair_request|save_repair_data|dispatch_kimi_repair|notification|effect_intent' arnold_pipelines/megaplan arnold
```

Exit `0`; relevant matches include:

- `auto.py:2016` — `enqueue_repair_request`
- `repair_requests.py:380` — `claim_active_repair_request`
- `repair_contract.py:1208` — `save_repair_data`
- `arnold-repair-trigger:254` — queue claim
- `arnold-repair-trigger:285` — `subprocess.Popen`
- `arnold-watchdog:4034` — `dispatch_kimi_repair`
- `arnold-watchdog:4099` — `claim_active_repair_launch`
- `arnold-watchdog:929-1071` — escalation/Discord/webhook notification path

```sh
nl -ba .megaplan/initiatives/custody-control-plane/decisions/m10-m11-structural-conformance-closure-20260723.md | sed -n '75,135p'
```

Exit `0`; relevant excerpts:

- C05: request without immutable accepted decision is pending/unknown and unclaimable.
- C06: every effect/authority transition rereads Run Authority, Custody, and WBC.
- C12: request → decision → claim → lease → attempt → effect → terminal/indeterminate → verification.
- C14: repair locks and provider adapters must be migrated behind WBC or remain read-only historical adapters.

Remote raw excerpt from the evidence pack:

```text
state.json current state: blocked
active step: null
execute error: validation job VJ24 references missing selectors that are not declared task outputs
There is no verification/validation_VJ24*.json artifact.
No r5 repair-data request ... and the r5 dispatch file is absent/empty.
```

## Identity join

| Identity class | Joined value |
|---|---|
| Session | `critique-ledger-accountability-v3-r5-20260803` |
| Plan | `cl2-wbc-backed-ledger-20260803-1357` |
| Chain state | `chain-a5c760402ea2.json` |
| Remote source head | `c116f38cc83de11a1a508eff6153205504d1ba5a` |
| Pinned runtime | `/workspace/runtime-candidates/arnold-wbc-full-20260804` |
| Runtime content SHA | `d0fa249a1310cd42920d345e6f664807318bd6fffbe699f1e0f3208563e92c7d` |
| Validation occurrences | VJ2, VJ8, VJ9, VJ19, VJ24 |
| Tasks/sense checks | T18, T23, SC18, SC23 |
| Lease observation | stopped; target PID `610293`; runner fence `11` |
| Binding drift identities | expected/active `e5de49a5ead7`/`117b71d9caf9`; `117b71d9caf9`/`cb6afb801753`; `d0fa249a1310`/`bf86f59d7417` |
| Request/claim/attempt IDs | No durable r5 request, claim, WBC attempt, or repair attempt ID supplied |
| Custody lease/epoch | No canonical Custody lease ID or custody epoch supplied |
| Run revision/occurrence/fingerprint | No complete joinable value supplied |
| Notification/message IDs | None supplied |

## UTC timeline

- `2026-08-03T15:40:52Z` — r5 watchdog scope: `alive_sessions=0`, `status=repair_unavailable`; required claimed repair request absent.
- `2026-08-03T17:52:40Z` — generic watchdog report says `alive`, but is explicitly older/stale and has repair disabled.
- `2026-08-04T10:24:44Z`, `10:24:54Z` — VJ2 exit `None`.
- `2026-08-04T11:27:18Z` — persistent execute attempt blocked after model work.
- `2026-08-04T15:21:17Z` — VJ8 exit `1`.
- `2026-08-04T16:42:29Z`, `16:44:34Z` — DeepSeek unavailable because `DEEPSEEK_API_KEY` was missing.
- `2026-08-04T16:59:49Z` — VJ9 exit `1`.
- `2026-08-04T19:35:41Z` — primary session marker last updated; stale `should_run=true`.
- `2026-08-04T20:30:48Z` — VJ24 deterministic rejection; T18/T23 were not dispatched.
- `2026-08-05` — evidence pack and Sol stage-1 evidence captured locally; local evidence mtimes are `11:12:23Z` and `11:17:55Z`.

## Boundary trace

| Boundary | Existing local path/effect | Adherence finding |
|---|---|---|
| Blocked detection | `auto.py:1932-2001`; watchdog wrapper detection events | Records lifecycle failure, but queue emission is best-effort and not WBC/Custody-bound. |
| Repair request | `repair_requests.py:127-220`; watchdog inline enqueue around `arnold-watchdog:1322` | JSON marker plus decision; no Run Authority grant/fence, WBC refs, run revision, or Custody occurrence/epoch. |
| Claim | `repair_requests.py:380-461`; `repair_lock.py:146-190` | `mkdir` lock and `owner.json` with PID/command/hostname; this is not a renewable Custody lease. |
| Dispatch | `arnold-repair-trigger:254-306`; `arnold-watchdog:4034-4095` | Direct `Popen`/background repair-loop launch after legacy lock checks; no canonical conjunctive action gate. |
| Attempt | `repair_contract.py:1208-1246`; `meta_repair.py:1379-1420`; repair-loop wrapper | Mutable repair-data/meta JSON; no local durable WBC execution-attempt API. |
| State transition | `auto.py:1976` and `write_plan_state`; dependency repair directly writes plan/chain state | Lifecycle mutation is not shown joined to RA/Custody/WBC. |
| Notification | watchdog `needs-human` sidecar, `EscalationLedgerWriter`, Discord DM/webhook at `arnold-watchdog:929-1071`; incident bridge | Notification effects are not joined to a canonical occurrence/version ledger in the inspected implementation. |
| Effect evidence | `arnold/kernel/effect_ledger.py`; `megaplan/observability/effect_ledger.py` | In-memory journal-folding/idempotency model and re-export shim, not the named durable WBC attempt/effect store. |

## Sidecar decision

The sidecars are intended by the baseline to be adapters/projections only:

- `NORTHSTAR.md:165-166` says markers, mutable JSON, logs, process facts, receipts, and status snapshots are evidence/projections.
- The WBC matrix marks legacy chain/status/repair-lock/supervisor readers non-authoritative with zero-reader gates.
- `status_snapshot.py:1001-1030` nevertheless treats fresh repair sidecars as inputs to status classification.
- `repair_contract.py:1215-1245` persists repair-data first and emits the incident-ledger bridge as best effort.
- The watchdog and repair-trigger wrappers use queue markers, PID locks, and sidecar-derived projections to decide or launch repair.

Therefore, they are not proven to be bounded read-only adapters in the current implementation; they remain legacy compatibility writers/readers with authority-increasing influence.

## Positive evidence

- The written contract has the correct single-owner split: Run Authority, WBC, and Custody are compositional, not competing ledgers.
- The local resolver is pure/read-only and the feature flags explicitly describe repair-request markers as “observe-only.”
- The local incident ledger is append-only and the generic effect ledger has idempotency/deduplication primitives.
- The remote run is honestly classified as `blocked`, not successful; T18/T23 were not falsely accepted.
- Runtime drift was emitted rather than silently ignored.

## Bounded negative evidence

Search scope was limited to the current dirty local checkout’s `arnold_pipelines`, `arnold`, and named initiative/evidence files, plus the exact remote paths and statements in the evidence pack. No remote source checkout was inspected.

Within that scope:

- No local canonical Run Authority/WBC/Custody package paths were present.
- No remote VJ24 verification artifact was present.
- No remote r5 repair-data request or dispatch record was present.
- No complete occurrence/request/claim/lease/epoch/WBC-attempt/notification join was available.
- No notification message IDs or durable occurrence/version dedupe records were supplied.

These negatives do not prove that no unlisted remote artifact exists.

## Strongest alternative explanation

The failure may be primarily a plan/worktree/runtime declaration mismatch: VJ19 and VJ24 may have consumed different selector maps, so the system may have intentionally stopped before repair admission.

A falsifying observation would be a durable accepted repair occurrence for the exact VJ24 fingerprint containing the current Run Authority grant/fence, Custody lease/epoch, WBC attempt, claim, dispatch, and typed outcome. The evidence pack explicitly reports no such r5 request/dispatch.

## Sol decision

**Immediate recovery:** preserve VJ24 as the current occurrence and do not resume, rebind, fabricate `test_replay_v2.py`, or treat VJ19 deferral as success. Sol needs an authoritative before-state proving the exact occurrence, Run Authority fence, Custody epoch, WBC attempt, and runtime lineage. If that canonical operation cannot be found, the occurrence must remain quarantined/typed-escalated.

**Durable architecture:** adopt the existing Run Authority/WBC/Custody owners through one custody-complete, occurrence-bound admission/action operation. Retire queue markers, PID locks, repair-data, watchdog, and notification sidecars to fenced adapters/projections with generated zero-authority proof. Do not introduce a second authority or fixer ledger.