# Skill distribution cleanup — one home per skill, symlinks all the way down

## Outcome

Every `megaplan-*` skill ends up with exactly one canonical home (inside the
megaplan package, under `megaplan/data/`), every installed copy under
`~/.claude/skills/` and `~/.codex/skills/` is a symlink into that source, and
drift between the source and the installed file becomes structurally
impossible. The `megaplan-observe` skill — currently hand-installed and
unregistered — joins the family and ships with `megaplan setup`.

## Scope (IN)

1. Promote `megaplan-observe` into the package:
   - Copy current `~/.claude/skills/megaplan-observe/SKILL.md` into
     `megaplan/data/observe_skill.md`.
   - Add `_canonical_observe_skill()` helper in `megaplan/cli.py` matching the
     existing `_canonical_tickets_skill` / `_canonical_decision_skill` /
     `_canonical_epic_skill` shape.
   - Add a branch in `bundled_global_file()` for `"observe_skill.md"`.
   - Add `_GLOBAL_TARGETS` entries for both Claude and Codex installs of
     `megaplan-observe`, with `install: "symlink"`.

2. Eliminate the install-time composition for the main skill by introducing
   committed pre-composed bundles:
   - Create `megaplan/data/_composed/claude_skill.md`,
     `megaplan/data/_composed/codex_skill.md`, and
     `megaplan/data/_composed/cursor_rule.mdc`.
   - Each contains the exact string that `bundled_global_file()` currently
     returns for that target — i.e. `_SKILL_HEADER + instructions.md +
     "\n\n" + <appendix>` (or `_CURSOR_HEADER + instructions.md` for cursor).
   - Refactor `bundled_global_file()` so the `claude_skill.md`,
     `codex_skill.md`, and `cursor_rule.mdc` branches read directly from
     `megaplan/data/_composed/<name>` instead of recomposing inline. The
     `"skill.md"` (header + instructions only) variant can keep composing
     inline OR also live in `_composed/`; pick the choice that keeps
     `bundled_global_file()` uniform.
   - Flip the `install:` mode for the three composed `_GLOBAL_TARGETS` entries
     (`.claude/skills/megaplan/SKILL.md`, `.codex/skills/megaplan/SKILL.md`,
     `.cursor/rules/megaplan.mdc`) from `"copy"` to `"symlink"`.
   - Add a CLI subcommand `megaplan setup --regen-composed` (or an equivalent
     standalone command — pick the name that fits cli.py's existing surface)
     that reads `instructions.md` + appendices, writes the three files under
     `_composed/`, and exits non-zero if any of them changed (so a CI / hook
     can detect drift).

3. Add a drift guard that fires before every commit in the megaplan repo:
   - A pre-commit hook (use the existing `pre-commit` framework if the repo
     already uses it; otherwise a plain `.git/hooks/pre-commit` script) that
     runs `megaplan setup --regen-composed` (or the equivalent) and fails the
     commit if the composed files would change. The hook must `git add` the
     regenerated files so a developer fixing the failure just re-runs `git
     commit`.

4. Reconcile out-of-package state. Package always wins; no diff inspection
   needed:
   - Delete `/Users/peteromalley/Documents/poms_skills/megaplan-decision/`.
   - Delete `/Users/peteromalley/Documents/poms_skills/megaplan-tickets/`.
   - Delete the regular directory `~/.claude/skills/megaplan-epic/` (the
     installer wants a symlink here; the regular dir is drift).
   - Delete the regular directory `~/.claude/skills/megaplan-observe/`
     (will be recreated as a symlink by `megaplan setup`).
   - Run `megaplan setup --force` after the deletions to materialize the
     intended symlink-everywhere layout.
   - Verify: `ls -la ~/.claude/skills/megaplan*` shows every megaplan-family
     skill as a symlink into the megaplan package.

5. Update the shadow-doc test:
   - `megaplan/tests/test_setup_no_shadow_skills.py` currently encodes the
     "single-source must symlink, multi-source may copy" rule. Update the
     test to assert the new invariant: **every** `_GLOBAL_TARGETS` entry uses
     `install: "symlink"`. The pre-composed files in `_composed/` are now
     single-source from the installer's perspective.

6. Write a short ADR at `docs/skill-distribution.md` capturing:
   - The two principles (one home per skill; symlink everything, including
     composed bundles, by pre-composing at commit time).
   - The canonical-home table for every megaplan-family skill.
   - The drift-guard mechanism and how to extend it if a new skill is added.
   - A short note on the personal vs package split, naming
     `~/Documents/poms_skills/` as the personal-toolbox home for non-megaplan
     skills.

## Scope (OUT)

- No changes to skills outside the megaplan family (no touching `bakeoff`,
  `subagent-launcher`, `hivemind`, etc. — those stay in
  `~/Documents/poms_skills/`).
- No CLI ergonomics changes to `megaplan setup` beyond adding the
  `--regen-composed` mode.
- No changes to the content of `instructions.md` / `claude_skill.md` /
  `codex_skill.md` beyond what's needed to seed `_composed/`. Existing edits
  in the working tree (the three sibling-skill pointers added earlier) are
  carried through.
- No changes to the `cursor` skill loading path beyond installing the
  composed bundle.
- No new tests beyond updating the shadow-doc test. Existing setup tests
  must still pass.

## Locked decisions

- **Canonical home for `megaplan-*` skills is the megaplan package** under
  `megaplan/data/`. Personal `~/Documents/poms_skills/` is for non-megaplan
  skills only.
- **Package always wins** when reconciling `poms_skills/` vs
  `megaplan/data/` — no diff inspection.
- **Composition moves from install-time to commit-time.** Composed bundles
  live in `megaplan/data/_composed/`, committed to the repo.
- **Pre-commit hook** is the drift guard (not a runtime check on every CLI
  invocation, which has a coverage hole when Claude reads the skill without
  invoking the megaplan CLI).
- **ADR at `docs/skill-distribution.md`** documents the strategy.

## Open questions

- Naming of the regen subcommand: `megaplan setup --regen-composed` vs a
  top-level verb like `megaplan setup regen` vs an internal-only helper
  invoked by the hook. Pick whichever keeps cli.py's existing surface
  consistent; document the choice in the ADR.
- Whether `pre-commit` framework is already in use in this repo. Check
  `.pre-commit-config.yaml`; if present, add the regen hook there. If absent,
  use a plain `.git/hooks/pre-commit`. The ADR should reflect what was
  actually chosen.

## Constraints

- Working tree currently has uncommitted edits to
  `megaplan/data/instructions.md` (three pointers added earlier to
  `megaplan-observe`, `megaplan-epic`, `megaplan-tickets` sibling skills).
  These edits MUST be preserved through the run. The first action that
  generates `_composed/` files will pick them up automatically.
- The destructive cleanup in step 4 deletes files in
  `~/Documents/poms_skills/` and `~/.claude/skills/` — outside the project
  dir. The execute phase must perform these deletions in a recoverable order
  (sources promoted into the package first; installer state regenerated;
  external state deleted last) so a failure mid-run doesn't leave the
  user with no working skill installation.
- The pre-commit hook must not break the developer experience: a failed
  regen-check that auto-stages the fix and prints a one-line message is
  acceptable; a hook that crashes or hangs is not.
- The existing test `test_setup_no_shadow_skills.py` is the invariant
  enforcement point. Don't loosen it — tighten it to the new rule.

## Done criteria

1. `ls -la ~/.claude/skills/megaplan*` shows five entries
   (`megaplan`, `megaplan-decision`, `megaplan-epic`, `megaplan-observe`,
   `megaplan-tickets`), and the four `megaplan-*` sub-skills are symlinks
   into `<megaplan-package>/data/`. The main `megaplan` directory contains a
   single `SKILL.md` that is a symlink into
   `<megaplan-package>/data/_composed/claude_skill.md`.
2. `ls -la ~/.codex/skills/megaplan*` shows the same shape for Codex.
3. `~/Documents/poms_skills/megaplan-decision` and
   `~/Documents/poms_skills/megaplan-tickets` no longer exist.
4. Editing `megaplan/data/instructions.md` and running
   `megaplan setup --regen-composed` regenerates the three `_composed/`
   files, and the new content appears at every install target via the
   symlinks without any further action.
5. Attempting to commit a change to `instructions.md` without re-running
   regen fails the pre-commit hook with a clear message; running it once
   makes the commit succeed.
6. `pytest megaplan/tests/test_setup_no_shadow_skills.py` passes against
   the new invariant ("every `_GLOBAL_TARGETS` entry symlinks").
7. `docs/skill-distribution.md` exists, names the canonical home for each
   skill, and documents the drift-guard mechanism.
8. The full `megaplan setup --force` run completes without error and leaves
   the install layout matching done-criterion #1 and #2.

## Touchpoints

- `megaplan/cli.py` — `_GLOBAL_TARGETS`, `bundled_global_file()`, the
  `_canonical_*_skill()` helpers, possibly `_install_owned_file()` and the
  setup command surface (new `--regen-composed` mode).
- `megaplan/data/observe_skill.md` — NEW.
- `megaplan/data/_composed/claude_skill.md` — NEW.
- `megaplan/data/_composed/codex_skill.md` — NEW.
- `megaplan/data/_composed/cursor_rule.mdc` — NEW.
- `megaplan/data/instructions.md` — already dirty, no further edits expected.
- `megaplan/tests/test_setup_no_shadow_skills.py` — tighten invariant.
- `.git/hooks/pre-commit` OR `.pre-commit-config.yaml` — add regen guard.
- `docs/skill-distribution.md` — NEW ADR.
- External state cleanup (outside the project dir):
  `~/Documents/poms_skills/megaplan-decision/`,
  `~/Documents/poms_skills/megaplan-tickets/`,
  `~/.claude/skills/megaplan-epic/`,
  `~/.claude/skills/megaplan-observe/`.

## Anti-scope

- Don't touch any non-megaplan skill (no `bakeoff`, no `subagent-launcher`,
  etc.) — they live in `~/Documents/poms_skills/` and stay there.
- Don't change the content of any megaplan skill beyond what's mechanically
  required to move composition. The earlier sibling-pointer edits in
  `instructions.md` are the only content change; preserve them.
- Don't add new megaplan-family skills, rename existing ones, or refactor
  the `_GLOBAL_TARGETS` schema beyond the install-mode flip.
- Don't introduce a runtime drift check (mtime poll, every-CLI-call guard)
  — the pre-commit hook is the chosen mechanism.
- Don't change the personal-collection sync mechanism in
  `~/Documents/poms_skills/sync.sh` — that's out of scope for this sprint.
- Don't migrate other Claude Code skills to use the same pre-compose pattern
  — this sprint is about the megaplan family only.
