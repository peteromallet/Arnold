# M5: Validator And CLI UX

## Outcome

Ship the authoring surface as a usable product interface, not just an internal compiler.

## Source Material

- M1-M4 outputs.
- Existing workflow CLI conventions.
- `docs/arnold/python-shaped-authoring-contract.md`

## Scope

Implement or update:

- `arnold workflow check <workflow.py>`.
- `arnold workflow compile <workflow.py> --out <manifest.json>`.
- `arnold workflow inspect <workflow.py>`.
- `arnold workflow explain <workflow.py>`.
- Machine-readable JSON diagnostics for agents.
- Human-readable diagnostics with source locations and fix guidance.
- Clear treatment of import violations, component contract violations, prompt/resource errors, ambiguous routes, policy mismatches, and manifest validation failures.
- CLI tests for source files, installed packages, and local project layouts.

## Constraints

- Diagnostics should explain the authored source first and expose engine internals only when useful.
- The CLI must not train users to edit generated DSL or manifest files as their primary workflow.

## Done Criteria

- A new pipeline author can validate a workflow file and understand what to fix.
- Agents can consume structured diagnostics without scraping prose.
- Megaplan’s canonical workflow can be checked, compiled, inspected, and explained through the CLI.
