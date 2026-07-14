---
schema_version: megaplan-strategy-v1
---

# Repository Strategy

> This file belongs at `.megaplan/initiatives/<slug>/STRATEGY.md` and is
> created with `megaplan strategy init` or `megaplan initiative new <slug> --strategy`.
> The frontmatter `schema_version` MUST remain `megaplan-strategy-v1`.
> Roadmap entries use the narrow bullet grammar described in CONTRACT.md.
>
> **Important rules:**
> - The Markdown file is authoritative. Generated JSON (`.megaplan/strategy.projection.json`)
>   is a disposable projection — never edit it directly. Delete it and rebuild with
>   `megaplan strategy project --write`.
> - Strategy entries are **pointers** to artifacts, not containers. Never copy ticket/epic
>   body text, lifecycle status, plan details, or completion evidence into strategy entries.
> - Roadmap visibility is **opt-in**. Tickets are backlog artifacts that only appear in the
>   strategy when explicitly added via `ticket new --roadmap-horizon`, `strategy add`, or
>   a direct Markdown edit. Not every open ticket belongs in the roadmap.

## Mission

<!-- One to three sentences describing the repository's core purpose and
     what success looks like. Keep this stable — it should not change
     sprint to sprint. -->

## Principles

<!-- Guiding principles that shape technical and process decisions.
     One principle per line; free-form Markdown is fine. -->

## Architecture Direction

<!-- High-level architectural intent: patterns, boundaries, technology
     choices that define the repo's shape. -->

## Constraints

<!-- Hard constraints: runtime, compatibility, security, compliance, or
     operational requirements that must be satisfied. -->

## Non-Goals

<!-- Explicitly out-of-scope work. Helps prevent scope creep and makes
     it clear what the strategy does NOT promise. -->

## Now

<!-- Work actively in progress or starting this cycle.
     One entry per line. ONLY the narrow bullet grammar is valid:

     - [ticket:<ULID>] <display title>
     - [epic:<initiative-slug>] <display title>

     Example:
     - [ticket:01KT50AZRMK5X890TQ565DDB5V] Fix authentication timeout
     - [epic:repository-strategy-roadmap] Repository strategy roadmap
-->

## Next

<!-- Work queued for the next cycle. Same grammar as Now. -->

## Later

<!-- Work recognized as strategically important but not yet scheduled.
     Same grammar as Now. -->
