# Package Layer Audit 02: CLI Commands

Audit `vibecomfy/cli.py`, `vibecomfy/commands/`, and CLI command registration.

Questions:
- Is command registration explicit and discoverable?
- Are command modules grouped coherently?
- Are there stale/debug files under CLI/commands?
- What command paths are import or entrypoint contracts?

Return safe docs/index cleanup and deferrals.
