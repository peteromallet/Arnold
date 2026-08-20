# T1.9 Sol preparation — one owner-authorized launch/stop transaction

**Status:** read-only implementation preparation; no implementation, test, cloud,
provider, process, owner, or release mutation was performed. This is not a T1.9
completion claim and it does not unblock T6.1.

**Recovery ancestor:** `6787d6363e8fc0603092913ae877db14f3b9fff8`

**Governing plan:**
`docs/arnold/critique-ledger-incident-prevention-and-durable-recovery-plan-2026-08-02.md`
(especially dependency table lines 97 and 123–124, T1.9 lines 354–367,
T6.1 lines 520–526, and runbook R4–R9 lines 1437–1615).

## Executive conclusion

T1.9 must not add a guard around `cloud chain --fresh`, tmux, raw `chain start`,
or the current provider APIs. Those surfaces are already the bypass. At the
recovery ancestor, one composite shell path can refresh or replace source,
upload mutable inputs, delete state, write a marker that contains a relaunch
command, start a tmux process, and then ask a watchdog to recognize it. No
authoritative owner transaction reserves all successor names, proves absence at
the point of use, binds the installed generation, records intent before each
effect, starts at most one runner, or reconciles a lost start acknowledgement.
The stop/restart paths are string/session based and do not revoke the exact
grant, lease, epoch, fence, GLEK, generation, and process birth that launched the
runner.

The missing boundary is a **neutral, owner-installed launch authority service**.
Megaplan may be a thin policy adapter, but it must not own or mint production
launch authority. The owner service consumes one immutable `LaunchSeed`, joins
Run Authority, Custody, exclusive WBC, Release Authority, and venue absence
reservations, durably records intent, uploads the exact approved bytes, and
claims one canonical runner slot. It returns either independently verified
success, a proven pre-effect rejection, or a non-redispatchable
`INDETERMINATE`. Before launch, it also issues and verifies the exact
`StopCapability` that can fence/revoke the same identity and stop only the
observed process birth while preserving evidence.

The implementation is not safe to begin from the dirty dependency worktrees as
if their interfaces were final. Sol must first obtain accepted, frozen owner
ports from T1.1, T1.5, T1.6, and T1.8 and create a clean integration lineage
from those accepted commits. In particular, the current T1.8 repair is
uncommitted/unaccepted and production mutation still deliberately lacks a
privileged adapter. T1.9 can implement hermetic/non-production conformance and
an isolated canary, but it cannot honestly claim a production launch path until
the production owner compositions exist.

## What the evidence proves

### 1. Governing requirements are stricter than “launch safely”

The plan requires T1.9 to consume, in one transaction:

- launch seed;
- Run Authority grant, revision, and fence;
- Custody occurrence, lease, and epoch;
- WBC attempt and intent;
- exact runtime generation;
- absence/collision proof;
- a scoped TTL;
- a pre-issued revoke/fence/stop capability bound to the same identity.

It must start at most one canonical runner, perform no source/runtime refresh,
fail rather than clean collisions, and avoid watchdog custody. T1.9 ends at an
installed CLI/API, contract/help digest parity, negative tests, and an isolated
non-production canary. The actual production successor launch is T6.1 and is
blocked by all predecessors. R6 explicitly says there is currently no safe
executable launch syntax and forbids filling one in until the installed command
and digest exist.

This means the implementation must model a fail-closed cross-owner saga, not
claim an impossible distributed filesystem/process transaction. Unknown owner
state, read failure, response loss, collision, or verifier disagreement must
deny or quarantine authority rather than select a retry path.

### 2. The ancestor launch path is a composite bypass

At `6787...:arnold_pipelines/megaplan/cloud/cli.py`:

- parser regions `:110–330` expose quickstart `--launch/--fresh`, `cloud chain`,
  `launch-epic`, `epic-chain`, source-refresh switches, and force-clean;
- `_build_chain_start_command` around `:2359–2390` builds raw
  `python -P -m arnold_pipelines.megaplan chain start`;
- `_megaplan_refresh_command` around `:2414–2524` fetches/checks out/pulls,
  may reset/clean/push, performs an editable install, and selects a runtime;
- `_tmux_chain_launch_command` around `:2535–2595` treats a tmux/marker match as
  already running or writes the marker and executes `tmux new-session`;
- `_tmux_epic_chain_launch_command` around `:2702–2737` repeats the pattern;
- `_tmux_chain_restart_command` around `:2740–2781` kills and restarts the
  session by name;
- `_run_chain_wrapper` around `:3400–3680` syncs the editable source branch,
  uploads inputs before a durable launch intent, optionally resets state for
  `--fresh`, writes a relaunch marker, starts tmux, and then requires watchdog
  tracking.

The fresh reset is materially unsafe for this task: it removes chain state and
the current plan directory before proving a collision-free successor. Raw
worktree `--fresh` behavior in
`6787...:arnold_pipelines/megaplan/chain/__init__.py` can likewise remove an
existing registered worktree/branch. A collision must instead be a stable,
preserved fact that rejects the new launch.

The marker/tmux check is not an owner CAS and cannot resolve response loss. If
the start applied but the SSH response disappeared, a retry can observe stale,
partial, aliased, or unrelated tmux/marker state. The code has no durable
runner-slot claim tied to process birth and generation, so “already running” is
not proof that the intended exact runner is the one that started.

### 3. Existing stop/resume paths do not stop or resume an identity

At `6787...:arnold_pipelines/megaplan/cloud/operator_control.py`, pause kills a
tmux session and repair-loop PIDs and edits `should_run`; resume reads the
marker’s relaunch command, flips `should_run`, and starts tmux. It does not
verify a current Run Authority grant, Custody lease/epoch, WBC GLEK, installed
generation, launch TTL, or exact process birth.

Other active surfaces are equally outside an owner transaction:

- `cloud/supervise.py` imports `_tmux_chain_restart_command` and can refresh,
  restart, or wake the chain;
- `cloud resume` reads a projected `next_step` and executes a phase command;
- `chain/epic_chain.py::_default_start_child_chain` invokes raw child
  `chain start`;
- `cloud/wrappers/arnold-chain` directly invokes raw `chain start`; `mp-chain`
  delegates to it;
- `cloud/template.py` and `cloud/templates/entrypoint.sh.tmpl` start agent,
  heartbeat, watchdog, resident, supervise, or chain tmux sessions;
- watchdog/systemd ensure scripts and repair/meta/auditor/manual-trigger paths
  can restart or spawn work;
- `scripts/cloud_hot_upload.py` is a direct code promotion/copy surface;
- `cloud/providers/ssh.py` and `cloud/providers/on_box.py` expose raw shell,
  upload, service/container, and filesystem mutation capabilities.

`cloud down` and `cloud destroy` are deployment/container lifecycle operations;
they are not a substitute for exact runner stop. `cloud exec`, raw SSH, and
attach-like command tunnels cannot remain capable of launching, killing, or
writing around the transaction merely because the ordinary command is gated.
Read-only status, logs, preflight, and observation can remain separate provided
their transports are structurally incapable of mutation.

### 4. T1.1 provides admission vocabulary, not a production launch owner

The current uncommitted T1.1 worktree is
`/private/tmp/arnold-critique-recovery-t1-1-admission-20260802` at `6787...`.
Its useful frozen-candidate concepts are:

- `arnold_pipelines/run_authority/admission.py:140` — strict
  `AdmissionTarget`;
- `:307–368` — `AdmissionReservationRequest` and record binding raw predicate
  and evidence digests, source/spec/brief/chain-state hashes, deterministic
  intended plan ID, runtime generation, expected authority revision/fence,
  idempotency, nonce, and expiry;
- `arnold_pipelines/run_authority_store.py:72–120` — production owner backend
  abstraction/attestation that fails closed when absent;
- `:128+` — local SQLite is explicitly non-production;
- `megaplan/chain/prerequisite_admission.py:484–572` — reserve and revalidate
  the successor before materialization.

T1.9 must consume an accepted production admission reservation/receipt through
the frozen owner client. It must not inject an in-process SQLite object or
duplicate the raw-CL1 predicate. The current T1.1 CLI composition still does
not itself install the production owner backend, so this is a real dependency,
not a paperwork check.

### 5. T1.5 fixes recovery topology, not launch authority

The current uncommitted T1.5 worktree is
`/private/tmp/arnold-critique-recovery-simple-fixer-20260802` at `6787...`.
It introduces `arnold/recovery/simple_fixer.py` with:

- fixed schema `arnold-recovery-owner-v1` and fixed socket
  `/run/arnold/recovery-owner-v1.sock` (`:29–30`);
- a strict recovery occurrence/F01 identity and `AuthorityEnvelope` joining Run
  Authority, Custody lease/epoch/fence, and WBC attempt/GLEK (`:148+`);
- forbidden delegation/scheduler/command/callback/queue fields;
- a production client with no environment/path/local fallback (`:270–322`);
- an explicitly test-only hermetic owner (`:326+`);
- durable intent and non-redispatchable `INDETERMINATE` handling.

T1.9 must bind the accepted singleton simple-fixer owner socket/schema/topology
into its `LaunchSeed`. The fixer’s ordinary recovery envelope is not a launch
grant and must not be widened into one. T1.9 also must not revive the
heartbeat/watchdog/meta-repair/managed-child topology that T1.5 is retiring.

### 6. T1.6 must own effects beneath the transaction

`.megaplan/subagents/critique-ledger-recovery/T1.6/t1-6-sol-implementation-brief.md`
requires one neutral exclusive effect dispatcher. Every irreversible launch or
stop effect must be a registered effect family and require current Run
Authority, Custody occurrence/lease/epoch, immutable generation, and WBC GLEK
before durable intent. There can be no optional adapter, caller-supplied
`apply_fn`, direct fallback, or exception-to-`FAILED` ambiguity.

T1.9 owns the launch/stop lifecycle and its identity. T1.6 owns the exclusive
capability to perform its upload, process-start, process-stop, and any other
external effects. Composite operations use stable child GLEKs; T1.9 must not
create a second dispatcher or retain raw provider calls behind it.

### 7. T1.8 must attest the exact installed generation first

The T1.8 worktree is
`/private/tmp/arnold-critique-recovery-gen-deploy-bootstrap-20260802`. Its HEAD
is `dae901e9bf2ecf289ad0aa201c50116f8bf1f899`, with an additional uncommitted
repair pass. The candidate vocabulary in
`arnold_pipelines/release_authority/contracts.py` includes:

- `GenerationVector`: source commit/tree/root, image, interpreter/venv,
  dependency locks, import roots, wrappers, services, config/state/contract
  bundles, routes, role bindings, and component digests;
- `MutationBinding`: owner capability, exact target/anchor/store/generation,
  expected selector/revision/fence, expiry, and idempotency;
- owner-installed versus hermetic `AuthorityAnchor`;
- deployment and recovery decisions/envelopes.

The prior independent review rejected the clean candidate for a second
hermetic lock domain and non-executable recovery. The current repair is not yet
accepted. More importantly, production mutation deliberately fails because the
privileged production adapter/observer is not installed. T1.9 must verify an
accepted Release Authority selection and process attestation; it must not
deploy, fetch, pip-install, hot-upload, or select a generation itself.

## Exact contract Sol should implement

### A. Owner boundary and installed surface

Place the domain-neutral contract beside the frozen T1.6 owner boundary, not
under Megaplan policy. The final package location should follow the accepted
T1.6 layout; if it remains `arnold/workflow`, suggested modules are:

```text
arnold/workflow/launch_contracts.py
arnold/workflow/launch_owner_client.py
arnold/workflow/launch_transaction.py
arnold/workflow/launch_reconciliation.py
arnold/workflow/launch_verifier.py
arnold/workflow/launch_cli.py
```

Install one fixed production executable, recommended as
`arnold-launch-authority`, with only typed subcommands:

```text
prepare       # pure canonicalization only; no target read or mutation
execute       # submit a signed owner envelope/opaque handle
reconcile     # observation/reconciliation of the same transaction identity
stop          # submit the pre-issued exact StopCapability
status        # owner record only; read-only
schema
contract-digest
```

An `arnold cloud authorized-launch` command may be a byte/digest-pinned thin
adapter to that client. It may not accept arbitrary owner socket, root,
executable, command, provider, environment, callback, or test adapter options.
Production composition uses a fixed owner endpoint and opaque owner-issued
handle. Hermetic fakes are available only from visibly test-only constructors
and cannot be selected by the installed production command.

The source checkout, built wheel, `python -P` installed runtime, all materialized
wrappers, `--help`, `schema`, and `contract-digest` must expose exactly the same
schema and digest. T6.1 remains blocked until the exact installed syntax and
digest are inserted into R6.

### B. `LaunchSeed`

The seed is canonical, strict (unknown/duplicate fields reject),
content-addressed, and signed or referenced by the owner envelope. It contains:

1. Schema version, contract digest, seed ID/digest, creation time, bounded
   expiry, environment, and non-production/canary scope.
2. Exact successor identity: session, chain/initiative, workspace, remote spec
   destination, deterministic plan ID/path, branch/ref, worktree registration
   and path, chain-state/marker identity, runner-slot ID, and publication
   namespace. Every identity includes normalized and raw bytes where aliasing
   matters.
3. Exact spec blob bytes digest/size, durable input manifest digest, source
   evidence digests, expected remote destination, and the post-upload verifier
   challenge. The uploader may not normalize or regenerate bytes after seed.
4. Accepted T1.1 admission reservation ID/digest, raw predicate decision and
   evidence receipt digests, intended plan ID, expected first transition, and
   owner cursor.
5. Exact T1.8 generation digest/vector digest, Release Authority selection and
   attestation receipt digests, interpreter/entrypoint identity, and source/runtime
   `no_refresh=true` invariant.
6. Topology digest: exactly one canonical runner and the accepted singleton
   simple-fixer service/schema/socket; watchdog, L2/meta fixer, managed child,
   relauncher, and heartbeat launch authority are forbidden.
7. Complete absence domain set and authoritative venue/owner identities.
8. Pre-issued `StopCapability` digest.

Seed changes always create a distinct signed seed; a caller cannot mutate the
same launch identity in place or reuse the old absence observation.

### C. `LaunchAuthorityEnvelope`

The execute request carries or references one immutable envelope containing:

- seed ID/digest;
- Run Authority owner ID, grant ID, capability limited to canary initialize plus
  first ordinary CL2 transition, grant revision, fence, issue/expiry, and owner
  cursor/store incarnation;
- Custody occurrence ID, lease ID, epoch, fence, lease expiry, and owner cursor;
- T1.6 WBC parent attempt ID, parent GLEK, durable intent ID/digest, store
  generation, and declared child-effect manifest digest;
- T1.8 generation and process-attestation challenge;
- venue owner/adapter ID and runner-slot reservation namespace;
- exact scoped TTL and monotonic deadline representation;
- absence reservation manifest and cursors;
- pre-issued stop capability ID/digest;
- independent verifier identity/query/challenge and all owner signatures.

All fences must be coherent under the frozen owner contracts. A string called
“grant”, marker, projection, local SQLite row, environment flag, or unsigned
JSON cannot satisfy the type. Owner adapters are mandatory; missing, stale,
timeout, split-brain, corrupt, unreadable, or disagreeing records yield zero
provider/process calls.

### D. Absence and collision are transactional reservations

A signed list saying “absent at preflight” is not launch authority. R4’s remote
probe is read-only information; T1.9 must reread and reserve targets immediately
before intent/effect through the authoritative venue/owners.

Reserve the complete set atomically where one owner can, and as a fail-closed
saga across owners where it cannot:

- workspace root and canonical path;
- session and canonical runner slot;
- remote spec destination;
- deterministic plan identity/directory;
- branch/ref and remote publication ref;
- worktree registration and canonical path;
- chain state and session marker identity;
- launch parent GLEK/child GLEKs;
- publication namespace/PR reservation;
- any provider/container/cgroup/unit identity used by the runner.

Each result is `ABSENT_RESERVED`, `COLLISION`, or `UNKNOWN`; only the first can
advance. Read error, permission error, corruption, dangling/escaping symlink,
case-fold or Unicode alias, stale owner cursor, duplicate registration, partial
object, or more than one match is collision/unknown, never absence. No launch
path may unlink, reset, clean, overwrite, adopt-by-name, or retry under the same
name. A safe retry after a true pre-effect failure needs a new explicitly signed
seed/name or an exact replay of an unexpired committed reservation under owner
rules.

Reservation TTL expiration fences new effects; it does not prove the targets
became absent. Claims must be released only when authoritative observation
proves zero effect and the contract permits release. Evidence is preserved.

### E. State machine and intent-before-effect

Use an append-only owner state machine such as:

```text
PREPARED (pure, no authority)
  -> AUTHORITY_VALIDATED
  -> TARGETS_RESERVED
  -> LAUNCH_INTENT_DURABLE
  -> SPEC_UPLOAD_DISPATCHED
  -> SPEC_UPLOADED_VERIFIED
  -> RUNNER_START_DISPATCHED
  -> RUNNING_VERIFIED

Any stage may instead enter:
  FAILED_PRE_EFFECT
  INDETERMINATE
  STOPPING
  STOPPED_FENCED
  QUARANTINED
```

Do not label the whole saga atomic. Before every irreversible child effect:

1. derive the stable child GLEK from parent GLEK, seed, effect family, exact
   target, exact bytes/argv, generation, and contract digest;
2. persist the complete child manifest and intent through the T1.6 owner;
3. reread current grant/fence, lease/epoch, generation selection, reservation,
   TTL, and stop fence;
4. dispatch only through the T1.6 exclusive capability;
5. durably record raw response and typed outcome;
6. independently observe before advancing the saga.

The upload effect writes the exact seeded spec/input bytes to a reserved
destination and fsyncs or obtains the venue’s durable equivalent. The verifier
must read back the remote blob and compare its digest/size to the seed before a
start intent can be accepted.

### F. Runtime/source no-refresh and canonical runner

The start request is structured, not an arbitrary shell string. It binds:

- accepted installed interpreter path and interpreter digest;
- `-P`/isolated import behavior;
- exact module/entrypoint and immutable argv;
- canonical workspace/cwd;
- allowlisted environment names and value digests;
- generation, seed, grant, occurrence, lease/epoch/fence, GLEK, topology, TTL,
  and stop-fence identities;
- venue process identity requirements (PID plus start time/process birth,
  cgroup/unit/container/namespace as applicable).

There is no `git fetch`, checkout, pull, push, reset, clean, pip install,
editable-install sync, runtime discovery, hot upload, wrapper replacement, or
environment-selected import path in execute/reconcile/stop. Generation promotion
is a prior T1.8 transaction. The launched runner receives an opaque capability
and raw `chain start` rejects before any plan/worktree/state mutation unless it
can verify that capability through the owner.

At-most-one is enforced by a venue-owner CAS on the exact runner slot, not tmux
name existence, marker text, PID-file presence, or a filesystem lock. Every
runner revalidates grant/lease/generation/stop fence before initialization and
before the first allowed transition. The canary capability contains no authority
for later phases.

### G. Response loss and indeterminate reconciliation

Any timeout, cancellation, connection loss, owner-write failure, process death,
or exception after a provider call boundary begins is `INDETERMINATE`, never an
ordinary retryable failure. The same transaction and GLEK are reconciled; a
second start is forbidden while ambiguity exists.

For upload ambiguity, the privileged observer reads the reserved destination
and reports exact content/object identity. Exact seeded bytes may be adopted;
absence may permit the same GLEK to continue only when the provider proves the
write did not apply and all authority/TTL remains current; mismatch or
unreadability quarantines.

For start ambiguity, the observer queries the authoritative runner slot and
process namespace and returns signed evidence including process birth, exact
argv/environment digests, cwd, generation, seed, grant/fence, lease/epoch,
GLEK, and spec digest:

- exactly one exact current process: adopt and move to independent running
  verification;
- authoritative zero plus proof that start did not apply: same-GLEK continuation
  may be allowed while authority is current;
- more than one, wrong identity/generation, incomplete evidence, query error, or
  disagreement: remain indeterminate/quarantine and invoke exact stop/fence.

Reconciliation does not rerun source refresh, upload different bytes, create a
new session, or kill an unknown process by string match.

### H. `StopCapability` and exact stop transaction

The stop capability is issued and validated before launch and is independently
usable while launch is `INDETERMINATE`. It contains:

- schema/contract digest, one-use nonce/idempotency identity, issue/expiry;
- exact seed, grant/revision/fence, occurrence/lease/epoch/fence, parent launch
  GLEK, generation, runner slot, and eventually observed process birth;
- a distinct stop parent GLEK and stable child-effect manifest;
- only these permitted operations: deny new WBC/effects, fence runner, revoke
  grant, advance/revoke lease, terminate exact process identity, verify absence,
  and preserve evidence;
- owner signatures and required reconciliation query.

Safe order:

1. durably record stop intent and stop child GLEKs;
2. deny any new launch/run effects for the identity;
3. publish the runner stop fence and revoke/fence Run Authority;
4. revoke or advance the Custody lease/epoch so the old holder cannot reacquire;
5. terminate only the exact PID/process birth/cgroup/unit bound to the runner;
6. reconcile lost stop acknowledgement;
7. verify owner grant revoked, lease advanced/fenced, WBC outcomes durable,
   exact process absent, and late old writes/effects rejected;
8. preserve workspace, spec, marker/projections, logs, owner records, and collision
   evidence.

Generic `tmux kill-session`, `pkill`/grep, provider down, container destroy,
state reset, branch/worktree deletion, marker edit, or “kill then relaunch” is not
this stop transaction. Stop failure leaves new effects fenced and remains
visible/indeterminate; it never restores authority by improvisation.

### I. TTL semantics

Every authority/reservation has a positive, bounded, canary-scoped TTL. Validate
wall-clock and monotonic/deadline consistency at submission and immediately
before each irreversible effect; the runner checks again at initialization and
the first transition. Expiry fences new effects and activates stop/reconciliation.
It does not convert unknown state to failure, release a collision, or authorize
a fresh attempt. Renewal requires a new signed owner envelope; launch code may
not refresh its own lease/grant/TTL.

## Required integration and frozen-interface handoff

Sol must not guess across moving dependency worktrees. Before mutation, record
accepted commit IDs and schema/help digests for:

1. **T1.1:** production Run Authority/admission owner client, reservation and
   revalidation receipt, authority cursor/fence semantics, deterministic plan ID,
   and installed composition. T1.9 consumes; it does not reimplement CL1.
2. **T1.5:** singleton simple-fixer owner endpoint/schema, exact recovery
   occurrence identity, topology/retirement inventory, and no-delegation rules.
   T1.9 binds the topology; it does not turn the fixer into launcher.
3. **T1.6:** exclusive owner client/capability, effect envelope, parent/child GLEK
   derivation, intent/outcome/reconciliation states, structured process/upload
   effect families, and installed production composition. T1.9 never calls raw
   transports.
4. **T1.8:** accepted generation vector/selection/attestation and fixed production
   observer. T1.9 verifies; it does not deploy or repair generations.
5. **T1.7 if used by any frozen owner:** store incarnation/cursor, migration,
   capacity and reserve semantics. Do not create a shadow T1.9 SQLite authority.

Create T1.9 from a clean integration lineage containing those accepted commits,
not from the recovery ancestor plus copied dirty diffs. If an owner port/schema
is not accepted, production execute must be unavailable. A hermetic test fake
may unblock contract work but cannot satisfy the installed-production test.

## Megaplan adapter and bypass retirement map

Build on the accepted T1.5/T1.6 retirements to avoid conflicting rewrites.
Every mutation-capable alias must either call the fixed owner client with an
opaque pre-issued handle or fail closed with `authorized_launch_required`.

### Primary files

- `arnold_pipelines/megaplan/cloud/cli.py`
  - add only the thin authorized transaction adapter;
  - remove/reject launch authority from quickstart `--launch`, `cloud chain`,
    `launch-epic`, `epic-chain`, `resume`, `pause-chain/resume-chain`, and
    `supervise`;
  - remove authorized-path `--fresh`, refresh, editable-sync, and force-clean;
  - keep preflight/status/logs read-only.
- `arnold_pipelines/megaplan/cloud/providers/base.py`, `providers/ssh.py`, and
  `providers/on_box.py`
  - remove public raw mutation capability from ordinary callers;
  - register structured upload/start/observe/stop venue effects behind T1.6;
  - separate read-only observation from arbitrary command execution.
- `arnold_pipelines/megaplan/cloud/operator_control.py`
  - remove relaunch-by-marker and kill-by-session; route exact stop to owner;
  - distinguish an observational pause request from authority revoke/stop.
- `arnold_pipelines/megaplan/cloud/supervise.py`
  - no restart/wake/refresh; observer only or retired.
- `arnold_pipelines/megaplan/cloud/template.py` and
  `cloud/templates/entrypoint.sh.tmpl`
  - no boot-time chain/agent/watchdog/supervisor launch authority;
  - install only the accepted singleton owner services and observational
    components in the pinned generation.
- `arnold_pipelines/megaplan/chain/__init__.py`
  - raw `chain start` verifies the opaque launch capability before any mutation;
  - no worktree/branch/state cleanup on collision; no fresh bypass.
- `arnold_pipelines/megaplan/chain/epic_chain.py`
  - child launch requires a new owner-authorized child launch seed/envelope;
  - direct subprocess start is rejected.
- `arnold_pipelines/megaplan/chain/operator_pause.py`,
  `supervisor/chain_runner.py`, and supervisor driver entrypoints
  - projections never grant resume/start authority; runner revalidates owner
    fence/lease/generation.
- `arnold_pipelines/megaplan/cli/__init__.py`, package `__main__` surfaces, and
  `arnold/cli/__init__.py`
  - ensure aliases cannot reach a raw handler.
- `pyproject.toml` and package data
  - install fixed scripts/schema and ensure wheel/source parity.

### Wrappers/templates/services/scripts to gate or retire

- `cloud/wrappers/arnold-chain`, `mp-chain`, `arnold-supervise`, `mp-supervise`,
  `arnold-cloud-discover`, `arnold-watchdog`, `arnold-heartbeat`,
  `arnold-repair-loop`, `arnold-meta-repair-loop`, `arnold-repair-trigger`,
  `arnold-progress-auditor`, `arnold-kimi-goal-operator`, and any materialized
  copies;
- watchdog ensure service/timer and entrypoint-started heartbeat/watchdog;
- `cloud/manual_repair_trigger.py`, `meta_repair.py`,
  `progress_auditor_controller.py`, `progress_auditor_escalation.py`,
  `six_hour_auditor.py`, old `cloud/simple_fixer.py`, managed-agent and resident
  fixer launch surfaces insofar as they can spawn/relaunch;
- `scripts/cloud_hot_upload.py`;
- AgentBox/provider lifecycle paths and any generic `ssh_exec`, `bash -lc`,
  subprocess, tmux, systemctl, Docker exec, or filesystem-copy alias that can
  reproduce upload/start/stop.

`arnold-cloud-discover` may report historical relaunch text for forensics, but
must never output an executable launch as an approved next action. Markers,
status snapshots, watchdog reports, and logs remain rebuildable evidence only.

## Mutation scope for Sol

The narrow correct scope is:

1. new neutral launch contracts/client/transaction/reconciler/verifier/CLI under
   the accepted T1.6 owner package;
2. one privileged venue adapter implementing structured reserve/upload/start/
   observe/stop effects through T1.6, with hermetic fake for tests and no fake
   production selection;
3. thin Megaplan seed builder/adapter and raw runner capability validation;
4. static/dynamic bypass inventory plus hard gates/retirements across the files
   above;
5. packaging/help/schema parity;
6. hermetic/local and isolated non-production canary evidence under `E/T1.9/`.

Out of scope:

- production cloud launch, provider deployment, service restart, source refresh,
  owner installation, or T6.1;
- reimplementing Run Authority, Custody, WBC, simple fixer, release deployment,
  notification UX, or CL1 policy;
- deleting/resetting the v2 incident session or any collision;
- launching a watchdog or generalized fixer to supervise launch;
- treating the cloud-session marker as delegation provenance.

## Adversarial test suite

### Contract and canonicalization

Add focused tests, recommended under
`tests/arnold/workflow/test_launch_contracts.py` and
`test_launch_owner_client.py`:

1. strict JSON: unknown fields, duplicate keys, wrong types, bool-as-int,
   non-finite values, noncanonical Unicode/path/number encodings, oversized
   payload, invalid signature, and schema/help digest mismatch reject;
2. golden seed/envelope/stop/GLEK vectors are byte-stable across source, wheel,
   processes, and restart;
3. every mismatch in seed/grant/revision/fence/occurrence/lease/epoch/GLEK/
   generation/topology/TTL/stop digest rejects with zero venue calls;
4. missing owner, timeout, corrupt response, stale cursor, forked owner record,
   and owner disagreement reject with zero calls;
5. production CLI cannot select a fake, socket, root, provider, executable,
   callback, raw command, or environment override.

### Absence, collision, and concurrency

Add `test_launch_reservations.py`:

1. a collision test for every workspace/session/spec/plan/branch/worktree/state/
   marker/runner/GLEK/publication target;
2. path aliases (`..`, symlink, dangling symlink, case fold, Unicode normalization,
   inode/hard-link where relevant), duplicate registrations, partial/corrupt
   state, and unreadable targets are never classified absent;
3. preflight says absent, adversary creates target before reservation: collision,
   no delete/overwrite/start;
4. target appears between cross-owner reservations: saga quarantines/fences,
   preserves evidence, zero start;
5. 2 and 200 concurrent identical launchers: one committed launch identity and
   at most one start; all others exact replay or collision, never another effect;
6. same seed/different envelope, same GLEK/different request, same name/different
   seed, and expired reservation are conflicts/quarantine;
7. ENOSPC/DB full/readonly/WAL corruption/cursor rollback before reservation or
   intent produces zero effects.

### Crash and response-loss matrix

Add `test_launch_transaction_crashes.py` and inject process-kill/error at least:

- before/after authority validation;
- before/after each target reservation and reservation commit;
- before/after parent and child intent commit;
- before upload call, during upload, after provider application, after readback,
  before/after upload receipt commit;
- before start call, after process spawn but before ACK, after ACK but before
  owner receipt, before/after independent observation;
- before/after running verification and canary-scope fence.

Assertions:

- pre-call crash is replayable only under the same current GLEK/authority;
- any may-have-applied state is durable `INDETERMINATE` and never blindly
  redispatched;
- exact upload/start observation may be adopted;
- zero may continue only with authoritative non-application proof;
- multiple/mismatched/unknown observations trigger stop/fence and preserve data;
- restart uses persisted exact bytes/argv/manifests, never rerenders or refreshes.

### At-most-one runner and generation

Add `test_runner_slot_and_attestation.py`:

1. process exists with same tmux/session but wrong seed, argv, cwd, source,
   generation, environment, spec digest, process birth, fence, or GLEK: collision
   plus stop/fence, never adoption;
2. marker exists but process absent, process exists but marker absent, PID reused,
   duplicate cgroup/unit, stale lock, and owner-slot/query disagreement;
3. launch command spy proves no fetch/pull/push/reset/clean/pip/editable install/
   hot upload/runtime discovery;
4. old generation, old wrapper, old interpreter, wrong import root, or post-launch
   source change cannot advance;
5. runner rejects direct invocation and revalidates before initialization/first
   transition; expired/revoked/fenced capability permits zero further effects.

### Stop and revoke

Add `test_stop_transaction.py`:

1. stop capability unavailable/invalid at prepare: launch cannot start;
2. concurrent/replayed stop is exact idempotency, one stop effect;
3. crash/response loss at every stop intent, WBC deny, RA revoke, lease advance,
   runner-fence publish, process termination, observation, and receipt boundary;
4. exact process only: adjacent tmux/session/PID/string-matching processes survive;
5. PID reuse or process-birth mismatch does not kill an unknown process and
   leaves authority fenced;
6. workspace/spec/plan/branch/worktree/marker/logs/owner evidence remain intact;
7. old process attempts late plan/Git/provider/notification effects after fence:
   all rejected;
8. stop while launch/upload/start is indeterminate converges or remains safely
   fenced without second start;
9. provider stop ACK loss reconciles by exact process identity, never generic
   kill or container destroy.

### Bypass closure

Extend/create a generated inventory test, preferably
`tests/integration/test_launch_boundary_closure.py`, scanning Python, shell,
templates, systemd, package scripts, wheels, and materialized wrappers. Runtime
spies must prove the fixed owner/T1.6 venue adapter is the only caller of
mutation-capable upload/start/stop transports.

Adapt at least these existing suites:

- `tests/cloud/test_cloud_chain_command.py`
- `tests/arnold_pipelines/megaplan/test_cloud_quickstart.py`
- `tests/arnold_pipelines/megaplan/test_epic_chain.py`
- `tests/arnold_pipelines/megaplan/test_chain_worktree_safety.py`
- `tests/cloud/test_ssh_deploy.py`
- `tests/cloud/test_cloud_hot_upload.py`
- `tests/cloud/test_editable_install_sync.py`
- `tests/cloud/test_watchdog_wrappers.py`
- `tests/cloud/test_manual_repair_trigger.py`
- `tests/cloud/test_progress_auditor_controller.py`
- T1.5’s `tests/cloud/test_recovery_topology_surfaces.py`,
  `test_wrapper_authority_bypass_gating.py`, `test_simple_fixer_retirement.py`,
  `tests/m9/test_bypass_gating.py`, `tests/m10/test_watchdog_and_auditor.py`, and
  `test_event_recovery_slo.py`;
- `tests/arnold_pipelines/megaplan/test_installed_package_composition_smoke.py`
- `tests/arnold_pipelines/megaplan/test_wheel_smoke.py`
- `tests/installed_wheel/*`, with a dedicated launch-authority entrypoint probe.

Static scans must include aliases and indirect imports, not only command text.
Explicitly test `cloud chain --fresh`, raw `chain start`, quickstart launch,
`launch-epic`, `epic-chain`, operator resume, cloud resume, supervisor restart,
entrypoint mode chain/auto, wrappers, watchdog/systemd relaunch, discovery output,
hot upload, raw provider SSH/on-box calls, generic exec, and installed/materialized
copies. Each must fail before mutation or accept only an opaque current owner
handle; none can mint one.

### Installed parity and canary

Add `tests/installed_wheel/test_launch_authority_entrypoint.py` and an isolated
canary suite:

1. source, wheel, `python -P`, fixed executable, thin cloud adapter, and every
   shipped wrapper report identical help/schema/contract digest;
2. imports resolve only from the approved installed generation;
3. no owner service means deterministic fail-closed and zero venue calls;
4. hermetic/non-production canary performs exactly initialization and one first
   ordinary CL2 transition with accepted T1.1 admission, current owners, exact
   generation, and one runner;
5. it cannot perform a second transition, publish, notify, create PRs, refresh
   code, or launch child/watchdog/meta agents;
6. an independent verifier accepts exact receipts before any hypothetical scope
   expansion; rejection invokes stop/fence.

The T1.9 canary is local/hermetic or specifically isolated non-production. It
must not call Hetzner, cloud provider mutation, installed production owner, or
the v2 critique session. Production T6.1 remains blocked until T3.6, T4.6, and
T5.6 plus the installed T1.9 transaction are complete.

## Implementation sequence

1. Freeze and record accepted T1.1/T1.5/T1.6/T1.8 commits, schemas, owner
   endpoints, help digests, and production composition assertions.
2. Define strict seed/envelope/absence/runner/stop contracts and golden vectors.
3. Implement owner persistence/state machine and fixed client with hermetic fake.
4. Register structured reserve/upload/start/observe/stop venue effects through
   T1.6; make raw mutation transports inaccessible to ordinary production code.
5. Implement ambiguity and exact-stop reconciliation before adding a happy-path
   start.
6. Add runner capability validation and first-transition revalidation.
7. Add thin Megaplan adapter and retire/gate every bypass using a generated
   inventory.
8. Prove installed help/schema/wheel/materialized parity.
9. Run the full adversarial/concurrency/crash suite.
10. Produce only isolated non-production canary receipts in `E/T1.9/` and submit
    independent review. Do not fill R6 or attempt T6.1 until accepted.

## Non-negotiable review failures

Independent review must hard-fail T1.9 if any of these is true:

- a launch/stop path can execute without all owner records or with a test/local
  owner in production;
- any target “absence proof” is a stale observation rather than a point-of-use
  reservation;
- collision handling deletes, resets, cleans, overwrites, or adopts by name;
- source/runtime refresh exists in execute, reconcile, resume, or stop;
- tmux/marker/PID-file/process-name is treated as authoritative identity;
- two concurrent requests can call start twice;
- response loss becomes `FAILED`, retry, fallback, new session, or new model;
- stop is unavailable before launch or can only kill by broad name/container;
- stop deletes evidence or does not revoke/fence grant, lease, and future WBC;
- a raw wrapper/provider/exec/resume/supervisor/watchdog path bypasses the owner;
- help/schema/digest differs between source, wheel, installed interpreter, or
  materialized wrapper;
- canary authority extends beyond initialize plus one first CL2 transition;
- T1.9 claims production launch despite missing accepted production owner/
  generation/venue composition.

## Read-only preparation record

Inspected:

- exact recovery ancestor `6787...` launch/stop/resume/provider/wrapper paths;
- governing T1.9, T6.1, R4–R9 requirements;
- current dirty T1.1, T1.5, and T1.8 worktree contracts/status;
- T1.6 exclusive-effect-custody preparation and implementation brief;
- repository test and installed-package surfaces.

No code or dependency worktree was edited. No test was run because this task was
contract preparation, not implementation validation. No cloud, provider,
process, owner, release, branch, worktree, or existing session state was
mutated. The only written artifact is this preparation report.
