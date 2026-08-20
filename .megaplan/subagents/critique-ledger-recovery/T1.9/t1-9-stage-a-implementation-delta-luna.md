# T1.9 Stage-A launch/stop implementation delta — Luna

Status: read-only coding handoff; **not implemented, deployed, launched, or complete**. SHA-256 is recorded in the parent handoff.

## Finite outcome

After the accepted T1.1, T1.5, T1.6, and T1.8 interfaces freeze, implement one owner-installed launch transaction for one fresh v3 critique-ledger successor. It binds one clean integration commit/tree and one already-installed T1.8 generation; reserves every launch identity; durably records WBC parent/child intents for exact input upload, process start, and exact stop; starts at most one canonical runner; allows only the ordered `init -> plan -> critique -> gate -> finalize` phase slice; accepts exactly one Run Authority transition strictly beyond the frozen v2 `gated/finalize` cursor; then fences and stops or expires.

This transaction has no authority for execute, Git/ref publication, PR creation, product deployment, a second milestone, source refresh, package installation, an alternate model route, or relaunch. The direct `cloud chain --fresh`, raw `chain start`, tmux, marker, watchdog, supervisor, resident, and provider-shell launch paths are unavailable in the Stage-A installed generation.

## Frozen inputs and owner ports

Record one integration manifest before coding the adapter. It must contain exactly one accepted commit/schema/endpoint tuple for each dependency and one candidate commit/tree/package vector:

- **T1.1:** fixed production Run Authority/admission client; `AdmissionReservationRequest`, accepted reservation/revalidation receipt, grant/revision/fence, authoritative cursor ordering, deterministic successor plan identity, and collision result. T1.9 consumes these; it never recomputes CL1 or instantiates local SQLite.
- **T1.5:** fixed singleton recovery-owner endpoint/schema and topology digest. The simple fixer is not a launcher. The manifest proves all resident/meta/watchdog/delegation launch authority is absent.
- **T1.6:** fixed exclusive dispatcher; `EffectEnvelope`, parent/child GLEK derivation, durable `RESERVED/STARTED/terminal/INDETERMINATE` states, registered upload/process capabilities, and independent reconcile port. No raw provider callback is accepted.
- **T1.8:** fixed Release Authority selection and live-vector attestation for the exact installed interpreter, entrypoint, package files, capability registry, process observer, generation digest, and source commit/tree. T1.9 may verify this generation; it may not deploy, refresh, install, or select another one.

If any port, endpoint, schema/help/contract digest, commit, tree, or generation differs from the frozen manifest, production `execute` is absent rather than degraded. Build T1.9 only on one clean integration descendant containing all four accepted commits; never copy dirty worktree diffs or accept multiple candidate generations.

## Minimal contracts

Add the neutral contract beside the accepted T1.6 owner boundary (use `arnold/workflow/` if that remains the frozen package layout):

```text
StageALaunchSeed
  schema + contract digest; seed ID/digest; issued/expires times
  integration commit + tree; wheel/package vector; installed generation digest
  immutable spec/input manifest: exact bytes, size, digest, destination
  fresh session/workspace/plan/branch/worktree/state/marker/runner-slot identities
  frozen v2 cursor + ordering digest; exact successor target transition
  ordered phase allowlist [init, plan, critique, gate, finalize]
  transition/cursor budget; one runner; no_refresh=true
  accepted T1.1 admission reservation/receipt digests
  topology, effect allowlist, absence-domain and stop-capability digests

StageALaunchEnvelope
  seed digest; fixed owner endpoint and venue identity
  RA grant/revision/fence/cursor/expiry
  Custody occurrence/lease/epoch/fence/expiry
  T1.6 parent launch attempt/GLEK/store generation
  exact child intents/GLEKs for UPLOAD, START and STOP
  T1.8 selection/attestation and process-observation challenge
  reservation manifest/cursors; monotonic deadline; one runner-slot claim
  pre-issued StageAStopCapability ID/digest

StageAStopCapability
  one-use identity; seed/grant/fence/lease/epoch/generation/runner-slot binding
  precommitted stop parent/child GLEK and exact allowed stop operations
  observed PID + process birth/cgroup or unit identity once start is adopted
  deny-new-effects, revoke/fence, terminate-exact-process, verify-absence only

StageALaunchReceipt
  append-only owner state/head; reservations; child intents/outcomes
  uploaded-byte verification; runner-slot/process attestation
  phase/cursor budget consumption; stop/expiry result; evidence digests
```

All records use strict canonical encoding: unknown/duplicate fields, non-finite times, aliases, malformed IDs, stale cursors, mixed owner heads, and signature/digest disagreement fail closed before a provider call. The installed production client uses one compiled/fixed owner endpoint and opaque handles; no CLI flag, environment variable, socket path, callback, or test backend can replace it.

## Transaction and state machine

Use one append-only owner transaction; do not claim filesystem/process atomicity:

```text
PREPARED
 -> AUTHORITY_VALIDATED
 -> IDENTITIES_RESERVED
 -> UPLOAD_INTENT_STARTED
 -> UPLOAD_VERIFIED | INDETERMINATE
 -> START_INTENT_STARTED
 -> RUNNING_VERIFIED | INDETERMINATE
 -> PHASE_SLICE_ACTIVE
 -> TARGET_CURSOR_ACCEPTED
 -> STOP_INTENT_STARTED
 -> STOPPED_FENCED | INDETERMINATE

Any pre-effect rejection -> FAILED_PRE_EFFECT
Any expiry before/within the slice -> EXPIRED_FENCED -> STOP_INTENT_STARTED
Any collision/read disagreement -> QUARANTINED (zero cleanup, zero launch)
```

Ordering is mandatory:

1. Validate current RA, Custody, WBC, Release/generation, admission, TTL, topology, and stop capability against the same frozen manifest.
2. Transactionally reserve fresh normalized and raw identities for workspace, session, remote input destination, deterministic plan/path, branch/ref, worktree registration/path, chain state/marker, runner slot, occurrence/GLEKs, and disabled publication namespace. A collision is durable evidence: never delete, reset, clean, overwrite, adopt by name, or retry with the same identity.
3. Persist the parent launch intent and exact upload child manifest/GLEK; reread coherent owner heads; dispatch the immutable seeded bytes once through T1.6; read back and verify bytes/durable object identity.
4. Persist the exact structured start child manifest/GLEK; reread heads; CAS-claim the one runner slot; dispatch once through T1.6. Start argv binds installed interpreter/entrypoint, cwd, allowlisted environment digests, seed, grant/fence, lease/epoch, GLEK, generation, TTL, and stop fence. The runner validates them before initialization.
5. Admit only the finite phase/cursor capability described below. Every accepted transition consumes the same envelope; no command or handler can mint/renew it.
6. On target acceptance or expiry, atomically deny new effects and persist the pre-issued stop child intent before any terminate call. Revoke/fence RA, advance/fence Custody, terminalize future WBC, stop only the exact observed process birth, verify absence, and preserve all evidence.

## Exact finite phase/cursor budget

Freeze the target from the accepted installed state schema, not from a string comparison at runtime. The envelope carries the frozen v2 owner cursor, its ordering/schema digest, the fresh v3 start cursor, the ordered phase allowlist, and one exact terminal target—normally the owner transition `gated/finalize -> finalized`, or the installed schema-equivalent whose accepted cursor is strictly greater than v2's last accepted cursor.

The runner may initialize v3 and invoke only `handle_init`, `handle_plan`, `handle_critique`, `handle_gate`, and `handle_finalize`, in that order, through the owner-aware chain driver. T1.2/T1.3 own the one configured physical critique route and authenticated result; scoped T1.4 owns its at-most-one admitted narrow graph repair. T1.9 merely enforces their frozen receipts and the envelope budget.

Before every phase and transition, the runner rereads the current grant/fence, lease/epoch, generation, WBC state, deadline, predecessor cursor, phase ordinal, and remaining budget. It rejects skips, repeats, backwards/equal cursor claims, execute, a second finalize/milestone, or any transition after the target. The owner CAS that accepts the first v3 cursor strictly beyond v2 simultaneously consumes the terminal cursor token and fences all further phase authority. Success is not process liveness or a `finalize` return; it is that owner receipt followed by confirmed exact stop/expiry. Failure before the target safely stops but does **not** satisfy Stage A and cannot auto-relaunch.

## Response loss: reconcile, never redispatch

Once T1.6 records an upload/start/stop child as `STARTED`, any timeout, cancellation, disconnect, owner-write ambiguity, process death, or missing acknowledgement is sticky `INDETERMINATE`. Reinvoke only `reconcile(transaction_id, child_GLEK)` against the fixed independent owner/provider observer:

- **Upload:** exact seeded object bytes/identity may be adopted; authoritative proof of definite `NOT_APPLIED` may resume the same GLEK only under the frozen T1.6 rule while all authority is current; mismatch/unreadable/unknown quarantines. Never upload again.
- **Start:** exactly one process matching slot, birth, argv/env/cwd, seed, generation, fences, GLEK, and input digest may be adopted. Zero is actionable only with authoritative proof the request did not apply; duplicate/wrong/incomplete/unknown invokes the pre-issued fence/stop path. Never issue a second start.
- **Stop:** reconcile exact process birth and owner fence/lease/WBC heads. Unknown stays fenced and visible; no broad `tmux kill-session`, name/PID grep, container destroy, or relaunch.

## Exact files and seams

### Add under the frozen neutral owner package

- `arnold/workflow/launch_contracts.py` — strict `StageALaunchSeed`, envelope, reservations, budget, stop capability, receipts, canonical vectors.
- `arnold/workflow/launch_transaction.py` — append-only reducer, reservation saga, upload/start/stop orchestration, terminal fencing.
- `arnold/workflow/launch_owner_client.py` — fixed production endpoint and opaque-handle client; visibly hermetic constructor only in tests.
- `arnold/workflow/launch_reconciliation.py` — exact upload/process/stop observation and sticky unknown reducer.
- `arnold/workflow/launch_verifier.py` — independent join over RA/Custody/WBC/generation/process/cursor/stop heads.
- `arnold/workflow/launch_cli.py` — installed `arnold-launch-authority {execute,reconcile,stop,status,schema,contract-digest}`; `status/schema/digest` are read-only and `prepare` is optional pure canonicalization only.

### Modify narrowly

- `arnold_pipelines/megaplan/cloud/cli.py`: add one byte/digest-pinned thin adapter; retire `_build_chain_start_command`, `_megaplan_refresh_command`, `_tmux_chain_launch_command`, `_tmux_epic_chain_launch_command`, `_tmux_chain_restart_command`, and mutation in `_run_chain_wrapper` for Stage A. `quickstart --launch/--fresh`, `cloud chain`, `launch-epic`, `epic-chain`, `resume`, and `supervise` cannot launch.
- `cloud/providers/base.py`, `ssh.py`, `on_box.py` (and `local.py` if included in installed composition): expose only registered structured upload/start/observe/stop capabilities to T1.6; ordinary callers retain read-only observation, not arbitrary shell/upload/process mutation.
- `cloud/operator_control.py` and `cloud/supervise.py`: remove marker-command resume, session-name kill/restart, wake, refresh, and relaunch authority; route exact stop/status only.
- `cloud/template.py`, `cloud/templates/entrypoint.sh.tmpl`, materialized wrappers and service/watchdog templates: install/start the accepted owner and observers only; no boot-time chain, resident, watchdog, repair, agent, or supervisor launcher.
- `chain/__init__.py`: raw `chain start` and `--fresh` reject before plan/worktree/state mutation without a current opaque owner capability; remove fresh cleanup from the authorized route.
- `chain/epic_chain.py::_default_start_child_chain`: unavailable in this generation; no child or second milestone.
- `supervisor/chain_runner.py::run_chain`, `ChainMilestonePackRunner`, and `drivers/in_process.py` / `drivers/subprocess_isolated.py`: require the envelope, runner-slot attestation, and budget at entry and before each transition; stop immediately after target acceptance/expiry.
- `handlers/init.py::handle_init`, `plan.py::handle_plan`, `critique.py::handle_critique`, `gate.py::handle_gate`, `finalize.py::handle_finalize`: consume owner-issued phase tokens/receipts at the earliest mutation seam; none accepts a marker, projection, environment flag, or synthesized capability. Execute/override/recovery handlers cannot enter the Stage-A route.
- Packaging/entrypoints in the accepted CLI layout (`arnold/cli/__init__.py`, Megaplan `__main__`, wheel manifests): install the fixed client and preserve source/wheel/`python -P` schema/help/digest parity.

Also hard-deny or omit `scripts/cloud_hot_upload.py`, manual/meta repair triggers, six-hour/progress-auditor mutation, managed-agent/resident launch, watchdog ensure/restart, generic cloud exec, and any copied wrapper capable of reaching the raw transports. Discovery output must not advertise a runnable legacy alias.

## Finite tests

Add:

- `tests/arnold/workflow/test_launch_contracts.py`
- `tests/arnold/workflow/test_launch_owner_client.py`
- `tests/arnold/workflow/test_launch_reservations.py`
- `tests/arnold/workflow/test_launch_transaction_crashes.py`
- `tests/arnold/workflow/test_runner_slot_and_attestation.py`
- `tests/arnold/workflow/test_stop_transaction.py`
- `tests/integration/test_launch_boundary_closure.py`
- `tests/installed_wheel/test_launch_authority_entrypoint.py`

The finite matrix must prove: all missing/stale/forged/mixed owner inputs make zero calls; fresh-name alias/collision/corruption/read-error cases never clean; concurrent launch requests produce one slot and one start; crash/ENOSPC/response loss before and after every owner commit/provider boundary never redispatches; exact upload/start/stop adoption works and conflicting evidence stays indeterminate; PID reuse/wrong generation/argv/env/cwd rejects; TTL expiry fences and stops; the ordered phase budget reaches exactly one owner-accepted cursor beyond v2 then denies execute/second transition; finalizer safe failure stops without a success claim; all raw launch/restart/provider/wrapper aliases fail before mutation; source, fresh wheel, installed `python -P`, fixed executable, adapter, and materialized wrappers expose identical schema/help/digest and rejection codes.

Run focused owner contract vectors first, then reservation/concurrency/crash reconciliation, runner/phase budget, exact stop, bypass closure, and installed parity. Existing cloud-chain command, quickstart, epic-chain, chain-worktree safety, SSH deploy/provider, hot-upload, editable-install, watchdog, manual-repair, progress-auditor, T1.5 topology/retirement, and T1.8 generation tests remain regressions only where their Stage-A mutation paths now hard-deny.

## Dependency and coding order

1. Freeze accepted T1.1/T1.5/T1.6/T1.8 commits, schemas, fixed endpoints, digests, capability registry, and one clean integration commit/tree/generation manifest.
2. Add strict contracts, golden vectors, pure budget/reducer, fresh-reservation model, and pre-issued exact stop capability.
3. Implement durable owner state and fixed client; prove crash/corruption/unknown behavior before any provider adapter.
4. Register only exact input-upload, one-runner start/observe, and exact-stop effects through T1.6. Implement reconciliation and stop before the happy path.
5. Enforce runner-slot, generation/process attestation, and the finite phase/cursor budget in the canonical runner/handlers.
6. Add the thin cloud adapter; structurally retire every raw launch/restart/fresh/tmux/marker/watchdog/provider bypass.
7. Prove source/wheel/installed/materialized parity, concurrency/fault tests, and the isolated finite canary. Independent review may accept only owner receipts; it must not infer completion from status, logs, marker, or bot messages.

## Deferred generalization

Defer multi-host/multi-venue launch, endpoint discovery, owner failover, lease renewal, multiple runners, arbitrary chain/epic shapes, second milestones, execute, Git/ref/PR/publication, product deploy, source/runtime promotion, hot upgrade, generic SSH/subprocess custody, broad provider APIs, watchdog/resident/supervisor restart, all model routes, universal owner-store migration, and historical-state migration. These are `UNAVAILABLE_IN_GENERATION` until separately owned and proven; they do not fall back to legacy behavior.

No code, Git, cloud, provider, process, owner, checklist, release, branch, worktree, or existing session state was mutated. The only written artifact is this implementation-delta report.
