# Luna explorer 7 — legacy-session migration and takeover policy

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Return under 1200 words.

Read `sol-p2-framing-result-20260804.md`, `sol-final-plan-20260804.md`, and
`luna-synthesis-20260804.md`. The current cloud estate contains old sessions,
stale markers, partial leases, legacy phase results, multiple worktrees, and
in-flight telemetry that cannot all be trusted.

Audit session/plan state schemas, chain manifests, markers/leases, recovery
receipts, source/runtime metadata, and any migration/takeover helpers. Define
which legacy sessions are provably adoptable, which can be quarantined and
restarted without losing history, and which are permanently ambiguous.

Recommend a dry-run classification and fenced handoff protocol that never
rewrites history or infers ownership from timestamps/tmux/markers alone.
Provide acceptance tests for complete identity migration, stale-but-dead
owner, expired-but-live owner, conflicting source/runtime, missing occurrence,
and ambiguous ownership. State the smallest human gates and what must remain a
follow-up rather than be automated in P2.
