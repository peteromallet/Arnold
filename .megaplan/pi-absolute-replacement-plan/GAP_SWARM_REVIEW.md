# Gap Swarm Review

Date: 2026-07-04  
Target plan: `FINAL_UNIFIED_AGENT_SURFACE_PLAN.md`  
Raw outputs:

- `/tmp/agent-surface-gap-swarm/known-results/`
- `/tmp/agent-surface-gap-swarm/broad-results/`

## Method

Ran two DeepSeek V4 Pro fanouts:

- 7 targeted subagents for known suspicious areas
- 10 broader swarm agents for unknown missing surfaces

All 17 completed successfully.

## Main Judgement

The plan was materially improved, but one major missing epic remained:

> Cloud, resident, watchdog, repair-loop, Guardian, and AgentBox systems are
> independent production agent surfaces. They cannot be buried inside adoption
> cleanup.

The final plan now adds **Epic 8: Cloud, Resident, Watchdog, And AgentBox
Surface Migration**.

## Known-Area Findings

### Profile Migration

Findings:

- There are two profile loading subsystems with overlapping names and different
  validation behavior.
- Existing system profiles contain many `hermes:*` specs.
- Pipeline-local profiles use `extends = "system:partnered"` and dotted keys.
- `KNOWN_AGENTS` still includes old route concepts such as `hermes` and
  `shannon`.

Plan changes:

- Add `profile-inventory.md`.
- Add `profile-loader-contract.md`.
- Add profile parity tests for every system and pipeline-local profile.
- Add `extends` integrity tests.
- Ensure `agent profiles` uses the canonical loader, not a new third parser.

### Credentials And Key Pool

Findings:

- Key behavior is spread across KeyPool, adapter env reads, preflight, user
  config, `~/.hermes/.env`, and provider-specific files.
- `resolve_model()` currently combines provider routing, key lookup, base URL
  resolution, and fallback policy.
- `~/.hermes/.env` is invisible to some adapters and preflight paths.
- OpenRouter, Zhipu, Kimi/Moonshot aliases, and governor charging need explicit
  parity.

Plan changes:

- Add `credential-source-inventory.md`.
- Add `credential-resolution-flow.md`.
- Add provider-router contract before deleting Hermes runtime routes.
- Bridge or deprecate `~/.hermes/.env` deliberately.

### Rate Limits, Retries, Fallbacks

Findings:

- Current rate-limit handling is not generic: some provider 429s are permanent,
  some trigger OpenRouter fallback, some cool down keys.
- `retry_after` is extracted but not used as backoff.
- Execute phase has different retry semantics because it can mutate state.
- Gate checks may classify some provider failures as operationally
  unverifiable.

Plan changes:

- Old error taxonomy must include retry budgets, rate-limit permanence,
  provider fallback maps, and `OPERATIONAL_UNVERIFIABLE` behavior.
- Adapter error taxonomy must include status code, retry-after, provider error
  code, retryability, and phase mutability.

### Prep/Fanout Routing

Findings:

- `prep_models`, `tier_models`, complexity routing, and fanout routing are
  deeply tied to current profile semantics.
- Fanout cannot be treated only as process scheduling; it is also profile and
  phase routing.

Plan changes:

- Add profile/tier/prep parity tests.
- Fanout measurements must include routing parity and cost attribution.

### Vendor Resolution

Findings:

- `premium`, `--vendor`, `--critic cross`, `--phase-model`, and `--depth` form a
  transformation pipeline.
- Reordering this pipeline would silently change behavior.
- Credential detection for premium route availability imports old runtime
  modules.

Plan changes:

- Add a rewrite-order contract test.
- Extract premium credential availability behind facade-owned credential
  mediation.
- Add vendor-swap table tests.

### Pipeline-Specific Profiles

Findings:

- Pipeline-local profiles bypass the same validation as system profiles.
- Archive profiles contain live-looking specs and could be copied back into
  active paths.
- `ConfigResolver`/profile agnosticism work is relevant and unfinished.

Plan changes:

- Add pipeline-local profile inventory.
- Decide canonical profile loading path.
- Quarantine archive profiles or ensure loaders ignore them.

### Hermes Execution Internals

Findings:

- Hermes is an execution core: `AIAgent`, tools, streaming, structured output,
  session DB, key pool, sandboxing, and cost/token extraction.
- `sys.path` injection and vendored runtime imports are load-bearing risks.

Plan changes:

- Add Hermes runtime inventory, tool-dispatch audit, streaming contract,
  structured-output matrix, provider parity suite, and syspath removal plan.

## Broad Swarm Findings

### Cloud / Resident / AgentBox

Findings:

- Cloud CLI, resident Discord runtime, AgentBox handler, Guardian scheduler,
  watchdog/repair loops, progress auditor, and incident bridge are independent
  agent surfaces.
- They dispatch agents directly through cloud wrappers, `launch_hermes_agent.py`,
  `codex exec`, and other paths.

Plan change:

- Add **Epic 8**.

### Artifact Consumers

Findings:

- Existing content types include plan, receipt, capsule, delta, gate-signal,
  review-output, execution-evidence, and state-artifact.
- Receipts inline `shannon_plan`, worker metadata, auth metadata, hashes,
  drift, and metrics.
- Supervisor state, event journals, effect ledgers, evidence contracts, and
  deletion inventory already exist.

Plan changes:

- Add receipt/content/event/effect-ledger contracts to Epic 1.
- Integrate with existing deletion inventory rather than creating a parallel
  list.

### Worktree / Git

Findings:

- Multiple independent worktree systems exist with different cleanup and branch
  safety semantics.
- Some cleanup paths use force-delete behavior.
- Patch application paths have rollback hazards.

Plan changes:

- Add `worktree-lifecycle-contract.md`.
- Add branch/worktree deletion-hazard audit.
- Add patch rollback requirements to Codex/apply governance.

### MCP / Browser / Web / Search

Findings:

- Browser tools are advertised but partially stubbed.
- MCP is a large integration surface with config, OAuth, subprocesses, sampling,
  and credential stripping.
- Web tools have SSRF/domain checks but lack content-boundary enforcement,
  tool-call cost/rate-limit accounting, and prompt-injection handling.

Plan changes:

- Add browser rebuild-or-remove decision.
- Add MCP config/token migration and telemetry.
- Add tool registry integration with facade permissions.
- Move web/search content-boundary design earlier.

### CI / Conformance

Findings:

- Existing conformance infrastructure is broader than CI currently runs.
- Installed-wheel proof is incomplete.
- Deleted-surface inventory already exists and must be reused.
- Some allowlists and compatibility lists need cleanup before they can enforce
  final deletion.

Plan changes:

- Epic 7 must require full conformance, installed-wheel conformance,
  deleted-surface checks, profile parity tests, and allowlist glob expansion.

### Config Overlays

Findings:

- Env/config precedence is fragmented: `~/.hermes/.env`, project `.env`, user
  config, `config.json`, `config.toml`, `MEGAPLAN_*` env reads, and override
  actions.
- Project config is not consistently available to runtime paths.
- Shannon may use OAuth/subscription credentials that `claude -p` may not
  consume.

Plan changes:

- Add `config-overlay-inventory.md`.
- Add project config unification and override telemetry.
- Shannon audit must answer OAuth-to-`claude -p` feasibility.

### Cost / Observability

Findings:

- There is substantial per-plan and pipeline-level cost infrastructure, but no
  facade-level cross-run history store.
- Cost ceiling enforcement and pricing freshness need to move earlier.

Plan changes:

- Add `engine-observability-contract.md`.
- Move global cost ceiling design into Epic 2.
- Add pricing freshness to `agent doctor`.

### Skills / Docs

Findings:

- `subagent-launcher/SKILL.md` is the highest-impact bypass manual.
- Multiple skills and cloud docs teach direct launchers.
- The facade cannot be adopted until replacement commands exist.

Plan changes:

- Consumer/adoption epic must include an explicit skills/docs migration tracker.
- Do not rewrite skills until `agent ask` / `agent fan` exist.

## Final Epic Count

The plan is now **8 epics**:

1. Discovery, contracts, and evaluation baselines
2. Thin facade, recording, and minimum enforcement
3. Provider execution and Hermes decomposition
4. Fanout feasibility and adapter design
5. Claude/Shannon retirement
6. Codex review/apply governance
7. Consumer migration, hardening, deletion, and installed-artifact proof
8. Cloud, resident, watchdog, and AgentBox surface migration

## Bottom Line

The suspicion was correct: Hermes decomposition was not the only hidden missing
area. The largest missed area was remote/unattended infrastructure agents. The
other findings mostly refine existing epics by making implicit contracts
explicit.
