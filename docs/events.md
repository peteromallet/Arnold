# Event-Kind Taxonomy — Megaplan Observability Layer

**Status:** Locked (2026-05-18)
**Source:** `docs/observability-and-introspection-design.md`, § "Event kinds (~25 total)"
**Total kinds:** 25 across 7 groups

Every event is one JSON line in `.megaplan/plans/<name>/events.ndjson`. Common envelope:

```jsonc
{
  "seq": 142,                          // monotonic, gap-detectable
  "ts_utc": "2026-05-18T14:25:11.483Z",
  "ts_rel_init_s": 3721.4,             // seconds since init
  "kind": "<kind>",
  "phase": "critique",                 // current phase, or null for plan-global events
  "payload": { ... }                   // kind-specific
}
```

---

## 1. Lifecycle (9 kinds)

Events emitted by the state-machine driver (`megaplan/auto.py`) and lock plumbing at phase transitions.

### 1.1 `init`

First event per plan. Written before the main drive loop begins.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — main `drive()` entry, before loop |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "init",
  "phase": null,
  "payload": {
    "plan_name": "obs-introspect-layer",
    "profile": "partnered",
    "robustness": "full",
    "depth": "high",
    "vendor": "claude",
    "binary_version": "0.21.0",
    "workflow": ["prep","plan","critique","gate","revise","finalize","execute","review"]
  }
}
```

### 1.2 `phase_start`

Emitted when the driver enters a new phase.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — before `_run_phase()` |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "phase_start",
  "phase": "critique",
  "payload": {
    "phase": "critique",
    "model": "claude:opus-4.7",
    "phase_timeout_s": 1800,
    "attempt": 1
  }
}
```

### 1.3 `phase_end`

Emitted when a phase completes successfully.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — after `_run_phase()` returns |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "phase_end",
  "phase": "critique",
  "payload": {
    "phase": "critique",
    "duration_s": 2341.2,
    "exit_code": 0,
    "artifacts_written": 7
  }
}
```

### 1.4 `phase_retry`

Emitted when a phase is retried (context exhaustion, provider fallback, error recovery).

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` (retry paths) + `megaplan/workers/hermes.py` (MiniMax→OpenRouter fallback) |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "phase_retry",
  "phase": "critique",
  "payload": {
    "phase": "critique",
    "attempt": 2,
    "reason": "context_exhaustion",
    "previous_model": "claude:opus-4.7",
    "next_model": "claude:opus-4.7",
    "truncation_applied": true
  }
}
```

### 1.5 `state_transition`

Emitted on every state-machine transition (e.g. `planned → critiquing`, `critiquing → critiqued`).

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — at state-variable assignment points |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "state_transition",
  "phase": null,
  "payload": {
    "from_state": "planned",
    "to_state": "critiquing",
    "trigger": "phase_start:critique",
    "iteration": 0
  }
}
```

### 1.6 `lock_acquired`

Emitted when the plan-level advisory lock is acquired.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — lock plumbing |
| **Consumed by** | `introspect`, `doctor` |

```jsonc
{
  "kind": "lock_acquired",
  "phase": null,
  "payload": {
    "lock_path": ".megaplan/plans/obs-introspect-layer/lock",
    "holder_pid": 58769,
    "holder_host": "macbook-pro.local"
  }
}
```

### 1.7 `lock_released`

Emitted when the plan-level advisory lock is released.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — lock plumbing |
| **Consumed by** | `introspect`, `doctor` |

```jsonc
{
  "kind": "lock_released",
  "phase": null,
  "payload": {
    "lock_path": ".megaplan/plans/obs-introspect-layer/lock",
    "held_duration_s": 3847.3,
    "holder_pid": 58769
  }
}
```

### 1.8 `plan_aborted`

Emitted when the plan terminates abnormally (unhandled exception, SIGTERM, user abort).

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — terminal error/abort paths |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "plan_aborted",
  "phase": "critique",
  "payload": {
    "reason": "unhandled_exception",
    "exception_type": "RuntimeError",
    "exception_message": "hermes returned non-zero: 137",
    "last_phase": "critique",
    "total_duration_s": 3847.3,
    "total_cost_usd": 12.45
  }
}
```

### 1.9 `plan_finished`

Emitted when the plan completes all phases successfully.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — terminal success path |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "plan_finished",
  "phase": null,
  "payload": {
    "total_duration_s": 5241.8,
    "total_cost_usd": 18.73,
    "phases_completed": ["prep","plan","critique","gate","revise","finalize","execute","review"],
    "exit_code": 0
  }
}
```

---

## 2. Subprocess (3 kinds)

Emitted by the subprocess context manager wrapping all worker spawns.

### 2.1 `subprocess_spawned`

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/observability/events.py` — `spawned()` context manager, applied at `_impl.py`, `auto.py`, `shannon.py` |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "subprocess_spawned",
  "phase": "critique",
  "payload": {
    "pid": 58800,
    "argv_redacted": ["python3", "-m", "hermes", "...", "--model", "claude:opus-4.7", "..."],
    "role": "critique_worker",
    "parent_pid": 58769
  }
}
```

### 2.2 `subprocess_exited`

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/observability/events.py` — `spawned()` context manager |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "subprocess_exited",
  "phase": "critique",
  "payload": {
    "pid": 58800,
    "returncode": 0,
    "duration_s": 2341.2,
    "role": "critique_worker"
  }
}
```

### 2.3 `subprocess_signaled`

Emitted when a subprocess dies from a signal (negative returncode).

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/observability/events.py` — `spawned()` context manager, on negative returncode |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "subprocess_signaled",
  "phase": "critique",
  "payload": {
    "pid": 58800,
    "signal": 9,
    "signal_name": "SIGKILL",
    "duration_s": 451.7,
    "role": "critique_worker",
    "last_stdout_line": "check 4/7: all_locations...",
    "last_stderr_line": null
  }
}
```

---

## 3. LLM (4 kinds)

Emitted by Hermes instrumentation (`megaplan/workers/hermes.py`).

### 3.1 `llm_call_start`

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/workers/hermes.py` — `run_hermes_step()`, before agent invocation |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "llm_call_start",
  "phase": "critique",
  "payload": {
    "provider": "anthropic",
    "model": "claude:opus-4.7",
    "prompt_hash": "a1b2c3d4e5f6a7b8",
    "streaming": true,
    "request_id": null,
    "max_tokens": 32000
  }
}
```

### 3.2 `llm_token_heartbeat`

~1 Hz during streaming LLM calls. Groups consecutive heartbeats in narrative rendering.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/workers/hermes.py` — token-heartbeat daemon thread |
| **Consumed by** | `trace`, `dash` (primary); `introspect` (for liveness) |

```jsonc
{
  "kind": "llm_token_heartbeat",
  "phase": "critique",
  "payload": {
    "tokens_emitted_so_far": 4234,
    "last_token_at": "2026-05-18T14:25:11.200Z",
    "tokens_per_second": 18.3,
    "provider": "anthropic",
    "model": "claude:opus-4.7"
  }
}
```

### 3.3 `llm_call_end`

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/workers/hermes.py` — after `run_conversation()` returns |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "llm_call_end",
  "phase": "critique",
  "payload": {
    "provider": "anthropic",
    "model": "claude:opus-4.7",
    "request_id": "req_01JX2K8N9PQ3RST4UVW5",
    "tokens_in": 48500,
    "tokens_out": 8200,
    "cost_usd": 1.23,
    "finish_reason": "end_turn",
    "duration_s": 312.4,
    "streaming": true
  }
}
```

### 3.4 `llm_call_error`

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/workers/hermes.py` — exception handler around LLM call |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "llm_call_error",
  "phase": "critique",
  "payload": {
    "provider": "anthropic",
    "model": "claude:opus-4.7",
    "provider_error_code": "rate_limit_exceeded",
    "retry_after_s": 30,
    "attempt": 2,
    "exception_type": "RateLimitError",
    "duration_to_error_s": 12.1
  }
}
```

---

## 4. Artifacts (2 kinds)

### 4.1 `artifact_written`

Emitted at the `atomic_write_json` / `atomic_write_text` level after every artifact write.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/_core/io.py` — wrap `atomic_write_json` and `atomic_write_text` |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "artifact_written",
  "phase": "critique",
  "payload": {
    "path": "critique_check_scope.json",
    "path_relative": "critique_check_scope.json",
    "size_bytes": 4521,
    "artifact_type": "critique_check"
  }
}
```

### 4.2 `artifact_invalidated`

Emitted when an artifact is deleted or superseded.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/handlers/` — artifact deletion/mutation paths |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "artifact_invalidated",
  "phase": "revise",
  "payload": {
    "path": "plan.md",
    "reason": "superseded_by_revise",
    "replaced_by": "revised_plan.md"
  }
}
```

---

## 5. Decisions (4 kinds)

### 5.1 `override_applied`

Emitted from each `_override_*` handler.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/handlers/override.py` — every `_override_*` function |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "override_applied",
  "phase": null,
  "payload": {
    "action": "set_profile",
    "previous_value": "partnered",
    "new_value": "premium",
    "reason": "escalating tier mid-run — critique found deeper issues than expected",
    "source": "user",
    "timestamp": "2026-05-18T14:30:00Z"
  }
}
```

### 5.2 `flag_raised`

Emitted when new unresolved flags appear in a gate pass.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/handlers/gate.py` — gate signal builder |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "flag_raised",
  "phase": "gate",
  "payload": {
    "flag_id": "FLAG-V4-001",
    "severity": "high",
    "summary": "brief invariant 2 contradicts decision 8 on slot body extension",
    "check": "correctness",
    "iteration": 3
  }
}
```

### 5.3 `flag_resolved`

Emitted when previously-unresolved flags disappear between gate passes.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/handlers/gate.py` — gate signal builder |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "flag_resolved",
  "phase": "gate",
  "payload": {
    "flag_id": "FLAG-V4-001",
    "resolution": "revise_addressed",
    "iteration": 4
  }
}
```

### 5.4 `note_added`

Emitted from `_override_add_note` and `megaplan record-tag`.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/handlers/override.py` (`_override_add_note`) + `megaplan/cli.py` (`record-tag`) |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "note_added",
  "phase": null,
  "payload": {
    "tag": "user-intervened",
    "note": "Raised cost cap to $50 after reviewing spend trajectory",
    "source": "cli",
    "timestamp": "2026-05-18T14:35:00Z"
  }
}
```

---

## 6. Cost (1 kind)

### 6.1 `cost_recorded`

Per-LLM-call cost record with provider `request_id` for audit.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/workers/hermes.py` — after `llm_call_end` |
| **Consumed by** | `introspect`, `trace`, `doctor`, `dash` |

```jsonc
{
  "kind": "cost_recorded",
  "phase": "critique",
  "payload": {
    "request_id": "req_01JX2K8N9PQ3RST4UVW5",
    "provider": "anthropic",
    "model": "claude:opus-4.7",
    "cost_usd": 1.23,
    "tokens_in": 48500,
    "tokens_out": 8200,
    "cumulative_cost_usd": 18.73
  }
}
```

---

## 7. Diagnostics (2 kinds)

### 7.1 `health_check_failed`

Emitted when a worker health check fails (stalled subprocess, unresponsive worker).

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/auto.py` — worker health-check paths |
| **Consumed by** | `introspect`, `doctor`, `dash` |

```jsonc
{
  "kind": "health_check_failed",
  "phase": "critique",
  "payload": {
    "check": "worker_responsive",
    "pid": 58800,
    "last_heartbeat_s_ago": 125.3,
    "suspected_wedged": true
  }
}
```

### 7.2 `drift_detected`

Emitted when `megaplan doctor --repo` finds rubric/binary or skill-out-of-sync drift.

| Field | Value |
|---|---|
| **Emitting subsystem** | `megaplan/observability/doctor.py` — repo-level check path |
| **Consumed by** | `introspect`, `doctor`, `dash` |

```jsonc
{
  "kind": "drift_detected",
  "phase": null,
  "payload": {
    "drift_type": "rubric_binary",
    "rubric_profiles": ["basic","led","thoughtful","super-premium"],
    "binary_profiles": ["solo","directed","partnered","premium","apex"],
    "missing_locally": ["basic","led","thoughtful","super-premium"],
    "warning": "rubric references 4 profiles your binary doesn't expose — check branch or update skill doc"
  }
}
```

---

## Event-Kind Cross-Reference Matrix

| Kind | Group | `introspect` | `trace` | `doctor` | `dash` |
|---|---|---|---|---|---|
| `init` | Lifecycle | ✓ (timeline, phase tracking) | ✓ | ✓ | ✓ |
| `phase_start` | Lifecycle | ✓ (active_phase) | ✓ | ✓ | ✓ (phase timeline) |
| `phase_end` | Lifecycle | ✓ (timeline) | ✓ | ✓ | ✓ |
| `phase_retry` | Lifecycle | ✓ | ✓ | ✓ | ✓ |
| `state_transition` | Lifecycle | ✓ (current state) | ✓ | ✓ | ✓ |
| `lock_acquired` | Lifecycle | ✓ | — | ✓ (stale-lock check) | — |
| `lock_released` | Lifecycle | ✓ | — | ✓ | — |
| `plan_aborted` | Lifecycle | ✓ | ✓ | ✓ | ✓ |
| `plan_finished` | Lifecycle | ✓ | ✓ | ✓ | ✓ |
| `subprocess_spawned` | Subprocess | ✓ (process_tree) | ✓ | ✓ (orphan check) | ✓ |
| `subprocess_exited` | Subprocess | ✓ | ✓ | ✓ | ✓ |
| `subprocess_signaled` | Subprocess | ✓ | ✓ | ✓ | ✓ |
| `llm_call_start` | LLM | ✓ (liveness: in-flight) | ✓ | ✓ (wedged check) | ✓ (active LLM) |
| `llm_token_heartbeat` | LLM | ✓ (liveness) | ✓ (narrative groups) | ✓ | ✓ (token rate) |
| `llm_call_end` | LLM | ✓ (liveness) | ✓ | ✓ | ✓ |
| `llm_call_error` | LLM | ✓ | ✓ | ✓ | ✓ |
| `artifact_written` | Artifacts | ✓ (last_artifact_at) | ✓ | ✓ | ✓ (recent events) |
| `artifact_invalidated` | Artifacts | ✓ | ✓ | — | ✓ |
| `override_applied` | Decisions | ✓ (block_details) | ✓ | ✓ | ✓ |
| `flag_raised` | Decisions | ✓ (outstanding_flags) | ✓ | ✓ | ✓ (flags pane) |
| `flag_resolved` | Decisions | ✓ | ✓ | ✓ | ✓ |
| `note_added` | Decisions | ✓ | ✓ | ✓ | ✓ |
| `cost_recorded` | Cost | ✓ (timeline cost) | ✓ | ✓ (cost trajectory) | ✓ (cost header) |
| `health_check_failed` | Diagnostics | ✓ | ✓ | ✓ | ✓ |
| `drift_detected` | Diagnostics | ✓ (rubric_doc.drift) | — | ✓ (primary) | ✓ |
