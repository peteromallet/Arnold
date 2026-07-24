---
schema_version: megaplan-strategy-v1
---

## Mission

Provide a reliable, self-service platform for planning, executing, and
governing AI-driven work across multiple repositories with minimal human
intervention.

## Principles

- **Determinism over convenience**: Parsers and serializers must produce
  byte-for-byte equivalent output on round-trip.
- **Identity over display**: Artifact identity is the `(type, ref)` pair;
  display titles are mutable and advisory.
- **Fail closed**: Missing or ambiguous data is a hard error, not a silent
  default.

## Architecture Direction

Adopt a layered architecture where the strategy document is the single
source of truth.  Downstream projections (JSON, views) are disposable and
must be regeneratable from the canonical Markdown.

## Constraints

- Python 3.11+.
- YAML frontmatter only; no TOML or JSON.
- Roadmap bullets must use the narrow `- [type:ref] title` grammar.
- No artifact bodies or lifecycle-status fields in the strategy model.

## Non-Goals

- Automatic issue tracker synchronization.
- Real-time dashboard.
- Multi-repo strategy federation (v1 is single-repo).
- Migration from legacy plan formats.

## Now

- [ticket:01KT50AZRMK5X890TQ565DDB5V] Fix authentication timeout in gateway
- [epic:repository-strategy-roadmap] Implement typed strategy contract and validator

## Next

- [ticket:01KT50AZRMK5X890TQ565DDB5W] Add rate-limiting middleware
- [epic:observability-pipeline] Build observability pipeline for agent execution traces

## Later

- [ticket:01KT50AZRMK5X890TQ565DDB5X] Migrate legacy config to new schema
- [epic:multi-tenant-isolation] Introduce tenant-level isolation for shared runners
