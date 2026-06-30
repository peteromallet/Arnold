# M2: Authoritative StepContract Registry

## Outcome

Megaplan phase metadata has one typed source of truth. Existing scattered schema/capture/normalizer/prompt/routing maps become derived views before old dicts are deleted.

## Scope

In scope:

- Add `arnold/pipelines/megaplan/step_contracts.py`.
- Define a small `StepContract` dataclass for phase identity, schema key, capture schema key, output kind, compatibility mode, normalizer reference, and default prompt/routing references as needed.
- Register contracts for `prep`, `plan`, `critique`, `critique_evaluator`, `revise`, `gate`, `finalize`, `execute`, `review`, and loop steps.
- Add factory/helpers that construct `StepInvocation` metadata from contracts.
- Derive old views used by `workers/_impl.py`, `model_seam.py`, prompts, schemas, and profile policy from the registry.
- Add byte/parity tests proving old and new invocation metadata agree before removing any old map.
- Delete raw duplicate dicts only when parity proves deletion is safe.

Out of scope:

- Changing model capture schemas.
- Changing prompt wording or routing policy semantics.
- Moving StepContract to neutral Arnold before Megaplan proves it internally.

## Locked Decisions

- StepContract does not own runtime model, provider, budget telemetry, prompt overrides, repair attempts, or output paths.
- The contract registry is initially Megaplan-specific. Generalization can follow after it is stable.

## Done Criteria

- Every current Megaplan step has a contract.
- Contract-derived metadata is byte-identical to legacy metadata before deletion.
- Model seam, prompt routing, worker parsing, and schema projection tests pass.
- AST/search tests prevent new raw ad-hoc invocation metadata construction where the contract factory should be used.
