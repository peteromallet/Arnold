# M2 Coverage Matrix — Documentation

## Overview

The coverage matrix (`coverage_matrix.py`) provides a machine-readable, exhaustive
classification of every credential surface in the Arnold/Hermes codebase. Each entry
declares:

- **credential_surface**: The code location or subsystem that handles credentials.
- **credential_type**: The kind of credential (PAT, API key, OAuth token, SSH key).
- **m2_status**: One of `covered`, `deferred`, or `uncovered`.
- **residual_risk**: `low`, `medium`, `high`, or `critical`.
- **deferral_target**: The milestone where coverage is planned (or `None` if not deferred).
- **notes**: Human-readable justification and mitigation context.

## Classification Rules

### `covered`
The credential path is fully brokered by the M2 Security Broker in production mode.
Raw credentials never reach the agent process. All agent-visible results are sanitized.

### `deferred`
The credential path is acknowledged as needing broker coverage but is explicitly
deferred to a later milestone (M4–M6). The residual risk is documented and accepted
for M2.

### `uncovered`
The credential path is documented but not planned for broker coverage in any current
milestone. Typically applies to free/local providers that don't carry secrets, or
paths where the architecture makes brokering infeasible.

## Coverage Summary

| Category | Count | Production Covered |
|----------|-------|-------------------|
| Git push-class mutations | 3 | 2 covered, 1 deferred (SSH bypass) |
| LLM API-key providers | 8 | 8 covered |
| LLM OAuth/refresh-token providers | 3 | 0 covered (deferred to M5–M6) |
| Skills hub GitHub auth | 1 | 0 covered (deferred) |
| MCP subprocess credentials | 1 | 0 covered (deferred) |
| Non-LLM tool credentials | 6 | 0 covered (deferred or uncovered) |
| Terminal/SSH/gh bypasses | 2 | 0 covered (deferred) |

## Conformance Integration

The `coverage_matrix.py` module exports a `get_coverage_matrix()` function that
returns all entries as a list of `CoverageEntry` dataclasses. Conformance checks
in later tasks (T15–T16) will:

1. Load the coverage matrix.
2. Cross-reference against the actual codebase credential surfaces.
3. Flag any surface found in code but missing from the matrix.
4. Flag any surface classified as `covered` but not actually routed through the broker.
5. Produce a conformance report with `PASS`/`FAIL`/`DEFERRED` per surface.

## Non-Production Uncovered Paths

The following paths are documented as **uncovered** for M2. Conformance output
must explicitly flag them rather than silently passing:

- `skills_hub.py::GitHubAuth` — GitHub API read tokens (PAT/gh CLI/GitHub App)
- `terminal_tool.py` — Shell access bypassing broker for git/ssh/gh operations
- `mcp_tool.py` — MCP subprocess environment with raw credentials from config.yaml
- `tts_tool.py` — ElevenLabs API key (`ELEVENLABS_API_KEY`)
- `image_generation_tool.py` — FAL.ai key (`FAL_KEY`)
- `web_tools.py` — Firecrawl API key (`FIRECRAWL_API_KEY`)
- `transcription_tools.py` — Groq API key (`GROQ_API_KEY`), OpenAI key (`VOICE_TOOLS_OPENAI_KEY`)
- `auxiliary_client.py` — Nous Portal OAuth, Codex OAuth, Anthropic OAuth refresh tokens
- `mcp_oauth.py` — MCP OAuth refresh tokens stored to disk
