---
name: megaplan-tickets
description: File and manage megaplan tickets — short, repo-scoped notes on problems or observations that get folded into epics and auto-addressed when the resolving epic completes.
---

# Megaplan tickets

Tickets are short, repo-scoped notes on problems, bugs, or "we should look at this" observations against a codebase. They live as committed `.md` files under `<repo>/.megaplan/tickets/` and (when a cloud store is configured) mirror to `tickets` / `ticket_epics` tables. Tickets are inert until folded into an epic — they capture problems, not work.

## When to file a ticket

Reach for `megaplan ticket new` when:
- During epic or plan execution you notice an **out-of-scope problem** that should be tracked but isn't blocking the current task.
- The user explicitly asks you to **capture an observation** ("file a ticket for that", "make a note of this for later").
- You want to log a rough edge or potential bug whose fix would be its own piece of work.

Do **not** use tickets for:
- Guidance/corrections to *how the tooling itself behaves* — that's `megaplan feedback` (a separate, plan-scoped concept).
- In-flight task state — that's the executor's own checklist.
- General notes or chat — write them in the conversation.

## Filing

```bash
megaplan ticket new "<title>" -b "<body>" [--tags tag1,tag2] [--roadmap-horizon Now|Next|Later] [--roadmap-title "..."]
```

Conventions:
- `-b "..."`, `--edit` (open `$EDITOR`), and `-` (read body from stdin) are mutually exclusive; one is required.
- `ticket new` prints **only the ULID** on stdout on success (logs go to stderr). Capture it for piping.
- `--tags` is comma-separated. Tags are freeform; common ones: `bug`, `refactor`, `tech-debt`, `observability`, `docs`, `cross-repo`.
- `source` is auto-derived: if `MEGAPLAN_TURN_ID` is set (the agent is running under a megaplan-launched worker), `source=agent` and the turn id is recorded; otherwise `source=human`.
- The repo is resolved from cwd via its root commit SHA (`git rev-list --max-parents=0 HEAD`). Identity survives rename / transfer / remote change.
- **`--roadmap-horizon` is opt-in.** Without it, the ticket is a normal backlog artifact — it does NOT appear in the strategy roadmap (`.megaplan/STRATEGY.md`). Pass `--roadmap-horizon Now|Next|Later` to also add the ticket to that horizon. Use `--roadmap-title` to set a different display title in the roadmap (defaults to the ticket title).
- Strategy entries are pointers, never containers — the roadmap bullet references the ticket ULID and never copies the ticket body, lifecycle status, or completion evidence. The JSON projection at `.megaplan/strategy.projection.json` is disposable; delete it and rebuild with `megaplan strategy project --write`.

Multi-line body via stdin:
```bash
cat <<'EOF' | megaplan ticket new "Title here" --tags tag1,tag2 -
First paragraph of the body.

More detail in a second paragraph.
EOF
```

## Reading

```bash
megaplan ticket list   [--status open|addressed|dismissed] [--tags t1,t2] [--json]
megaplan ticket show   <id> [--json]
megaplan ticket search [KW ...] [--all] [--project P]... [--all-projects]
                       [--status ...] [--tags ...]
                       [--sort created|edited|length|title] [--asc]
                       [--limit N] [--json] [--no-snippet]
```

`--json` on read commands emits structured output; safe for piping.

### Searching across repos

`ticket search` is the cross-cutting reader. Defaults:

- **Scope** — current repo. Pass `--all-projects` to scan every known repo (locally: the auto-maintained `~/.config/megaplan/known_repos.json` registry; cloud: every codebase). Pass `--project PATH|owner/name|name` (repeatable) to scope to specific repos.
- **Keywords** — multiple positional args. Default is **OR** (any keyword matches). Pass `--all` to require all keywords. Match is case-insensitive substring across **title, body, tags, and resolution_note**.
- **Sort** — `--sort {created,edited,length,title}`; `--asc` flips to ascending. Default: created, descending.
- **Snippets** — human output shows a 120-char snippet around the first match. `--no-snippet` to hide.

Examples:

```bash
# Anything mentioning "stderr" or "timeout" in this repo:
megaplan ticket search stderr timeout

# Same, but require BOTH terms:
megaplan ticket search stderr timeout --all

# Across every repo on this machine, only open, sorted by longest body first:
megaplan ticket search redis --all-projects --status open --sort length --json

# Scoped to two specific repos:
megaplan ticket search auth --project ~/Documents/reigh-app --project banodoco/megaplan
```

## Editing and linking

```bash
megaplan ticket edit    <id> [--title ...] [--body ...] [--status ...] [--add-tag ...] [--remove-tag ...]
megaplan ticket link    <ticket> <epic> [--resolves]
megaplan ticket unlink  <ticket> <epic>
megaplan ticket addressed <id> [--note "..."]
megaplan ticket dismiss   <id> [--reason "..."]
megaplan ticket reopen    <id>
```

`link ... --resolves` marks the join with `resolves_on_complete=true`. When the linked epic transitions to `done`, the ticket auto-flips to `addressed` and gets a `resolution_note` referencing the epic. Idempotent — re-running on an already-addressed ticket is a no-op.

## Modes

Megaplan runs in one of two modes; tickets work transparently in both:

- **Local-only** (no cloud store configured) — `.md` files on disk are the sole source of truth. `codebase_id` will be `null` in frontmatter; identity is computed on demand from the repo's root SHA.
- **Cloud-configured** (`SUPABASE_DB_URL` or megaplan config points at a store) — every operation writes the `.md` file **and** mirrors to the `tickets` / `ticket_epics` tables. Auto-registers the codebase on first ticket if needed.

You do not need to detect the mode yourself; the CLI dispatches based on whether a store is configured.

## Local format

```
<repo>/.megaplan/tickets/{ulid}-{slug}.md
```

```markdown
---
id: 01HXY...
title: Execute step retries swallow stderr on timeout
tags: [execute, observability]
status: open
source: agent
codebase_id: null            # null in local-only, populated in cloud
created_at: 2026-05-11T14:22:00Z
epics:
  - id: epic_01HZ...
    resolves_on_complete: true
---

# Body

Markdown prose describing the issue.
```

Commit ticket files. The `.md` is the human-readable artifact and (in local-only) the system of record.

## Discovery at planning time

When a new epic is created or refined for the current repo, the planner automatically surfaces open tickets ranked by tag overlap with the epic's goal and recency. The planner may propose links with `resolves_on_complete=true`. You don't need to remind it — discovery is built into the plan-phase prompt assembly.

## Quick reference

| You want to … | Run |
|---|---|
| File a ticket | `megaplan ticket new "title" -b "body" [--tags t1,t2]` |
| Pipe a multi-line body | `cat body.md \| megaplan ticket new "title" -` |
| List open tickets | `megaplan ticket list --status open --json` |
| Search by keyword in this repo | `megaplan ticket search foo bar` |
| Search across every repo | `megaplan ticket search foo --all-projects` |
| Link a ticket to an epic so it auto-closes | `megaplan ticket link <tid> <eid> --resolves` |
| Mark addressed manually | `megaplan ticket addressed <tid> --note "..."` |
| Reopen a closed ticket | `megaplan ticket reopen <tid>` |

That's the whole surface. The auto-address hook does the rest.
