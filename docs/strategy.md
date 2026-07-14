# Repository Strategy

The repository strategy lives at `.megaplan/initiatives/<slug>/STRATEGY.md` as a canonical root file under the `megaplan-initiatives-v1` policy. It is the single Markdown-authoritative document that declares the repository's stable direction and its living roadmap. It never belongs in `.megaplan/briefs`. All other artifacts — JSON projections, tool output, IDE plugins — are disposable derivatives. Never edit them directly.

Create it with either interface:

```bash
# Reuse the single matching repository-strategy initiative, or create
# .megaplan/initiatives/repository-strategy/STRATEGY.md.
megaplan strategy init

# Select an initiative explicitly.
megaplan strategy init --initiative my-repository-strategy

# Include it while scaffolding a new initiative.
megaplan initiative new my-repository-strategy --strategy
```

Initialization creates missing canonical initiative subdirectories and a minimal `README.md`, but never overwrites an existing strategy unless `--force` is explicitly supplied. Existing repositories with `.megaplan/STRATEGY.md` remain readable and writable for backward compatibility; all newly initialized documents use the initiative layout.

During migration, keep exactly one authoritative strategy document. If a legacy `.megaplan/STRATEGY.md` and an initiative-root `STRATEGY.md` coexist, or if multiple initiatives contain one, strategy commands fail closed and report every conflicting path. Reconcile the documents deliberately; `strategy init --initiative <slug>` may be used only to select the initialization target and does not make duplicate authorities safe for normal reads or writes.

## Authority model

**Typed Markdown is authoritative.** The strategy Markdown file is the one source of truth. The generated JSON at `.megaplan/strategy.projection.json` is a deterministic, disposable projection. It can be deleted and rebuilt from the Markdown at any time. Consumers that treat the projection as authoritative are violating the contract.

This means:

- Every strategy mutation writes the Markdown file, not the projection.
- `megaplan strategy project --write` regenerates the projection from the Markdown.
- CI deletes the projection before rebuilding it, never committing stale JSON.
- If the projection disagrees with the Markdown, the Markdown wins — always.

## Stable direction

The five stable-direction sections describe long-lived intent. They change rarely and only with deliberate discussion:

1. **Mission** — the repository's core purpose and what success looks like.
2. **Principles** — guiding principles that shape technical and process decisions.
3. **Architecture Direction** — high-level patterns, boundaries, and technology choices.
4. **Constraints** — hard requirements that must be satisfied (runtime, compatibility, security).
5. **Non-Goals** — explicitly out-of-scope work to prevent scope creep.

These sections are free-form Markdown prose. They are required, ordered, and case-sensitively titled.

## Roadmap horizons: Now, Next, Later

The roadmap is organized into three time horizons that appear after the stable direction sections:

- **Now** — work actively in progress or starting this cycle.
- **Next** — work queued for the following cycle.
- **Later** — work recognized as strategically important but not yet scheduled.

Horizons are independent of artifact type. Both tickets and epics can appear in any horizon.

Roadmap sections MAY be empty (no entries), but the sections themselves MUST be present and in order.

## Roadmap entry vocabulary

The executable roadmap vocabulary is exactly two item types: `ticket` and `epic`. Every roadmap entry uses the narrow bullet grammar:

```
- [type:ref] display title
```

### `ticket` entries

A ticket entry points to a committed `.megaplan/tickets/{ulid}-{slug}.md` file. The ref is the ticket's ULID (uppercase). Example:

```
- [ticket:01KTH21DTP1HR3ER5W7SRRJVV5] Prevent stale git pre-commit hook rot
```

### `epic` entries

An epic entry points to a committed initiative directory at `.megaplan/initiatives/{slug}/`. The ref is the canonical initiative slug (lowercase, hyphenated). Example:

```
- [epic:repository-strategy-roadmap] Repository strategy roadmap
```

No other item types are valid. Introducing a third type requires a schema version bump.

## Identity: type + ref

Roadmap entry identity is the `(type, ref)` pair. This pair MUST be unique across all horizons. The identity is immutable — once a ticket ULID or initiative slug is set, it does not change.

Titles are mutable display text and are never part of identity. You can edit a display title in the Markdown at any time without affecting the entry's identity. The parser and validator derive identity only from `type` and `ref`.

## Mutable display titles

The display title in a roadmap bullet is free text to the end of the line. It can be updated by editing the Markdown directly or via `megaplan strategy add` with a changed title (which replaces the entry). The validator emits a **warning** (not an error) when the strategy title diverges from the artifact's title — this is a stale-title diagnostic, not a blocking failure.

The warning does NOT normalize the Markdown title. The human-authored text is preserved as-is. Only a human (or agent acting on human instruction) updates it.

## Optional roadmap visibility

**Tickets are not automatically strategy-visible.** A ticket filed with `megaplan ticket new` is a backlog artifact. It only becomes strategy-visible when explicitly added to the roadmap via one of:

- `megaplan ticket new --roadmap-horizon Now|Next|Later --roadmap-title "..."` — opt-in at creation time.
- `megaplan strategy add --type ticket --ref <ULID> --title "..." --horizon Now|Next|Later` — explicit addition after creation.
- Direct Markdown edit adding a `- [ticket:<ULID>] <title>` bullet under a roadmap section.

Similarly, an epic initiative exists on disk at `.megaplan/initiatives/<slug>/` but only appears in the strategy when its entry is added to a roadmap horizon.

This design preserves the distinction between the full backlog (every ticket and initiative) and the strategy (the deliberately selected subset that represents current direction). Not every open ticket belongs in the roadmap.

## Validation

`megaplan strategy validate` loads, parses, validates, and resolves the strategy file against referenced artifacts. It returns:

- `clean: true` when zero diagnostics are found.
- `error_count` and `warning_count` counts.
- Source-located diagnostics with path, line, and column.

Hard errors (blocking, exit code 1):

- Missing or unknown `schema_version`.
- Missing or out-of-order required sections.
- Malformed roadmap bullets.
- Invalid ticket ULID format.
- Non-canonical epic ref.
- Unsupported item type (anything other than `ticket` or `epic`).
- Duplicate `(type, ref)` across horizons.
- Missing artifact reference (ticket file or initiative directory does not exist).
- Typed bullet outside a roadmap section.

Warnings (non-blocking):

- Stale display title (strategy title differs from the artifact's title).

CI runs `megaplan strategy validate` on every push. A dirty worktree or active run state does not affect validation — it is network-free and database-free.

## Projection rebuild

The JSON projection at `.megaplan/strategy.projection.json` is a disposable artifact. To rebuild it:

```bash
# Print projection to stdout (inspect without writing):
megaplan strategy project

# Delete and rebuild the projection file:
rm -f .megaplan/strategy.projection.json
megaplan strategy project --write
```

The projection:
- Uses its own schema version `megaplan-strategy-projection-v1`.
- Is deterministic — same Markdown + same artifacts → byte-for-byte identical JSON.
- Contains stable direction, ordered horizons, entry `type`/`ref`/`title`/`horizon`/`source`, and a validation summary.
- Excludes ticket/epic body text, lifecycle status, plan details, and completion evidence.
- Uses deterministic key ordering and stable formatting.
- Is never read as an authority source.

## Promotion

Promoting a ticket to an epic is a coordinated multi-step operation:

```bash
megaplan ticket promote <ticket_id> \
  --initiative-slug my-initiative \
  --title "Epic display title" \
  --goal "One-line goal statement"
```

What promotion does:

1. **Retains the source ticket.** The ticket file is never deleted. Its ULID is never reused as the epic ID. The ticket's identity history is preserved.
2. **Searches for an existing initiative** with a matching slug. If one exists, it is reused. If not, a canonical initiative folder is created at `.megaplan/initiatives/<slug>/`.
3. **Creates or reuses the epic.** The epic's ID is the initiative slug (never the ticket ULID). This preserves distinct ticket and epic identities.
4. **Records provenance.** A relationship link of kind `promoted_to_epic` is written into the ticket frontmatter with a `provenance: promotion:<ticket_id>` traceability string.
5. **Replaces the roadmap entry.** If the ticket was in the strategy roadmap, its entry is replaced by an epic entry in the same horizon. Non-roadmap tickets are not forced into the strategy.

The `--skip-strategy` flag skips the roadmap replacement step.

Promotion is idempotent for the same ticket + initiative pair. Promoting a ticket already promoted to a different epic fails with a conflict error.

## Recovery and troubleshooting

### Strategy file is missing

```bash
# Scaffold a fresh initiative-root strategy from the v1 template:
megaplan strategy init

# Overwrite an existing file:
megaplan strategy init --force
```

### Projection is stale or missing

The projection is disposable. Delete it and rebuild:

```bash
rm -f .megaplan/strategy.projection.json
megaplan strategy project --write
```

### Validation errors after a manual edit

```bash
# See all diagnostics with source locations:
megaplan strategy validate --json

# Show the full parsed representation:
megaplan strategy show --json

# List entries to verify horizon placement:
megaplan strategy list
```

Common causes:
- Duplicate `(type, ref)` across horizons — remove one entry.
- Typed bullet outside a roadmap section — move it under Now/Next/Later.
- Invalid ULID — check the ticket file for a valid, uppercase ULID.
- Non-canonical epic slug — use the exact initiative directory name.
- Missing artifact — create the ticket or initiative first, then add it to the roadmap.

### Stale display title warnings

When an artifact's title changes (e.g., `megaplan ticket edit <id> --title "..."`), the strategy Markdown may contain the old title. The validator warns but does not block. To fix:

```bash
# Option A: CLI edit — remove and re-add with the new title
megaplan strategy remove --type ticket --ref <ULID>
megaplan strategy add --type ticket --ref <ULID> --title "New Title" --horizon Next

# Option B: Direct Markdown edit
# Edit the display title in .megaplan/initiatives/<slug>/STRATEGY.md directly.
# The parser preserves the human-authored text as-is.
```

### Promotion conflict

When promotion detects that a ticket is already promoted to a different epic, it fails with a `PromotionConflictError`. The conflict details include the existing epic ID and initiative slug. To resolve:

1. Check the existing promotion link in the ticket frontmatter.
2. Decide whether to reuse the existing epic or unlink and re-promote.
3. If re-promoting, use `megaplan ticket unlink <ticket> <epic>` first.

### Strategy file modified concurrently

The write path uses hash/mtime conflict detection. If a concurrent edit is detected:

1. Re-read the strategy with `megaplan strategy show --json`.
2. Re-apply your changes.
3. Write again.

## Tickets as backlog artifacts

Tickets are the repository's problem backlog. They are committed `.md` files under `.megaplan/tickets/` that capture bugs, observations, and technical debt. Tickets are **source artifacts** — they exist independently of the strategy and carry their own lifecycle (open, addressed, dismissed).

The relationship between tickets and strategy is:

- **Tickets are the source.** The strategy references them; it does not duplicate them.
- **Strategy entries are pointers.** A `- [ticket:<ULID>]` bullet is a reference, not a container. It never copies the ticket body, lifecycle status, plan, or completion evidence.
- **Visibility is opt-in.** A ticket only appears in the strategy roadmap when explicitly added. Most tickets live in the backlog, not the roadmap.
- **Lifecycle stays in artifacts.** Marking a ticket as `addressed` updates the ticket file. It does not modify the strategy. If a resolved ticket's roadmap entry should be removed, do that as a separate deliberate action.

This separation keeps the strategy focused on direction and the backlog focused on operational tracking. Both are valuable; neither duplicates the other.
