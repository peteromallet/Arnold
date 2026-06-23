# M1: Component Contract And Grammar

## Outcome

Freeze the V1 Python-shaped authoring contract before implementation. The result should make clear what a workflow author may write, what imports are valid, how steps/prompts/policies/schemas/subflows are exposed, how validation discovers them, and what metadata must survive into DSL and `WorkflowManifest`.

## Source Material

- `.megaplan/briefs/workflow-manifest-runtime-cleanup/python-shaped-authoring-production-polish-plan.md`
- `.megaplan/briefs/workflow-manifest-runtime-cleanup/m4-5-python-shaped-authoring-frontend-plan.md`
- `.megaplan/briefs/workflow-manifest-runtime-cleanup/codex-end-state-megaplan-planning.py`
- `.megaplan/briefs/workflow-manifest-runtime-cleanup/codex-derived-megaplan-authoring-artifacts.md`
- `.megaplan/briefs/workflow-manifest-runtime-cleanup/deepseek-workflow-authoring-synthesis.md`

## Locked Decisions

- This is an authoring frontend over `arnold.workflow.dsl.Pipeline` and `WorkflowManifest`, not a new runtime.
- Workflow `.py` imports are the user-facing source of truth for component dependencies.
- Workflow compilation parses and validates source. It must not execute workflow code to discover topology.
- Valid workflow imports resolve only to typed workflow components or compiler intrinsics from `arnold.workflow.authoring`.
- Do not build on `arnold.pipeline.native`, `_pipeline`, `stages`, native projection, or compatibility shims.
- Generated catalogs may exist, but they are derived from component exports and imports, not edited as source.

## Scope

Define and document:

- V1 grammar and grammar version metadata.
- Component contract shape for steps, prompts, policies, schemas, and subflows.
- Canonical package and local-project file layout.
- Component discovery and import validation rules.
- Reserved compiler intrinsics and shadowing/aliasing rules.
- Source-span and manifest provenance requirements.
- Diagnostics contract, including stable machine-readable error codes.
- Acceptance fixtures for linear workflows and invalid imports.

## Done Criteria

- The grammar is small, explicit, and versioned.
- A component author can tell where to put a custom step or prompt and how to export it.
- A workflow author can tell what imports are allowed and why a rejected import failed.
- Later milestones can implement against this contract without reopening source-of-truth decisions.
