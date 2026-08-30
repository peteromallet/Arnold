# Settled-plan W1 — sequencing and verification lens

## Immutable North Star

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

## Frozen agent goal

# Agent Goal — make the 24h failure marathon structurally impossible

[North Star](./northstar.md) — this run advances "one door per invariant" and
"deaths speak" by shipping the systemic guard Grok specified in
docs/nbf-grok-verdicts.md (§3), verified by structural tests.

## Objective
Implement, in this repo, the typed worker-disposition control plane that makes the
2026-08-26 NBF failure marathon (11+ failure events, docs/nbf-failure-ledger.md)
impossible to recur:

1. **Unique admission gate.** Extend `require_production_worker_dispatch_runtime`
   (cloud/runtime_attestation.py) into the single production worker-admission door:
   spec translation, catalog row, model-family classification, live omp membership,
   seed/interpreter binding, timeout budget — fail closed before any worker exists.
2. **Wire all three launch doors — exactly once each.** workers/_impl.py non-OMP
   routes, workers/omp.py run_omp_step (backend entry; _impl delegates to it at
   _impl.py:7698-7713 — the nested OMP path must total ONE hit), and
   cloud/babysitter/launch.py pre-managed-launch. No other refresh_/require_
   preflight may execute on these paths.
3. **Typed death dispositions — every real signal branch.** Route ALL terminate
   sites through one typed helper over `IncidentLedger.append_event`
   (incident/ledger.py:338-361), appending
   `{killer, signal, elapsed_s, disposition_id}`:
   - launcher: the child is killed BEFORE TimeoutExpired raises
     (subagent-launcher/launch_omp_agent.py:251-261) — disposition at the kill,
     not the exception
   - resident/subagent.py: two terminate→kill ladders (:4818-4824, :5065-5072)
   - watchdog: SIGTERM + wedged-signaling path (wrappers/arnold-watchdog)
   - ensure-megaplan-watchdog restack pkill
4. **Fingerprint redispatch block — pre-launch.** Admission refuses to launch a
   worker whose dispatch fingerprint matches the last terminal fingerprint
   (incident/projection.py:452-478 currently only diagnoses at the 3rd repeat)
   unless a durable changed-precondition identity is recorded.
5. **Joint model admission — and expired-ID proof.** One admission function
   validates spec↔catalog↔family↔live provider membership simultaneously; a
   test proves the discriminating case: static catalog ACCEPTS an expired id
   (ox-alpha, workers/omp.py:98-105 / model_seam.py:502-506) while the joint
   admission REJECTS it typedly against the live provider.
6. **Structural spy test — three doors, gate-before-spawn.** Driving
   `run_step_with_worker` (workers/_impl.py:7347 — NOT the underscore name)
   and `run_omp_step` under a production manifest hits the gate exactly ONCE
   per dispatch (the nested OMP delegation totals one hit), the babysitter
   pre-launch door is covered, the spy intercepts only final spawn/RPC (no
   mock early-return), and a door-bypass today would make it fail.

## In scope / non-goals
- In scope: engine code above + their focused tests; catalog/family wiring already
  on main stays; hot-env pin file gets a comment pointing at the gate (no behavior).
- Non-goals: the 22-milestone NBF chain itself (it runs independently);
  Discord/resident features; CI rework beyond making new tests run.

## Settled decisions
- Model policy (user-pinned, superseding the earlier staged declaration):
  Planner, Oracle, and any justified `[XHARD]` task = GPT-5.6 Sol
  (`gpt-5.6-sol`, high reasoning); every normal exploration, critique,
  execution, and independent review task = GPT-5.6 Luna (`gpt-5.6-luna`).
  No model switch is authorized without user approval.
- Fix delivery = fixer contract: commit in candidate tree, ship to origin/main,
  never hotfix-by-deploy-only.
- Single-scan supervision verdicts are banned; two-scan confirmation pattern is
  the standard for any kill decision.

## Validation
- pytest tests/cloud/test_runtime_attestation.py (existing 42) PLUS new
  disposition/admission/spy suites, all green locally.
- Structural spy asserts exactly-once gating from both doors.
- bash -n on wrapper changes; grep proves no remaining raw refresh_/require_ pair
  on the three doors.

## Done / stop
Done when criteria 1–6 hold with green suites and the structural spy passes after a
fresh `git fetch && git rebase origin/main`. Stop (blocked) only if box evidence
needed for a disposition consumer is unavailable and user cannot grant it.

## Sync policy
Push branch `megado-nbf-guard-0826` to origin when batches pass oracle gates.
Merging to main requires user approval at completion review.

## Source custody for resumed execution

Build on refreshed `origin/main` at immutable source SHA
`798c50619204010ed3f4297fbb57988fe9381924`; preserve the five branch-only
planning/evolution commits and the protected untracked artifacts named in
`custody.md`. The source update does not widen scope or authorize a main merge.

7. **Cooldown-aware scheduling conditions (T7, added via plan evolution — ledger
   entry 13).** Treat an active same-phase/spec cgroup-OOM cooldown as a typed,
   time-bounded `scheduling_condition`, never a worker/phase failure: shared
   pre-dispatch seam calls `memory_cooldown_wait_secs`, emits `retry_wait`
   evidence, sleeps via injectable clock/sleeper, reruns admission. A
   scheduling condition increments neither deterministic-phase-failure nor
   repeated-signature counters and cannot set the plan to `blocked`; genuine
   repeated internal_errors still open their breakers. Foundation shipped to
   main: a9e1c7d0d6 (death expiry) + af370f5ec6 (defer refusals; recover
   repeated-failure blocks).

8. **Typed `provider_degraded` scheduling condition (T8, plan evolution — ledger
   entry 14).** Consecutive upstream idle-timeouts/availability errors for one
   spec become a typed, time-bounded `scheduling_condition`
   (`reason=provider_degraded`, carrying `phase`/`spec`/`retry_after_s`) —
   never a worker/phase failure. Breaker-exempt like T7. If a configured
   fallback exists (same-family alternate or last-known-good), flip through the
   existing fallback-chain door (`fallback_chains.py`,
   `_advance_configured_spec_fallback`) with the flip target passing joint
   admission (criterion 5); if the pin is scalar, hold with a bounded health
   probe and redispatch once after recovery. Flip AND return-to-primary append
   ledger evidence. Files: fallback_chains.py, workers/_impl.py,
   handlers/shared.py, orchestration/phase_result.py, recovery_policy.py,
   auto.py breakers, incident/ledger.py. DEEP verdict (Grok 4.6, full spec in
   .oracle/findings/evolution-entry14.txt).

## Immutable settled-plan candidate

Plan SHA-256: 770c61d4c63e1af0af1c92630fbce3ccdf956d66250c8134cb4db00c5b3dcb69

# Plan — Typed NBF worker admission, disposition, and scheduling control plane

## 1. Planning basis and custody

This plan was produced read-only from current HEAD.

- Branch: `megado-nbf-guard-0826`
- HEAD: `922241d0bdb3e993c3b554cc69f19948adef7bc3`
- Source base: `origin/main` at `798c50619204010ed3f4297fbb57988fe9381924`
- Branch state: six commits ahead of `origin/main`; the sixth is the resumed-custody commit.
- Untracked protected artifact: `.oracle/briefs/planner-sol.md`
- The earlier protected evolution artifacts are now preserved in the branch history.
- `.oracle/tasklist.md` is foreign onboarding-run evidence and is excluded from this plan.
- No tests were run during planning because the planner contract forbids mutating commands; even collection can create caches. Existing test coverage was inspected statically.
- `tests/cloud/test_runtime_attestation.py` currently contains 42 tests.
- `omp models --help` confirms a machine-readable live membership surface: `omp models --json`. In this read-only sandbox, a direct listing failed closed when OMP attempted a SQLite schema migration; production admission must convert such catalog-read failures into typed refusal, never absence or acceptance.

## 2. Verified current-state inventory

| Criterion | Status | Current evidence | Remaining gap |
|---|---|---|---|
| 1. Unique admission gate | **Partially satisfied** | `cloud/runtime_attestation.py::require_production_worker_dispatch_runtime` at approximately lines 2961–3046 validates seed, manifest generation, dependency interpreter, and seed interpreter. `chain/source_admission.py::worker_launch_preflight` separately validates the runtime/source vector. | The gate has no production callers and does not jointly validate translation, catalog row, model family, live OMP membership, timeout, memory cooldown, dispatch fingerprint, or changed-precondition identity. |
| 2. Exactly-once wiring at three doors | **Partially satisfied** | `_impl.py::run_step_with_worker` is the public orchestration door. `_run_step_with_worker_legacy` currently executes the raw refresh/require pair around lines 7576–7591 and source preflight around 7632–7651. `_impl.py` delegates OMP to `workers/omp.py::run_omp_step` around 7698–7713. Babysitter launches through `cloud/babysitter/launch.py::run_managed_command` around 579–586. | `run_omp_step` and babysitter have no gate. Adding calls naïvely would double-gate nested OMP. The raw `_impl` preflight and the separate memory preflight in `handlers/shared.py` must be absorbed and deleted. |
| 3. Typed death dispositions | **Partially satisfied** | `IncidentLedger.append_event` is the canonical journal door (`incident/ledger.py:338–361`). `auto.py::_build_worker_death_record` records cgroup-OOM evidence in `state.json`. Watchdog wedge handling has a partial two-scan marker. | No canonical `worker_disposition` type/helper exists. Launcher timeout, resident TERM→KILL ladders, resident follow-up SIGINT, watchdog TERM/KILL paths, and ensure-restack kills remain anonymous. The OOM record is not routed through the incident ledger and lacks the complete disposition contract. |
| 4. Pre-launch fingerprint redispatch block | **Missing** | `incident/projection.py::_populate_incident_placeholders` diagnoses a third repeated `repair_attempt`; `_attempt_fingerprint` hashes incident prose/actions. | There is no canonical worker dispatch fingerprint, durable changed-precondition identity, or admission-time refusal. |
| 5. Joint model admission and expired-ID proof | **Partially satisfied** | `workers/omp.py::parse_omp_spec`, `validate_omp_catalog_model`, `_OMP_CATALOG_MODELS`; `arnold/pipeline/model_seam.py::classify_model_family`; launcher `_translate_model`. Static catalog and family classification both accept expired `openrouter/stealth/ox-alpha`. | These vocabularies are not joined, translation is duplicated, and no live provider membership check exists. |
| 6. Structural gate spy | **Missing** | Existing runtime, OMP adapter, WBC, and babysitter tests cover their individual behavior. | No production-manifest test drives the public doors, intercepts only final RPC/spawn, or proves gate-before-spawn and exactly-once nested OMP. |
| 7. Cooldown-aware scheduling | **Partially satisfied** | `runtime/memory_headroom.py::memory_cooldown_wait_secs` expires cgroup-OOM deaths. `handlers/shared.py` performs memory selection. `auto.py::_memory_cooldown_refusal_wait` recognizes the structured refusal and resets breaker counters before `time.sleep`. Tests cover expiry and breaker behavior. | It remains a post-failure `auto.py` exception path rather than a typed shared admission condition. Sleep/clock are not injected; retry-wait evidence is not emitted; `RecoveryPolicy` does not natively exempt the condition; admission is not rerun inside the shared seam. |
| 8. `provider_degraded` scheduling | **Missing** | `fallback_chains.py` classifies availability/infrastructure. `_impl.py::_advance_configured_spec_fallback` is the existing rotator. `RuntimeTransitionWriter` already records fallback considered/taken. OMP classifies upstream idle timeout as availability. | No two-observation degradation state, scheduling-condition type, scalar hold/probe, durable route state, joint admission of a flip target, return-to-primary evidence, or breaker exemption exists. |

### Important current duplicate/control paths

- Runtime preflight: raw refresh/require plus `worker_launch_preflight` in `_impl.py`.
- Memory preflight: `handlers/shared.py:375–435`.
- OMP grammar/catalog: `workers/omp.py`.
- Launcher translation: `skills/subagent-launcher/launch_omp_agent.py::_PREFIX_MAP/_translate_model`.
- Repeated failure: diagnostic-only projection after three attempts.
- Worker death: `state.json` record, plan journal event, and raw signals—none joined through one ledger helper.

## 3. Simplest safe design

### 3.1 One typed admission request and receipt

Extend `require_production_worker_dispatch_runtime` as the only production admission door. It receives a typed request containing:

- phase and plan identity;
- selected and configured specs;
- normalized agent/provider/model identity;
- timeout budget;
- source/runtime/manifest/seed context;
- dispatch fingerprint inputs;
- latest terminal disposition and any subsequent changed-precondition identity;
- injectable live-membership resolver, clock, sleeper, and evidence writer.

It returns an immutable admission receipt carrying the canonical normalized spec, family, live membership digest, timeout, runtime vector, dispatch fingerprint, and precondition identity. It either returns that receipt or raises a typed refusal/scheduling condition. It never returns a partial “probably valid” result.

The function composes existing helpers; it does not duplicate their logic:

1. Translate the spec through one canonical translator.
2. Parse and statically validate the catalog row.
3. Normalize the provider-neutral model and classify its family.
4. For OMP routes, resolve `omp models --json` and require exact provider/model membership.
5. Refresh and validate seed/manifest/interpreter identity.
6. Run the existing source/runtime-vector preflight.
7. Validate a finite positive timeout budget.
8. Apply memory/headroom and cooldown admission.
9. Derive and compare the dispatch fingerprint.
10. Return one receipt used by the caller.

Manifestless development remains explicitly non-production. Production intent, a production manifest, or a configured cloud seed may never collapse to the development no-op.

### 3.2 One canonical dispatch fingerprint

Create a canonical fingerprint from stable dispatch preconditions:

- phase;
- normalized selected spec and family;
- prompt/phase input identity where available;
- source revision and runtime vector;
- dependency interpreter identity;
- timeout budget;
- live membership digest;
- relevant configured fallback-chain identity.

A terminal worker disposition records this fingerprint. Admission refuses the same terminal fingerprint unless a later durable changed-precondition event names what changed and carries a new content identity. Accepted changes include a new source/runtime generation, admitted route change, verified provider recovery, or explicit recovery action. A timestamp, sleep, PID change, or retry count is not a changed precondition.

Cooldown and provider-degradation scheduling conditions are not terminal worker failures and therefore do not poison the terminal fingerprint.

### 3.3 One disposition helper

Add one typed helper adjacent to `IncidentLedger` for every worker signal or observed signal death. Required fields are:

```text
disposition_id
dispatch_fingerprint
killer
signal
elapsed_s
timeout_source
phase
selected_spec
worker identity
observed_at
evidence
```

The helper validates all required fields and synchronously calls `IncidentLedger.append_event`. For in-band kills, ledger failure prevents the signal. TERM and later KILL are separate dispositions with separate IDs. For an already-observed kernel cgroup-OOM death, the orphan detector records `killer=kernel:cgroup_oom`, `signal=SIGKILL`, and the measured elapsed interval before clearing the orphan.

Shell callers use a narrow CLI over the same helper. They do not handcraft JSON.

### 3.4 Typed scheduling conditions

Add `ExitKind.scheduling_condition` and a strict `SchedulingCondition` payload with at least:

```text
reason
phase
spec
retry_after_s
disposition_id
```

Optional route transitions add `from_spec` and `to_spec`.

Scheduling conditions:

- do not call `record_step_failure`;
- do not increment deterministic, repeated-signature, or recovery-circuit counters;
- cannot transition a plan to `blocked`;
- emit durable `retry_wait` evidence;
- use injected clock/sleeper;
- rerun full admission after waiting.

`RecoveryPolicy` handles this type before failure/circuit accounting rather than resetting counters after they were incremented.

### 3.5 T8 reuses the existing fallback door

Provider degradation is established only after two consecutive exhausted dispatch observations for the same phase/spec with an availability/idle-timeout classification and no intervening success or changed precondition.

- Configured non-execute chain: call `_advance_configured_spec_fallback`; jointly admit the proposed target before changing routing.
- Scalar pin: hold for a bounded interval, run an injected bounded provider probe, and allow one redispatch only after recovery.
- Execute/loop-execute: never rotate; preserve `ExecuteFallbackUnsafe` and use hold/probe only.
- Successful primary probing returns through the same route controller and appends a return event.
- A last-known-good route may be used only when it is already inside the configured chain or other explicit policy. Observed historical success does not silently widen a scalar user pin.
- Route flip and return state are durable incident-ledger evidence; any state metadata is only a cache.

### 3.6 Explicitly rejected anti-patterns

This implementation must not:

- add another preflight beside the admission gate;
- gate `_impl` and `run_omp_step` for the same nested OMP dispatch;
- scrape English stderr in `auto.py` to infer scheduling policy;
- treat a single idle-timeout, stale heartbeat, socket dip, or scan as sustained failure;
- accept PID liveness as health without an advancing sequence/progress identity;
- treat an anonymous integer return code as a disposition;
- redispatch a terminal fingerprint because time passed;
- create an independent provider rotator;
- let a live-membership read error become an empty-but-accepted catalog;
- apply a box-only hotfix that is absent from the candidate branch.

## 4. Execution batches and tasks

All implementation, focused test, critique, and independent-review tasks are **GPT-5.6 Luna**. Planning/revision and Oracle judgments are **GPT-5.6 Sol**. No model switch is authorized.

### Batch 1 — Typed control-plane contracts

#### NBF-01 — Add scheduling, disposition, and precondition contracts

**Classification:** Normal.

**Files and symbols**

- `arnold_pipelines/megaplan/orchestration/phase_result.py`
  - `ExitKind`
  - new `SchedulingCondition`
  - `PhaseResult` serialization/deserialization
- `arnold_pipelines/megaplan/orchestration/recovery_policy.py`
  - `RecoveryPolicy.classify`
  - `classify_with_circuit`
- `arnold_pipelines/megaplan/incident/schema.py`
- `arnold_pipelines/megaplan/incident/ledger.py`
  - `IncidentLedger.append_event`
  - `RuntimeTransitionWriter`
- New `arnold_pipelines/megaplan/incident/disposition.py`
  - `WorkerDisposition`
  - canonical fingerprint and disposition-ID builders
  - `record_worker_disposition`
  - `record_changed_precondition`
  - provider flip/return and scheduling evidence helpers
  - narrow CLI used by shell wrappers
- New focused tests:
  - `tests/arnold_pipelines/megaplan/test_worker_disposition.py`
  - `tests/arnold_pipelines/megaplan/test_scheduling_conditions.py`

**Work**

- Introduce strict typed payloads and round-trip serialization.
- Require complete disposition fields and reject incomplete or malformed events before append.
- Add explicit changed-precondition identity and provider flip/return event forms.
- Route all writes through `IncidentLedger.append_event`.
- Make `RecoveryPolicy` return a scheduling action before circuit accounting.
- Keep genuine `internal_error`, malformed output, auth, schema, and test failures on the existing failure paths.

**Acceptance**

- Incomplete `{killer, signal, elapsed_s, disposition_id}` cannot be appended.
- TERM and KILL for one ladder receive distinct deterministic disposition IDs.
- A scheduling condition never increments any breaker.
- Three identical genuine `internal_error` outcomes still open the existing breaker.
- Ledger write failure is visible and fail-closed.
- Event replay preserves every required identity.

**North Star connection:** “Deaths speak”; anonymous exits and scheduling-as-failure are forbidden.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_plan_circuit.py
```

**Synchronization point**

Sol Oracle reviews the schemas before callers adopt them. Renaming fields after Batch 2 begins is not allowed without a plan revision.

### Batch 2 — The one admission door and exactly-once wiring

#### NBF-02 — Expand the production admission gate

**Classification:** Normal.

**Dependencies:** NBF-01.

**Files and symbols**

- `cloud/runtime_attestation.py`
  - `require_production_worker_dispatch_runtime`
  - `refresh_runtime_launch_seed_for_worker_dispatch`
  - `require_configured_runtime_launch`
- `chain/source_admission.py::worker_launch_preflight`
- `workers/omp.py`
  - `parse_omp_spec`
  - `validate_omp_catalog_model`
  - new canonical translation/live-membership adapter
- `arnold/pipeline/model_seam.py::classify_model_family` — reuse, not fork
- `skills/subagent-launcher/launch_omp_agent.py`
  - delete local translation authority and call the canonical translator
- `runtime/memory_headroom.py`
  - `memory_cooldown_wait_secs`
  - `select_memory_safe_spec`
- `handlers/shared.py`
  - remove the standalone memory dispatch gate
- `incident/disposition.py`
- `observability/work_ledger.py` retry-wait emitter
- `tests/cloud/test_runtime_attestation.py`
- New `tests/cloud/test_worker_dispatch_admission.py`

**Work**

- Add the typed request/receipt and compose all admission invariants.
- Normalize translator ownership; retain existing accepted mappings but delete the duplicate launcher vocabulary.
- Resolve live OMP membership through `omp models --json`, with an injectable resolver for tests.
- Treat command failure, malformed JSON, ambiguous membership, and catalog-read timeout as typed admission rejection.
- Prove the discriminating expired-ID case:
  - static catalog accepts `openrouter/stealth/ox-alpha`;
  - family classification accepts it;
  - injected live catalog excludes it;
  - joint admission rejects it typedly before RPC.
- Move the current source/runtime-vector preflight under the gate.
- Move memory/headroom admission under the gate and delete the `handlers/shared.py` copy.
- For an active cgroup-OOM cooldown, emit a typed scheduling condition and retry-wait evidence, sleep through injected time, then rerun the entire gate.
- Enforce dispatch fingerprint/change-precondition rules before returning a receipt.

**Acceptance**

- One gate receipt proves every invariant in the frozen objective.
- Production intent cannot pass without seed/manifest/interpreter proof.
- Unknown, expired, or live-absent model IDs fail before client/spawn construction.
- Timeout `None`, zero, negative, non-finite, or policy-invalid values fail typedly.
- A same terminal fingerprint is refused on its first proposed redispatch.
- A later valid changed-precondition event permits admission and is included in the new receipt.
- Three active cooldown observations create retry-wait evidence but zero worker launches; expiry produces exactly one admitted launch.
- No raw memory preflight remains in `handlers/shared.py`.

**North Star connection:** “Models are admitted, not assumed”; “one door per invariant.”

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/workers/test_omp_adapter.py
```

#### NBF-03 — Wire the three production doors exactly once

**Classification:** Normal.

**Dependencies:** NBF-02.

**Files and symbols**

- `workers/_impl.py`
  - `run_step_with_worker`
  - `_run_step_with_worker_legacy`
  - dispatcher closures
  - nested OMP delegation
- `workers/omp.py::run_omp_step`
- `cloud/babysitter/launch.py::launch_babysitter`
- `cloud/babysitter/launch.py::_managed_spec`
- `docs/nbf-hourly-loop-goal.md` checked-in current-pin note
- `cloud/fixer_model_policy.py` credentials/pin documentation
- New `tests/cloud/test_worker_dispatch_spy.py`
- Babysitter tests beside:
  - `tests/cloud/test_babysitter_routing.py`
  - `tests/cloud/test_babysitter_goal.py`

**Work**

- Delete `_impl.py`’s raw refresh/require/source-preflight block.
- Non-OMP `_impl` routes call the gate once immediately before the final backend call.
- `_impl` OMP routes do not gate; `run_omp_step` is the sole physical OMP admission site.
- Direct `run_omp_step` gates once before output seeding, client construction, or RPC.
- Production admission precedes the mock-worker early return; manifestless test mode retains its explicit development behavior.
- Babysitter gates immediately before writing the running receipt and calling `run_managed_command`.
- Ensure both normal and `MEGAPLAN_USE_AGENT_DISPATCHER=1` paths follow the same rule.
- Change the checked-in pin note to state that pins are advisory input and `require_production_worker_dispatch_runtime` is authoritative.
- Do not mutate `/workspace/.cloud-hot-env`; it is outside the repository and protected by custody.

**Structural spy scenarios**

1. Public `run_step_with_worker`, native non-OMP route: one gate, then final worker call.
2. Public `run_step_with_worker`, nested OMP route: one total gate inside `run_omp_step`.
3. Direct `run_omp_step`: one gate, then final fake RPC.
4. Babysitter: one gate, then `run_managed_command`.
5. Gate rejection: zero final calls in every scenario.
6. No test sets `MEGAPLAN_MOCK_WORKERS=1`; only the final spawn/RPC seam is replaced.

**Acceptance**

- Gate count is exactly one in each scenario.
- Ordering proves admission receipt before spawn/RPC.
- Removing any one door call causes its structural test to fail.
- Reintroducing an outer OMP gate makes the nested test fail with count two.
- The three door files contain no raw `refresh_runtime_launch_seed_for_worker_dispatch` / `require_configured_runtime_launch` call.

**North Star connection:** one admission door; duplicate preflights are deleted.

**Focused validation**

```bash
pytest -q \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

**Synchronization point**

Sol Oracle checks the structural spy and the negative grep before any death/scheduling caller work is accepted.

### Batch 3 — Every worker death speaks

#### NBF-04 — Route Python signal branches through the disposition helper

**Classification:** Normal.

**Dependencies:** NBF-01; admission receipts from NBF-02 provide fingerprints.

**Files and symbols**

- `skills/subagent-launcher/launch_omp_agent.py::main`
- `resident/subagent.py`
  - same-session follow-up SIGINT path
  - timeout TERM→KILL ladder around 4816–4825
  - exception TERM→KILL ladder around 5065–5072
- `auto.py`
  - orphan recovery
  - `_build_worker_death_record`
  - `_emit_worker_killed_event`
- `incident/disposition.py`
- `tests/resident/test_managed_provider_agent_runner.py`
- New or focused launcher tests under `tests/skills/`
- `tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py`

**Work**

- Replace launcher `subprocess.run(timeout=...)` with explicit `Popen`/wait or communicate control.
- On timeout, append the SIGKILL disposition at the kill site, then kill/wait, then write timeout metadata/return 124. The exception/return path may not invent the disposition after the child is already dead.
- Before each resident SIGINT, SIGTERM, and SIGKILL, synchronously append its disposition.
- Preserve both terminate→wait→kill ladders and their return behavior.
- Convert the cgroup-OOM orphan evidence into a ledger disposition with `killer=kernel:cgroup_oom`, `signal=SIGKILL`, elapsed time, worker identity, and dispatch fingerprint before orphan recovery authorizes redispatch.
- Keep the state-level worker-death projection as a cache/diagnostic derived from the canonical event.

**Acceptance**

- Tests record call order: disposition append precedes every actual signal call.
- A ledger failure prevents in-band signaling.
- Timeout metadata and return codes remain compatible.
- The OOM observer produces exactly one canonical disposition for one active-step identity.
- Unknown dead-PID cases use an explicit unknown killer/cause; they do not claim cgroup OOM without a positive counter delta.
- Both resident ladders test the TERM-only and TERM→KILL branches.

**North Star connection:** SIGKILL, timeout, and terminate are typed facts, not anonymous integers.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/resident/test_managed_provider_agent_runner.py
```

#### NBF-05 — Instrument watchdog and restack kills; require sustained proof

**Classification:** Normal.

**Dependencies:** NBF-04 helper/CLI.

**Files and symbols**

- `cloud/wrappers/arnold-watchdog`
  - `signal_hung_fixer_children`
  - `babysitter_wedged`
  - stale babysitter signaling
  - `kill_process_group`
  - `kill_pid_and_descendants`
  - repair-tree reaping
- `cloud/systemd/ensure-megaplan-watchdog`
- `incident/disposition.py` CLI
- `tests/cloud/test_watchdog_wrappers.py`
- New `tests/cloud/test_watchdog_dispositions.py`

**Work**

- Replace every real signal in these two files with:
  1. exact victim resolution;
  2. two observations keyed by PID plus process-start identity;
  3. positive lack-of-progress proof using the same progress/sequence identity;
  4. synchronous disposition append;
  5. signal.
- Retain `kill -0`/`os.kill(pid, 0)` liveness probes as non-signal probes and classify them explicitly in the structural test.
- Upgrade the existing wedge marker so PID replacement or advancing progress clears the first observation.
- Add the same two-scan contract to hung-child signaling and ensure-restack; the current single stale-heartbeat scan is insufficient.
- TERM→KILL process-group escalation writes one event per signal.
- The ensure script resolves the active source/runtime for the helper; it must not hardcode a stale candidate checkout.
- Ledger/helper failure leaves the process alive and exits non-success/records the inability to kill.

**Acceptance**

- First stale/wedge scan never signals.
- A second scan with a changed PID, process-start identity, or advancing sequence resets confirmation.
- Only two matching separated observations permit signaling.
- Every TERM/KILL carries killer, signal, elapsed, disposition ID, and victim identity.
- No process can be reaped based only on `completed.json`, PID presence, or a single stale mtime.
- Shell syntax is valid.
- Structural signal inventory contains only the canonical disposition wrapper plus liveness probes.

**North Star connection:** no single-scan verdict and no judgment-based health claim.

**Focused validation**

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
pytest -q \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py
```

**Synchronization point**

Sol Oracle receives a signal-site inventory showing every real signal, its killer identity, two-scan evidence owner, and test. Any unclassified real signal in the scoped files blocks the batch.

### Batch 4 — Scheduling conditions and provider resilience

#### NBF-06 — Finish T7 and implement T8 through the existing fallback door

**Classification:** Normal.

**Dependencies:** NBF-01 through NBF-03.

**Files and symbols**

- `fallback_chains.py`
  - `classify_retryability`
  - same-family operational classification
- `workers/_impl.py`
  - `_initial_fallback_metadata`
  - `_advance_configured_spec_fallback`
  - worker-result and `CliError` fallback handling
- `workers/omp.py`
  - availability evidence exported from exhausted attempts
  - bounded injectable provider probe
- `handlers/shared.py`
- `orchestration/phase_result.py`
- `orchestration/phase_result_classify.py`
- `orchestration/recovery_policy.py`
- `auto.py`
  - external retry handling
  - deterministic/repeated-signature breakers
  - remove the special post-failure cooldown reset path after admission owns it
- `incident/ledger.py`
- `incident/disposition.py`
- New `tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py`
- Existing fallback, phase-result, memory, auto, and execution-policy suites

**Work**

- Finish T7 by deleting the post-failure string/payload special case once typed admission scheduling is active.
- Count provider degradation by exhausted dispatch observation, not individual text fragments. Two consecutive matching observations are required; an intervening success/change clears the streak.
- Recognize only structured idle-timeout/availability classes. Auth, quota, rate limit, unsupported model, malformed output, context, schema, and internal errors retain their existing typed policies.
- Emit `provider_degraded` with phase/spec/retry-after/disposition identity before generic external-failure blocking.
- For configured non-execute fallbacks:
  - call `_advance_configured_spec_fallback`;
  - run joint admission on the candidate;
  - append flip evidence before redispatch;
  - update existing fallback metadata/observability.
- For scalar pins:
  - bounded hold;
  - one injected no-tool health probe;
  - one redispatch only after a passing probe;
  - otherwise return another scheduling condition without blocking.
- Persist enough route state to avoid hammering the primary on every outer-loop iteration.
- Probe and return to primary on later dispatch; append return evidence before the route changes.
- Preserve execute/loop-execute fallback prohibition.

**Acceptance**

- One timeout does not flip.
- Two consecutive availability/idle-timeout observations produce `provider_degraded`.
- The condition changes none of the three breaker families and never blocks the plan.
- The ledger-14 scenario does not create 126 retries or an invalid-transition cascade.
- A configured same-family alternate flips only through `_advance_configured_spec_fallback` and only after joint admission.
- An unadmitted fallback is rejected without RPC.
- A scalar pin waits/probes and performs at most one post-recovery redispatch.
- Return to primary appends `from_spec`, `to_spec`, `reason`, and `disposition_id`.
- A genuine repeated `internal_error` still opens its breaker.
- Execute and loop-execute still raise/preserve `ExecuteFallbackUnsafe`.

**North Star connection:** scheduling is not failure; provider health needs sustained evidence; no unchanged precondition is retried blindly.

**Focused validation**

```bash
pytest -q \
  tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py
```

**Synchronization point**

Sol Oracle judges T7/T8 jointly. Passing T7 by retaining `auto.py` counter resets, or passing T8 by adding a second rotator, is a rejection.

### Batch 5 — Fresh-base integration, authoritative validation, and delivery

#### NBF-07 — Rebase, validate once broadly, review, and push the candidate branch

**Classification:** Normal.

**Dependencies:** All implementation batches.

**Work**

1. Commit every accepted batch in the candidate tree.
2. Verify the six custody commits and protected untracked artifact still exist.
3. Run:

```bash
git fetch origin main --prune
git rebase origin/main
```

4. Resolve any rebase conflict by composing with new main; do not reset, stash away, or overwrite unrelated work.
5. Run the authoritative broad validation exactly once after the fresh rebase.
6. Capture:
   - exact rebased SHA;
   - test command and result;
   - gate-call spy counts;
   - signal-site inventory;
   - negative raw-preflight grep;
   - shell syntax results;
   - criterion completion table.
7. Assign one Luna independent reviewer to the full completion evidence.
8. Submit the result to the Sol Oracle completion gate.
9. Push `megado-nbf-guard-0826` to origin. If rebase rewrote an already-published branch, verify the expected remote tip and use `--force-with-lease`, never unguarded force.
10. Stop before merging to main and request the user’s explicit approval.

**North Star connection:** fixes exist only when committed and deliverable through the fixer contract.

## 5. Task model classification

| Task | Classification | Rationale |
|---|---|---|
| NBF-01 typed contracts | Normal / Luna | Closed field/schema work with strict unit tests. |
| NBF-02 joint admission | Normal / Luna | Existing parser, catalog, classifier, runtime, source, and memory seams are known; the task is precise composition and deletion of duplicates. |
| NBF-03 door wiring and spy | Normal / Luna | Mechanical call-site ownership with an exact structural oracle. |
| NBF-04 Python dispositions | Normal / Luna | Signal branches and ordering requirements are enumerated and injectable. |
| NBF-05 wrapper/restack dispositions | Normal / Luna | Shell work is broad but bounded to two files, with exact two-scan and structural tests. |
| NBF-06 T7/T8 | Normal / Luna | It spans several policies, but the control rules, non-cases, existing rotator, and validation scenarios are sufficiently explicit for Luna. |
| NBF-07 integration/delivery | Normal / Luna | Mechanical custody, validation, review, and push workflow. |

No task is tagged `[XHARD]`. T8 has coupled concerns and non-local risk, but the irreducible kernel has been reduced to explicit state transitions and negative scenarios. There is no evidence that Luna cannot execute it reliably from this mechanical brief, so it does not meet all exceptional thresholds.

## 6. Additional exploration

No blocking exploration remains.

The only initially material unknown—the machine-readable live OMP membership surface—was resolved to `omp models --json`. Implementation must inspect its JSON shape and normalize it behind an injected adapter, but that is bounded implementation work, not a design choice. Its attempt to migrate a read-only local database also establishes the required failure behavior: typed rejection, never bypass.

No box investigation is required for disposition consumers. All required source signal sites and the existing OOM observer are present in this checkout.

## 7. Open questions and assumptions

### Genuine user-authority question

- **Merge approval:** after the completion review and branch push, merging `megado-nbf-guard-0826` into `main` requires explicit user approval. This does not block implementation.

### Implementable assumptions

- The two-observation rule applies to provider degradation, watchdog wedge, hung child, repair reaping, and ensure-restack.
- One exhausted provider dispatch is one degradation observation; internal retry chatter is supporting evidence, not multiple supervision scans.
- Last-known-good does not widen a scalar pin. It is eligible only when already authorized by the configured route chain/policy.
- Actual `/workspace/.cloud-hot-env` is outside the repository and protected. This run updates the checked-in pin/policy note to point at the gate and performs no box-only comment hotfix. A literal box-file annotation would require a separate operational authorization and would not substitute for committed source.
- Existing static `ox-alpha` rows remain for the discriminating regression test; admission, not deletion of historical catalog data, proves expiry handling.
- No full live provider marathon or box mutation is required for completion. Fake clock, membership, RPC, process, and ledger seams provide deterministic structural evidence.

## 8. Effort and huge-run determination

Best-effort implementation effort:

| Batch | Estimate |
|---|---:|
| Typed contracts | 1–1.5 engineer-days |
| Admission and door wiring | 2–2.5 engineer-days |
| Python and shell dispositions | 2–2.5 engineer-days |
| T7/T8 scheduling | 2.5–3 engineer-days |
| Rebase, validation, review, delivery | 1 engineer-day |
| **Total** | **8.5–10.5 engineer-days** |

**Huge-run determination: NO.** The implementation scope is approximately 1.5–2 focused working weeks, not greater than two weeks. It does not require a megaplan epic. The batch synchronization points remain useful review boundaries but are not huge-run cumulative gates.

## 9. Validation and completion matrix

One authoritative integration owner runs the broad matrix once, after the fresh rebase. Individual executors run only their focused suites during their batch.

| Criterion | Command/scenario | Evidence captured | Reviewer disposition |
|---|---|---|---|
| 1. Unique admission | Runtime and admission suites; production manifest with missing seed, wrong interpreter, invalid timeout, and valid receipt | Complete admission receipt and typed negative results | **PASS** only if all production invariants are composed by `require_production_worker_dispatch_runtime`; duplicate admission authority is blocking. |
| 2. Three doors exactly once | Structural spy for non-OMP, nested OMP, direct OMP, babysitter; raw-call negative grep | Ordered gate/spawn trace and per-dispatch count `1` | **PASS** only if nested OMP totals one and each bypass test fails when its gate is removed. |
| 3. Death dispositions | Launcher timeout; both resident ladders; SIGINT; OOM observer; watchdog TERM/KILL; restack TERM | Ledger rows with required fields and call-order evidence | **PASS** only if every scoped signal has a disposition before signal, or observer disposition before redispatch. |
| 4. Fingerprint block | Terminal disposition followed by same request; then changed-precondition event and retry | Typed first-redispatch rejection; later admitted receipt naming change identity | **PASS** only if the block occurs pre-spawn on the first identical retry. |
| 5. Joint model admission | Static `ox-alpha` acceptance plus live-membership rejection; malformed live catalog; admitted current model | Separate static and joint results | **PASS** only if the discriminating case proves static acceptance and typed live rejection. |
| 6. Structural spy | No mock early return; final fake RPC/spawn only; gate rejection causes zero final calls | Spy source and ordered trace | **PASS** only if a door bypass or double gate makes the suite fail. |
| 7. Cooldown scheduling | Fake clock: three active cooldown checks, expiry, one launch; genuine post-expiry refusal | Retry-wait events, zero breaker deltas, one launch after expiry | **PASS** only if admission owns the wait/recheck and `auto.py` no longer repairs counters afterward. |
| 8. Provider degradation | One timeout; two timeouts; admitted chain flip; scalar hold/probe; return primary; execute prohibition; repeated internal error | Scheduling, flip, return ledger rows and breaker snapshots | **PASS** only if conditions never block, rotations use the existing door, and genuine failures still trip breakers. |

### Authoritative post-rebase command

```bash
pytest -q \
  tests/cloud/test_runtime_attestation.py \
  tests/cloud/test_worker_dispatch_admission.py \
  tests/cloud/test_worker_dispatch_spy.py \
  tests/cloud/test_babysitter_routing.py \
  tests/cloud/test_babysitter_goal.py \
  tests/cloud/test_watchdog_dispositions.py \
  tests/cloud/test_watchdog_wrappers.py \
  tests/workers/test_omp_adapter.py \
  tests/resident/test_managed_provider_agent_runner.py \
  tests/arnold_pipelines/megaplan/test_worker_disposition.py \
  tests/arnold_pipelines/megaplan/test_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_provider_scheduling_conditions.py \
  tests/arnold_pipelines/megaplan/test_incident_ledger.py \
  tests/arnold_pipelines/megaplan/test_phase_runtime_incarnation.py \
  tests/arnold_pipelines/megaplan/test_memory_headroom.py \
  tests/arnold_pipelines/megaplan/test_worker_memory_gate.py \
  tests/arnold_pipelines/megaplan/test_auto_recover_blocked.py \
  tests/arnold_pipelines/megaplan/test_fallback_chains.py \
  tests/arnold_pipelines/megaplan/test_phase_result_classify.py \
  tests/arnold_pipelines/megaplan/test_gpt56_execution_policy.py \
  tests/arnold_pipelines/megaplan/test_common_worker_dispatch_wbc.py
```

```bash
bash -n arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog
bash -n arnold_pipelines/megaplan/cloud/systemd/ensure-megaplan-watchdog
```

```bash
if rg -n \
  'refresh_runtime_launch_seed_for_worker_dispatch|require_configured_runtime_launch' \
  arnold_pipelines/megaplan/workers/_impl.py \
  arnold_pipelines/megaplan/workers/omp.py \
  arnold_pipelines/megaplan/cloud/babysitter/launch.py
then
  exit 1
fi
```

A structural test—not an unreviewed grep count—owns the final signal inventory because `kill -0`/`os.kill(pid, 0)` are legitimate liveness probes.

## 10. Completion conditions

The work is complete only when:

- criteria 1–8 have `PASS` evidence in the matrix;
- existing 42 runtime-attestation tests remain green;
- all new admission, disposition, scheduling, provider, and spy suites are green;
- wrapper syntax checks pass;
- the raw refresh/require pair is absent from all three doors;
- every scoped signal branch is dispositioned;
- fresh fetch/rebase has completed and the authoritative suite passed afterward;
- custody commits and protected artifacts survive;
- the candidate branch is pushed to origin;
- no box-only code or hot-env behavior change exists;
- the independent Luna reviewer and Sol Oracle accept the completion;
- no merge to main has occurred without user approval.

## 11. Settled-plan readiness

**Disposition: ALREADY_SETTLED.**

Evidence:

- Every frozen criterion has a verified current-state status and named remaining delta.
- Physical launch doors, signal sites, fallback seam, breaker paths, and shipped T7 foundations were inspected at current HEAD.
- The live OMP catalog interface is known.
- No product-policy or architecture choice remains open.
- No `[XHARD]` execution is justified.
- No box evidence is required to begin.
- The reserved pre-settled critique placeholder remains unexecuted.

## Planner verdict

The plan can enter the GPT-5.6 Luna settled-plan streamlining wave now. There is no blocking exploration. The only later user-authority checkpoint is approval to merge the reviewed, pushed candidate branch into `main`.

## Relevant prior evidence and accepted dispositions

# NBF failure-marathon — Grok 4.6 verdicts (full text, restored)

Six glm-5.3-flash investigators examined the six shipped fix classes; Grok 4.6
adjudicated deep-structural vs adherence. Restored from session output after
Sol found the committed copy truncated.

## Per-class verdicts

| Class | Verdict | Confidence |
|---|---|---|
| A Identity-routing | **ADHERENCE** | high |
| B Catalog/family | **MIXED** (lean DEEP) | high |
| C Turn-timeout | **MIXED** (lean DEEP) | high |
| D Runtime-resilience | **MIXED** | high |
| E Dispatch-unification | **DEEP** | high |
| F Supervision-ops | **MIXED** | high |

**A — ADHERENCE.** `_PREFIX_MAP` had a documented `omp:` identity branch
(docstring, SKILL.md) and a rewrite of a subprocess script dropped it. Nothing
imported `launch_omp_agent.py`, so coverage never saw it. Drift from an existing
contract, preventable by a unit test of `_translate_model("omp:openrouter/…")`.
The expired-row issue is class B composing with A, not the identity defect.

**B — MIXED, lean DEEP.** Chain: `parse_omp_spec` yields `model_id =
"z-ai/glm-5.3-flash"`, `_PROVIDER_PREFIXES` has no `z-ai/`, GLM matched only
`glm-|glm/`, enforced-tier rethrow killed gate 3×. The patch (`"z-ai/glm"`) is
string-specific adherence; the defect is two independently mutated vocabularies
(`_OMP_CATALOG_MODELS` vs `classify_model_family`) with no coupling invariant.
The next nested OpenRouter slug hits the same hole.

**C — MIXED, lean DEEP.** The 1800→7200 bump only covers launcher rc=124; rc=-15
at 1401.9s was NOT the launcher (under the 1800s bound). The patch is a constant;
the defect is the receipt schema: `_write_metadata` stores `status`+`exit_code`
only; babysitter receipts `returncode` only. Launcher TimeoutExpired (CPython
SIGKILL), resident `worker.terminate()`, watchdog SIGTERM all collapse to an
anonymous integer. Ledger row 12 needed host ftrace — schema gap recurring across
every chain.

**D — MIXED.** Cgroup OOM is DEEP: dispatch was model-blind, SIGKILL uncatchable —
prevent-at-dispatch + `oom_kill` counter is the honest design. Seed custody is
ADHERENCE: interpreter vectors were recorded; `ready:true` came from an errors
list omitting the check. The WIP `require_production_worker_dispatch_runtime`
with zero production callers is class E.

**E — DEEP.** Three production doors, three contracts: orchestration
(`_impl.py:7580-7634` raw refresh/require pair), chain
(`chain/__init__.py:7500-7539` own raises), backend (`run_omp_step`,
`omp.py:1110` has none, dies late at `omp.py:482-488` generic). Typed gate at
`runtime_attestation.py:2923` has zero production callsites. N doors with
inconsistent preflight is architectural.

**F — MIXED.** Restack classifier + two-scan wedge are DEEP; stall-reap bump is
adherence. #1 and #3 are the same hole: one observation instant treated as
sustained truth.

## Cross-cutting themes

1. **Five model vocabularies, no joint admission** — frozen catalog
   (`workers/omp.py:88-117`), `_PREFIX_MAP`, `_PROVIDER_PREFIXES`/classify,
   live models.yml, babysitter env pin. Ledger rows 5 & 12.
2. **Deaths without killer identity** — OOM SIGKILL, launcher timeout, resident
   terminate, watchdog SIGTERM, restack pkill all land anonymous. Why the night
   was 24h, not 2h.
3. **Non-unique control plane** — invariants as comments/WIP/one-of-N paths;
   single stale `completed.json` triggered kills; wedge SIGTERM on one
   `_tree_has_live_work()` false.

## The one systemic guard

A required `worker_disposition` record: unique admission function
(`require_production_worker_dispatch_runtime` expansion) wired to the three
launch doors; every terminate site appends
`{killer, timeout_source, signal, elapsed_s}`; incomplete disposition = typed
block; redispatch of same fingerprint = typed block. Structural spy: wrap the
gate, drive one `_run_step_with_worker` and one `run_omp_step` under a
production manifest, assert both hit it exactly once.

## Sol amendments (sense-check REVISE)

1. Spy: `run_step_with_worker` (workers/_impl.py:7347), not the underscore name;
   no mock early-return; intercept final spawn/RPC; cover babysitter/launch.py.
2. Don't double-gate: `_impl.py:7698-7713` delegates to `run_omp_step`.
3. Reuse existing pieces; expired-ID test proves "static accepts, live catalog
   rejects typed".
4. `signal_hung_fixer_children` + ensure-restack still single-observation —
   extend two-scan + live-pid/seq proof to both.
5. One typed disposition helper over `IncidentLedger.append_event`; test every
   signal branch (launcher pre-exception kill; resident ladders).
6. Fingerprint: add PRE-LAUNCH enforcement, not 3rd-attempt diagnosis.

Accepted prior corrections already required by the goal/plan: public
run_step_with_worker naming; exactly-once non-OMP/OMP/babysitter door ownership;
gate-before-final-spawn/RPC; one typed disposition helper across the real launcher,
resident, watchdog, and restack signal branches; pre-launch terminal-fingerprint
refusal with durable changed-precondition identity; static-accept/live-reject
expired-ID proof; T7 cooldown scheduling-condition semantics; and T8
provider_degraded scheduling/fallback/return evidence. Repeating one of these
without new evidence is not a new finding.

Model policy: this is a normal independent critique assigned to GPT-5.6 Luna.
Do not widen the frozen goal or rewrite the plan. Return a concise critique only.
Every finding must state North Star alignment or anti-pattern impact.

Challenge execution order, synchronization seams, test realism, and whether
failures can be localized before dependent batches proceed. Look for unnecessary
serialization, unsafe parallelism, duplicated expensive validation, weak structural
spies, and missing fail-closed negative cases. Keep validation proportionate.

Return:
- `PASS_SEQUENCE_AND_VERIFICATION`, or ranked findings `SEQ-N`.
- For each: material yes/no, exact plan section and source/test evidence, simplest
  correction, criterion impact, and North Star disposition.
- Under 700 words.
