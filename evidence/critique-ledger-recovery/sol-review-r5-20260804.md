# Sol review brief: r5 execution block and lease gap

Date: 2026-08-04 UTC
Scope: `critique-ledger-accountability-v3-r5-20260803`, plan
`cl2-wbc-backed-ledger-20260803-1357` on the cloud agentbox.

## Decision requested

Give a firm judgement on (a) why this run stopped, (b) whether the intended
source fix is to update stale tests or to undo the new idempotency behavior,
(c) the safest resume point, and (d) the durable lease/observer fix so a
managed run cannot execute without authoritative custody. Distinguish facts
from inference and do not recommend a blind relaunch.

## Durable evidence

- Cloud process at the time of observation: chain wrapper PID 377534 and
  chain process PID 377538, launched from the pinned runtime
  `/workspace/runtime-candidates/arnold-wbc-full-20260804` at revision
  `c116f38cc83de11a1a508eff6153205504d1ba5a`.
- At 15:18:31Z, `megaplan introspect` showed `display_state=executing`,
  `execution_state=executing`, `active_phase=execute`, attempt 6,
  model `zhipu:glm-5.2`, liveness `progressing` (“last event 1s ago”),
  `latest_failure=null`, an in-flight `llm_call_start`, and event sequence
  9223 with fresh token-heartbeat events. `doctor` separately reported phase,
  LLM liveness, cost, and no orphan process as OK.
- The active step initially had no `runner_lease`. The marker lease file was
  still bound to a dead earlier PID 373187 and had expired at 14:26:20Z.
  The launch command exported `ARNOLD_REPAIR_SESSION` but the managed lease
  startup failure is swallowed, so the chain was allowed to run unbound.
- As containment only, a liveness lease sidecar was attached to the already
  live PID 377538 at 15:20:48Z. It created runner fence 8, target PID 377538,
  and renewed successfully. This did not restart or duplicate the chain.
- The chain then exited/block-recorded at 15:21:17Z. At 15:24:48Z the chain
  PID and sidecar were both gone. `state.json` is authoritative:
  `current_state=blocked`, with `latest_failure.kind=pre_dispatch_validation_failed`,
  `phase=execute`, `job_id=VJ8`, `exit_code=1`,
  `retryable_infrastructure=false`, `worker_dispatched=false`,
  `suggested_action=Repair the failing validation gate before resuming execute.`
- The exact gate command was:

  ```text
  timeout 120s pytest tests/arnold/workflow/test_attempt_ledger_store.py \
    tests/arnold/workflow/test_attempt_ledger_static_negative_checks.py \
    --tb=short -q --tb=no --no-header -rA
  ```

  It returned 1. Re-running against the stopped worktree produced 126 tests:
  122 passed and 4 failed. All four failures are legacy expectations that a
  divergent event with the same idempotency key silently deduplicates:

  - `test_append_dedups_on_duplicate_idempotency_key`
  - `test_duplicate_of_pre_terminal_event_returns_existing_after_terminal`
  - `test_duplicate_of_terminal_event_returns_existing`
  - `test_dedup_does_not_persist_duplicate_row`

  Each now raises `arnold.workflow.attempt_ledger_store.IdempotencyConflictError`
  with “already exists with divergent canonical content.”
- The worker’s durable batch-5 notes say T6 intentionally added
  `IdempotencyConflictError` and a shared `canonical_event_json` helper, and
  explicitly says divergent same-key retries must raise; it also says the
  outbox path was not yet completed and T4 was not started. The plan’s critique
  flags likewise require content-safe divergence rather than silent dedup.
- The same worker notes report a stale editable-runtime import problem during
  foreground verification: `arnold.workflow` resolved to
  `/workspace/runtime-candidates/arnold-4ed98585fda8c76a8ebfba04b856b6aa9b685a47-live`
  instead of the session worktree. The exact re-run from the worktree does
  import the worktree and exposes the four semantic expectation failures above.
- Current worktree inspection shows `arnold/workflow/attempt_ledger_store.py`,
  `arnold/workflow/ledger_outbox.py`, and tests are dirty. The helper is
  imported by the outbox, but `canonical_event_json` is not currently
  re-exported from `arnold.workflow` despite the worker note claiming it was.

## Constraints

- Do not treat fresh event/token sidecars as custody authority.
- Do not kill/relaunch a process while an exact live runner is still active.
- Do not mutate the blocked plan’s state by hand; resume only through its
  typed recovery path after the gate contract is repaired.
- Preserve completed batches T1–T3 and the partial T6 evidence; do not silently
  discard or replay them.

## Questions Sol must answer

1. Is `IdempotencyConflictError` the correct contract and are these four tests
   stale, or is the implementation wrong? What exact minimal test/code changes
   should be made before resume?
2. Does the uncompleted outbox path make T6 unsafe to accept even after the
   four expectation tests are updated? What is the smallest coherent repair?
3. Can this plan resume from the typed VJ8 block without restarting T1–T3,
   and what receipt/evidence checks must be performed first?
4. What launch invariant prevents a managed chain from running when lease
   acquisition fails? Recommend the precise fail-closed startup/lease handoff,
   stale-owner recovery, and observer classification changes.
5. Give a short ordered recovery plan and identify anything that must remain a
   follow-up rather than being smuggled into this resume.

## Fresh evidence gathered after cancelling the first Sol review

- The authoritative cloud observation at `2026-08-04T15:37:00Z` is no longer
  executing: `introspect` reports `plan_state=blocked`,
  `display_state=blocked`, `execution_state=blocked`, `active_phase=null`,
  `liveness=stalled`, and `block_details.recoverable_via=["recover-blocked"]`.
  The event journal's last event is `2026-08-04T15:21:17.996Z`; there is no
  chain process and no sidecar. This answers the immediate question: it is not
  cooking now.
- The current marker is not authoritative for a live run:
  `runner_pid=null`, `runner_start_identity=null`, `lease=null`, last marker
  update `2026-08-04T14:21:43Z`. The target container itself is healthy and has
  325G free on its host-backed `/workspace` volume. A separate, old container
  named `megaplan-cloud-agent` is exited with a historical Docker-rootfs
  `no space left on device` error; it is not the r5 target and must not be
  confused with the active target container.
- The current introspect payload retains a stale unmatched `llm_call_start`
  from `2026-08-04T14:23:35Z` (GLM-5.2) even though the phase is null, the
  process is gone, and the state is blocked. This is telemetry/projection
  residue, not evidence of a live model call. It is a second control-plane
  smell: terminal/block transitions must close or quarantine in-flight-call
  records.
- The exact VJ8 command was rerun in the cloud worktree with the pinned runtime.
  It completed in 11.67s with `126` tests total: `122 passed`, `4 failed`.
  Running only the four failures shows all raise
  `arnold.workflow.attempt_ledger_store.IdempotencyConflictError` from
  `_append_tx` because the same key's canonical event content differs. The
  tests currently assert silent deduplication. This is a deterministic source
  contract mismatch, not a provider outage, timeout, or worker-dispatch failure.
- The plan history shows a pattern rather than a single incident: three
  critique attempts failed structural validation before one succeeded;
  finalize had six invalid-schema rejections, then a missing-required-field
  structural audit failure, a usage-limit failure, and later a successful
  Sol finalize; execute then hit four `VJ2 exited None` validation failures,
  a blocked state, and finally the current `VJ8 exited 1` block. The system did
  preserve these typed history entries, but notification/observer surfaces did
  not collapse them into one incident lineage.
- The pinned r5 config confirms the intended routing is
  `profile=partnered-5-glm`, execute via `hermes:zhipu:glm-5.2`, and finalize
  via `codex:gpt-5.6-sol:high`. The current VJ8 failure happened before any
  execute worker was dispatched (`worker_dispatched=false`), so changing the
  execute model cannot fix this gate.

## Additional questions for the consolidated Sol judgement

6. Given the fresh VJ8 reproduction, decide whether the four tests should be
   rewritten to assert content-safe divergence, or whether the implementation
   should preserve legacy silent deduplication. Treat the plan brief's
   “content-safe” and “divergent same-key retry raises” language as binding
   evidence, not as an assumption.
7. Decide whether stale in-flight LLM telemetry after a blocked terminal state
   is merely an observer bug or evidence that recovery could accidentally
   resurrect an old call. Recommend the smallest fail-closed repair.
8. Account for the repeated critique/finalize/VJ2 failures as one incident
   lineage: what should be automatic retry/fixer behavior, what should be a
   hard block, and how should notifications be deduplicated?
9. State the shortest safe path from the current typed block to a resumed run,
   including the exact evidence gates for the test-contract repair, outbox
   completion, runtime/lease custody, and one clean VJ8 pass.

## Luna cross-checks (fresh, read-only)

- Credential/lifecycle audit: the current r5 launcher has the GLM/Zhipu keys and
  base URLs in its isolated empty-parent-env probe; the pinned runtime is
  `/workspace/runtime-candidates/arnold-wbc-full-20260804` at `c116f38`. The
  routing ledger shows 8/8 post-13:47 calls selecting and actually using
  `hermes:zhipu:glm-5.2`, with no fallback. The stale “missing
  OpenAI credentials” message belongs to an earlier 13:47 relaunch artifact,
  not the VJ8 failure.
- State-machine audit: `state.json` and the VJ8 artifact independently prove a
  deterministic pre-dispatch block (`126 passed, 4 failed`,
  `worker_dispatched=false`, `retryable_infrastructure=false`). The stale
  chain-health/session projections still say gated/running, while introspect
  says blocked; status surfaces are therefore reading incompatible projections.
  The observer/doctor surface also omits the decisive `latest_failure` detail
  and suggests a generic force-proceed path, which is unsafe for a validation
  block.
- The state-machine audit additionally found T6's `ledger_outbox.py` write not
  represented in its declared write set and outbox tests not yet run. It
  recommends an occurrence-scoped `recover-blocked` bound to the VJ8 fingerprint
  and repair commit, never a generic force-proceed, followed by a fresh lease,
  one clean VJ8/outbox/static-suite pass, and projection/notification refresh.
- Route/control-plane audit: the lease gap was real at launch (managed lease
  acquisition failure was swallowed); attaching a sidecar later proved only
  liveness, not startup custody. The invariant must be fail-closed: no chain
  process may dispatch or mutate plan state until it holds a marker-bound lease
  for its exact PID/start identity/container/fence. Stale owners need an
  explicit fenced handoff, not a marker overwrite.
- Recovery audit found another concrete state-machine smell: the current
  `state.json` VJ8 block is newer and has `resume_cursor.retry_strategy=
  repair_validation_failure`, but the older `phase_result.json` still says
  `exit_kind=external_error`. The `_external_error_requires_resume` helper
  consults that stale phase result as well as the latest failure, so
  `recover-blocked` may misclassify this deterministic validation failure and
  demand a generic `resume`. Recovery must bind to the newest failure
  occurrence (or reject stale phase results) before choosing a transition.
- Route/observer audit adds two status-surface facts: the target container's
  PID 1 is only an HTTP health server, not the chain runner; and the resident
  container/watchdog snapshot writer is not a durable chain supervisor. The
  `/opt/.../.megaplan/status/cloud-status.json` snapshot is stale (generated
  2026-08-03 18:10Z) and the watchdog sweep stopped around 17:51Z, explaining
  `/whats-cooking` stale/duplicate “running” reports. A stale `phase_result.json`
  also carries the old missing-OpenAI-credentials narrative despite successful
  GLM calls later in the same run. Status must join artifacts by occurrence ID
  and freshness, never display an old provider error as the current cause.
- A later blocker-recovery inspection reports `can_continue=false` and
  `has_terminal_blockers=true`: synthetic U1 prerequisite blockers cover the
  pending tasks with zero recorded resolutions, and a quality blocker reports
  that `finalize.json` still has pending tasks without authoritative execution
  updates. Therefore `recover-blocked` is not a generic resume button even
  after VJ8 is repaired. The U1/quality evidence must be resolved or explicitly
  scoped by an approved transition; it must not be marked resolved merely to
  bypass the gate.

## Sol execution constraint

The evidence above is complete. Make the judgement from this brief only; do
not inspect the repository or launch tools. Return a firm, concise decision
(contract choice, safe recovery order, and durable fixes), with no code edits.

## Sol judgement (GPT-5.6 Sol, high reasoning; 2026-08-04)

Sol's firm conclusion: VJ8 is a deterministic pre-dispatch validation failure,
not a model, credential, container, disk, timeout, or worker failure. The
`IdempotencyConflictError` behavior is correct and the four legacy tests must
be updated to distinguish identical-content deduplication from divergent
same-key rejection. T6 is not yet coherent: finish the outbox integration,
declare `ledger_outbox.py` in the write set, resolve the public export claim,
and run ledger + outbox + static-negative suites together.

Sol's safe order is: preserve T1-T3/T6 receipts; make an immutable repair
identity; prove the pinned runtime import; obtain one clean VJ8 plus outbox and
static-suite pass; bind recovery to the newest VJ8 occurrence/fingerprint and
reject the stale external-error phase result; resolve U1/quality blockers
without fabricating resolutions; acquire a fresh marker-bound fenced lease;
then invoke occurrence-scoped `recover-blocked` and resume execute. Do not
force-proceed or relaunch blindly.

Sol's durable invariant is fail-closed startup: no managed chain may read or
advance execution state, dispatch a worker, or emit `executing` until the exact
PID/start identity/container/session owns a current marker-bound fenced lease.
Lease acquisition/renewal errors must stop dispatch, stale-owner takeover must
be an explicit fenced CAS, and observers must classify fresh events without a
matching lease as unowned activity/custody violation. Terminal/block
transitions must quarantine unmatched LLM telemetry; status and notifications
must join by occurrence ID and freshness. Automatic repair is appropriate for
bounded schema/provider failures, but deterministic VJ8 remains a hard source
block with one deduplicated incident lineage.
