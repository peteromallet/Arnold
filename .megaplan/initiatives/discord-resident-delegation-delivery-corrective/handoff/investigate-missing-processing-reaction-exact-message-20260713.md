# Investigate missing processing reaction for exact Discord message

Determine why the waiting/processing emoji is not visibly appearing for the current inbound Discord message, despite the resident acknowledging that it should appear promptly.

Scope:

- Trace the exact inbound message using immutable launch provenance supplied by the resident launcher. Do not manufacture or replace Discord provenance.
- Inspect the deployed/current resident reaction implementation, durable reaction intent/state, Discord provider attempts/receipts, and restart/replay reconciliation.
- Distinguish among: reaction never queued, queued but not attempted, provider attempt failed, successfully added then removed too early, wrong message target, runtime not deployed/restarted, or Discord UI/API behavior.
- Compare source checkout behavior with the actually running/deployed resident runtime.
- Reproduce safely with focused tests or read-only evidence where possible. Do not restart the resident, interrupt chains, or use arbitrary remote shell commands.
- If the cause is safely fixable locally, implement and test the fix. Preserve unrelated dirty work.
- Report a concise verified outcome, evidence, any changes/tests, whether the fix is live, and any required deployment/restart step.

This is a root-cause task, difficulty D8, and its terminal summary must reply to the originating Discord message through resident-managed delivery.
