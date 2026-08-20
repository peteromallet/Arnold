---
type: anchor
anchor_type: north_star
slug: critique-ledger-vj24-migration-20260805
title: 'North Star: Critique Ledger Vj24 Migration 20260805'
created_at: '2026-08-05T11:05:09.602945+00:00'
---

# North Star: Critique Ledger Vj24 Migration 20260805

## End State

The stalled r5/VJ24 occurrence remains immutable and quarantined. A single,
idempotent migration operation can validate its retained evidence, allocate a
fresh child run with new Run Authority, Custody and WBC identities, append a
content-addressed parent-to-child receipt, and advance the cursor by CAS. The
child can then enter the ordinary chain/operator path. No same-occurrence
resume, marker edit, or projection-created authority is possible.

## Non-Negotiables

- Parent `cl2-wbc-backed-ledger-20260803-1357` / VJ24 is
  `QUARANTINED_IMMUTABLE`; `same_occurrence_resume` is false.
- Run Authority owns grant/fence/CAS; Custody owns occurrence/lease/epoch; WBC
  owns attempt/effect evidence. No fourth ledger or caller-writable authority.
- A migration is accepted only when every cross-owner identity and the
  finalized `task_contract_hash` agree; missing or conflicting evidence fails
  closed without dispatch. The broader
  `selector_task_output_contract.v1` shared-consumer schema is a follow-up F2
  obligation, not a reason to invent a second prelaunch authority.
- The operation is idempotent and replay-safe: one parent, one child, one
  receipt, one integer parent Run Authority journal CAS advance, and no
  provider effect during preparation.

## Explicit Non-Goals

Do not resume r5 in place, edit its state/marker/finalize artifacts, launch a
fresh duplicate Critique chain, rebuild the whole Custody Control Plane, or
undertake the broad historical T1.5/T1.7/T1.10 inventory.

## Allowed Temporary Bridges

The sprint may use deterministic fixture stores and a dry-run operator command
to prove the migration contract. These fixtures must be clearly typed as
non-production evidence and cannot satisfy the r5 launch gate by themselves.

## Drift Signals

Stop if a task proposes same-session resume, `--fresh`, direct JSON/state edits,
new authority storage, a lease without a real owner API, or a child receipt
without a real Run Authority/Custody/WBC join. Also stop if the selector fix is
implemented only in execute (rather than normalized at the shared
finalize/execute seam), if an expected cursor is compared to itself, or if a
source-cursor hash is coerced into an integer journal cursor. The first-child
cutline uses the existing `task_contract_hash`; cross-consumer selector schema
adoption is owned by follow-up F2.
