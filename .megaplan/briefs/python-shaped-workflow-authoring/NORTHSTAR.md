# Python-Shaped Workflow Authoring North Star

Arnold workflows should be authored, reviewed, validated, and explained from ordinary Python source files, while the existing DSL, `WorkflowManifest`, runtime journal, resume, suspension, artifact, and packaging contracts remain the execution source of truth.

The end state is a smooth authoring product:

- Workflow authors edit `workflow.py` and typed component exports, not generated DSL or manifest files.
- The compiler parses and validates source without executing workflow code.
- Imports are the user-facing dependency declaration for steps, prompts, policies, schemas, and subflows.
- Diagnostics point at source spans with stable machine-readable codes and human-actionable messages.
- Megaplan's real planning workflow is readable as canonical authored Python and still behaves identically through `build_pipeline()`.
- Shipped docs, skills, examples, CLI inspection, rendered topology, package artifacts, and conformance ledgers all present Python-shaped authoring as the primary interface.
- No deleted legacy authoring/runtime surfaces return as compatibility shims.

Every milestone must preserve the separation between authoring frontend and runtime backend: Python-shaped authoring lowers into the established DSL/manifest machinery; it does not create a second runtime.
