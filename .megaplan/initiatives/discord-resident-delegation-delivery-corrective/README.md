# Discord Resident Delegation Delivery Corrective

Correct the end-to-end Discord → resident → delegated-agent → terminal-reply lifecycle so every inbound message has immutable provenance, durable custody, idempotent execution, and recoverable delivery through one authoritative ledger.

The executable epic contains the existing lifecycle-correctness milestones M1–M6 followed by **M7 — Resident Completion Attachments v1**. M7 is a disabled-by-default, opt-in completion-output slice: agents declare files through the structured result protocol, the resident captures validated project files into immutable custody, and Discord delivery uses deterministic bounded batches with durable retry and receipt evidence. Text-only and non-Discord completion behavior remains compatible.

M7 deliberately provides no malware, secret, or DLP scanning. Project-directory containment is not a security boundary: a full-access delegated agent can copy sensitive material into an eligible project file and exfiltrate it through this feature. Operators must treat enablement as an explicit trust decision.

## Durable resident successor queues

Resident-managed agents can now precommit a bounded, success-gated successor that inherits the predecessor's immutable Discord/delegation provenance, authorization boundary, logical aggregation key, and sole synthesis/delivery ownership. The successor prompt receives typed path references to the predecessor manifest, result, and log; artifact contents are never inlined into queue or hot-context state. Terminal failure or invalid result fails closed, cancellation/supersession propagates, launch retry is bounded, cycles are rejected, and the manifest-bound execution lock plus queue transition lock make restart/concurrent reconciliation idempotent.

- Architecture and evidence: [decisions/durable-resident-subagent-successor-queues.md](decisions/durable-resident-subagent-successor-queues.md)
- Related resident-agent visibility contract: `../agentbox-persistent-machine/briefs/resident-agent-custody-and-hot-context.md`
- Operator surface: `launch_subagent(depends_on_run_id=...)`, or `python -P -m arnold_pipelines.megaplan resident queue-subagent-successor ...`; inspect with `resident inspect-subagent-queue`.
