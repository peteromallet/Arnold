# Megaplan Live Watchdog Supervisor

## Outcome

Build an MVP that keeps track of likely-live Megaplan/Arnold runs on this machine, classifies their health, and uses an Arnold pipeline to handle problem incidents with bounded repair/relaunch/recheck loops.

The finished system should let a user run an hourly watchdog that discovers active-ish `.megaplan` plans and chains across normal repos, worktrees, and temp folders; records what it saw; identifies likely live runs; categorizes issues; dispatches repair subagents for problem cases; attempts safe relaunch/resume; waits five minutes; rechecks; and retries up to three times before marking the incident unresolved.

## Scope In

- Add a small watchdog entry point, likely under `scripts/` or an Arnold/Megaplan CLI-adjacent module, that can be run manually and later from `launchd`.
- Discover candidate plans by scanning for `.megaplan/plans/*/state.json` under at least:
  - `~/Documents`
  - `~/Documents/.megaplan-worktrees`
  - `~/.megaplan-worktrees`
  - `/tmp`
  - `/private/tmp`
- Discover likely live processes by inspecting `ps` output for Megaplan/Arnold/Shannon/Codex/Claude process signatures.
- Discover tmux sessions relevant to Shannon or chain runners where possible.
- Correlate process lines to plan names, plan directories, repo paths, and chain specs.
- Record a durable registry of seen plans/chains/incidents. SQLite is preferred if it stays simple; JSON/NDJSON is acceptable for MVP if the code is clearer.
- Produce a current report artifact listing:
  - likely live runs
  - recently active runs
  - stale non-terminal runs
  - problem candidates
  - actions attempted
  - retry counts
- Add an Arnold pipeline, tentatively named `megaplan_supervisor`, for incident handling. It should accept a JSON snapshot or incident bundle and produce structured classification and action results.
- Use Arnold primitives where they fit:
  - deterministic stages for enrich/classify
  - `ParallelStage` for per-incident diagnosis/repair fanout if practical
  - structured `StepResult` / artifact outputs for reports
- Define health categories:
  - `all_good`
  - `false_stall`
  - `harness_issue`
  - `plan_issue`
  - `environment_issue`
  - `dead_or_disappeared`
  - `unknown`
- Implement the repair policy with an explicit allowlist. Safe commands may include read-only inspections, `introspect`, `trace`, `doctor`, `resume`, `auto`, and chain `status` / `start --one --no-git-refresh --no-push` when enough context is present.
- Dispatch subagents only for problem candidates. The subagent prompt must be self-contained and bounded, and the returned result must be structured enough for the supervisor to decide whether an action is safe.
- Implement a three-attempt loop per incident:
  - diagnose
  - fix or run allowed command
  - relaunch/resume if appropriate
  - wait five minutes
  - recheck
  - repeat up to three total attempts
- Add tests for scanner parsing, classification, registry updates, action allowlist enforcement, and retry-loop behavior without launching real long-running agents.
- Document how to run the watchdog manually and how it should be scheduled hourly later.

## Scope Out

- Do not automatically force human gates or verification requirements.
- Do not run destructive git commands such as reset/checkout against user work.
- Do not push, merge, delete worktrees, or delete plan directories.
- Do not spend cloud resources or start remote runners automatically.
- Do not build a full UI.
- Do not require every historical stale plan on the machine to be cleaned up.
- Do not make the hourly scheduler itself an Arnold pipeline. The scheduler/registry loop should stay a thin operational script; the Arnold pipeline handles bounded incidents.

## Locked Decisions

- The hourly/global inventory loop and durable registry live outside the Arnold pipeline primitive.
- The Arnold pipeline is the incident-handling primitive: observe, classify, fan out diagnosis/repair, relaunch, recheck, and report.
- A direct process match is the strongest live signal. Recent `state.json` or `events.ndjson` writes without a process are only `recent` or `maybe_live`.
- Repair must be policy-gated. Subagents recommend fixes; the supervisor only executes allowlisted commands or code edits under explicitly safe conditions.
- Three attempts is the hard retry cap for one incident before marking it unresolved.
- The five-minute wait happens after a repair/relaunch attempt before rechecking liveness.

## Open Questions For The Planner

- Whether the first implementation should persist registry state in SQLite or a simple JSON/NDJSON directory.
- The exact package location for the watchdog and `megaplan_supervisor` pipeline within the current Arnold/Megaplan layout.
- Whether subagent dispatch should initially call the existing Hermes/Codex adapters, shell out to known launchers, or be abstracted behind a testable repair-agent interface with a fake implementation.
- Whether the five-minute wait belongs inside the Arnold pipeline step or in the outer daemon while the pipeline emits a resumable/check-later state.

## Constraints

- Must work when the installed `megaplan` CLI is broken by a local checkout shadowing issue; direct filesystem/process scanning should still work.
- Must avoid false positives from broad repo-path matches. Process-to-plan correlation should prefer exact plan name, exact plan dir, or explicit chain state current-plan fields.
- Must not require network access for discovery/classification tests.
- Must keep test fixtures small and deterministic.
- Must degrade to report-only when repair-agent credentials or model launchers are unavailable.

## Done Criteria

- A manual command can scan the machine and print/write a report of likely live Megaplan/Arnold runs.
- The scanner finds non-terminal `.megaplan` plans across worktrees and temp directories.
- The classifier distinguishes live, recent/maybe-live, stale, blocked, failed, disappeared, harness-suspect, and unknown cases.
- The registry remembers previously seen runs and can mark disappeared or terminal runs on a later scan.
- The Arnold supervisor pipeline can consume a snapshot with at least one problem incident and produce a structured action report.
- The retry loop is covered by tests and caps at three attempts.
- The action allowlist is covered by tests and blocks destructive commands.
- Documentation includes manual usage and an example hourly scheduling command or `launchd` note.

## Touchpoints

- `arnold/pipeline/` primitives for pipeline wiring, `Stage`, `ParallelStage`, `StepResult`, and artifacts.
- `arnold/pipelines/` for adding the supervisor pipeline package.
- Existing Megaplan observability surfaces: `introspect`, `trace`, `doctor`, `chain status`.
- Existing process/runtime code around Shannon, Codex, Hermes, and Arnold/Megaplan chain runners.
- `scripts/` for the watchdog CLI if that matches local conventions.
- Tests under `tests/` or `tests/arnold/` matching the repository's current layout.

## Prep Direction

Focus prep on the current Arnold pipeline primitive, package conventions under `arnold/pipelines/`, existing Megaplan observability APIs, and safe process/state correlation. Do not spend prep time designing a UI or cloud runner integration.

## Run Dials

Overall plan difficulty: 4/5; selected profile: `partnered-4`; because the planning risk is cross-system orchestration and safe repair boundaries across Arnold pipelines, Megaplan state, process liveness, and subagent dispatch.

Planning complexity: `full`; because this is real engineering work with safety policy and tests, but not a production data migration or public API contract change requiring `thorough`.

Depth: `high`; because the planner needs to reason across the current pipeline primitive, Megaplan observability, process supervision, and daemon/pipeline boundary.
