# M2: Compiler Core And Linear Lowering

## Outcome

Implement the first production compiler slice: restricted Python source -> validated component references -> `arnold.workflow.dsl.Pipeline` -> `WorkflowManifest` for linear workflows.

## Source Material

- M1 component contract and grammar output.
- `.megaplan/briefs/workflow-manifest-runtime-cleanup/python-shaped-authoring-production-polish-plan.md`
- Existing `arnold.workflow` DSL/compiler/validation/runtime APIs on the cleanup base.

## Scope

Implement:

- Public compile/check APIs for Python-shaped workflow source and files.
- AST parsing and semantic validation without `eval`, `exec`, or workflow-function invocation.
- One top-level workflow function.
- Assignment and tuple assignment from component calls.
- Keyword argument/dataflow lowering for component inputs.
- Import resolution through the M1 component contract.
- `halt`, `suspend`, and `transition` compiler intrinsic handling where needed for the linear subset.
- Source spans on lowered DSL nodes/routes.
- Golden fixtures for accepted and rejected linear workflows.

## Constraints

- Do not add runtime semantics that are not already expressible in DSL/manifest.
- Reject unsupported Python constructs with source-oriented diagnostics.
- Keep the generated manifest deterministic across repeated compiles.

## Done Criteria

- A simple workflow file compiles into an explicit DSL pipeline and valid manifest.
- Invalid imports, unsupported syntax, unknown components, and malformed calls fail with stable diagnostics.
- Tests prove no workflow code executes during compilation.
