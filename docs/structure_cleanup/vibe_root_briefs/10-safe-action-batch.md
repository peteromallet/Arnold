Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Synthesize a safe action batch for cleaning top-level `vibecomfy/*.py`.

Context:
- Other agents will inspect detailed lenses; you independently inspect the current tree and recommend a small, testable batch.
- User wants deletion and reorganization, not just docs.
- Do not edit files.

Focus:
- Prefer actions that reduce root clutter with low behavioral risk.
- Include deletions of shims/dead files where proven.
- Include moves only where imports/tests are straightforward.
- Avoid huge public API migrations.

Output:
- "Do now" list, "Do later" list, "Do not do" list.
- For each do-now item, include commands/tests to verify.
- Keep under 800 words.
