# M7 — Documentation Reconciliation (final)

## Outcome
The docs describe the now-pristine end-state truthfully and without duplication. This is
the last content milestone before publish: it runs after all code is settled (M1–M6) so
it can describe a final API, citing `docs/api/m6-public-api.md`.

## Problem (audit lens 9 — with two stale claims corrected)
- **`CLAUDE.md` and `AGENTS.md` are byte-identical** (41,155 bytes each) — yet CLAUDE.md
  cites AGENTS.md as a *distinct* reference. Real (verified).
- **README teaches v2.6 API while CLAUDE.md teaches v2.7** — divergent "how to use"
  surfaces. Real.
- `docs/release_notes.md` is a 6-line stub shadowing the real 187-line
  `docs/release_notes/v2.7.0.md`. Real.
- Stale sprint/plan/spike docs; `sprint5_followups.md:5` has a copy-paste header titled
  "Sprint 4". Real.
- **CORRECTED — not in scope:** the audit (lens 9) claimed `README.md` points to a
  non-existent bundled skill file. The current source is `docs/agent-skill/SKILL.md`,
  and root agent files are only bootstraps. Do **not** recreate a `.claude/` mirror.
  Only the *version* content in the README needs aligning.

## Scope
1. **De-duplicate CLAUDE.md / AGENTS.md.** Keep both as thin bootstraps pointing to
   `docs/agent-skill/SKILL.md` — eliminate byte-for-byte skill copies so they cannot drift.
2. **Version-align `README.md` to v2.7**, matching the `new_workflow`/`node` ContextVar
   authoring surface CLAUDE.md teaches. Keep the (valid) `docs/agent-skill/SKILL.md`
   reference; only update the API examples and version story.
3. **Fix `release_notes.md`** to redirect to `docs/release_notes/`.
4. **Archive stale docs** into `docs/historical/` with correct `Status:` headers; fix the
   `sprint5_followups.md` header.
5. **Align docs to the real API surface** recorded in `docs/api/m6-public-api.md` — the
   loader table, exported names, and aliases in CLAUDE.md must match what actually imports.
6. Fold the verified audit findings' resolutions into the v2.x release notes / migration
   notes.

## Locked decisions
- Docs only — **no code changes** in this milestone. If a doc/code mismatch is found that
  needs a code fix, it is a follow-up ticket, not a silent edit here.
- Cite `docs/api/m6-public-api.md` as the source of truth for importable names; do not
  re-derive the API from memory.

## Done criteria
- `CLAUDE.md`/`AGENTS.md` are not byte-identical; neither can silently drift from the
  other.
- README version story is single and current (v2.7); its skill-path reference still
  resolves.
- `release_notes.md` redirects correctly; stale docs are archived with correct status.
- Every importable name the docs claim is asserted by the M6 import-surface test.
- Full `pytest` green (docs-only changes should not move it).

## Touchpoints
`README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/` (release notes, historical, sprint docs),
`docs/api/m6-public-api.md` (read-only input).

## Anti-scope
No code edits. No re-opening of M1–M6. Do not chase the false-positive skill path.
