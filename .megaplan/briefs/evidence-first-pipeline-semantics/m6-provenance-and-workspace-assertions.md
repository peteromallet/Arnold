# M6: Provenance and Workspace Assertions

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Roll write-time metadata and freshness helpers across key artifacts and stores so later policy can reason about freshness uniformly.

Add cheap target workspace assertions at authority transitions only: target `HEAD`, dirty-set, and the checked SHA used for evidence decisions are recorded and compared at execute-start, review-start, done/advance, and reset. This replaces v1's per-boundary tree hashing with lower-cost assertions that supply the TOCTOU checked-SHA needed by transition policy.

## Scope

IN:

- Add write-time metadata to key artifacts:
  - `phase_result.json`
  - `execution_audit.json`
  - `review_audit.json`
  - `finalize.json`
  - `execution.json`
  - `review.json`
  - `gate_v*.json`
  - `critique_v*.json`
  - `execution_batch_*.json`
  - receipts / artifact-written events
- Add a common artifact metadata shape for file and DB-backed stores.
- Link receipts, phase results, and artifacts through invocation ids and artifact hashes.
- Add freshness helpers that distinguish:
  - fresh
  - stale
  - missing
  - legacy-unknown
  - baseline-unavailable
- Preserve field-level trust semantics for mixed artifacts, especially `finalize.json`.
- Capture target `HEAD`, dirty-set, and checked SHA at authority transitions only:
  - execute-start
  - review-start
  - done/advance
  - reset
- Compare the checked SHA against the current target head before authority increases and surface stale-decision diagnostics.

OUT:

- No new enforcement policy.
- No transition expansion.
- No cryptographic tamper-proof chains.
- No per-boundary engine-tree hashing.
- No broad contamination detection; M0 isolation owns prevention.

## Locked Decisions

- Metadata is written at artifact creation, not inferred later from filenames.
- Receipts are audit records, not automatically verified evidence when they mirror worker payload fields.
- Legacy artifacts remain readable as unknown/legacy.
- Target workspace assertions run at authority transitions, not every phase boundary.
- The checked SHA is the TOCTOU anchor for later transition decisions.

## Open Questions

- Exact metadata protocol for DB-backed artifacts.
- Whether mixed artifacts need sub-document metadata in v1 or companion evidence records.
- Where to centralize artifact write wrappers without broad churn.
- Exact dirty-set representation and comparison rules for carried dirty paths.

## Constraints

- Broad but mechanical: minimize behavior changes.
- Do not destabilize existing plan loading.
- Tests should cover old and new artifact formats.
- Workspace assertions must be cheap and avoid false positives on expected target mutation.

## Done Criteria

1. Key newly written artifacts carry provenance metadata.
2. Common freshness helper classifies fresh/stale/missing/legacy/baseline-unavailable.
3. File and DB store paths share the same metadata semantics where applicable.
4. Receipts and artifact-written events include hashes/provenance summaries.
5. Existing artifacts without metadata load as legacy-unknown.
6. Target `HEAD`, dirty-set, and checked SHA are captured at execute-start, review-start, done/advance, and reset.
7. A stale checked-SHA or unexpected dirty-set change at an authority transition produces structured diagnostics.
8. Tests cover representative artifacts, stores, workspace assertions, stale checked-SHA, carried dirty paths, and legacy reads.

## Touchpoints

- artifact write helpers
- `megaplan/store/*`
- `megaplan/orchestration/phase_result.py`
- `megaplan/execute/*`
- `megaplan/handlers/*`
- `megaplan/receipts/*`
- authority transition preflights
- reset entrypoints
- artifact/freshness/workspace assertion tests

## Rubric

- Profile: `directed`
- Robustness: `full`
- Depth: `medium`

Rationale: broad but mostly mechanical after M1-M5 define the shape, with modest added care for cheap TOCTOU assertions at the authority transitions that matter.

