# Long-Shot Surface Swarm Review

Date: 2026-07-04

This review is the second broad exploratory sweep after the targeted gap swarm.
It used 12 DeepSeek subagents to search for obscure or long-tail agent launch,
profile, skill, CLI, artifact, cloud, credential, test, and import surfaces that
could invalidate the unified agent-control plan.

Raw inputs and outputs:

- Briefs: `longshot-swarm/briefs/`
- Results: `longshot-swarm/results/`
- Aggregate report: `longshot-swarm/results/_report.json`

## Execution Summary

- Agents: 12
- Status: 12 succeeded, 0 failed
- Model: `deepseek:deepseek-v4-pro`
- Toolsets: file, web, terminal
- Wall clock: 320.8 seconds
- Sum agent time: 1650.07 seconds

## Judgement

The swarm did **not** find a reason to add a ninth epic. It did find enough
missing detail that the canonical plan needed strengthening in four areas:

1. Skills are an execution surface, not just documentation.
2. Pipeline agent steps and model-seam hooks are compatibility contracts.
3. Event, receipt, and WorkerResult payloads need executable schemas.
4. AgentBox/cloud/resident includes more independent state, credential, and
   lifecycle systems than the plan named.

## Durable Findings

### Skill And Doc Distribution

The repo has multiple skill distribution paths:

- `sync-skills.sh`
- `megaplan setup` / `_GLOBAL_TARGETS`
- generated skills from `scripts/generate_arnold_docs.py`
- globally installed Claude/Codex/Agents/Hermes skill directories
- cloud wrapper sync of extra skills
- Hermes Skills Hub and `~/.hermes/skills`

The `subagent-launcher` skill is itself a launch surface because it teaches
direct `launch_hermes_agent.py`, `fan.py`, `codex exec`, and Claude launcher
commands. Directory-symlinked skills also carry executable payloads, not only
`SKILL.md` text.

Plan consequence: add a **Skill Manifest Bridge** to Epic 2 and make skill
distribution/rewrites a hard Epic 7 migration item. Existing skill docs remain
readable, but generated and installed skill payloads must route through the
facade after cutover.

### Pi Skill Integration

External research showed Pi already supports native Agent Skills using
`SKILL.md` files in Pi skill directories such as `~/.pi/agent/skills/`,
project `.pi/skills/`, and `.agents/skills/`. The plan should not fork a
separate skill framework. Arnold should add metadata and sync/generation around
existing `SKILL.md` content, then install or project it into Pi's native skill
loader where useful.

Plan consequence: use a bridge, not a fork. The shared facade remains the route
owner; Pi's skill loader is an engine capability behind the facade.

References used for the Pi skill judgement:

- `https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md`
- `https://github.com/tintinweb/pi-subagents`
- `https://github.com/shalomb/agent-skills`

### Pipeline Runtime Contracts

The neutral pipeline layer has agent-like surfaces outside the obvious
Megaplan worker paths:

- `AgentStep` and `PanelReviewerStep` accept an injected `_worker` callable.
- `model_seam.py` has import-time hook registries.
- `pattern_dynamic.py` supports dynamic fanout and specialization.
- `StepInvocationAdapterRegistry` has a reserved `"model"` slot.
- native graph projection maps fanout instructions into runtime stages.

Plan consequence: Epic 2 must formalize these as compatibility contracts, not
leave them as duck-typed implementation details.

### Event, Receipt, And Telemetry Payloads

The swarm found schema drift risk:

- `Receipt` omits fields that `build_receipt` emits: `shannon_plan`,
  `worker_channel`, `auth_channel`, and `auth_metadata`.
- `COST_RECORDED` has production consumers but no typed payload schema.
- `LLM_CALL_END` consumers read fields that are not consistently emitted.
- WorkerResult-to-AgentResult projection is tested in fragments, not as a
  unified cross-adapter parity contract.

Plan consequence: Epic 1 must add receipt/event/telemetry payload schemas and
tests before runtime replacement.

### CLI And Human Surfaces

Long-standing operator surfaces must be wrapped before replacement:

- `python -m arnold_pipelines.megaplan ...`
- `agentbox ...`
- `python -m arnold_pipelines.megaplan cloud ...`
- `python -m arnold_pipelines.megaplan resident ...`
- `sync-skills.sh`
- generated docs teaching `arnold workflow ...`
- scripts such as `megaplan_live_watchdog.py`, `cloud_hot_upload.py`, and
  conformance/doc generators

Plan consequence: keep existing verbs working during the observation window,
but route them internally through the facade where they launch or govern agents.

### Cloud, Resident, AgentBox, And Watchdogs

Epic 8 already existed, but the swarm found missing named sub-surfaces:

- `agentbox/credentials/` is a separate credential subsystem.
- `agentbox` CLI is a standalone command surface.
- AgentBox durable operations store may remain a parallel source of truth.
- `resident/subagent.py` calls `launch_hermes_agent.py` directly.
- systemd units and `ensure-megaplan-watchdog` are lifecycle surfaces.
- `scripts/megaplan_live_watchdog.py` is separate from bash watchdog wrappers.
- AgentBox notifications and GitHub/CI status recording should integrate with
  facade observability or be explicitly scoped out.

Plan consequence: strengthen Epic 8 rather than create a new epic.

### Credentials, Config, And Overrides

The plan already covered key pools and `~/.hermes/.env`, but it missed:

- `HERMES_*` OAuth/config env vars
- `CLOUD_WATCHDOG_*` and `ARNOLD_*` wrapper env vars
- `~/.hermes/config.yaml`
- `~/.hermes/auth.json`
- `~/.hermes/.anthropic_oauth.json`
- `~/.config/megaplan/config.toml`
- `auto_improve/api_keys.json`
- `/workspace/agentbox.yaml`
- env alias/suffix behavior such as `KIMI_API_KEY_2`
- override order for `--vendor`, `--critic`, `--phase-model`, `--depth`,
  `--deepseek-provider`, and adaptive critique flags

Plan consequence: add explicit inventory docs and rewrite-order tests to Epic 1.

### Import And Vendoring Boundaries

Hermes is not only a launcher; much of it is vendored under `arnold/agent/`.
There are multiple import paths for `AIAgent`, `SessionDB`, Shannon adapters,
Hermes adapters, and fanout helpers. Deletion needs installed-wheel scans and
import-graph checks, not only source grep.

Plan consequence: Epic 7's installed-artifact proof remains necessary and must
include `arnold/agent` vendoring/import boundaries.

## Non-Findings

Archived profiles under `docs/archive/m5/` are historical data, not an external
compatibility surface. Their agent spec syntax is still parseable, but their
stage names are archive-local. No migration tooling is required for them beyond
documenting that they are out of scope.

The stale deliberation profile test is a cleanup issue, not a blocker for this
plan.
