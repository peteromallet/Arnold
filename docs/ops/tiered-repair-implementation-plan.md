# Tiered Repair Implementation Plan

## Executive Summary

The repo already has most of the one-hour repair and six-hour audit machinery, but it is spread across large cloud wrapper scripts and several Python state helpers. The implementation should not begin with a rewrite. It should first make the existing repair entrypoint current-plan anchored, self-verifying, and evidence-producing, then add immediate failure-triggered repair as an enqueue layer, and only then add meta-repair and richer audit behavior.

The critical path is now governed by the data contract in
`docs/ops/tiered-repair-data-contract.md`. That contract makes four things
non-negotiable: current-target resolution must be recorded in every artifact,
process liveness is only partial proof, human escalation is an answer/resume
ledger rather than a deletable marker, and every state-mutating repair actor
uses one shared session lock.

The implementation critical path is:

1. Standardize the repair evidence contract emitted by `arnold-repair-loop`.
2. Centralize current-target resolution and shared repair locking.
3. Make verification prove live/progressing state, not only tmux/process liveness.
4. Add a failure-triggered repair request path that feeds the same bounded repair loop as the hourly watchdog.
5. Add a 60-minute repair envelope and a 90-minute meta-repair wrapper.
6. Convert human escalation to a durable answer/resume ledger.
7. Expand the six-hour auditor so it cross-references prior incidents and can land narrow repair-system fixes with tests.

## Executable Five-Sprint Epic

After an adversarial Codex review from five perspectives, the executable epic
order is intentionally different from the inventory-style stages below. The
reviewers agreed that the old Stage 1 through Stage 8 list captures the right
implementation surface, but it defers resolver, locking, escalation
preservation, redaction gates, and cloud rollback safety too late for an
autonomous cloud rollout.

The chain-ready epic lives at:

- `.megaplan/initiatives/tiered-repair-hardening/chain.yaml`
- `.megaplan/initiatives/tiered-repair-hardening/briefs/`
- `.megaplan/initiatives/tiered-repair-hardening/notes/challenge-synthesis.md`

The five aggressive two-week sprints are:

1. **Cloud-safe substrate**: repair contract kernel, current-target resolver in
   observe mode, shared repair lock, universal redaction, escalation ledger
   skeleton/current pointer, feature flags, and rollback-capable cloud runbook.
2. **Repair correctness**: enforce lock use inside the existing one-hour repair
   loop, add the 60-minute envelope, replace liveness-only success with
   independent verification, and prove true-human-blocker outcomes.
3. **Failure-triggered repair**: add repair requests, dedupe, stale suppression,
   trigger wrapper, watchdog queue scan, and only the highest-signal hooks
   (`latest_failure` and `awaiting_human_verify`) first.
4. **Human workflow and cloud hardening**: make escalation answerable,
   resumable, authorized, current-target matched, supersedable, and covered by
   cloud smoke/rollback evidence.
5. **Meta-repair and auditor intelligence**: add gated meta-repair, root-cause
   audit cross-references, green checks, retention/index cleanup, and bounded
   repair-system fixes.

Feature flags or observe-only modes are required for behavior-changing layers,
especially request dispatch, meta-repair, and audit autofix. Meta-repair and
auditor source edits start disabled or patch-only until prior conformance gates
pass.

Four nested DeepSeek/Hermes mapping probes were run before writing this plan. All completed successfully:

- Watchdog/repair wrappers.
- Chain/plan state and failure hooks.
- Six-hour auditor and meta-repair.
- Discord/resident/human escalation.

A second Codex/DeepSeek pass produced `docs/ops/tiered-repair-data-contract.md`
with four more probes: persisted data, stage handoffs, retention/indexing, and
adversarial critique. Its findings are folded into the architecture and stages
below.

## Current Implementation Surface

### Cloud Watchdog

Primary file: `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`

Important functions:

- `scan_once()` scans marker files under `/workspace/.megaplan/cloud-sessions`, adopts marker-less tmux sessions, calls `launch_chain_tick()`, reaps stale repairs, and writes `/workspace/watchdog-report.json`.
- `launch_chain_tick()` is the per-session decision engine. It checks terminal state, chain health, plan attention state, state mismatch, awaiting-human states, stale needs-human sidecars, sibling sessions, repair-loop busy state, and direct relaunch fallback.
- `plan_attention_status_env()` is embedded Python that inspects plan and chain state, `latest_failure`, `active_step`, state mismatch, manual review, awaiting-human, tiers tried, and pushed commits.
- `chain_health_status()` is embedded Python that detects chain cycles, repeated completion-guard failures, stuck nonterminal state, no-advance, and uncommitted execute output. It already avoids no-advance false positives while an active plan step is live.
- `repair_unhealthy_session()` and `dispatch_kimi_repair()` dispatch the bounded repair wrapper in the background.
- `repair_needs_human_matches_current_plan()` filters stale needs-human sidecars against the current plan.
- `workspace_has_other_alive_session()` prevents relaunching a superseded parent when a sibling session is alive.
- `notify_needs_human()` sends Discord/webhook escalation when repair cannot be started or a true manual review remains.
- `resolve_relaunch_command()` builds the plan/chain relaunch command.

System behavior:

- The main loop is `while true; do scan_once; sleep "$INTERVAL"; done`.
- The default interval is hourly.
- The watchdog already background-dispatches the repair loop instead of blocking the tick.
- Some stale-parent and stale-sidecar guards exist, but the policy ordering is scattered rather than centralized.

Tests:

- `tests/cloud/test_watchdog_wrappers.py` is the main wrapper characterization suite.
- Relevant existing tests include awaiting-human/manual-review dispatch, stale needs-human marker clearing, sibling session suppression, chain health no-advance guards, repair-loop busy locks, recurrence wiring, and Discord DM fallback behavior.

### One-Hour Repair Loop

Primary file: `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`

Important functions:

- `repair_data_init()` initializes the repair-data JSON artifact.
- `repair_clear_stale_state_if_needed()` clears stale latest failures, replay tail artifacts, and plan/chain mismatches before model repair.
- `repair_recurrence_prepare_attempt()` calls `arnold_pipelines.megaplan.cloud.repair_recurrence`.
- `run_dev_fix_turn()` dispatches the dev-fix model sequence.
- `mechanical_launch_step()` kills/relaunches the target session and calls verification.
- `verify_started_and_holding()` currently proves the session starts and remains alive for the initial/hold checks.
- `run_kimi_launch_turn()` is the fallback launch operator.
- `repair_exhausted_should_retry_without_human()` distinguishes repeated mechanical failures from true human gates.
- `send_discord_escalation()` formats and sends the terminal escalation.
- `write_needs_human_marker()` writes `<session>.needs-human.json`.

Current flow:

- Early exit if the target is already complete or alive.
- Optionally clear stale state and try mechanical relaunch.
- Run exactly three iterations:
  - iteration 1: GLM if available, otherwise Codex `gpt-5.4`;
  - iteration 2: Codex `gpt-5.4`;
  - iteration 3: Codex `gpt-5.5`;
  - each iteration tries dev-fix, mechanical launch, and Kimi launch if configured.
- If recurrence is detected without a human gate, exit as `recurring_retry_pending`.
- Otherwise send Discord escalation and write the needs-human marker.

Gaps:

- The loop has fixed iterations but no top-level 60-minute wall-clock envelope.
- Repair-data is rich but not a formal contract shared by meta-repair and audit.
- Verification is liveness-oriented; it does not yet require state advancement or fresh event proof.
- Current-plan anchoring exists in pieces, not as one reusable resolver.

### Recurrence and Repair State

Primary file: `arnold_pipelines/megaplan/cloud/repair_recurrence.py`

Important functions:

- `build_problem_signature()` builds controlled-field signatures from failure context.
- `build_advancement_snapshot()` captures plan/chain/git/PR progress signals.
- `update_session_repair_snapshot()` records per-session repair-progress history.
- `evaluate_recurrence()` detects same-signature and no-advance recurrence.
- `atomic_write_json()` is the existing safe writer for repair-loop sidecars.

Tests:

- `tests/cloud/test_repair_recurrence.py` covers layer 1 and layer 2 recurrence, advancement resets, merged PR detection, git branch advancement, and state fallbacks.

### Six-Hour Progress Auditor

Primary file: `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`

Systemd units:

- `arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.service`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-progress-audit.timer`

Important behavior:

- Runs every 6 hours through systemd.
- Discovers plans from markers, tmux/workspace activity, and recent state/event changes.
- Builds evidence from plan state, chain state/logs, repair-data history, stale-state evidence, watchdog reports, and user action context.
- Dispatches Codex as the top-level audit orchestrator with `codex exec --sandbox danger-full-access`.
- The Codex brief tells Codex to use DeepSeek subagents and may allow narrow source fixes in `$ARNOLD_SRC` on `editible-install`.
- Writes `/workspace/audit-reports/<ts>-audit.{json,md}` and appends `/workspace/audit-report.log`.

Current config knobs:

- `MEGAPLAN_AUDIT_MARKER_DIR`
- `MEGAPLAN_AUDIT_REPAIR_DATA_DIR`
- `MEGAPLAN_AUDIT_REPORT_DIR`
- `MEGAPLAN_AUDIT_REPORT_LOG`
- `MEGAPLAN_AUDIT_WATCHDOG_REPORT`
- `MEGAPLAN_AUDIT_ARNOLD_SRC`
- `MEGAPLAN_AUDIT_DISCOVER_BIN`
- `MEGAPLAN_AUDIT_LAUNCHER`
- `MEGAPLAN_AUDIT_WINDOW_HOURS`
- `MEGAPLAN_AUDIT_SUBAGENT_TIMEOUT_SECS`
- `MEGAPLAN_AUDIT_SUBAGENT_MAX_TOKENS`
- `MEGAPLAN_AUDIT_SUBAGENT_PROFILE`
- `MEGAPLAN_AUDIT_MODEL`
- `MEGAPLAN_AUDIT_CODEX_TIMEOUT_SECS`
- `MEGAPLAN_AUDIT_SUBAGENT_SKILL`

Gaps:

- It can recommend or perform bounded fixes through Codex, but the evidence store does not yet cross-reference prior tickets, old audit reports, old watchdog reports, or root-cause patterns.
- There is no dedicated progress-auditor test file.
- The wrapper says "5-hour" in the service description while the timer runs every 6 hours.

### Chain, Plan State, and Failure Hooks

Primary files:

- `arnold_pipelines/megaplan/_core/state.py`
- `arnold_pipelines/megaplan/auto.py`
- `arnold_pipelines/megaplan/planning/state.py`
- `arnold_pipelines/megaplan/chain/status.py`
- `arnold_pipelines/megaplan/supervisor/chain_runner.py`
- `arnold/runtime/event_journal.py`
- `arnold/execution/backend.py`
- `arnold/pipeline/steps/human_gate.py`
- `agentbox/guardian/handlers.py`
- `agentbox/run_dirs.py`

Important functions and surfaces:

- `write_plan_state()` writes `<plan_dir>/state.json` atomically with lock protection.
- `_record_lifecycle_failure()` in `auto.py` records `latest_failure` and optional `resume_cursor`.
- `_clear_latest_failure_for_success()` clears stale failure fields after success.
- `set_active_step()`, `touch_active_step()`, and `clear_active_step()` maintain `active_step`.
- `STATE_AWAITING_HUMAN_VERIFY` defines the plan state used for human verification gates.
- `classify_chain_status()` maps plan state into operation status.
- `NdjsonEventJournal` writes runtime `events.ndjson`.
- `agentbox/run_dirs.py::append_event()` writes operation-run events.
- `HumanGateStep.run()` writes `awaiting_user.json` and halts.
- `MegaplanChainGuardianHandler` maps chain status into guardian transitions.

Safe hook principle:

- Do not run repair synchronously inside these state/journal writers.
- Emit a small repair request marker/event and let the cloud watchdog/trigger process start the normal repair wrapper.

Candidate hook points:

- `arnold_pipelines/megaplan/auto.py::_record_lifecycle_failure()` after `latest_failure` is written.
- `arnold_pipelines/megaplan/auto.py` active-step orphan/stale handling paths after a worker is proven dead.
- `arnold/pipeline/steps/human_gate.py::HumanGateStep.run()` after `awaiting_user.json` is written, for mechanical clarification gates.
- `arnold/execution/backend.py` where `node_failed` or `run_failed` events are appended.
- `agentbox/guardian/handlers.py::MegaplanChainGuardianHandler` where effective status becomes failed, stale bookkeeping, or awaiting human verify.

### Discord, Resident, and Human Escalation

Primary files:

- `arnold_pipelines/megaplan/discord_dm.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-discord-dm`
- `arnold_pipelines/megaplan/resident/discord.py`
- `arnold_pipelines/megaplan/resident/config.py`
- `arnold_pipelines/megaplan/resident/auth.py`
- `arnold_pipelines/megaplan/resident/runtime.py`
- `arnold_pipelines/megaplan/resolution_contract.py`
- `arnold_pipelines/megaplan/blocker_recovery.py`
- `arnold_pipelines/megaplan/user_actions.py`

Important functions and config:

- `discord_dm.send_discord_dm()` sends REST DMs using `DISCORD_BOT_TOKEN` and `DISCORD_DM_USER_ID`.
- `discord_dm.render_discord_dm()` formats chunked payloads.
- `ResidentConfig.from_env()` reads resident Discord/user/model config.
- `ResidentAuthorizer` enforces allowed users/channels and high-impact action confirmation.
- `resolution_contract.classify_resolution_behavior()` separates satisfied/fallback/hard-block states.
- `blocker_recovery.evaluate_prerequisite_blockers()` and `evaluate_quality_blockers()` classify blockers and whether continuation is allowed.

Current policy:

- `arnold-repair-loop::repair_exhausted_should_retry_without_human()` already avoids Discord escalation for recurring non-human mechanical problems.
- `arnold-watchdog::launch_chain_tick()` dispatches repair before needs-human for `awaiting_human` and auto-stall `manual_review`.
- Direct Discord escalation remains for genuine manual review or unavailable repair.

Tests:

- `tests/arnold_pipelines/megaplan/test_discord_dm.py`
- `tests/resident/test_discord_outbound.py`
- Existing cases in `tests/cloud/test_watchdog_wrappers.py` around `manual_review`, `awaiting_human`, and needs-human markers.

### Existing Subagent Dispatch

Primary files:

- `arnold_pipelines/megaplan/skills/subagent-launcher/launch_hermes_agent.py`
- `arnold_pipelines/megaplan/skills/subagent-launcher/fan.py`
- `arnold_pipelines/megaplan/resident/subagent.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-kimi-goal-operator`
- `arnold_pipelines/megaplan/pipelines/live_supervisor/repair_agent.py`

Important details:

- `resident/subagent.py::launch_subagent_task()` already wraps `launch_hermes_agent.py` asynchronously and could be a model for Python-native audit/meta-repair dispatch.
- `live_supervisor/repair_agent.py::HermesRepairAgent` is only a stub and raises `NotImplementedError`.
- `arnold-progress-auditor` dispatches Codex, and the Codex prompt dispatches DeepSeek.
- `arnold-repair-loop` dispatches Codex/Hermes/Kimi directly through wrapper commands rather than through a reusable Python abstraction.

## Proposed Architecture and Flow

### Governing Data Contract

The implementation should treat `docs/ops/tiered-repair-data-contract.md` as
the data authority. New code should implement the contract incrementally, but it
should not introduce new sidecars or reports whose semantics conflict with it.

Core contract rules:

- Every repair, audit, trigger, meta-repair, and escalation artifact records the
  current-target resolver output or a reference to it.
- Mutable current files remain available for fast readers, but incident,
  attempt, escalation, meta-repair, audit, and repair-event history is immutable
  or append-only.
- `verification.status = "partial_liveness"` is not terminal success.
- Human escalation is an append-only ledger plus a mutable current pointer.
- Failure context included in prompts, Discord payloads, Markdown reports, and
  contract summaries is redacted before persistence or dispatch.
- Any actor that mutates plan state, chain state, repair sidecars, or human
  escalation records must hold the shared repair lock for that target.

### Shared Repair Evidence Contract

Create the stable JSON contract emitted by each repair attempt and consumed by
meta-repair and audit.

Recommended module:

- New: `arnold_pipelines/megaplan/cloud/repair_contract.py`

Responsibilities:

- Normalize the fields already present in `<session>.repair-data.json`.
- Provide `load_repair_evidence()`, `write_repair_evidence()`, and `append_repair_event()` helpers.
- Provide schema-like validation without adding a heavy dependency.
- Preserve backward compatibility with old repair-data files.
- Write both mutable current snapshots and immutable attempt/incident records.
- Redact secret-bearing fields before writing prompt-visible or human-visible
  summaries.

Minimum fields:

- `schema_version`
- `chain_session_id`
- `workspace_path`
- `remote_spec`
- `run_kind`
- `current_chain_state_path`
- `current_plan_name`
- `current_plan_state`
- `active_phase`
- `active_worker_pid`
- `latest_failure`
- `clarification_gate`
- `markers_considered`
- `sidecars_considered`
- `policy_ordering_decision`
- `repair_action_attempted`
- `launch_command`
- `verification`
- `discord_escalation`
- `recurrence`
- `known_prior_issue_refs`
- `outcome`

Additional contract artifacts:

- current snapshot: `<marker_dir>/repair-data/<session>.repair-data.json`;
- immutable attempts: `<marker_dir>/repair-data/attempts/<attempt_id>.json`;
- incidents: `<marker_dir>/repair-data/incidents/<incident_id>.json`;
- repair events: `<marker_dir>/repair-events.ndjson`;
- summary Markdown: `<marker_dir>/repair-data/<session>.repair-summary.md`;
- current needs-human pointer: `<marker_dir>/repair-data/<session>.needs-human.json`;
- escalation ledger: `<marker_dir>/repair-data/escalations.ndjson`;
- repair-data index: `<marker_dir>/repair-data/index.json`.

The contract should remain JSON/NDJSON-first so the bash wrappers can write it
through embedded Python until more wrapper logic is extracted. Markdown
companions are summaries, not authority.

### Shared Repair Lock

Add one lock primitive used by failure-triggered repair, hourly repair,
meta-repair, and audit-initiated cleanup.

Recommended module:

- New: `arnold_pipelines/megaplan/cloud/repair_lock.py`

Responsibilities:

- Implement an atomic `mkdir`-style session/workspace lock.
- Record lock owner, pid, command, started timestamp, target id, and timeout.
- Provide stale-lock inspection without deleting useful proof.
- Make state mutation helpers assert the lock is held where practical.

Initial use sites:

- `arnold-repair-loop` before stale state clearing, gate answering, relaunch,
  needs-human updates, and repair marker mutation;
- `arnold-repair-trigger` before dispatching a one-hour repair for a request;
- `arnold-meta-repair-loop` before retriggering or applying repair-system state
  cleanup;
- six-hour auditor only when it performs cleanup or bounded fixes that mutate
  the cloud repair state.

### Current Target Resolver

Centralize the policy ordering from the design doc.

Recommended module:

- New: `arnold_pipelines/megaplan/cloud/current_target.py`

Responsibilities:

- Given a marker/session/workspace/spec, resolve:
  - live child chain state;
  - active plan state;
  - live tmux/process evidence;
  - fresh chain events;
  - matching current repair markers;
  - stale parent markers;
  - historical sidecars.
- Return a structured decision: current target, stale artifacts to ignore/clear, and rationale.
- Return stable identifiers: `target_id`, current plan ref, chain ref, and
  ignored artifact refs.

Initial use sites:

- `arnold-watchdog::plan_attention_status_env()`
- `arnold-watchdog::repair_needs_human_matches_current_plan()`
- `arnold-watchdog::workspace_has_other_alive_session()`
- `arnold-repair-loop::repair_data_init()`
- `arnold-repair-loop::repair_clear_stale_state_if_needed()`

Implementation note:

- Do not replace all embedded Python at once. First add the module and call it from wrapper heredocs, then migrate duplicated wrapper snippets in follow-up PRs.

### Failure-Triggered Repair Requests

Add a lightweight request enqueue layer rather than direct long-running repair calls from runtime code.

Recommended files:

- New: `arnold_pipelines/megaplan/cloud/repair_requests.py`
- New wrapper: `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
- Optional systemd path/service:
  - `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.path`
  - `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service`

Flow:

1. Failure hook writes an immutable request JSON under `/workspace/.megaplan/cloud-sessions/repair-requests/`.
2. The request also appends an event to `<marker_dir>/repair-events.ndjson`.
3. The trigger wrapper coalesces duplicate requests by current target signature.
4. The trigger wrapper acquires the shared repair lock before dispatching.
5. The trigger wrapper calls the same dispatch path used by the watchdog:
   - either `arnold-watchdog --once` for broad reconciliation;
   - or a narrower wrapper mode that invokes `repair_unhealthy_session`/`dispatch_kimi_repair` for one marker.
6. `arnold-repair-loop` remains the fixer of record.

Hook events:

- `latest_failure_recorded`
- `awaiting_human_verify`
- `worker_exited_expected_active`
- `state_missing_or_invalid`
- `state_mismatch`
- `stale_marker_conflict`
- `no_advance_outside_active_step`

Deduplication:

- Key by target id, normalized incident signature, trigger kind, state/event
  cursor, and active step run id when present.
- Do not key primarily by exact timestamp; timestamp drift fragments the same
  incident.
- Add a bounded `root_cause_hint_hash` from redacted stderr/message/error-code
  context so distinct failures in the same phase do not collapse into one
  recurrence.
- Use the shared repair lock, not just PID/busy sidecars, to prevent concurrent
  state mutation.

### One-Hour Repair Budget and Verification

Change `arnold-repair-loop` from "three iterations" to "bounded loop within 60 minutes", while preserving the current model order initially.

Recommended changes:

- In `arnold-repair-loop` add top-level env:
  - `CLOUD_WATCHDOG_REPAIR_BUDGET_SECS=3600`
  - `CLOUD_WATCHDOG_REPAIR_ITERATION_MAX=3` for compatibility during migration.
- Track `deadline_epoch` at startup.
- Before every model dispatch, Kimi launch, mechanical launch, and Discord escalation, record remaining budget and skip impossible work.
- Record `repair_timeout` as a distinct outcome if the deadline expires.
- Wrap long subcommands with remaining-budget timeouts rather than fixed 600-second defaults.

Verification changes:

- Extend `verify_started_and_holding()` or add `verify_repair_effect()` after it.
- Proof options, in order:
  - current target is complete;
  - current target is awaiting a true human blocker and Discord escalation was delivered or explicitly unavailable;
  - worker/tmux is alive and `active_step.last_activity_at`, chain event seq, plan iteration, milestone index, or git head advanced after launch;
  - fresh `events.ndjson` or chain log lines appeared after launch.
- "tmux alive only" should become `verification.partial_liveness`, not success.
- A self-reported dev-fix summary is evidence about what the agent claimed, not
  proof of repair. Record git before/after and whether a nontrivial diff
  occurred.
- Prompt-visible verification data must be redacted.

### Meta-Repair Loop

Add a separate wrapper for repair-system failure.

Recommended files:

- New wrapper: `arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop`
- New Python helper: `arnold_pipelines/megaplan/cloud/meta_repair.py`
- New systemd service/timer or watchdog dispatch path:
  - `arnold_pipelines/megaplan/cloud/systemd/megaplan-meta-repair.service`
  - optional `megaplan-meta-repair.timer` if using a queue scan model.

Trigger conditions:

- `arnold-repair-loop` exits with `repair_timeout`.
- `arnold-repair-loop` cannot inspect required state.
- `arnold-repair-loop` cannot launch its model/tooling.
- `arnold-repair-loop` exhausts budget and `recurring_retry_pending` persists for the same signature.
- Discord escalation fails for a true human decision.
- Repair actors cannot acquire the shared lock because stale lock handling is
  itself broken.
- Verification remains at `partial_liveness` for the same incident signature.

Flow:

1. Read the repair evidence contract and recent watchdog/audit reports.
2. Diagnose whether the bug is in wrapper code, prompt, stale marker handling, current-target resolution, shared locking, verification, launch command, env/config, model availability, or Discord escalation.
3. Patch Arnold repair tooling only when the fix is bounded and testable.
4. Run focused tests.
5. Re-run `arnold-repair-loop` for the same session.
6. Verify the repair loop itself succeeded by evidence, not by direct hand-fixing the epic.
7. Stop after 90 minutes or when the remaining issue is proven human-only.

Dispatch model:

- Initial implementation can use `codex exec --sandbox danger-full-access` as the orchestrator, following the progress auditor pattern.
- The prompt must explicitly equip Codex to launch nested DeepSeek/Hermes subagents and require it to delegate broad mapping, log/history review, independent root-cause probes, and bounded fix investigations to those subagents wherever practical.
- Later, consider Python-native dispatch through a real `HermesRepairAgent` implementation.

### Six-Hour Auditor Enhancements

Keep `arnold-progress-auditor` as the outer wrapper, but enrich the evidence and reporting.

Add cross-reference inputs:

- `/workspace/audit-reports/*.json`
- `/workspace/audit-report.log`
- `/workspace/watchdog-report.json`
- `/workspace/watchdog-reports/*.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/*.repair-data.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/index.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/incidents/*.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/attempts/*.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/meta/*.json`
- `/workspace/.megaplan/cloud-sessions/repair-data/escalations.ndjson`
- `/workspace/.megaplan/cloud-sessions/repair-events.ndjson`
- `/workspace/.megaplan/cloud-sessions/*.repair-progress.json`
- `/workspace/repair-findings/persistent-problems.md`
- Store tickets through `arnold_pipelines/megaplan/store/_file/tickets.py` when available.
- Recent commits in `$ARNOLD_SRC`.

Add root-cause pattern output:

- New report field: `root_cause_patterns`.
- New report field: `related_prior_incidents`.
- New report field: `autonomous_fix_attempts`.
- New report field: `risky_or_deferred_fixes`.
- New report field: `green_checks`, even when no suspicious plans are found.

Autonomous fix policy:

- Allowed: narrow Arnold repair-system bugs with focused tests and no secret exposure.
- Allowed: stale state cleanup in the running workspace when evidence proves it is stale.
- Not allowed: broad refactors, policy changes that alter human approval semantics, or direct epic hand-fixes that bypass repair-loop verification.

## Exact Files, Functions, and Scripts Likely to Edit

### New Files

- `arnold_pipelines/megaplan/cloud/repair_contract.py`
- `arnold_pipelines/megaplan/cloud/repair_lock.py`
- `arnold_pipelines/megaplan/cloud/current_target.py`
- `arnold_pipelines/megaplan/cloud/repair_requests.py`
- `arnold_pipelines/megaplan/cloud/meta_repair.py`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-trigger`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.path`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-repair-trigger.service`
- `arnold_pipelines/megaplan/cloud/systemd/megaplan-meta-repair.service`
- Optional: `arnold_pipelines/megaplan/cloud/systemd/megaplan-meta-repair.timer`
- `tests/cloud/test_repair_contract.py`
- `tests/cloud/test_repair_lock.py`
- `tests/cloud/test_current_target.py`
- `tests/cloud/test_repair_requests.py`
- `tests/cloud/test_meta_repair.py`
- Optional: `tests/cloud/test_progress_auditor.py`

### Existing Files

- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
  - `scan_once()`
  - `launch_chain_tick()`
  - `plan_attention_status_env()`
  - `chain_health_status()`
  - `repair_unhealthy_session()`
  - `dispatch_kimi_repair()`
  - `repair_needs_human_matches_current_plan()`
  - `workspace_has_other_alive_session()`
  - `notify_needs_human()`
  - `resolve_relaunch_command()`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
  - `repair_data_init()`
  - `repair_recurrence_prepare_attempt()`
  - `repair_clear_stale_state_if_needed()`
  - `mechanical_launch_step()`
  - `verify_started_and_holding()`
  - `run_dev_fix_turn()`
  - `run_kimi_launch_turn()`
  - `repair_exhausted_should_retry_without_human()`
  - `send_discord_escalation()`
  - `write_needs_human_marker()`
  - main loop near `for iteration in 1 2 3`
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`
  - discovery evidence builder
  - `dispatch_one()`
  - Codex/DeepSeek brief template
  - JSON/Markdown report writer
- `arnold_pipelines/megaplan/cloud/repair_recurrence.py`
  - reuse and possibly extend `build_problem_signature()` and `build_advancement_snapshot()`
- `arnold_pipelines/megaplan/auto.py`
  - `_record_lifecycle_failure()`
  - orphaned/stale active step handling
- `arnold_pipelines/megaplan/_core/state.py`
  - probably no behavior change at first; use as the stable state writer.
- `arnold/pipeline/steps/human_gate.py`
  - `HumanGateStep.run()`
- `arnold/execution/backend.py`
  - failure event emission around `node_failed`/`run_failed`
- `agentbox/guardian/handlers.py`
  - chain status to repair request emission
- `arnold_pipelines/megaplan/resident/subagent.py`
  - possible reuse for meta-repair/audit subagent dispatch, not required in stage 1.
- `arnold_pipelines/megaplan/pipelines/live_supervisor/repair_agent.py`
  - implement `HermesRepairAgent` later if Python-native repair agents become a goal.
- Tests:
  - `tests/cloud/test_watchdog_wrappers.py`
  - `tests/cloud/test_repair_recurrence.py`
  - `tests/arnold_pipelines/megaplan/watchdog/test_repair_runner.py`
  - `tests/arnold_pipelines/megaplan/test_discord_dm.py`
  - `tests/resident/test_discord_outbound.py`
  - selected runtime/chain tests touched by hook emission.

## Staged Implementation Plan

### Stage 1: Formalize Repair Evidence

Goal:

- Make the existing repair loop emit a stable contract without changing repair decisions.

Implementation:

- Add `repair_contract.py`.
- Teach `arnold-repair-loop` to include `schema_version`, current target, markers considered, verification result, recurrence result, Discord status, and outcome in the existing repair-data JSON.
- Write a mutable latest snapshot plus immutable incident and attempt records.
- Add `repair-events.ndjson` append support for request, attempt, verification,
  escalation, meta-repair, and cleanup events.
- Add redaction helpers for prompt-visible and human-visible failure context.
- Preserve existing keys for old tests and old auditor parsing.
- Add a small validator command or function used by tests.

Tests:

- Add `tests/cloud/test_repair_contract.py`.
- Add redaction tests for stderr, command lines, auth headers, API keys, token
  shaped strings, and event payloads.
- Extend `tests/cloud/test_watchdog_wrappers.py` cases that already inspect repair-data:
  - failure signal collection;
  - stale state clearing;
  - awaiting-human classification;
  - needs-human marker writing;
  - recurrence.
- Run:
  - `pytest tests/cloud/test_repair_contract.py tests/cloud/test_repair_recurrence.py`
  - `pytest tests/cloud/test_watchdog_wrappers.py -k "repair_loop or recurrence or needs_human"`

Validation:

- Run a local fixture repair loop and assert the JSON validates.
- Confirm old report writer still handles existing fields.

### Stage 2: Add Shared Repair Lock And Current-Target Resolution

Goal:

- Enforce the design policy ordering in one place and ensure state mutation is
  serialized through one shared lock.

Implementation:

- Add `repair_lock.py`.
- Use an atomic lock directory with owner metadata, target id, pid, command,
  started timestamp, and timeout.
- Wire the lock into `arnold-repair-loop` before stale state clearing,
  gate-answering, relaunch, needs-human writes, and repair marker mutation.
- Add `current_target.py`.
- Implement resolver over marker JSON, chain state, plan state, tmux/process evidence, event mtimes, needs-human sidecars, repair-progress sidecars, and sibling sessions.
- First wire it into wrapper heredocs only for observe/diagnostic output.
- Then replace `repair_needs_human_matches_current_plan()` internals with resolver-backed logic.
- Then use it in `repair_data_init()` so every repair evidence file records the same target decision.
- Record ignored stale artifacts and resolver rationale in repair evidence.

Tests:

- Add `tests/cloud/test_repair_lock.py` covering:
  - exactly one actor acquires the lock;
  - stale lock is detected but not silently deleted;
  - mutation helpers refuse to run without a lock where practical.
- Add `tests/cloud/test_current_target.py` covering:
  - live child chain beats stale parent marker;
  - active plan beats stale needs-human sidecar;
  - sibling live session suppresses parent relaunch;
  - fresh events beat old repair-progress sidecars;
  - invalid/missing state returns explicit diagnostics.
- Extend wrapper characterization:
  - stale needs-human marker clearing;
  - sibling session clearing;
  - awaiting-human repair dispatch against current plan.

Validation:

- `pytest tests/cloud/test_repair_lock.py`
- `pytest tests/cloud/test_current_target.py`
- `pytest tests/cloud/test_watchdog_wrappers.py -k "stale repair needs-human or sibling or awaiting_human"`

### Stage 3: Improve Verification Semantics

Goal:

- Treat repair success as live/progressing/human-proven, not just process alive.

Implementation:

- Add `verify_repair_effect()` in `arnold-repair-loop` or `repair_contract.py`.
- Capture pre-launch and post-launch snapshots:
  - chain state;
  - plan state;
  - `active_step`;
  - event/log mtimes and sequence;
  - git HEAD when relevant;
  - tmux/process liveness.
- Update `mechanical_launch_step()` to call the enhanced verifier.
- Record `verification.status` as one of:
  - `complete`;
  - `progressed`;
  - `live_with_fresh_activity`;
  - `true_human_blocker`;
  - `partial_liveness`;
  - `failed`.
- Keep current "came up and held" behavior as a compatibility fallback until tests are updated.
- Remove that compatibility fallback before this stage is considered complete:
  terminal success must never be based on process liveness alone.

Tests:

- Extend `tests/cloud/test_watchdog_wrappers.py` around `verify_started_and_holding()`.
- Add fixtures where tmux is alive but no state/event progress occurs.
- Add fixtures where event seq advances without milestone index change due to active long-running step.
- Add a fixture where a dev-fix claims success but produces no nontrivial diff;
  assert the claim is not success proof.

Validation:

- `pytest tests/cloud/test_watchdog_wrappers.py -k "verify_started or mechanical_launch or chain_health_no_advance"`

### Stage 4: Add 60-Minute Repair Envelope

Goal:

- Replace implicit fixed attempt behavior with an explicit 60-minute budget while preserving the current iteration sequence.

Implementation:

- In `arnold-repair-loop`, add `CLOUD_WATCHDOG_REPAIR_BUDGET_SECS`.
- Compute `deadline_epoch`.
- Add `remaining_budget_secs()` helper.
- Wrap model dispatches, Kimi launch, mechanical relaunch, and state inspection in remaining-budget timeouts.
- Keep `CLOUD_WATCHDOG_REPAIR_ITERATION_MAX=3` for initial compatibility.
- Set outcome `repair_timeout` when the envelope expires.
- Make timeout an explicit trigger for meta-repair.

Tests:

- Add wrapper tests with very small budget:
  - timeout before first model dispatch;
  - timeout between mechanical launch and Kimi;
  - timeout records evidence and does not send human escalation unless blocker is true human.
- Assert old three-iteration behavior remains when budget permits.

Validation:

- `pytest tests/cloud/test_watchdog_wrappers.py -k "repair_loop and timeout"`

### Stage 5: Failure-Triggered Repair Request Layer

Goal:

- Start repair soon after known bad states without waiting for the hourly tick.

Implementation:

- Add `repair_requests.py` for atomic request writing, dedupe keys, and queue scan.
- Add `arnold-repair-trigger` wrapper:
  - reads request queue;
  - resolves current target;
  - refuses stale/superseded requests;
  - acquires the shared repair lock before dispatch;
  - dispatches existing repair loop through the same lock/busy policy as watchdog.
- Add systemd path/service for cloud deployment, or make watchdog run a short request scan at the start of every `scan_once()`.
- Add hook emission in:
  - `auto.py::_record_lifecycle_failure()`;
  - `human_gate.py::HumanGateStep.run()`;
  - `arnold/execution/backend.py` failure event branches;
  - `agentbox/guardian/handlers.py` failed/stale/awaiting-human status mapping.

Tests:

- `tests/cloud/test_repair_requests.py`:
  - atomic writes;
  - dedupe;
  - timestamp drift does not split the same incident;
  - redacted root-cause hints separate materially different incidents;
  - stale request suppression;
  - repair busy suppression.
- Focused runtime tests for hook emission should assert request file content only, not start real repair.
- Wrapper tests for `arnold-repair-trigger` should run against temp marker dirs.

Validation:

- `pytest tests/cloud/test_repair_requests.py`
- `pytest tests/cloud/test_watchdog_wrappers.py -k "repair_running or repair_dispatched"`
- Selected tests around lifecycle failure and human gate once hook files are added.

### Stage 6: Meta-Repair Wrapper

Goal:

- When the one-hour loop fails as a system, fix the repair system and prove the ordinary repair loop then succeeds.

Implementation:

- Add `meta_repair.py` helpers:
  - load repair evidence;
  - classify repair-system failure;
  - build Codex/DeepSeek prompt;
  - record meta-repair attempts;
  - enforce 90-minute budget.
- Add `arnold-meta-repair-loop` wrapper.
- Trigger it from `arnold-watchdog` when repair evidence outcome is `repair_timeout`, persistent `recurring_retry_pending`, state-inspection failure, model/tool launch failure, or Discord delivery failure for a true human blocker.
- Require meta-repair output to include:
  - diagnosis;
  - files changed;
  - tests run;
  - retrigger command;
  - verification evidence.
- Require meta-repair records under `repair-data/meta/` and a Markdown
  companion.
- Meta-repair may only count success if the ordinary repair loop is retriggered
  and produces non-partial verification.
- Do not let meta-repair count direct epic hand-fixing as success unless the normal repair loop subsequently succeeds.

Tests:

- `tests/cloud/test_meta_repair.py`:
  - classification from repair evidence;
  - prompt contains "fix repair system, not epic one-off";
  - budget enforcement;
  - retrigger requirement;
  - post-retrigger verification must not be `partial_liveness`;
  - no secrets in prompt snapshot.
- Wrapper characterization in `tests/cloud/test_watchdog_wrappers.py`:
  - meta-repair dispatch after timeout;
  - no dispatch for true human-only blocker with delivered Discord.

Validation:

- `pytest tests/cloud/test_meta_repair.py`
- `pytest tests/cloud/test_watchdog_wrappers.py -k "meta_repair or repair_timeout or recurring_retry"`

### Stage 7: Six-Hour Auditor Cross-References and Bounded Fixes

Goal:

- Make the auditor useful as a root-cause loop, not only a suspicious-plan reporter.

Implementation:

- Add evidence collection for:
  - previous audit reports;
  - watchdog reports;
  - archived watchdog reports;
  - repair-data history across sessions;
  - incident/attempt/meta/escalation records;
  - repair-events ledger;
  - repair findings;
  - tickets;
  - recent repair-system commits.
- Update auditor brief to require:
  - related prior issues;
  - root-cause category;
  - bounded fix eligibility decision;
  - tests required before commit.
- Add report fields for root-cause patterns and related incidents.
- Add `green_checks` so a quiet six-hour window still leaves proof of what was
  examined.
- Add a green-report summary of what was checked when there are no suspicious plans.
- Fix systemd service description to match 6 hours.

Tests:

- Add `tests/cloud/test_progress_auditor.py` or extend existing wrapper tests:
  - no suspicious plans still writes useful report;
  - prior audit report is linked;
  - repair-data repeated signature is included;
  - Codex dispatch prompt includes bounded-fix and no-secrets policy;
  - report includes `root_cause_patterns`.

Validation:

- `pytest tests/cloud/test_progress_auditor.py`
- `pytest tests/cloud/test_watchdog_wrappers.py -k "progress auditor"`

### Stage 8: Discord Escalation Hardening

Goal:

- Escalate only true human decisions and make each escalation answerable,
  resumable, and auditable.

Implementation:

- Add a small classification helper, probably in `repair_contract.py` or a new `human_blockers.py`, that normalizes:
  - unresolved user actions;
  - `manual_review` with human origin;
  - `awaiting_human_verify`;
  - auto-stall/manual-review mechanical gates;
  - satisfied/waived/accepted-blocked user action resolutions.
- Use it in `arnold-repair-loop::repair_exhausted_should_retry_without_human()` and `arnold-watchdog::launch_chain_tick()`.
- Add append-only `escalations.ndjson` entries for escalation opened,
  delivered, answered, superseded, timed out, and resume attempted.
- Keep `<session>.needs-human.json` only as a mutable current pointer.
- Include exact question, allowed responses, suggested default, current plan,
  current chain state, evidence paths, response channel/message id, resume
  handler/command, and Discord delivery status in the escalation record.
- Keep `DISCORD_BOT_TOKEN`, `DISCORD_DM_USER_ID`, auth headers, command-line
  tokens, and secret-shaped log snippets out of logs and prompts.
- A cleared needs-human pointer must not delete the escalation ledger history.

Tests:

- Extend `tests/arnold_pipelines/megaplan/test_discord_dm.py`.
- Extend `tests/cloud/test_watchdog_wrappers.py` around manual-review and awaiting-human cases.
- Extend `tests/resident/test_discord_outbound.py` only if resident outbound behavior changes.
- Add tests that a human answer maps back to an escalation id and resume handler.
- Add tests that superseded questions are resolved in the ledger, not erased.

Validation:

- `pytest tests/arnold_pipelines/megaplan/test_discord_dm.py tests/resident/test_discord_outbound.py`
- `pytest tests/cloud/test_watchdog_wrappers.py -k "manual_review or awaiting_human or discord"`

## Risks and Policy Decisions

### Risks

- The wrappers are large shell scripts with embedded Python. Large edits can regress cloud behavior without obvious local failures.
- Hooking runtime state writers directly to long-running repair would destabilize normal execution. Use marker emission only.
- Current-plan resolution can become too clever and accidentally clear useful historical sidecars. Treat stale clearing as explicit, logged, and test-covered.
- "Tmux alive" is not enough proof, but requiring state advancement too quickly can false-fail legitimately slow workers. Use fresh activity as an intermediate success state.
- Autonomous audit fixes can become too broad. The auditor must be constrained to repair-system bugs with focused tests.
- Discord delivery can fail because of config/env rather than human absence. Treat delivery failure as a repair-system issue, not proof the human was notified.
- Exact timestamp dedupe can fragment the same incident; overly broad
  controlled-field dedupe can collapse distinct root causes. Use normalized
  signatures plus redacted root-cause hints.
- A deletable needs-human marker can lose the only copy of a question while the
  human is trying to answer. Preserve escalation history in the ledger.
- Any prompt or Markdown report that includes stderr, command lines, log tails,
  or event payloads can leak secrets unless redaction is contract-level.
- Meta-repair can falsely credit itself for transient recovery. Its success
  proof must be an ordinary repair-loop retrigger that produces non-partial
  verification.

### Policy Decisions

- Meta-repair should be a separate wrapper, not folded into `arnold-repair-loop`, so normal repair remains bounded and inspectable.
- Failure hooks should enqueue repair requests and return immediately.
- The repair evidence contract should be tolerant of old sidecars.
- The shared lock is required before repair actors mutate plan state, chain
  state, repair sidecars, needs-human pointers, or escalation ledgers.
- Human escalation history is append-only; current pointers may be cleared or
  superseded, but the ledger is preserved.
- The six-hour auditor may patch Arnold repair tooling only when it can run a focused test and commit a narrow change.
- Direct hand-fixing the epic is not a successful meta-repair unless the ordinary repair loop is retriggered and verified.
- Discord should be reserved for true human decisions, not mechanical clarification gates or stale markers.
- Process liveness alone is never terminal success.

## Cloud Machine Runbook After Merge/Deploy

After merging and deploying the staged changes to the cloud machine:

1. Update the Arnold source on the cloud machine and confirm the editable install points at the deployed checkout.
2. Install or refresh wrappers under `/usr/local/bin`:
   - `arnold-watchdog`
   - `arnold-repair-loop`
   - `arnold-progress-auditor`
   - new `arnold-repair-trigger`
   - new `arnold-meta-repair-loop`
3. Install or refresh systemd units:
   - existing watchdog units;
   - `megaplan-progress-audit.service`;
   - `megaplan-progress-audit.timer`;
   - new repair-trigger service/path if used;
   - new meta-repair service/timer if used.
4. Run `systemctl daemon-reload`.
5. Restart or reload the watchdog service.
6. Enable/start any new repair-trigger path/timer.
7. Confirm `megaplan-progress-audit.timer` is enabled and has the expected 6-hour cadence.
8. Run a one-shot watchdog scan:
   - `arnold-watchdog --once`
9. Run a synthetic repair-data validation against recent sidecars.
10. Run a no-op or fixture repair-trigger request and confirm it is deduped or dispatched correctly.
11. Inspect, without printing secrets:
   - `/workspace/watchdog-report.json`
   - latest `/workspace/watchdog-reports/*.json`, if archival is enabled
   - `/workspace/audit-report.log`
   - latest `/workspace/audit-reports/*.md`
   - `/workspace/.megaplan/cloud-sessions/repair-data/*.repair-data.json`
   - `/workspace/.megaplan/cloud-sessions/repair-data/index.json`
   - `/workspace/.megaplan/cloud-sessions/repair-data/escalations.ndjson`
   - `/workspace/.megaplan/cloud-sessions/repair-events.ndjson`
12. Confirm the shared repair lock can be acquired/released by a fixture repair
    and that a second actor reports busy/coalesced without mutating state.
13. Confirm Discord escalation with a safe test payload only if configured, and verify the result file says delivered or gives a non-secret failure reason.
14. Confirm the safe test escalation leaves a ledger entry and a mutable current
    pointer, and that resolving/superseding the pointer preserves ledger history.

## Open Questions Requiring Human Judgement

- Should the failure-triggered repair path be systemd path-based, watchdog-polled, or both? Both is more robust; systemd-only is cleaner but easier to miss if unit installation drifts.
- Should meta-repair be allowed to commit and push autonomously, or should it stop after producing a patch and test evidence? The current auditor already allows narrow autonomous commits; meta-repair could follow that policy, but it is higher impact.
- What is the acceptable delay before declaring "live but no state advancement" a verification failure for long-running workers? The code should support a configurable threshold.
- Should repair evidence become a documented compatibility surface for external tools, or remain internal to the cloud wrappers for now?
- Which ticket store should the auditor use on the cloud machine when multiple workspaces/repos are active?
- Should Discord responses be free text, strict commands with escalation ids, or
  structured reaction/button choices?
- Which paths may store raw unredacted evidence locally, and what permissions
  should they require?
- Should meta-repair require a negative-control retry to distinguish a true
  repair-system fix from transient recovery?
