Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Task: Audit top-level package files for generated, cached, vendored, or environment-specific artifacts that should not live under `vibecomfy/`.

Context:
- We should delete generated local junk and move generated-but-checked-in artifacts only if the repo has a better fixture/cache location.
- Do not edit files.

Focus:
- `vibecomfy/comfy_metadata.json`
- generated node wrapper surfaces
- any package-root JSON/data-ish files
- `py.typed`
- package root modules that are generated snapshots in disguise

Output:
- For each artifact-like file: keep/move/delete, evidence, impact, verification command.
- Keep under 700 words.
