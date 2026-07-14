# Strategy Contract v1 — `megaplan-strategy-v1`

## Authority

**Typed Markdown is authoritative.** The initiative-root
`.megaplan/initiatives/<slug>/STRATEGY.md` is the single source of truth for
the repository's stable direction and roadmap. JSON and
other indexes are deterministic, disposable projections — they are never
independently editable, and a consumer MUST NOT treat generated JSON as an
authority source.

The projection path is `.megaplan/strategy.projection.json`. It can be deleted
and rebuilt from the Markdown and referenced artifacts at any time. Editing
only the projection file cannot change parsed strategy meaning.

## Schema Version

The file MUST carry YAML frontmatter with `schema_version: megaplan-strategy-v1`.
Parsers MUST reject any unknown or missing schema version with a diagnostic that
includes the expected version and the version found.

```yaml
---
schema_version: megaplan-strategy-v1
---
```

## Required Sections

### Stable Direction

Stable direction sections describe long-lived strategy intent. They MUST be
present and are preserved as free-form Markdown bodies. The v1 contract
requires exactly these five sections in this order:

1. `## Mission`
2. `## Principles`
3. `## Architecture Direction`
4. `## Constraints`
5. `## Non-Goals`

Section titles are matched case-sensitively. Additional stable-direction
sections MUST NOT be added without a schema version bump. Missing or
out-of-order sections produce hard diagnostics.

### Roadmap

Roadmap sections carry the Now / Next / Later portfolio. They MUST appear
after all stable direction sections and use exactly these titles:

1. `## Now`
2. `## Next`
3. `## Later`

Roadmap sections MAY be empty (no entries), but the sections themselves MUST
be present and in order.

## Roadmap Entry Grammar

Roadmap entries are one-line bullets using the following narrow grammar:

```
- [<type>:<ref>] <display title>
```

Where:

- `<type>` is exactly `ticket` or `epic` (case-sensitive).
- `<ref>` is an immutable artifact identifier:
  - For `ticket`: a valid, uppercase ULID string (e.g. `01KT50AZRMK5X890TQ565DDB5V`).
  - For `epic`: a canonical initiative slug as validated by `slugify_initiative`
    (e.g. `repository-strategy-roadmap`).
- `<display title>` is free text up to end of line. It is mutable display text
  and never part of the entry's identity.

Entry examples:
```
- [ticket:01KT50AZRMK5X890TQ565DDB5V] Fix authentication timeout
- [epic:repository-strategy-roadmap] Repository strategy roadmap
```

### Grammar Constraints

- **Only one entry per line.** Multi-line entry bodies are not supported.
- **Typed bullets only under roadmap sections.** A `- [type:ref]` bullet
  outside `## Now`, `## Next`, or `## Later` produces a hard diagnostic.
- **No Markdown tables.** v1 intentionally uses bullet grammar only. Tables
  are not required for this version.
- **No embedded bodies or status.** Entries reference artifacts; they do not
  duplicate ticket/epic bodies, lifecycle status, plans, or completion evidence.
- **No artifact body or lifecycle fields.** The parsed strategy model, and the
  generated projection, MUST NOT contain fields for artifact body text or
  lifecycle status.

## Identity

Roadmap entry identity is exactly `(type, ref)`. This pair MUST be unique
across all horizons. Duplicate `(type, ref)` pairs produce hard validation
errors.

- `type` is the executable item type (`ticket` or `epic`).
- `ref` is the immutable artifact identifier (ULID for tickets, slug for epics).

Titles are mutable display text, never identity. Parsers and validators MUST
NOT derive identity from titles, filenames, or display text.

## Executable Item Types

The executable roadmap vocabulary is exactly `ticket` and `epic`. A third
executable item type in the strategy Markdown produces a hard diagnostic.
Extending the vocabulary requires a schema version bump.

Horizon (`Now`, `Next`, `Later`) is independent of artifact type. Both
`ticket` and `epic` entries are accepted in any horizon.

## Diagnostics Policy

All diagnostics MUST include source location with path, line number, and
column. This allows automation to act safely on validation results.

### Hard Errors (blocking)

- Missing or unknown `schema_version`.
- Missing or out-of-order required sections.
- Malformed roadmap bullets (cannot parse `type:ref`).
- Invalid ticket ULID format.
- Non-canonical epic ref (not a valid initiative slug).
- Unsupported item type (anything other than `ticket` or `epic`).
- Duplicate `(type, ref)` across any horizon.
- Missing artifact reference (ticket or epic does not exist in the repository).
- Typed bullet outside a roadmap section.

### Warnings (non-blocking)

- Stale display title: the title in the strategy Markdown differs from the
  title in the referenced artifact. Warnings MUST NOT normalize the Markdown
  title — the human-authored text is preserved as-is.

## Projection Rebuildability

The JSON projection at `.megaplan/strategy.projection.json`:

- Carries its own schema version `megaplan-strategy-projection-v1` and source
  version `megaplan-strategy-v1`.
- Is deterministic: given the same Markdown and artifact state, rebuilding
  produces byte-for-byte equivalent JSON.
- Contains stable direction, ordered horizons, entry `type`/`ref`/display
  `title`, source location, and validation summary.
- Excludes ticket/epic body text, lifecycle status, plan details, and
  completion evidence.
- Uses deterministic key ordering and stable formatting.
- Is never read as an authority source by parsers, validators, or resolvers.

## Serialization

The serializer writes canonical Markdown that round-trips without semantic
loss. Roadmap entry identity is preserved exactly. Stable-direction section
bodies are preserved as-authored. The serializer does not normalize display
titles or reorder sections.

## No-Body / No-Status Rule

Strategy entries are pointers to artifacts, not containers for them. The
contract explicitly prohibits:

- Embedding ticket or epic body text in strategy entries.
- Including lifecycle status, plan details, or completion evidence.
- Making generated JSON or display titles authoritative.
- Using titles or filenames as identity.
