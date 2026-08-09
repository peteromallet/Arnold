---
type: brief
slug: m3-operator-ergonomics
title: CLI and Operator Ergonomics
epic: repository-strategy-roadmap
created_at: '2026-07-13T21:35:51.654886+00:00'
---

# CLI and Operator Ergonomics

## Outcome

Expose the strategy contract and lifecycle through a coherent Megaplan CLI that
supports direct human Markdown editing and safe convenience operations. Tickets
can be created, given a horizon, moved, validated, projected, or promoted
without lossy rewrites or bypassing initiative search and identity rules.

## Scope

### In scope

- Add/register strategy commands for initialization/template creation,
  validation, human-readable show/list, and projection rebuild/export.
- Add lossless roadmap mutations for add/remove/move between Now/Next/Later,
  keyed by `type + ref`, with optimistic conflict/error behavior.
- Define how `ticket new` feeds the roadmap (explicit opt-in horizon or a
  separate add command), while preserving the ability to create non-strategic
  tickets.
- Add a promotion command/workflow that searches initiatives first, creates a
  canonical initiative only when needed, records relationships, and updates the
  strategy according to M2's chosen transition policy.
- Restore/align ticket CLI parser registration with the existing handlers and
  canonical `python -P -m arnold_pipelines.megaplan` surface.
- Produce structured JSON command output as a view of the Markdown/artifacts,
  with stable error kinds and nonzero exits for invalid authority.
- Add CLI help, parser snapshots, and subprocess end-to-end tests.

### Out of scope

- Interactive TUI/web UI, arbitrary text editor automation, cross-repository
  commands, or automatic horizon prioritization.
- Broad CLI rewrites unrelated to tickets, initiatives, and strategy.

## Locked Decisions

- Hand editing valid typed Markdown remains a supported first-class workflow.
- CLI writes the authoritative Markdown/artifact relationship data; it does not
  write an independently authoritative JSON roadmap.
- Roadmap inclusion for new tickets is explicit, not automatic.
- Identity and promotion rules from M1/M2 are enforced by every command.

## Open Questions for This Sprint

- Choose command names/flags that fit the current resident CLI without creating
  aliases whose behavior diverges.
- Choose a lossless or narrowly canonical rewrite strategy that preserves prose
  outside typed roadmap blocks and reports concurrent-edit conflicts.
- Decide whether stale display titles are refreshed by an explicit command or
  merely diagnosed during validation/show.

## Constraints

- Use `-P`-compatible module invocation and preserve structured `CliError`
  conventions.
- Commands must be scriptable/noninteractive by default and safe in dirty repos.
- No command may silently create a duplicate initiative or reuse an identifier.
- This sprint is sized to at most two weeks.

## Done Criteria

- Help and parser surfaces expose ticket and strategy commands through the
  resident Megaplan module.
- A subprocess test covers create ticket outside roadmap, add to Next, move to
  Now, promote to a new epic, rebuild projection, and validate final references.
- Direct valid Markdown edits remain readable and produce equivalent CLI output.
- Invalid refs, duplicate identities, malformed blocks, retry collisions, and
  concurrent modification yield stable actionable errors without partial loss.
- JSON output is reproducible from authoritative Markdown/artifacts and clearly
  identified as generated.

## Touchpoints

- `arnold_pipelines/megaplan/cli/__init__.py`, `cli/parser.py`, command roots,
  `handlers/tickets.py`, and new strategy handlers.
- Ticket/initiative CLI tests, parser snapshots, and documentation.

## Anti-Scope

- Do not make the CLI the only valid editor.
- Do not rewrite unrelated Markdown prose or reformat the whole strategy on a
  one-item mutation without an explicit canonicalization contract.
- Do not add status fields to roadmap entries for prettier output.
- Do not restore removed legacy entrypoints as a second CLI authority.
