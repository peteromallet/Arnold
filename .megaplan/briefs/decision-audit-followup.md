# Tighten docs/megaplan-decision.md per the audit

## Outcome
Restructure docs/megaplan-decision.md to apply 9 audit findings. Same substantive content, ~30% leaner, top-down (answer-first) ordering. The doc should pass the pyramid-principle test: reader gets the three-dial decision framework before supporting machinery, no rule restated more than once, each section earns its heading.

## Scope IN
Action these 9 findings (paraphrased — apply with judgment):

1. **Lead-in buries the answer (lines 8-11).** Open with one sentence and the three-dial table immediately. Push the "dials are independent, weigh holistically, mismatch means split" commentary into a 2-line note under the table.

2. **Tier table cells are paragraph-blobs (lines 78-82).** Each "Picks for" cell should be (a) one-sentence definition of the social configuration, (b) 3-5 example workloads as a short list, (c) one "drop down to X when…" guard. Move longer explanations (e.g., tier-5 vendor-interchange commentary) into short prose paragraphs below the table — once each, not embedded in cells.

3. **"Tighten the brief" stated 4×.** Currently appears at lines 20-25 (intro), line 51 (dominant variable), line 64 (missing #3/#4 surfaces flags), line 348 (operating principle). State it ONCE, in the brief section, as that section's headline. Delete duplicates.

4. **Phase-table recap bullets (lines 104-110)** re-narrate what the table shows. Replace with one sentence: "Each tier upgrades one block of phases to premium; once upgraded, a phase stays upgraded. Tier 5 doesn't add coverage — it splits premium across two vendors."

5. **Prep + feedback sections (lines 165-181, 183-196)** are parallel boilerplate for two CLI flags. Collapse into one section "Optional phases (`--with-prep`, `--with-feedback`)" with two short subsections or paragraphs.

6. **Notation section over-built (lines 200-247).** Replace with ~10 lines: the rule, one table with ~5 representative examples spanning spine + modifiers together. Delete the "Where to use this" subsection (it's filler).

7. **Robustness paragraph (lines 136-140)** restates the table. Replace with one line: "Cost scales ~1.5-2× from `light` → `full`, another ~1.3× to `thorough`."

8. **Forward references (lines 23, 247, 266-267, 295).** Inline the relevant info or delete the cross-ref where the content is 1-2 lines away.

9. **Operating principles section (lines 346-360) mostly repeats earlier material.** Keep only "one profile per sprint" and "bake-off is opt-in" as principles. Keep one anti-pattern: "always use Claude is wrong." Delete the rest — they're restatements of rules already stated in their natural homes.

## Scope OUT
- No edits to `megaplan/data/instructions.md` (the megaplan tooling skill) or any other file.
- No new substantive content — only structural/prose tightening.
- Findings #10 (hedge clauses) and #11 (heading renames) are deferred.

## Locked decisions
- Canonical names stay: profiles `solo / directed / partnered / premium / apex`, robustness `bare / light / full / thorough / extreme`, depth unchanged.
- "Always run megaplan, even for tiny work" rule stays. `bare` is the floor.
- Tier 4/5 framing on "premium executes the code" stays.
- All cross-references to other skills (`megaplan`, `bakeoff`) stay.

## Open questions
- Voice choices in rewrites (planner judgment — preserve the existing direct, em-dash-heavy style).
- Exact wording of collapsed sections (planner judgment).

## Constraints
- Don't lose any substantive rule from the current doc. If a finding asks to delete something that turns out to carry unique substantive content, keep that content (move it; don't drop it).
- Preserve the existing frontmatter (name/description).
- Preserve the existing skill cross-references.
- Output must read top-down — never force the reader to skip ahead.

## Done criteria
- Each of findings #1-9 has been addressed (with notes if a finding turned out to need adjustment in execution).
- No rule appears twice in the doc.
- The doc is meaningfully shorter (target: ~30% reduction in length).
- Doc renders cleanly (valid markdown, working tables, working symlink at `~/.claude/skills/megaplan-decision/SKILL.md`).

## Touchpoints
- `docs/megaplan-decision.md` (only)

## Anti-scope
- Don't touch `megaplan/data/instructions.md`.
- Don't touch any code (CLI, profile TOMLs, etc.).
- Don't add new claims or new sections.
- Don't change canonical names or shorthand syntax.
- Don't expand scope to "while we're here, let me also…"
