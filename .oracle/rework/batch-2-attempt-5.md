# Batch 2 attempt 5 — Sol oracle verdict

Verdict: **REWORK REQUIRED**. Implement the minimum complete fix at the four
remaining R3 roots, preserving the frozen tasklist, North Star, status, and
existing Batch-2 contracts.

- **R3-NATIVE-001** — native admission must use the authoritative constructor
  capability/catalog seam, construct valid routes once, reject unknown/stale/
  mismatched proofs before any reservation or work, and recompute proof
  identity fields.
- **R3-TERM-002** — carry typed terminal outcomes through the native, OMP, and
  managed doors while retaining legacy return shapes; preserve and validate
  receipt/context/identity/timing/fingerprint fields, and make terminal
  append/link failure unresolved with exactly one terminal attempt.
- **R3-LIFE-003** — enforce only `not_started -> entered -> accepted -> closed`,
  allow byte-identical replay, validate complete reopen history, and derive
  state from the ordered terminal marker.
- **R3-AUTH-004** — inspect every relevant call in configured physical-door
  files, including nested helpers and multiline/reversed False and bool forms,
  while retaining existing authority checks.

Scope is deliberately limited to these roots and focused regressions; no
second managed WBC authority or Batch-3/provider/scheduler/journal redesign.
