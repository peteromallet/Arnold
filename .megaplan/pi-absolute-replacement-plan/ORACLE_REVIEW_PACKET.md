# Oracle Review Packet: Unified Agent Surface Plan

## Purpose

This document is a self-contained packet for an extremely capable outside model
or reviewer that has no prior context from the Arnold/Megaplan codebase.

The goal is not to get a polite opinion. The goal is to force a holistic
judgement:

- execute mostly as written
- resequence the plan
- split it into smaller migrations
- reject the direction and choose a narrower fix

The reviewer should validate, refute, or provoke a stronger plan. They should
not assume hidden repository knowledge.

After this packet was answered, the resulting decision was captured in:

- `ORACLE_DECISION.md`

That decision supersedes the original monolithic execution sequence by splitting
the work into independently shippable migrations.

## Decision Being Reviewed

Arnold/Megaplan currently has multiple agent launch paths and runtime surfaces:
Hermes/DeepSeek launchers, high-N fanout scripts, Shannon Claude workers,
direct Claude/Codex CLI use, worker-specific artifact contracts, skills, and
Megaplan phase runners.

The proposed direction is to replace unmanaged launch paths with one shared
agent-control surface.

Target end state:

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

The key rule:

> Pi, `claude -p`, and Codex may remain as engines. They must not remain as
> separate integration contracts. Shannon must be retired entirely.

## Current World The Oracle Needs To Understand

The existing system is not just "some scripts." It has several mature but
fragmented behaviors:

- `fan.py` runs many DeepSeek/Hermes-style agents efficiently by importing the
  runtime once and fanning out work in one process. It is valuable because
  process-per-agent fanout can be too memory-heavy.
- Shannon is a Claude worker layer, not merely a name. It includes tmux-based
  interactive Claude sessions, a stream-json channel, session planning,
  liveness detection, artifact metadata, auth handling, retry behavior, and
  compatibility fields such as `shannon_plan`.
- `shannon_stream.py` is closer to native `claude --print --output-format=stream-json`;
  `shannon.py` is a deeper tmux/interactive Claude runtime. They should not be
  treated as identical.
- Codex is currently valuable for review/apply behavior. The plan preserves it
  as a governed engine behind the shared surface rather than pretending Pi must
  replace its quality immediately.
- There is already some adapter architecture in the codebase: an agent
  dispatcher/adapter seam exists. The proposed project should be understood as
  upgrading this into a real control plane, not necessarily inventing the
  adapter idea from scratch.
- Worker results and receipts include compatibility metadata. `shannon_plan`
  is treated as opaque by some consumers, but it is still threaded through
  result, receipt, retry, and fanout paths.
- Skills and human workflows may currently call direct launchers because they
  are fast and familiar. A new surface that is harder to use will be bypassed.

## Proposed Final Surface

The final runtime should expose at least:

- `agent ask`
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

The original implementation plan used `agent launch` heavily, but adoption
reviews flagged a missing ergonomic requirement: `agent ask "..."` or another
zero-friction path must exist, otherwise users will keep `claude -p` or Codex
aliases for ad-hoc questions.

## Forbidden Final Production Patterns

These can exist only as explicit temporary bakeoff/oracle paths during
migration:

- `fan.py`, `fan_process.py`, `fan_kill.py`
- `launch_hermes_agent.py`
- `launch_claude_agent.py`
- direct caller-level `codex exec`, `codex exec review`, `codex apply`
- direct caller-level `claude -p`
- `shannon.py` or `shannon_stream.py` as production worker routes
- `shannon_tmux`, `shannon_stream`, or Shannon worker-channel routing
- `run_shannon_step` / `run_shannon_stream_step` as production dispatch targets
- Shannon adapter registration as a maintained adapter
- `megaplan/vendor/shannon/index.ts` as a runtime dependency
- active Hermes env dependency such as `~/.hermes/.env`
- hidden direct CLI/session-manager invocation from callers

Allowed final patterns:

- `agent-control -> Pi adapter -> Pi runtime`
- `agent-control -> Claude adapter -> claude -p`
- `agent-control -> Codex adapter -> Codex runtime`
- `agent-control -> approved provider adapter -> provider-native runtime`

## Why This Is Hard

The plan is not just a CLI rename. It is a runtime/control-plane migration with
cross-cutting responsibilities:

- stable adapter contracts
- model/provider alias resolution
- tool permission policy
- structured output validation
- worktree isolation
- high-N fanout
- timeout and process-tree kill semantics
- retry/fallback classification
- history, replay, telemetry, cost, lineage
- review/apply quality
- web/browser/MCP permissions
- supply-chain policy for Pi ecosystem code
- compatibility with existing Megaplan phases and artifacts
- deletion of old paths without unsafe big-bang cutover

## Critical Corrections From Multi-Agent Sense-Check

Ten DeepSeek reviewers and one high-reasoning Codex reviewer were used to
stress the plan from different angles. Their strongest shared conclusions:

1. The plan should explicitly relate to the existing adapter/dispatcher seam.
   It should upgrade that seam into a control plane rather than blindly rebuild
   the same abstraction elsewhere.
2. Shannon retirement is under-specified if it assumes `claude -p` is a drop-in
   replacement. Shannon tmux, Shannon stream, and `claude -p` have different
   execution and liveness models.
3. The adapter contract must be normative. Without a precise interface, Pi,
   `claude -p`, and Codex will become three separate systems hidden behind one
   CLI.
4. Fanout feasibility is the biggest architectural risk. If N=50 cannot match
   or beat `fan.py` without unbounded memory/process growth, the plan must be
   resequenced around fanout first.
5. Data contracts must move earlier. Run records, artifact manifests,
   `engine_plan`, legacy-route mapping, error taxonomy, cost events, and lineage
   must be drafted by M0/M1, not retrofitted in observability later.
6. Security cannot stop at tool allowlists. Web/browser/MCP outputs introduce
   prompt-injection and context-boundary risk; secrets and env inheritance need
   explicit policy.
7. Adoption is not an enforcement problem only. The shared surface must be
   shorter, clearer, and easier to debug than direct launcher bypasses.
8. Testing must include seeded negative failures and statistical bakeoff
   design, not only old-vs-new smoke comparisons.
9. Operations need first-class treatment: install contract, global cost
   ceilings, rate-limit backpressure, incident runbooks, and cloud runner
   constraints.
10. The plan may be over-scoped unless it can name the smaller 80-percent plan
    and reject it on evidence.

## Context Bundle The Oracle Should Assume Is Needed

If this packet is sent to an oracle model, the model should say whether it needs
more data in these categories before reaching a final verdict:

- Current launcher inventory: callers, scripts, skills, worker channels, CLI
  flags, env vars, and artifact paths for Hermes, fan, Shannon, Claude, Codex,
  Pi, MCP/tools, browser, and web.
- Old behavior contracts: artifact schemas, exit codes, timeout/kill behavior,
  retry classification, structured output expectations, cost/token metadata,
  and historical failure modes.
- Real workload corpus: successful briefs, failed briefs, high-N fanout jobs,
  review/apply examples, browser/web tasks, write-capable worktree tasks.
- Measured baselines: success rate, latency p50/p95, memory at N=8/32/50/100,
  orphan-process rate, cost, artifact size, structured-output validity, review
  quality.
- Existing architecture map: import graph, process tree, package/dependency
  graph, cloud/CI runner constraints, install layout, and direct subprocess
  call sites.
- Engine capability facts: exact Pi, Claude, and Codex APIs/CLIs available,
  version pins, JSON/streaming behavior, sandbox/tool policy, lifecycle control,
  MCP/tool support.
- Security constraints: secret sources, network policy, filesystem
  permissions, browser/localhost expectations, vendoring policy,
  supply-chain audit posture.
- Rollout constraints: acceptable downtime, rollback window, current users of
  old paths, migration order, and what final deletion legally means.

## Non-Negotiable Precondition Documents

Before implementation begins, the plan should produce or bundle these docs:

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

## Shannon Behavior Depth Audit Required

Before claiming Shannon can be replaced by `claude -p`, classify each behavior
as one of:

- reproduced in the `claude -p` adapter
- obsoleted by stateless single-turn execution
- moved into the shared surface
- intentionally dropped with sign-off
- still unknown, blocks cutover

Behaviors to classify:

| Behavior | Current Shannon concern |
| --- | --- |
| Tmux interactive Claude runtime | not equivalent to `claude -p` |
| Stream-json Claude channel | closer to `claude -p`, but still its own worker |
| Prompt projection | worker-specific prompt shaping |
| Session identity | receipts, retries, provenance |
| `/clear` / `/compact` style session rotation | stale-context control |
| Transcript capture and parsing | postmortem and liveness |
| Three-channel liveness | distinguishing silent work from wedge |
| Long-running tool-call idle behavior | avoiding false timeout kills |
| Auth-channel handling | API key/OAuth/subscription differences |
| Read-only/write-capable tool policy | profile safety |
| Execute envelope repair | salvaging truncated structured output |
| Non-root/cloud user handling | containment in remote runners |
| Claude binary pinning/stub detection | avoiding updater races |
| Workspace trust and MCP config isolation | repeatable startup behavior |
| `shannon_plan` consumers | data migration and receipt compatibility |
| `worker_channel=shannon_*` dispatch | old routing bypass risk |

If any production path still imports Shannon workers, Shannon adapters, or
vendored Shannon runtime code after cutover, the plan has failed by its own
definition.

## Normative Engine Adapter Contract Needed

The oracle should judge whether this contract is sufficient.

Every engine adapter should register:

- `engine_id`: stable string, no aliases
- `execution_model`: `stateless`, `sessionful`, or `pooled`
- `capabilities`: structured output, streaming, tools, browser, web, patch,
  worktree, session affinity, max concurrency
- `supported_providers`: informational only; shared surface owns resolution
- `security_profile`: what the adapter can and cannot enforce

Launch signature:

```text
launch(profile, resolved_model, input, output_dir, timeout_sec, abort_signal)
  -> run_handle
```

Run handle contract:

- `status()` returns quickly with state, exit code, error code, partial output
- `wait(timeout)` blocks only within bounded timeout
- `kill()` best effort, bounded latency
- `artifacts()` returns normalized artifact paths
- `telemetry()` returns structured telemetry matching the shared schema

Invariants:

- The shared surface owns output directory layout.
- The shared surface owns model/provider alias resolution.
- The shared surface owns timeout and kill policy.
- Native engine errors are mapped into the shared taxonomy.
- Tool calls are transparent to telemetry where the engine exposes them.
- Stateless adapters must not keep session state.
- Sessionful adapters must declare session affinity and cleanup behavior.
- Engine-specific metadata goes under `engine_specific`, not into caller-facing
  ad hoc fields.

## Evaluation And Bakeoff Expectations

The oracle should not accept "equal or better" without an evaluation protocol.

Minimum expected evaluation properties:

- stratified corpus across profiles, engines, failure modes, token lengths, and
  toolsets
- repeated runs where nondeterminism matters
- blind quality judging for subjective outputs
- seeded review findings and patch conflicts
- negative tests for provider errors, rate limits, disk full, network failure,
  encoding attacks, sandbox escape attempts, SSRF, history corruption, secret
  echo, and fanout partial-kill recovery
- explicit thresholds for success rate, latency, memory, cost, structured
  output validity, review false negatives/positives, patch apply success, kill
  latency, and orphan-process tolerance

## The Ten Oracle Questions

The oracle should answer these in order. For each, answer:

- verdict: pass, pass with changes, resequence, split, or reject
- reasoning
- missing evidence
- concrete plan changes required
- kill-condition assessment

### 1. Strategic Premise

What problem is this plan actually solving: fragmented launch paths, Shannon
retirement, Pi adoption, high-N fanout, operator trust, or all of these?

Questions:

- Is a unified control surface the minimal sufficient intervention, or is the
  plan bundling separable migrations into one risky rewrite?
- Which current failures would remain unsolved even if this plan succeeds?
- What is the smaller plan that captures 80 percent of the value, and why is it
  insufficient?
- Should Pi be framed as the primary substrate, or merely one engine behind a
  more neutral surface?

Kill question:

- If the old stack's pain is mostly Shannon-specific or artifact-contract
  specific, why is a 12-20 week runtime replacement justified?

### 2. Boundary Of Shared-Surface Ownership

What exactly counts as an illegal bypass versus an approved engine adapter?

Questions:

- Can the plan define a stable interface that does not leak Pi, Claude, Codex,
  or Shannon details into callers?
- Are `claude -p` and Codex being preserved as engines, or smuggled back in as
  hidden launch systems?
- Does the existing adapter/dispatcher seam become the foundation of the
  control plane, or is it replaced? Why?
- Can adapter ownership be proven by import graph, installed artifact scan, and
  runtime telemetry?

Kill question:

- If adapter ownership cannot be mechanically checked, is the cutover criterion
  enforceable?

### 3. Contract Fidelity

Which old behaviors are compatibility contracts, and which are accidental legacy
quirks?

Questions:

- Are artifact, error, timeout, metadata, and structured-output contracts
  specified enough to write conformance tests before implementation?
- What current behaviors are intentionally dropped, and who signs off?
- Which downstream consumers parse old artifacts or compatibility fields?
- Can the plan freeze old contracts without freezing old implementation bugs?

Kill question:

- If M0 cannot produce executable contract tests, should implementation begin?

### 4. High-N Fanout Feasibility

Can the new surface match or beat `fan.py` at N=50 without one cold heavyweight
runtime per task?

Questions:

- What concrete architecture handles N=50/N=100: process pool, broker, daemon,
  pooled Pi runtime, or something else?
- What are the memory, file descriptor, stdout/stderr buffer, and provider
  backpressure ceilings?
- How does the scheduler recover if it crashes mid-fanout?
- How are stragglers, rate limits, global timeout, partial results, and external
  kill handled?

Kill question:

- If the N=50 design remains speculative after the spike, should the whole plan
  be resequenced around fanout first?

### 5. Shannon Retirement

Can Shannon truly be replaced by `claude -p`, and what must be preserved?

Questions:

- Which Shannon behaviors were essential: prompt projection, stream parsing,
  session identity, liveness, artifacts, auth, permission policy, or Claude
  interactive affordances?
- Which behaviors are made unnecessary by stateless `claude -p`, and which need
  replacement elsewhere?
- Why did both tmux and stream Shannon channels exist, and what does that imply
  about replacing both?
- How will legacy `agent=shannon`, `worker_channel=shannon_*`, and
  `shannon_plan` be detected, migrated, and eventually rejected?

Kill question:

- If any production path still imports Shannon workers/adapters/vendor code
  after cutover, has the plan failed?

### 6. Review/Apply Quality

Should Codex remain the review/apply engine behind the shared surface, and what
would count as a regression?

Questions:

- Is Codex merely governed by the surface, or is the plan trying to replace
  Codex quality with Pi-derived plugins?
- What seeded review findings and patch-conflict cases must the new surface
  catch?
- What false-negative/false-positive thresholds are acceptable?
- If Pi review differs from Codex review, who arbitrates quality?

Kill question:

- If review/apply quality drops without explicit accepted tradeoff, should those
  paths be cut over?

### 7. Security, Permissions, And Prompt Injection

Can the shared surface actually enforce tool policy across engines and untrusted
inputs?

Questions:

- Can profiles enforce cwd, writable roots, browser access, web access, network
  access, command audit, and MCP approval uniformly across engines?
- Can engine-native tools bypass shared policy?
- How are secrets passed to subprocesses without broad environment inheritance?
- What context-boundary protections prevent web/browser/MCP prompt injection
  from influencing write-capable agents?
- What vendored Pi ecosystem code is allowed, and what supply-chain checklist
  rejects unsafe packages?

Kill question:

- If tools can bypass profile policy through engine-native mechanisms, is the
  shared surface actually the control plane?

### 8. Observability, Data Model, And Replay

Can runtime behavior be reconstructed from artifacts and history?

Questions:

- Are run/task/artifact/error/cost/history schemas defined early enough to avoid
  retrofitting telemetry later?
- What replaces `shannon_plan`, and where does engine-specific metadata live?
- What does `agent replay` mean: deterministic re-execution, timeline
  reconstruction, or both?
- Does telemetry prove which adapter and engine actually executed each task?
- How does lineage work for fanout children, retries, subagents, and kills?

Kill question:

- If a killed or failed run cannot be diagnosed without raw process logs, will
  operators trust the migration?

### 9. Migration, Rollback, And Deletion

Can the system migrate safely without preserving permanent fallback paths?

Questions:

- Is rollback facade-owned, artifact-stable, auditable, scan-visible, and
  time-boxed?
- What old paths may exist during shadow/canary, and how are they prevented from
  becoming permanent?
- Are compatibility aliases translated before dispatch-capable code sees them?
- What exact static and runtime checks prove forbidden paths are gone from
  production callers and installed artifacts?

Kill question:

- If temporary compatibility has no deletion test and deadline, is it just
  another permanent launch path?

### 10. Operations, Cost, And Adoption

Can this be operated and adopted outside the original developer's machine?

Questions:

- What single command installs the surface on a clean Ubuntu runner, and what
  fails first?
- How are provider keys, rate limits, global cost ceilings, and queue admission
  enforced before provider calls happen?
- What is the incident runbook for pool exhaustion, orphan processes, provider
  outage, and runaway cost?
- Is there a zero-friction path such as `agent ask "..."` that is shorter and
  more debuggable than direct `claude -p` or `codex exec`?
- How will static checks handle shell aliases, personal scripts, Makefiles, CI
  YAML, and skills that wrap forbidden launchers?

Kill question:

- If the official surface is slower, harder to type, or harder to debug than
  bypasses, will enforcement alone be enough?

## Anti-Leading Instructions For The Oracle Prompt

Do not ask: "Does this plan make sense?"

Ask the oracle to choose one:

- execute mostly as written
- resequence
- split into smaller migrations
- reject

Do not describe Pi as the obvious substrate. Provide facts about Pi's lifecycle,
extension model, process model, JSON behavior, and tool policy, then ask whether
it is sufficient.

Do not frame Shannon deletion as morally necessary. Ask what must be preserved,
what can be discarded, and what proof shows it is gone.

Do not let "shared surface" remain a slogan. Force enforceable boundaries,
testable contracts, and deletion checks.

## Requested Oracle Output Format

The oracle should respond with:

1. Overall verdict: execute, resequence, split, or reject.
2. Confidence level and what evidence would change it.
3. The top five missing context items that block judgement.
4. The top five changes required before implementation begins.
5. The top five risks that can invalidate the whole direction.
6. A revised milestone order if resequencing is needed.
7. A smaller 80-percent plan and whether it is preferable.
8. Direct answers to the ten oracle questions above.
9. A final list of non-negotiable gates.
