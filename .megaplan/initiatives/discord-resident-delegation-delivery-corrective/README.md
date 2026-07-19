# Discord Resident Delegation Delivery Corrective

Correct the end-to-end Discord → resident → delegated-agent → terminal-reply lifecycle so every inbound message has immutable provenance, durable custody, idempotent execution, and recoverable delivery through one authoritative ledger.

## Current delivery-status truth

The resident now treats `internal_contributor` only as an aggregation role.
Work completion, result delivery, and whole-request/aggregation delivery are
separate authoritative dimensions. Independently meaningful execution results
retain truthful bounded delivery while one synthesis owner remains able to
issue a later combined conclusion; analytical fragments may remain silent.
Current queue predecessor state is rebuilt from durable manifests, and hot
context exposes actionable deterministic fan-in warnings rather than trusting
stale embedded snapshots.

Design, migration behavior, regression fixture, and verification custody are
indexed in
[`decisions/internal-contributor-delivery-status-hot-context-20260717.md`](decisions/internal-contributor-delivery-status-hot-context-20260717.md).

The executable epic contains the existing lifecycle-correctness milestones M1–M6 followed by **M7 — Resident Completion Attachments v1**. M7 is a disabled-by-default, opt-in completion-output slice: agents declare files through the structured result protocol, the resident captures validated project files into immutable custody, and Discord delivery uses deterministic bounded batches with durable retry and receipt evidence. Text-only and non-Discord completion behavior remains compatible.

M7 deliberately provides no malware, secret, or DLP scanning. Project-directory containment is not a security boundary: a full-access delegated agent can copy sensitive material into an eligible project file and exfiltrate it through this feature. Operators must treat enablement as an explicit trust decision.

## Durable resident successor queues

Resident-managed agents can precommit a bounded, success-gated successor behind one predecessor or an ordered fan-in of up to eight. The successor launches only after every distinct predecessor succeeds with a valid result, while preserving their immutable Discord/delegation provenance, authorization boundary, logical aggregation key, and exactly-one synthesis/delivery ownership. The successor prompt receives typed path references to each predecessor manifest, result, and log; artifact contents are never inlined into queue or hot-context state. Any terminal failure or invalid result fails closed, cancellation/supersession propagates, launch retry is bounded, cycles are rejected, and the manifest-bound execution lock plus queue transition lock make restart/concurrent reconciliation idempotent.

- Architecture and evidence: [decisions/durable-resident-subagent-successor-queues.md](decisions/durable-resident-subagent-successor-queues.md)
- Related resident-agent visibility contract: `../agentbox-persistent-machine/briefs/resident-agent-custody-and-hot-context.md`
- Operator surface: legacy `launch_subagent(depends_on_run_id=...)`, fan-in `launch_subagent(depends_on_run_ids=[...])`, or `python -P -m arnold_pipelines.megaplan resident queue-subagent-successor --after-run-id ...|--after-run-ids ...`; inspect with `resident inspect-subagent-queue`.
