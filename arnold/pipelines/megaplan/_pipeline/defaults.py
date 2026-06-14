"""Pinned default models for claude: and codex: agent specs.

When a spec has no explicit model, megaplan injects the appropriate default
so every run is reproducible regardless of the user's local CLI configuration.

The canonical GPT-5.5 model ID for ``codex`` is ``gpt-5.5`` — the string
accepted by the ``codex exec -c model=...`` flag.
"""

from __future__ import annotations

CLAUDE_DEFAULT_MODEL: str = "claude-opus-4-7"
CODEX_DEFAULT_MODEL: str = "gpt-5.5"
