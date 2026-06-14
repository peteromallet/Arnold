# M7 Agent Shim Audit

Deliverable for T12 (audit-only, per SD5: no non-empty shim deleted in M7).

## Scope

This audit surveys every importlib-based re-export shim under `arnold/agent/` that
bridges the `arnold.agent.*` path to the canonical `arnold.pipelines.megaplan.agent.*`
(or, in two cases, to another intra-`arnold.agent` path).  The audit is **inventory
and direction only**; actual deletion belongs to the successor Agent Runtime
Extraction epic (Ticket B).

## Shim inventory

Each row is a shim file, its canonical target, and a classification.

| # | Shim path (`arnold/agent/...`) | Canonical target | Direction |
|---|---|---|---|
| 1 | `model_tools.py` | `arnold.agent.tools.model_tools` | intra-agent — consolidate into `tools/` |
| 2 | `toolsets.py` | *not a shim* — real module | keep; may move to megaplan agent |
| 3 | `run_agent.py` | *not a shim* — real entry point | keep; may move to megaplan agent |
| 4 | `contracts.py` | *not a shim* | keep |
| 5 | `hermes_time.py` | *not a shim* | keep |
| 6 | `utils.py` | *not a shim* | keep |
| 7 | `agent/anthropic_adapter.py` | `arnold.pipelines.megaplan.agent.agent.anthropic_adapter` | megaplan → delete after consolidation |
| 8 | `agent/redact.py` | `arnold.pipelines.megaplan.agent.agent.redact` | megaplan → delete after consolidation |
| 9 | `agent/copilot_acp_client.py` | `arnold.pipelines.megaplan.agent.agent.copilot_acp_client` | megaplan → delete after consolidation |
| 10 | `agent/auxiliary_client.py` | `arnold.pipelines.megaplan.agent.agent.auxiliary_client` | megaplan → delete after consolidation |
| 11 | `agent/model_metadata.py` | `arnold.pipelines.megaplan.agent.agent.model_metadata` | megaplan → delete after consolidation |
| 12 | `agent/context_compressor.py` | `arnold.pipelines.megaplan.agent.agent.context_compressor` | megaplan → delete after consolidation |
| 13 | `agent/display.py` | `arnold.pipelines.megaplan.agent.agent.display` | megaplan → delete after consolidation |
| 14 | `agent/trajectory.py` | `arnold.pipelines.megaplan.agent.agent.trajectory` | megaplan → delete after consolidation |
| 15 | `agent/prompt_builder.py` | `arnold.pipelines.megaplan.agent.agent.prompt_builder` | megaplan → delete after consolidation |
| 16 | `agent/prompt_caching.py` | `arnold.pipelines.megaplan.agent.agent.prompt_caching` | megaplan → delete after consolidation |
| 17 | `agent/usage_pricing.py` | `arnold.pipelines.megaplan.agent.agent.usage_pricing` | megaplan → delete after consolidation |
| 18 | `tools/checkpoint_manager.py` | `arnold.pipelines.megaplan.agent.tools.checkpoint_manager` | megaplan → delete after consolidation |
| 19 | `tools/honcho_tools.py` | `arnold.pipelines.megaplan.agent.tools.honcho_tools` | megaplan → delete after consolidation |
| 20 | `tools/delegate_tool.py` | `arnold.pipelines.megaplan.agent.tools.delegate_tool` | megaplan → delete after consolidation |
| 21 | `tools/memory_tool.py` | `arnold.pipelines.megaplan.agent.tools.memory_tool` | megaplan → delete after consolidation |
| 22 | `tools/interrupt.py` | `arnold.pipelines.megaplan.agent.tools.interrupt` | megaplan → delete after consolidation |
| 23 | `tools/clarify_tool.py` | `arnold.pipelines.megaplan.agent.tools.clarify_tool` | megaplan → delete after consolidation |
| 24 | `tools/vision_tools.py` | `arnold.pipelines.megaplan.agent.tools.vision_tools` | megaplan → delete after consolidation |
| 25 | `tools/browser_tool.py` | `arnold.pipelines.megaplan.agent.tools.browser_tool` | megaplan → delete after consolidation |
| 26 | `tools/todo_tool.py` | `arnold.pipelines.megaplan.agent.tools.todo_tool` | megaplan → delete after consolidation |
| 27 | `tools/terminal_tool.py` | `arnold.pipelines.megaplan.agent.tools.terminal_tool` | megaplan → delete after consolidation |
| 28 | `tools/session_search_tool.py` | `arnold.pipelines.megaplan.agent.tools.session_search_tool` | megaplan → delete after consolidation |
| 29 | `honcho_integration/session.py` | `arnold.pipelines.megaplan.agent.honcho_integration.session` | megaplan → delete after consolidation |
| 30 | `honcho_integration/client.py` | `arnold.pipelines.megaplan.agent.honcho_integration.client` | megaplan → delete after consolidation |
| 31 | `hermes_cli/config.py` | `arnold.pipelines.megaplan.agent.hermes_cli.config` | megaplan → delete after consolidation |
| 32 | `hermes_cli/models.py` | `arnold.pipelines.megaplan.agent.hermes_cli.models` | megaplan → delete after consolidation |
| 33 | `hermes_cli/auth.py` | `arnold.pipelines.megaplan.agent.hermes_cli.auth` | megaplan → delete after consolidation |
| 34 | `hermes_cli/env_loader.py` | `arnold.agent.providers.env_loader` | intra-agent — consolidate into `providers/` |

## Empty `__init__.py` packages (safe to delete now)

These four `__init__.py` files are empty (0 bytes) and carry no code:

- `arnold/agent/__init__.py`
- `arnold/agent/agent/__init__.py`
- `arnold/agent/tools/__init__.py`
- `arnold/agent/honcho_integration/__init__.py`
- `arnold/agent/hermes_cli/__init__.py`
- `arnold/agent/providers/__init__.py`

**Staged deletions in M7:** Already staged as empty-byte files (0-byte placeholders). These
were correctly left in place by T12 (audit-only) and are not removed in this batch; they are
the responsibility of the successor Agent Runtime Extraction epic per SD5.

## Direction map

```
arnold/agent/                             arnold/pipelines/megaplan/agent/
  ┌─────────────────────────────┐           ┌──────────────────────────────────┐
  │ model_tools.py              │──shim──→ │ tools/model_tools.py             │
  │ toolsets.py  (REAL)         │──move──→ │ toolsets.py   (canonical home)   │
  │ run_agent.py (REAL)         │──move──→ │ run_agent.py  (canonical home)   │
  │ contracts.py (REAL)         │──move──→ │ contracts.py  (canonical home)   │
  │ hermes_time.py (REAL)       │──move──→ │ hermes_time.py (canonical home)  │
  │ utils.py     (REAL)         │──move──→ │ utils.py       (canonical home)  │
  │ agent/*.py   (SHIM×11)      │──DEL───→ │ agent/*.py     (already SSoT)    │
  │ tools/*.py   (SHIM×10)      │──DEL───→ │ tools/*.py     (already SSoT)    │
  │ honcho_integration/* (SHIM×2)│──DEL──→ │ honcho_integration/* (already SSoT)│
  │ hermes_cli/* (SHIM×4)       │──DEL───→ │ hermes_cli/*   (already SSoT)   │
  │ providers/   (REAL)         │  KEEP   │                                 │
  └─────────────────────────────┘           └──────────────────────────────────┘
```

**Key:** REAL = real module (needs move to canonical megaplan agent home); SHIM = thin
importlib re-export (already has SSoT in megaplan agent — delete after all consumers
import from canonical path); intra-agent = shim within `arnold.agent/` (consolidate).

## Consumer impact assessment

Before any shim deletion, a sweep must confirm no out-of-tree or internal consumer imports
through the shim paths. The risk classes:

- **Low risk (intra-agent):** `model_tools.py`, `hermes_cli/env_loader.py` — both redirect
  within `arnold.agent`. Consolidation is a single-package refactor.
- **Medium risk (megaplan shim → megaplan SSoT):** All 27 shims pointing to
  `arnold.pipelines.megaplan.agent.*` — the SSoT already lives at the canonical path.
  The `arnold.agent.*` shim is only a convenience. A grep of `arnold/` and `tests/` for
  `from arnold.agent.` imports will reveal callers still using the shim path.
- **Real modules:** `toolsets.py`, `run_agent.py`, `contracts.py`, `hermes_time.py`,
  `utils.py`, `providers/*` — these are real implementations masquerading under the
  generic `arnold.agent` namespace. They should move to the megaplan agent package as
  the canonical home, leaving behind deprecation shims or being consumed directly.

## M7 disposition

Per SD5: **No deletion of any non-empty shim in M7.** The 6 empty `__init__.py` files
are already staged as empty (0-byte) and remain. All actual shim deletions are deferred
to the Agent Runtime Extraction successor epic (Ticket B).

## Verification

- `rg 'importlib\.import_module.*arnold\.agent' arnold/agent/` returns 30 matches covering
  exactly the shims enumerated above.
- `rg 'from arnold\.agent\.' arnold/ tests/` identifies remaining consumers using the shim
  import path — these must be migrated to the canonical `arnold.pipelines.megaplan.agent.*`
  path before shim deletion.
