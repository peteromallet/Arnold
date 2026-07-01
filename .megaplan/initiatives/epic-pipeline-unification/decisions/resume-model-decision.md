# Resume-model decision — single authoritative encoding

**M2.5 artifact.**  Decision is defaulted (not an open question — `must_ask_peter=false`).

---

## (a) Inventory of the four resume encodings (line:column verified 2026-05-30)

### 1. `current_state` + `resume_cursor` — the canonical failure-record pair

Written uniformly at **every** `_record_lifecycle_failure` call site in
`megaplan/auto.py`.  The function signature (L874:L886) accepts `current_state:
str|None` and `resume_cursor: dict[str, Any]|None`.  All 18 `_record_failure`
call sites pass both fields:

| Kind                       | Line  | `current_state`     | `resume_cursor` shape                        |
|----------------------------|-------|---------------------|----------------------------------------------|
| `status_lookup_failed`     | 1477  | `None`              | `{phase, retry_strategy:"rerun_status"}`     |
| `cost_cap_exceeded`        | 1506  | `None`              | `{phase, retry_strategy:"increase_cap_or_resume"}` |
| `iteration_cap`            | 1763  | `None`              | `{phase, retry_strategy:"restart_or_continue"}` |
| `stall_generic`            | 1785  | `None`              | `{phase, retry_strategy:"manual_review"}`    |
| `phase_timeout`            | 1856  | (from state.json)   | `{phase, batch_index:null, retry_strategy:"fresh_session"}` |
| `external_error`           | 1876  | `STATE_BLOCKED`     | `{phase, retry_strategy:"wait_and_retry"}`   |
| `gate_escalated`           | 1919  | (from state.json)   | `{phase, retry_strategy:"manual_review"}`    |
| `no_next_step`             | 1937  | (from state.json)   | `{phase, retry_strategy:"manual_review"}`    |
| `context_retry_exhausted`  | 2045  | `None`              | `{phase, retry_strategy:"fresh_session"}`    |
| `phase_timeout` (per-phase)| 2153  | (from state.json)   | `{phase, batch_index:null, retry_strategy:"fresh_session"}` |
| `external_error` (per-ph)  | 2188  | `STATE_BLOCKED`     | `{phase, retry_strategy:"check_provider_and_retry"}` |
| `phase_failed`             | 2248  | `STATE_BLOCKED`     | `{phase, retry_strategy:"rerun_status"}`     |
| `phase_failed` (fallthru)  | 2263  | `STATE_BLOCKED`     | `{phase, retry_strategy:"rerun_status"}`     |
| `phase_callback_failed`    | 2289  | `STATE_FAILED`      | `{phase, retry_strategy:"manual_review"}`    |
| `execution_blocked` (prereq)| 2374  | `STATE_BLOCKED`     | `{phase, batch_index:null, retry_strategy:"fresh_session"}` |
| `execution_blocked` (quality)|2428  | `STATE_BLOCKED`     | `{phase, batch_index:null, retry_strategy:"fresh_session"}` |
| `execution_blocked` (cap)  | 2624  | `STATE_BLOCKED`     | `{phase, retry_strategy:"fresh_session"}`    |

**Shape:** `resume_cursor` is always `{phase: str, retry_strategy: str,
batch_index: int|null}`.  `current_state` is `None` for driver-lifecycle exits
(the real `current_state` is read from `state.json` in the defaulting block at
L889:L914) and explicit (e.g. `STATE_BLOCKED`, `STATE_FAILED`) for
phase-failure exits.

**Coverage:** Every `_outcome(status=…)` return site that records a failure also
writes this pair.  Zero migration cost — the format is already uniform.

### 2. `STATE_AWAITING_HUMAN` — a terminal `DriverOutcome.status` value

- **Definition:** `types.py:28-29` — `STATE_AWAITING_HUMAN_VERIFY` is the
  canonical literal; `STATE_AWAITING_HUMAN` is a backwards-compat alias.
- **Terminal gate:** `auto.py:1544` — when state is in
  `AUTOMATION_TERMINAL_STATES` (`types.py:75-80`) and the blocked-guard passes,
  `STATE_AWAITING_HUMAN` returns a terminal `_outcome("awaiting_human", …)`.
  Falls through to exit code **1** (the implicit default after `run_auto`
  L2879, since `awaiting_human` is not in the explicit mapping at L2861-2878).
- **Handlers that reference it:** `override.py:12,972,975` (resume-clarify
  gate); `plan.py:9,42,128,159`; `verifiability.py:8,215`; `tiebreaker.py:10,130`;
  `execute.py:16,248`; `review.py:22,262,268`; `workflow.py:26`;
  `workflow_data.py:22,23,47,78`.
- **Not a parallel resume channel.** `STATE_AWAITING_HUMAN` is a
  `DriverOutcome.status` value (the automation driver's terminal output), not a
  separate resume encoding.  The driver exits; resume is handled by the
  pipeline executor + CLI reading `awaiting_user.json` and `state.json`.

### 3. `_pipeline_paused_stage` — a pipeline-internal pause marker

- **Written:** `_pipeline/steps/human_gate.py:97` — as a `state_patch` key
  alongside `_pipeline_paused: True` in the `StepResult` returned when the
  human-gate stage halts.
- **Read:** `_pipeline/run_cli.py:267` — read from `state.json` on resume to
  identify which stage paused.
- **Cleared:** `cli/__init__.py:951` — popped from state before resuming the
  pipeline after a human-gate response.
- **NOT in `executor.py` or `resume.py`** (verified: grep returns zero matches
  in both files). The `resume.py` module handles resume via
  `check_awaiting_user` (`resume.py:104`) + `state.json::resume_cursor`, not
  via `_pipeline_paused_stage`.

### 4. `awaiting_user.json` — the human-gate pause file

- **Written:** `_pipeline/steps/human_gate.py:90-91` — written to
  `<plan_dir>/awaiting_user.json` when the human-gate stage pauses.
- **Read:** `_pipeline/resume.py:111` (`check_awaiting_user`, L104);
  `_pipeline/run_cli.py:271` (resume cursor reload); `cli/__init__.py:860,890`
  (resume-clarify flow).
- **Cleaned:** `cli/__init__.py:963-964` — unlinked after successful resume.
- **No committed instances on disk** (verified: `search_files` returns zero
  files matching `awaiting_user.json` in the repo).

---

> **Footnote — citation drift vs the M5c brief.** The M5c brief
> (`m5c-control-plane.md:73`) cites `_pipeline/executor.py:264,376` as the
> `halt_reason=="awaiting_user"` site.  **Both line numbers are stale.**
> Actual site is `executor.py:349`.  The `resume.py:104` cite is verified
> correct.  This decision doc cites the re-read current line numbers.

---

## (b) Decision: `current_state` + `resume_cursor` is the single resume fact

**The pair `{current_state, resume_cursor{phase, retry_strategy,
batch_index}}` is THE authoritative resume encoding.**  It is already written
uniformly at every `_record_lifecycle_failure` call site (18 sites, verified
above).  Migration cost is zero — the format is consistent and every exit
branch that records a failure writes this pair.

No new encoding is introduced.  No existing encoding is split.

---

## (c) `STATE_AWAITING_HUMAN` stays as a terminal `DriverOutcome.status` value

`STATE_AWAITING_HUMAN` (and its alias `STATE_AWAITING_HUMAN_VERIFY`) is a
**terminal DriverOutcome.status** — the automation driver's output when it
reaches a human-gate halt.  It is NOT a parallel resume channel.  Resume from
an awaiting-human state is driven by:
1. `awaiting_user.json` (the pause file, read by the pipeline resume path)
2. `state.json` (carries `current_state` + workflow cursor)

The status value itself is diagnostic — it tells an inspector *why* the driver
stopped — but the *machinery* that resumes the run reads `awaiting_user.json`
and the `resume_cursor` in `state.json`, not the `DriverOutcome.status`.

---

## (d) `_pipeline_paused_stage` and `awaiting_user.json` become projections under M3

Under M3's R1 authority flip (the WAL becomes authoritative, `state.json`
becomes a rebuilt cache):

- **`_pipeline_paused_stage`** is a transient pipeline-internal key written to
  `state.json` by the human-gate stage and cleared on resume.  Under M3 it
  becomes a **projection** — recomputed from the WAL fold as "the last stage
  that emitted a halt-with-awaiting-user event," not a separately persisted
  key.  The realized-graph `predecessors(stage)` query (M3 hinge gate,
  `m3-hinge.md` L47-49) subsumes this directional information.

- **`awaiting_user.json`** is the clarify/resume cursor.  Under M3 it
  becomes a **projection** of `current_state` + `resume_cursor` — the file
  is rebuilt from the WAL fold when the last event is a `human_gate` pause
  event carrying the clarification payload.  M5c F6 (`m5c-control-plane.md`
  L73-86) consumes this projection as the clarify cursor.

<!-- M3 cross-reference: see m3-hinge.md L122-123 (R1 flips HERE, gated on
     the M2.5 oracle).  The blocked_retry_quality_to_cap corpus trace
     (oracle_role: "replay+resume" in MANIFEST.json) is the replay oracle
     authorizing the R1 flip. -->

<!-- M5c cross-reference: see m5c-control-plane.md F6 section (L55-86).  The
     clarify cursor (`awaiting_user.json`) is rebuilt from the WAL fold
     carrying `current_state` + `resume_cursor`. -->

---

## (e) Known bugs RECORDED (not fixed here)

1. **Chain-blocked-retry: `DEFAULT_MAX_BLOCKED_RETRIES=1`.**  The
   `blocked_retry_quality_to_cap` golden captures the AS-IS behavior where a
   single quality-gate block exhausts the retry budget.  This is a known
   regression (MEMORY `chain_blocked_retry`); the M5c recovery-path binding
   must honor a retry budget >1 (`m5c-control-plane.md` L168).

2. **Idle-stall history.**  Idle timeouts via `DEFAULT_PHASE_IDLE_TIMEOUT_SECONDS`
   (1800s) are recorded in the `idle_timeout` golden.  Non-deterministic
   `idle_seconds` values are normalized via `_IDLE_SECONDS_RE` in the test
   harness.

---

## (f) M3 implementation contract

1. **Rebuild `next_step` via the realized-graph projection.**  The
   `_BRANCHES` table + MANIFEST.json provide the dispatch table; M3's
   `build_topology(run_config)` produces the graph that `workflow_next`
   projects from.

2. **The `blocked_retry_quality_to_cap` trace is the replay oracle** authorizing
   the R1 flip (`m3-hinge.md` L122-123, L47-49).  Its events capture the full
   retry loop → cap → `worker_blocked` transition.  The M3 hinge gate replays
   this trace across the version boundary (substrate-swap oracle,
   `m3-hinge.md` L182-186).

3. **Cross-reference stubs:**
   - **M3 hinge:** `m3-hinge.md` L122-123 — the "R1 flips HERE" locked
     decision already cites the M2.5 oracle.  A placeholder comment in this
     doc (section (d)) anchors the cross-reference.
   - **M5c:** `m5c-control-plane.md` F6 section (L55-86) references the
     clarify cursor.  A placeholder comment in this doc (section (d)) anchors
     the cross-reference.

---

**Authoritative after M2.5.**  The characterization corpus
(`tests/characterization/auto_drive_corpus/` + `MANIFEST.json`) is the
single source of truth for all 28 exit branches.  The `oracle_role` tags
(`terminal` / `replay` / `replay+resume`) in MANIFEST.json identify which
traces serve as the M3 replay oracle.
