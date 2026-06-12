Working directory: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

Synthesize a safe first cleanup batch for the `artifacts/` and `out/` layer.

Constraints:

- Do not delete ignored `out/` content without user approval.
- Prefer moving active docs into `docs/` only when references are clear.
- Keep generated snapshots if tests or docs depend on exact paths.

Return ordered actions, deferrals, and verification commands. Under 650 words.
