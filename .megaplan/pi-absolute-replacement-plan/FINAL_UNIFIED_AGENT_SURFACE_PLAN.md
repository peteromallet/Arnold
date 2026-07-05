# Final Unified Agent Surface Plan

Date: 2026-07-04  
Status: final integrated plan after oracle review, Codex deviation review, gap swarm, Pi skill research, and long-shot surface swarm  
Related files:

- `PI_ABSOLUTE_REPLACEMENT_PLAN.md` - reconstructed source plan
- `ORACLE_REVIEW_PACKET.md` - self-contained oracle prompt packet
- `ORACLE_DECISION.md` - oracle verdict and direct answers
- `CODEX_DEVIATION_REVIEW.md` - Codex follow-up deviations
- `GAP_SWARM_REVIEW.md` - DeepSeek targeted + broad swarm gap review
- `LONGSHOT_SWARM_REVIEW.md` - second broad long-shot surface sweep
- `QUALITY_OF_LIFE_PARITY.md` - operator ergonomics and affordance parity notes
- `QOL_PARITY_MATRIX.md` - testable QoL parity checklist

## Executive Decision

Proceed, but **split the work into independently shippable epics**.

Do not execute the original monolithic replacement plan. The direction is
correct, but the old sequence tied too much of the project to its hardest and
least-proven parts: high-N fanout and tmux-Shannon retirement.

The final rule:

> Ship a thin recording/control facade first. Replace runtimes only after the
> facade has captured contracts, baselines, telemetry, adoption data, and
> deletion evidence.

## Final Target State

All Arnold/Megaplan agent work routes through one agent-control surface:

```text
Arnold / Megaplan callers
  -> agent-control facade
      -> shared policy, profiles, artifacts, telemetry, kill/control, history
          -> Pi engine
          -> Claude engine adapter
              -> claude -p where stateless execution is sufficient
              -> sessionful Claude adapter if tmux-Shannon behavior is load-bearing
          -> Codex engine adapter
          -> other approved provider-native engines
```

Pi, Claude, and Codex may remain as engines. They must not remain as separate
caller-facing integration contracts.

Shannon is retired as a production contract. That does **not** mean every
Shannon behavior is blindly replaced by `claude -p`; tmux-Shannon behavior is
audited and either reproduced in a sessionful adapter, made obsolete by the new
surface, or explicitly dropped with sign-off.

## Final Epic Shape

There are **8 epics**:

1. Discovery, contracts, and evaluation baselines
2. Thin facade, recording, and minimum enforcement
3. Provider execution and Hermes decomposition
4. Fanout feasibility and adapter design
5. Claude/Shannon retirement
6. Codex review/apply governance
7. Consumer migration, hardening, deletion, and installed-artifact proof
8. Cloud, resident, watchdog, and AgentBox surface migration

This is **1 discovery/prep epic + 7 delivery epics**. The Codex deviation review
changed the grouping by promoting adoption concerns and pulling minimum
security/enforcement into the facade epic. A later correction adds provider
execution/Hermes decomposition as an explicit epic because existing profiles
depend heavily on `hermes:*` specs. The gap swarm adds an eighth epic because
cloud/resident/watchdog/AgentBox systems are independent production agent
surfaces, not just adoption cleanup.

## Decision Map

| Epic | What ships | What can fail independently | Evidence that kills/resequences it | Old path deleted |
| --- | --- | --- | --- | --- |
| 1. Discovery/contracts | Executable contract tests, baselines, schemas, Shannon audit | Runtime replacement | Missing conformance tests, unknown Shannon audit rows, no fanout baseline | None |
| 2. Thin facade | `agent ask/launch/kill/history/doctor`, run records, telemetry, cost, credential mediation start | Runtime replacement | Facade too slow, unusable, or not recording enough to diagnose failures | None |
| 3. Provider/Hermes | Canonical provider adapters; `hermes:*` compatibility mapping; useful Hermes internals extracted or replaced | Active Hermes deletion | Provider parity fails; Hermes key/retry/cost behavior not reproduced | Active Hermes runtime route after parity |
| 4. Fanout | `agent fan` spike or pooled adapter decision | Fanout deletion | N=50 cannot match `fan.py`; orphan/rate-limit/crash recovery fails | `fan.py` caller path only after parity |
| 5. Claude/Shannon | Claude adapter, stream-Shannon retirement, tmux-Shannon disposition, `engine_plan` migration | Tmux-Shannon deletion | tmux behavior is load-bearing and no sessionful adapter exists | `shannon_stream.py`, then `shannon.py`/vendor after audit |
| 6. Codex governance | `agent review/apply` over Codex with facade-owned artifacts/telemetry | Codex replacement | Seeded review/patch thresholds fail | Direct caller-level Codex review/apply |
| 7. Adoption/hardening/deletion | Skills/docs/CI/runbooks/profiles migrated; security hardening; installed-artifact proof; observation window | Final cutover | Users keep bypassing; forbidden paths remain in artifacts/telemetry; security tests fail | Remaining forbidden production paths |
| 8. Cloud/resident/AgentBox | Cloud CLI, watchdog, repair loops, resident Discord, AgentBox handlers route through facade | Cloud migration | Watchdog/repair parity fails; AgentBox lifecycle cannot be represented; auth shims break | Direct cloud, resident, and AgentBox agent calls after parity |

## Epic 1: Discovery, Contracts, And Evaluation Baselines

Goal: make the old world testable before changing it.

Deliverables:

- `current-launcher-inventory.md`
- `old-launch-contract.md`
- `old-artifact-contract.md`
- `old-error-taxonomy.md`
- `engine-adapter-contract.md`
- `operator-qol-parity-contract.md`
- `qol-parity-matrix.md`
- `shannon-behavior-depth-audit.md`
- `fanout-baseline-report.md`
- `security-threat-model.md`
- `evaluation-protocol.md`
- `operational-prerequisites.md`
- `profile-inventory.md`
- `profile-loader-contract.md`
- `credential-source-inventory.md`
- `credential-resolution-flow.md`
- `config-overlay-inventory.md`
- `config-file-inventory.md`
- `env-alias-and-suffix-inventory.md`
- `hermes-oauth-env-inventory.md`
- `cloud-env-var-inventory.md`
- `override-pipeline-contract.md`
- `skill-distribution-inventory.md`
- `skill-manifest-contract.md`
- `pi-package-source-review-matrix.md`
- `cli-and-human-command-surface-inventory.md`
- `pipeline-agent-step-contract.md`
- `model-seam-hook-contract.md`
- `cloud-resident-agent-surface-inventory.md`
- `agentbox-credential-and-operation-store-inventory.md`
- `worktree-lifecycle-contract.md`
- `old-receipt-contract.md`
- `engine-observability-contract.md`
- `event-payload-contract.md`
- `telemetry-projection-contract.md`
- `run-record.schema.json`
- `artifact-manifest.schema.json`
- `engine-plan.schema.json`
- `legacy-route.schema.json`
- `error-taxonomy.schema.json`
- `receipt.schema.json`
- `cost-recorded-payload.schema.json`
- `llm-call-end-payload.schema.json`
- `worker-result-projection.schema.json`
- `content-type-contract.md`
- `event-journal-contract.md`
- `effect-ledger-contract.md`
- real-brief, failing-brief, review/apply, browser/web, worktree, and fanout
  corpora

Required measurements:

- `fan.py` memory, latency p50/p95, success rate, cost, orphan rate, and
  artifact behavior at N=8, N=32, N=50, and N=100
- Shannon channel usage: tmux vs stream, workload classes, failures, session
  reuse, long-idle tool-call behavior
- current direct-launch usage from scripts, skills, CI, Makefiles, docs, and
  observed human workflows
- operator QoL baselines: context compaction, context-budget controls,
  session resume/persistence, liveness heartbeat, timeout/hang diagnostics,
  query-file/large-prompt handling, permission modes, OAuth/session reuse,
  max-token defaults, streaming output, diff/review/apply UX, kill cleanup,
  live cost visibility, doctor output, worktree ergonomics, and skill
  invocation behavior
- QoL matrix classification: each operator affordance is marked preserved,
  facade-replaced, intentionally dropped with sign-off, or blocked by an engine
  adapter gap
- cloud/resident/AgentBox surfaces: cloud CLI, watchdog wrappers, repair loops,
  progress auditor, resident Discord runtime, AgentBox handler, Guardian
  scheduler, incident bridge, and remote discovery/recovery scripts
- skill surfaces: `sync-skills.sh`, `megaplan setup` skill targets,
  generated skills, installed Claude/Codex/Agents/Hermes skill directories,
  Hermes Skills Hub, cloud extra-skill sync, and executable payloads shipped
  inside directory-symlinked skills
- Pi package adoption candidates: source-review matrix for `pi-subagents`,
  `@tintinweb/pi-subagents`, `pi-sub-agent`, `pi-agents-team`,
  `pi-web-providers`, `pi-web-access`, `@hypabolic/pi-hypa`,
  `context-mode`, `pi-chat`, and `pi-mcp-adapter`, covering ownership risk,
  credential behavior, subprocess behavior, network behavior, artifact model,
  deletion impact, license, and supply-chain status
- CLI and human surfaces: `python -m arnold_pipelines.megaplan ...`,
  `agentbox ...`, cloud/resident/bakeoff/incident subcommands, operator
  scripts, generated command examples, and the onboarding setup flow
- profile system: system TOMLs, pipeline-local TOMLs, archive profiles,
  `extends` chains, `tier_models`, `prep_models`, `premium`, `--vendor`,
  `--critic`, `--phase-model`, and `--depth`
- config/env overlays: `~/.hermes/.env`, project `.env`, user config, project
  `.megaplan/config.toml`, `MEGAPLAN_*` env reads, and override actions
- credential/config edge cases: `HERMES_*` OAuth/config vars,
  `CLOUD_WATCHDOG_*`, `ARNOLD_*`, `~/.hermes/config.yaml`,
  `~/.hermes/auth.json`, `~/.hermes/.anthropic_oauth.json`,
  `~/.config/megaplan/config.toml`, `auto_improve/api_keys.json`,
  `/workspace/agentbox.yaml`, provider env aliases, and numbered key suffixes
- override ordering: `apply_profile_expansion`, vendor rewrite, critic rewrite,
  depth rewrite, phase-model appends, `--deepseek-provider`, and adaptive
  critique flags
- pipeline dispatch seams: `AgentStep`, `PanelReviewerStep`, dynamic fanout,
  model-step adapter registration, model-seam hook registries, and native graph
  fanout projection
- event/receipt consumers: WorkerResult, AgentResult, receipts,
  `COST_RECORDED`, `LLM_CALL_END`, `events.ndjson`, cost aggregation, trace,
  doctor, introspect, auto-stall detection, and receipt query/projection paths

Gate:

- Old-contract conformance tests exist and pass against the current system.
- Receipt, event-payload, WorkerResult projection, and cost/LLM telemetry
  schemas exist and are validated by tests against current emitters and
  consumers.
- Profile rewrite-order, credential detection, provider alias/suffix, and
  `resolve_model()` characterization tests exist.
- QoL parity matrix is complete for all high-impact rows and has acceptance
  tests or signed intentional differences.
- Adapter contract is frozen enough for Epic 2.
- No Shannon audit row remains `unknown`.
- Production migration is blocked until this passes.
- Disposable throwaway spikes are allowed before this gate, but their code must
  not become production migration code.

## Epic 2: Thin Facade, Recording, And Minimum Enforcement

Goal: ship the shared surface without changing runtime behavior.

The facade initially wraps existing launchers unchanged. This is intentional.
It delivers run records, telemetry, history, kill, cost, and adoption paths
before the plan takes dependency on runtime replacement.

Commands:

- `agent ask`
- `agent launch`
- `agent kill`
- `agent history`
- `agent doctor`
- `agent profiles`
- `agent profile show <name>`
- `agent skills`
- `agent skill sync`

Scope:

- uniform run records, artifact manifests, lineage, telemetry, cost events
- shared error taxonomy mapping
- seeded failure diagnosis from facade artifacts
- `agent ask "..."` as the zero-friction ad-hoc path
- QoL parity layer:
  - context compaction, summarized tool history, and budget warnings;
  - session persistence, stateless one-shot behavior, and resume IDs;
  - live heartbeats, hang detection, partial artifacts, and timeout diagnostics;
  - query-file and large-prompt handling;
  - clear permission-mode mapping for Claude, Codex, Pi, and provider-native
    engines;
  - OAuth/session reuse diagnostics and route-degradation explanations;
  - safe token defaults, model aliases, and empty-output/length-cap warnings;
  - streaming output, final-response extraction, and compact transcripts;
  - graceful/hard kill, fanout group kill, orphan cleanup, and post-kill status;
  - live/final cost visibility with exact-vs-estimated provenance.
- first credential mediation: provider keys issued through the facade where
  feasible; no broad ambient env inheritance for new facade-spawned paths
- global cost ceiling design and warning/abort behavior
- facade-level history store design, not only per-plan `events.ndjson`
- engine observability contract: every adapter emits model, provider,
  prompt/completion tokens, cost, duration, profile, user/skill attribution, and
  exact/estimated token provenance
- profile commands use the canonical profile loader; no third parser
- formal pipeline dispatch contracts for `AgentStep`, `PanelReviewerStep`,
  dynamic fanout specialization, model-step adapter registration, and
  model-seam hook registration; duck-typed worker injection becomes a tested
  protocol
- Skill Manifest Bridge:
  - keep `SKILL.md` as the source format;
  - add optional `agent_surface` metadata for preferred commands, required
    capabilities, default profile, allowed engines, and install/sync behavior;
  - validate skills through `agent doctor --skills`;
  - sync/generate Pi-compatible skill material using Pi's native skill loader
    locations, while keeping the facade as the route owner;
  - treat executable payloads shipped inside skill directories as controlled
    migration material, not invisible docs;
  - rewrite `subagent-launcher` to teach `agent ask`, `agent launch`,
    `agent fan`, `agent review`, and `agent apply` before direct launcher
    deletion.
- optional Pi package wrapper spikes:
  - `pi-subagents` may be wrapped experimentally for child-agent/fanout flows;
  - `pi-web-providers` and `pi-web-access` may be wrapped experimentally for
    web/search flows;
  - wrappers must emit Arnold run records, use Arnold credential mediation, and
    remain behind facade profile permissions.
- minimum enforcement policy:
  - explicit env allowlists
  - profile-to-engine permission mapping
  - no write-capable facade profile without worktree/writable-root policy
  - no web/browser profile without declared network/content boundary
- `agent doctor` validates binaries, versions, keys, config, and runner
  assumptions

Gate:

- Existing behavior remains unchanged except for added recording/control.
- `agent ask` is within the agreed latency/keystroke budget versus direct
  `claude -p`.
- QoL parity acceptance tests show common operator tasks are no worse than
  direct Claude/Codex/Hermes for context management, resume, liveness, large
  prompts, permissions, streaming output, kill/cleanup, cost visibility, and
  failure diagnosis, or have signed intentional differences.
- A seeded failed run is diagnosed from facade artifacts alone.
- Adapter contract, run record, and artifact manifest are stable enough for
  other epics.
- Pipeline step/hook conformance tests pass through the facade wrapper.
- `agent doctor --skills` can detect stale installed skills, stale generated
  skills, direct-launch examples, missing Pi skill sync targets, and
  directory-symlink payloads that still expose forbidden launchers.
- Broad adoption cannot expand until minimum security negative tests pass.
- Broad adoption cannot expand until `agent doctor` validates credentials,
  pricing freshness, configured provider coverage, and runner install health.

## Epic 3: Provider Execution And Hermes Decomposition

Goal: replace Hermes as an active production runtime route without losing the
provider execution behavior current profiles depend on.

Why this is explicit:

- Existing profiles contain many `hermes:*` specs.
- Those specs currently mean both "provider/model selector" and "use the Hermes
  runtime."
- In the final system, `hermes:*` can exist only as compatibility syntax during
  migration. It must not mean "route through active Hermes runtime."

Scope:

- Inventory all `hermes:*` profile specs and direct Hermes model execution call
  sites.
- Inventory every `hermes:*` string literal in Python and TOML and produce a
  machine-readable legacy-to-canonical mapping.
- Capture Hermes behavior for key selection, provider/model aliases, retries,
  streaming, rate limits, structured output, cost/token accounting, error
  mapping, and partial output.
- Decide per behavior whether to extract, vendor, reimplement, or drop.
- Implement canonical provider adapters for DeepSeek, Fireworks/Kimi, Zhipu, and
  any other provider currently reached through Hermes.
- Replace the `resolve_model` monolith with a provider-router contract before
  deleting active Hermes runtime routes.
- Preserve or explicitly change KeyPool behavior: key source precedence,
  429 cooldown, provider-specific fallback, governor charging, zhipu
  `api_keys.json`, OpenRouter fallback, and Kimi/Moonshot aliases.
- Decide how `~/.hermes/.env` and project `.env` are bridged, deprecated, or
  blocked under facade credential mediation.
- Reconcile the two existing `~/.hermes/.env` load paths: manual KeyPool parse
  and dotenv-based environment injection.
- Preserve or intentionally change `HERMES_*` OAuth/config behavior,
  `~/.hermes/config.yaml`, `~/.hermes/auth.json`,
  `~/.hermes/.anthropic_oauth.json`, provider key aliases, numbered key
  suffixes, Codex/Copilot OAuth resolution, `gh auth token` fallback, and
  governor charging on key acquire.
- Add rewrite-order tests for `--vendor`, `--critic`, `--phase-model`,
  `--depth`, `--deepseek-provider`, and adaptive critique flags.
- Add profile parity tests: current loader output vs canonical resolver output
  for every system and pipeline-local profile.
- Add `extends` integrity tests for pipeline-local profiles.
- Map legacy specs:
  - `hermes:deepseek:deepseek-v4-pro` -> provider `deepseek`, model
    `deepseek-v4-pro`, canonical provider/Pi adapter
  - `hermes:deepseek:deepseek-v4-flash` -> provider `deepseek`, model
    `deepseek-v4-flash`, canonical provider/Pi adapter
  - `hermes:fireworks:...` -> provider `fireworks`, model path, canonical
    provider/Pi adapter
- Emit `legacy_route` telemetry for every `hermes:*` compatibility resolution.
- Rewrite profile TOMLs to canonical specs only after telemetry proves the
  mapping is correct.

Gate:

- Existing `hermes:*` profile routes pass provider parity tests through the
  canonical adapter.
- Every current profile resolves identically through the canonical resolver, or
  every intentional difference has sign-off.
- Cost, retry, rate-limit, timeout, structured output, and error behavior are
  equivalent or intentionally changed with sign-off.
- No production caller depends on active Hermes runtime after the deletion
  deadline.
- Historical `hermes:*` specs remain readable until the compatibility deadline,
  but new canonical profiles stop using the prefix.

## Epic 4: Fanout Feasibility And Adapter Design

Goal: decide whether `fan.py` can be absorbed/replaced without regression.

Judgement call: `fan.py` is forbidden as a caller-facing production path, but
its import-once pooled execution mechanism is valuable. It may be absorbed as
internal implementation of a pooled adapter if governed by the facade.

Scope:

- throwaway N=50/N=100 architecture probe during or immediately after Epic 1
- facade-owned `agent fan` spike
- admission control, run manifest, partial-result contract
- external kill, scheduler crash recovery, stale reconciliation
- rate-limit backpressure and timeout accounting
- straggler policy
- orphan-process audit
- memory/FD/stdout/stderr bounds
- `fan.py` model shortcut parity (`pro`, `flash`, `fast`, `mimo`, `kimi`,
  `glm`) and timeout/client-kwargs behavior
- `fan.py` process-isolation and `fan_kill.py` semantics
- compatibility with `_core/hermes_fanout.py`, `_core/worker_fanout.py`,
  `_core/process_fanout.py`, and `agent_runtime.scatter_agent_units`
- benchmark `pi-subagents`, `pi-sub-agent`, and `@tintinweb/pi-subagents`
  against `fan.py` at N=8, N=32, N=50, and N=100 before adopting any Pi-side
  fanout implementation
- effect-ledger/idempotency integration so scheduler crash recovery cannot
  duplicate external effects
- fanout cost aggregation and budget attribution by profile, user/skill, engine,
  and fanout group

Gate:

- N=50 parity-or-better versus `fan.py` on memory, p95 latency, success rate,
  artifact completeness, and orphan rate.
- If parity fails, the fanout track is redesigned or paused; other epics
  continue.
- `fan.py` caller path is not deleted until this gate passes.

## Epic 5: Claude/Shannon Retirement

Goal: retire Shannon as a production contract.

Sequence:

1. Build Claude adapter.
2. Retire stream-Shannon first.
3. Disposition tmux-Shannon by evidence.
4. Migrate `shannon_plan` consumers to `engine_plan`.
5. Delete Shannon workers/adapters/vendor code only after tests prove no
   production import remains.

Important framing:

- `claude -p` likely replaces stream-Shannon.
- `claude -p` may not replace tmux-Shannon.
- If tmux-Shannon behavior is load-bearing, build a sessionful Claude adapter
  or keep that track open until a replacement exists.

Shannon audit dispositions:

- reproduced in the new adapter
- moved into the shared facade
- obsoleted by stateless execution
- intentionally dropped with sign-off
- blocks cutover

Gate:

- Stream route has zero production imports of `workers.shannon_stream`.
- Tmux route has zero production imports of `workers.shannon`,
  `agent_adapters.shannon`, and `vendor/shannon` before deletion is declared.
- Historical `shannon_plan` remains readable.
- New production runs never write `shannon_plan`.

## Epic 6: Codex Review/Apply Governance

Goal: govern Codex, not replace its quality.

Scope:

- `agent review` backed by Codex
- `agent apply` backed by Codex or a governed patch backend
- facade-owned artifacts, telemetry, cost, timeout, failure handling
- seeded review corpus
- patch-conflict corpus
- explicit false-negative, false-positive, patch-success, and failure-diagnostic
  thresholds

Gate:

- No quality regression beyond declared thresholds.
- Any regression has a signed accepted tradeoff.
- Direct caller-level Codex review/apply is deleted only after governed paths
  meet the thresholds.

## Epic 7: Consumer Migration, Hardening, Deletion, And Installed-Artifact Proof

Goal: make the facade the default human/agent path, prevent bypasses, and
complete hardening/cutover path by path.

Scope:

- skills
- docs
- CI
- Makefiles
- shell snippets and recommended aliases
- cloud runner setup
- default profiles
- runbooks
- failure diagnostics
- deprecation warnings and telemetry
- examples that teach `agent ask`, `agent launch`, `agent fan`, `agent review`,
  and `agent apply`
- rewrite or delegate `subagent-launcher`, `sync-skills.sh`,
  `megaplan setup` skill targets, generated `_codex_skills` output, composed
  Claude/Codex skills, and cloud extra-skill sync so installed skills no longer
  teach or carry forbidden direct launchers after the deadline
- preserve human-facing command compatibility during the observation window:
  `python -m arnold_pipelines.megaplan ...`, `agentbox ...`, cloud/resident
  subcommands, setup/config commands, watchdog wrapper names, and documented
  onboarding commands must wrap or delegate before they are renamed or deleted
- generated docs and examples use a single facade-owned command template rather
  than embedding stale launcher commands
- archive profile note: archived `docs/archive/m5/**/profiles/*.toml` files are
  historical data and out of migration scope unless a live test or production
  loader references them
- OS-level enforcement for write-capable and web/browser profiles
- prompt-injection/context-boundary tests
- MCP/tool permission inventory only for existing load-bearing usage; do not
  introduce MCP as a new canonical dependency
- existing MCP config/token migration or containment from Hermes config paths,
  if any current workflow actually depends on it
- browser surface rebuild or deliberate removal from advertised toolsets
- web/search content-boundary enforcement and cost/rate-limit accounting
- tool registry integration with facade profile permissions
- config unification: project config available to runtime paths, unified
  `ConfigResolver` decision, and visibility for override actions
- worktree lifecycle unification: allocation, branch namespace, cleanup,
  protected branch/delete checks, stale/prunable detection, and patch rollback
- vendored Pi ecosystem supply-chain review
- Pi package wrapper/fork deletion gates: any adopted Pi package has
  installed-artifact scans, direct-launch scans, source-review sign-off, and a
  clear fork/wrap/vendor/reference decision
- installed-wheel and import-graph proof for `arnold/agent` vendoring,
  dynamic import shims, duplicate Shannon adapters, Hermes adapters,
  `run_agent`/`hermes_state` bare imports, and stale `.pyc`/RECORD references
- one-command install and runner reproducibility
- global cost ceiling and rate-limit admission
- incident runbooks
- statistical bakeoff
- installed-artifact scans
- runtime telemetry observation window

Metrics:

- percentage of newly touched workflows using `agent`
- direct-command bypass count from scans and telemetry
- time-to-diagnose seeded failure through facade vs direct CLI
- number of skills/docs still recommending forbidden launchers
- number of installed skill directories still carrying forbidden executable
  payloads

Deletion rule:

Every temporary compatibility path gets a CI deletion test and calendar deadline
when it is created.

Gate:

- Adoption target is explicit, not "agreed later."
- Critical skills and CI jobs use the facade.
- Critical generated docs and installed skill payloads use or point to the
  facade.
- Bypass count is trending down and no blocked workflow needs a direct launcher
  to function.
- Forbidden patterns absent from production callers.
- Forbidden patterns absent from installed artifacts.
- Runtime telemetry shows no forbidden path usage for the observation window.
- Security negative tests pass.
- `agent doctor` passes on a clean runner.
- Required CI runs full conformance, installed-wheel conformance,
  deleted-surface checks, profile parity tests, and allowlist glob expansion.

## Epic 8: Cloud, Resident, Watchdog, And AgentBox Surface Migration

Goal: bring unattended remote and infrastructure agent surfaces under the same
facade contract.

Why this is its own epic:

- Cloud CLI, resident Discord runtime, watchdog/repair loops, AgentBox handlers,
  Guardian scheduler, and incident bridge dispatch agents outside normal
  Megaplan phase execution.
- These paths have their own auth shims, tmux/session handling, state stores,
  cloud trust flags, repair budgets, and liveness contracts.
- Treating them as "docs/adoption" would leave the main production automation
  as the largest permanent bypass.

Scope:

- Inventory `cloud/cli.py`, cloud wrapper scripts, resident runtime/Discord
  tools, AgentBox adapter, Guardian scheduler, cloud discovery/recovery, and
  incident bridge.
- Inventory `agentbox` CLI commands (`run`, `status`, `logs`, `attach`,
  `cleanup`, `reconcile`, `guardian`, `doctor`, `services`, `notify`,
  `creds`, `bootstrap`, `version`) as a standalone operational surface.
- Inventory and reconcile `agentbox/credentials/` and `agentbox credential *`
  with facade-owned credential mediation.
- Define whether the AgentBox durable operation store delegates to the facade,
  integrates with it, or remains a separate source of truth with an explicit
  observation boundary.
- Inventory AgentBox locks, notifications, GitHub/CI status recording, and
  `agentbox_host` operation type.
- Inventory systemd units, timers, path units, template variables,
  `ensure-megaplan-watchdog`, and host/container lifecycle hooks.
- Inventory `scripts/megaplan_live_watchdog.py` separately from bash cloud
  wrappers.
- Evaluate `pi-agents-team` and `pi-chat` only as references for
  resident/background UX and worker patterns; do not let either become an
  operational state owner.
- Define an `agent cloud` / resident contract or explicitly define how existing
  cloud commands delegate through the facade.
- Route watchdog, repair-loop, progress-auditor, kimi-goal-operator, and
  meta-repair agent calls through facade run records, telemetry, cost, kill,
  and credential mediation.
- Reconcile `MEGAPLAN_TRUSTED_CONTAINER=1` and remote isolation bypass behavior
  with facade policy.
- Reconcile `CLOUD_WATCHDOG_*`, `ARNOLD_*`, `AGENTBOX_CONFIG`, and remote
  `/workspace/agentbox.yaml` config/env behavior with facade config and
  credential mediation.
- Migrate Claude refresh-token shims, Codex OAuth seeding, and cloud provider
  key delivery into facade-owned credential mediation.
- Ensure watchdog and incident bridge can observe facade-governed runs and
  diagnose repair failures from facade artifacts.

Gate:

- All cloud-wrapper agent calls route through the facade or have signed explicit
  scope-out.
- Watchdog/repair/auditor parity: no regression in repair success rate or
  time-to-repair.
- AgentBox/resident launches produce facade run records and are visible through
  `agent history` / `agent doctor`.
- Direct `launch_hermes_agent.py`, `codex exec`, or raw Claude calls are deleted
  from cloud wrappers, resident subagent dispatch, and AgentBox launch paths
  after parity.
- AgentBox doctor, services, credential push/test, notifications, GitHub/CI
  recording, and operation-store state are either facade-observable or
  explicitly scoped out with owner sign-off.

## Non-Negotiable Gates

1. Contract gate: M0 documents and executable conformance tests exist.
2. Adapter gate: adapter contract freeze before facade is considered stable.
3. Event/receipt gate: receipt, WorkerResult projection, `COST_RECORDED`,
   `LLM_CALL_END`, and event envelope schemas validate against current emitters
   and consumers.
4. Pipeline seam gate: AgentStep, PanelReviewerStep, dynamic fanout,
   model-step adapter registration, and model-seam hook registration have
   executable compatibility tests.
5. Skill bridge gate: `agent doctor --skills` passes against source,
   generated, installed, and Pi-sync skill surfaces, and no critical installed
   skill teaches forbidden direct launchers after its deadline.
6. Minimum enforcement gate: broad facade adoption waits for baseline security
   negative tests.
7. Hermes decomposition gate: `hermes:*` specs pass parity through canonical
   provider adapters before active Hermes runtime routing is deleted.
8. Fanout gate: N=50 parity-or-better before deleting `fan.py` caller path.
9. Shannon gate: zero unknown audit rows and no production Shannon imports after
   cutover.
10. Codex quality gate: labeled corpus thresholds pass before deleting direct
   Codex review/apply paths.
11. Adoption gate: explicit adoption and bypass metrics pass.
12. Rollback gate: emergency fallback is facade-owned, time-boxed, telemetered,
   and unable to become permanent.
13. Install gate: clean runner install and `agent doctor` pass before adoption
    expands to cloud/CI.
14. Deletion gate: each compatibility path has a CI deletion test and deadline.
15. Cloud surface gate: cloud/resident/watchdog/AgentBox agent calls route
    through the facade or are explicitly scoped out with owner sign-off.

## Final Judgement Calls

- Keep eight epics.
- Promote adoption/consumer migration to a real epic.
- Move minimum security/enforcement into the facade epic.
- Keep later security hardening as final cutover work.
- Add Skill Manifest Bridge as a first-class facade capability. Do not fork a
  skill framework; use existing `SKILL.md` content and Pi's native skill loader
  locations behind facade-owned routing and policy.
- Use Pi packages only as wrappers, forks, vendored snippets, or references
  behind the facade. Do not let a Pi package own routing, credentials, policy,
  run records, history, or deletion gates.
- Do not adopt MCP as a canonical migration dependency. Inventory and contain
  existing MCP only if it is already load-bearing; otherwise scope it out.
- Treat pipeline agent steps, model-seam hooks, event payloads, receipts, and
  WorkerResult projection as contracts, not incidental internals.
- Add Hermes decomposition as an explicit epic because `hermes:*` currently
  carries provider execution behavior, not just legacy launcher naming.
- Add cloud/resident/watchdog/AgentBox migration as an explicit epic because
  these are independent production agent surfaces.
- Split Shannon stream and tmux paths.
- Govern Codex first; do not try to replace Codex quality during this project.
- Treat `fan.py` internals as potentially valuable implementation material, but
  forbid `fan.py` as a caller-facing production path.
- Do not present this as "Pi replaces everything." Present it as "the shared
  surface owns the contract; engines are replaceable behind it."

## Summary

The project should proceed, but only as a split migration.

The first real deliverable is not Pi runtime replacement. It is a thin,
ergonomic, recording control surface that wraps the current world and produces
the evidence needed to replace it safely.
