# Elegant Cloud Status and Resident Reporting Plan

## Problem

The Discord resident, watchdog notifications, and local operator CLI can currently answer the same question from different evidence paths. That is why "Are the projects still running?" and "How's it going now?" produced different answers.

The specific failure was not just a bad config value. It exposed a design issue:

- The laptop CLI can run `megaplan cloud status --all` by SSHing into the Hetzner box.
- The Discord resident runs inside the Hetzner container, but was configured with a stale `MEGAPLAN_RESIDENT_CLOUD_YAML`.
- From inside the container, `cloud status --all` may try to SSH back to its own host, which requires an SSH identity the container should not need.
- When that path fails, the resident falls back to local `.megaplan` plan/chain state, which is useful but incomplete for shared-runner status.
- Watchdog already writes runner truth to `/workspace/.megaplan/cloud-sessions/` and `/workspace/watchdog-report.json`, but the resident does not treat that as the canonical broad-status source.

This is too many sources of truth for one operational question.

## North Star

There should be one canonical "what is running?" status document for the cloud worker.

Every status consumer should read that same document:

- Discord resident replies.
- Watchdog Discord notifications.
- `megaplan cloud status --all`.
- Human debugging commands.
- Future dashboards or health endpoints.

The resident should never need to SSH back into the host it is already running on to answer a broad status question.

## Desired Shape

Introduce a canonical cloud status snapshot:

```text
/workspace/.megaplan/status/cloud-status.json
```

This file is produced on the cloud box by local observation only. It aggregates:

- Cloud session markers from `/workspace/.megaplan/cloud-sessions/*.json`.
- Chain health files from `/workspace/.megaplan/cloud-sessions/*.chain-health.progress.json`.
- Watchdog verdicts from `/workspace/watchdog-report.json`.
- Process/tmux liveness from the current container namespace.
- Plan state from each session workspace when available.
- Repair-loop state from repair markers and active repair processes.

It emits a small, stable schema designed for human summaries and automated assertions.

## Status Schema

Top-level:

```json
{
  "generated_at": "2026-07-04T22:13:15Z",
  "source": "cloud-local-observer",
  "summary": {
    "running": 2,
    "blocked": 1,
    "repairing": 1,
    "complete": 18,
    "attention": 1
  },
  "sessions": []
}
```

Each session:

```json
{
  "session": "native-platform-followup",
  "display_name": "native-platform-followup",
  "workspace": "/workspace/native-platform-followup/Arnold",
  "spec": "/workspace/native-platform-followup/Arnold/.megaplan/initiatives/native-platform-followup/chain.yaml",
  "status": "running",
  "should_run": true,
  "tmux": "alive",
  "process": "alive",
  "watchdog": "alive",
  "repairing": false,
  "current_plan": "m4-durable-substrate-and-20260704-2124",
  "completed_count": 3,
  "milestone_count": 8,
  "latest_activity": "2026-07-04T22:13:09Z",
  "operator_next": "observe progress",
  "evidence": {
    "marker": "/workspace/.megaplan/cloud-sessions/native-platform-followup.json",
    "chain_health": "/workspace/.megaplan/cloud-sessions/native-platform-followup.chain-health.progress.json",
    "watchdog_report": "/workspace/watchdog-report.json"
  }
}
```

Status values should be deliberately boring:

- `running`: expected to be working and has live process or active recent progress.
- `repairing`: blocked/stalled and an automated repair is active or dispatched.
- `blocked`: should not be running until a blocker is resolved.
- `complete`: no runner expected.
- `attention`: inconsistent evidence, stale heartbeat, missing workspace, missing spec, or unknown policy.

## Consumer Rules

For broad questions such as "how's it going?", "what is active?", "is it cooking?", or "why did it not reply?", the resident must use this precedence:

1. Read `/workspace/.megaplan/status/cloud-status.json` if present and fresh.
2. If stale or missing, run the local cloud-status snapshot builder inside the container.
3. If snapshot building fails, explain the status system failure explicitly and include only clearly labeled fallback evidence.

The resident should not answer broad status questions from arbitrary `.megaplan/plans` or `.megaplan/chains` searches unless it labels that as degraded mode.

## Implementation Plan

### 1. Extract a pure status aggregator

Add a module, likely:

```text
arnold_pipelines/megaplan/cloud/status_snapshot.py
```

Responsibilities:

- Read marker directory, watchdog report, chain-health files, plan state, tmux/process state.
- Normalize them into the schema above.
- Never require SSH.
- Work from inside the cloud container.
- Be unit-testable with fixture directories.

This module should not know about Discord, resident conversations, or CLI rendering.

### 2. Make watchdog write the snapshot

After every watchdog sweep, write:

```text
/workspace/.megaplan/status/cloud-status.json
/workspace/.megaplan/status/cloud-status.previous.json
```

Write atomically through a temporary file and rename.

This makes watchdog the regular producer of the current truth. The snapshot builder can still be run on demand, but the common path is read-only.

### 3. Make `cloud status --all` use the snapshot when local

When `megaplan cloud status --all` is running inside the cloud container, it should detect:

```text
MEGAPLAN_TRUSTED_CONTAINER=1
/workspace/.megaplan/cloud-sessions exists
```

Then it should read or rebuild the local snapshot instead of invoking the SSH provider against `root@159.69.51.216`.

When running from a laptop, it can still SSH to the box and ask the container for the same snapshot. The laptop should not independently reconstruct status from a different algorithm.

### 4. Make the resident consume the snapshot

Resident hot context should include:

```json
{
  "cloud_status_snapshot": {},
  "plan_activity_summary": {
    "active_working": [],
    "should_be_working_but_needs_attention": [],
    "recently_completed": []
  }
}
```

`plan_activity_summary` should be derived from the canonical snapshot first. Local plan/chain scans become supplemental detail only.

Prompt rule:

> For broad status questions, answer from `cloud_status_snapshot`. If the snapshot is unavailable or stale, say so before using fallback evidence.

### 5. Delete stale YAML dependency for broad status

`MEGAPLAN_RESIDENT_CLOUD_YAML` can remain useful for targeted cloud operations, but it should not be required for broad status.

Broad status should use:

```text
MEGAPLAN_STATUS_SNAPSHOT=/workspace/.megaplan/status/cloud-status.json
```

If that env var is absent, default to the same path.

This removes the failure mode where the resident points at one initiative YAML and misses all shared-runner sessions.

### 6. Unify outbound notifications and replies

Watchdog notifications and resident replies should call the same formatter:

```text
arnold_pipelines/megaplan/cloud/status_format.py
```

Formatters:

- `format_cloud_status_short(snapshot)` for Discord.
- `format_cloud_status_detailed(snapshot)` for CLI.
- `format_attention_only(snapshot)` for watchdog alerts.

This prevents one path saying "2 running" while another says "only native completion is done".

### 7. Make degraded mode explicit

If the snapshot cannot be produced, the user-facing answer should say:

```text
Cloud status is degraded: <reason>. I can see <fallback evidence>, but this is not the canonical shared-runner view.
```

Never silently answer from partial plan files as though it is full cloud status.

## Tests

Add fixture-driven tests for:

- Two running sessions plus one repairing session produces `summary.running == 2`, `summary.repairing == 1`.
- Completed sessions are not counted as active even if old plan state says `finalized`.
- Missing workspace becomes `attention`, not `complete`.
- Repair marker plus blocked watchdog item becomes `repairing`.
- Resident broad-status context prefers snapshot over local `.chains`.
- CLI inside trusted container does not try SSH.
- CLI from laptop fetches the same snapshot from the container.
- Discord formatter stays under 2000 characters or chunks predictably.

## Migration Steps

1. Add snapshot module and tests.
2. Wire watchdog to write the snapshot, without changing existing status behavior.
3. Teach `cloud status --all` to read the snapshot when running locally in the cloud container.
4. Teach resident hot context to read the snapshot.
5. Switch broad-status prompt instructions to require snapshot-first answers.
6. Point Discord resident env at `MEGAPLAN_STATUS_SNAPSHOT`, not an initiative-specific cloud YAML.
7. Remove or demote old fallback paths once tests cover the new snapshot contract.

## Acceptance Criteria

The cleanup is done when:

- Asking the Discord bot "How's it going now?" reports the same running/blocked/complete counts as `megaplan cloud status --all`.
- The resident can answer broad status from inside the container with no SSH key.
- A stale or missing initiative `cloud.yaml` cannot change broad status answers.
- Watchdog notifications and resident replies use the same session classifications.
- The status answer cites its evidence source and timestamp.
- There is one obvious place to debug status truth: `/workspace/.megaplan/status/cloud-status.json`.

## Non-Goals

- Do not redesign chain execution.
- Do not merge the resident and watchdog processes.
- Do not require copying laptop SSH keys into the cloud container.
- Do not make Discord the source of operational truth.

## Design Principle

The cloud box should describe itself from inside itself. Everything else should read that description.

