# Arnold Runtime Contract (M2a + M3d)

This document is the normative reference for the M2a and M3d runtime
surface: operation kinds, the run envelope, the step-level driver
protocol, settings categories and precedence, the legacy-resume
migration sequence, batch carriers, canonical deadline/cancellation
rules, and unsupported-mechanic declarations.  It also contains the
M2b migration checklist and the full IN-SCOPE / DEFERRED table for
all ten cross-cutting concerns.

---

## 1. Operation Kinds and the Opaque-String Rule

The runtime recognises exactly **six** neutral operation kinds,
declared in `arnold.runtime.operations.OperationKind`:

| Kind value           | Purpose                                                    |
|----------------------|------------------------------------------------------------|
| `run_phase`          | Execute one phase of the plugin.                           |
| `status_projection`  | Read or project the current run status (status + control   |
|                      | are collapsed per the "one operation or a small operation  |
|                      | family" guidance from the brief).                          |
| `resume`             | Resume an interrupted run from a cursor.                   |
| `override_list`      | Enumerate pending override actions for the caller.         |
| `override_apply`     | Apply an override action.                                  |
| `profile_validate`   | Validate a named profile against the plugin manifest.      |

### Opaque-String Rule (SD2)

`override_list` and `override_apply` carry their action vocabulary
inside `OperationRequest.payload["action"]` as an **opaque string**.
Arnold never interprets the action label.  Megaplan's 11 routed
override actions remain Megaplan vocabulary; they arrive and leave
as opaque payload bytes so M2b can migrate the existing override
dispatcher onto this seam without rewriting it.

```python
# Correct: action is opaque, Arnold never reads it
req = OperationRequest(
    kind=OperationKind.OVERRIDE_APPLY,
    payload={"action": "<plugin-owned-action-string>", ...},
)
```

---

## 2. RuntimeEnvelope — Fields, schema\_version, and JSON Shape

`RuntimeEnvelope`, `RunEnvelope`
live in `arnold.runtime.envelope`.  All three are `frozen=True` dataclasses.

### 2.1 RuntimeEnvelope fields

| Field                         | Type                        | Notes                                              |
|-------------------------------|-----------------------------|----------------------------------------------------|
| `schema_version`              | `ClassVar[int] = 2`         | Pinnable without instantiation.                    |
| `plugin_id`                   | `str`                       | Identifies the plugin.                             |
| `manifest_hash`               | `str`                       | Hash of the plugin manifest; used for trust gating.|
| `plugin_state_schema_version` | `int`                       | Plugin-owned state schema version.                 |
| `run_id`                      | `str`                       | Unique run identifier.                             |
| `artifact_root`               | `str`                       | Base path for run artifacts.                       |
| `resume_cursor`               | `ResumeCursorRef \| None`   | Opaque cursor; `None` for fresh runs.              |
| `trust_state`                 | `str`                       | Defaults to `\"unknown\"`.                           |
| `created_at`                  | `str`                       | ISO-8601 timestamp string.                         |
| `cross_cutting`               | `RunEnvelope`               | Composed cross-cutting sub-record.                 |

`lease_id`, `fencing_token`, and `capacity_grant` are carried inside
the composed :class:`RunEnvelope`, not as top-level fields on
:class:`RuntimeEnvelope`.  The M3 capacity-grant hinge semantics are
delivered through the RunEnvelope semilattice (join, fencing, capacity).

`RUNTIME_ENVELOPE_SCHEMA_VERSION` is also exported at module level so
importers can pin the integer without instantiating.

### 2.2 RunEnvelope fields (canonical cross-cutting carrier)

| Field           | Type                   | Notes                              |
|-----------------|------------------------|------------------------------------|
| `taint`         | `tuple[str, ...]`      | Taint label set.                   |
| `cost`          | `Mapping[str, Any]`    | Opaque cost accounting blob.       |
| `lineage`       | `tuple[str, ...]`      | Provenance chain.                  |
| `deadline`      | `str \| None`          | ISO-8601 deadline.                 |
| `cancellation`  | `str \| None`          | Cancellation token or reason.      |
| `retry_budget`  | `Mapping[str, Any]`    | Opaque retry-budget blob.          |
| `error_class`   | `str \| None`          | Runtime-neutral error class label. |

### RunEnvelope

`RuntimeEnvelope.to_json()` emits sorted-key JSON.
`RuntimeEnvelope.from_json()` is the inverse; it rejects a persisted
`schema_version` that does not equal the class constant.

```json
{
  "schema_version": 2,
  "plugin_id": "my-plugin",
  "manifest_hash": "sha256-abc...",
  "plugin_state_schema_version": 0,
  "run_id": "run-001",
  "artifact_root": "/var/runs/run-001",
  "resume_cursor": null,
  "trust_state": "unknown",
  "created_at": "2026-06-02T00:00:00Z",
  "cross_cutting": {
    "taint": "clean",
    "cost": 0.0,
    "lineage": [],
    "deadline": null,
    "cancellation": false,
    "retry_budget": 3,
    "error_class": null,
    "lease_id": null,
    "fencing_token": null,
    "capacity_grant": 0
  }
}
```

When `resume_cursor` is non-null its shape is:
```json
{
  "plugin_id": "<str>",
  "run_id": "<str>",
  "cursor": { "<opaque keys>": "<opaque values>" }
}
```

---

## 3. StepwiseDriver Protocol and IsolationMode Ownership

`StepwiseDriver` is a `@runtime_checkable` Protocol declared in
`arnold.runtime.driver`.

### 3.1 IsolationMode

`ISOLATION_MODES: frozenset[str]` owns the complete set of permitted
isolation modes — exactly two members:

| Value                   | Meaning                                             |
|-------------------------|-----------------------------------------------------|
| `"in_process"`          | Step executes in the same process as the runtime.   |
| `"subprocess_isolated"` | Step executes in a forked subprocess.               |

The settings resolver validates that `isolation_mode` is a member of
`ISOLATION_MODES`; any other value is a hard `isolation_mode_invalid`
validation error.

### 3.2 StepwiseDriver Protocol surface

```python
class StepwiseDriver(Protocol):
    isolation_mode: str          # must be in ISOLATION_MODES

    def advance(
        self, envelope: RuntimeEnvelope
    ) -> AdvanceOutcome: ...

    def checkpoint(
        self, envelope: RuntimeEnvelope
    ) -> CheckpointOutcome: ...

    def resume(
        self,
        envelope: RuntimeEnvelope,
        cursor: ResumeCursorRef,
    ) -> RuntimeEnvelope: ...
```

`AdvanceOutcome` and `CheckpointOutcome` are frozen dataclasses whose
`kind` field must be one of `{"advanced", "halted", "awaiting",
"failed"}` (defined in `ADVANCE_OUTCOME_KINDS` and
`CHECKPOINT_OUTCOME_KINDS`).

M2b migrates `megaplan/drivers/*` onto this Protocol surface.

---

## 4. Settings Categories, Precedence Chain, and Source Labels

Types live in `arnold.runtime.settings`; the resolver lives in
`arnold.runtime.settings_resolver`.

### 4.1 Four categories (mutually exclusive field sets)

| Category                    | Fields                                                                                               |
|-----------------------------|------------------------------------------------------------------------------------------------------|
| `InheritableSettings`       | `wall_timeout_s`, `idle_timeout_s`, `heartbeat_interval_s`, `poll_cadence_s`, `deadline_epoch_s`, `retry_budget`, `cost_cap_usd` |
| `GloballyAggregatedSettings`| `max_workers`, `cancellation`                                                                        |
| `StageLocalSettings`        | `stage_id`, `overrides`                                                                              |
| `IsolationSettings`         | `isolation_mode`                                                                                     |

No field name appears in more than one category (enforced by
`TestCategoryExclusivity`).

### 4.2 Precedence chain (last wins)

```
ARNOLD_DEFAULT < PLUGIN_DEFAULT < PROFILE < RUN_OVERRIDE < ENV_OVERRIDE
```

Each resolved key is wrapped in `EffectiveSetting(key, value, source)`
where `source` is one of the five `SettingSource` enum members:

| Member          | Value             |
|-----------------|-------------------|
| `ARNOLD_DEFAULT`| `"arnold_default"`|
| `PLUGIN_DEFAULT`| `"plugin_default"`|
| `PROFILE`       | `"profile"`       |
| `RUN_OVERRIDE`  | `"run_override"`  |
| `ENV_OVERRIDE`  | `"env_override"`  |

### 4.3 Stage inheritance and child-scope overrides

`resolve_settings()` accepts `stage_local` and `child_scope_overrides`
kwargs.  Run-level effective settings flow into each stage as a base;
stage-local overrides (sourced as `RUN_OVERRIDE`) win for the named
stage.  Child-scope overrides follow the same pattern for named child
scopes.

### 4.4 Validation errors (returned, never raised)

| Code                      | Condition                                                   |
|---------------------------|-------------------------------------------------------------|
| `unknown_stage_key`       | `stage_id` not in `pipeline_stages`.                       |
| `idle_exceeds_wall_timeout`| `idle_timeout_s > wall_timeout_s` in resolved settings.   |
| `negative_timeout`        | Any timeout key (`wall_timeout_s`, `idle_timeout_s`, `heartbeat_interval_s`, `poll_cadence_s`) resolves to a negative value. |
| `isolation_mode_invalid`  | Resolved `isolation_mode` not in `ISOLATION_MODES`.         |
| `max_workers_nonpositive` | Resolved `max_workers` <= 0.                                |
| `deadline_negative`       | Resolved `deadline_epoch_s` < 0 (SD3; positive expired deadline is a runtime concern, not a validation error). |
| `cost_cap_negative`       | Resolved `cost_cap_usd` < 0.                                |
| `heartbeat_nonpositive`   | `heartbeat_interval_s` is set and <= 0.                     |
| `poll_cadence_nonpositive`| `poll_cadence_s` is set and <= 0.                           |

### 4.5 Canonical deadline and cancellation (SD1, SD2)

**`deadline_epoch_s: float | None`** (in `InheritableSettings`) is the
only canonical deadline for runtime comparisons.  Arnold batch runners
and timeout supervisors compare `time.time()` against
`deadline_epoch_s` — a numeric, epoch-seconds value.

`RunEnvelope.deadline: float | None` is **metadata only**.  It
carries a POSIX timestamp for the envelope semilattice but is
**never used for deadline enforcement** by Arnold batch runners or
timeout supervisors — those use `deadline_epoch_s` exclusively (SD1).

**`GloballyAggregatedSettings.cancellation: bool`** is the canonical
cancellation request.  Arnold batch runners check this boolean to
decide whether to stop processing new units.

`RunEnvelope.cancellation: bool` is **opaque metadata**
carried through the envelope semilattice.  It is never evaluated by
Arnold mechanics for cancellation enforcement (SD2).

### 4.6 Negative vs expired deadlines (SD3)

A **negative** `deadline_epoch_s` is a configuration error:
`deadline_negative` in the resolver.  An **already-expired positive**
deadline is a valid runtime condition that produces a neutral
`deadline_expired` outcome — the caller (Megaplan) decides whether to
retry, escalate, or halt.

### 4.7 Unsupported mechanics (SD4)

`idle_timeout_s` and `heartbeat_interval_s` are declared contract
fields on `InheritableSettings` but are **unsupported mechanics in
M3d**.  Arnold dry-run output annotates both keys with
`(unsupported)`.  Batch runners never enforce idle-output polling or
heartbeat emission.  Full implementation is deferred to a later
milestone.

---

## 5. Legacy-Resume Migration Sequence

`migrate_legacy_resume()` in `arnold.runtime.resume` is a **pure
function** — it never writes state; callers own persistence.

### 5.1 Sequence

1. **Non-mapping input** → return `(None, TrustTransition("unknown", "unknown"))`.
2. **Already-migrated state** (has a `runtime_envelope` block with
   valid `plugin_id` and `run_id`) → return the existing cursor +
   `TrustTransition("unknown", "trusted")` without re-running the hash
   check.
3. **Fresh migration**:
   a. Extract `plugin_id` and `run_id`; either missing/non-string →
      return the malformed result.
   b. Locate the stored manifest hash via `manifest_hash` key first,
      then `manifest_sha256` alias; missing or non-string → return the
      malformed result.
   c. Strip **excluded keys** from the cursor payload:
      `phase`, `stage`, `plugin_id`, `run_id`, `manifest_hash`,
      `manifest_sha256`, `runtime_envelope`.
   d. Compare stored hash against `current_manifest_hash`:
      - Match → `TrustTransition("unknown", "trusted")`.
      - Mismatch → `TrustTransition("unknown",
        "quarantined-manifest-mismatch")`.

### 5.2 Dual-key compatibility (`phase` / `stage`)

Both the legacy `phase` key and the legacy `stage` key are accepted as
the in-flight step identifier and both are **excluded** from the cursor
payload.  The exclusion is unconditional: neither key leaks into the
neutral `ResumeCursorRef.cursor` mapping.

### 5.3 None-on-malformed policy

Every malformed-state case (non-mapping, missing identifiers,
non-string identifiers) returns `(None, TrustTransition("unknown",
"unknown"))`.  The function never raises on bad input.

---

## 6. M2b Migration Checklist

The following five migration targets must be completed in M2b.  Each
item is independent and may be tackled in any order, but all five must
be done before the M2a runtime surface can be considered load-bearing
for production traffic.

1. **`megaplan/auto.py::drive()`** — migrate the drive loop to accept
   a `RuntimeEnvelope` instead of the legacy `RunEnvelope`; wire
   `OperationRegistry` dispatch for `run_phase` and `status_projection`
   operations; thread `resume_cursor` through the `RESUME` operation
   kind on warm-start paths.

2. **`megaplan/handlers/resume.py`** — replace the legacy resume-state
   load path with a call to `migrate_legacy_resume()`; persist the
   returned `ResumeCursorRef` into a `RuntimeEnvelope` block; honour
   the `TrustTransition` output by writing `trust_state` into the
   envelope before dispatching the driver.

3. **`megaplan/control_interface.py` dispatch** — migrate the dispatch
   router to call `OperationRegistry.dispatch()` for the
   `override_list` and `override_apply` operation kinds; preserve the
   existing action vocabulary as opaque `payload["action"]` strings so
   no re-naming is needed.

4. **`megaplan/cli/*` profile commands** — thread the five-layer
   settings precedence chain through profile-bearing CLI commands;
   emit `EffectiveSetting` source attribution in dry-run output;
   validate `isolation_mode` against `ISOLATION_MODES` at command
   entry.

5. **`megaplan/drivers/*`** — adopt the `StepwiseDriver` Protocol;
   declare `isolation_mode` as a string attribute pinned to one of the
   two values in `ISOLATION_MODES`; implement `advance`, `checkpoint`,
   and `resume` methods with the prescribed outcome carriers.

---

## 7. IN-SCOPE / DEFERRED Table

The following table covers all ten cross-cutting areas identified in
the M2a brief.  "IN SCOPE" means M2a land at least a structural stub
or carrier for this concern; "DEFERRED" means M2a intentionally omits
it and a later milestone owns the semantics.

| Cross-cutting area          | Status    | M2a Surface / Notes                                                                        | Target (DEFERRED) |
|-----------------------------|-----------|--------------------------------------------------------------------------------------------|--------------------|
| identity/discovery          | DEFERRED  | `plugin_id` and `manifest_hash` are carried in `RuntimeEnvelope` as opaque strings.  Full service-registry discovery and plugin-manifest negotiation are out of scope. | M3a |
| model/profile routing       | DEFERRED  | No routing logic in `arnold/runtime/`; tier-model selection and profile routing remain Megaplan concerns. | M5a |
| prompt/context              | DEFERRED  | No prompt construction or context-window management; those remain Megaplan concerns.       | M5a |
| artifact/dataflow           | DEFERRED  | `artifact_root` is carried as an opaque path.  Artifact schema, content-hash policy, and dataflow graph are out of scope. | M3c |
| control/resume              | IN SCOPE  | `ResumeCursorRef`, `TrustTransition`, `migrate_legacy_resume()`, and the `RESUME` operation kind are all landed.  The `resume` method on `StepwiseDriver` is defined. | — |
| recovery/failure            | IN SCOPE  | `InheritableSettings.retry_budget`, `cost_cap_usd`, and the nine validation rules (including `deadline_negative`, `cost_cap_negative`, `heartbeat_nonpositive`, `poll_cadence_nonpositive`) provide the structural recovery envelope.  Per-step retry semantics are M2b driver responsibility. | — |
| resource/security           | IN SCOPE  | `wall_timeout_s`, `idle_timeout_s` (unsupported in M3d), `heartbeat_interval_s` (unsupported in M3d), `poll_cadence_s`, `deadline_epoch_s`, `cost_cap_usd` are all in `InheritableSettings`.  Canonical deadline/cancellation per SD1/SD2.  Trust-state labels provide the quarantine hook. | — |
| isolation/environment       | IN SCOPE  | `ISOLATION_MODES` + `IsolationSettings.isolation_mode` define the two supported isolation boundaries.  Subprocess-launch knobs (image, env injection, resource limits) are reserved for a later milestone. | — |
| observability/audit         | DEFERRED  | No event emission, structured logging, or audit trails in `arnold/runtime/`.              | M7 |
| composition/subpipeline policy | DEFERRED | Fan-out semantics, nesting rules, and sub-pipeline composition policy are out of scope. `ParallelStage` in the executor raises `NotImplementedError` as a deliberate M2b placeholder. | M3c |

---

## 8. Batch Outcome Mechanics (M3d)

Arnold batch runners (`scatter_gather_threaded` and
`scatter_gather_processes`) classify every run into exactly one
**neutral outcome kind** drawn from `BATCH_OUTCOME_KINDS`.  The
runners detect these conditions and emit the corresponding
`BatchRunResult.outcome_kind` — they **never** raise exceptions for
operational conditions.  Callers (Megaplan adapters) translate each
outcome into domain-appropriate actions.

### 8.1 Neutral outcome kinds detected by Arnold

| Outcome kind            | Detected by Arnold when …                                                                    |
|-------------------------|---------------------------------------------------------------------------------------------|
| `completed`             | All units finished within resource bounds — the default.                                    |
| `wall_timeout`          | The per-unit wall-clock timeout expired and the unit was terminated / killed.  Siblings     |
|                         | continue unaffected.  The timed-out unit produces a sentinel result via `on_unit_error`.   |
| `deadline_expired`      | `deadline_epoch_s` is set and `time.time() > deadline_epoch_s`.  **Process runner**:        |
|                         | detected pre-launch (returns immediately without spawning children).  **Thread runner**:    |
|                         | detected post-execution (all submitted units complete, then outcome is classified).         |
| `cancelled`             | `cancellation_requested` is `True`.  **Process runner**: detected pre-launch.               |
|                         | **Thread runner**: detected post-execution.                                                 |
| `idle_unsupported`      | `idle_timeout_s` is set (non-`None`) — Arnold annotates but does **not** enforce            |
|                         | idle-output polling.  This is a declared-but-unsupported mechanic in M3d.                   |
| `heartbeat_unsupported` | `heartbeat_interval_s` is set (non-`None`) — Arnold annotates but does **not** enforce      |
|                         | heartbeat emission.  This is a declared-but-unsupported mechanic in M3d.                    |
| `error`                 | Every unit produced an error result (process runner only).                                  |

### 8.2 Unsupported mechanics (idle / heartbeat)

`idle_timeout_s` and `heartbeat_interval_s` are **declared contract
fields** on `InheritableSettings` and `BatchRuntimeSettings` but are
**unsupported in M3d**.  Arnold dry-run output annotates both keys with
`(unsupported)`.  Arnold batch runners do **not** implement
idle-output polling or heartbeat emission.  Full implementation is
deferred to a later milestone.

When either field is non-`None`, the process runner returns
`idle_unsupported` / `heartbeat_unsupported` immediately (pre-launch).
The thread runner does not inspect these fields.

### 8.3 Megaplan outcome translation (M3d adapters)

Megaplan adapters (`hermes_fanout.scatter_gather`,
`hermes_fanout.scatter_gather_processes`, and future worker-fanout
adapters) translate Arnold's neutral `BatchRunResult.outcome_kind`
into Megaplan-appropriate actions:

| Arnold outcome         | Megaplan adapter action                                                                    |
|------------------------|-------------------------------------------------------------------------------------------|
| `completed`            | Return `GenericScatterResult` with ordered results, totals, and side results.             |
| `wall_timeout`         | Timed-out units appear as sentinel error results via `on_unit_error`; completed siblings  |
|                        | are included in ordered results.  Total cost/tokens reflect completed units only.         |
| `deadline_expired`     | Process adapter: if `on_unit_error` was provided, produce sentinel results for all        |
|                        | pending units; otherwise raise `CliError(\"worker_error\", …)`.  Thread adapter:            |
|                        | all units already completed; the outcome is informational only.                           |
| `cancelled`            | Same as `deadline_expired` — sentinel results via `on_unit_error` when available,         |
|                        | otherwise `CliError`.                                                                      |
| `idle_unsupported`     | Raise `CliError(\"worker_error\", …)` — the caller configured an unsupported mechanic.      |
| `heartbeat_unsupported`| Same as `idle_unsupported`.                                                               |
| `error`                | All units failed; results are propagated as-is.  Callers may treat the full-error          |
|                        | condition as a retry / escalation signal at the orchestration layer.                      |

This mapping is **intentionally owned by the Megaplan adapter layer**,
not by Arnold.  Arnold remains policy-free: it classifies the outcome
and returns a neutral `BatchRunResult`; the adapter decides whether to
retry, escalate, or halt.

---

## 9. M5b Extraction Map

This section is the normative extraction map for **M5b** ("Move Execute,
Review, And Orchestration Policy Into The Plugin").  It enumerates three
sets of boundaries settled during M3d implementation so that M5b can
depend on Arnold mechanics without re-litigating design decisions.

### 9.1 Megaplan-owned policy (must remain in Megaplan for M5b)

These policy concerns are **not moved into Arnold** by M3d.  They remain
in `megaplan/execute/`, `megaplan/review/`, `megaplan/orchestration/`,
and their callers.  M5b relocates them into the Megaplan plugin package;
Arnold never encodes their meanings or defaults.

| #  | Policy concern                     | Current home (representative)                                | Notes                                                                 |
|----|------------------------------------|--------------------------------------------------------------|-----------------------------------------------------------------------|
| 1  | Destructive confirmation           | `megaplan/execute/core.py`, `batch.py`                       | User-acknowledged irreversible actions; gating before execution.      |
| 2  | Review-mode approval               | `megaplan/review/checks.py`, `parallel.py`                   | Approval gating tied to review verdicts; plugin-owned semantics.      |
| 3  | Blocked lifecycle                  | `megaplan/execute/core.py`, `orchestration/recovery_policy.py`| Blocked-task state machine: detect, retry, escalate, or halt.         |
| 4  | Retry-blocked-tasks                | `megaplan/orchestration/recovery_policy.py`                  | Policy decision to retry tasks that are blocked (vs fresh or external).|
| 5  | Batch transitions                  | `megaplan/execute/batch.py`                                  | How execute moves from one batch to the next (size, ordering, gates). |
| 6  | Timeout checkpoint recovery        | `megaplan/execute/timeout.py`                                | Merging checkpointed partial results after a timeout; evidence reset. |
| 7  | Evidence attribution               | `megaplan/orchestration/execution_evidence.py`               | Which step produced which evidence; evidence sufficiency checks.      |
| 8  | Task complexity / tier selection   | `megaplan/execute/_binding/tier.py`                          | Model-tier assignment based on task complexity; cost/quality tradeoff.|
| 9  | Review checks                      | `megaplan/review/checks.py`, `mechanical.py`                 | Incomplete verdicts, empty evidence, rework staying in review,        |
|    |                                    |                                                              | batch-by-batch review, blocked-status acceptance.                     |
| 10 | Execute policy (general)           | `megaplan/execute/` broadly                                  | Task batching, prerequisites, history entries, approval mode,         |
|    |                                    |                                                              | evidence validation, final-plan artifact assembly.                    |
| 11 | Orchestration policy (general)     | `megaplan/orchestration/` broadly                            | Gate checks, plan audit, tiebreaker support, iteration pressure,      |
|    |                                    |                                                              | completion contracts, critique status, verifiability, suite running.  |
| 12 | Recovery defaults & vocabularies   | `megaplan/orchestration/recovery_policy.py`                  | `retry_fresh`, `retry_transient`, `halt`, `escalate`, budget defaults,|
|    |                                    |                                                              | external retry phase lists — all remain Megaplan vocabulary.          |
| 13 | Megaplan phase vocabulary          | All `megaplan/` modules                                      | Phase names (`planning`, `critique`, `finalize`, `tiebreaker`,        |
|    |                                    |                                                              | `escalate`), override action labels, gate labels — never in Arnold.   |

### 9.2 Arnold-owned mechanics available for M5b

These mechanics were extracted or created during M3d and are **neutral,
policy-free, and importable from `arnold.runtime` or `arnold.pipeline`**.
M5b code may depend on them freely — they carry no Megaplan defaults.

| #  | Mechanic                                       | Module                                  | Notes                                                              |
|----|------------------------------------------------|-----------------------------------------|--------------------------------------------------------------------|
| 1  | Batch carriers                                 | `arnold.runtime.batch`                  | `BatchUnit`, `BatchUnitResult`, `BatchRunResult`,                   |
|    |                                                |                                         | `BatchRuntimeSettings`, `BatchOutcomeKind`, hook Protocol types.    |
| 2  | Runtime settings normalization                 | `arnold.runtime.batch_settings`         | `build_batch_runtime_settings()` — maps resolved settings into      |
|    |                                                |                                         | `BatchRuntimeSettings` without parsing envelope strings.            |
| 3  | Neutral wall / deadline / cancellation detection| `arnold.runtime.batch`                  | `wall_timeout`, `deadline_expired`, `cancelled` outcomes detected   |
|    |                                                |                                         | by `scatter_gather_threaded` and `scatter_gather_processes`.        |
| 4  | Thread-pool scatter-gather                     | `arnold.runtime.batch`                  | `scatter_gather_threaded()` — deterministic ordered results,        |
|    |                                                |                                         | side-task aggregation, cost/token totals, tolerant `on_unit_error`. |
| 5  | Process-pool scatter-gather                    | `arnold.runtime.batch`                  | `scatter_gather_processes()` — spawn context, wall-timeout kill,    |
|    |                                                |                                         | hard-kill grace, deadline/cancellation pre-flight checks.           |
| 6  | Recovery classifier Protocol                   | `arnold.runtime.recovery`               | `ArnoldRecoveryPolicy` Protocol with `classify(error, context)`;    |
|    |                                                |                                         | `RecoveryContext`, `RecoveryDecision` frozen carriers.              |
| 7  | Null recovery policy                           | `arnold.runtime.recovery`               | `NullRecoveryPolicy` — returns `status='unset'`; no silent fallback |
|    |                                                |                                         | to Megaplan defaults.                                               |
| 8  | Settings validation                            | `arnold.runtime.settings` / `_resolver`  | Nine validation rules (incl. `deadline_negative`, `cost_cap_negative`,|
|    |                                                |                                         | `heartbeat_nonpositive`, `poll_cadence_nonpositive`).               |
| 9  | Dry-run source reporting                       | `arnold.runtime.dry_run`                | `dry_run_report()` — annotates every effective setting with its      |
|    |                                                |                                         | source layer and `(unsupported)` tags for idle/heartbeat.           |
| 10 | Pipeline fan-out `max_workers` fallback        | `arnold.pipeline.executor`              | `_run_parallel_stage()` and `run_fanout()` accept inherited          |
|    |                                                | `arnold.pipeline.pattern_dynamic`       | `max_workers`; explicit stage/concurrency settings win.             |
| 11 | Subprocess driver deadline capping             | `megaplan/drivers/subprocess_isolated.py`| Accepts `batch_settings` (`BatchRuntimeSettings`); computes          |
|    |                                                |                                         | `min(wall_cap, wall_timeout_s, deadline_remaining_s)` at run time.  |
| 12 | Operation registry & run envelope              | `arnold.runtime.operations`             | `OperationKind`, `OperationRequest`/`OperationResult`,               |
|    |                                                | `arnold.runtime.envelope`               | `RuntimeEnvelope`, `RunEnvelope` — all neutral carriers.   |
| 13 | StepwiseDriver Protocol                        | `arnold.runtime.driver`                 | `StepwiseDriver`, `ISOLATION_MODES`, `AdvanceOutcome`,               |
|    |                                                |                                         | `CheckpointOutcome` — driver contract for M5b to implement.         |
| 14 | Legacy-resume migration                        | `arnold.runtime.resume`                 | `migrate_legacy_resume()` — pure function; callers own persistence. |
| 15 | Canonical deadline / cancellation rules        | `arnold.runtime.settings`               | SD1: `deadline_epoch_s` (float|None) canonical; envelope deadline    |
|    |                                                | `arnold.runtime.CONTRACT.md` §4.5       | is metadata.  SD2: `cancellation` (bool) canonical; envelope string |
|    |                                                |                                         | is opaque token/reason.                                             |
| 16 | Settings categories & precedence               | `arnold.runtime.settings` / `_resolver` | Four categories (Inheritable, GloballyAggregated, StageLocal,        |
|    |                                                |                                         | Isolation); five-layer precedence chain; `EffectiveSetting` wrapper. |

### 9.3 Explicit M3d deferrals (M5b must not depend on)

These mechanics are **declared but not implemented** in M3d.  M5b must
either avoid them, implement them first, or accept that they are absent.

| #  | Deferred mechanic                     | Status in M3d                                        | Target milestone |
|----|---------------------------------------|------------------------------------------------------|------------------|
| 1  | Idle-output supervision               | `idle_timeout_s` is a declared field on              | Later (post-M5b) |
|    |                                       | `BatchRuntimeSettings` but triggers `idle_unsupported`|
|    |                                       | outcome in process runner; thread runner ignores it. |
| 2  | Heartbeat emission / checking         | `heartbeat_interval_s` is a declared field but       | Later (post-M5b) |
|    |                                       | triggers `heartbeat_unsupported` outcome in process  |
|    |                                       | runner; thread runner ignores it.                    |
| 3  | Full subprocess supervisor extraction | `_supervise_subprocess` remains in Megaplan          | Later (post-M5b) |
|    |                                       | (`megaplan/drivers/subprocess_isolated.py`). Only    |
|    |                                       | deadline capping was threaded through in M3d.        |
| 4  | Moving execute / review /             | These policy modules are **untouched** by M3d.       | M5b              |
|    | orchestration policy                  | Their relocation is the M5b deliverable.             |
| 5  | Output polling infrastructure         | No polling loop, event emission, or structured       | Later (post-M5b) |
|    |                                       | logging exists in `arnold/runtime/`.                 |
| 6  | Per-step retry semantics              | Retry budget envelope exists in `InheritableSettings`| M2b / M5b driver |
|    |                                       | but per-step retry logic is driver/adapter concern.  | responsibility   |

### 9.4 How to read this map

- **§9.1 items** are Megaplan policy.  M5b moves them into the plugin
  (`arnold/pipelines/megaplan/` or equivalent).  Arnold never imports or
  references them.
- **§9.2 items** are Arnold mechanics.  M5b code may `import` them
  directly from `arnold.runtime` or `arnold.pipeline`.  They carry no
  opinion about execute, review, or orchestration meanings.
- **§9.3 items** are gaps.  If M5b needs idle-output polling, heartbeat
  infrastructure, or a fully extracted subprocess supervisor, it must
  build them before depending on them — or defer them further.
