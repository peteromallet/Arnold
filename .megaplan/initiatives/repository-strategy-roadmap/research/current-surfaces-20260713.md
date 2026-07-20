# Current Surface Audit — Repository Strategy Roadmap

Inspected at resident runtime revision
`962fcb0ec530594290439c7c41a1be0602467336` before locking the briefs.

## Existing durable artifacts

- Tickets are authoritative Markdown files under `.megaplan/tickets/` with YAML
  frontmatter and body. New tickets receive immutable ULIDs; filenames combine
  ULID and mutable title slug.
- Ticket frontmatter currently carries an `epics` list containing `epic_id`,
  `resolves_on_complete`, and `linked_at`. Core operations support link/unlink,
  open/addressed/dismissed/reopen, and automatic addressing when a resolving
  epic completes.
- Store-backed ticket operations mirror the file model through `Ticket` and
  `TicketEpicLink`; file-only and store contract behavior already has tests.
- Canonical initiatives live at `.megaplan/initiatives/<slug>/` under layout
  policy `megaplan-initiatives-v1`, with `README.md`, optional `NORTHSTAR.md`,
  `chain.yaml`, and typed subdirectories. Initiative search covers slug, title,
  and description.
- `artifacts.py` already supplies generic Markdown/frontmatter parse/write,
  title, slug, keyword, and directory helpers suitable for reuse where their
  semantics match.

## Gaps relevant to this epic

- There is no first-class `.megaplan/STRATEGY.md`, roadmap parser, validator,
  typed strategy model, or rebuildable strategy projection.
- Current ticket-to-epic links express resolution but not the complete
  ticket-promotion/supersession contract locked by the product direction.
- Existing ticket handlers and dispatch exist, but the current resident module
  parser does not register the `ticket` command; help exposes initiative/brief
  but not ticket or cloud. Cloud's canonical parser/runner still exists in
  `arnold_pipelines.megaplan.cloud.cli` and is used by resident cloud wrappers.
- The repository includes historical ticket filenames without ULID prefixes;
  migration cannot assume every legacy file is immediately roadmap-eligible.
- Existing projections concern run/status/incident authority and should not be
  refactored merely to add strategy; the new projection must remain explicitly
  downstream of Markdown and artifact lookup.

## Planning consequences

- Freeze strategy authority and grammar before lifecycle or CLI work.
- Extend/adapt the existing relationship substrate instead of inventing an
  independent promotion database.
- Treat parser registration/parity as an explicit CLI milestone.
- Include a separate migration sprint and fail closed on ambiguous legacy IDs.
- Adopt Arnold only after lifecycle and compatibility contracts are proven.
