# Tighten docs/megaplan-decision.md — pure restructure, zero additions

## Outcome
Apply 9 enumerated audit findings to the current `docs/megaplan-decision.md`. Same substantive content (every existing rule and feature mention preserved), ~30% leaner, top-down (answer-first) ordering. The doc must end shorter than it started.

## Hard rule — NO NEW CONTENT
This run is removal, reordering, collapsing, and merging only. **Adding a single new sentence of substantive content is a failure.** Specifically forbidden:
- No new section headings.
- No new flag documentation (in particular: do not add anything about `--in-worktree`, `--with-prep`, `--with-feedback`, `--vendor`, `--critic`, etc. that isn't already in the doc).
- No new worked invocations.
- No new tables, no new bullets that introduce information not already present.
- No "while we're here, this is also worth saying" expansions.

A previous run on this brief added a `--in-worktree` section that was not requested. That section is legitimate (it was authored elsewhere) and **stays** — but it is the ceiling for any future additions, not an example to imitate. Do NOT add similar expansions.

## Scope IN — the 9 audit findings

Apply each. Where a line-number is given it's pre-restructure; use it as a starting hint, then locate the current text by searching.

1. **Lead-in buries the answer.** Open with one sentence ("Three dials decide how to run a sprint:" or similar) and the three-dial table *immediately*. The "dials are independent, weigh holistically, mismatch means split" commentary moves to a 2-line note *under* the table.

2. **Tier table cells are paragraph-blobs.** Each "Picks for" cell in the "When to pick each tier" table should be: (a) one-sentence definition of the social configuration, (b) 3-5 example workloads as a short list, (c) one "drop down to X when…" guard. Move the longer explanations (e.g. tier-5 vendor-interchange commentary, tier-4 "tiers 4-5 are the only tiers where premium executes" framing) into short prose paragraphs below the table — once each, not embedded in cells. Preserve all existing claims; just relocate them.

3. **"Tighten the brief" stated multiple times.** Currently appears in: the intro, the brief section, the operating principles. State it ONCE, in the brief section, as that section's headline. Delete the other occurrences (their nuance, if any, gets folded into the single canonical statement).

4. **Phase-table recap bullets re-narrate the table.** Replace the "Two things to notice in the phase table" bulleted block with one sentence: "Each tier upgrades one block of phases to premium; once upgraded, a phase stays upgraded. Tier 5 doesn't add coverage — it splits premium across two vendors."

5. **Prep + feedback sections are parallel boilerplate.** Collapse "When to add a prep phase" and "When to add a feedback phase" into one section "Optional phases (`--with-prep`, `--with-feedback`)" with two short subsections. Preserve every existing bullet from both; just unify the wrapper text.

6. **Notation section over-built.** Replace the multi-table notation section with ~10 lines: the rule ("write `profile/robustness/depth`, omit defaults, append modifiers"), one table with ~5 representative examples spanning spine + modifiers together. Delete the "Where to use this" subsection. Preserve all the syntax conventions (`@vendor`, `, critic=...`, `+prep`, `+feedback`).

7. **Robustness paragraph restates the table.** Replace the prose paragraph after the robustness table with one line: "Cost scales ~1.5-2× from `light` → `full`, another ~1.3× to `thorough`."

8. **Forward references.** "See above/below" pointers that name content within 1-2 lines: inline the relevant info or delete the cross-ref. The critique==review invariant's "see below" reference (2 lines away from the section it points at) is pure noise — delete.

9. **Operating principles section mostly repeats earlier material.** Keep only "One profile per sprint" and "Bake-off is opt-in." Keep one anti-pattern bullet: "Always use Claude is wrong" (it carries novel content). Delete the rest — they restate rules stated in their natural homes earlier in the doc.

## Locked decisions
- Canonical names: profiles `solo / directed / partnered / premium / apex`; robustness `bare / light / full / thorough / extreme`; depth unchanged.
- "Always run megaplan, even for tiny work" rule stays. `bare` is the floor.
- Tier 4/5 execution-difficulty framing stays.
- The `--in-worktree` section currently in the doc stays verbatim. Do not edit it. Do not collapse it. Do not move it.
- All cross-references to other skills (`megaplan`, `bakeoff`) stay.

## Open questions
Voice choices in rewrites (planner judgment — preserve existing direct, em-dash-heavy style).

## Constraints
- Don't lose any substantive rule or feature mention. If a finding asks to delete something that turns out to carry unique substantive content, keep that content (move it, don't drop it).
- Preserve frontmatter unchanged.
- Output must read top-down.
- Final doc must be meaningfully shorter than the input. If the doc is the same length or longer at the end, the run has failed.

## Done criteria
- Each finding #1-9 addressed.
- No rule appears twice.
- Tier table cells are scannable (single sentence + short list + one-line guard, not multi-paragraph blobs).
- Doc is ~30% shorter (line count down by ~30%, target).
- `--in-worktree` section unchanged.

## Touchpoints
`docs/megaplan-decision.md` only.

## Anti-scope (reiterated)
No new content. No new sections. No new flag docs. No new examples. No new claims. If you're tempted to add something for clarity, the answer is no — the audit is a removal pass.
