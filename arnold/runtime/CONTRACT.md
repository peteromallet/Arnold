# Arnold Runtime Contract (M2a)

This document is the normative reference for the M2a runtime surface:
operation kinds, the run envelope, the step-level driver protocol,
settings categories and precedence, and the legacy-resume migration
sequence.  It also contains the M2b migration checklist and the full
IN-SCOPE / DEFERRED table for all ten cross-cutting concerns.

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

`RuntimeEnvelope` and `CrossCuttingEnvelope` live in
`arnold.runtime.envelope`.  Both are `frozen=True` dataclasses.

### 2.1 RuntimeEnvelope fields

| Field                         | Type                        | Notes                                              |
|-------------------------------|-----------------------------|----------------------------------------------------|
| `schema_version`              | `ClassVar[int] = 1`         | Pinnable without instantiation.                    |
| `plugin_id`                   | `str`                       | Identifies the plugin.                             |
| `manifest_hash`               | `str`                       | Hash of the plugin manifest; used for trust gating.|
| `plugin_state_schema_version` | `int`                       | Plugin-owned state schema version.                 |
| `run_id`                      | `str`                       | Unique run identifier.                             |
| `artifact_root`               | `str`                       | Base path for run artifacts.                       |
| `resume_cursor`               | `ResumeCursorRef \| None`   | Opaque cursor; `None` for fresh runs.              |
| `trust_state`                 | `str`                       | Defaults to `"unknown"`.                           |
| `created_at`                  | `str`                       | ISO-8601 timestamp string.                         |
| `cross_cutting`               | `CrossCuttingEnvelope`      | Composed cross-cutting sub-record.                 |

`lease_id`, `fencing_token`, and `capacity_grant` are **intentionally
absent** (SD3): those are M3 capacity-grant hinge concerns.

`RUNTIME_ENVELOPE_SCHEMA_VERSION` is also exported at module level so
importers can pin the integer without instantiating.

### 2.2 CrossCuttingEnvelope fields

| Field           | Type                   | Notes                              |
|-----------------|------------------------|------------------------------------|
| `taint`         | `tuple[str, ...]`      | Taint label set.                   |
| `cost`          | `Mapping[str, Any]`    | Opaque cost accounting blob.       |
| `lineage`       | `tuple[str, ...]`      | Provenance chain.                  |
| `deadline`      | `str \| None`          | ISO-8601 deadline.                 |
| `cancellation`  | `str \| None`          | Cancellation token or reason.      |
| `retry_budget`  | `Mapping[str, Any]`    | Opaque retry-budget blob.          |
| `error_class`   | `str \| None`          | Runtime-neutral error class label. |

### 2.3 JSON shape

`RuntimeEnvelope.to_json()` emits sorted-key JSON.
`RuntimeEnvelope.from_json()` is the inverse; it rejects a persisted
`schema_version` that does not equal the class constant.

```json
{
  "schema_version": 1,
  "plugin_id": "my-plugin",
  "manifest_hash": "sha256-abc...",
  "plugin_state_schema_version": 0,
  "run_id": "run-001",
  "artifact_root": "/var/runs/run-001",
  "resume_cursor": null,
  "trust_state": "unknown",
  "created_at": "2026-06-02T00:00:00Z",
  "cross_cutting": {
    "cancellation": null,
    "cost": {},
    "deadline": null,
    "error_class": null,
    "lineage": [],
    "retry_budget": {},
    "taint": []
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
| `negative_timeout`        | Any timeout key resolves to a negative value.               |
| `isolation_mode_invalid`  | Resolved `isolation_mode` not in `ISOLATION_MODES`.         |
| `max_workers_nonpositive` | Resolved `max_workers` <= 0.                                |

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
| recovery/failure            | IN SCOPE  | `InheritableSettings.retry_budget`, `cost_cap_usd`, and the five validation rules provide the structural recovery envelope.  Per-step retry semantics are M2b driver responsibility. | — |
| resource/security           | IN SCOPE  | `wall_timeout_s`, `idle_timeout_s`, `heartbeat_interval_s`, `poll_cadence_s`, `deadline_epoch_s`, `cost_cap_usd` are all in `InheritableSettings`.  Trust-state labels provide the quarantine hook. | — |
| isolation/environment       | IN SCOPE  | `ISOLATION_MODES` + `IsolationSettings.isolation_mode` define the two supported isolation boundaries.  Subprocess-launch knobs (image, env injection, resource limits) are reserved for a later milestone. | — |
| observability/audit         | DEFERRED  | No event emission, structured logging, or audit trails in `arnold/runtime/`.              | M7 |
| composition/subpipeline policy | DEFERRED | Fan-out semantics, nesting rules, and sub-pipeline composition policy are out of scope. `ParallelStage` in the executor raises `NotImplementedError` as a deliberate M2b placeholder. | M3c |
