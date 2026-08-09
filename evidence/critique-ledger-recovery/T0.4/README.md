# T0.4 authoritative incident inventory

This is a read-only, content-addressed join for session
`critique-ledger-accountability-v2-20260728` and plan
`cl2-wbc-backed-ledger-20260731-1411`. It does not replace or promote any
owner record. T0.2 supplied 319 preserved claims; the inventory contains one
row for each claim, six explicit T4 action targets, six fail-closed gap targets,
and eleven additive incident/writer-surface join rows.

## Outputs and verification

- `inventory.json` — strict schema `t0.4.authoritative-incident-inventory.v1`.
- `inventory.csv` — operator-oriented flattened view of the same rows.
- `unresolved.json` — all missing, blocked, unavailable, and indeterminate
  owner records; none is treated as absent, safe, terminal, released, or
  redispatchable.
- `verify_inventory.py` — checks schema/vocabularies, deterministic IDs,
  uniqueness, every source claim/object and digest, and exact T4 target maps.
- `verification-receipt.json` — verifier result.

The verifier result is **PASS**. It checked 342 rows and 389 source references;
all 389 content-addressed objects matched their T0.2 manifest digests. There
are 342 unique record IDs and 342 unique target IDs. All T4.1–T4.6 tasks have
exact inventory targets, including explicit unresolved targets where an owner
record was not preserved. T0.4's completion criterion is therefore satisfied.

## Counts

| Dimension | Counts |
|---|---|
| Rows | 342 |
| Unresolved rows | 14 |
| Categories | `marker_projection_artifact` 101; `repair_fixer` 62; `phase_task_state` 55; `selection_session_spec` 27; `diagnostic` 22; `run_authority` 13; `plan_state` 11; `wbc` 10; `writer_effect_surface` 9; `incident` 4; `runtime_vector` 6; `cloud_generation` 5; `chain_state` 4; `notification` 3; `git` 3; `custody` 2; `process` 2; `storage_health` 2; `cloud_image_package` 1 |
| Current state | `hash-verified` 308; `hash-verified-redacted` 10; `observed` 12; `blocked` 2; `unavailable` 4; `missing` 4; `indeterminate` 2 |
| Authority classification | `evidence-only` 235; `projection` 90; `unavailable` 12; `inferred` 3; `ambiguous` 2 |
| Required action | `preserve` 322; `fence` 4; `verify` 2; `revoke` 3; `expire` 2; `reconcile` 2; `no-redispatch` 3; `quarantine` 1; `CAS-away` 1; `read-only-freeze` 2 |

## Critical exact targets

- **T4.1**: the complete selection/session/spec/workspace/plan/branch/profile/
  runtime tuple, including the target chain record and runtime source vector.
- **T4.2**: the exact v2 tuple's Run Authority grant/decision/fence/revocation
  set. The current owner ledger is unavailable, so revoke is fail-closed.
- **T4.3**: the exact v2 tuple's Custody target/lease/epoch/fence-token/claim
  set. No plain release or key reuse is permitted; the owner record is
  unavailable.
- **T4.4**: WBC attempt stores, custody-shaped ledger, event/routing evidence,
  GLEK/intent/outcome/provider-receipt scope. Missing completeness remains
  `INDETERMINATE` and no-redispatchable.
- **T4.5**: `chain-501c561132ce` and the old session marker. Selection must be
  moved by owner CAS; the marker is not edited.
- **T4.6**: the exact remote workspace, branch, plan path and artifact scope,
  frozen read-only.

## Gaps and contradictions

1. T0.0 forensic reports conflict: `result.md` says no owner-issued
   RA-CONTAIN interface exists and T0.2 explicitly leaves containment blocked,
   while `ra-contain-agent-final.md` reports an implementation commit. T0.4
   preserves that contradiction as unresolved and does not treat the report or
   commit as an accepted owner receipt.
2. T0.2 has no persisted current Run Authority grant/fence/revocation owner
   ledger, and no current Custody owner query/receipt. The inventory records
   these as unresolved targets, not as proof that nothing existed.
3. WBC-adjacent SQLite attempt stores, `routing_ledger.jsonl`,
   `critique_custody_v1.json`, event logs, and receipts are preserved, but the
   evidence does not prove a complete GLEK/provider-outcome reconciliation.
4. Notification filename and content scans both exited successfully with
   empty output. No provider was queried; delivery, intent, message ID, and
   provider receipt are therefore unknown rather than absent or safe.
5. The container import/config/model-route probe was blocked by OCI
   `ENOSPC`; host process, image, mount, and package metadata do not close that
   gap. The runtime candidate `arnold/manifest` was also unavailable.
6. The chain record/log evidence contains an absent/stale selection reference
   and the preserved session marker observed `launch_in_progress`/starting
   behavior. These are separate projection/evidence rows and are not promoted
   into chain authority.
7. The Git evidence records commit `bf25a699f85315e1a282df55502ba275253411f9`,
   tree `20ada0ea10f921cf79d22f5f38111820576b62a5`, branch
   `megaplan/critique-ledger-accountability-v2-20260728`, and dirty/untracked
   state. The remote runtime vector separately names commit
   `c7bcb06af536acfe759c1b31a785afc19afe92d4`; this is an identity join to
   preserve, not a resolution of source/runtime drift.

## Safety boundary

Excerpts are limited to T0.2 `minimal_safe_excerpt` values and are scrubbed for
credentials, secrets, and URLs. T0.2 objects are not rewritten. No provider,
cloud, branch, plan, marker, worktree, or external service was contacted or
mutated while producing T0.4.
