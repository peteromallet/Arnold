# M9 — Compatibility Expiry Map

Generated: 2026-07-22T22:56 UTC  
Scope: M9 rebuildable projections and liveness — compatibility bridge lifecycle  
Schema: m9.compatibility-expiry-map.v1  
Depends on: T45 (wbc_compat.py), T46 (retention/__init__.py), T47 (cross-tenant gate), T18 (compatibility/__init__.py)

## Purpose

This document maps every M9 compatibility projection to its **reader count**,
**expiry condition**, **deletion gate**, and the corresponding **adoption-matrix
row** (from `research/wbc-boundary-adoption-matrix.md`).  It serves as the
concrete deletion path for M10 — each entry defines when a compatibility
bridge can be safely removed.

SD3 governs:

> Compatibility bridges remain allowed only when explicitly non-authoritative,
> source-versioned, expiry-scoped, and backed by reader-count or zero-reader
> deletion gates.

---

## Compatibility Projection Inventory

### 1. WBC Compatibility Adapters (`compatibility/wbc_compat.py`)

| # | Wrapper ID | Schema In → Out | Reader Count | Expiry Condition | Deletion Gate | Adoption Matrix Row |
|---|---|---|---|---|---|---|
| WC01 | `wbc-compat-active-v1` | `wbc.v0` → `wbc.v1` | 2 (introspect, chain_runner) | 90 days after M10 GA | `reader_count==0` AND `deletion_blocked_until` passed | T40 (WbcAdapter), T41 (introspect cutover) |
| WC02 | `wbc-compat-legacy-gap-pre-wbc` | `none` → `wbc.v1` (gap marker) | 0 (never consumed) | Permanent — represents unbackfillable gap | Cannot be deleted (gap evidence is permanent) | NF01 (pre-WBC plans), T39 §10 |
| WC03 | `wbc-compat-legacy-gap-migration-cutoff` | `wbc.v0` → `wbc.v1` (gap marker) | 0 (never consumed) | Permanent — represents migration boundary | Cannot be deleted (gap evidence is permanent) | NF02 (migration cutoff), T39 §10 |
| WC04 | `wbc-compat-legacy-gap-missing-receipt` | `wbc.v0` → `wbc.v1` (gap marker) | 1 (chain_runner acceptance gate) | When WBC receipt becomes available | `reader_count==0` (gate reads receipt instead) | NF03 (missing receipts), T42 |
| WC05 | `wbc-compat-deprecated` | `wbc.v0` → `wbc.v1` | 0 | Already expired | Ready for deletion (zero readers) | T39 §10.1 |
| WC06 | `wbc-compat-expired` | `wbc.v0` → `wbc.v1` | 0 | Expired at M9+60d | Ready for deletion | T39 §10.2 |

### 2. Compatibility Projection Wrappers (`compatibility/__init__.py`)

| # | Wrapper ID | Schema In → Out | Reader Count | Expiry Condition | Deletion Gate | Adoption Matrix Row |
|---|---|---|---|---|---|---|
| CP01 | `compat-projection-status-v1` | `status.v1` → `status.v2` | 3 (CLI status_view, cloud status_snapshot, resident status_tree) | When all readers use `status.v2` natively | `reader_count==0` | C05, C23, C76 |
| CP02 | `compat-projection-introspect-v1` | `introspect.v1` → `introspect.v2` | 2 (watchdog parity, auditor parity) | When watchdog/auditor use `introspect.v2` natively | `reader_count==0` | C15, C111 |
| CP03 | `compat-projection-work-ledger-v1` | `work_ledger.v1` → `work_ledger.v2` | 2 (observability/introspect, acceptance evidence) | When all ledger consumers use v2 | `reader_count==0` | C20, C123 |
| CP04 | `compat-projection-completion-io-v1` | `completion_io.v1` → `completion_io.v2` | 1 (chain_runner finalization) | When chain_runner uses WBC adapter natively | `reader_count==0` | C111, T42 |
| CP05 | `compat-projection-retention-v1` | `retention.v1` → `retention.v2` | 2 (cloud status_snapshot, resident status_tree) | When retention projections are adapter-backed | `reader_count==0` | C49, C97, T46 |
| CP06 | `compat-projection-unknown-fields-strip` | `m9.v1` (with unknown) → `m9.v0` (stripped) | 1 (legacy CLI consumers) | When legacy CLI consumers are decommissioned | `reader_count==0` | C01-C04 |

### 3. Cross-Tenant / Retention Gates (`retention/__init__.py`)

| # | Wrapper ID | Schema In → Out | Reader Count | Expiry Condition | Deletion Gate | Adoption Matrix Row |
|---|---|---|---|---|---|---|
| RT01 | `retention-cross-tenant-gate` | `tenant.v1` → `negative-gate` | 2 (cloud, resident) | Permanent — security gate | Cannot be deleted (security enforcement) | NF06, T47 |
| RT02 | `retention-history-access-classification` | `history.v1` → `typed-access` | 2 (cloud, resident) | Permanent — audit classification | Cannot be deleted (audit required) | NF07, T47 |
| RT03 | `retention-tombstone-projection` | `tombstone.v1` → `deletion-marker` | 1 (cloud status_snapshot) | When plan is fully purged | `reader_count==0` after purge | NF08, T46 |
| RT04 | `retention-expiry-projection` | `expiry.v1` → `ttl-check` | 2 (cloud, resident scheduler) | When all expired plans are purged | `reader_count==0` after purge | NF09, T46 |

### 4. Completion Summary Adapters (T44)

| # | Wrapper ID | Schema In → Out | Reader Count | Expiry Condition | Deletion Gate | Adoption Matrix Row |
|---|---|---|---|---|---|---|
| CS01 | `compat-completion-classify-resident` | `complete/idle` → `complete/indeterminate/idle` | 2 (resident status_tree, context_tree) | When all completion consumers use indeterminate | `reader_count==0` | C76, C81, T44 |
| CS02 | `compat-completion-classify-cloud` | `complete/idle` → `complete/indeterminate/idle` | 2 (cloud status_snapshot, plan_activity_summary) | When all cloud completion consumers use indeterminate | `reader_count==0` | C23, C49, T44 |

---

## Zero-Reader Deletion Path (M10)

### Deletion Readiness Criteria

A compatibility projection is **ready for deletion** when ALL of:

1. **`reader_count == 0`** — every consumer has migrated to the native M9+ schema.
2. **`deletion_blocked_until_epoch_ms` has passed** — the grace period after deprecation has elapsed.
3. **No active incident bridge references** — the incident ledger contains no unresolved events referencing the wrapper.
4. **Acceptance evidence recorded** — a `compat-wrapper-deleted` acceptance transaction is committed.

### Deletion Sequence (M10)

```
1. Mark wrapper DEPRECATED → 30-day grace period starts
2. Track reader_count via WbcCompatAdapterRegistry / WrapperRegistry
3. When reader_count == 0 AND grace period passed:
   a. Generate deletion evidence (content-addressed snapshot of wrapper state)
   b. Commit acceptance transaction confirming zero-reader state
   c. Mark wrapper DELETED
   d. Remove wrapper from registry
4. Permanent gap markers (WC02, WC03, RT01, RT02) are NEVER deleted
```

### Permanent Evidence (Never Deleted)

| Wrapper ID | Reason |
|---|---|
| WC02 (`pre-wbc`) | Unbackfillable pre-WBC history — gap is evidence |
| WC03 (`migration-cutoff`) | Migration boundary marker — required for audit |
| RT01 (`cross-tenant-gate`) | Security enforcement — cross-tenant gate must persist |
| RT02 (`history-access-classification`) | Audit classification — history access audit trail required |

---

## Reader-to-Wrapper Mapping (for M10 migration planning)

### Consumers → Wrappers

| Consumer | Domain | Wrappers Used | Migration Target (M10) |
|---|---|---|---|
| `cli/status_view.py` | CLI | CP01, CP06 | Native `status.v2` schema |
| `cloud/status_snapshot.py` | Cloud | CP01, CP05, CS02, RT03 | Native M9+ projections |
| `resident/status_tree.py` | Resident | CP01, CP05, CS01 | Native M9+ projections |
| `resident/context_tree.py` | Resident | CS01 | Native indeterminate completions |
| `resident/scheduler.py` | Resident | RT04 | Native TTL checks |
| `observability/introspect.py` | Observability | CP02, CP03, WC01 | Native WBC adapter queries |
| `supervisor/chain_runner.py` | Execution | CP04, WC01, WC04 | Native WBC adapter evidence |
| `cloud/watchdog.py` | Watchdog | CP02 | Native introspect.v2 |
| `watchdog/repair_runner.py` | Watchdog | (none — native M9 eligibility) | Already native |
| `orchestration/completion_io.py` | Orchestration | CP04 | Native WBC-backed completion evidence |

---

## Adoption Matrix Cross-Reference

Every compatibility wrapper row above maps to one or more rows in the
[WBC Boundary Adoption Matrix](./wbc-boundary-adoption-matrix.md).  See
the "Adoption Matrix Row" column in each inventory table.

### M10 Deletion Gate Checklist

- [ ] All `reader_count` fields verified at zero
- [ ] All `deletion_blocked_until_epoch_ms` timestamps passed
- [ ] Permanent gap markers (WC02, WC03, RT01, RT02) excluded from deletion
- [ ] Deletion acceptance transactions committed
- [ ] Incident bridge audit confirms no active references
- [ ] Wrapper registries pruned of DELETED entries
- [ ] Compatibility `__init__.py` imports removed for deleted wrappers
- [ ] `wbc_compat.py` adapters with `reader_count==0` and EXPIRED status removed

---

## Schema

```json
{
  "schema": "m9.compatibility-expiry-map",
  "version": 1,
  "generated_at": "2026-07-22T22:56:00Z",
  "depends_on": ["T45", "T46", "T47", "T18"],
  "non_authoritative": true,
  "total_wrappers": 14,
  "permanent_evidence_markers": 4,
  "deletable_wrappers": 10,
  "active_readers_total": 20
}
```
