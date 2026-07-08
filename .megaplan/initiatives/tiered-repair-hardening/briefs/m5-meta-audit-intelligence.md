---
superseded_by: custody-control-plane
---

# M5 - Meta-Repair And Auditor Intelligence

## Objective

Add the higher-order loop: when ordinary repair fails as a system, meta-repair diagnoses and fixes the repair system, then retriggers ordinary repair and proves it succeeded. The six-hour auditor becomes a root-cause/pattern loop with green checks, cross-references, and bounded repair-system fixes.

## Files And Areas To Change

- `arnold_pipelines/megaplan/cloud/meta_repair.py`
  - Load repair evidence, classify repair-system failure, build redacted Codex/DeepSeek prompt, record meta attempts, enforce 90-minute budget, require ordinary repair retrigger.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-meta-repair-loop`
  - Dispatch Codex with `danger-full-access` only where required, explicitly equipped to launch nested DeepSeek/Hermes subagents for mapping and independent root-cause probes.
  - Keep patch/commit/push behavior behind explicit policy flags.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
  - Trigger meta-repair for repair timeout, persistent recurring retry, state-inspection failure, model/tool launch failure, partial-liveness recurrence, and Discord delivery failure for true human blockers.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-progress-auditor`
  - Read incidents, attempts, meta records, escalations, repair events, watchdog reports, audit reports, persistent findings, tickets, and recent repair-system commits.
  - Write root-cause patterns, related prior incidents, autonomous fix attempts, risky/deferred fixes, and `green_checks`.
  - Keep autonomous fixes bounded to Arnold repair-system bugs with focused tests and no secret exposure.
- Retention/indexing:
  - Maintain repair-data `index.json`.
  - Add retention/cleanup behavior that never deletes unresolved incidents/escalations or latest active-session snapshots.
- Tests:
  - `tests/cloud/test_meta_repair.py`
  - `tests/cloud/test_progress_auditor.py`
  - focused wrapper adapter tests for meta dispatch and audit report fields.

## Feature Flags

- `META_REPAIR_ENABLED` default off until tests and a fixture run pass.
- `AUDIT_AUTOFIX_ENABLED` default off or patch-only until signoff.
- Any commit/push behavior requires an explicit policy gate.

## Verifiable Completion Criterion

- Meta-repair cannot count direct epic hand-fixing as success.
- Meta-repair success requires ordinary repair-loop retrigger with non-partial verification.
- Meta-repair records diagnosis, changed files, tests, retrigger command, and post-retrigger evidence.
- Auditor writes useful green reports when no suspicious plans are found.
- Auditor links repeated incidents to prior repair/audit/watchdog evidence.
- Auditor prompts and reports are redacted and include bounded-fix/no-secrets policy.
- Retention/index cleanup preserves unresolved incidents/escalations and appends cleanup events.

## Guardrails

- Do not enable autonomous commits/pushes without an explicit flag and focused tests.
- Do not let meta-repair bypass the ordinary repair loop to claim success.
- Do not broaden auditor fixes beyond repair-system bugs.
