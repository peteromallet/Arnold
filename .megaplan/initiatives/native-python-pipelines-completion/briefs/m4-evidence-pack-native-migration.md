# M4 - Evidence Pack Native Migration

## Objective

Migrate `evidence_pack` to the native-first contract, including shared native suspension and resume, while preserving ingest, fanout, reduction, human review, attestation, and downstream example behavior.

## Files To Change And Instructions

- `arnold/pipelines/evidence_pack/__init__.py`
  Move metadata and `build_pipeline(...)` to the final projected-shell-plus-`native_program` contract.
- `arnold/pipelines/evidence_pack/pipeline.py`
  Create the native declaration for ingest, validator fanout, reduction, human review, and attestation emission.
- `arnold/pipelines/evidence_pack/steps.py`
  Keep runtime-agnostic step logic here and remove graph-only orchestration assumptions.
- `arnold/pipelines/evidence_pack/pipelines.py`
  Reduce this module to private legacy builders only or eliminate it as the public construction surface.
- `arnold/pipelines/evidence_pack/hooks.py`
  Replace graph-executor coupling with runtime-neutral hooks or delete the hook surface if it is no longer needed.
- `arnold/pipelines/evidence_pack/resume.py`
  Remove package-specific continuation architecture and route resume through shared native runtime semantics.
- `arnold/pipelines/evidence_pack/verifier.py`
  Keep verification and attestation behavior aligned with the migrated pipeline contract.
- `arnold/pipelines/_deliberation_example/__init__.py`
  Update the example package exports to stop importing graph-era review concepts.
- `arnold/pipelines/_deliberation_example/pipelines.py`
  Repoint example construction to the migrated `evidence_pack` contract.
- `arnold/pipelines/_deliberation_example/_hooks.py`
  Remove or adapt any old hook usage that assumes graph-based continuation.
- `tests/arnold/pipelines/evidence_pack/test_end_to_end.py`
  Keep the end-to-end review lifecycle stable under the native-backed contract.
- `tests/arnold/pipelines/evidence_pack/test_hooks.py`
  Rework hooks coverage around the new runtime-neutral contract.
- `tests/arnold/pipelines/evidence_pack/test_pipelines.py`
  Assert the package now returns a projected shell with `native_program`.
- `tests/arnold/pipelines/evidence_pack/test_resume.py`
  Verify shared native suspension and resume behavior.
- `tests/arnold/pipelines/evidence_pack/test_steps.py`
  Keep step-level behavior stable.
- `tests/arnold/conformance/test_evidence_pack_conformance.py`
  Update conformance assertions to the final native-first behavior.
- `tests/arnold/pipeline/test_evidence_pack_expressibility.py`
  Keep expressibility coverage aligned with the migrated declaration and resume contract.
- `tests/arnold/pipeline/test_composite_resume.py`
  Update shared resume coverage if `evidence_pack` changes the common continuation path.

## Verifiable Completion Criterion

- `evidence_pack` returns a projected `Pipeline` shell with non-null `native_program`.
- Human review and resume flow through shared native runtime semantics rather than package-specific continuation builders.
- The named end-to-end, resume, conformance, and expressibility tests all pass against the migrated package contract.

## Native Representation Alignment

- Matrix rows affected: Human decision/suspension; Path-addressed checkpoints; Behavior parity with existing Megaplan.
- Expected status change: substrate `enabled` by proving shared native suspension/resume works outside Megaplan.
- Proof artifacts: evidence-pack resume tests, human-review suspension tests, conformance fixture, and expressibility coverage.
- False-pass guard: a package-specific continuation builder or handler-local wait state would not prove the shared suspension primitive Megaplan needs.
- Deferrals: Megaplan-specific human gates and resume paths remain owned by composition M1/M5 and platform M4/M6.
- Canonical paths/imports: record any shared resume/import surfaces changed so Megaplan M3.5/M5 can depend on the same contract.

## Risks And Blockers

- `evidence_pack` combines fanout, reduction, human review, and continuation, so it is easy to get a structurally valid but behaviorally wrong migration.
- Example consumers under `_deliberation_example` can keep stale imports alive if they are not updated in the same milestone.
- Shared resume changes can regress other human-gated packages if the common contract is not stable after M3.5.

## Dependencies

- Depends on M1 and M3.5.
- Must finish before M5 test cleanup can treat native traces as canonical.
