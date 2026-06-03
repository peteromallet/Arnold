# Configuration & Environment Map

Where megaplan reads its settings and secrets.

## Config Files

| What | Path | Managed By |
|---|---|---|
| User config | `~/.config/megaplan/config.json` | `megaplan config set|show|reset` (CLI) |
| User overrides (optional) | `~/.config/megaplan/config.toml` | Hand-edited; overrides JSON defaults |
| Project profiles | `.megaplan/profiles.toml` | Hand-edited or `megaplan config profiles` |
| Project state | `.megaplan/state.json` | Megaplan runtime |

## Agent Routing

Megaplan resolves which model runs each pipeline phase through a fixed precedence chain:

1. **Explicit `--phase-model` pins** (CLI). `--phase-model plan=codex:high` beats everything below.
2. **Persisted `phase_model` entries** in the plan's `state.json`. These survive plan load/resume and have the same force as explicit CLI pins.
3. **Profile phase slots** (from the selected built-in or custom profile TOML).
4. **`DEFAULT_AGENT_ROUTING`** — the project's hardcoded fallback. Premium phases (plan, critique, revise, finalize, execute, review, etc.) use the symbolic agent spec **`premium`** (e.g., `premium:low`), not a concrete vendor name. Non-premium phases (prep) use `hermes`.

The symbolic `premium` spec is a vendor-neutral placeholder, **not a runnable worker**. Before dispatch it is resolved to `claude` or `codex` based on the effective premium vendor, which follows its own precedence:

1. **`--vendor` CLI flag** (`claude` or `codex`) — highest.
2. **`[agent] vendor`** in user config (`~/.config/megaplan/config.json`).
3. **Project default** — `claude` unless overridden.

Choosing `--vendor codex` means every unresolved symbolic `premium` slot becomes `codex` (no implicit Claude invocation). Choosing `--vendor claude` means the reverse. Concrete premium profiles that are not marked `vendor_locked`, including `all-claude`, are still rewritable by `--vendor`. Profiles with `vendor_locked = true` (`all-codex`, `variable-claude`, `variable-codex`, `apex`) are exempt from vendor rewriting.

**Concrete-only user config.** The `agents.<phase>` keys in user config must be explicit worker names (`claude`, `codex`, `hermes`). `megaplan config set agents.plan premium` is rejected — the symbolic spec is a source-default/profile construct, not a user-facing value. Use the `--vendor` flag or `[agent] vendor` to control which vendor premium phases route to, and use `--phase-model` or explicit `agents.<phase> = claude`/`codex` to pin individual phases.

Display surfaces (`megaplan config show`, `megaplan status`, cloud templates) always show the resolved concrete spec, never the symbolic `premium` placeholder.

## Provider & Agent Keys

Provider keys live in `~/.hermes/.env` (dotenv format, one `KEY=value` per line) and fall back to process environment variables:

| Variable | Used By |
|---|---|
| `ANTHROPIC_API_KEY` | Claude (premium plan / review / hard execute) |
| `OPENAI_API_KEY` | Codex / GPT (premium plan / review / hard execute) |
| `DEEPSEEK_API_KEY` | DeepSeek v4-pro / flash (cheap phases) |
| `FIREWORKS_API_KEY` | Fireworks-hosted DeepSeek (alternative cheap provider) |
| `OPENROUTER_API_KEY` | OpenRouter (Kimi / GLM / other open models) |
| `GITHUB_TOKEN` | Push, private-clone, and PR operations |
| `CLAUDE_CODE_REFRESH_TOKEN` | Claude Code agent session refresh |

The `megaplan setup` command detects installed agents and walks through credential setup interactively.

## Cloud Secrets

`cloud.yaml` has a `secrets:` list. Each name in that list is a local process environment variable name. During `megaplan cloud deploy`, the current values of those variables are uploaded to the remote container and redacted from cloud log output where possible.

Example:

```yaml
secrets:
  - OPENAI_API_KEY
  - GITHUB_TOKEN
  - ANTHROPIC_API_KEY
```

## Database Mode

When using Supabase Postgres for shared state:

| Variable | Purpose |
|---|---|
| `SUPABASE_DB_URL` | Supabase Postgres connection string |
| `MEGAPLAN_ACTOR_ID` | Identifies this machine / cloud instance for state-locking |

Install with `pip install 'megaplan-harness[db]'`, then set both variables.

## Quick Reference: Key Paths

```
~/.config/megaplan/config.json          # CLI-managed config
~/.config/megaplan/config.toml          # Hand-edited overrides
~/.hermes/.env                          # Provider keys
.megaplan/profiles.toml                 # Project-local profiles
cloud.yaml                              # Cloud deployment config (secrets list)
```
