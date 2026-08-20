# T1.9 bounded v3 zero-recovery canary — exact implementation brief

Date: 2026-08-02  
Mode: read-only implementation preparation; no source, Git, cloud, provider,
owner, process, or release mutation

## Verdict

**READY for one bounded code lane, but not launch-ready.** Implement the
accepted T1.9 launch transaction and finite runner under one explicit profile,
`ZERO_RECOVERY`. Keep the production handle unavailable until the accepted
dependency ports, the provider/preflight receipt, and an actual externally
authenticated T1.8 production authority are frozen into one clean installed
generation.

The resulting canary has exactly one path:

```text
one immutable input upload
-> one exact runner start
-> init -> plan -> critique -> gate -> finalize
-> one exact target-transition CAS
-> deny all new effects
-> one exact process stop
-> STOPPED_FENCED
-> SUCCEEDED_CLOSED
```

It has no `prep`, `revise`, `execute`, `review`, tiebreaker, override, second
finalize, second milestone, generic command, Git/ref/PR, product deploy,
refresh, package install, retry, automatic relaunch, fixer, notification,
diagnostic, resident, watchdog, timer, or direct-provider route. Every error or
uncertainty enters fence/stop and makes zero T1.5/T1.10 calls.

Controlling records:

- T1.9 v2 specification, SHA-256
  `9a604b05637d2f9eba54db6a6f42e488e2d2979105a6b0d1d6dcb5665688ad11`.
- T1.9 independent specification PASS, SHA-256
  `c3378830a6866ebaedb618a0a466bd6198900f7c74523596f925a25e60c39669`.
- zero-recovery route adjudication, SHA-256
  `abe9d64aeb0a35f81ec5fa72b804471a2b2307e34210b993163575a7090e2f47`.
- accepted T1.8 commit
  `06d41e6b7148db4e5b464131762d63fd697db056`, tree
  `a8a67b2e01b9129673afdc7931cb3ffdce03a2de`; root adjudication SHA-256
  `9fdb7ebf585aeddc0571b726cefcda9d3fdb5cae52d8d3f512999c688af1db2b`.
- common recovery ancestor
  `6787d6363e8fc0603092913ae877db14f3b9fff8`.

## 1. The one permitted profile

Add a closed enum in `arnold/launch/contracts.py`:

```python
class RecoveryCapabilityProfile(str, Enum):
    ZERO_RECOVERY = "ZERO_RECOVERY"
```

`ZERO_RECOVERY` is not an omitted dependency and not a passing T1.5/T1.10
canary. It changes the v2 records as follows:

- `BuildInterfaceManifest` records T1.5 and T1.10 as
  `NOT_CONSUMED_OPERATIONAL_CANARY`, with their HARD-FAIL/deferred evidence
  digests. It contains no T1.5/T1.10 endpoint, implementation, key, or success
  receipt.
- `StageAProductionGoManifest.recovery_capability_profile` is exactly
  `ZERO_RECOVERY` and carries current owner-signed deny receipts for recovery,
  fixer, initial notification, reminder, chunk, diagnostic, resident,
  watchdog, and direct notification-provider families.
- Budgets for those families are exactly zero, and their capability/GLEK,
  credential, worker, timer, service, wrapper and fallback sets are empty.
- The only mutating effect families are `input-upload=1`, `runner-start=1`,
  the separately accepted bounded model-attempt set, and `runner-stop=1`.
  Process observation is read-only. The launch WBC operation identities (and
  any T1.6 child GLEKs required by the accepted upload/start/stop contract) are
  not recovery GLEKs and may name only those three launch operations.
- `StageALaunchSeed` and `StageALaunchEnvelope` bind the zero-recovery deny-set
  digest. They have no recovery/notification parent, child derivation, provider
  binding, recipient, payload, credential, worker or scheduling field.
- Any unknown field, positive recovery budget, recovery/notification GLEK,
  credential, unit, timer or import changes the canonical digest and is rejected
  before Launch Authority append, reservation, filesystem write, process start
  or provider call.

This distinction is required by the accepted v2 contract: `ZERO_RECOVERY`
means zero **recovery/notification** GLEKs, credentials and workers. If “no
GLEKs” is instead intended literally across upload/start/stop too, stop and
revise the accepted T1.9/T1.6 interface; silently removing those exact launch
operation identities would discard the specified no-redispatch mechanism.

Do not silently delete the v2 positive-fixer fields. Make the profile a closed,
canonical schema choice and make the verifier prove the negative capability
graph. `NOT_CONSUMED_OPERATIONAL_CANARY` can never satisfy a T1.5/T1.10
completion query.

## 2. Exact files and responsibilities

### Add — launch owner

| File | Exact responsibility / public symbols |
| --- | --- |
| `arnold/launch/__init__.py` | Lazy public value types and opaque handles only. No backend, key, socket, path, provider, callback or test constructor. |
| `arnold/launch/contracts.py` | Strict frozen canonical records from T1.9 v2, plus `RecoveryCapabilityProfile`, typed dependency dispositions and zero-capability deny receipts. Reject aliases, unknown/duplicate fields, noncanonical IDs and mixed heads. |
| `arnold/launch/ports.py` | `RunAuthorityPort`, `CustodyPort`, `EffectDispatcherPort`, `ReleaseAuthorityPort`, `ReservationOwnerPort`, `IndependentProcessObserverPort`. No recovery or notification port. |
| `arnold/launch/repository.py` | Owner-local `append(expected_head, event, operation_id)`, `read_head()`, `read_operation_receipt(operation_id)`. Never caller-root SQLite or implicit store initialization. |
| `arnold/launch/reducer.py` | The v2 append-only state machine. Reject gaps, rollback, conflicting operation bytes and illegal transitions. `SUCCEEDED_CLOSED` is reachable only through `STOPPED_FENCED` for this profile. `EXPIRED_FENCED`, `FAILED_FENCED`, `TARGET_CURSOR_INDETERMINATE` and `QUARANTINED` are failures, not canary success. |
| `arnold/launch/replay.py` | `resolve_owner_operation()`; exact operation-receipt lookup only. A projection/current head/log/marker never proves an operation. |
| `arnold/launch/transaction.py` | `execute_launch(handle)`, `reconcile_launch(transaction_id, challenge)`, `request_stop(stop_handle)`. The failure helper persists failure/fence and calls only the stop saga; it must not import T1.5/T1.10. |
| `arnold/launch/stop.py` | `advance_stop_saga()` with WBC deny, runner fence, RA fence, Custody advance, one stop `STARTED`, and exact process reconciliation. Never `pkill`, PID grep, tmux name, container destroy or provider down. |
| `arnold/launch/runner_guard.py` | `claim_phase`, `record_phase_outcome`, `accept_target`; use the fixed external owner and process-bound context. No environment/marker/JSON/Python-token authority. |
| `arnold/launch/verifier.py` | Recompute the complete current owner join. Enforce `ZERO_RECOVERY`, exact zero recovery effects, the finite cursor budget, the exact target receipt, and exact stopped process. |
| `arnold/launch/client.py` | Server-authenticated opaque launch/stop client only. |
| `arnold/launch/production.py` | Sole `production_launch_client()` composition. It reads only Release-Authority-pinned installed configuration; it accepts no caller-selected socket/root/provider/key/backend. Missing composition returns typed unavailable before mutation. |
| `arnold/launch/cli.py` | `execute`, `reconcile`, `stop`, read-only `status`, `schema`, `contract-digest`; optional `prepare` is pure and grants no authority. |
| `tests/arnold/launch/fakes.py` | All fake ports/backends. Test selection cannot be exposed through production constructors or environment variables. |

### Add — finite runner

`arnold_pipelines/megaplan/stage_a_runner.py` exposes only:

```python
run_stage_a_slice(opaque_handle: str) -> StageASliceResult
```

It obtains a process-bound context from the fixed owner, then calls exactly
`handle_init`, `handle_plan`, `handle_critique`, `handle_gate`, and
`handle_finalize`, once each and in order. It must not import `auto.drive`,
`run_chain`, `run_epic_chain`, supervisor launch, execute/review handlers, Git
operations, cloud deploy, recovery or notification modules. A handler response
requesting `prep`, `revise`, repeat, skip, execute, review, tiebreaker, override
or another milestone is a typed slice failure followed by fence/stop.

The runner's `except`/cancellation/expiry path is structurally:

```text
record launch/slice failure
-> persist FENCE_INTENT_DURABLE
-> deny except already-bound stop/reconcile
-> advance_stop_saga
-> return FAILED_FENCED or QUARANTINED
```

There is no recovery adapter lookup and no exception fallback.

### Modify — point-of-use closure

| Existing file/symbol at `6787d...` | Required narrow change |
| --- | --- |
| `arnold/cli/__init__.py::main` | Add `arnold launch-authority ...` dispatch to `arnold.launch.cli`; do not add a console script. Preserve other Arnold commands. |
| `arnold_pipelines/megaplan/handlers/init.py::handle_init` | Call the shared installed-generation guard on the first executable line, before `ensure_runtime_layout()` at line 327. The guard claims `init` before directory/layout creation. |
| `handlers/plan.py::handle_plan` | Guard before `load_plan_locked()` at line 156; no lock, worker or artifact before the claim. |
| `handlers/critique.py::handle_critique` and `orchestration/critique_runtime.py::handle_critique` | Guard both the exported wrapper and canonical implementation. A direct import of the runtime implementation must not bypass the claim. Keep `handle_revise` unavailable. |
| `handlers/gate.py::handle_gate` | Guard before `load_plan_locked()` at line 925. Any route other than the one accepted gate-to-finalize transition stops. |
| `handlers/finalize.py::handle_finalize` | Guard before `load_plan_locked()` at line 2219. Add a Stage-A-only pure evidence branch in `_write_finalize_artifacts`: use owner-stored immutable base/test-selection inputs and make zero calls to `_resolve_evidence_base_ref`, `_current_plan_changed_files`, `_capture_git_status_snapshot_recursive`, `_capture_test_baseline_for_plan`, suite runners or subprocess. The current code otherwise runs Git at lines 1308-1346/2109 and may run the test suite at lines 855-879/2120, violating this canary's no-command boundary. Final artifacts remain local unpublished bytes until the exact target CAS is accepted/replayed. Any T1.4 rejection/repair need stops; no revise route. |
| `runtime/manifest_backend.py::MegaplanManifestBackend` | Under the pinned Stage-A registry, the allowed handler set is only `plan`, `critique`, `gate`, `finalize`; `init` is runner-owned. At `_execute_node_payload` lines 116-122, an unknown/unlisted ID must fail, not complete as a neutral pass-through. `_resolve_handler` must not construct mappings containing prep/revise/execute/review/tiebreaker/override for this profile. `build_megaplan_registries` must reject recovery/notification extra capabilities/effects. |
| `arnold_pipelines/megaplan/cli/__init__.py::main` | In the installed Stage-A generation, reject every mutating raw command before `maybe_auto_sync_repo_editor_support()` at current line 3460 and before `_setup_chain_worktree`. Permit only documented read-only status/schema routes. A caller flag/environment value cannot select Stage-A mode. |
| `arnold_pipelines/megaplan/auto.py::run_auto` and `drive` | Typed `AUTHORIZED_LAUNCH_REQUIRED` before `_apply_local_auto_engine_default` or any state/process mutation. This is a demonstrated residual bypass not named in the v2 file list. |
| `chain/__init__.py::{run_chain,run_chain_cli}` | Reject start/plan/execute/resume/fresh and child launch before state/worktree/process mutation. Read-only status remains. |
| `chain/epic_chain.py::{run_epic_chain,run_epic_chain_cli}` | Same early denial; never start a child chain. |
| `supervisor/chain_runner.py::run_chain` | Same early denial before supervisor state/event/process mutation. |
| `cloud/cli.py::run_cloud_cli` | Add one `authorized-stage-a-launch` action check before `_load_cloud_spec()` / `_provider_for_action()` (current lines 569-570), accepting only an opaque handle and delegating to `production_launch_client()`. It may not instantiate `SshProvider` or any provider. All legacy chain/bootstrap/fresh/tmux/deploy/exec/resume/down/destroy/repair routes remain unavailable in the Stage-A generation; read-only observation/preflight stays separate. |
| `cloud/providers/ssh.py::{build,deploy,down,destroy,ssh_exec,upload_file,upload_archive}` and `_maybe_route_through_wbc` | The installed reachability scan already proves this direct leaf: `_maybe_route_through_wbc` currently calls `apply_fn` when its adapter is `None` (lines 295-298), while `build`/`deploy` bypass the helper entirely when no adapter is supplied. Under the fixed Stage-A generation, reject before SSH/filesystem/process mutation unless an external accepted dispatcher supplies the exact pre-bound launch child. A caller-created `SshProvider` or missing adapter is never direct-fallback authority. Preserve ordinary non-Stage behavior outside the dedicated generation. |

Generate the installed reachability inventory after these shared guards. Patch
an additional leaf only when the inventory proves a mutation path reaches
around them. Do not blanket-edit provider, recovery, notification, model or
release packages, and do not resurrect a retired wrapper.

## 3. Required owner interfaces

Use the v2 ports exactly. The minimum call direction is:

```text
Launch Authority
  -> RunAuthorityPort: revalidate, exact target CAS, fence, read receipt
  -> CustodyPort: read current lease, advance fence, read receipt
  -> EffectDispatcherPort: reserve exact launch child, STARTED once,
     dispatch registered upload/start/stop once, reconcile, deny except stop
  -> ReservationOwnerPort: exact absence reservation + exact receipt replay
  -> ReleaseAuthorityPort: current installed-generation attestation only
  -> IndependentProcessObserverPort: exact PID/birth/cgroup-or-unit/vector
```

No port may return a boolean success. Every mutation has a stable operation ID,
canonical request/result digest, owner incarnation, predecessor/head/sequence
and authenticated receipt. After any child is `STARTED`, reconciliation may
adopt exact applied evidence but never dispatch it again. Definite
`NOT_APPLIED` is failed/fenced, not retry authority. `UNKNOWN` is sticky and
quarantined.

The finite slice may claim a cursor beyond v2 only if the current GO join also
contains the accepted exercised T1.2 terminal-attempt receipt, T1.3 raw
target-bound bundle receipt and scoped T1.4 graph-admission/terminal-rejection
contract. Their absence may still prove one runner started/stopped, but it may
not produce the target CAS or `SUCCEEDED_CLOSED`.

## 4. Exact T1.8 consumption boundary

The accepted T1.8 implementation provides the canonical shapes in
`arnold_pipelines/release_authority/contracts.py`:

- `GenerationVector` (lines 204-297), including source/image/runtime,
  lockfiles, installed provenance, `.pth`, imports, wrappers, services,
  configuration, state, contract/routes, role bindings and components;
- `RoleProcessBirth` and `ProcessAttestation` (lines 937-1000); and
- typed selector/runtime/writer operation receipts (lines 1003-1081).

Its read-only observation protocol is
`release_authority/executor.py::ReadOnlyObservationAdapter` (lines 110-122).
Its external production evidence shapes are
`production.py::{ProductionAuthorityBinding,AuthenticatedDiscoveryEvidence,
ExternallyAuthenticatedProductionAuthority}`.

T1.9's `ReleaseAuthorityPort.attest_current_generation()` must return an opaque
owner-authenticated receipt binding the exact accepted `GenerationVector`,
`ProcessAttestation`, selected generation, old-writer rejection, adapter/peer,
challenge, current owner head and expiry. T1.9 may verify that receipt; it may
not call `execute_deployment`, `HermeticAdapter`, `DeploymentStore`, select a
generation, install bytes, start services or construct the evidence dataclasses
as authority.

Critical availability gate: accepted T1.8 intentionally ships no production
integration. `release_authority/production.py::discover_production_authority()`
always raises `production_authority_integration_missing`, and
`verifier.py::verify_deployment()` rejects owner-installed mode with
`production_observation_adapter_missing`. Therefore a positive production GO
handle is impossible until a separately accepted privileged venue adapter and
observer implement the accepted contract. Local/hermetic T1.8 tests are not a
substitute.

## 5. Provider observation/preflight boundary

The current bounded provider candidate is in
`/private/tmp/arnold-critique-recovery-cloud-observation-preflight-20260802`
and was still uncommitted/unaccepted during this inspection. Freeze its eventual
commit/tree before using it. The intended interfaces are:

- `cloud/providers/ssh.py::SshProvider.observe_container()`;
- `SshProvider.observe_prelaunch_capacity()`;
- `ssh_preflight.py::classify_container_inspect()` producing
  `arnold.cloud.ssh_container_observation.v1` with
  `running|stopped|paused|restarting|missing|unknown`, image/exit/OOM/error and
  exact `/workspace` bind;
- `workspace_prelaunch_command()` and
  `parse_workspace_prelaunch_result()` producing
  `arnold.cloud.ssh_workspace_prelaunch.v1`; and
- the configured floors in `cloud/spec.py::ResourcesSpec` and `load_spec()`.

Before any deploy/start mutation, Release Authority must bind fresh canonical
digests of both observations. Required GO predicates are exact configured bind,
sufficient bytes/inodes/receipt reserve, reserve fsync, SQLite WAL/FULL/checkpoint,
atomic receipt+directory fsync, cleanup, and a typed quota result. Any stale,
unknown, non-running collector state, mount mismatch, shortfall, cleanup error
or unreadable field is NO-GO.

The inspected candidate currently tests bytes, inodes, fsync, WAL and receipt
reserve, but contains no explicit quota field or quota test. Close that in the
provider lane or record a venue-authenticated proof that `f_bavail/f_favail`
are already quota-limited; do not let T1.9 infer quota health. T1.9 consumes the
Release-Authority-bound receipt digest only and never performs SSH/Docker or
constructs a provider.

The inspected preflight is also a separately invoked CLI observation; it is
not yet causally bound to `run_cloud_cli(... deploy ...)`. The separately
accepted privileged T1.8 deploy composition must require the exact fresh
preflight receipt before its first mutation. Merely having run `cloud
preflight` earlier, or embedding its JSON in a caller-provided GO manifest, is
not that binding.

## 6. Transaction and phase invariants

1. Resolve the owner-issued opaque handle; rejoin all current heads, deadline,
   provider-preflight receipt and installed-release receipt before the first
   Launch Authority append.
2. Reject if the selected generation contains any recovery/notification
   credential, service, worker, timer, wrapper, GLEK or callable route, or if
   the old v2 recovery/notification grants/GLEKs/services are not fenced.
3. Reserve every raw and normalized identity as the v2 ordered fail-closed
   saga. `COLLISION` or `UNKNOWN` never deletes/adopts/resets/releases a name.
4. Persist upload intent and exact child; mark `STARTED`; dispatch the seeded
   bytes once; independently read back bytes and identity. Never redispatch.
5. Persist start intent and exact child; claim slot; mark `STARTED`; dispatch
   the fixed installed argv/cwd/environment once. Never redispatch.
6. Bind one exact process birth to slot and pre-issued stop before issuing the
   `init` phase token.
7. For each phase, claim ordinal/predecessor/current heads, call the guarded
   handler once, and record exact dependency/outcome receipts. Any unexpected
   route signal stops.
8. Precommit the exact target operation. Lost response is resolved by exact
   operation receipt, never by a later head or state projection.
9. Persist `FENCE_INTENT_DURABLE` immediately after exact target acceptance;
   deny all new children; complete the stop saga.
10. `SUCCEEDED_CLOSED` requires the exact target receipt, one upload, one start,
    five exact ordered phase outcomes, zero recovery/notification intents and
    calls, and an independently observed exact stopped process with a complete
    stop receipt. Expiry alone does not satisfy this canary's exact-stop goal.

Manual supervision is read-only. Re-executing the same envelope is replay, not
a relaunch. A later canary requires an exact fenced terminal state plus a new
owner decision, seed, envelope, names, slot and operation identities. Any
unknown process/effect/stop truth forbids relaunch.

## 7. Hostile tests

Add the v2 test files unchanged in ownership, with these zero-recovery cases:

### Contract/GO tests

- `tests/arnold/launch/test_contracts.py`: canonical vectors; duplicate,
  alias, unknown, wrong-case and noncanonical fields; positive recovery budget,
  any recovery/notification capability/GLEK/credential/service/worker/timer or
  fallback rejects.
- `test_authority_provenance.py`: caller-minted/wrong-key/stale/cross-venue/
  cross-candidate handles and caller-selected production paths make zero owner,
  reservation, filesystem, process and provider calls.
- `test_production_go_join.py`: missing/stale/unaccepted T1.2/T1.3/scoped-T1.4,
  T1.8 production integration, provider preflight, v2 fence or zero-capability
  deny receipt rejects before reservation. T1.5/T1.10
  `NOT_CONSUMED_OPERATIONAL_CANARY` is accepted only with the exact zero graph
  and never reported as a pass.

### Replay/crash/stop tests

- `test_repository_and_owner_replay.py`, `test_reservation_saga.py`,
  `test_transaction_crashes.py`, `test_response_loss.py`,
  `test_stop_and_expiry.py`, `test_target_cas_replay.py`: crash/ENOSPC/
  cancellation/response loss before and after every append, owner CAS,
  WBC/provider boundary, observation, target CAS, deny/fence and stop step.
  Two and 200 concurrent execute/reconcile callers produce one reservation set,
  one upload, one start and one stop; no `STARTED` effect is redispatched.
- Wrong/multiple/zero PID, PID reuse, birth/cgroup/unit/argv/cwd/env/input/GLEK/
  generation mismatch and observer disagreement issue no phase token.
- Stop response loss queries the exact operation/process only. Broad kill,
  container removal, new stop operation or renewed run authority is forbidden.

### Runner/guard/no-effect tests

- `test_runner_guard_and_budget.py`: exact five-phase order and once-only
  budget; direct imports of every wrapper/canonical handler reject before lock,
  layout, model or file mutation; prep/revise/execute/review/tiebreaker/override,
  skip/repeat/second-finalize/second-milestone all stop.
- Inject failure at entry and after model/result/artifact boundaries of all five
  phases. Assert `FENCE_INTENT_DURABLE`, stop advancement, zero imports/calls to
  T1.5/T1.10, zero recovery/notification intents, and zero provider messages.
- Monkeypatch subprocess, Git helpers, suite runner, recovery, notification,
  Discord/webhook and direct provider constructors to fail if called. A full
  successful Stage-A slice must leave every counter at zero except the bounded
  model route and exact upload/start/stop.
- 200 read-only observations make zero provider calls and no owner transition
  except observation receipts.

### Boundary/installed tests

- `tests/integration/test_stage_a_launch_boundary_closure.py`: exercise raw
  Megaplan init/phase/auto/resume/chain/epic/supervisor, `--fresh`, cloud
  bootstrap/chain/tmux/deploy, watchdog/repair/diagnostic/notification and
  direct module aliases under the installed Stage-A generation. Every mutation
  alias returns typed denial before its first write/process/provider call;
  read-only status remains available.
- Generate and hash a reachability inventory over Python modules, `python -m`
  entrypoints, `pyproject` scripts, shell wrappers, Docker/template output,
  systemd services/timers and materialized installed files. Require no recovery
  or notification credential binding and no active resident/watchdog/timer.
- `tests/installed_wheel/test_stage_a_launch_authority.py`: compare source,
  fresh wheel, isolated installed `python -P` from outside the repository,
  `arnold launch-authority`, thin cloud adapter and materialized wrappers for
  identical schema/help/contract digest, error code and critical file hashes.
  Confirm there is no second console script and no source-tree import leakage.
- Run the full accepted T1.8 release-authority suite and installed probes on the
  composite wheel; keep wrong-target rollback and minimum-Pydantic checks.
- Run the provider-preflight hostile tests, including stdout-only failure,
  injection-safe identifiers, malformed/unknown lifecycle, bind mismatch,
  quota unknown/limited, capacity shortfall, WAL/fsync/cleanup failures, and
  stopped-container short-circuit before `docker exec`.

Use exact receipts and call counters as oracles. Logs, status, markers, bot
prose and file existence are never acceptance evidence.

## 8. Packaging and installed-generation rules

- Merge accepted T1.8's complete lineage, not only its tip. Preserve
  `hatchling==1.27.0`, `pydantic>=2.11,<3`, `cryptography>=42`, the build group,
  `arnold-gen-deploy`, and its installed-wheel fixture behavior.
- The existing Hatch wheel package list already includes `arnold` and
  `arnold_pipelines`; the new packages need no new console entrypoint.
- Add only the `arnold launch-authority` subcommand. The cloud adapter is a
  subcommand of the existing Megaplan/cloud CLI.
- Regenerate `uv.lock` once only after all accepted base-lane dependency edits
  are composed. Never splice locks.
- `GenerationVector.wrappers`, `.services`, `.configuration`, `.imports`,
  `.role_bindings`, `.routes_digest` and `.components` must cover the actual
  launch owner/client, finite runner, process observer and zero-recovery
  registry. Old recovery/notification/watchdog/resident processes are rejected
  writers, not omitted observations.

## 9. Conflict map from `6787d...`

| Input/lane | Exact base-relative files | T1.9 conflict/disposition |
| --- | --- | --- |
| Accepted T1.8 `06d41e6...` | Adds `arnold_pipelines/release_authority/**`, bootstrap, docs/tests/probes; modifies `pyproject.toml`, `tests/installed_wheel/conftest.py`, `uv.lock` (26 files, +13,788/-35). | No textual overlap if T1.9 adds no script and extends the installed suite in a new file. Preserve T1.8 packaging and consume its types; do not edit its executor/store to fake production availability. |
| Current provider-preflight candidate | Modifies `cloud/providers/ssh.py`, `cloud/spec.py`, `cloud/templates/cloud.yaml.tmpl`; adds `cloud/providers/ssh_preflight.py`, `tests/cloud/test_ssh_prelaunch_observation.py`. | No current textual overlap with the planned T1.9 `cloud/cli.py` adapter, but semantic overlap at status/preflight dispatch. Recompute after the provider commit freezes; preserve host observation short-circuit and keep launch adapter provider-free. |
| Accepted T1.3 `2f1500ae...` | Overlaps `handlers/finalize.py` and `orchestration/critique_runtime.py`; also modifies worker/model/package files and `pyproject.toml`. | High semantic conflict. Phase claim precedes lock/model/capture; T1.3 authenticated result precedes scoped T1.4 admission and target CAS. Preserve T1.3 package-data globs with T1.8 pins. |
| Provisional T1.1 `3ed353f...` / later scoped RA composition | Overlaps `handlers/init.py`, `handlers/finalize.py`, `chain/__init__.py`, `supervisor/chain_runner.py`, and Run Authority exports. | Do not implement T1.9 on a separate base branch and later choose one side. Build on the exact accepted scoped RA composite; phase claim is first, then target-bound RA admission/current-head checks. T1.1 remains unaccepted as observed here. |
| RA-CONTAIN `48e13e1...` | `run_authority/__init__.py`, containment, tests, `pyproject.toml`, `uv.lock`. | Preserve lazy containment exports. Resolve dependencies with T1.8's stricter cryptography pin and one regenerated lock. |
| T1.2/scoped T1.4/T1.6 | Currently specifications rather than accepted implementation ports. | Real production target CAS is unavailable until their exercised receipt/effect ports freeze. T1.9 may implement against protocols/fakes, but must keep production GO typed unavailable rather than absorb or counterfeit these owners. |

Single highest-risk join:
`handlers/finalize.py::handle_finalize`. Required order is:

```text
T1.9 phase claim/current-head check
-> target-bound RA admission
-> plan lock/load
-> sole bounded model effect
-> T1.3 authenticated raw capture
-> T1.2 terminal attempt receipt
-> scoped T1.4 graph admission (no repair in ZERO_RECOVERY)
-> pure/no-Git/no-test-command final artifact bytes
-> precommitted exact target CAS/replay
-> publish only the pre-bound local artifacts/projection
-> T1.9 deny/fence/exact stop
```

An automatic textual merge is not acceptance of that order.

## 10. Sole-lane execution order and stop gates

1. Create a clean worktree from the frozen integration base descended from
   `6787d...`; record commit/tree and all accepted component ancestry.
2. Freeze provider/preflight commit/schema/tests and the actual privileged T1.8
   production adapter/observer endpoint. If either is absent, code may proceed
   against protocols/fakes but production execute stays unavailable.
3. Freeze strict contracts/golden vectors and the ZERO_RECOVERY negative graph.
4. Implement repository/reducer/exact replay, then signed issuance and complete
   GO verification with no provider adapter.
5. Implement reservations and stop saga; exhaust crash/response-loss tests.
6. Bind only accepted upload/start/observe/stop and model ports; implement one
   happy path. No T1.5/T1.10 import or optional fallback.
7. Add finite runner, handler guards and the no-Git/no-test-command finalize
   path.
8. Close raw CLI/auto/chain/epic/supervisor/cloud bypasses; generate installed
   reachability inventory and patch only proved residuals.
9. Build one wheel and run source/wheel/installed/materialized hostile parity.
10. Obtain a fresh independent review. It may accept the local candidate but
    cannot authorize cloud mutation until current owner heads, provider
    preflight, production T1.8, v2 fencing, installed live-vector attestation
    and fresh signed v3 seed/envelope all exist.

This lane makes no claim that T1.5/T1.10 pass, that automatic recovery or
notification exists, that a cloud deployment occurred, or that ordinary
execute/publication/product authority is available. The exact canary
notification count is zero.
