---
id: 01KYV57FAPY2H0ZRQMM8MJ29EM
title: Preserve opaque pytest node IDs in M11 validation accounting
status: open
source: human
tags:
- bug
- release-blocker
- validation
- evidence-accounting
- m11
codebase_id: null
created_at: '2026-07-31T03:59:29.110861+00:00'
last_edited_at: '2026-07-31T05:32:19+00:00'
resolution_note: null
epics:
- epic_id: custody-control-plane
  resolves_on_complete: false
  kind: associated
  provenance: null
  linked_at: 2026-07-31 03:59:37.244460+00:00
---

## Observed failure

The frozen M11 full-suite collector silently omitted 208 legitimate
parametrized pytest node IDs containing spaces. On consolidation commit
`5642cdd1ac`, pytest collected 17,605 nodes, while the old parser retained only
17,397. Collection discarded every line with whitespace and execution parsing
assumed node IDs were whitespace-free. This invalidated exact
collect-versus-execute equality and the downstream no-gap aggregate.

## Resolution and acceptance

Treat pytest node IDs as opaque strings: preserve the complete collect-only
line and parse the execution status after the complete node ID. Reject
duplicate collected IDs and duplicate terminal outcomes rather than collapsing
them through sets or dictionaries.

- Parametrized node IDs containing spaces, punctuation, `::`, and status words
  such as `PASSED` survive collection and execution byte-for-byte.
- Collection and executed inventories are exactly equal.
- Every collected node occurs exactly once; duplicates fail closed.
- Existing immutable receipt hashes and no-gap/no-overlap aggregation remain
  unchanged.
- The focused validation runner and no-debt receipt suites pass.

## Reopened release-discovery residual

The exact `1a10886218` no-debt discovery run found a second opaque-node
accounting defect after the original fix. Pytest renders inherited tests as
`<nodeid> <- <definition-source.py> PASSED`. The frozen inventory contains
only `<nodeid>`, while the terminal parser treated the provenance suffix as
part of the node ID. Shard 004 therefore ran 852 passing tests but admitted
only 810 outcomes; 42 inherited file/PostgreSQL conformance cases were
reported as missing.

The corrective implementation must:

- recover inherited-test provenance only when the left side exactly matches a
  frozen node ID and the right side is a pytest Python source locator;
- preserve literal arrows, spaces, punctuation, and status words inside opaque
  node IDs;
- retain duplicate, ambiguous, unexpected, overlap, and gap fail-closed
  behavior; and
- remain open until the exact final release revision reruns the complete frozen
  inventory with zero missing, duplicate, skipped, xfail/xpass, or debt.

Discovery evidence is preserved at
`Arnold-validation-checkpoints/1a10886218-full-no-debt-20260731/`, including
`full-suite-004-defect.json` and the immutable shard custody/terminal receipts.
