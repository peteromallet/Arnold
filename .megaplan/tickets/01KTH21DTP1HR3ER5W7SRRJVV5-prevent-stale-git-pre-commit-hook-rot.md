---
id: 01KTH21DTP1HR3ER5W7SRRJVV5
title: Prevent stale git pre-commit hook rot
status: open
source: human
tags:
- bug
- reliability
- hooks
- setup
- dx
codebase_id: null
created_at: '2026-06-07T12:48:33.622270+00:00'
last_edited_at: '2026-06-07T12:48:33.622270+00:00'
epics: []
---

Problem
`megaplan setup --install-hooks` installs the canonical pre-commit hook as a one-time copy. Existing checkouts can silently keep running obsolete hook logic after the canonical hook changes. Observed locally: an old hook runs obsolete composed-skill regeneration and stages stale paths, requiring `--no-verify` as a workaround.

Acceptance criteria
- Installed pre-commit hooks self-check against the canonical template and fail with a clear reinstall command when stale.
- Add an auto-sync or warning path similar to installed skill sync so normal CLI use detects stale hooks.
- Avoid hardcoded generated-file `git add` paths in the hook; either resolve them dynamically or let the regen command report touched paths.
- Extend hook/setup tests to cover stale hook detection and refresh behavior.
- Document the refresh behavior and the immediate local remediation command.

Suggested touchpoints
- `arnold/pipelines/megaplan/data/pre-commit-hook.sh`
- `arnold/pipelines/megaplan/cli/__init__.py`
- `arnold/pipelines/megaplan/cli/setup.py`
- `arnold/pipelines/megaplan/cli/skills.py`
- `tests/test_prep_no_shadow_skills.py`

