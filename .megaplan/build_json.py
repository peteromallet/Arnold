import json

with open('.megaplan/plan_v4_draft.md', 'r') as f:
    plan_text = f.read()

output = {
    "plan": plan_text,
    "changes_summary": "Revised plan v4 addressing both open significant flags from critique v3. (1) FLAG-007/correctness: Added in_flight_llm: bool and last_event_age_seconds: Optional[float] to SignalBundle (Step 2). Updated compute_signal_bundle (Step 13) to extract in_flight_llm from events.ndjson by scanning for unmatched llm_call_start entries within 2 hours. Updated classify_incident (Step 3) to detect false_stall when liveness is 'progressing' AND in_flight_llm is True AND last_event_age_seconds > 300 — the plan is only 'progressing' because of a hanging LLM call, effectively stalled. Added defensive fallback for stalled + in_flight_llm. Updated pipeline integration test (Step 8) to include an in-flight LLM snapshot fixture verifying false_stall flows through. (2) FLAG-008/correctness: Rewrote Step 17 (CLI) to describe the correct dataflow: daemon builds snapshot → runs pipeline → reads classifications.json from artifact_root → selects problem incidents from pipeline output. Removed the erroneous 'classifications already in the snapshot' language. The CLI now explicitly reads pipeline-produced classification artifacts after pipeline execution, with no inline classification policy.",
    "flags_addressed": [
        {
            "id": "FLAG-007",
            "resolution": "addressed",
            "reason": "Added in_flight_llm: bool and last_event_age_seconds: Optional[float] to SignalBundle model (Step 2). Updated compute_signal_bundle (Step 13) to extract in_flight_llm from events.ndjson by scanning for unmatched llm_call_start entries (replicating _compute_liveness internal logic at introspect.py:268-288). Updated classify_incident (Step 3) to detect false_stall when liveness=='progressing' AND in_flight_llm==True AND last_event_age_seconds>300 (the only 'progress' is a hanging LLM; no real event in >300s means effectively stalled). Added defensive fallback for stalled+in_flight_llm. Updated tests in Steps 3 and 8 to cover the false_stall path. This makes false_stall reliably reachable despite _compute_liveness returning 'progressing' for in-flight-LLM plans.",
            "where": "Phase 1 — Step 2 (SignalBundle gains in_flight_llm + last_event_age_seconds fields), Step 3 (classifier updated with primary false_stall detection path), Phase 2 — Step 6 (ClassifyStep uses updated SignalBundle), Step 8 (pipeline test includes in-flight-LLM fixture), Phase 3 — Step 13 (compute_signal_bundle extracts in_flight_llm from events.ndjson)"
        },
        {
            "id": "FLAG-008",
            "resolution": "addressed",
            "reason": "Rewrote Step 17 dataflow description to be internally consistent. The daemon now: (a) builds snapshot, (b) loads registry, (c) runs pipeline with snapshot as initial_state, (d) AFTER pipeline execution reads classifications.json from artifact_root, (e) selects problem incidents from pipeline-produced classifications — not from the snapshot. Removed all 'classifications already in the snapshot' language. The Snapshot contract (Steps 2, 14) remains scan_ts_utc/plans[]/incidents[] — classifications are produced inside the pipeline by ClassifyStep and read by the daemon from artifact files. No inline classification policy exists in main().",
            "where": "Phase 4 — Step 17 (CLI entrypoint — complete dataflow rewrite from 'selects problem incidents via classification already in the snapshot' to explicit pipeline-artifact reading sequence)"
        }
    ],
    "assumptions": [
        "Registry naming: the package directory is `live_supervisor` (underscore) so it is importable while the CLI name is `live-supervisor` (hyphen, via _cli_name registry.py:860).",
        "The daemon engine lives as a new code module `arnold/pipelines/megaplan/watchdog/` (sibling of the existing `supervisor/` code module). It is NOT auto-discovered as a pipeline because the registry only scans the `pipelines/` subdir.",
        "Registry persistence uses NDJSON at `~/.megaplan/watchdog/registry.ndjson` — simpler than SQLite, adequate for tens-to-hundreds of plans, trivially migratable later.",
        "The 5-minute wait lives in the daemon; the pipeline's RecheckEmitStep only emits a recheck_after timestamp and a resumable marker and never sleeps.",
        "The DiagnoseStep reads pre-bundled SignalBundle from each incident (computed by the daemon's compute_signal_bundle), keeping the pipeline pure and tests free of subprocesses/LLM.",
        "Repair dispatch is abstracted behind a RepairAgent Protocol with a FakeRepairAgent for tests and a HermesRepairAgent that degrades to no_repair_available when credentials/launchers are absent.",
        "DEFAULT_SCAN_ROOTS is an explicit module constant (the five required roots, ~-expanded, with /private/tmp↔/tmp dedup on macOS) consumed by both discover_plans() and the --roots CLI flag; missing roots are skipped silently.",
        "Broken-megaplan-CLI fallback: the repair-runner attempts allowlisted commands and, on a missing/shadowed executable, records command_unavailable and continues; the scanner/correlator/signals never use the CLI.",
        "arnold_api_version is \"1.0\" (must be 1.x; CURRENT_MAJOR=2 at manifest.py:27) and driver is the plain string \"in_process\", entrypoint is the bare name \"build_pipeline\".",
        "Tests follow repo conventions: pipeline tests under tests/pipelines/test_live_supervisor*.py and daemon tests as flat tests/test_watchdog_*.py; never tests/arnold/ or tests/scripts/.",
        "The MVP uses linear Stage composition (not ParallelStage) for per-incident handling; ParallelStage fanout is noted as a future enhancement.",
        "Pipeline invocation: the daemon creates a temp directory, constructs RuntimeEnvelope(artifact_root=str(tmpdir)), and invokes arnold.pipeline.executor.run_pipeline(pipeline, initial_state={\"snapshot\": snapshot_dict}, envelope=envelope). After execution it reads artifact files from tmpdir / <stage> / <artifact>.json. This is the identical pattern to tests/pipelines/test_jokes_pipeline.py:69-77.",
        "Degraded signal bundles: when compute_signal_bundle fails (corrupt state, missing events, import error), it returns SignalBundle(degraded=True, failure_reason=...). The classifier maps degraded bundles to unknown health category, and RepairDecisionStep emits no_repair_available. in_flight_llm defaults to False and last_event_age_seconds to None when events are unreadable.",
        "Pipeline output files: each step writes one JSON artifact file under ctx.artifact_root / <stage_name> / and returns the Path in StepResult.outputs. The Arnold executor merges outputs into state; the daemon also reads artifact files directly from the artifact_root directory.",
        "StepContext is imported from arnold.pipeline (Arnold neutral type) — it carries artifact_root: str, state: Any, inputs: Mapping, and other fields. Steps use ctx.artifact_root exclusively (no bridge to ctx.plan_dir needed).",
        "in_flight_llm detection in compute_signal_bundle replicates the _compute_liveness internal logic (introspect.py:268-288): find unmatched llm_call_start within last 2 hours where no llm_call_end with matching request_id exists. Stale starts >2h old are excluded (they don't count as in-flight).",
        "false_stall classification uses the primary path liveness==progressing AND in_flight_llm==True AND last_event_age_seconds>300 because _compute_liveness always returns progressing when in_flight_llm is true (defeating the stalled+in_flight_llm path). The stalled+in_flight_llm check remains as defensive fallback."
    ],
    "success_criteria": [
        {
            "criterion": "The live_supervisor package's __init__.py exposes all 8 required manifest fields as module-level literals (name, description, default_profile, supported_modes, driver, entrypoint, arnold_api_version, capabilities) plus a top-level build_pipeline, and read_manifest()/validate_package_module() both succeed with zero errors.",
            "priority": "must",
            "requires": ["run_tests", "read_files"]
        },
        {
            "criterion": "classify_incident() maps every observed signal combination to the correct one of the seven health categories, including: progressing+in_flight_llm+last_event>300s→false_stall (NEW v4), live process+terminal→all_good, no process+recent events→recent triage, no process+no events+non-terminal→dead_or_disappeared, degraded signal bundle→unknown. Covered by test_classifier_distinguishes_all_health_categories.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "enforce_allowlist() rejects all six forbidden destructive command categories (git reset/checkout/push/merge, worktree deletion, plan-dir deletion), allows introspect/trace/doctor/chain status unconditionally, and gates auto/resume/chain-start on the required context fields, covered by test_allowlist_blocks_destructive and test_allowlist_allows_safe.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "RetryLoop state machine makes at most three attempts per incident, refuses the fourth, and returns (unresolved, True) with retry_count=3; success-before-cap and terminal-mid-loop paths are exercised, covered by test_retry_loop_caps_at_three_attempts.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "discover_plans() finds state.json-bearing plan directories under all five default roots and deduplicates overlapping roots, covered by test_scanner_discovers_plans_across_all_roots.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "scan_processes() identifies Megaplan/Arnold/Shannon/Codex/Claude processes without false positives and checks pid liveness via _pid_is_live, covered by test_scanner_parses_process_signatures and test_scanner_checks_pid_liveness.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "correlate_processes_to_plans() prefers exact plan-name, then exact plan-dir, then chain current_plan, rejecting broad repo-path matches, covered by test_correlates_process_to_plan_by_exact_name and test_rejects_broad_repo_path_matches.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "compute_signal_bundle() produces liveness, block_details, in_flight_llm (NEW v4), last_event_age_seconds (NEW v4), and normalized doctor findings per plan; on failure returns degraded SignalBundle with degraded=true and failure_reason while in_flight_llm defaults to False. Covered by test_signal_computation_degraded and test_in_flight_llm_extraction.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "WatchdogRegistry (NDJSON) records first_seen/last_seen/last_state/incident_count/retry_count, updates last_seen on re-encounter, and marks disappeared plans, covered by test_registry_remembers_and_updates_seen_plans.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "build_pipeline() assembles a valid 4-stage pipeline (classify→diagnose→repair_decision→recheck_emit) that accepts a Snapshot dict via initial_state (including incidents with in_flight_llm signals — NEW v4), writes classification/diagnosis/repair/recheck artifacts under RuntimeEnvelope.artifact_root, and produces a structured per-incident action report with no subprocesses or LLM calls launched. The false_stall category flows correctly through the pipeline when given an in-flight LLM incident fixture. Covered by test_pipeline_accepts_snapshot_and_produces_action_report using the Arnold executor pattern (RuntimeEnvelope + run_pipeline).",
            "priority": "must",
            "requires": ["run_tests", "parse_diff"]
        },
        {
            "criterion": "When repair-agent credentials/model launchers are unavailable, the pipeline degrades to report-only: classification and diagnosis still run and RepairDecisionStep emits a no_repair_available verdict rather than failing, covered by test_degraded_mode_report_only_no_credentials.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "RecheckEmitStep returns promptly with a recheck_after timestamp = now+300s and a resumable marker and never sleeps internally, covered by test_five_minute_wait_emitted_not_blocked.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "The watchdog scanner/correlator/signal-computation/snapshot work via direct filesystem and process access with no dependency on the installed megaplan CLI; with megaplan missing/broken it still produces a valid snapshot and only the conditional repair path records command_unavailable, covered by test_watchdog_works_with_broken_megaplan_cli.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "RepairRunner executes allowlisted commands and gracefully handles missing/shadowed executables by recording command_unavailable rather than crashing, covered by test_repair_runner_handles_missing_executable and test_repair_runner_executes_allowlisted_command.",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "No forbidden destructive commands (git reset/checkout/push/merge, worktree deletion, plan-directory deletion) appear anywhere in the new code (scanner, engine, pipeline, CLI); static search of the diff returns zero matches.",
            "priority": "must",
            "requires": ["read_files", "parse_diff"]
        },
        {
            "criterion": "The full existing test suite still passes after all changes (no regressions introduced by the new package or engine).",
            "priority": "must",
            "requires": ["run_tests"]
        },
        {
            "criterion": "Each new module file stays roughly under 300 lines and each step/function has a single clear responsibility.",
            "priority": "should",
            "requires": ["read_files", "subjective_judgment"]
        },
        {
            "criterion": "The pipeline uses Arnold StepContext/StepResult idiomatically (steps import from arnold.pipeline, write artifacts to ctx.artifact_root/<stage>/, return file paths in outputs, use state_patch for inter-stage data, linear classify→diagnose→repair_decision→recheck_emit via Edge/halt) consistent with the jokes pipeline pattern.",
            "priority": "should",
            "requires": ["read_files"]
        },
        {
            "criterion": "Documentation includes manual usage (python scripts/megaplan_live_watchdog.py --once), an hourly scheduling example (launchd plist or cron), the live-supervisor pipeline input/output contract (Snapshot JSON via initial_state, artifact files under RuntimeEnvelope.artifact_root), and explains false_stall detection (progressing+in_flight_llm+no recent real events).",
            "priority": "should",
            "requires": ["read_files"]
        },
        {
            "criterion": "Manual smoke run of python scripts/megaplan_live_watchdog.py --once on a machine with at least one .megaplan plan produces a readable report artifact.",
            "priority": "info",
            "requires": ["run_shell", "observe_runtime_logs"]
        }
    ],
    "questions": []
}

with open('.megaplan/plan_v4_output.json', 'w') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print("JSON written successfully")
