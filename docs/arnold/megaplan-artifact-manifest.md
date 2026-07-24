# Megaplan Artifact Manifest

Canonical artifact paths for the three primary Megaplan workflow routes:
**proceed** (gate→finalize→execute→review-pass→done),
**review-needs-rework** (review-finds-issues→revise-loop→re-review), and
**execute failure/resume** (partial-failure→checkpoint→resume).

This manifest is authoritative for artifact-path assertions in the native golden
manifest (`tests/arnold_pipelines/megaplan/fixtures/native_goldens/manifest.json`)
and is enforced by `test_native_golden_manifest.py` obligation checks.

---

## 1. Proceed Artifact Path

The "proceed" path is the happy-path Megaplan flow: prep completes, plan is
generated, critique passes, gate recommends proceed, finalize emits tasks and
baselines, execute runs the task DAG, review passes, and the workflow reaches
done.

| Stage | Artifact(s) | Content type | Schema keys | Warrant source |
|---|---|---|---|---|
| **prep** | `prep_notes_vN.json` (via `write_plan_artifact`) | `application/x-megaplan-plan+json` | `plan_text`, `version`, `questions` | `handlers/prep.py:handle_prep` |
| **plan** | `plan_vN.json` (via `write_plan_artifact`) | `application/x-megaplan-plan+json` | `plan_text`, `version`, `success_criteria`, `assumptions` | `handlers/plan.py:handle_plan` |
| | `receipt_plan.json` (via `write_receipt_artifact`) | `application/x-megaplan-receipt+json` | `step`, `success`, `summary`, `artifacts` | `handlers/plan.py` |
| **critique** | `receipt_critique.json` | `application/x-megaplan-receipt+json` | `step`, `success`, `summary` | `handlers/critique.py:handle_critique` |
| **gate** | `gate_signals_vN.json` | `application/x-megaplan-gate-signal+json` | `signals`, `robustness`, `preflight_results`, `unresolved_flags` | `handlers/gate.py:handle_gate` |
| | `receipt_gate.json` | `application/x-megaplan-receipt+json` | `step`, `success` | `handlers/gate.py` |
| **finalize** | `finalize_plan_vN.json` | `application/x-megaplan-plan+json` | `plan_text`, `version`, `success_criteria` | `handlers/finalize.py:handle_finalize` |
| | `receipt_finalize.json` | `application/x-megaplan-receipt+json` | `step`, `success`, `summary`, `artifacts` | `handlers/finalize.py` |
| | `tasks.json` (task listing) | `application/x-megaplan-execution-evidence+json` | `tasks`, `status`, `artifacts` | `handlers/finalize.py:_write_finalize_artifacts` |
| **execute** | `receipt_execute.json` | `application/x-megaplan-receipt+json` | `step`, `success`, `summary`, `artifacts` | `handlers/execute.py:handle_execute` |
| | Execution evidence per task | `application/x-megaplan-execution-evidence+json` | `tasks`, `status` | `handlers/execute.py` |
| **review** | `review_output.json` | `application/x-megaplan-review-output+json` | `verdict`, `rework_items`, `summary` | `handlers/review.py:handle_review` |
| | `receipt_review.json` | `application/x-megaplan-receipt+json` | `step`, `success` | `handlers/review.py` |

### Proceed route summary

```
prep → plan → critique → gate(recommendation=proceed) → finalize → execute → review(verdict=pass) → done
```

Every stage above except `done` produces at minimum a receipt artifact. Content
types are registered in `arnold_pipelines.megaplan.content_types` via
`build_megaplan_content_type_registry()`.

---

## 2. Review-Needs-Rework Artifact Path

When review returns `verdict=rework`, the workflow loops back through revise →
critique → gate → finalize → execute → review.  Each iteration increments the
artifact version and may produce additional delta artifacts.

| Stage | Additional artifact(s) | Notes |
|---|---|---|
| **review (rework)** | `review_output.json` (verdict=rework, rework_items populated) | Triggers revise loop |
| | `receipt_review.json` | success=false |
| **revise** | `plan_vN.json` (new version) | Incremented version from plan revision |
| | `delta_vN.json` (via delta content type) | `from_version`→`to_version` diff |
| | `receipt_revise.json` | |
| **critique (re-entry)** | `receipt_critique.json` (new version) | |
| **gate (re-entry)** | `gate_signals_vN.json` (new version) | |
| **finalize (re-entry)** | `finalize_plan_vN.json` (new version) | |
| | Updated `tasks.json` | |
| **execute (re-entry)** | New execution evidence | Partial re-execution possible |
| **review (re-entry)** | `review_output.json` (verdict=pass or rework) | Loop bounded by M4_LOOP_MAX_ITERATIONS (4) |

### Rework loop summary

```
review(verdict=rework) → revise → critique → gate(proceed|iterate) → finalize → execute → review
```

The loop is bounded by `M4_LOOP_MAX_ITERATIONS` (4). On cap exhaustion without
pass, the workflow transitions to blocked/escalate.  Artifacts from each
iteration are versioned and retained.

### Cap exhaustion artifacts

When the rework loop exhausts its cap:
- `review_output.json` with `verdict=blocked` or escalated
- Additional `receipt_review.json` with `success=false`
- Escalation to `override` handler may produce override artifacts

---

## 3. Execute Failure/Resume Artifact Path

When execute encounters partial failure (some tasks succeed, some fail), the
workflow writes checkpoint artifacts and can resume from the last completed
stage.

| Stage | Artifact(s) | Purpose |
|---|---|---|
| **execute (partial)** | `receipt_execute.json` (success=false) | Documents which tasks failed |
| | Per-task execution evidence (success/failure) | `status` per task |
| | `checkpoint.json` (path-addressed) | Resume cursor for each successful task path |
| **resume** | `resume_cursor.json` | Restores execution state |
| | `receipt_execute_resume.json` | Resume-specific receipt |
| | Additional per-task evidence (retried tasks) | |

### Execute failure/resume summary

```
execute(partial_failure) → checkpoint → resume_from_path → execute(retry_failed) → review
```

Checkpoint paths are stable and path-addressed (per `path-addressed-checkpoints`
alignment row).  The native runtime trace captures the `checkpoint` event kind
in `events.ndjson` and writes `checkpoint.json` with resume state.

### Native trace artifacts (all paths)

Every deterministic runner produces a five-file native trace directory:

| File | Content | Normalization |
|---|---|---|
| `events.ndjson` | Event stream (pipeline.init, phase.start/end, stage.complete, checkpoint) | Strip `seq`, `ts_utc`, `ts_rel_init_s` |
| `state.json` | Pipeline state (`status`, `stage`) | Canonical JSON |
| `stages.json` | Completed stage list | Canonical JSON |
| `artifacts.json` | Artifact path→hash map | Canonical JSON |
| `checkpoint.json` | Checkpoint state for resume | Canonical JSON |

---

## 4. Obligation Mapping (D1/D5/D6/D8/D10)

The following table maps artifact obligations to the scenario IDs that must
satisfy them in the native golden manifest.

### D1 — Prep/Plan

| Obligation | Value |
|---|---|
| `expected_files` | `plan_vN.json`, `receipt_plan.json`, `prep_notes_vN.json` |
| `schema_keys` | `plan_text`, `version`, `questions`, `success_criteria`, `assumptions`, `step`, `success`, `summary`, `artifacts` |
| `receipt_metrics` | `receipt_plan.success==true`, `receipt_plan.artifacts` non-empty |
| `warrant_source_refs` | `arnold_pipelines/megaplan/handlers/prep.py`, `arnold_pipelines/megaplan/handlers/plan.py`, `arnold_pipelines/megaplan/content_types.py` |
| `renamed_equivalents` | (none — D1 paths stable from M1) |

### D5 — Tiebreaker

| Obligation | Value |
|---|---|
| `expected_files` | `tiebreaker_researcher_output.json`, `tiebreaker_challenger_output.json`, `tiebreaker_decision.json`, `receipt_tiebreaker.json` |
| `schema_keys` | `verdict`, `rework_items`, `summary` (review-like output), `step`, `success` (receipt) |
| `receipt_metrics` | `receipt_tiebreaker.success`, researcher+challenger outputs present |
| `warrant_source_refs` | `arnold_pipelines/megaplan/handlers/tiebreaker_run.py`, `arnold_pipelines/megaplan/handlers/tiebreaker_decide.py`, `arnold_pipelines/megaplan/workflows/components.py` (TIEBREAKER_POLICY) |
| `renamed_equivalents` | `tiebreaker.py` → `tiebreaker_run.py` + `tiebreaker_decide.py` (split during M3 handler extraction) |

### D6 — Finalize

| Obligation | Value |
|---|---|
| `expected_files` | `finalize_plan_vN.json`, `receipt_finalize.json`, `tasks.json` |
| `schema_keys` | `plan_text`, `version`, `success_criteria`, `step`, `success`, `summary`, `artifacts`, `tasks`, `status` |
| `receipt_metrics` | `receipt_finalize.success==true`, `receipt_finalize.artifacts` includes task listing, baseline selection evidence |
| `warrant_source_refs` | `arnold_pipelines/megaplan/handlers/finalize.py`, `arnold_pipelines/megaplan/content_types.py` |
| `renamed_equivalents` | `stages/finalize.py` → `handlers/finalize.py` (M3 migration) |

### D8 — Execute Gates

| Obligation | Value |
|---|---|
| `expected_files` | `gate_signals_vN.json`, `receipt_gate.json`, `human_decision.json`, `receipt_execute.json` |
| `schema_keys` | `signals`, `robustness`, `preflight_results`, `unresolved_flags`, `step`, `success`, `summary`, `artifacts`, `tasks`, `status` |
| `receipt_metrics` | `receipt_gate.success` with approval/deny/resume, `receipt_execute.success` |
| `warrant_source_refs` | `arnold_pipelines/megaplan/handlers/gate.py`, `arnold_pipelines/megaplan/handlers/execute.py`, `arnold_pipelines/megaplan/workflows/components.py` (GATE_POLICY) |
| `renamed_equivalents` | `stages/gate.py` → `handlers/gate.py` (M3 migration), `stages/execute.py` → `handlers/execute.py` (M3 migration) |

### D10 — Review Caps

| Obligation | Value |
|---|---|
| `expected_files` | `review_output.json`, `receipt_review.json`, `rework_items.json`, `cap_exhaustion.json` |
| `schema_keys` | `verdict`, `rework_items`, `summary`, `step`, `success`, `artifacts` |
| `receipt_metrics` | `receipt_review.success` per iteration, cap-exhaustion detected when `verdict=blocked` after M4_LOOP_MAX_ITERATIONS |
| `warrant_source_refs` | `arnold_pipelines/megaplan/handlers/review.py`, `arnold_pipelines/megaplan/workflows/components.py` (REVISE_LOOP_POLICY, M4_LOOP_MAX_ITERATIONS=4) |
| `renamed_equivalents` | `stages/review.py` → `handlers/review.py` (M3 migration), old `review/rework` route label → `review:rework` (M1 vocabulary normalization) |

---

## 5. Cross-Reference: Content-Type Registry

All artifact content types are registered in `arnold_pipelines.megaplan.content_types`:

| Content type ID | Retention | Key schema fields |
|---|---|---|
| `application/x-megaplan-plan+json` | RUN | `plan_text`, `version`, `questions`, `success_criteria`, `assumptions` |
| `application/x-megaplan-receipt+json` | AUDIT | `step`, `success`, `summary`, `artifacts` |
| `application/x-megaplan-gate-signal+json` | RUN | `signals`, `robustness`, `preflight_results`, `unresolved_flags` |
| `application/x-megaplan-review-output+json` | RUN | `verdict`, `rework_items`, `summary` |
| `application/x-megaplan-execution-evidence+json` | AUDIT | `tasks`, `status`, `artifacts` |
| `application/x-megaplan-state-artifact+json` | AUDIT | `name`, `current_state`, `iteration`, `config`, `meta` |
| `application/x-megaplan-capsule+json` | LEGAL_HOLD | `capsule_hash`, `completeness`, `replay_ready`, `record_count` |
| `application/x-megaplan-delta+json` | RUN | `from_version`, `to_version`, `diff`, `flags_addressed` |

---

## 6. Renamed Equivalent Summary

| Pre-M1 name/path | Post-M1 name/path | Migration milestone |
|---|---|---|
| `stages/prep.py` | `handlers/prep.py` | M3 handler extraction |
| `stages/plan.py` | `handlers/plan.py` | M3 handler extraction |
| `stages/critique.py` | `handlers/critique.py` | M3 handler extraction |
| `stages/gate.py` | `handlers/gate.py` | M3 handler extraction |
| `stages/revise.py` | `handlers/revise.py` | M3 handler extraction |
| `stages/finalize.py` | `handlers/finalize.py` | M3 handler extraction |
| `stages/execute.py` | `handlers/execute.py` | M3 handler extraction |
| `stages/review.py` | `handlers/review.py` | M3 handler extraction |
| `stages/tiebreaker.py` | `handlers/tiebreaker_run.py` + `handlers/tiebreaker_decide.py` | M3 handler split |
| `stages/override.py` | `handlers/override.py` | M3 handler extraction |
| `review/rework` (route label) | `review:rework` | M1 vocabulary normalization |
| `gate/proceed` (route label) | `gate:proceed` | M1 vocabulary normalization |
