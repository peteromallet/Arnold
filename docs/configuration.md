# Configuration & Environment Map

Where megaplan reads its settings and secrets.

## Config Files

| What | Path | Managed By |
|---|---|---|
| User config | `~/.config/megaplan/config.json` | `megaplan config set|show|reset` (CLI) |
| User overrides (optional) | `~/.config/megaplan/config.toml` | Hand-edited; overrides JSON defaults |
| Project profiles | `.megaplan/profiles.toml` | Hand-edited or `megaplan config profiles` |
| Project state | `.megaplan/state.json` | Megaplan runtime |

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
