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
