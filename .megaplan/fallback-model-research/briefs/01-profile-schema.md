Working directory: /Users/peteromalley/Documents/Arnold

Task: Research what it would take to allow sequential fallback model lists in Megaplan profiles, e.g. a profile value that means "try codex:gpt-5.5, then codex:gpt-5.4, then hermes:deepseek:deepseek-v4-pro" if the first model fails due to timeout/limits/provider errors.

Your lens: profile parsing, validation, config persistence, CLI/user/project/built-in profile layering, and backwards compatibility.

Inspect at least:
- arnold_pipelines/megaplan/profiles.py
- arnold_pipelines/megaplan/profiles/policy.py
- arnold_pipelines/megaplan/profiles/partnered-5.toml
- arnold/agent/contracts.py
- tests around profile parsing and parser snapshots.

Return:
- exact files/functions that need changes
- recommended TOML syntax
- compatibility hazards
- tests that should be added/updated
- a concise implementation plan

Keep final answer under 900 words. Take a position.
