---
id: 01KTPVVVVV002AGENTRUNTIME
title: Agent Runtime Extraction — untangle bidirectional shim topology, consolidate canonicals, delete shims
status: open
source: agent
tags:
- megaplan
- agent
- architecture
- successor-epic
- shim-cleanup
codebase_id: null
created_at: '2026-06-10T06:30:00.000000+00:00'
last_edited_at: '2026-06-10T06:30:00.000000+00:00'
epics: []
---

# Agent Runtime Extraction — Successor Epic

M7 catalogued the `arnold/agent/` → `arnold/pipelines/megaplan/agent/` shim topology
(see `docs/arnold/m7-agent-shim-audit.md` for the full inventory). This epic untangles
that bidirectional topology, consolidates all agent code under the canonical
megaplan agent package, and deletes the shims.

## Reference

Full audit: `docs/arnold/m7-agent-shim-audit.md` (T12 deliverable).

## Action items

### 1. Migrate real modules to canonical home

These modules are real implementations currently living under the generic
`arnold/agent/` namespace. They should move to the megaplan agent package:

| Module | Current path | Canonical target |
|---|---|---|
| `toolsets.py` | `arnold/agent/toolsets.py` | `arnold/pipelines/megaplan/agent/toolsets.py` |
| `run_agent.py` | `arnold/agent/run_agent.py` | `arnold/pipelines/megaplan/agent/run_agent.py` |
| `contracts.py` | `arnold/agent/contracts.py` | `arnold/pipelines/megaplan/agent/contracts.py` |
| `hermes_time.py` | `arnold/agent/hermes_time.py` | `arnold/pipelines/megaplan/agent/hermes_time.py` |
| `utils.py` | `arnold/agent/utils.py` | `arnold/pipelines/megaplan/agent/utils.py` |
| `providers/*` | `arnold/agent/providers/` | `arnold/pipelines/megaplan/agent/providers/` |

After relocation, leave deprecation shims at the old paths that emit
`DeprecationWarning` and re-export from the canonical location (same pattern
as `CrossCuttingEnvelope` → `RunEnvelope`).

### 2. Consolidate intra-agent shims

Two shims redirect within `arnold.agent/` rather than to the megaplan agent package:

| Shim | Target | Action |
|---|---|---|
| `arnold/agent/model_tools.py` | `arnold.agent.tools.model_tools` | Migrate callers to `arnold.agent.tools.model_tools` directly; delete shim after consumer migration. |
| `arnold/agent/hermes_cli/env_loader.py` | `arnold.agent.providers.env_loader` | Migrate callers to `arnold.agent.providers.env_loader` directly; delete shim after consumer migration. |

### 3. Delete megaplan-agent shims (27 files)

These 27 shims are thin importlib re-exports where the SSoT already lives at
`arnold.pipelines.megaplan.agent/*`. After confirming no consumers import through
the shim path (grep `from arnold.agent.` in `arnold/` and `tests/`), delete each
shim file:

**`arnold/agent/agent/` (11 shims):**
`anthropic_adapter.py`, `redact.py`, `copilot_acp_client.py`, `auxiliary_client.py`,
`model_metadata.py`, `context_compressor.py`, `display.py`, `trajectory.py`,
`prompt_builder.py`, `prompt_caching.py`, `usage_pricing.py`

**`arnold/agent/tools/` (10 shims):**
`checkpoint_manager.py`, `honcho_tools.py`, `delegate_tool.py`, `memory_tool.py`,
`interrupt.py`, `clarify_tool.py`, `vision_tools.py`, `browser_tool.py`,
`todo_tool.py`, `terminal_tool.py`, `session_search_tool.py`

**`arnold/agent/honcho_integration/` (2 shims):**
`session.py`, `client.py`

**`arnold/agent/hermes_cli/` (3 shims):**
`config.py`, `models.py`, `auth.py`

### 4. Delete empty `__init__.py` packages

These 6 files are already 0-byte (staged empty in M7):

- `arnold/agent/__init__.py`
- `arnold/agent/agent/__init__.py`
- `arnold/agent/tools/__init__.py`
- `arnold/agent/honcho_integration/__init__.py`
- `arnold/agent/hermes_cli/__init__.py`
- `arnold/agent/providers/__init__.py`

### 5. Verify no remaining consumers

After all shim deletions and real-module relocations:

- `rg 'from arnold\.agent\.' arnold/ tests/` returns zero matches
- `rg 'import arnold\.agent\.' arnold/ tests/` returns zero matches (except
  imports from `arnold.pipelines.megaplan.agent` which is the canonical home)
- All agent tests pass under the canonical `arnold.pipelines.megaplan.agent` path

## Out of scope

- Extracting a generic agent runtime from the megaplan agent — this epic
  consolidates agent code into the megaplan plugin; a separate extraction
  of genuinely generic agent substrate (model routing, tool dispatch,
  sandbox isolation) would be a distinct follow-up.
- Any change to `arnold/pipelines/megaplan/agent/` code behavior — this is
  a relocation-only epic.

## Suggested touchpoints

- `arnold/agent/` — shim deletions and real-module deprecation shims
- `arnold/pipelines/megaplan/agent/` — canonical home for all agent code
- `arnold/pipelines/megaplan/agent/__init__.py` — may need updated imports
- All test files under `tests/` that import from `arnold.agent.*`
- `docs/arnold/m7-agent-shim-audit.md` — reference audit document
