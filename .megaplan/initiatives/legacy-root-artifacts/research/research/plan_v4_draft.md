# Implementation Plan: Megaplan Live Watchdog Supervisor (v4)

## Overview

Build an MVP that discovers likely-live Megaplan/Arnold runs across five directory roots, classifies their health into seven categories, and uses a new Arnold pipeline package (`live-supervisor`) to handle problem incidents with bounded diagnosis→repair→relaunch→recheck loops capped at three attempts. The system must function even when the installed `megaplan` CLI is shadowed/broken, using direct filesystem/process access.

**Executor selection (resolves FLAG-005):** The pipeline is executed via the **Arnold neutral executor** (`arnold.pipeline.executor.run_pipeline`), the same path used by the existing `jokes` pipeline test. This executor builds `StepContext` with `artifact_root` from `RuntimeEnvelope.artifact_root`. Steps write artifacts to `Path(ctx.artifact_root) / <stage_name> / <artifact>.json` and return those paths in `StepResult.outputs`. The daemon creates a `RuntimeEnvelope(artifact_root=str(tmpdir))` and invokes `run_pipeline(pipeline, initial_state={"snapshot": snapshot_dict}, envelope=envelope)`. This avoids the Megaplan executor's `StepContext` (which has `plan_dir` but no `artifact_root`) and keeps the pipeline compatible with both test and production paths without a bridge helper.

**v4 changes (FLAG-007, FLAG-008):**
- **FLAG-007:** `SignalBundle` now carries an explicit `in_flight_llm: bool` field (extracted from events.ndjson by `compute_signal_bundle`). `classify_incident` detects `false_stall` when liveness is `"progressing"` but the only "progress" is a hanging in-flight LLM call with the last real event >300s ago. This makes the `false_stall` category reachable despite `_compute_liveness` returning `"progressing"` for in-flight LLM plans.
- **FLAG-008:** Step 17 (CLI) now explicitly describes the correct dataflow: daemon builds snapshot → runs pipeline → reads classification/diagnosis artifacts from `artifact_root` → selects problem incidents from pipeline output (not from snapshot). No "classifications already in the snapshot" language remains.

**Prior design features carried forward:**

- **Pipeline output contract (FLAG-001):** Every step writes structured JSON results to artifact files under `ctx.artifact_root` and returns those file paths in `StepResult.outputs`. Inter-stage data flows via `state_patch`.
- **Snapshot → Incident contract (FLAG-002):** A daemon step (`signals.py`) computes introspect liveness, block_details, in_flight_llm, and normalized doctor findings from plan state+events and attaches them to each plan entry. `build_snapshot` then constructs `Incident` objects with complete signal bundles. The pipeline receives the full Snapshot (with incidents) as `ctx.state["snapshot"]`.
- **Pipeline invocation (FLAG-003):** The daemon invokes the pipeline in-process via `build_pipeline()` → `run_pipeline()` using a temp directory as artifact_root. The script entry is `python scripts/megaplan_live_watchdog.py --once`. No `arnold pipelines run` subcommand is required.
- **Step sizing (FLAG-004):** Process scanning+correlation split into process parsing+liveness, tmux/orphan enrichment, and correlation. Retry loop split into retry state machine and repair-runner with broken-CLI fallback.
- **Degraded signals:** When liveness/block_details/doctor computation fails for a plan, the signal bundle carries `degraded: true` + `failure_reason` and the classifier maps to `unknown` with `no_repair_available` downstream.

**Repository shape that constrains the design (unchanged):**

- The idiomatic home for the new Arnold pipeline is a **package directory** under `arnold/pipelines/megaplan/pipelines/`, auto-discovered by `_scan_dir_for_pipeline_modules` (`arnold/pipelines/megaplan/_pipeline/registry.py:882`) which scans `arnold.pipelines.megaplan.pipelines.*`.
- **Naming:** the directory MUST be named with an **underscore** (`live_supervisor`) so it is importable as `arnold.pipelines.megaplan.pipelines.live_supervisor`, while being CLI-discovered as `live-supervisor` (registry `_cli_name` converts underscores to hyphens).
- The existing `arnold/pipelines/megaplan/supervisor/` is a **code module** (chain/bakeoff orchestration), NOT a pipeline package — the new watchdog must not collide with it. The daemon **engine** lives as a new code module `arnold/pipelines/megaplan/watchdog/`, mirroring the `supervisor/` code-module pattern.
- The pipeline contract requires 8 module-level manifest fields (`arnold/pipeline/discovery/manifest.py:31` `REQUIRED_FIELDS`: name, description, default_profile, supported_modes, driver, entrypoint, arnold_api_version, capabilities) + a top-level `build_pipeline` symbol + a `SKILL.md` sibling. `arnold_api_version` must be `1.x` (`< CURRENT_MAJOR=2`, `manifest.py:27`).
- Reusable primitives: `_pid_is_live` (`_core/state.py:307`), `plan_lock_is_held` (`_core/state.py`), `TmuxSession` (`runtime/process.py:283`), `_compute_liveness` → `progressing|quiet|stalled|timeout-imminent` (`observability/introspect.py:232`), `_compute_block_details` → `{is_blocked,current_state,recoverable_via}` (`introspect.py:350`), `format_chain_status` (`chain/__init__.py:1990`), `build_chain_parser` with `--one/--no-git-refresh/--no-push` (`chain/__init__.py:2105`), `read_events` (`observability/events.py:563`), and `TERMINAL_STATES`/`AUTOMATION_TERMINAL_STATES` (`planning/state.py:70,79`).

---

## Phase 1: Pipeline foundation — contract, models, pure rules

### Step 1: Create the `live_supervisor` pipeline package skeleton + contract
**Scope:** Small — Complexity: 2
1. **Create** `arnold/pipelines/megaplan/pipelines/live_supervisor/__init__.py` with the 8 manifest fields as literal module-level constants: `name="live-supervisor"`, `description`, `default_profile=None`, `supported_modes=()`, `driver="in_process"`, `entrypoint="build_pipeline"`, `arnold_api_version="1.0"`, `capabilities=("plan_supervision","incident_classification","repair_dispatch")`.
2. **Define** a top-level `def build_pipeline()` that initially delegates to `build_skeleton_pipeline(name, description)` from `arnold/pipelines/_authoring.py:354` (a valid single-halt-stage pipeline). This placeholder is replaced in Step 8.
3. **Create** `arnold/pipelines/megaplan/pipelines/live_supervisor/SKILL.md` (one-paragraph input/output contract — required by `read_manifest`, `manifest.py:340`).
4. **Verify** with a throwaway check: `from arnold.pipeline.discovery.manifest import read_manifest; read_manifest(Path(.../__init__.py))` returns a `Manifest` (not `ManifestError`), and `from arnold.pipelines._authoring import validate_package_module; validate_package_module(import_module(...)) == []`. This proves the package is discoverable before writing any logic.

### Step 2: Typed models (`model.py`)
**Scope:** Medium — Complexity: 3
1. **Create** `live_supervisor/model.py` with frozen dataclasses/enums: `HealthCategory` (`all_good|false_stall|harness_issue|plan_issue|environment_issue|dead_or_disappeared|unknown`), `Triage` (`live|recent|maybe_live|stale`), `CheckFinding` (with `scope: Literal["plan","repo"]`), `PlanEntry`, `SignalBundle` (liveness enum, liveness_reason, block_details dict, doctor_findings list, **`in_flight_llm: bool = False`** (NEW v4 - resolves FLAG-007), **`last_event_age_seconds: Optional[float] = None`** (NEW v4), degraded bool, failure_reason str|None), `Incident` (has PlanEntry + SignalBundle), `Diagnosis`, `RepairRecommendation`, `RepairAction`, `AllowlistVerdict`, `Snapshot` (the JSON contract: `scan_ts_utc`, `plans[]`, `incidents[]`). Each model carries `to_dict()`/`from_dict()` so the daemon↔pipeline boundary is pure JSON.
2. **Add** `tests/pipelines/test_live_supervisor_model.py` covering round-trip `to_dict`/`from_dict`, default values, degraded SignalBundle serialization, and `in_flight_llm`/`last_event_age_seconds` serialization.

### Step 3: Doctor-signal normalizer + 7-category classifier (`rules.py`, part A)
**Scope:** Medium — Complexity: 4
1. **Create** `live_supervisor/rules.py`. Implement `normalize_doctor_findings(plan_findings, repo_findings)` that flattens BOTH single `tuple[str,str,str]` returns (e.g. `_check_stale_lock`, `doctor.py:224`) AND `list[tuple[str,str,str]]` returns (`_check_skill_sync`, `doctor.py:543`) into a uniform `list[CheckFinding]`, tagging `scope="plan"` for plan-level checks and `scope="repo"` for repo-level/global checks (skill_sync, editable_install, multiple_checkouts, rubric_drift).
2. **Implement** `classify_incident(incident) -> HealthCategory` as a pure function over the incident's bundled `SignalBundle` (liveness, block_details, normalized doctor findings, `TERMINAL_STATES` membership, **`in_flight_llm`** (NEW v4), **`last_event_age_seconds`** (NEW v4)). Mapping:
   - process live + `progressing` + recent real events (<60s) → `all_good`
   - **`progressing` + `in_flight_llm == True` + `last_event_age_seconds > 300`** → **`false_stall`** (NEW v4: the plan is "progressing" only because of an in-flight LLM call; no real event in >300s means it's effectively stalled)
   - `stalled` + `in_flight_llm == True` → `false_stall` (defensive fallback if `_compute_liveness` semantics change)
   - `stalled` + in-progress work (not terminal, not in-flight LLM) → `plan_issue`
   - repo-scope findings present → `environment_issue`
   - stale-lock/orphan-subprocess/multiple-checkouts findings → `harness_issue`
   - phase-timeout/outstanding-flags/block_details.recoverable_via → `plan_issue`
   - no process + no recent events + non-terminal → `dead_or_disappeared`
   - degraded signal bundle → `unknown`
   - otherwise `unknown`
   Edge cases: live process + terminal state → `all_good` (terminal, not a problem); no process + recent events → still `recent` triage (not `dead`).
3. **Add** `tests/pipelines/test_live_supervisor_rules.py` `class TestClassifier` covering every category including `false_stall` with `in_flight_llm=True` and `last_event_age_seconds>300`, degraded signals, and all other edge cases (the `test_classifier_distinguishes_all_health_categories` fail_to_pass test).

### Step 4: Action allowlist enforcer (`rules.py`, part B)
**Scope:** Medium — Complexity: 3
1. **Implement** `enforce_allowlist(action, context_bundle) -> AllowlistVerdict` as a pure function. Unconditionally allow: `introspect`, `trace`, `doctor`, `chain status`. Conditionally allow: `auto` (requires `plan_name` + `state` + `block_details.recoverable_via`), `resume` (requires `plan_name` + `is_resumable`), `chain start --one --no-git-refresh --no-push` (requires `chain_spec_path` + `has_pending_milestones`). Reject: any `git reset|checkout|push|merge`, any worktree/plan-directory deletion, and anything not in the allowlist.
2. **Add** `class TestAllowlist` to `tests/pipelines/test_live_supervisor_rules.py` covering the six destructive rejections, unconditional allows, and conditional-allow context gating (the two `test_allowlist_*` fail_to_pass tests).

---

## Phase 2: Repair agent + pipeline assembly

### Step 5: Repair-agent protocol + fakes (`repair_agent.py`)
**Scope:** Small — Complexity: 2
1. **Create** `live_supervisor/repair_agent.py` defining `RepairAgent` (a `Protocol` with `diagnose_and_recommend(incident: Incident, diagnostic_bundle: Mapping) -> RepairRecommendation`). Provide `FakeRepairAgent(recommendation_map)` returning deterministic recommendations by `plan_id`, and `HermesRepairAgent` that is constructed with an optional model-launcher handle — when the handle/credentials are absent it raises `RepairUnavailable`, which the caller translates to `no_repair_available`. The agent never executes commands; it only recommends.
2. **Add** `tests/pipelines/test_live_supervisor_repair_agent.py` asserting `FakeRepairAgent` determinism and that a `None`-credentials `HermesRepairAgent` signals unavailability.

### Step 6: Classify + Diagnose steps (`steps.py`, part A)
**Scope:** Medium — Complexity: 3
1. **Create** `live_supervisor/steps.py`. Imports `StepContext` and `StepResult` from `arnold.pipeline` (Arnold neutral types — `StepContext` has `artifact_root: str`). `ClassifyStep.run(ctx)` reads the `Snapshot` dict from `ctx.state["snapshot"]`, iterates `snapshot["incidents"]`, runs `classify_incident` per incident using the incident's pre-bundled `SignalBundle` (which now includes `in_flight_llm` and `last_event_age_seconds` — NEW v4), writes the classification JSON artifact to `Path(ctx.artifact_root) / "classify" / "classifications.json"`, and returns `StepResult(outputs={"classifications": artifact_path}, state_patch={"classifications": [...], ...}, next="diagnose")`.
2. **`DiagnoseStep.run(ctx)`** reads classifications from `ctx.state`, enriches each problem incident using its pre-bundled `SignalBundle` (already in the incident — no live subprocesses), normalizes doctor findings via `normalize_doctor_findings`, writes a diagnosis JSON artifact to `Path(ctx.artifact_root) / "diagnose" / "diagnoses.json"`, and returns `StepResult(outputs={"diagnoses": path}, state_patch={"diagnoses": [...]}, next="repair_decision")`.
3. **Add** `tests/pipelines/test_live_supervisor_steps.py` `class TestClassifyStep`, `class TestDiagnoseStep` using `tmp_path` fixtures: construct Arnold `StepContext(artifact_root=str(tmp_path), state={"snapshot": snapshot_dict}, ...)`, run the step, assert artifact file existence and contents — no agents or subprocesses launched.

### Step 7: RepairDecision + RecheckEmit steps (`steps.py`, part B)
**Scope:** Medium — Complexity: 3
1. **Implement** `RepairDecisionStep.run(ctx)`: accepts an injectable `RepairAgent` (default `FakeRepairAgent(None)`); calls `agent.diagnose_and_recommend(...)`, then `enforce_allowlist(recommendation, context)`; writes a `repair_decisions.json` artifact to `Path(ctx.artifact_root) / "repair_decision" / "repair_decisions.json"`; emits a `RepairAction` (allowed), an `AllowlistVerdict` (rejected), or a `no_repair_available` verdict when the agent signals unavailability. Returns `next="recheck"`.
2. **Implement** `RecheckEmitStep.run(ctx)`: writes `recheck_emit.json` artifact to `Path(ctx.artifact_root) / "recheck_emit" / "recheck_emit.json"` with `recheck_after` (now+300s ISO), `resumable: True`, and the per-incident action report. Returns `StepResult(outputs={"recheck_emit": path}, next="halt")`. **It never sleeps** — the daemon owns the wait.
3. **Add** `class TestRepairDecisionStep`, `class TestRecheckEmitStep` to the same test file covering degraded mode (`test_degraded_mode_report_only_no_credentials`) and the no-sleep timestamp emission (`test_five_minute_wait_emitted_not_blocked`).

### Step 8: Assemble `build_pipeline` and wire the contract (`pipelines.py`)
**Scope:** Medium — Complexity: 3
1. **Create** `live_supervisor/pipelines.py` with `build_pipeline()` using `PipelineBuilder` from `arnold/pipeline/builder.py` adding four linear `Stage`s: `classify → diagnose → repair_decision → recheck_emit` (edges via `Edge` from `arnold/pipeline/types.py`), entry `classify`, terminal edge `halt`. Use plain `Stage` (not `ParallelStage`) for the MVP. Each stage's `step` attribute holds the step instance from `steps.py`.
2. **Update** `__init__.py` `build_pipeline` to delegate to `pipelines.build_pipeline` (replacing the Step-1 skeleton). Keep all 8 manifest fields as literal constants (the AST reader needs literals, `manifest.py:99`).
3. **Pipeline invocation contract (Arnold executor):** The daemon creates a temp directory `tmpdir`, constructs a `RuntimeEnvelope(artifact_root=str(tmpdir))` (from `arnold.runtime.envelope`), and invokes `arnold.pipeline.executor.run_pipeline(pipeline, initial_state={"snapshot": snapshot_dict}, envelope=envelope)`. After execution the daemon reads the artifact files directly from `tmpdir / classify / classifications.json`, `tmpdir / diagnose / diagnoses.json`, `tmpdir / repair_decision / repair_decisions.json`, `tmpdir / recheck_emit / recheck_emit.json`. This is the identical pattern to `tests/pipelines/test_jokes_pipeline.py:69-77`. No `arnold pipelines run` subcommand is required.
4. **Add** `tests/pipelines/test_live_supervisor_pipeline.py` — build the pipeline, create `RuntimeEnvelope(artifact_root=str(tmp_path))`, run via `run_pipeline(pipeline, initial_state={"snapshot": snapshot_dict}, envelope=envelope)`, read the output artifact files, assert a structured per-incident action report with classification, recommended action, allowlist-verdict, and retry count (`test_pipeline_accepts_snapshot_and_produces_action_report`). Include a snapshot fixture with an in-flight LLM incident to verify `false_stall` classification flows through the pipeline. Re-run `validate_package_module` to confirm zero errors.

---

## Phase 3: Watchdog discovery engine (daemon-side, outside the pipeline)

### Step 9: Multi-root plan scanner (`watchdog/discovery.py`)
**Scope:** Small — Complexity: 3
1. **Create** `arnold/pipelines/megaplan/watchdog/__init__.py` (re-export surface) and `watchdog/discovery.py`. Define the explicit module constant **`DEFAULT_SCAN_ROOTS`** = the five required roots: `~/Documents`, `~/Documents/.megaplan-worktrees`, `~/.megaplan-worktrees`, `/tmp`, `/private/tmp` (expand `~`, and on macOS dedupe `/private/tmp`↔`/tmp` by resolved path).
2. **Implement** `discover_plans(roots=DEFAULT_SCAN_ROOTS)` using direct `Path.iterdir`/glob for `.megaplan/plans/*/state.json` under each root, reading `state.json` via `json.load` (no `megaplan` CLI). Missing roots are silently skipped. Deduplicate plans found under overlapping roots by canonical resolved `plan_dir`.
3. **Add** flat `tests/test_watchdog_discovery.py` `class TestScanner` building deterministic fixtures under `tmp_path` that simulate each root with sample `state.json`, asserting discovery + dedup (`test_scanner_discovers_plans_across_all_roots`).

### Step 10: Process-signature scanner + liveness (`watchdog/processes.py`)
**Scope:** Small — Complexity: 3
1. **Implement** `scan_processes(ps_lines=None)` in `watchdog/processes.py` that parses ps output (caller passes lines; default reads real `ps`) for Megaplan/Arnold/Shannon/Codex/Claude signatures, returning structured records with pid + cmdline + category. Use `_pid_is_live` (`_core/state.py:307`) for liveness. Avoid false positives via anchored signature matching.
2. **Add** `tests/test_watchdog_processes.py` with mocked ps lines for `test_scanner_parses_process_signatures` and `test_scanner_checks_pid_liveness`.

### Step 11: Tmux session + orphan enrichment (`watchdog/tmux_scan.py`)
**Scope:** Small — Complexity: 2
1. **Implement** `enrich_with_tmux(processes, plan_dirs)` in `watchdog/tmux_scan.py` that uses `TmuxSession(...).exists()` / `detect_orphans` (`runtime/process.py:283,348`) to discover tmux sessions and orphans associated with each plan directory or process. Returns an enriched process list.
2. **Add** `tests/test_watchdog_tmux.py` with mocked `TmuxSession` for `test_enrich_discovers_tmux_sessions`.

### Step 12: Process-to-plan correlation (`watchdog/correlate.py`)
**Scope:** Medium — Complexity: 3
1. **Implement** `correlate_processes_to_plans(processes, plans)` in `watchdog/correlate.py` preferring, in order: **exact plan-name** match in cmdline, then **exact plan-dir** match, then **chain-state `current_plan`** field (via `format_chain_status`-style reads of `chain_state.json`). Explicitly reject broad repo-path-only matches (the false-positive guard).
2. **Add** `tests/test_watchdog_correlate.py` with overlapping-name fixtures for `test_correlates_process_to_plan_by_exact_name` and `test_rejects_broad_repo_path_matches`.

### Step 13: Signal-bundle computation (`watchdog/signals.py`)
**Scope:** Medium — Complexity: 4
1. **Implement** `compute_signal_bundle(plan_entry) -> SignalBundle` in `watchdog/signals.py` that, for each plan, reads state.json + events.ndjson and computes:
   - **Liveness** via `_compute_liveness(events, plan_dir, state, now_ts)` (`introspect.py:232`): returns `(enum, reason)`.
   - **Block details** via `_compute_block_details(plan_dir, state)` (`introspect.py:350`): returns `{is_blocked, current_state, recoverable_via}`.
   - **`in_flight_llm`** (NEW v4 — resolves FLAG-007): scans events.ndjson for unmatched `llm_call_start` entries (no corresponding `llm_call_end` by `request_id`) within the last 2 hours. Replicates the internal logic from `_compute_liveness` (`introspect.py:268-288`) so the classifier can distinguish real progress from a hanging LLM mask. Stores as `bool` in SignalBundle.
   - **`last_event_age_seconds`** (NEW v4): computed from the most recent event's `ts_utc` vs `now_ts`. Stored as `Optional[float]` in SignalBundle (None when no events exist).
   - **Doctor findings** by running `doctor` checks in-process (or reading pre-collected findings): normalizes both single-tuple and list[tuple] returns via `normalize_doctor_findings`.
2. **Graceful degradation:** If any computation raises (missing state, corrupt events, import failure), return a `SignalBundle` with `degraded=True` and `failure_reason=<message>`. The classifier maps degraded bundles to `unknown` health category. `in_flight_llm` defaults to `False` and `last_event_age_seconds` to `None` when events are unreadable.
3. **Add** `tests/test_watchdog_signals.py` `class TestSignalComputation` exercising live/stalled/blocked/degraded paths AND `in_flight_llm` extraction (with fixtures containing `llm_call_start`/`llm_call_end` event pairs) using `tmp_path` fixtures with sample `state.json` and `events.ndjson`.

### Step 14: Snapshot builder + Incident construction + NDJSON registry (`watchdog/snapshot.py` + `watchdog/registry.py`)
**Scope:** Medium — Complexity: 3
1. **Implement** `build_incidents(plans, signal_bundles) -> list[Incident]` in `watchdog/snapshot.py`: for each plan, attach its computed `SignalBundle` (now including `in_flight_llm` and `last_event_age_seconds`), assign `Triage` (`live|recent|maybe_live|stale` based on process presence + event recency), and construct an `Incident` dataclass.
2. **Implement** `build_snapshot(roots, registry_path)` that aggregates `discover_plans` → `scan_processes` → `enrich_with_tmux` → `correlate_processes_to_plans` → `compute_signal_bundle` (per plan) → `build_incidents` into a `Snapshot` dict (`scan_ts_utc`, `plans[]`, `incidents[]`). The Snapshot carries complete signal bundles on each incident — the daemon passes this entire Snapshot as `initial_state` to the pipeline.
3. **Implement** `WatchdogRegistry(ndjson_path)` (NDJSON, one JSON object per line per plan) with `load()`, `update_seen(plans, now)` (set `first_seen`/`last_seen`/`last_state`, bump `incident_count`), `mark_disappeared(seen_before, current)`, and atomic `save()` (write-temp-then-replace). Fields: `plan_id, first_seen, last_seen, last_state, incident_count, retry_count`.
4. **Add** `tests/test_watchdog_registry.py` for `test_registry_remembers_and_updates_seen_plans` (re-encounter updates `last_seen`, disappearance marked, retry/incident history preserved across invocations) using `tmp_path`.

---

## Phase 4: Retry loop, CLI orchestration, documentation

### Step 15: Retry-loop state machine (`watchdog/retry.py`)
**Scope:** Medium — Complexity: 3
1. **Implement** `RetryLoop(max_attempts=3)` in `watchdog/retry.py` as a state machine: `attempt() → (result, done)`. Tracks attempt count; after the third failure returns `(unresolved, True)` with `retry_count=3`. Exit paths: success before cap (returns `(resolved, True)`), terminal-state mid-loop (returns `(terminal, True)`), three failures (returns `(unresolved, True)`). Refuses fourth attempt — raises `RetryCapExceeded`.
2. **Add** `tests/test_watchdog_retry_loop.py` `class TestRetryStateMachine` covering exactly-three-then-refuse, success-before-cap, and terminal-mid-loop (`test_retry_loop_caps_at_three_attempts`), using a `FakePipelineRunner` that returns canned results.

### Step 16: Repair-runner with broken-CLI fallback (`watchdog/repair_runner.py`)
**Scope:** Medium — Complexity: 3
1. **Implement** `RepairRunner` in `watchdog/repair_runner.py`: accepts an allowlisted command string, executes it via `subprocess.run`, captures stdout/stderr/returncode. If the `megaplan`/`arnold` executable is missing or raises (shadowed checkout), records a `command_unavailable` outcome — never crashes. Returns a structured `RepairResult(status, stdout, stderr, rc)`.
2. **Broken-CLI resilience:** `RepairRunner` checks `shutil.which` before execution and catches `FileNotFoundError`/`OSError`. Scanner/classification/snapshot never go through this path (they use direct FS/process access, Steps 9-13).
3. **Add** `tests/test_watchdog_repair_runner.py` for `test_repair_runner_handles_missing_executable` and `test_repair_runner_executes_allowlisted_command`.

### Step 17: CLI entrypoint (thin glue orchestrator) (`scripts/megaplan_live_watchdog.py`)
**Scope:** Medium — Complexity: 3
1. **Create** `scripts/megaplan_live_watchdog.py` (note `scripts/__init__.py` already exists). `argparse` flags: `--once` (single scan + report), `--roots` (comma list, default `DEFAULT_SCAN_ROOTS`), `--repair-runner {subprocess,dry-run}` (default `subprocess`), `--report-path`, `--registry-path` (default `~/.megaplan/watchdog/registry.ndjson`).
2. **`main()` is strictly glue-only** (resolves FLAG-008). Correct dataflow:
   a. Calls `build_snapshot(roots)` → produces a `Snapshot` dict (`scan_ts_utc`, `plans[]`, `incidents[]` with complete SignalBundles including `in_flight_llm`).
   b. Loads `WatchdogRegistry` and updates seen plans.
   c. For the snapshot's incidents, creates a temp directory `tmpdir`, constructs `RuntimeEnvelope(artifact_root=str(tmpdir))`, and invokes `arnold.pipeline.executor.run_pipeline(pipeline, initial_state={"snapshot": snapshot_dict}, envelope=envelope)`.
   d. **After pipeline execution**, reads the classification artifact from `tmpdir / classify / classifications.json` (produced by ClassifyStep inside the pipeline). Selects problem incidents from these pipeline-produced classifications — NOT from the snapshot. No inline classification policy exists in `main()`.
   e. Reads diagnosis and repair-decision artifacts from `tmpdir / diagnose / diagnoses.json` and `tmpdir / repair_decision / repair_decisions.json`.
   f. For each problem incident, feeds the pipeline's repair recommendation to `RetryLoop` + `RepairRunner` (no inline retry or repair policy).
   g. Writes the report artifact to `--report-path` and updates the registry.
3. **Keep** the daemon's scanner/process logic CLI-independent so `--once` works with a broken `megaplan` binary (only the repair path shells out, which has the Step 16 fallback).
4. **Add** `tests/test_watchdog_cli.py` for `test_watchdog_works_with_broken_megaplan_cli` (monkeypatch `shutil.which("megaplan") → None` and assert the scan/snapshot still succeed and only the repair path reports `command_unavailable`).

### Step 18: Documentation
**Scope:** Small — Complexity: 1
1. **Add** `docs/megaplan_live_watchdog.md` covering: manual usage `python scripts/megaplan_live_watchdog.py --once [--roots ...] [--report-path ...]`; hourly scheduling (a `launchd` plist snippet for macOS + a cron line); the pipeline I/O contract (Snapshot JSON via `initial_state`, artifact files written under `RuntimeEnvelope.artifact_root`); the seven health categories explaining `false_stall` detection (progressing + in_flight_llm + no recent real events); the allowlist policy; and the degraded-mode behavior when repair-agent credentials are unavailable.

---

## Execution Order
1. Steps 1→2→3→4: skeleton/contract → models (including in_flight_llm) → classifier + allowlist (all pure, all testable).
2. Steps 5→6→7→8: repair agent → stages → pipeline assembly + contract wiring (Arnold executor).
3. Steps 9→10→11→12→13→14: discovery engine — scanner, processes, tmux, correlation, signals (including in_flight_llm extraction), snapshot+registry (independent of pipeline internals except shared JSON Snapshot contract).
4. Steps 15→16→17: retry state machine, repair-runner adapter, CLI glue orchestrator (depend on both pipeline and engine; CLI reads classifications from pipeline artifacts).
5. Step 18: docs last.

## Validation Order
1. After Step 1: `read_manifest` + `validate_package_module` return clean.
2. After Steps 3-4: focused unit tests for classifier (including false_stall with in_flight_llm) + allowlist pass.
3. After Step 8: full pipeline integration test passes — pipeline accepts a Snapshot dict via `initial_state` (including incidents with in_flight_llm signals), writes artifact files under `RuntimeEnvelope.artifact_root`, daemon reads the action report.
4. After Steps 9-14: `pytest tests/test_watchdog_discovery.py tests/test_watchdog_processes.py tests/test_watchdog_tmux.py tests/test_watchdog_correlate.py tests/test_watchdog_signals.py tests/test_watchdog_registry.py`.
5. After Steps 15-17: `pytest tests/test_watchdog_retry_loop.py tests/test_watchdog_repair_runner.py tests/test_watchdog_cli.py`.
6. Final: full repo test suite (`pytest -q`) to confirm no regressions, plus a static scan confirming no forbidden destructive git/delete commands were introduced.
