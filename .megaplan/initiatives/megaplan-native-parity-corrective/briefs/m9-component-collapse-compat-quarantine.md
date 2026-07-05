# M9 - Component Collapse And Compatibility Quarantine

## Objective

Remove, demote, or quarantine all component/handler/runtime paths that formerly
owned report-level semantics.

## Files To Change And Instructions

- `components.py`
  Remove report-owned route bindings, topology contracts, fanout/reducer
  contracts, handler refs, and override dispatch metadata, or mark them
  compatibility-only with tests proving they cannot influence corrected flow.
- `manifest_backend.py`, `route_dispatch.py`, `auto.py`, CLI dispatch
  Delete decision translators or quarantine as legacy with explicit fences.
- Compatibility shells and projected native programs
  Prove they consume canonical source-derived semantics or cannot satisfy
  traceability rows.

## Verifiable Completion Criterion

- Deleting/quarantining semantic metadata from `components.py` does not change
  deterministic corrected product-routing traces.
- Adapters that translate data may remain; adapters that translate decisions
  are gone or legacy-fenced.
- No implemented row cites components, handler refs, route bindings, manifest
  backend routing, auto next-step derivation, CLI handlers, or projected-native
  shells as proof.

