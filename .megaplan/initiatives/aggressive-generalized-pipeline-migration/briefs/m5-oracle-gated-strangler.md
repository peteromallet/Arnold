# M5: Oracle-Gated Strangler

## Outcome

The migration is protected by replay and parity, not trust. Each future deletion or route flip must have an oracle that proves it.

## Scope

In scope:

- Inventory existing oracle infrastructure: fold/WAL equivalence, replay oracles, substrate-swap oracles, hinge-gate topology parity, pipeline parity, evaluand/calibration replay, and dual-run scaffolding.
- Add a formal command or test group for each migration parity class.
- Create golden traces for happy path, iterate, blocked/resume, retry/recovery, and escalation where fixtures already exist or can be produced cheaply.
- Add artifact byte comparison where deterministic.
- Add semantic event/state comparison for timestamps, IDs, and nondeterministic fields.
- Make oracle commands part of the acceptance gates for subsequent extractor/strangler work.
- Extract the generic verification RUNNERS the substrate is missing (Arnold has contract types but no contract runners): the typed subprocess oracle runner (`orchestration/oracle.py:21-73`, zero coupling) -> `arnold/runtime/oracle.py`; `SuiteDelta` + `compute_delta` test-suite structural diff (`completion_contract.py:299-383`) -> `arnold/pipeline/suite_delta.py` via a minimal `SuiteRunProtocol`; the `EvidenceStatus` + `TrustClass` enums (`evidence_contract.py:36-61`) -> `arnold/pipeline/types.py`. Leave the megaplan-coupled `EvidenceRef`/`ArtifactRef`/`verifiability`/`completion_contract` bulk in place.

Out of scope:

- Rewriting the oracle harness from scratch.
- Broad fixture generation unrelated to executor/supervisor/control migration.

## Locked Decisions

- Deleting compatibility shims requires dual-green or oracle evidence.
- Byte parity is preferred; semantic parity is allowed where nondeterminism is explicit and documented.

## Done Criteria

- Oracle command/test groups exist and are documented.
- At least one golden trace exercises each major migrated layer from M0-M4.
- Future shim deletion has a clear oracle gate.
- CI-targeted oracle tests pass.
