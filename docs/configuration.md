# Configuration & Environment Map

Where megaplan reads its settings and secrets.

## Config Files

| What | Path | Managed By |
|---|---|---|
| User config | `~/.config/megaplan/config.json` | `megaplan config set|show|reset` (CLI) |
| User overrides (optional) | `~/.config/megaplan/config.toml` | Hand-edited; user-level defaults (vendor, prep_clarify) — *not* part of effective-config precedence |
| Project config (new) | `<project>/.megaplan/config.toml` | Hand-edited; project-scoped effective-config layer — highest precedence when `project_dir` is supplied |
| Project profiles | `.megaplan/profiles.toml` | Hand-edited or `megaplan config profiles` |
| Project state | `.megaplan/state.json` | Megaplan runtime |

## Project-Scoped Config Layer (`.megaplan/config.toml`)

A project can carry its own config at `<project>/.megaplan/config.toml`. This
is an **operator-authored** file — hand-edited, checked into the repository —
that provides per-project effective-config overrides without requiring every
team member to set global JSON values.

### Precedence (project-aware call sites)

When a call site supplies `project_dir` (currently only `_build_state_config`
in `megaplan init`), the resolution order is:

    DEFAULTS < ~/.config/megaplan/config.json < <project>/.megaplan/config.toml

1. **`DEFAULTS`** (lowest) — built-in compiled defaults in `megaplan.types`.
2. **Global JSON** — `~/.config/megaplan/config.json`, managed by
   `megaplan config set|show|reset`.
3. **Project TOML** (highest) — `<project>/.megaplan/config.toml`.

When `project_dir` is **omitted** (the default for every call site except
`_build_state_config`), the function behaves exactly as before: only global
JSON and DEFAULTS are consulted. An absent project config file is a no-op —
current behavior is fully preserved.

### Minimal example

```toml
[execution]
worker_timeout_seconds = 120
test_command = "pytest"
auto_approve = true
```

This would set `worker_timeout_seconds` to 120, `test_command` to `"pytest"`,
and `auto_approve` to `true` for every plan initialized in this project,
regardless of the user's global JSON config.

### Productive stream progress policy

Long-lived execute streams use `execution.slow_output_policy` to distinguish
productive work from a connection that is merely alive. The conservative
defaults allow 180 seconds of initial grace, measure visible output over 300
seconds, bound reasoning-only progress to 600 seconds and an active tool to 900
seconds, and require 30 seconds of sustained suspicion before a slow/silent
stream becomes fallback-eligible. A provider heartbeat alone has only 60
seconds of grace. Streaming transport timeouts surface immediately with the
`streaming_timeout` reason instead of being hidden inside an executor retry.

```toml
[execution.slow_output_policy]
enabled = true
initial_grace_s = 180
observation_window_s = 300
silence_timeout_s = 180
min_visible_chars_per_s = 0.05
reasoning_grace_s = 600
tool_grace_s = 900
heartbeat_grace_s = 60
escalation_grace_s = 30
surface_streaming_timeouts = true
```

Set `enabled = false` to retain transport/runtime timeouts without proactive
slow-output fallback. Unknown keys, wrong types, negative durations, and zero
silence/observation windows are rejected during plan initialization. The
validated effective policy is copied into plan state so a run is reproducible.

### Distinction from user-level `~/.config/megaplan/config.toml`

| File | Scope | Role |
|---|---|---|
| `~/.config/megaplan/config.toml` | User-wide | User-level defaults (`default_vendor`, `default_prep_clarify`) — loaded by `user_config.py`, *not* part of `get_effective` precedence |
| `<project>/.megaplan/config.toml` | Project-wide | Project-scoped effective-config layer — loaded by `io.load_project_config`, participates in `get_effective` and `setting_is_explicit` when `project_dir` is passed |

The user-level TOML exposes convenience defaults (e.g., which vendor to prefer
when no `--vendor` flag is given). The project-level TOML overrides actual
effective-config keys (`execution.test_command`, `execution.auto_approve`,
etc.) with higher precedence than global JSON.

### Explicit pin semantics

Any key present in the project TOML is treated as an **explicit pin** by
`setting_is_explicit(..., project_dir=...)`. This means profile-level
fallbacks (e.g., a profile's `adaptive_critique` or `critic_model` metadata)
are **not consulted** when the project config already sets the key — the
project operator's intent is deliberate and takes priority.

### Deferred non-init migration

Only `_build_state_config` in `megaplan init` receives `project_dir` in this
sprint. All other `get_effective` call sites (finalize, baseline, shannon,
chain, gate, review, execute, workers) remain on global+DEFAULTS. A future
targeted migration will extend `project_dir` threading to those call sites
as needed.

## Agent Routing

Megaplan resolves which model runs each pipeline phase through a fixed precedence chain:

1. **Explicit `--phase-model` pins** (CLI). `--phase-model plan=codex:high` beats everything below.
2. **Persisted `phase_model` entries** in the plan's `state.json`. These survive plan load/resume and have the same force as explicit CLI pins. When a profile phase is a TOML array (fallback chain), the persisted entry uses the compact `__fallback_json__:<json-array>` encoding so the chain survives serialization without being parsed as a raw agent spec.
3. **Profile phase slots** (from the selected built-in or custom profile TOML). Phase spec values can be scalar strings or TOML string arrays for fallback chains — see the main megaplan skill's **Fallback chains (v1)** section for the full advancement rules.
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
| `FIREWORKS_API_KEY` | Fireworks-hosted non-DeepSeek models, if explicitly configured |
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
~/.config/megaplan/config.json          # CLI-managed global config
~/.config/megaplan/config.toml          # Hand-edited user-level defaults (vendor, prep_clarify)
~/.hermes/.env                          # Provider keys
.megaplan/config.toml                   # Project-scoped config layer (overrides global JSON)
.megaplan/profiles.toml                 # Project-local profiles
cloud.yaml                              # Cloud deployment config (secrets list)
```
