# Luna explorer 1 — entry-point and mutation boundary

You are GPT-5.6 Luna, read-only, high reasoning. Do not edit files, launch
cloud commands, or use collaboration tools. Inspect only the bounded surfaces
below and return a concise evidence report (under 1200 words).

Context: Sol's P2 north star is a versioned ExecutionAttempt ledger plus one
admission/commit protocol. The current critique run exposed VJ8/VJ9 validation
contract mismatches, a missing hot-env bootstrap on resume, stale projections,
and false liveness. Read `evidence/critique-ledger-recovery/sol-p2-framing-result-20260804.md`
and `sol-final-plan-20260804.md` first.

Audit surfaces: `arnold_pipelines/megaplan/cloud/cli.py`,
`arnold_pipelines/megaplan/agentbox_adapter.py`, chain start/spec/driver code,
`arnold_pipelines/megaplan/supervisor/`, `cloud/`, `watchdog/`,
`blocker_recovery.py`, `handlers/override.py`, and status/projection writers.

Map every path that can launch a worker or mutate executing/blocked/terminal
state, lease/marker state, or recovery receipts. Identify bypasses around a
single admission authority, swallowed exceptions, and writes that do not carry
an attempt/generation identity. Cite exact files/functions and propose the
smallest P2 boundary plus one conformance test that proves no entry point can
publish `executing` without admission.
