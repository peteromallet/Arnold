---
id: 01KRNKTKF8S857SZNMYH5DQ20D
title: Make cloud chain supervision first-class
status: open
source: human
tags:
- cloud
- chain
- supervision
- reliability
- provider-fallback
codebase_id: null
created_at: '2026-05-15T10:44:58.472245+00:00'
last_edited_at: '2026-05-15T10:44:58.472245+00:00'
epics: []
---

During the Astrid git-backed-packs chain, the cloud run needed a project-local shell supervisor to keep work moving. That worked operationally, but it is the wrong abstraction for Megaplan long term.

## What happened

- The user wanted a long Megaplan chain to run on cloud, all remaining milestones on one PR, with a push after each sprint.
- The built-in chain flow is milestone/PR oriented, so we wrapped `megaplan chain start --one --no-push --no-git-refresh` in a shell loop that commits/pushes to PR #8 after each completed sprint.
- Sprint 2 exposed a real Astrid issue and was fixed, but review then hit Codex quota. Resume retried the same Codex route and stayed stuck.
- Sprint 3 failed before planning because `plan=codex:medium` hit quota. Recovering required manually editing `state.json` back from `failed` to `initialized`, deleting failure cursors, changing phase routing to direct DeepSeek, and rerunning the phase.
- We added a cloud tmux supervisor that logs immediately/hourly, detects quota-failed states, rewrites phase routing to an approved fallback, restarts `megaplan auto`, and restarts the chain runner when a sprint completes.

## Why this is a Megaplan product gap

The shell supervisor is useful but hacky:

- It edits private state files directly.
- It encodes provider fallback outside Megaplan.
- It cannot distinguish every valid recovery from real product/architecture decisions.
- It relies on tmux/session naming conventions.
- It implements single-PR chain behavior outside the chain engine.
- It gives the user operational confidence, but not a durable or reusable cloud abstraction.

## Desired first-class behavior

Build a native cloud operator/supervisor mode with explicit policy:

1. Early check-in cadence
   - run an immediate post-launch check;
   - run an early check after 10-15 minutes;
   - run hourly checks after that;
   - write structured status snapshots, not just raw logs.

2. Safe auto-advance
   - continue states with unambiguous valid next steps;
   - restart a dead runner when no active phase process exists;
   - resume `megaplan auto` for active plans that are not blocked;
   - continue a chain after a completed milestone.

3. Provider fallback and quota recovery
   - detect provider quota/rate-limit/auth failures as infrastructure failures;
   - allow retrying the failed phase with an approved fallback provider without hand-editing state;
   - preserve an audit trail showing original provider, fallback provider, reason, and affected phase;
   - never silently change model class for product decisions unless the chain/profile explicitly allows it.

4. Single-PR chain mode
   - support `chain start` options for one long branch/PR across multiple milestones;
   - commit and push after each completed milestone;
   - update the same PR body/status summary;
   - avoid automatic base-branch refresh that stomps an active long-running branch unless requested.

5. Decision boundary
   - auto-handle infrastructure: dropped SSH/WebSocket, stale tmux/process, provider quota, dead runner, known retryable phase failures;
   - do not auto-resolve merge conflicts, failing tests that require code judgment, destructive cleanup, or scope/architecture ambiguities;
   - surface those as blocked states with a concise reason and suggested next action.

6. Multiple tasks on one cloud worker
   - document or implement a helper for sibling checkouts (`/workspace/repo-task-name`), separate branches, separate tmux/session names, and separate logs;
   - prevent accidental launch of two mutating plans in the same checkout unless explicitly forced.

## Acceptance criteria

- A cloud chain can be launched in supervised mode and gets immediate, early, and hourly status snapshots.
- A quota failure in a phase can be retried with an approved fallback provider through a supported command/API, without state-file surgery.
- A chain can run multiple milestones on one PR and push after each milestone.
- The supervisor records what it did and why in machine-readable artifacts.
- The supervisor refuses to make product/architecture decisions outside declared policy.
- Documentation explains the recommended operator loop and when to use isolated sibling checkouts.

## Related observation

I added a temporary `Cloud Operator Loop` section to the local Megaplan skill docs so agents know the current operational pattern. That should become product documentation once the native feature exists.

