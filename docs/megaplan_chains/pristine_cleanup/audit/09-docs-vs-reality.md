## Docs vs Reality — Ranked Findings

### HIGH

1. **CLAUDE.md and AGENTS.md are byte-for-byte identical duplicates.** Both files are 41,155 bytes, 589 lines, identical in every character. `CLAUDE.md:580` even lists `AGENTS.md` as a separate reference ("agent-facing constraints and rules"), implying different content. This guarantees future drift and doubles maintenance cost with zero benefit.

2. **Resolved: README.md previously pointed to a non-existent bundled skill path.** The old README referenced `.claude/skills/vibecomfy/SKILL.md` even when that path was not a stable tracked source. The current repository uses `docs/agent-skill/SKILL.md` as the single authored skill source, with root agent files as bootstraps.

3. **Version API drift: README (v2.6) vs CLAUDE.md/AGENTS.md (v2.7) describe different authoring surfaces.** `README.md:136–158` shows v2.6 shape with `from vibecomfy.nodes.core import CLIPTextEncode, SaveImage` and `_id=` kwargs. `CLAUDE.md:392–408` shows v2.7 `from vibecomfy.templates import new_workflow, node` ContextVar pattern. The two canonical "how to use" documents teach incompatible current APIs. A new user following README vs an agent following CLAUDE.md will write different code.

### MEDIUM

4. **`docs/historical/agent_readable_templates_v2.md` is mis-categorized.** `historical/agent_readable_templates_v2.md:3` says "Status: active" with a start date of 2026-05-17 and an owner. A doc marked "active" in a directory called "historical" is self-contradictory — readers can't tell whether to treat it as current guidance or archived.

5. **`docs/template_cleanup_followups.md` is an ephemeral sprint artifact.** Captured 2026-05-23 on dev branch `agentic-port-20260523`, it lists outstanding work items (B.1–B.4 with effort estimates), a "Priority suggestion" section, and recoverability checkpoints. This is a task tracker, not reference documentation. It will rot as items are completed or abandoned.

6. **`docs/release_notes.md` is a 6-line stub shadowing a real 187-line release notes file.** The top-level `release_notes.md:3` only covers "v2.7 Sprint 1 Foundation" in 4 lines. The actual release notes live at `docs/release_notes/v2.7.0.md` (187 lines, with breaking changes, deprecations, and new features). Discovery is broken — the stub should redirect.

7. **`docs/sprint5_followups.md:5` has a copy-paste header error.** The first section is titled "Out Of Scope For Sprint 4" in a document named "Sprint 5 Follow-Ups." The body text says "Full bidirectional workflow roundtrip remains Sprint 5 work" — so the scope is about Sprint 5, but the header references Sprint 4. This is stale copy-paste from a prior sprint doc.

### LOW

8. **Missing migration guide: v2.4→v2.5.** Migration docs exist for `v2.3→v2.4`, `v2.5→v2.6`, and `v2.5→v2.7`, but there is no `migration_v24_to_v25.md`. The version migration chain has a gap; someone on v2.4 has no documented upgrade path before reaching v2.5→v2.6/v2.7 guides.

---

**Worst thing in this lens:** #1 — **CLAUDE.md and AGENTS.md are identical duplicates.** It's the most severe because (a) CLAUDE.md itself cites AGENTS.md as a *distinct* reference doc (line 580), meaning the project's own conventions believe these should differ, (b) any future edit to one must be manually mirrored to the other or they'll drift, and (c) it wastes 41KB of duplicated content that agents must parse twice for no benefit.
