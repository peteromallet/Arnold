# Codex Pi Extension Review

Date: 2026-07-04

Input:

- `FINAL_UNIFIED_AGENT_SURFACE_PLAN.md`
- `LONGSHOT_SWARM_REVIEW.md`
- `GAP_SWARM_REVIEW.md`
- current Pi package candidates from `pi.dev`
- user constraint: default to **not using MCP** unless a strong argument exists

Raw Codex output:

- `CODEX_PI_EXTENSION_REVIEW.raw.txt`

## Verdict

Do not change the core architecture. Arnold should still own routing, policy,
credentials, run records, deletion gates, profile semantics, and fanout
contracts.

Pi packages are useful as references, spikes, or wrapped engine-side helpers
behind the Arnold facade. They should not become replacement control planes.

## Package Verdicts

| Package | Verdict | Plan use |
| --- | --- | --- |
| `pi-subagents` | Wrap or fork after source review | Best candidate for Epic 4 fanout and `subagent-launcher` migration. Benchmark against `fan.py`; do not let it own run records or policy. |
| `@hypabolic/pi-hypa` | Vendor small pieces or use as reference | Useful for noisy shell/tool output compression and recoverable evidence in Epics 1, 2, and 7. Arnold schemas remain authoritative. |
| `pi-web-providers` | Wrap as optional provider layer | Useful for web/search provider routing, but only behind facade permissions, cost/rate limits, and content-boundary enforcement. |
| `pi-web-access` | Wrap selectively | Useful for browser/web corpora and research tasks. High-risk surface due to GitHub cloning, PDF/video/web extraction; needs strict provenance, SSRF, prompt-injection, and cost gates. |
| `pi-sub-agent` | Spike/reference only | May inform isolated subprocess child-agent design. Prefer only if simpler/better than `pi-subagents` after source review. |
| `@tintinweb/pi-subagents` | Spike/reference only | Relevant for Claude-Code-style subagents, but compare against `pi-subagents`, `pi-sub-agent`, and Arnold `fan.py` before adoption. |
| `pi-agents-team` | Reference for Epic 8 only | Background worker/team ideas may inform resident/watchdog/AgentBox. Do not import another operational state owner. |
| `context-mode` | Reference only | FTS5/search ideas may be useful, but MCP orientation makes it a poor canonical dependency. |
| `pi-chat` | Do not use unless resident UX demands it | Only relevant for chat/resident UX, not the facade. |
| `pi-mcp-adapter` | Do not use | MCP adds config, OAuth, subprocess, token, and permission complexity without clear benefit for this migration. |

## Epic Deltas

- Epic 1: add a Pi package source-review matrix covering ownership risk,
  credentials, subprocesses, network behavior, artifact model, deletion impact,
  license, and supply-chain status.
- Epic 2: allow thin experimental wrappers for `pi-subagents`,
  `pi-web-providers`, and `pi-web-access` only if they emit Arnold run records
  and use Arnold credential mediation.
- Epic 4: benchmark `pi-subagents`, `pi-sub-agent`, and
  `@tintinweb/pi-subagents` against `fan.py` at N=8/32/50/100.
- Epic 7: add installed-artifact scans and deletion gates for any adopted Pi
  package wrapper/fork.
- Epic 8: evaluate `pi-agents-team` and maybe `pi-chat` only as references for
  resident/background patterns.

## MCP Decision

Do not adopt MCP as part of the canonical path. Do not use `pi-mcp-adapter`.

The plan should narrow MCP language to:

- inventory existing MCP usage;
- contain it behind facade permissions if already load-bearing;
- otherwise scope it out.

MCP is not justified as a new dependency for this migration.
