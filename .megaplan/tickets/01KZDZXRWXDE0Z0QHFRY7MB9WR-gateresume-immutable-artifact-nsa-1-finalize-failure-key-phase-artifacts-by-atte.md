---
id: 01KZDZXRWXDE0Z0QHFRY7MB9WR
title: 'Gate/resume immutable-artifact + NSA-1 finalize failure: key phase artifacts
  by attempt/epoch'
status: open
source: human
tags:
- megaplan-engine
- gate
- resume
- finalize
- north-star
- immutable-artifact
- recovery
codebase_id: null
created_at: '2026-08-07T11:32:22.557569+00:00'
last_edited_at: '2026-08-07T11:32:22.557569+00:00'
epics: []
---

# Gate/resume immutable-artifact + NSA-1 finalize failure (megaplan engine)

## Symptom
Plan cl2-wbc-backed-ledger-20260805-2140 (critique-ledger r7) reached `gated` (gate PROCEED) but finalize blocked repeatedly:
1. `north_star_finalize_unresolved_blocking` — carried blocking North Star action NSA-1 (`add_human_halt`) unresolved with `action_type_mismatch`, because no revise metadata recorded `north_star_actions_addressed` (we reached finalize without a revise pass).
2. `RuntimeError: immutable artifact identity already contains different bytes: gate_v5.json` — the tiebreaker wrote a resolved gate_v5.json, then the follow-up gate run saw different bytes → `deterministic_phase_failure` → blocked.
3. Over-archiving via `invalidate_replan_derived_artifacts(include_critique_epoch=True)` removed `critique_custody_v5.json` + the producer/raw/manifest family that gate resume REQUIRES (`critique_custody_receipt_invalid`).

## Root cause
The engine assigns multiple semantically different phase attempts the same immutable identity (gate_v5.json): tiebreaker, repaired rerun, provider retry all write the same versioned artifact. The create-once check correctly rejects the second write. The finalize NSA check requires a revise-metadata acknowledgment that doesn't exist when gate-PROCEED is reached without revise.

## Fixes already applied (runtime branch fixer/critique-epoch-invalidation-20260806)
- `f5a38311d` gate-PROCEED satisfies carried blocking North Star actions (gate independently adjudicated the halting condition)
- `202903987` phase-scoped invalidation — gate_retry archives only gate family, preserves critique custody that validate_gate_input_custody requires
- `dda8fd9cd` gate baseline presence via git plumbing
- Gate now routes through GLM-5.2 (profile) instead of deepseek-v4-pro which timed out

## Deeper fix (GPT-5.6 recommended, NOT yet implemented)
1. **Gate artifacts keyed by gate attempt/epoch, not plan iteration** (highest priority)
2. Explicit critique-epoch binding in state (gate resolves the exact bound critique epoch, not `critique_custody_v{iteration}.json`)
3. `resume` should reject `repair_phase_contract` cursors and route to `override recover-blocked` (workflow.py:732)
4. Explicit `restore-invalidation --manifest` archive reversal tooling

## Fits
megaplan-chain-milestone-gates/s1 (attempt/epoch-keyed gates) + critique-ledger r7 cl2-ledger-replay (direct victim).

## Evidence
- Plan history: gate error 10:14:15Z, gate success 11:03:05Z, finalize error 11:11:16Z, finalize success 11:23:05Z
- GPT-5.6 proper-fix analysis (gate_failure_evidence.md)

