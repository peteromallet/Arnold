---
id: 01KS5CJXVWG4Z9PFG5EXR3Y8FP
title: Make non-git project-dir snapshot warnings concise and actionable
status: open
source: human
tags:
- bug
- execute
- observability
- git
codebase_id: null
created_at: '2026-05-21T13:46:17.853026+00:00'
last_edited_at: '2026-05-21T13:46:17.853026+00:00'
epics: []
---

During the Sisypy `sisypy-undetermined-recurring-run-semantics` run on 2026-05-21, the project directory was intentionally nested and untracked inside a larger workspace:

`/Users/peteromalley/Documents/reigh-workspace/sisypy`

Megaplan repeatedly emitted advisory messages such as:

```text
Project directory is not a git repository.
Advisory quality: skipped quality checks because post-batch git snapshot failed: Project directory is not a git repository.
Advisory observation skip before batch 1/1: Project directory is not a git repository.
Advisory observation skip after batch 1/1: Project directory is not a git repository.
Advisory audit skip: Project directory is not a git repository.
```

The warnings were technically correct, but operationally noisy. The right operator action was to ignore them and avoid initializing git inside the nested project. The repeated warnings made it harder to spot the real blocker: missing per-task execute metadata.

Desired behavior:

1. Detect non-git project directories early and classify the run as `snapshot_unavailable` once.
2. Surface one concise warning in status, including what capabilities are degraded: no git snapshot, weaker dirty-state audit, no diff-backed file attribution.
3. Do not repeat the same advisory at every observation/audit boundary.
4. If the project directory is inside a parent git repo, report that separately and avoid implying the operator should run `git init` in the project directory.
5. Keep execution possible for intentionally non-git projects, but make the quality-gate semantics explicit.

Acceptance test idea:

Run execute against a temporary non-git project directory nested inside a git repo. Status should include one stable snapshot capability warning, and repeated observation/audit calls should not duplicate advisory noise.

