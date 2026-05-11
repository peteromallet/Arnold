# Sprint brief — Tickets MVP

## Goal

Implement the tickets feature in megaplan per the design in `docs/tickets.md`. Tickets are short, repo-scoped notes on issues/problems, captured by humans or by agents on a human's prompt, that get folded into epics and auto-addressed when the resolving epic completes.

**The design doc `docs/tickets.md` is the source of truth for the data model, CLI surface, file format, modes, codebase identity, and integration touchpoints. Read it first. This brief only adds sprint scoping — what's in, what's out, what success looks like.**

## In scope for this sprint

Everything required to make tickets usable end-to-end in both **local-only mode** and **cloud-configured mode**:

1. **Schema migration (cloud-only)**: add `tickets` and `ticket_epics` tables; add `root_commit_sha` column to `codebases` with an index. Additive only — no changes to existing tables beyond the new column.
2. **`megaplan/store/db.py`**: CRUD helpers for the new tables, column allowlist entries, codebase resolution that prefers `root_commit_sha`.
3. **New module `megaplan/tickets/`**: the canonical local representation. Frontmatter read/write for `.megaplan/tickets/{ulid}-{slug}.md` files. Mode-aware dispatch (cloud-configured → file + DB; local-only → file only). Codebase identity resolution from cwd via `git rev-list --max-parents=0 HEAD`.
4. **CLI `megaplan ticket …`** with all verbs in `docs/tickets.md` § CLI: `new`, `list`, `show`, `edit`, `link`, `unlink`, `addressed`, `dismiss`, `reopen`. `ticket new` prints only the ULID to stdout on success; `--json` on read commands. `source` auto-derived from `MEGAPLAN_TURN_ID` env.
5. **Auto-address hook**: in the epic state-transition path, after an epic moves to `done`, call `megaplan.tickets.address_resolved_by_epic(epic_id)`. Implementation handles both modes per the design doc. Idempotent.
6. **Planner discovery integration**: when assembling context for new/refined epics, include open tickets for the current repo, ranked by `tag overlap with epic goal desc, created_at desc`. The planner can propose links with `resolves_on_complete=true`. Same data shape in both modes (DB query in cloud, file scan in local-only).
7. **Resident/agent prompt**: a short paragraph teaching the agent that `megaplan ticket new` exists and when to use it (out-of-scope observations during epic work, user-requested captures).
8. **Tests** covering both modes for: file ↔ DB round-trip, link/unlink, auto-address idempotence, codebase identity resolution (rename case, fresh-repo case), CLI happy paths.

## Out of scope (defer)

- **Offline queue / `.pending/` directory / `megaplan ticket sync`**. Write-through only for now; if the DB write fails in cloud mode, the CLI errors loudly and the user retries. The design doc describes the offline queue — explicitly **do not build it** this sprint. Build the minimal write-through path.
- Conflict detection on concurrent edits — last-write-wins is fine.
- Severity, assignment, comments, cross-repo tickets — explicitly excluded per the design doc.
- Anything described in the doc's **Open items** section.

## Success criteria

- `megaplan ticket new "title" -b "body"` works in a local-only repo and writes the `.md` file.
- The same command in a cloud-configured repo writes the `.md` file **and** inserts a `tickets` row, auto-registering the codebase if needed (with `root_commit_sha` populated).
- `megaplan ticket link <ticket> <epic> --resolves` updates both the file frontmatter and the DB join row.
- Marking an epic `done` flips the linked ticket's status to `addressed` and writes a `resolution_note` referencing the epic — in both modes.
- New epic creation surfaces open tickets for the repo in the planner's context, ranked.
- Tests pass for both modes.

## Notes for the planner

- Follow the **core-first principle**: `megaplan/tickets/` owns the capability; the DB layer is purely additive and only kicks in when a store is configured. Mode detection follows whatever mechanism megaplan core already uses (presence of a configured store) — do not invent a new one.
- The `tickets` concept is **distinct from `feedback`**. Do not reuse the `feedback` table; do not conflate their lifecycles.
- Vendor flags / FK conventions / migration patterns should match how existing tables are handled in `megaplan/store/db.py`. Read existing CRUD helpers before designing new ones.
- The auto-address hook integration point is the one place where you must touch existing epic state-transition code. Find the existing hook surface (where epic events are emitted on state change) and add the call there — don't invent a parallel transition path.
