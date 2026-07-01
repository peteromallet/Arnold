# M1.5: Public authoring contract and compatibility matrix

## Outcome
A locked, written public authoring contract that every later sprint can reference. The contract defines canonical imports, context aliases, stage/port semantics, CLI external input declarations, dry-run artifact behavior, and the deprecated private-import policy.

## Scope

IN:
- Write `docs/arnold/pipeline-authoring-contract.md` (or extend `new-arnold-pipeline/SKILL.md`) covering:
  - **Canonical imports**: graph pipelines import from `arnold.pipeline`; Megaplan-specific adapters import from `arnold.pipelines.megaplan._pipeline.*` with deprecation warning.
  - **Context fields and aliases**: neutral `StepContext` fields vs Megaplan adapter fields; mapping table.
  - **Stage/port declaration semantics**: what `produces`/`consumes` mean, how `PortRef` declares external CLI inputs vs inter-stage dependencies, required vs optional ports.
  - **CLI external input declaration contract**: how a stage declares that a port is satisfied by `--input KEY=VALUE` from the CLI.
  - **Dry-run artifact contract**: what `arnold run --dry-run` produces (rendered prompts, no API calls, deterministic artifacts).
  - **Deprecated private import policy**: `_pipeline.types` is a compatibility facade; deprecation warning text; migration path.
- File a brief decision record (`.megaplan/initiatives/arnold-pipeline-friction/briefs/decisions.md`) capturing the choices made.
- Update `new-arnold-pipeline/SKILL.md` to reference the contract.

OUT:
- No production code changes beyond doc updates.
- No new schemas or formats until M2.

## Locked decisions
- The contract is the source of truth for M2, M3, and M4.
- External inputs are declared via a specific port/field convention (to be decided in this sprint).

## Open questions
- Do we use `ReadRef`, `BindingRef`, or a new `external=True` flag on `PortRef` for CLI inputs?
- What is the exact dry-run artifact shape (file names, content schema)?

## Constraints
- The contract must be stable enough that M2 can implement CLI validation against it without reopening the design.

## Done criteria
- Contract doc exists and is approved by the planning harness.
- `new-arnold-pipeline/SKILL.md` links to it.
- Decision record captures the external-input declaration choice.

## Touchpoints
- `docs/arnold/pipeline-authoring-contract.md` (new)
- `arnold/pipelines/_template/skills/new-arnold-pipeline/SKILL.md`
- `.megaplan/initiatives/arnold-pipeline-friction/briefs/decisions.md` (new)

## Anti-scope
- Do not implement validation or code generation in this sprint.
- Do not change the `Port`/`PortRef` dataclasses here; that is M2.
