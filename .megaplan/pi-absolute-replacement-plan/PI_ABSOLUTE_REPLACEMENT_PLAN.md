# Unified Agent Surface Plan

Reconstructed: 2026-07-04  
Original discussion: 2026-06-27 Codex session `019f09da-0bca-7822-b7c0-bf30a626355b`  
Original target path: `/Users/peteromalley/Documents/Arnold/.megaplan/pi-absolute-replacement-plan/PI_ABSOLUTE_REPLACEMENT_PLAN.md`
Updated: 2026-07-04 to preserve `claude -p` and Codex as maintained engines
behind the same agent-control surface.
Updated: 2026-07-04 to retire Shannon entirely in favor of the maintained
`claude -p` engine adapter behind that surface.
Updated: 2026-07-04 after oracle review: split the work into independently
shippable migrations, with a thin recording/control facade first and deletion
per path only after evidence-backed gates.

## Reconstruction Note

This document reconstructs the missing plan from the surviving conversation
transcript and the surviving VibeComfy draft:

- `/Users/peteromalley/.codex/sessions/2026/06/27/rollout-2026-06-27T18-11-52-019f09da-0bca-7822-b7c0-bf30a626355b.jsonl`
- `/Users/peteromalley/Documents/reigh-workspace/vibecomfy/docs/Arnold/pi-agent-migration-breakdown.md`

It is not byte-for-byte the vanished file. It preserves the remembered decision,
end state, package strategy, risk model, hard gates, and sequencing from the
conversation.

For presenting this plan to a frontier/oracle model with no Arnold codebase
context, use the self-contained review fork:

- `ORACLE_REVIEW_PACKET.md`
- `ORACLE_DECISION.md`
- `FINAL_UNIFIED_AGENT_SURFACE_PLAN.md`

That packet includes the plan, the current-system context the oracle would
otherwise lack, the main risks surfaced by the DeepSeek/Codex sense-checks, and
the ten questions the oracle should answer to validate, refute, resequence, or
split the direction.

The oracle verdict was: **split into smaller migrations with a mandated
sequence**. The direction survives review; the original monolithic execution
shape does not. The facade ships first as a thin recording/control wrapper
around existing launchers. Runtime replacement, fanout deletion, Shannon
retirement, Codex governance, and security hardening then proceed as separately
gated tracks.

The final integrated plan is now captured in
`FINAL_UNIFIED_AGENT_SURFACE_PLAN.md`. This reconstructed plan remains as the
historical/source plan.

## Superseding Update: One Surface, Multiple Engines

The reconstructed original emphasized "absolute replacement" of all old launch
systems. The current target is more precise:

- Maintain Pi as the primary native runtime and extension substrate.
- Maintain `claude -p` for Claude-native execution.
- Maintain Codex for OpenAI/Codex-native execution, review, and apply where it
  remains the best tool.
- Route all of them through the same Arnold/Megaplan agent-control surface.
- Replace Shannon entirely with the `claude -p` engine adapter. Shannon names,
  fields, and channels may exist only as transitional compatibility inputs or
  historical metadata until they are migrated away.

The clean break is no longer "delete every non-Pi engine." It is:

> no caller-specific launch paths, no unmanaged ad hoc subprocesses, and no
> hidden runtime behavior outside the shared surface.

Pi, `claude -p`, and Codex can survive as engines. Shannon must not survive as
an engine, worker channel, adapter, or separate integration contract.

## Executive Summary

We want a literal, end-to-end replacement of the current fragmented
Arnold/Megaplan agent launching stack with a unified agent-control surface. The
target is not a world where every caller individually shells out to Hermes,
Codex, Claude, Pi, or the old DeepSeek fanout launcher. The final state is a
clean shared control plane that provides launch, fanout, review, apply, web,
browser, structured-output, observability, cost, history, timeout, and kill
semantics consistently across supported engines.

The key correction from the conversation was:

> Replace absolutely everything.

That superseded the earlier pragmatic hybrid recommendation at the time. The
current refinement is: replace every unmanaged launch path, but keep strong
native engines such as Pi, `claude -p`, and Codex when they are routed through
the shared surface.

Expected scale: 12-20 weeks. This is a runtime replacement project, not a thin
subprocess wrapper.

The revised execution rule is: do not treat 12-20 weeks as one cutover. Ship
each migration independently and make each legacy-path deletion its own tested
event with a deadline.

## Final End State

All agent work in Arnold/Megaplan routes through one shared surface:

```text
Arnold / Megaplan callers
  -> agent-control facade
      -> shared policy, profiles, artifacts, telemetry, kill/control, history
          -> Pi engine
          -> claude -p engine, replacing Shannon
          -> Codex engine
          -> other approved provider-native engines
          -> structured artifacts, telemetry, history, cost, kill/control events
```

The final runtime exposes at least:

- `agent launch`
- `agent fan`
- `agent kill`
- `agent review`
- `agent apply`
- `agent web`
- `agent browser`
- `agent history`
- `agent replay`
- `agent doctor`
- `agent bakeoff`

Names may still be implemented under `pi-agent` if that is the chosen package
name, but the contract is engine-neutral.

The final runtime owns:

- model aliasing and provider resolution
- agent profile discovery and namespacing
- tool permission policy
- structured output validation
- timeout and process-tree kill behavior
- high-N fanout
- worktree isolation
- retry and fallback classification
- JSON/NDJSON output contracts
- cost and token telemetry
- history search and replay
- subagent depth, budget, and concurrency limits
- install/update policy for vendored Pi extensions
- engine adapters for Pi, Claude, Codex, and other approved native engines

## Forbidden Final Launch Patterns

These may be used only as temporary comparison oracles during development. They
must not remain in final production launch paths:

- `fan.py`
- `fan_process.py`
- `fan_kill.py`
- `launch_hermes_agent.py`
- `launch_claude_agent.py`
- `shannon.py` or `shannon_stream.py` as production worker routes
- `shannon_tmux`, `shannon_stream`, or any Shannon worker-channel selection
- `run_shannon_step` / `run_shannon_stream_step` as production dispatch targets
- `arnold_pipelines.megaplan.agent_adapters.shannon` as a maintained adapter
- `megaplan/vendor/shannon/index.ts` as a runtime dependency
- direct caller-level `codex exec`
- direct caller-level `codex exec review`
- direct caller-level `codex apply`
- direct caller-level Claude CLI subprocess launching
- direct caller-level `claude -p`
- Claude Code Agent tool as a runtime dependency
- Hermes `AIAgent`
- active reads from `~/.hermes/.env`
- `PYENV_VERSION=3.11.11` as a required launch mechanism
- `@mariozechner/pi-*` packages as final dependency names
- `@oh-my-pi/*` packages as final dependency names

Allowed final patterns:

- `agent-control -> Pi adapter -> Pi runtime`
- `agent-control -> Claude adapter -> claude -p`, including legacy requests
  that previously selected Shannon
- `agent-control -> Codex adapter -> Codex runtime`
- `agent-control -> approved provider adapter -> provider-native runtime`

External model providers and approved native engines are allowed. Bypassing the
shared launch surface is not. Shannon is not an approved native engine in the
final state.

## What Pi Gives Us

Pi already provides a useful substrate:

- markdown/frontmatter-defined agents
- a coding-agent runtime with core file and shell tools
- extension mechanisms for tools, commands, hooks, UI, and workflows
- provider/model configuration
- JSON-mode subprocess execution
- examples for subagents, sandboxing, permissions, and tool extension

The original research also found that Oh My Pi is a deep fork rather than a
thin extension bundle. It is useful as a pattern library, not as the base.
Trying to trim OMP down to Pi would be a maintenance project in itself.

Therefore:

- Start from Pi, not Oh My Pi.
- Vendor/adapt small Pi ecosystem pieces.
- Normalize them behind our own `pi-agent` contract.
- Do not rely on OMP package names or OMP runtime surfaces in the end state.

## Ecosystem Pieces To Mine

The conversation identified these as useful source material:

| Need | Best source material | Use |
| --- | --- | --- |
| Patch application | `code-yeongyu/pi-apply-patch`, `gturkoglu/pi-codex-apply-patch` | Codex-style safe patch/edit semantics |
| Subagents | `nicobailon/pi-subagents`, `tintinweb/pi-subagents`, `hazat/pi-interactive-subagents` | Agent profiles, parallel/chain execution, structured outputs, history |
| Worktrees | `pasky/pi-side-agents`, `@zenobius/pi-worktrees` | Worker isolation and collision avoidance |
| Web/search | `nicobailon/pi-web-access`, `code-yeongyu/pi-websearch` | Search, fetch, extraction, source/citation plumbing |
| Browser | `coctostan/pi-agent-browser`, `fitchmultz/pi-agent-browser-native`, `narumiruna/pi-extensions` | CDP/browser automation |
| Review loops | `earendil-works/pi-review`, `nicobailon/pi-review-loop`, `zeflq/pi-reviewer` | Codex-review replacement patterns |
| Sandboxing | Pi sandbox example, `carderne/pi-sandbox` | Tool permission and shell containment |
| Durable state | `pi-crew` | Locks, stale-run recovery, persisted task state |
| Tool/task semantics | Oh My Pi | Task depth, schema validation, memory, task policy inspiration only |

None of these is accepted wholesale. Each must be classified:

- `use-as-is`: rare, only if contract and supply-chain posture are acceptable.
- `vendor/adapt`: preferred for concrete, compact implementation patterns.
- `inspiration-only`: use concepts, rewrite implementation.
- `reject`: too broad, too coupled, insecure, or conflicting with final runtime.

## Required Feature Parity

### 1. Launcher Contract

The old launcher contract includes behavior spread across Hermes, DeepSeek
fanout, Codex, Claude, Shannon, Megaplan profiles, shell scripts, and skills.

The shared surface must support:

- inline query and query-file launch
- project directory / cwd selection
- read-only, write-capable, and terminal-capable toolsets
- model alias resolution
- provider selection
- max-token/output cap handling
- timeout handling
- structured stdout/stderr behavior
- artifact output directory
- `.txt`, `.meta.json`, `.error.txt`, and `_report.json` artifacts
- deterministic exit codes
- deterministic machine-readable error codes
- progress heartbeat
- parent abort propagation
- parent-child task lineage
- token/cost/duration telemetry
- partial-result capture on timeout/failure
- compatibility mapping for legacy `agent=shannon`, `worker_channel=shannon_*`,
  and `shannon_plan` artifacts during the migration window

### 2. Agent Profiles

Profiles must replace hardcoded launcher behavior.

Required profile fields:

```yaml
name: scout
description: Read-only codebase scout
model: deepseek-v4-pro
tools: [read, grep, find, ls, web]
timeout_seconds: 1800
max_output_chars: 40000
cwd_policy: project
sandbox: read_only
schema: optional-json-schema-ref
worktree: none
history: persist
cost_budget_usd: optional
```

Canonical first profiles:

- `scout`: read-only repo/context research.
- `planner`: plan synthesis and decomposition.
- `worker`: write-capable implementation in isolated worktree.
- `reviewer`: independent code review.
- `judge`: rubric-based gate/review.
- `web-researcher`: web/search/fetch with citations.
- `browser-agent`: browser/CDP verification.
- `patcher`: safe patch application.
- `red-team`: adversarial failure-mode finder.

Avoid proliferating dozens of profile names until the core runtime is stable.

### 3. High-N Fanout

This is the hardest gap.

Current `fan.py` can run large DeepSeek panels efficiently because it imports
the agent runtime once and fans work out through threads. Existing Pi subagent
packages are mostly process/session-per-agent and do not solve N=50/N=100
memory efficiency.

The final state still forbids `fan.py`. Therefore we must build a Pi-native
high-N backend.

Required behavior:

- N=50 normal research fanout
- N=100 stress target
- max concurrency control
- per-task timeout
- group/global timeout
- output directory contract
- `_report.json` summary
- `.meta.json` per task
- partial results on timeout
- external kill by run id
- no unbounded stderr/stdout buffers
- bounded memory growth
- retry classification
- deterministic task ids
- stable ordering in reports
- resume/reconcile stale runs

Implementation options to spike:

- shared Pi worker pool with one runtime process hosting multiple agent tasks
- warm reusable Pi processes with strict per-task cleanup
- broker process that multiplexes isolated sessions
- process pool with aggressive output caps and memory ceilings
- hybrid execution internally, but still owned by the shared surface and not
  Python `fan.py`

The migration fails if final high-N paths still call `fan.py`.

### 4. Review And Apply

Codex-style review/apply behavior must move behind the shared surface. Codex may
remain the execution engine for these paths if the shared surface owns policy,
artifacts, telemetry, failure handling, and output normalization.

Required review features:

- diff-aware code review
- severity-ordered findings
- file/line references
- no issues found path
- test-gap reporting
- PR/comment-ready output
- repository context gathering
- configurable rubric
- output as Markdown and structured JSON

Required apply features:

- atomic patch application
- workspace containment
- conflict detection
- dry-run mode
- patch preview
- clear failure diagnostics
- file allow/deny lists
- rollback or non-destructive failure
- integration with worktree worker mode

Good starting points: Codex itself as a maintained engine, plus
`pi-apply-patch`, `pi-codex-apply-patch`, `pi-review`, `pi-reviewer`, and
`pi-review-loop` as source material for parity and fallback design.

### 5. Web, Browser, And External Tools

Pi needs first-class support for:

- web search
- page fetch
- PDF/text extraction
- GitHub file/source fetch
- citations/source metadata
- SSRF and local-network protection
- browser/CDP navigation
- screenshots
- local localhost verification
- headless test execution

Use `pi-web-access` / `pi-websearch` and browser extensions as source material,
but normalize output and permissions behind `pi-agent`.

### 6. Worktree Isolation

Write-capable agents must not collide with the main checkout or each other.

Required modes:

- `none`: same checkout, read-only only by default.
- `temp-worktree`: isolated temporary worktree, cleaned on success or retained on failure.
- `named-worktree`: durable worktree for long-running implementation.
- `branch-worktree`: create/update a branch for the agent.
- `readonly-snapshot`: copy or archive for audit/review.

Required behavior:

- carry or reject dirty worktree intentionally
- preserve source checkout unchanged
- record branch/base/head metadata
- collect diff after run
- expose worktree path in meta
- support explicit cleanup
- refuse dangerous deletes outside worktree

### 7. Structured Output

Many Megaplan phases depend on machine-readable JSON.

Required behavior:

- JSON schema validation
- JSON repair only where explicitly allowed
- provenance for repaired output
- raw output preservation
- schema-shaped default prevention unless policy allows it
- clear `schema_validation_failed` error
- support for final text plus JSON artifact
- compatibility with phase-specific output shapes

### 8. Timeout, Kill, And Stale Recovery

Pi must own lifecycle control.

Required behavior:

- per-task timeout
- group timeout
- idle timeout
- SIGTERM then SIGKILL cascade
- process-tree cleanup
- orphan detection
- stale lock/run reconciliation
- best-effort control inbox
- external `pi-agent kill <run-id>`
- partial artifact capture before kill
- no silent hangs

### 9. Telemetry, History, Cost

Every run should produce:

- run id
- parent run id
- task id
- agent/profile
- provider/model
- cwd/worktree
- start/end/duration
- time to first output where available
- token usage if available
- cost if available
- tool calls count
- exit code
- error code
- retry/fallback events
- artifact paths
- final status

History must be searchable by:

- cwd
- profile
- model
- error code
- date range
- parent run
- brief/task id
- text query

### 10. Security And Supply Chain

Security must be designed into the runtime, not bolted on later.

Required controls:

- extension allowlist
- pinned package versions or vendored source
- no arbitrary remote extension install in production
- tool permissions per profile
- cwd and writable-root enforcement
- env inheritance policy
- secret redaction in logs/artifacts
- network access policy
- browser sandbox policy
- shell command audit
- supply-chain review for vendored Pi packages

## Architecture

### Runtime Layers

```text
Layer 0: Existing Arnold/Megaplan callers
  - megaplan phases
  - skills
  - cloud wrappers
  - review/fix workflows
  - subagent-launcher replacement callers

Layer 1: agent-control facade
  - stable CLI/API
  - output contract
  - error taxonomy
  - profile resolution
  - run id generation

Layer 2: shared control plane
  - launch scheduler
  - fan scheduler
  - worktree manager
  - kill/control manager
  - telemetry/history writer
  - artifact writer

Layer 3: execution engines
  - single-agent subprocess engine
  - pooled high-N fanout engine
  - review engine
  - apply/patch engine
  - web/browser engines
  - claude -p engine adapter
  - Codex engine adapter
  - no Shannon engine; legacy Shannon inputs are translated before dispatch

Layer 4: ecosystem modules
  - vendored/adapted subagent packages
  - web/search packages
  - apply-patch packages
  - browser/CDP packages
  - sandbox packages
  - Claude/Codex adapter modules
```

### Compatibility During Migration

The facade should initially mimic enough old flags to enable mechanical caller
migration:

```bash
agent launch \
  --agent scout \
  --engine pi \
  --model deepseek:deepseek-v4-pro \
  --query-file brief.md \
  --project-dir "$PWD" \
  --toolsets file,web,terminal \
  --timeout 1800 \
  --output-dir results
```

This compatibility is transitional. The internal execution must be owned by the
shared surface and routed through approved engine adapters. Old launchers can be
invoked only by explicit bakeoff/oracle commands:

```bash
agent bakeoff --old hermes --new shared --briefs-dir briefs --output-dir comparison
```

The bakeoff command may call old launchers until cutover; production launch
commands may not.

### Shannon Retirement Requirements

Shannon is replaced by the `claude -p` adapter, not wrapped indefinitely.

Required retirement work:

- Inventory `shannon.py`, `shannon_stream.py`, `shannon_session.py`,
  `agent_adapters/shannon.py`, `megaplan/vendor/shannon/index.ts`,
  `shannon_plan`, `shannon_run_nonces`, `worker_channel=shannon_tmux`, and
  `worker_channel=shannon_stream`.
- Preserve the real behavior that mattered: Claude prompt projection, session
  identity, transcript capture, stream-json parsing, liveness classification,
  timeout handling, retryability, cost/tokens, permission policy, and artifact
  shape.
- Implement that behavior in the shared Claude adapter around `claude -p`.
- Map legacy `agent=shannon` and old Shannon channel specs to the Claude
  adapter during the migration window, with telemetry that makes the legacy
  input visible.
- Treat `shannon_plan` as opaque historical metadata only. New runs should emit
  engine-neutral metadata such as `engine_plan` or a Claude-specific field
  owned by the new adapter.
- Update bakeoff/channel-shadow tests to compare old Shannon only as an oracle,
  not as a candidate production route.
- Remove Shannon availability checks, vendored Shannon runtime dependencies,
  Shannon worker-channel switches, and Shannon adapter registration before the
  final cutover gate.
- Final behavior for explicit Shannon requests should be either a compatibility
  alias resolved before dispatch or a clear deprecation error. It must not call
  a Shannon worker.

## Split Migration Plan

Oracle verdict: split into smaller migrations with a mandated sequence.

The revised plan is not "execute the monolith." It is also not a retreat from
the final state. The change is that each migration must be independently
shippable and independently abortable:

- observability/data contracts
- fanout runtime
- Shannon stream retirement
- Shannon tmux disposition
- Codex governance
- security policy and enforcement
- deletion/bakeoff

The decisive structural change is that the facade ships first as a thin
recording/control wrapper around existing launchers, before replacing runtimes.
It must collect the evidence that later deletion gates depend on.

### M0: Evidence And Contracts

Goal: define and measure the old world before changing it.

Tasks:

- Inventory all current launch paths.
- Capture CLI flags for Hermes, fan, Shannon, Claude, Codex, and Megaplan
  worker phases.
- Capture artifact contracts, exit codes, failure modes, timeout behavior,
  model/provider resolution, and toolset behavior.
- Capture Shannon-specific behavior from tmux and stream channels:
  `shannon_plan`, transcript roots, session identity, liveness probes,
  auth-channel metadata, and `worker_channel` routing.
- Build real-brief, failing-brief, review/apply, browser/web, worktree, and
  high-N fanout corpora.
- Measure `fan.py` baselines at N=8, N=32, N=50, and N=100: memory, p50/p95
  latency, orphan rate, success rate, cost, artifact size, and timeout behavior.
- Measure Shannon channel usage: tmux vs stream, workloads, failure modes,
  session reuse, and long-idle tool-call behavior.
- Draft all run/task/artifact/error/cost/history schemas before implementation.
- Draft the Shannon behavior depth audit with every row classified.

Deliverables:

- `current-launcher-inventory.md`
- `old-launch-contract.md`
- `old-artifact-contract.md`
- `old-error-taxonomy.md`
- `shannon-behavior-depth-audit.md`
- `engine-adapter-contract.md`
- `run-record.schema.json`
- `artifact-manifest.schema.json`
- `engine-plan.schema.json`
- `legacy-route.schema.json`
- `error-taxonomy.schema.json`
- `fanout-baseline-report.md`
- `security-threat-model.md`
- `evaluation-protocol.md`
- `operational-prerequisites.md`
- `task-corpus/`
- `failure-corpus/`

Hard gate:

- Executable conformance tests exist and pass against the current system.
- No Shannon audit row remains `unknown`.
- No runtime replacement work begins before this gate passes.

### M1: Thin Facade, Recording First

Goal: ship the shared surface without changing runtime behavior.

Tasks:

- Implement `agent ask`, `agent launch`, `agent kill`, `agent history`, and
  `agent doctor`.
- Delegate to existing launchers unchanged behind the facade.
- Produce uniform run records, artifact manifests, telemetry events, cost
  events, lineage records, and error taxonomy mappings.
- Start credential mediation: provider keys are supplied by the facade rather
  than ambient shell inheritance where feasible.
- Add profile discovery: `agent profiles` and `agent profile show <name>`.
- Add zero-friction ad-hoc usage: `agent ask "..."` must be competitive with
  direct `claude -p`.
- Add fake-provider and wrapped-launcher tests.
- Add seeded failure diagnosis tests: a failed run must be diagnosable from
  facade artifacts alone.

Hard gate:

- Facade adoption reaches the agreed target for newly touched workflows.
- `agent ask` overhead is within the agreed budget versus direct `claude -p`
  (target: about one second or better unless M0 proves another budget).
- Existing launch behavior remains unchanged except for added recording/control.
- Seeded failure can be diagnosed without raw process logs.

### M2: Fanout Spike And Pooled Adapter Track

Goal: decide whether `fan.py` can be absorbed or replaced without regression.

Tasks:

- Treat the valuable `fan.py` mechanism as import-once pooled execution
  internals, not as an allowed caller-facing path.
- Build a facade-owned `agent fan` spike with admission control, run manifest,
  scheduler crash recovery, external kill, partial-result contract, rate-limit
  backpressure, straggler policy, and orphan audit.
- Test pooled adapter options: existing fan internals, process pool, broker,
  daemon, or Pi-backed pool.
- Benchmark N=8, N=32, N=50, and N=100 against M0 baseline.
- Measure memory, p50/p95 latency, success rate, cost, FD growth, artifact
  completeness, kill latency, and orphan process count.

Hard gate:

- N=50 is parity-or-better versus `fan.py` on memory, p95 latency, success
  rate, and orphan rate before any commitment to delete `fan.py`.
- Spike failure aborts or redesigns only the fanout track; it does not block
  M3-M5.

### M3: `claude -p` Adapter And Stream-Shannon Retirement

Goal: retire the stream-like Shannon route first, without pretending tmux
Shannon is already solved.

Tasks:

- Implement the Claude adapter around `claude -p`.
- Replace the `shannon_stream.py` production route only.
- Translate legacy `agent=shannon` and `worker_channel=shannon_stream` at the
  facade boundary before dispatch-capable code sees them.
- Record `legacy_route` telemetry and deprecation deadlines.
- Add `engine_plan` emission for new runs.
- Add tests proving stream-Shannon compatibility does not import or invoke
  Shannon stream workers.

Hard gate:

- Contract tests pass for the stream route.
- Seeded failure tests pass.
- Production stream route has zero imports of `workers.shannon_stream` or
  equivalent vendored stream runtime.

### M4: Tmux-Shannon Disposition

Goal: decide and execute the tmux-Shannon endgame based on evidence.

Allowed dispositions:

- build a sessionful Claude adapter if tmux behavior is load-bearing
- replace with stateless `claude -p` if evidence proves sessionful behavior is
  not needed
- intentionally drop behavior with named sign-off

Tasks:

- Finish the Shannon behavior depth audit.
- Migrate consumers from `shannon_plan` to `engine_plan`.
- Move liveness/heartbeat responsibilities that belong to the facade out of
  Shannon-specific code.
- Preserve or explicitly drop session rotation, transcript capture, envelope
  repair, auth handling, permission handling, binary pinning, and cloud user
  behavior.
- Delete vendored Shannon code only after consumer migration and parity tests.

Hard gate:

- No production path imports `workers.shannon`, `agent_adapters.shannon`, or
  `vendor/shannon`.
- Every intentionally dropped behavior has named sign-off.
- Historical `shannon_plan` artifacts remain readable; new runs never write
  `shannon_plan`.

### M5: Codex Governance

Goal: govern Codex review/apply behind the surface without degrading quality.

Tasks:

- Implement `agent review` over Codex.
- Implement `agent apply` over Codex or a governed patch backend.
- Preserve Codex quality and ergonomics where it wins.
- Add seeded review findings and patch-conflict corpora.
- Define false-negative, false-positive, patch success, and failure diagnostic
  thresholds.
- Add dry-run, rollback/non-destructive failure, and PR/comment-ready outputs.

Hard gate:

- No quality regression beyond declared thresholds.
- Any regression requires explicit signed tradeoff.
- Codex-backed execution is governed by shared artifacts, telemetry, cost,
  timeout, and failure handling.

### M6: Security Enforcement And Tool Policy

Goal: make the shared surface a real control plane, not a policy translation
layer only.

Tasks:

- Split security into two tiers:
  - policy translation: map profiles to engine-native flags/settings/tools
  - policy enforcement: OS/container/user/network/worktree controls that hold
    even if the engine misbehaves
- Implement credential mediation or an equivalently hard mechanism so production
  direct bypasses fail without facade-issued credentials.
- Add explicit env allowlists for subprocess engines.
- Add web/browser/MCP context-boundary policy and prompt-injection tests.
- Add source-dependent tool attenuation: untrusted external content cannot
  coexist with unmediated write/shell capability.
- Add vendored Pi ecosystem supply-chain checklist.

Hard gate:

- Write-capable and web/browser profiles have OS-level enforcement, not only
  engine-native policy.
- Direct `claude -p` / `codex exec` bypass on a production runner fails or is
  visibly unauthenticated without facade mediation.
- Prompt-injection and bypass attempts fail in tests.

### M7: Deletion, Bakeoff, And Per-Path Cutover

Goal: delete old active paths one by one, with dated tests.

Tasks:

- Add static checks, import graph checks, installed-artifact checks, and runtime
  telemetry checks for forbidden patterns.
- Give every compatibility path a calendar deadline and CI deletion test when
  the compatibility path is introduced.
- Run statistical bakeoffs on the stratified corpus.
- Run negative-test suite: provider failures, rate limits, disk full, network
  partition, encoding attacks, sandbox escape attempts, SSRF, history
  corruption, secret echo, and fanout partial-kill recovery.
- Update skills, docs, CI, Makefiles, and runbooks.
- Keep telemetry to prove no forbidden path is used for at least the agreed
  observation window after cutover.

Hard gate:

- All forbidden patterns are absent from production callers and installed
  artifacts.
- Every temporary compatibility path has either been deleted or has a failing
  gate preventing release past its deadline.
- Runtime telemetry shows no forbidden path usage for the observation window.

### Track Independence Rule

M2 failure must not block M3-M5. M3 failure must not block M5. M5 failure must
not block M6. Each track must either ship a useful facade-governed improvement,
delete a legacy path, or produce evidence that stops only that track.

## Test Matrix

| Layer | Tests |
| --- | --- |
| L0 unit | profile parse, model aliases, schema refs, output paths |
| L1 fake provider | success, no output, malformed output, timeout, provider error |
| L2 subprocess | stderr spam, stdout caps, SIGTERM/SIGKILL, partial capture |
| L3 single agent | real scout/reviewer briefs against Pi, `claude -p`, and Codex adapters |
| L4 structured | Megaplan phase JSON outputs, schema mismatch, repair provenance |
| L5 worktree | write isolation, diff capture, dirty source, cleanup |
| L6 fanout | N=8/N=32/N=50/N=100 memory/time/output behavior |
| L7 review/apply | diff review, patch application, conflict handling |
| L8 web/browser | search/fetch/citation, CDP navigation, screenshots |
| L9 bakeoff | old launchers vs shared-surface corpus comparison |
| L10 cutover | forbidden dependency scans, installed-wheel/source parity |

## Hard Gates

The migration cannot be considered complete until:

1. All M0 documents exist and executable old-contract conformance tests pass
   against the current system.
2. The thin facade ships first and records uniform run, artifact, telemetry,
   lineage, cost, and error data while preserving old runtime behavior.
3. `agent ask` is competitive with direct ad-hoc CLI use, and a seeded failure
   is diagnosable from facade artifacts alone.
4. Credential mediation or an equivalently hard mechanism prevents production
   direct bypasses from silently using provider credentials outside the facade.
5. Shared `agent fan` handles N=50 at parity-or-better versus the measured
   `fan.py` baseline before `fan.py` deletion is approved.
6. Stream-Shannon and tmux-Shannon are retired separately; tmux-Shannon deletion
   requires a complete behavior audit and zero production imports of Shannon
   workers, adapters, worker channels, or vendored runtime code.
7. Shared `agent review` and `agent apply` govern Codex paths without quality
   regression beyond declared thresholds.
8. Write-capable and web/browser profiles have OS-level enforcement, not only
   engine-native policy translation.
9. Structured outputs pass schema validation with deterministic failure modes.
10. Timeout and kill behavior leaves no orphan process tree in test scenarios.
11. Every temporary compatibility path has a CI deletion test and calendar
    deadline from the day it is created.
12. Clean install checks prove forbidden dependencies are absent from installed
    artifacts, and runtime telemetry shows no forbidden path usage for the
    observation window.

## De-Risking Strategy

The main risks are not whether Pi can spawn an agent. Pi can. The risks are
contract fidelity, high-N fanout, output structure, and operator trust.

Mitigations:

- Freeze old contracts first.
- Use old launchers as comparison oracles, not permanent dependencies.
- Build fake-provider tests before touching real models.
- Keep every artifact contract explicit.
- Treat high-N fanout as a first-class runtime problem.
- Preserve strong native engines where useful, but put them behind the facade.
- Vendor small pieces, not broad packages.
- Run bakeoffs on real historical briefs.
- Add static forbidden-dependency checks before cutover.
- Use installed-artifact checks so editable-source cleanup does not lie.

## Schedule Shape

Realistic delivery: 12-20 weeks if all tracks proceed. The work is no longer
one 12-20 week cutover; it is a sequence of independently shippable migrations.

Suggested shape:

- Weeks 1-2: M0, evidence and executable contract freeze.
- Weeks 3-4: M1, thin facade wrapping existing launchers with recording,
  `agent ask`, `agent kill`, `agent history`, and `agent doctor`.
- Weeks 4-6: M2, fanout spike and pooled adapter decision.
- Weeks 5-7: M3, `claude -p` adapter and stream-Shannon retirement.
- Weeks 7-10: M4, tmux-Shannon disposition and `shannon_plan` migration.
- Weeks 8-10: M5, Codex governance for review/apply.
- Weeks 9-12: M6, security enforcement, credentials, web/browser/MCP policy.
- Weeks 12-20: M7, per-path deletion, bakeoff, docs, CI checks, operational
  hardening, and observation-window telemetry.

The schedule can compress only by shipping independent tracks earlier. It must
not compress by retaining old launchers as permanent production paths.

## Open Questions

1. Should `pi-agent` live inside Arnold, a separate local package, or an upstream Pi extension bundle?
2. Which model/provider aliases are canonical for DeepSeek, Kimi, Zhipu, Claude, and OpenAI-family routes?
3. What is the minimum acceptable quality threshold for replacing Codex review?
4. Does high-N fanout need true N=100 on day one, or is N=50 the cutover gate with N=100 as stress?
5. Which current skills must be updated in the first cutover wave?
6. Which artifacts should be stable for compatibility versus intentionally redesigned?
7. How much of Oh My Pi should be mined before declaring it too coupled?
8. Do cloud/remote runners need Pi installed, vendored, or bootstrapped per job?
9. Should legacy `agent=shannon` requests remain as a short-lived alias to the
   Claude adapter, or should they fail closed after M10?

## Sense-Check Addendum

This reconstruction is directionally coherent, but the implementation plan
needs these clarifications before it becomes execution-ready.

### 1. Define "Shared-Surface-Owned" Precisely

The plan forbids old launch systems but allows approved engines behind the
facade. That distinction must be explicit:

- allowed: calling Pi core, `claude -p`, or Codex through owned engine adapters
- allowed temporarily: direct Pi/Claude/Codex subprocesses while bringing up the
  facade, if every call is inside the adapter layer
- not allowed in final high-N paths: one full cold process per task if that
  cannot satisfy memory and throughput gates
- not allowed: shelling out to Hermes, Shannon, Codex CLI, Claude CLI,
  `claude -p`, or `fan.py` as hidden caller-level implementation details

The final architecture should prefer a library, daemon, worker pool, or broker
interface where an engine exposes one or where we build one. A raw
subprocess-per-agent model is acceptable only where the performance and cleanup
gates prove it is good enough and the subprocess is owned by the adapter layer.

### 2. Clarify Package Name Prohibitions

The forbidden `@mariozechner/pi-*` / `@oh-my-pi/*` dependency language is about
unreviewed final runtime dependencies and namespace ownership, not a ban on
using Pi-derived code.

Execution-ready wording should be:

- Pi core may be a dependency if pinned, reviewed, and intentionally owned.
- OMP should not be a final runtime dependency.
- Ecosystem package code may be vendored/adapted after supply-chain review.
- Final package names should be under an Arnold-owned namespace so operator
  docs, audit trails, and update policy are unambiguous.

### 3. Add MCP And Permission Parity

The feature list covers web/browser/external tools, but the current launcher
ecosystem also depends on MCP-like tool integration and explicit permission
behavior. Add parity requirements for:

- MCP server discovery and configuration
- per-profile MCP allowlists
- tool approval/denial policy
- noninteractive mode behavior
- audit logs for denied tool calls
- safe handling of tools that expose credentials or network access

### 4. Separate Provider From Agent Runtime

The plan correctly forbids direct Codex CLI, direct Claude CLI, and Shannon as
launch systems, but it should not accidentally forbid OpenAI or Anthropic as
model providers or `claude -p` / Codex as approved adapter backends. The
canonical distinction:

- allowed: OpenAI/Anthropic/DeepSeek/Kimi/Zhipu model APIs behind Pi provider
  adapters
- allowed: `agent-control -> Claude adapter -> claude -p`
- allowed: `agent-control -> Codex adapter -> Codex runtime`
- forbidden final path: callers invoking `codex`, `claude`, `claude -p`,
  Shannon, Hermes, or their CLI/session managers directly as the agent runtime

### 5. Add Rollback Without Permanent Fallback

"Absolute replacement" should not mean unsafe cutover. The plan should permit a
time-boxed rollout fallback during M9/M10, while keeping the final gate strict.

Recommended rule:

- shadow/bakeoff can call old launchers
- canary rollout can retain an emergency rollback flag for a bounded bake period
- final completion requires deleting or disabling the old launch path and adding
  checks that prevent it from returning

### 6. Add Data Model Deliverables

M8 mentions history and telemetry, but implementation needs concrete storage
contracts earlier:

- run record schema
- task record schema
- artifact manifest schema
- error taxonomy schema
- cost/token event schema
- parent/child lineage schema
- retention and redaction policy

These schemas should be drafted by M1/M2, then extended through M8. Otherwise
later phases will retrofit observability into incompatible artifacts.

### 7. Tighten Success Metrics

Several gates say "equal or better" or "acceptable". Before execution, define
measurable thresholds:

- success rate delta allowed
- median/p95 latency target
- N=50/N=100 memory ceiling
- max orphan-process tolerance: zero in controlled tests
- structured-output exactness percentage
- review false-negative tolerance on seeded findings
- patch apply success rate on historical patch corpus
- maximum artifact size and parent-context return size

### 8. Preserve The Good Abstraction

Even with absolute replacement, keep the facade abstraction. The strongest
version of the plan is:

```text
callers depend on the shared agent-control contract
the shared surface owns runtime selection
old systems are only temporary oracles
approved engines satisfy the contract
hard gates prove old systems are gone
```

That gives a clean break without baking today's Pi, Claude, Codex, or Shannon
internals directly into every Arnold/Megaplan caller.

## Related Recovered Artifacts

The vanished original directory reportedly contained:

- `PI_ABSOLUTE_REPLACEMENT_PLAN.md`
- `PI_CLEAN_BREAK_PLAN.md`
- `PI_ECOSYSTEM_SUBAGENT_EVALUATION.md`
- `SYNTHESIS_BUNDLE_RECOMMENDATION.md`
- `pi-supply-chain-audit-report.md`
- `codex-review/output.txt`
- `codex-review/prompt.md`
- `discovery-briefs/`
- `discovery-results/`
- `investigation-briefs/`
- `investigation-results/`
- `ecosystem-sensecheck-results/`
- `requirements-extract.md`
- `requirements-extract.json`

The surviving transcript states the final move target was:

`/Users/peteromalley/Documents/Arnold/.megaplan/pi-absolute-replacement-plan/`

This reconstructed plan restores the main strategic document only. The detailed
50-agent per-topic reports were not recoverable from the filesystem.
