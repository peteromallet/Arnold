# Documentation Accuracy Audit

## Outcome
Every piece of human-facing project documentation accurately reflects the
**current** state of the code. Statements that are stale, wrong, or describe
removed/renamed features are corrected, removed, or updated — surgically, in
place. Code is ground truth; docs follow code.

## Scope (IN)
- `docs/*.md` — the 21 top-level design/architecture/feature docs.
- `docs/foundation-audit/*.md` — the 11 FOUNDATION_* component docs + preamble.
- `README.md`
- `CHANGELOG.md` (only correct factual inaccuracies about what shipped; do NOT
  rewrite history or re-date entries).

Each in-scope doc must be checked against the actual `megaplan/` source:
CLI flags, subcommand names, config keys, profile/phase/workflow descriptions,
robustness levels, file paths, function/class names, and described behavior.

## Scope (OUT / anti-scope — do NOT touch)
- `docs/archive/**` — historical sprint records; leave exactly as-is.
- `megaplan/agent/skills/**/references/**` and other vendored upstream skill docs.
- `.desloppify/**` — tool run artifacts.
- `megaplan/pipelines/**/prompts/**`, `megaplan/data/**/*.md` — runtime prompt/data
  assets, not human documentation.
- **Source code.** Do not change `.py` files to make code match docs. When a doc
  and the code disagree, the **code is correct** and the **doc** is fixed.
- Tests. Do not add or modify tests.

## Locked decisions
- Code is ground truth. Every fix moves the doc toward the code, never the reverse.
- Surgical edits only: preserve each doc's existing structure, headings, voice,
  internal links, and intent. No wholesale rewrites, no reflowing untouched prose.
- Do not author brand-new docs. This sprint corrects existing docs only.
- Verify every claim against the repository before changing it — do not "fix" a
  doc from memory or assumption.

## Open questions for the planner to resolve
- Which docs have drifted most (e.g. CLI flags renamed, phases added/removed,
  config keys changed)?
- Are there docs describing features that have been removed or substantially
  refactored since the doc was written?
- Where do docs make claims about file/function names that no longer exist?

## Constraints
- Preserve valid internal cross-links and markdown structure.
- Code blocks and command examples must match real, current CLI/API surfaces.
- Do not introduce claims the code does not support.

## Done criteria
- Every in-scope doc has been verified against current code.
- Each correction is grounded in a specific code reference (file + symbol/flag).
- No in-scope doc contains a statement contradicted by the current code.
- A short per-doc summary of what changed (or "verified, no change needed").

## Touchpoints
- Audited surfaces: `docs/`, `docs/foundation-audit/`, `README.md`, `CHANGELOG.md`.
- Ground-truth source: `megaplan/` (CLI in `megaplan/cli*`, handlers, orchestration,
  profiles, types, schemas, workflow).
