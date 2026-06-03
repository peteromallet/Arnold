# M4: Artifact Provenance Rollout

Source ticket: `01KT50AZRMK5X890TQ565DDB5V`

## Outcome

Roll write-time metadata and freshness helpers across key artifacts and stores so later policy can reason about freshness uniformly.

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

OUT:

- No new enforcement policy.
- No transition expansion.
- No cryptographic tamper-proof chains.

## Locked Decisions

- Metadata is written at artifact creation, not inferred later from filenames.
- Receipts are audit records, not automatically verified evidence when they mirror worker payload fields.
- Legacy artifacts remain readable as unknown/legacy.

## Open Questions

- Exact metadata protocol for DB-backed artifacts.
- Whether mixed artifacts need sub-document metadata in v1 or companion evidence records.
- Where to centralize artifact write wrappers without broad churn.

## Constraints

- Broad but mechanical: minimize behavior changes.
- Do not destabilize existing plan loading.
- Tests should cover old and new artifact formats.

## Done Criteria

1. Key newly written artifacts carry provenance metadata.
2. Common freshness helper classifies fresh/stale/missing/legacy/baseline-unavailable.
3. File and DB store paths share the same metadata semantics where applicable.
4. Receipts and artifact-written events include hashes/provenance summaries.
5. Existing artifacts without metadata load as legacy-unknown.
6. Tests cover representative artifacts and stores.

## Touchpoints

- artifact write helpers
- `megaplan/store/*`
- `megaplan/orchestration/phase_result.py`
- `megaplan/execute/*`
- `megaplan/handlers/*`
- `megaplan/receipts/*`
- artifact/freshness tests

## Rubric

- Profile: `directed`
- Robustness: `full`
- Depth: `medium`

Rationale: broad but mostly mechanical after M0-M3 define the shape.

