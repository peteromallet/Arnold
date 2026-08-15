# Reinitiated chain — m1 gate PROCEED (2026-08-13)

## Outcome
The megaplan-maintenance chain was reinitiated on the fixed engine and is
now driving milestone m1 normally through plan -> critique -> gate.

- Plan: m1-containment-and-truthful-20260813-1656
- Gate: PROCEED (gate.json), rationale cites feature_flags.py:280-298 etc.
- Chain record: execution_binding present, engine fixer lineage dfa83761a6
- No latest_failure on the new plan (previous identity-less/adoption stalls gone)

## Fixer fixes that unblocked it (all on fixer/megaplan-maintenance-20260813)
1. T-0640: aligned repair queue root (ARNOLD_REPAIR_QUEUE_ROOT else marker-adjacent)
2. D2: owner-adoption authorized launch -> exact-occurrence consumer (join-claim)
3. Join-claim consumer delegate_owner_adopted_occurrence (F01 gap closed)
4. Provenance .pth/editable relaxation for T-0301 worktree-first
5. Inverted reconcile land path (git_ops.py source-lineage reachability)
6. Watchdog bootstrap resolves manifest-bound runtime (not /workspace/arnold)
7. execution_binding: worktree-first runtime launch-ready without pip editable
8. Runtime launch seed: auto-build + export at every chain start
9. Supervisor wrapper isolation (env -u PYTHONPATH) + re-prepared clean source
10. Seed chain-binding validation compares runtime identity only
11. Session marker resolution for direct chain start

## Engine lineage
- Branch: fixer/megaplan-maintenance-20260813 @ dfa83761a6 (deployed to candidate)
- Manifest expected_head dfa83761a6, runtime_root arnold-4a830c6ac9a0, gen 6
- Supervisor runtime re-prepared self-contained (probe ready true)

## Evidence
- gate.json recommendation PROCEED
- plan state gated, 240+ events, plan_v1.md
- watchdog reports 20260813T17*.json (fresh sweeps, chain not stalled)
