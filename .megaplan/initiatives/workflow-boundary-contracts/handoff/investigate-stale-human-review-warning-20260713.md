# Task: establish the exact identity and chronology of the WBC human-review warning

Investigate the Discord warning titled `Megaplan needs human review - workflow-boundary-contracts-corrective-20260710` and determine, with timestamped evidence, whether it refers to the currently running Workflow Boundary Contracts corrective epic, an earlier attempt, or a stale projection of the same run.

Required analysis:

1. Correlate these identities and explain their roles:
   - cloud/session ID `workflow-boundary-contracts-corrective-20260710`
   - initiative/spec `workflow-boundary-contracts`
   - current plan `c1-contract-reality-20260711-1433`
   - separate prerequisite Run Authority epic (3 milestones)
2. Reconstruct the chronology of the manual-review halt, warning creation/delivery, repair request, stale-state clearing, runner/reviewer restart, and current live state. Use authoritative event/state timestamps and resident message/outbox evidence where available.
3. Determine why a needs-human warning could coexist with or arrive after an automatically resumed live review. Distinguish durable incident evidence, mutable projections, delivery lag, and current authority.
4. Apply the superfixer chain-of-custody test: identify the first layer that misclassified or failed to supersede the condition and the next layer that failed to catch stale output before user delivery.
5. Recommend a structural correction, including incident identity/versioning, authority cursors, pre-delivery revalidation, alert supersession/clearing, typed HUMAN_ACTION_REQUIRED versus UNKNOWN/REPAIRING/RUNNING, and consistent user-facing naming.

Constraints:

- Read-only investigation. Do not mutate chain state, restart services, resume work, or edit implementation code.
- Do not run arbitrary remote shell commands. Use local canonical state, constrained status/observation surfaces, and stored resident evidence.
- Treat the canonical watchdog snapshot and current live process/heartbeat evidence as authoritative for current status, but identify contradictions explicitly.
- Return a concise, evidence-backed final summary suitable for automatic reply to the exact originating Discord message.
