# Changelog

## 0.22.0 (BREAKING)

This release **removes the YAML pipeline runtime** and introduces a single Python composition framework for defining megaplan pipelines.

### Breaking changes

- **YAML pipeline runtime removed.** The YAML compiler (`megaplan/_pipeline/compiler.py`), schema (`megaplan/_pipeline/schema.py`), loader (`megaplan/_pipeline/loader.py`), and YAML-specific step glue (`megaplan/_pipeline/steps/gate.py`, the YAML wrapper modes in `steps/agent.py` / `steps/panel.py` / `steps/human_gate.py`) are gone. `megaplan/pipelines/planning/pipeline.yaml` and `megaplan/pipelines/writing-panel-strict/pipeline.yaml` have been deleted alongside their YAML-only tests (`tests/_pipeline/test_loader.py`, `tests/_pipeline/test_schema.py`, `tests/_pipeline/test_yaml_steps.py`).
- **Pipeline discovery now scans Python modules**, not YAML files. The registry looks for sibling Python modules under `megaplan/pipelines/<name>(.py|/)` and user-installed modules under `~/.megaplan/pipelines/<name>.py`, each exposing a `build_pipeline()` factory. The hardcoded built-ins (`planning`, `doc-critique`, `judges`) continue to register through their existing builder functions; sibling-file discovery is additive.
- **Migration note.** Any external YAML pipelines (none known) must be rewritten as Python modules that expose `build_pipeline() -> Pipeline` constructed via `Pipeline.builder(...)` and the pattern library. The internal pipelines (`planning`, `writing-panel-strict`) have already been ported.

### New surface

- **Python composition framework** in `megaplan._pipeline.patterns` — reusable pattern functions: `critique_revise_gate_loop`, `panel_parallel`, `alternating_turns`, `subpipeline_call`, `mode_prompts`, `iterate_until`, `escalate_if`, `majority_vote`, `phase_zero_gate`.
- **Fluent builder** at `megaplan._pipeline.builder.PipelineBuilder`, reached via `Pipeline.builder(name, description='', *, default_profile=None, supported_modes=())` on the existing `Pipeline` dataclass. The builder exposes chained methods `.input()`, `.agent()`, `.panel()`, `.gate()`, `.human_gate()`, `.subpipeline()`, `.tiebreaker()`, `.iterate()`, `.escalate()`, `.mode()`, `.overlay()`, `.build()` over the existing `Pipeline` / `Stage` / `ParallelStage` / `Edge` primitives. Pipeline-level metadata (description, default profile, supported modes) is held on the `PipelineRegistry.metadata` surface, not on the frozen `Pipeline` dataclass.
- **Planning tiebreaker is now first-class.** The `tiebreaker` stage in the planning pipeline runs the full researcher → challenger → synthesis child subloop via `TiebreakerStep` (the previous placeholder handler step has been replaced).

### Behavior delta to surface

- **Tiebreaker escalate emissions land directly on `finalize` via the new `gate`-kind `escalate → finalize` edge** and therefore do **not** exercise `run_pipeline_with_policy`'s escalate-policy resolver at `executor.py:349-355`. This matches the sibling planning gate stage, which already routes `escalate → finalize` directly. Callers that previously expected `policy.escalate.resolve()` to fire on a tiebreaker-subloop escalation will not see it. (Correctness-1 / FLAG-TIEBREAKER-ESCALATE-POLICY-BYPASS / warning #6.)

## Unreleased

### Repository organization

A repo-wide layout pass groups the loose top-level `megaplan/*.py` modules into four cohesive subpackages and consolidates a handful of misplaced files. **No compatibility shims were left at the old paths** — every internal caller (in `megaplan/**/*.py` and `tests/**/*.py`) was atomically rewritten to the new path in the same commit as each move. The public top-level `megaplan.__all__` surface is unchanged: every name previously re-exported at the `megaplan.*` top level is still importable from `megaplan.*`, now sourced from the new subpackage paths.

- **Documentation assets**: `scorecard.png` moved to `docs/assets/scorecard.png`; `README.md` reference updated.
- **Briefs**: `briefs/feedback-as-phase.md` and `briefs/with-feedback.md` moved to `docs/briefs/`; the empty top-level `briefs/` directory was removed.
- **Benchmarks**: top-level `evals/` renamed to `benchmarks/` (kept at repo root, not under `tests/`, so `swe_bench.py` stays out of pytest collection); the one caller in `tests/test_swe_bench.py` was rewritten.
- **Shared test contract helper**: `megaplan/tests/store_contract.py` (a test-only helper that shadowed `megaplan.tests`) moved to `tests/contract/store_contract.py`; `tests/test_db_store.py` and `tests/test_file_store.py` rewritten to import from the new path. The empty `megaplan/tests/` package was removed. The vendored `megaplan/agent/tests/` (hermes-agent's own test tree) is intentionally **not** touched.
- **`.gitignore`**: added `.desloppify.bak-*` so future desloppify backups are ignored by default; the user's local `.desloppify.bak-2026-05-16/` is **not** deleted (out of scope).
- **Pricing**: `megaplan/{claude,codex,fireworks}_pricing.py` moved into a new `megaplan/pricing/` package as `claude.py`, `codex.py`, `fireworks.py`. The package `__init__.py` re-exports the three submodules for `from megaplan.pricing import claude, codex, fireworks` style access.
- **Workers**: `megaplan/workers.py` (2,500-line module) became `megaplan/workers/_impl.py` under a new `megaplan/workers/` package, and `megaplan/shannon_worker.py` / `megaplan/hermes_worker.py` moved alongside as `megaplan/workers/shannon.py` and `megaplan/workers/hermes.py`. The new `megaplan/workers/__init__.py` re-exports the full public surface (`CommandResult`, `WorkerResult`, `STEP_SCHEMA_FILENAMES`, `validate_payload`, `run_step_with_worker`, `resolve_agent_mode`, `set_work_dir_override`, `session_key_for`, `update_session_state`, `mock_worker_output`, plus the test-relied-on private helpers) so `from megaplan.workers import X` continues to resolve. Inside the package, `shannon.py` and `hermes.py` import directly from `megaplan.workers._impl` (not the package `__init__`) to eliminate partial-import / circular-import risk. ~80 `patch('megaplan.workers.X')` test sites that targeted symbols defined inside the old `workers.py` were rewritten to `patch('megaplan.workers._impl.X')` so monkeypatching still hits the lookup-site.
- **Execute group**: `megaplan/step_edit.py` moved to `megaplan/execute/step_edit.py`; the three call sites (`megaplan/__init__.py`, `megaplan/cli.py`, `megaplan/handlers/shared.py`) were rewritten. The thin `megaplan/execution_timeout.py` re-export shim was deleted now that its only external caller (`tests/test_doc_mode.py`) imports from `megaplan.execute.timeout` directly.
- **Orchestration group**: nine helper modules moved into a new `megaplan/orchestration/` package — `evaluation.py`, `phase_result.py`, `iteration_pressure.py`, `verifiability.py`, `tiebreaker.py`, `parallel_critique.py`, `progress.py`, `feedback.py`, and `audit.py` → **renamed to `plan_audit.py`** on the way in, to disambiguate from the unrelated `megaplan/audits/` package. The orchestration `__init__.py` is deliberately lazy (no eager submodule imports) to avoid a circular through `megaplan.store.plan_repository`. The 60+ import sites across `megaplan/**` and `tests/**` were rewritten exhaustively, including string-form `patch('megaplan.evaluation.X')` mock targets. `megaplan.__all__` names like `build_orchestrator_guidance`, `compute_plan_delta_percent`, `flag_weight`, `build_gate_signals`, and `compute_recurring_critiques` now resolve through `megaplan.orchestration.evaluation` but remain importable at the top level.
- **Runtime group**: four infrastructure helpers — `sandbox.py`, `key_pool.py`, `capabilities.py`, `doc_assembly.py` — moved into a new `megaplan/runtime/` package. `types.py` and `flags.py` were intentionally **kept** at the top level (heavily referenced; moving them would have caused churn for no readability gain). The runtime `__init__.py` eagerly re-exports each submodule's public surface (`SandboxViolation`, `install_sandbox`, `acquire_key`, `resolve_model`, `ALL_CAPABILITIES`, `assemble_doc`, `extract_sections`, etc.) since the runtime modules sit at the bottom of the dependency graph with no circular risk.
- **Audits parallel-path dedupe**: `megaplan/audits/capabilities.py` and `megaplan/audits/verifiability.py` were byte-identical / near-duplicate copies of the canonical capability registry and verifiability audit. They have been collapsed into thin re-export shims (`from megaplan.runtime.capabilities import *` and `from megaplan.orchestration.verifiability import *` respectively, each with an explicit `__all__` snapshot) so the canonical implementation lives in exactly one place. All existing import sites — `from megaplan.audits.capabilities import …`, `from megaplan.audits.verifiability import …`, and `from megaplan.audits import …` — continue to resolve to the same symbols (verified via `is`-identity checks against the canonical modules).
- **No-shim policy**: per user direction, no compatibility shims were left at any of the old top-level module paths above (e.g. `megaplan/claude_pricing.py`, `megaplan/shannon_worker.py`, `megaplan/evaluation.py`). Every internal caller is rewritten to the new path. **Downstream consumers** outside this repo that still import `megaplan.shannon_worker`, `megaplan.hermes_worker`, `megaplan.evaluation`, etc., must update to the new paths listed above.
- **Deferred**: the `.claude/skills/megaplan.md` flat-file → `.claude/skills/megaplan/SKILL.md` directory-bundle migration is **not** performed here. It remains a flat file pending user confirmation that the host Claude Code skill auto-discovery handles the directory form on this machine.

### Ticket linkage proposal

Ticket `01KRDSY0BK70DB58H9QRD6ZGMR` ("Clean up megaplan/ structure — split mega-files and consolidate root modules") describes three independent cleanup axes. This plan addresses **Axis 2** (consolidate the 23 root-level `.py` files into cohesive subpackages: `pricing/`, `workers/`, `orchestration/`, `runtime/`, plus the `execute/step_edit.py` move and `audits/` dedupe) but **explicitly defers Axis 1** (splitting the mega-files `store/db.py` ~4,134 LOC, `store/file.py` ~3,011 LOC, `cli.py` ~2,180 LOC, `workers/_impl.py` ~2,491 LOC after the move, and `auto.py` ~1,696 LOC). Axis 3 (the `ARCHITECTURE.md` doc) is also untouched.

**Proposal**: link this plan to ticket `01KRDSY0BK70DB58H9QRD6ZGMR` with `resolves_on_complete=false` — the ticket must stay open after this plan completes so that the split-mega-files half remains visible as outstanding work. Equivalently, the `megaplan ticket link` CLI form is `megaplan ticket link 01KRDSY0BK70DB58H9QRD6ZGMR <epic_id>` *without* the `--resolves` flag (omitting `--resolves` is the equivalent of `resolves_on_complete=false`).

**Tickets NOT linked**:
- `01KRNKTKF8S857SZNMYH5DQ20D` ("Make `cloud chain` supervision first-class") — unrelated; no overlap with this layout refactor.
- `01KRP5NG65429N1Y5W8J15V2YR` ("`chain replan` leaves stale blocked execution state and weakly applies ordering fixes") — unrelated; chain-replan correctness issue, not a layout concern.

The actual `ticket link` invocation is pending user action **U4** (the after-execute confirmation in this plan's `user_actions.md`); the local `megaplan ticket` CLI also currently errors with `ModuleNotFoundError: No module named 'ulid'`, so the link operation would have to be performed in an environment with the ticket-store dependencies installed. This CHANGELOG entry stands as the durable manual record of the proposal until either condition is resolved.

## v0.21.0 — 2026-04-25

This release lands the full **Sprint 1 (step receipts + scope-drift hardening)** and **Sprint 2 (multi-profile bake-off)** features that v0.20.0's bakeoff caveat (`sprint1_pending: true`) was waiting on, plus a coordinated reliability pass on the auto-driver and executor caught by running the bake-off against itself.

### Sprint 1 — Step receipts + scope-drift hardening

Per-phase auditable records that make model-vs-model comparison and longitudinal queries possible.

- **Receipt artifact** per `(plan_id, phase, iteration, attempt)`: `step_receipt_<phase>_v<iter>.json` in the plan dir, also appended as a single line to a global append-only log at `~/.megaplan/audit/receipts.jsonl`. Plan-dir copy wins on divergence; jsonl is rebuildable from plan dirs.
- **Canonical prompt hash**: every receipt records both `prompt_hash_raw` (sha256 of the full rendered prompt) and `prompt_hash_canonical` (sha256 after redacting timestamps, plan-id, abs paths, env fingerprints). Canonicalization function lives in `megaplan/receipts/canonical.py` with a versioned `canonicalization_version: 1`. Two runs of the same plan-phase produce identical canonical hashes — the contract everything else rides on.
- **Phase-specific extractors** (`megaplan/receipts/extractors.py`): pure functions that turn already-written artifacts into per-phase metrics dicts. Plan emits `step_count`, `task_count`, `oos_file_count`, `success_criteria_count`, etc. Critique emits `findings_per_check`, `severity_distribution`, `rubber_stamp_ratio`. Execute emits `files_claimed`, `files_in_diff`, `scope_drift_files_added`, `loc_added_outside_claimed`, plus the same fields for blocking. Review emits verdict + per-task verdict counts. Trivially testable; can backfill historical plans.
- **Scope drift as a first-class metric**: `scope_drift_files_added`, `scope_drift_files_missing`, `loc_added_outside_claimed` with a `benign_set` allow-list. Severity tier (`none` / `low` / `high`) surfaces in StepResponse and as a top-level receipt field.
- **Blocking promotion**: at `robust` and `superrobust` robustness, `high` severity scope drift hard-blocks execute (`megaplan/execute/quality.py`). `standard` robustness still advises only — no behavior change there.
- **`megaplan audit query` subcommand**: filter the global jsonl by `--model`, `--phase`, `--profile`, `--since`; aggregate via `--agg avg,p50,p95`; output as table or `--json`. Sprint 1's read API.

### Sprint 2 — Multi-profile bake-off (full implementation)

`megaplan bakeoff {run,status,tail,compare,pick,merge,resume,abandon}` runs the same idea concurrently across N profiles, each in its own worktree, so you can compare profile output on identical inputs.

- **Worktree lifecycle**: `git worktree add --detach <path> <base-sha>` per profile, sibling to the repo at `<repo-parent>/.megaplan-worktrees/<exp-id>/<profile>/`. Base SHA captured once at bakeoff start; every profile demonstrably starts from the same commit. Detached HEADs deliberately. Cleanup is explicit: `bakeoff merge` removes worktrees on success, crashes leave a `BAKEOFF_CRASHED` marker for forensic diffs, `bakeoff abandon <exp-id>` is the explicit cleanup later.
- **Concurrent execution**: `asyncio.create_subprocess_exec` per profile, per-profile log files, no interleaving. Standard isolation invariants hold under load — main repo `git status` stays clean while N worktrees grow independent diffs.
- **Comparison schema** (versioned, `schema_version: 1`): `experiment_id`, `base_sha`, `idea_hash`, per-profile `outcome_status`, `metrics` (duration_s, cost_usd, rework_cycles, escalations, review_verdict, diff_lines, tests_added, scope_drift_severity_by_phase), `judge_verdict` (rank, rationale_per_profile, scope_drift_flags, concerns), `human_decision`. Failed profiles get null fields, never missing keys.
- **Three-tier decision**: auto-computed metrics (always), LLM judge (advisory, optional via `--judge`), human pick (authoritative via `bakeoff pick`).
- **LLM judge contract**: omit `--judge` → skip (no paid call); `--judge auto` → first free of `claude`/`codex`/`gpt-5` *not* present as an executor in any profile being compared, with canonical agent+model comparison; `--judge <model>` → explicit. Output: `comparison.json` (structured) + `comparison.md` (readable).
- **Asymmetric merge**: `git diff base..chosen-worktree-HEAD` piped to `git apply` (not `git merge` — no throwaway-branch history); copies all profiles' archive bundles (plan dir + auto.log + outcome.json + init.log) into `.megaplan/bakeoffs/<exp-id>/<profile>/`; copies the chosen profile's plan dir into `.megaplan/plans/` for follow-up reference.
- **Crash isolation**: profile failures (init crash, model 404, codex context exhaustion mid-run) don't kill the bakeoff. Crashed profiles still surface in `compare` as evaluation data ("this profile can't even plan this kind of idea").
- **`--detach`**: launches per-profile autos and returns immediately. Subprocesses continue as independent OS processes. User polls outcomes via `bakeoff status`. (Earlier behavior of awaiting completion regardless of `--detach` is fixed in this release.)
- **`--robustness {tiny,light,standard,robust,superrobust}`**: passed through to each profile's `megaplan init`. Default-None preserves prior behavior when omitted.
- **Project-layer profiles in worktrees**: orchestrator copies `<repo>/.megaplan/profiles.toml` into each worktree before init, so project-only profiles like `all-kimi` resolve from the worktree's gitignored `.megaplan/`.
- **Resume** (`bakeoff resume`) only relaunches non-terminal profiles — winners are left alone.

### Auto-driver reliability

A coordinated set of failure-mode-specific retry caps and graceful aborts. Each can be tuned independently and surfaces a distinct terminal status in the outcome.

- **`--max-context-retries N` (default 2)** with new `context_retry_exhausted` outcome status (exit code 7). When codex execute returns the fragment `"ran out of room in the model's context"`, auto-driver re-runs execute with `--fresh` appended (idempotent guard against double-append). Counts as a separate retry category from the stall threshold so it can't compound. Hit IRL during sprint 2's own execute (40 min in, batch 14/16) — without this, six retry iterations all immediately fail before stalling.
- **`--max-cost-usd N`** with new `cost_cap_exceeded` outcome status (exit code 6). After every phase, sums `cost_usd` across `state["history"]`; aborts the loop if cumulative spend exceeds N. The check runs *after* each phase so a single expensive phase finishes; the *next* phase doesn't launch. Default unset = no cap (existing behavior). Argparse rejects negative or non-numeric values.
- **`--max-blocked-retries N` (default 1)** with new `worker_blocked` outcome status (exit code 8). Detects when execute exits 0 but the latest history entry has `result: "blocked"` (e.g. done tasks missing `files_changed`/`commands_run` from hermes-style workers) and bails after N retries with the deviation reasons surfaced in the outcome. Without this, the auto-driver retries execute every iteration until stall-threshold catches it 5 iterations later — which two profiles in the reliability bake-off hit live.
- **DriverOutcome additions**: `total_cost_usd`, `cost_cap_usd`, `context_retries_used`, `max_context_retries`, `blocked_retries_used`, `max_blocked_retries`, `blocking_reasons[]`. All emitted in `to_json()` and the `--outcome-file` write.

### Executor — auto-attribute evidence

Closes the root cause of `worker_blocked` for hermes/glm-style workers that mark done with empty arrays.

- **`_auto_attribute_unclaimed_paths`** (`megaplan/execute/quality.py`): runs after `_merge_batch_results` and before `_check_done_task_evidence`. Captures the worktree's git-status snapshot, identifies paths not claimed by any task, finds done tasks in the current batch with empty `files_changed` AND empty `commands_run`, and attributes the unclaimed paths to those tasks. Marks each such task with `auto_attributed_files: true` so audits distinguish system-inferred from model-reported. Mirrors the marker into `payload["task_updates"]` so `execution_batch_<n>.json` reflects attribution.
- **Multi-task ambiguity**: when several done tasks share an unclaimed pool, all get the full pool (permissive) plus a single `Auto-attribution ambiguous: N done tasks shared K unclaimed files` deviation so users can disambiguate.
- **Recursive snapshot helper** (`_capture_git_status_snapshot_recursive`): expands untracked directories (which `git status --porcelain` lists as bare `dir/` entries) so newly-created dirs aren't lost during attribution.
- **Schema additions**: `auto_attributed_files: boolean` on the finalize-task and execute-task-update schemas, doc/joke-mode excluded.

### Profiles system

- **`--profile <name>`** flag on every megaplan subcommand that accepts agent/model overrides. Expands a named TOML preset into per-phase `--phase-model` arguments before argparse-driven dispatch.
- **Three-layer profile resolution**: built-in (`megaplan/profiles/*.toml`) → user (`~/.megaplan/profiles.toml`) → project (`.megaplan/profiles.toml`). Last layer wins per profile name.
- **State fallback**: handlers recover the profile name from `state['config']['profile']` when the auto-driver invokes a fresh subprocess that doesn't propagate `--profile`. Documented in the function's docstring.
- **`all-open` retuned**: plan/prep/revise/gate/finalize/loop_plan use `hermes:moonshotai/kimi-k2.6`; critique/execute/review/loop_execute/tiebreakers use `hermes:glm-5.1`. README profile section cleaned up.

### Hermes integration

- **Vendored `megaplan/agent/`** subtree (~5MB) — workers no longer rely on a parallel-installed hermes/agent CLI. Subtree imported from upstream commit `980e6b1c`.
- **Worker imports rewired** through the vendored subtree (`megaplan/hermes_worker.py`, `megaplan/workers.py`).
- **`megaplan/agent/__init__.py` sys.path shim**: ensures the vendored subtree's internal imports resolve regardless of the parent megaplan import context.

### Work directory handling

- **`workers.py`** defaults `work_dir` to the plan's `project_dir`, not the parent process's CWD. Stops cross-contamination when megaplan is invoked from outside the project dir.
- **Loud warning** when `work_dir` diverges from `project_dir` — surfaces a misconfiguration class that previously caused silent execute drift.

### Other

- **`--mode joke`** on `megaplan init`: tuned for film-scene scripts; uses `sections_written` evidence semantics rather than `files_changed`.
- **`--from-doc <path>`** on `megaplan init`: imports `## Settled Decisions` from a prior doc artifact into the new plan's success criteria. (Originally cut from v0.20.0 release notes; landing here for completeness.)
- **Module reorganization**: review-phase code grouped into `megaplan/review/` subpackage; audit/execute modules split into `megaplan/audits/` and `megaplan/execute/` subpackages; legacy `tests/test_megaplan.py` removed in favor of per-phase test files.
- **CHANGELOG and README**: updated alongside the diff for each major feature.

### Migration notes

- Receipts are **additive** — existing plans continue to function. No schema bump required.
- `bakeoff compare` schema stays at `schema_version: 1`. Sprint-1 receipt-derived fields (per-phase scope drift severity) populate live now where v0.20.0's caveat emitted nulls.
- New auto-driver flags default to safe values (`--max-context-retries 2`, `--max-blocked-retries 1`, `--max-cost-usd unset`). Existing scripts that run `megaplan auto` without these flags get a strictly better failure surface — no regression.
- New outcome statuses (`cost_cap_exceeded`, `context_retry_exhausted`, `worker_blocked`) and exit codes (6/7/8) — callers that switch on `outcome.status` should add cases.
- `auto_attributed_files: boolean` field is optional in finalize/execute schemas; absent means model-reported, present means system-inferred.

## v0.20.0 — 2026-04-21

### Sprint 2 bake-off — multi-profile worktree comparison

Adds `megaplan bakeoff {run,status,tail,compare,pick,merge,resume,abandon}` for running one idea through multiple profiles concurrently in isolated detached worktrees. `compare` produces the schema-versioned dataset, `pick` records the human selection, and `merge` applies only the chosen profile's code patch while archiving every profile's evaluation artifacts.

- **Judge contract**: omit `--judge` -> skip (no paid call); `--judge auto` -> first free of `claude`/`codex`/`gpt-5` with canonical agent+model comparison; `--judge <model>` -> explicit.
- **Sprint 1 caveat**: until receipts, canonical prompt hashes, and first-class scope drift fully land, `scope_drift_severity_by_phase` emits phase keys with `null` values plus `sprint1_pending: true`.
- **Forward-compatible schema**: bake-off comparison output uses `schema_version=1`; future receipt-derived fields arrive additively, with no schema bump.

### Sprint 2 cloud — chain commands, local + ssh providers, toolchain extensibility

Second sprint of the built-in cloud runner. Core megaplan gains chain ergonomics; cloud grows new providers and thin wrappers; the ad-hoc `~/Documents/reigh-megaplan-dev/` external folder is retired.

- **Core `megaplan chain start --spec <path>`**: validates the spec, resolves referenced idea files, kicks the auto-loop per milestone. Replaces the separate `init + auto` pair for chained milestones. Works locally without any cloud dependency.
- **Core `megaplan chain status --spec <path>`**: reads `chain_state.json`, prints `current_milestone`, `completed`, `remaining`, and per-milestone status. Human-readable block plus structured JSON `summary`.
- **Core `megaplan init --idea-file <path>`**: read the plan idea from a file instead of the positional CLI arg. Pairs with optional `--auto-start` to kick `auto` immediately after init.
- **Cloud wrappers (thin)**: `megaplan cloud chain <spec>` uploads the spec and invokes core `chain start` remotely; `megaplan cloud bootstrap <idea-file>` uploads an idea and invokes `init --idea-file --auto-start` remotely; `megaplan cloud status --chain` fetches the remote `chain_state.json` and runs the core formatter.
- **Local provider** (`provider: local`): docker-compose-backed runner for fast iteration and CI smoke tests. No Railway CLI, no cloud account. Template at `megaplan/cloud/templates/docker-compose.yaml.tmpl`.
- **SSH provider** (`provider: ssh`): plain docker-over-ssh. "Any host with docker + ssh" story. Supports persistent deploy dirs per-host.
- **Toolchain extensibility**: `toolchains:` block in `cloud.yaml` accepts named recipes (rust, go, java, or `custom` with a user-supplied install snippet). Template renderer appends matching Dockerfile stages so the baked image carries only what the target repo needs.
- **Secret redaction**: `megaplan cloud logs` output is passed through `megaplan/cloud/redact.py`, which masks values of declared `secrets:` keys as `***REDACTED***`. Follow-mode (`-f`) streams with the same redaction applied line-by-line.
- **`Provider.supports_session` capability**: session gating is now a capability flag on the provider ABC rather than a hardcoded `provider == "railway"` check in the CLI.
- **Reigh parity migration**: `docs/cloud-migration-from-reigh.md` documents the one-to-one field mapping between the old `~/Documents/reigh-megaplan-dev/` env vars and the new `cloud.yaml`. The external folder can be retired after running the parity deploy.

Concurrent refactors landing alongside sprint 2:
- `megaplan/handlers.py` (~6k lines) split into a `megaplan/handlers/` package by phase.
- `tests/test_megaplan.py` split into per-phase `test_critique.py`, `test_execute.py`, `test_finalize.py`, `test_gate.py`, `test_init_plan.py`, `test_prep.py`, `test_revise.py`.
- `--from-doc <path>` flag on `megaplan init` imports `## Settled Decisions` from a prior doc artifact into the new plan's success criteria.

## v0.19.0 — 2026-04-21

### Built-in cloud runner via `megaplan cloud`

Generalises the ad-hoc Railway container setup (previously external, at `~/Documents/reigh-megaplan-dev/`) into a built-in subcommand. Sprint 1 of two; scope is operational parity with the existing Railway flow.

- **New subcommand group**: `megaplan cloud {init,build,deploy,status,attach,logs,exec,resume,down,destroy}` covers the full lifecycle of a provider-backed run.
- **Subpackage layout** under `megaplan/cloud/`: `spec.py` (cloud.yaml loader + schema validation), `template.py` (renders `entrypoint.sh` / `railway.toml` / `cloud.yaml`), `cli.py` (argparse wiring, dispatched from `megaplan.cli`).
- **Provider plugin model**: `providers/` ships a `Provider` ABC plus a Railway plugin that wraps the `railway` CLI. Non-Railway providers (ssh, local) are explicit non-goals for this sprint.
- **Bundled templates**: `megaplan/cloud/templates/` ships `Dockerfile`, `entrypoint.sh.tmpl`, `healthserver.py`, `railway.toml.tmpl`, `cloud.yaml.tmpl`, and `chain.yaml.example`.
- **Extracted run wrappers**: `megaplan/cloud/wrappers/` ships `mp-run`, `mp-supervise`, `mp-heartbeat`, and `mp-chain` bash scripts, lifted out of the old entrypoint heredocs so they are versioned and editable.
- **`handle_init` strictness**: `--output` on a code-mode plan now raises `invalid_args` instead of being silently accepted. The only legitimate use of `--output` was a dropped `--mode doc` flag, which is now an explicit error.
- **Discoverability**: README gains a short "Cloud runs" section, `megaplan/data/instructions.md` gains a "Cloud Mode" block so the skill teaches Claude Code / Codex when to suggest `megaplan cloud`, and `.gitignore` now covers `.env` / `.env.*` / `*.env` since the cloud flow encourages `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GITHUB_TOKEN` secrets.
- **Out of scope for sprint 1**: ssh/local providers, `cloud init-plan` bootstrap, toolchain extensibility block, retiring the external reference folder. The existing `~/Documents/reigh-megaplan-dev/` keeps running unchanged.

### `--mode metaplan` alias for doc mode

- **CLI**: `megaplan init --mode metaplan` is now the preferred name for design/document runs. Internally it normalizes to `mode == "doc"`, so all existing state files, prompts, schemas, and downstream checks are untouched. `--mode doc` remains a valid alias.
- **Docs**: README section renamed to "Metaplan mode," with the defensive "Looking for metaplan/preplan?" subsection merged in now that metaplan is the real name. The SWE-bench Experiment section was dropped. Skill instructions updated to match.

### Doc-mode aggregator preserves executor output

- **Bug**: `assemble_doc` was overwriting the executor-authored output file with `executor_notes` (verification prose), so every doc-mode run ended with status-summary text instead of the intended deliverable. The executor is the authoritative author — the aggregator's only job is to fall back when the executor couldn't write to disk.
- **Fix**: `assemble_doc` now returns untouched if the output file exists with non-empty content. Empty or missing files still fall through to the degraded notes-based path; a docstring callout flags that its content is verification prose, not authored sections. Regression tests cover both branches.

### Misc

- Doc-mode / metaplan pointer landed pre-alias: README "Doc mode" section, `instructions.md` Modes block with a keyword-loaded "Looking for metaplan or preplan mode?" subsection, and `claude_subagent_appendix.md` note about the `--mode doc --output` flags the outer skill appends.
- README prose cleanup (light-megaplan run; no factual or code-example changes).
- License correction: README had claimed MIT; actual license per `LICENSE` and `pyproject.toml` is Open Source Native License (OSNL) 0.2.

## v0.18.1 — 2026-04-16

### Rework-cycle-aware stall detection in `megaplan auto`

Fixes a false-positive stall in the auto-driver when a plan is in a review→rework loop.

- **Bug**: `megaplan auto` counted iterations at the same `state` and bailed after `--stall-threshold` (default 5). When review returns `needs_rework`, state ping-pongs `finalized ↔ executed ↔ finalized` while execute re-runs batches. From the naive stall counter's view the plan looked "stuck at finalized for 5 iterations" even though new `review.json` / `execution.json` artifacts were being written and real progress was happening. Observed on plan `milestone-m1b-from-docs-state-20260416-1226` — 7 execute batches + 1 review cycle completed, driver exited rc=2.
- **Fix**: auto's driver loop now tracks `review.json` mtime as a forward-progress marker. When the marker advances, the stall counter resets and a rework-cycle counter increments. The new `--max-review-rework-cycles` flag (default 3, mirroring `execution.max_review_rework_cycles`) caps runaway rework loops independently of `--stall-threshold`.
- **Helpers**: `_resolve_plan_dir(plan, cwd)` walks up from cwd to find `.megaplan/plans/<plan>`, matching how `megaplan status` resolves plans. `_get_review_marker(plan_dir)` stats `review.json` and returns `None` for plans without a review artifact (e.g. light-robustness plans) — in that case the driver falls back to plain stall detection, preserving existing behavior.
- **CLI**: `--stall-threshold` help text updated to clarify that it fires only when state AND `review.json` are both unchanged. New `--max-review-rework-cycles` flag added with matching default.
- **Tests**: `tests/test_auto.py` (new file) covers stall reset on review-marker advance, rework cap enforcement, plain-stall fallback when no review.json exists, and the plan-dir resolver.
- **Scope**: auto.py driver loop only — execute and review phase logic are untouched.

## v0.18.0 — 2026-04-15

### Automated tiebreaker triggering

Gate-driven automatic tiebreaker routing with budgeted, audited guardrails. Builds on the advisory `megaplan tiebreaker` subcommand from v0.17.1 — the harness now detects recurring constraint tensions and routes to tiebreaker automatically.

- **Iteration-pressure analysis**: `megaplan/iteration_pressure.py` computes flag recurrence history — fuzzy-groups flags by Jaccard word similarity, tracks `addressed_then_reopened_count`, and renders a pressure table into the gate prompt context.
- **Mechanical recurrence validation**: harness validates TIEBREAKER recommendations against actual flag history via `_validate_tiebreaker`. Re-prompts the gate once if no mechanical signal exists; force-demotes to ITERATE on second failure.
- **`tiebreaker-run` top-level command**: auto-driver-callable command that invokes `_run_tiebreaker` inside a plan-locked context and transitions the plan state.
- **Gate integration**: `handle_gate` detects `TIEBREAKER` recommendations, runs the validator, transitions to `tiebreaker_pending` on approval.
- **Budget guardrails**: `max_tiebreakers_per_plan` (default 2). Exceeded budgets force-demote to ESCALATE.
- **Domain blocklist**: `tiebreaker_blocklist` config field skips tiebreaker for specified concern categories.
- **Spec-level opt-out**: `allow_tiebreaker: false` in config disables the mechanism entirely.
- **Audit tracking**: `megaplan/audit.py` records tiebreaker usage, timing, and token costs. `megaplan tiebreaker audit` CLI for per-plan and global stats. `handle_tiebreaker_decide` writes an audit record on every decision.
- **Auto driver**: `drive()` returns `status="awaiting_human"`, `"tiebreaker_pending"`, or `"tiebreaker_ready"` for the matching automation-terminal states and stops cleanly.
- **Gate prompt**: now includes the Iteration Pressure Analysis block; TIEBREAKER bullet explicitly cites `addressed_then_reopened_count` thresholds.

## v0.17.1 — 2026-04-15

### Tiebreaker subcommand (`megaplan tiebreaker`)

New advisory subcommand that produces structured decision context for architectural questions (e.g. when `gate` returns ESCALATE).

- **Two-agent pipeline**: a researcher agent gathers evidence and options, then a challenger agent stress-tests the findings — each in an independent ephemeral session.
- **CLI**: `megaplan tiebreaker --plan <name> --question "..."` (or `--question-file`), `megaplan tiebreaker status`, `megaplan tiebreaker decide --pick/--escalate/--replan --rationale`.
- **Structured artifacts**: `tiebreaker_researcher.json`, `tiebreaker_challenger.json`, and a synthesized `tiebreaker.md` with decision-ready sections (options table, evidence summary, agreement/disagreement, fallback plan).
- **Idempotent**: re-runs produce versioned artifacts (`_v2`, `_v3`, …).
- **Configurable agents**: `agents.tiebreaker_researcher` and `agents.tiebreaker_challenger` in config, defaulting to codex.
- **Gate schema**: `TIEBREAKER` added as fourth recommendation, with `tiebreaker_question`, `tiebreaker_flag_ids`, `tiebreaker_fuzzy_group_id` optional fields. Gate prompt documents the new option.
- **Plan lifecycle**: `tiebreaker_pending` / `tiebreaker_ready` states added with workflow transitions; both are automation-terminal.
- **Settled-decision immunity**: critique and revise prompts read `tiebreaker_decisions.json` and instruct agents not to re-raise settled concerns without materially new evidence.
- **Hot-fix**: `_run_tiebreaker` uses `WorkerResult.payload` instead of the nonexistent `.success`/`.parsed`/`.error` attributes — caught by live-cloud smoke run.

Automatic gate-driven tiebreaker routing (pressure analysis, budgeting, audit tracking) lands in v0.18.0.

## v0.17.0 — 2026-04-15

### Verifiability contracts

Success criteria now declare which capabilities are needed to verify them, enabling pre-critique auditing and human-deferred verification.

- **Capability registry**: closed set of 11 mechanism-shaped strings in `megaplan/capabilities.py` — 6 container (`run_shell`, `read_files`, `run_tests`, `parse_diff`, `read_build_output`, `run_linter`) and 5 human (`drive_browser`, `inspect_runtime_ui`, `observe_runtime_logs`, `subjective_judgment`, `verify_physical_device`).
- **`requires` field on success criteria**: optional `requires: [cap1, cap2]` on each criterion in plan/revise schemas. Defaults to `[]` for backward compatibility.
- **Pre-critique audit**: `megaplan/verifiability.py` validates that `requires` entries are known capabilities and that the union of worker capabilities can satisfy them. Synthetic `verifiability` flags are injected into the critique phase.
- **`deferred_human` verdict**: review criteria that require human-only capabilities are marked `deferred_human` instead of `fail` or `waived`.
- **`awaiting_human_verify` state**: plans with deferred human criteria enter this automation-terminal state instead of `done`.
- **`megaplan verify-human`**: CLI command to record human verification evidence and transition from `awaiting_human_verify` to `done`.
- **`megaplan audit-verifiability`**: CLI command to inspect capability coverage of a plan's criteria without changing state.
- **`megaplan status --pending-human`**: lists plans in `awaiting_human_verify` state.
- **Migration**: `requires` defaults to `[]` via schema default. Existing plans work unchanged.

## v0.16.0 — 2026-04-15

### Chain driver (`megaplan chain`)

New first-class subcommand that drives an ordered pipeline of milestone plans described by a YAML spec. Replaces ad-hoc bash orchestration (`chain.sh`) so plan-state logic lives in megaplan instead of fragile shell polling.

- **Spec-driven**: `megaplan chain --spec path/to/chain.yaml` reads milestones, optional seed plan, and failure/escalate policies from YAML.
- **Resumable**: progress is persisted to `chain_state.json` next to the spec (`current_milestone_index`, `current_plan_name`, `last_state`, `completed`). A relaunched process reads this file and picks up where the previous run stopped.
- **State-aware in the right layer**: each milestone is driven via the existing `megaplan.auto.drive` entry point, so phase selection (`plan → prep → critique → ... → review`) stays in megaplan. Shell wrappers no longer need to classify `next_step`.
- **`megaplan chain status --spec PATH`**: prints current chain progress without driving.
- **Failure/escalate policies**: `stop_chain` (default), `skip_milestone`, `retry_milestone`.
- **Seed handling**: if a seed plan is specified and not already in a terminal state, it is driven first under the same auto loop — fixing the gap where seed plans had no state-aware driver.
- **Validation**: up front, the chain driver checks every idea file exists and the seed plan (if set) resolves under the project root. Structured `invalid_spec` / `missing_idea_file` / `missing_seed_plan` errors.
- **`--no-git-refresh` flag**: suppresses the automatic `git checkout main && git pull` that runs before each milestone. Default: enabled (preserves existing CI/orchestrator behavior). Disable on developer checkouts where you do not want chain to stomp on the currently checked-out branch.
- **PyYAML** added as a runtime dependency.

### Tests

- `tests/test_chain.py` covers spec parsing, `chain status`, idea-file validation, seed-plan validation, happy-path execution (with `auto.drive` mocked), resume-from-`chain_state.json`, on-failure `stop_chain`, and `--no-git-refresh` suppression.

## v0.15.0 — 2026-04-15

### Doc mode

Megaplan can now run in `--mode doc`, letting execution produce a single document artifact instead of a code diff.

- `megaplan init` adds `--mode doc` and `--output <relative/path>` for document-targeted plans.
- Execute workers now support a doc-mode schema with `sections_written` instead of per-task file changes.
- Doc-mode prompt tracks reframe prep, execute, and review around authoring and document quality.
- Execution auditing can now reason about section-based delivery instead of only file-based changes.

## v0.14.6 — 2026-04-15

### Poisoned-session recovery

Fixes a class of infinite-loop failure where a persistent Codex/Claude session retained an obsolete "sandbox is broken" belief (e.g. an old `bwrap: Creating new namespace failed: Permission denied` line from before `MEGAPLAN_TRUSTED_CONTAINER=1` was wired up). On subsequent runs the model would read the stale history, refuse to execute, and return `status=blocked` — which megaplan then silently dropped as malformed, preventing any state progress and triggering supervisor restart loops.

- **Accept `status=blocked`**: `execution.py`, `execution_timeout.py`, and the execute/finalize JSON schemas now accept `blocked` as a valid task status. Blocked updates are merged and recorded instead of being silently discarded as malformed `task_updates`.
- **Detect poisoned sessions**: new `_is_poisoned_environmental_failure(raw)` helper matches known-stale sandbox error signatures. When it fires in `run_codex_step`/`run_claude_step` on a *resumed* session in *trusted-container* mode, megaplan drops the session id and recursively retries with `fresh=True`, mirroring the existing rollout-missing recovery from v0.14.3.
- **Surface blocked tasks**: the execute summary now lists blocked task IDs and emits a warning (`"N task(s) reported status=blocked by the worker — investigate executor_notes before continuing"`) so supervisors and humans see the real reason a batch did not advance instead of just `state=finalized`.
- **Status reports `tasks_blocked`**: CLI `status` output exposes `tasks_blocked` alongside `tasks_done` / `tasks_skipped` / `tasks_pending`.
- **Auto driver exits rc=5 on all-blocked stalls**: when `megaplan auto` detects a state-stall and every remaining task is `blocked` (no pending), it exits with status `blocked` / exit code 5 and a specific reason, distinct from generic `stalled=2` and `escalated=3`. Supervisors can treat this as a poisoned-worker signal and retry with `--fresh`.

## v0.14.5 — 2026-04-15

### Git-worktree isolation for subprocess workers

Fix: when megaplan invoked its `claude` / `codex` subprocess workers, it was passing the plan's stored `project_dir` as the `--add-dir` / `-C` target. Runs started from a git worktree would silently write source-code changes back into the main checkout, colliding with other concurrent runs.

- **CWD drives `--add-dir`**: `run_claude_step` now passes the CWD (or an explicit override) as `--add-dir` and subprocess cwd, instead of the plan's stored `project_dir`.
- **CWD drives Codex `-C`**: `run_codex_step` now passes the CWD as Codex's `-C` and as the `sandbox_workspace_write.writable_roots` entry. The `--add-dir` for Codex still points at the plan's artifacts directory (`plan_dir`), which is unchanged.
- **Plan state still lives at `project_dir`**: `.megaplan/plans/<name>/` artifacts remain co-located with the plan as before. Only the source-code working tree the worker sees has changed.
- **Divergence warning**: emits a one-time warning at startup when CWD differs from the plan's stored `project_dir`, so operators notice when a plan created in checkout A is being executed from worktree B.
- **`--work-dir PATH` flag**: every worker-invoking subcommand (`plan`, `prep`, `critique`, `revise`, `gate`, `finalize`, `execute`, `review`, `auto`, `loop-init`, `loop-run`) accepts `--work-dir` to explicitly override the detected CWD.

## v0.14.0 — 2026-04-15

### Strict gate flag resolution

The gate no longer silently accepts unresolved blocking flags on a PROCEED recommendation. PROCEED now requires explicit `flag_resolutions` for every blocking flag, and a retry is issued once when the first response still leaves blocking blockers unresolved.

- **No implicit acceptance**: unresolved blocking flags now trigger a single gate reprompt instead of being auto-marked as accepted tradeoffs.
- **Auto-downgrade on retry failure**: if the retry still leaves blocking flags unresolved, the gate artifact is rewritten as `ITERATE` with an auto-downgrade rationale note and `reprompted: true`.
- **Stricter tradeoff validation**: `accept_tradeoff` entries now require concrete, flag-specific rationale; rubber-stamp phrases are rejected the same way weak dispute evidence is rejected.
- **Debt derived from explicit resolutions**: accepted tradeoff debt entries now come from validated `flag_resolutions` rather than fallback unresolved-flag recording.
- **Gate test coverage refreshed**: existing gate debt tests now follow the strict-resolution contract, and new tests cover reprompt success, reprompt downgrade, rubber-stamp rejection, no-reprompt happy path, and resolution-derived debt recording.

## v0.12.0 — 2026-04-15

### Auto driver

New `megaplan auto --plan <name>` drives a plan from its current state to a terminal outcome without human intervention. The driver is intentionally dumb: it reads `status`, runs `next_step`, and loops. All real judgment stays in the phase logic.

- **Gate escalation policy**: ESCALATE defaults to force-proceed. Opt out with `--on-escalate abort` or `--on-escalate fail`.
- **Stall detection**: bails after N consecutive iterations in the same state (default 5).
- **Iteration cap**: hard stop at 200 iterations by default to bound runaway loops.
- **Structured exit codes**: `done=0`, `failed=1`, `stalled=2`, `escalated=3`, `cap=4` — so shell callers and CI can branch on terminal state without parsing output.
- Emits a JSON outcome with the final state snapshot and event log on exit.

### Cross-directory plan discovery

`resolve_plan_dir` now walks both parent and child directories to locate plans by name, so megaplan commands work from anywhere in a project tree — not just the directory containing `.megaplan/`.

- **`megaplan list --tree`**: list plans in the current subtree.
- **`megaplan list --all`**: system-wide plan discovery across the whole workspace.

### Standard robustness: init→plan transition

The `standard` robustness profile now picks up the init→plan transition that was previously only wired under heavier levels. Standard plans no longer stall after init waiting for a transition that never fires.

### Tests

Added `test_auto` coverage for the driver loop, escalation policies, stall detection, and iteration caps.

## v0.10.0 — 2026-04-10

### Codex backend hardening

The Codex (OpenAI) worker path got a major reliability overhaul, fixing a class of issues that caused silent failures, misclassified errors, and lost output when running with `--agent codex` or Hermes.

- **Timeout recovery**: when a Codex step times out, megaplan now attempts to recover partial output from the output file and stdout before raising. If valid structured output was produced before the timeout, the step succeeds instead of failing.
- **Per-step timeout caps**: non-execute steps (plan, critique, revise, etc.) are capped at 300s instead of inheriting the full 7200s worker timeout. Execute steps keep the full timeout.
- **Environment isolation**: child Codex processes no longer inherit `CODEX_THREAD_ID` or `CODEX_CI` from the parent, preventing workers from attaching to the wrong session.
- **Error classifier rewrite**: connection-level failures (DNS, WebSocket, stream disconnect) are now detected before HTTP status codes, fixing false positives where thread IDs or unrelated numbers were misclassified as 429s. Bare numeric patterns (`429`, `500`, etc.) now use word-boundary regex.
- **JSON extraction rewrite**: switched from greedy brace-matching to `JSONDecoder.raw_decode()`, which correctly handles trailing logs/traces after the JSON object.
- **Merged partial output**: timeout and crash error payloads now include both stderr/stdout and any file the worker managed to write, giving better diagnostics.

### Concurrency & observability

- **Plan locking**: all step handlers now acquire an `fcntl` file lock, preventing two processes from running steps on the same plan concurrently. Collisions produce a clear error naming the active step and agent.
- **Active step tracking**: `state.json` now carries an `active_step` field (`step`, `agent`, `mode`, `run_id`, `started_at`) set before the worker launches and cleared on completion or failure. Stale detection at 300s.
- **`megaplan status`**: now returns `active_step`, `last_step`, `total_cost_usd`, notes, and session summaries — everything the orchestrator needs without reading raw state.
- **`megaplan watch`**: new command combining `status` + `progress` into a single response for real-time monitoring.

### Tiny robustness level

New `--robustness tiny` mode stubs the critique and gate steps entirely, going straight from `plan` to `gated` to `finalize`. Useful for trivial tasks where the full critique loop is overhead.

### Parallel review for heavy mode

Heavy robustness now runs review checks in parallel (same pattern as parallel critique), splitting mechanical checks, sense checks, and task verification across concurrent workers.

### OpenAI strict-mode schema compatibility

- Recursive `required` reconciliation: all schema properties are now added to `required` arrays to satisfy OpenAI's structured output constraint that every property must be required.
- `flag_id` and `source` in review rework items changed from optional strings to required nullable (`["string", "null"]`).
- Gate `flag_resolutions` entries now require both `evidence` and `rationale` fields (use `""` for the one that doesn't apply).
- `accepted_tradeoffs` is now always returned (use `[]` when empty).

### Prompt improvements

- **Nested harness guard**: all worker prompts now include a preamble preventing the model from recursively invoking the `megaplan` CLI or skill.
- **Plan focus guidance**: planning prompt now tells the model to stop exploring once it has enough evidence, and to avoid `.megaplan/`, prior plan artifacts, and unrelated docs.
- **Standard robustness now includes prep**: removed the override that skipped the prep phase for standard robustness. All levels now run prep.

### Other

- License changed to OSNL 0.2.
- README updated: robustness level descriptions, observability section rewritten for `status`/`watch`.
- Comprehensive new test suites: `test_handle_review_robustness`, `test_parallel_review`, `test_review_checks`, `test_review_mechanical`, `test_tiny_robustness`, `test_config`, `test_io_git_patch`.
