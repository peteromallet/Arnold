# Add `megaplan config profiles diff` subcommand

## Goal

Add a new subcommand `megaplan config profiles diff <profile-a> <profile-b>` that prints a phase-by-phase comparison of two profiles, highlighting where they differ.

## Motivation

When running `megaplan bakeoff`, users pick 2–3 profiles to compare. Today the only way to understand *what's actually different* between two profiles is to open their TOML files side by side. A built-in diff subcommand would make profile comparison self-describing and reduce bakeoff onboarding friction.

## Requirements

### CLI

- Subcommand path: `megaplan config profiles diff <profile-a> <profile-b>`
- Both arguments required and positional.
- Unknown profile name → exit non-zero with a clear error message showing known profiles.
- Resolves profiles via the existing `load_profiles()` machinery so built-in, user, and project layers are all discoverable.

### Default output (human-readable)

For each phase key present in either profile, print one row:

```
phase             profile-a          profile-b          diff
plan              claude             hermes:kimi-k2.6   yes
critique          codex              hermes:glm-5.1     yes
execute           codex              hermes:glm-5.1     yes
...
```

- Columns: `phase`, `<profile-a-name>`, `<profile-b-name>`, `diff` (`yes`/`no`).
- Missing value for a phase in one profile → show `(not set)` in that column and `yes` in diff.
- Rows sorted by phase name; phases where both profiles agree still printed but with `diff=no`.
- A trailing summary line: `N of M phases differ.`

### JSON output

- `--json` flag emits a structured object suitable for piping to `jq`:

```json
{
  "profile_a": "standard",
  "profile_b": "all-kimi",
  "phases": [
    {"phase": "plan", "profile_a": "claude", "profile_b": "hermes:moonshotai/kimi-k2.6", "diff": true},
    ...
  ],
  "differing_phase_count": 11,
  "total_phase_count": 12
}
```

- No human-readable table when `--json` is passed — pure JSON on stdout.

### Tests

- Minimum coverage:
  - Two profiles with some overlapping and some differing phases → correct `diff` column values.
  - Phase present in one profile but not the other → `(not set)` rendered and counted as differing.
  - `--json` flag produces valid JSON with the documented schema.
  - Unknown profile name → non-zero exit, error message lists known profiles.
  - Two identical profiles → `differing_phase_count == 0` and summary line reflects that.

## Out of scope

- Colorized diff output (ANSI colors) — keep v1 plain-text.
- Profile *merging* or *editing* via the CLI.
- Diffing more than two profiles at once (v1 is strictly pairwise).

## Success criteria

1. `megaplan config profiles diff standard all-kimi` prints a table with the columns and summary described above.
2. `megaplan config profiles diff standard all-kimi --json` emits valid JSON conforming to the documented schema.
3. Tests for the documented scenarios pass.
4. No regressions in existing profile-related tests.
