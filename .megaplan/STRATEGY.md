---
schema_version: megaplan-strategy-v1
---

# Repository Strategy

## Mission

Arnold builds intelligent pipelines out of many coordinated models. Its first tool, Megaplan, is a planning and execution harness that makes LLM-driven software development systematically robust by decomposing work into independently checked phases, each running on the cheapest model that can do it well.

## Principles

- Structure makes LLMs robust — decompose, scope, and independently check every phase.
- Use the cheapest capable model per component; reserve premium models for adjudication and genuinely hard work.
- Typed Markdown is authoritative; generated JSON is a disposable projection.
- Strategy entries point to artifacts, never copy bodies or lifecycle state.

## Architecture Direction

- Pipeline phases are explicit stages with typed I/O contracts.
- Model routing is profile-driven and vendor-neutral at the agent-spec level.
- Run state is durable and recoverable; custody and audit trails are first-class.
- The strategy contract separates stable direction from the living roadmap.

## Constraints

- Must work in dirty worktrees without cloud state for local validation.
- Ticket identity is a ULID; epic identity is a canonical initiative slug.
- The executable roadmap vocabulary is exactly `ticket` and `epic`.

## Non-Goals

- Replacing existing ticket/epic artifact storage with strategy entries.
- Making the generated projection JSON independently authoritative.
- Including every open ticket in the roadmap.

## Now

- [epic:repository-strategy-roadmap] Repository strategy roadmap

## Next

- [ticket:01KTH21DTP1HR3ER5W7SRRJVV5] Prevent stale git pre-commit hook rot

## Later

- [ticket:01KTH21EC489596QWBC3419JC9] Add compact megaplan monitor command for plan and chain health
