# Tickets

A lightweight way to capture problems, bugs, or "we should look at this" notes against a repo, so they can later be folded into epics. Tickets are deliberately small: just enough structure to triage, link, and auto-close when the work that addresses them ships.

## Why this is a new concept (not `feedback`)

The existing `feedback` table holds guidance about *the tooling itself* — corrections to how the agent behaves, what to avoid, what worked. It is injected into prompts.

Tickets are different: they describe *a problem in a codebase* that may become work. They are inert until folded into an epic. Keep the tables separate; no shared lifecycle.

## Modes

Megaplan runs in two modes; tickets must work in both.

- **Local-only** — no cloud configured. The `.md` files on disk are the sole source of truth. No DB row, no codebase row. Identity is the repo's root commit SHA, computed on demand.
- **Cloud-configured** — DB store available. The `.md` files remain on disk and committed to the repo, and a mirrored row exists in `tickets` / `ticket_epics`. The DB is the system of record for live state; the file is the human-readable artifact.

Mode detection follows the same rule megaplan core already uses (presence of a configured store). The CLI dispatches: if cloud is configured, write-through to DB and sync; otherwise file-only operations.

Everything in the rest of this doc applies to both modes unless explicitly marked **(cloud-only)**.

## Data model

The tables below are **cloud-only**: they're created and used when a store is configured. In local-only mode, the equivalent state lives entirely in `.md` frontmatter (see [Local format](#local-format)).

### New table: `tickets` (cloud-only)

| column | type | notes |
|---|---|---|
| `id` | ULID | also the local filename stem |
| `codebase_id` | FK → `codebases.id` | required, primary scoping |
| `title` | text | required, ≤120 chars, one line |
| `body` | text | required, markdown, non-empty |
| `tags` | text[] | optional, freeform |
| `status` | enum | `open` \| `addressed` \| `dismissed`, default `open` |
| `source` | enum | `human` \| `agent` \| `post-mortem` |
| `filed_by_actor_id` | FK → actors | nullable |
| `filed_in_turn_id` | FK → `bot_turns` | nullable; populated when agent files mid-turn |
| `resolution_note` | text | filled on addressed/dismissed |
| `created_at`, `last_edited_at`, `addressed_at`, `dismissed_at` | timestamps | |

### New table: `ticket_epics` (many-to-many, cloud-only)

| column | type | notes |
|---|---|---|
| `ticket_id` | FK | |
| `epic_id` | FK | |
| `resolves_on_complete` | bool | **the key field** — does completing this epic close this ticket? |
| `linked_at`, `linked_by_actor_id`, `note` | | |

Primary key `(ticket_id, epic_id)`. A ticket can be linked to N epics over its life; an epic can address N tickets.

### Addition to `codebases` (cloud-only)

Add `root_commit_sha` (text, indexed). Used as the durable repo identity — see [Codebase identity](#codebase-identity). Backfilled lazily for existing rows on first access. In local-only mode this column doesn't apply; the root SHA is computed directly from `git` when needed.

That's the entire schema change. No new event/audit tables — provenance is covered by `filed_by_actor_id` / `filed_in_turn_id` and the local file's git history.

## Local format

One markdown file per ticket, **committed to the repo**:

```
<repo>/.megaplan/tickets/{ulid}-{slug}.md
```

The path establishes the repo association — no `codebase_id` in frontmatter.

```markdown
---
id: 01HXY...
title: Execute step retries swallow stderr on timeout
tags: [execute, observability]
status: open
source: agent
filed_by: actor_01H...        # raw string; FK only resolved in cloud mode
filed_in_turn: turn_01H...    # raw string; FK only resolved in cloud mode
created_at: 2026-05-11T14:22:00Z
epics:
  - id: epic_01HZ...
    resolves_on_complete: true
---

# Body

Markdown prose describing the issue.
```

Frontmatter is **complete in local-only mode** — it carries everything needed to reconstruct ticket state without a DB. In cloud mode, the same fields are mirrored to the `tickets` row; `filed_by` / `filed_in_turn` become real FKs (`filed_by_actor_id`, `filed_in_turn_id`). The `epics:` list mirrors the `ticket_epics` join in cloud mode and is the sole representation of links in local-only mode.

## CLI

One surface. The agent shells out to it; no separate tool API.

```
megaplan ticket new "<title>" [-b "<body>" | --edit | -]  [-t tag1,tag2]
megaplan ticket list   [--tag X] [--status open] [--epic E]
megaplan ticket show   <id>
megaplan ticket edit   <id>                              # opens $EDITOR on the .md
megaplan ticket link   <ticket> <epic> [--resolves]
megaplan ticket unlink <ticket> <epic>
megaplan ticket addressed <id> [--note "..."]
megaplan ticket dismiss   <id> [--note "..."]
megaplan ticket reopen    <id>
```

Conventions:

- `--json` on any read command emits structured output.
- `ticket new` prints **only the ULID** to stdout on success (human chatter to stderr) so the agent can pipe/capture it trivially.
- `source` is auto-derived: if `MEGAPLAN_TURN_ID` is set in env, `source=agent` and `filed_by` / `filed_in_turn` are populated; otherwise `source=human`.
- All commands resolve the repo from cwd (see [Codebase identity](#codebase-identity)). In cloud mode this resolves to a `codebase_id` (auto-registering the row if needed). In local-only mode it's just the cwd repo; no registration step.
- `list` scope differs by mode: in local-only it lists files under `<cwd>/.megaplan/tickets/`. In cloud mode the same command can also accept `--codebase <owner>/<name>` to query across repos via the DB; without that flag it defaults to the current repo.

## Lifecycle & auto-addressing

1. **File** → `status=open`, written to `.md` and DB.
2. **Link to epic** → join row created, optionally `resolves_on_complete=true`.
3. **Epic completes** → for each ticket linked with `resolves_on_complete=true`, flip ticket to `addressed`, set `addressed_at`, fill `resolution_note` with `"Resolved by epic <id> on <date>: <epic title>"`. Idempotent — re-running on an already-addressed ticket is a no-op.
4. **Epic cancelled/dismissed** → ticket status is untouched. Link stays as history.
5. **Reopen** → `reopen` flips ticket back to `open`. The linking epic's join row has `resolves_on_complete` demoted to `false` and a note appended.

Auto-addressing fires from the epic state-transition hook (same place that emits epic events). Add a single call after `state → done`: `address_tickets_resolved_by_epic(epic_id)`. The implementation has two paths, dispatched on mode:

- **Cloud-configured** — updates `tickets` rows and the corresponding `.md` frontmatter in the working repo (if present).
- **Local-only** — walks `.megaplan/tickets/*.md`, finds files whose `epics:` list contains this epic with `resolves_on_complete: true`, and updates their frontmatter in place.

Both paths are idempotent.

## Discovery at planning time

When a new epic is created or refined for a repo, surface the open tickets for that codebase (ranked by tag overlap with the epic goal + recency) into the planner prompt. The planner proposes which to link with `resolves_on_complete=true`. This is the natural "folding" moment — no separate ceremony.

A standalone `megaplan ticket link` exists for ad-hoc linking outside that flow.

## Codebase identity

Durable key: the SHA of the repo's root commit (`git rev-list --max-parents=0 HEAD`). Survives rename, transfer, fork, remote URL change.

**Local-only mode**: compute the root SHA on demand. That's the identity. No row, no registration.

**Cloud-configured mode**: stored as `codebases.root_commit_sha`. Resolution order on any ticket CLI invocation:

1. Compute the root SHA from cwd.
2. Look up codebase by `root_commit_sha`. If found, use that `codebase_id`. If `(owner, name)` no longer matches the current remote, silently update those columns — the ID is preserved, all tickets keep working.
3. If not found, fall back to `(owner, name)` lookup (handles pre-existing rows without `root_commit_sha` — backfill it on hit).
4. If still not found, auto-register a new codebase row using current owner/name/remote and the root SHA, then proceed.

Edge cases:

- **No commits yet** → CLI refuses; tell the user to make their first commit.
- **Multiple root commits** (rare) → use the smallest SHA when sorted; document.
- **Submodule / subdir** → root SHA is the outer repo's. Tickets attach to the repo, not the subdir.

## Sync model

Mode-dependent:

- **Local-only** — every operation writes the `.md` file. That's it. No queue, no sync, no DB.
- **Cloud-configured** — write-through with an offline fallback queue:
  - Every `ticket new/edit/link/...` writes the `.md` and pushes to DB in the same call.
  - If the DB write fails (offline, network error), the intent is stashed in `.megaplan/tickets/.pending/{ulid}.json`.
  - The next successful online command (or an explicit `megaplan ticket sync`) flushes the pending queue.
  - The `.md` files are the truth offline; the DB is the truth when reachable. Reconcile on flush by comparing `last_edited_at`.

`megaplan ticket sync` is a no-op in local-only mode.

## What this does NOT include (intentionally)

- No severity field — tags cover prioritization for now.
- No assignment / owner — tickets are repo-scoped, not person-scoped.
- No comments / threads — edit the body or add a new ticket.
- No cross-repo tickets — one ticket, one codebase. Use a `cross-repo` tag if needed.
- No separate audit table — provenance is on the row + git history of the `.md`.
- No agent-facing tool API distinct from the CLI.

If any of these become real pain points, revisit. Don't pre-build.

## Integration touchpoints (what to change beyond the new tables)

Follow the core-first principle: the local-file path lives in `_core` / `megaplan/tickets/`; DB persistence is layered on top and only kicks in when a store is configured.

- New module `megaplan/tickets/` — the canonical local representation (read/write `.md` files, frontmatter parsing, link/address operations on files), plus mode-aware dispatch into the store. This module is what the CLI and the epic hook both call.
- `megaplan/store/db.py` **(cloud-only)**: add `tickets` and `ticket_epics` to the column allowlists; CRUD helpers (`create_ticket`, `list_tickets`, `link_ticket_to_epic`, `address_tickets_resolved_by_epic`, etc.); add `root_commit_sha` to `codebases` allowlist.
- Schema migration **(cloud-only)**: create the two tables; `ALTER TABLE codebases ADD COLUMN root_commit_sha text` with an index.
- `megaplan/cli.py`: register the `ticket` subcommand group. CLI handlers call into `megaplan/tickets/`, which internally decides whether to also touch the store.
- Epic state-transition hook (wherever an epic moves to `done`): call `megaplan.tickets.address_resolved_by_epic(epic_id)`. The function runs the file-update path in both modes, and the DB-update path additionally in cloud mode.
- Epic planner prompt assembly: when building context for a new/refined epic, include open tickets for the repo. In local-only mode this reads `.megaplan/tickets/*.md`; in cloud mode it queries the DB. Same shape of data, different source.
- Resident/agent prompt: a short paragraph telling the agent that `megaplan ticket new` exists and when to reach for it (out-of-scope observations during epic work, user-requested captures).

## Strategy roadmap integration

Tickets are **backlog artifacts**, not automatically strategy-visible items. A ticket only appears in the repository's initiative-root strategy roadmap (`.megaplan/initiatives/<slug>/STRATEGY.md`) when explicitly added. This preserves the distinction between the full ticket backlog and the deliberately selected subset that represents strategic direction.

### Opt-in visibility at creation time

`megaplan ticket new` supports optional `--roadmap-horizon` and `--roadmap-title` flags:

```bash
# File a ticket AND add it to the Next horizon:
megaplan ticket new "Fix authentication timeout" -b "..." --roadmap-horizon Next

# With an explicit roadmap display title:
megaplan ticket new "Fix auth" -b "..." --roadmap-horizon Now --roadmap-title "Fix authentication timeout in OAuth flow"
```

Without these flags, the ticket is created as a normal backlog artifact — it does not appear in the strategy roadmap.

### Adding existing tickets to the roadmap

```bash
megaplan strategy add --type ticket --ref <ULID> --title "Display Title" --horizon Next
```

The artifact (ticket file) must exist first. The strategy entry is a pointer — it references the ticket by ULID and never copies the ticket body, lifecycle status, or completion evidence.

### Lifecycle stays in artifacts, not strategy

When a ticket is marked addressed (`megaplan ticket addressed <id>`), the status is written to the ticket file only. The strategy Markdown is **not** modified. If the roadmap entry should be removed, do that as a separate deliberate action:

```bash
megaplan strategy remove --type ticket --ref <ULID>
```

### Ticket promotion to epic

When a ticket grows in scope and warrants its own initiative, promote it:

```bash
megaplan ticket promote <ticket_id> \
  --initiative-slug my-feature \
  --title "My Feature Epic" \
  --goal "..."
```

Promotion preserves distinct ticket and epic identities (the ticket ULID is never reused as the epic ID). If the ticket was in the strategy roadmap, its entry is replaced by an epic entry in the same horizon. See `docs/strategy.md` for full promotion details.

### Visualization

```bash
# See what's in the roadmap:
megaplan strategy list

# Filter to tickets only:
megaplan strategy list --type ticket

# See ticket status (separate from strategy):
megaplan ticket list --status open
```

The strategy shows _what the repository is working toward_. The ticket list shows _what problems exist_. They are related but intentionally separate views.

## Open items

- Exact ranking heuristic for "open tickets shown at planning time" — start with `tag overlap desc, created_at desc`, refine if it's noisy.
- Whether `ticket edit` should diff the new frontmatter against the DB and reject conflicting concurrent edits, or last-write-wins. Last-write-wins for now; add conflict detection only if it bites.
