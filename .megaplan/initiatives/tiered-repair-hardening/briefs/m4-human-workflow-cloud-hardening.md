---
superseded_by: custody-control-plane
---

# M4 - Human Workflow And Cloud Hardening

## Objective

Make human escalation answerable, resumable, authorized, and cloud-operable. This sprint turns escalation from "we sent a DM or wrote a marker" into an audited workflow with current-target matching, allowed responses, delivery state, supersession, and resume handling.

## Files And Areas To Change

- `arnold_pipelines/megaplan/cloud/human_blockers.py` or equivalent
  - Normalize unresolved user actions, manual review with human origin, `awaiting_human_verify`, mechanical gates, satisfied/waived/accepted-blocked resolutions.
- `arnold_pipelines/megaplan/cloud/repair_contract.py`
  - Finalize escalation ledger entries and pointer schema.
- `arnold_pipelines/megaplan/discord_dm.py`
  - Ensure payload rendering is redaction-gated.
  - Persist delivery status/message/channel evidence without leaking tokens.
- `arnold_pipelines/megaplan/resident/auth.py`
  - Tie escalation replies to allowed user/channel and high-impact action confirmation where state mutation/resume occurs.
- `arnold_pipelines/megaplan/resident/discord.py`
  - Route replies by explicit `escalation_id`, current-target match, and resume handler.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-watchdog`
  - Treat Discord delivery failure as repair-system/config failure, not proof the human was notified.
- `arnold_pipelines/megaplan/cloud/wrappers/arnold-repair-loop`
  - Use human-blocker classifier and escalation ledger consistently.
- Docs/runbooks:
  - cloud preflight and rollback;
  - safe test escalation;
  - resolving/superseding pointers while preserving ledger history.
- Tests:
  - `tests/arnold_pipelines/megaplan/test_discord_dm.py`
  - `tests/resident/test_discord_outbound.py`
  - wrapper tests for manual review / awaiting human / Discord delivery.

## Verifiable Completion Criterion

- Escalation ledger has opened, delivered/unavailable, answered, superseded, timed out, and resume-attempted records.
- Mutable needs-human pointer can be cleared or superseded without deleting ledger history.
- Unauthorized Discord answer is ignored and audited.
- Stale/superseded answer cannot resume a different current target.
- Answer must include or map to escalation id and resume handler.
- Cloud runbook includes rollback of wrappers/units/flags, old sidecar compatibility checks, and safe non-secret inspection commands.
- Per-sprint cloud smoke evidence is recorded or the sprint documents exactly why live cloud smoke was unavailable.

## Guardrails

- Do not enable autonomous audit source patches yet.
- Do not make free-text Discord replies mutate state without explicit authorization and current-target matching.
- Do not print secrets while inspecting Discord or cloud status.
