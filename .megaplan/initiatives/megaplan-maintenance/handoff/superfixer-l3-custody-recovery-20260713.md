# Superfixer/L3 custody recovery operator

## Outcome

Diagnose and correct the end-to-end fixer custody failure affecting the canonical Workflow Boundary Contracts session `workflow-boundary-contracts-corrective-20260710`, then safely re-trigger the original session and prove genuine forward progress. Also correct the systemic L3-to-repair handoff so future six-hour auditor findings can cause an authorized, idempotent resident-managed repair agent to be launched without turning the auditor itself into an unconstrained mutator.

## Governing workflows

Read and follow the `superfixer-debug` skill first and the `megaplan-cloud` skill for on-box cloud operation. Apply the TRACKED / FIXED / INTENT / CONTEXT audit to watchdog, L1 repair loop, L2 meta-repair, and L3 six-hour auditor. Find both the first fixer that failed and the layer above it that failed to detect or act on that failure.

Do not use arbitrary remote shell commands, raw SSH, `pkill`, `killall`, cgroup-wide stops, or tmux cleanup. This task is running on the agentbox; use constrained Megaplan/on-box mechanisms and canonical managed-agent lifecycle controls. Do not weaken guards or manually advance state to hide the symptom.

## Known authoritative evidence to verify

- The six-hour auditor detected the C1 incident and repeatedly reported the missing meta-repair path; it is currently designed as report-only.
- Repair request `7473fa422fea89a936d0be64f25468524f0d7d0e1c8632478f5dcfc6ec37860e` was accepted but had no typed failure/blocker identity and received zero claims, attempts, or terminal decisions.
- The WBC runner is stopped with a stale dead review worker, while advisory repair sidecars do not establish liveness.
- Current shared snapshot (2026-07-13T14:39:21Z) reports WBC at 25% overall, C1 execution complete but stuck in review/recovery custody.
- A separate Discord incident displaced a resident restart request with an older automatic agent-completion delivery. Inspect the durable conversation/outbox/turn records and determine whether the same correlation, idempotency, or custody design weakness affects repair-agent launching.

## Required work

1. Inspect all canonical superfixer evidence sources and the exact runtime/wrapper versions actually executing.
2. Establish the causal chain for the accepted-but-unclaimed repair request and for L3 findings that never became executable custody.
3. Preserve L3's audit independence. Implement a typed, durable, authorized handoff from actionable L3 findings into the resident-managed Codex launch lifecycle (or the correct existing repair dispatcher), including stable incident/request identity, claim/lease ownership, idempotency, bounded retries, terminal decisions, and delivery evidence. Do not grant arbitrary direct process-launch authority to report rendering.
4. Fix the first broken fixer and the supervising layer that failed to catch it. Include regression tests for missing blocker identity, accepted-but-unclaimed requests, repeated L3 findings, duplicate suppression, launch failure, restart/recovery, and exact reply/incident correlation.
5. Deploy or refresh only through canonical safe mechanisms. Verify the executing supervisor/repair/auditor runtime uses the corrected code.
6. Re-trigger the original WBC C1 session through its authoritative recovery path. Prove real movement using fresh runner identity, heartbeat/events, repair claim/attempt/terminal records, and plan/chain advancement—not stale projections.
7. Run the retroactive six-hour auditor and prove it recognizes the repaired incident as recovered while still surfacing genuinely unresolved sibling cases.
8. Survey the same failure mode across the fixer stack and resident completion delivery, addressing closely related systemic defects that are necessary for reliable custody. Avoid unrelated cleanup.

## Completion report

Report root cause, changed contracts/code, tests, deployment/runtime identity, the original WBC recovery evidence, remaining genuine human gates, and any unresolved delivery state. Continue autonomously until the repair path and original chain recovery are verified or a genuine approval/credential/product-decision gate is reached.
