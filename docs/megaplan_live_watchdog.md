# Megaplan Live Watchdog Supervisor

A small operational harness that discovers likely-live Megaplan/Arnold runs on
the local machine, classifies their health, and uses the `live-supervisor`
Arnold pipeline to decide safe repair actions.

## Manual usage

Run a single scan from the repo root:

```bash
python scripts/megaplan_live_watchdog.py --once
```

By default only plans with a live process or recent activity (state/event mtime)
within the last **24 hours** are included. Change the window:

```bash
python scripts/megaplan_live_watchdog.py --once --lookback-hours=4
```

Use `0` to disable the age filter and scan every non-terminal plan:

```bash
python scripts/megaplan_live_watchdog.py --once --lookback-hours=0
```

Limit the scan roots:

```bash
python scripts/megaplan_live_watchdog.py --once \
  --roots="~/Documents,/tmp" \
  --report-path=/tmp/watchdog-report.json
```

Use `--repair-runner=dry-run` to classify and diagnose without executing any
allowlisted commands.

## Hourly scheduling

### macOS `launchd`

Save as `~/Library/LaunchAgents/com.megaplan.live-watchdog.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.megaplan.live-watchdog</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>/path/to/repo/scripts/megaplan_live_watchdog.py</string>
    <string>--once</string>
    <string>--report-path=/tmp/megaplan-watchdog-report.json</string>
  </array>
  <key>StartInterval</key>
  <integer>3600</integer>
  <key>StandardOutPath</key>
  <string>/tmp/megaplan-watchdog.out</string>
  <key>StandardErrorPath</key>
  <string>/tmp/megaplan-watchdog.err</string>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.megaplan.live-watchdog.plist
```

### Cron

```cron
0 * * * * cd /path/to/repo && python3 scripts/megaplan_live_watchdog.py --once --report-path=/tmp/megaplan-watchdog-report.json
```

## Architecture

- **Daemon/CLI** (`scripts/megaplan_live_watchdog.py`) owns scanning, registry
  persistence, retry timing, and report emission. It never performs its own
  classification or allowlist decisions.
- **Discovery engine** (`arnold_pipelines/megaplan/watchdog/`) reads
  `state.json` and `events.ndjson` directly from the filesystem, scans `ps`
  for process signatures, and correlates processes to plans. It works even
  when the installed `megaplan` CLI is broken.
- **Pipeline** (`arnold_pipelines/megaplan/pipelines/live_supervisor/`) is an
  Arnold neutral pipeline invoked in-process via `run_pipeline()` with a
  `RuntimeEnvelope`. It classifies, diagnoses, decides repairs, and emits a
  recheck request.

## Pipeline I/O contract

Input: `initial_state={"snapshot": <Snapshot dict>}`.

Output artifact files written under `RuntimeEnvelope.artifact_root`:

| Stage | File | Contents |
|-------|------|----------|
| `classify` | `classifications.json` | Per-incident `health_category` |
| `diagnose` | `diagnoses.json` | Per-incident diagnosis + reasoning |
| `repair_decision` | `repair_decisions.json` | Recommended command + allowlist verdict |
| `recheck_emit` | `recheck_emit.json` | `recheck_after` timestamp, `resumable` flag, decisions |

The CLI reads these artifacts after pipeline execution and selects non-`all_good`
incidents for the retry/repair loop.

## Health categories

| Category | Meaning |
|----------|---------|
| `all_good` | Live process and real progress, or terminal state. |
| `false_stall` | Liveness reports `progressing` only because of an in-flight LLM call with no real event in >300s. |
| `harness_issue` | Stale lock, orphan subprocess, multiple checkouts. |
| `plan_issue` | Blocked, phase timeout, or explicit `recoverable_via`. |
| `environment_issue` | Repo-scope doctor findings (skill sync, rubric drift, etc.). |
| `dead_or_disappeared` | No live process and no recent real events. |
| `unknown` | Degraded signals or unrecognized state. |

## Allowlist policy

Always allowed (read-only):

- `introspect`
- `trace`
- `doctor`
- `chain status`

Conditionally allowed:

- `auto` — requires `plan_name`, `state`, and `block_details.recoverable_via`.
- `resume` — requires `plan_name` and `is_resumable`.
- `chain start --one --no-git-refresh --no-push` — requires `chain_spec_path` and pending milestones.

Always rejected:

- `git reset`, `git checkout`, `git push`, `git merge`, `git rebase`.
- Worktree or plan-directory deletion.
- Any command not in the allowlist.

## Degraded mode

When repair-agent credentials or model launchers are unavailable, the pipeline
still runs classification and diagnosis. `RepairDecisionStep` emits a
`no_repair_available` verdict instead of failing. The CLI logs this in the
report and does not crash.

If the installed `megaplan`/`arnold` executable is missing or shadowed, the
scanner and classifier continue to work because they use direct filesystem and
process access. Only the repair-runner path records `command_unavailable`.
