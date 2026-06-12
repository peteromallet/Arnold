Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Determine which top-level `vibecomfy/*.py` modules are intentional public API or package-level boundaries.

Context:
- Cleanup must not accidentally destroy public package ergonomics.
- But public API should be explicit, not accidental root sprawl.
- Do not edit files.

Focus:
- Inspect `vibecomfy/__init__.py`, docs, examples, recipes, and tests for top-level imports.
- Identify modules that should remain at root because users plausibly import them directly.
- Identify modules that should be private/internal or moved despite current root placement.
- Note any root modules that need README documentation if kept.

Output:
- Keep-at-root list with justification.
- Demote/move list with import evidence.
- Ambiguous/public-risk list.
- Keep under 900 words.
