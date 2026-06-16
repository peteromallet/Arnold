# Structured Output Template Boundaries

## Outcome

Implement a template-fill path for all enforced megaplan structured-output contracts so fast/open Hermes models can fill canonical JSON files instead of inventing strict JSON objects from scratch.

This sprint covers `critique`, `critique_evaluator`, `gate`, `finalize`, `execute`, and `review` in one coherent contract/promotion design, and adds a registry/parity check so every enforced model-generated structured contract has a template builder. `plan` and `revise` remain Markdown-oriented and should get skeleton/prompt improvements only if needed to support the structured phases.

## Scope

In scope:

- Add canonical template builders for `critique`, `critique_evaluator`, `gate`, `finalize`, `execute`, and `review`.
- Add a central template registry keyed by step/phase contract, with a parity test against enforced model-generated `StepContract` schemas.
- For enforced structured contracts that are not wired into file-fill in this sprint, provide a builder and mark the handler integration as a follow-up, or document why the contract is not model-generated.
- Have handlers write phase scratch output files such as `critique_output.json`, `critique_evaluator_output.json`, `gate_output.json`, `finalize_output.json`, `execute_output.json`, and `review_output.json` before invoking the worker where the worker path supports file fill.
- Update prompts to reference the exact scratch file path and require filling that file.
- Make parsing prefer the scratch file, validate it, then write the existing canonical artifact such as `critique_vN.json`, `gate.json`, `finalize.json`, `execution.json`, or `review.json`.
- Add narrow recovery for common model aliases while preserving strict canonical artifacts.
- Add tests for every covered phase, with doc/metaplan finalize as the highest-priority regression.

Out of scope:

- Replacing the existing canonical artifacts (`finalize.json`, `critique_v*.json`, `gate.json`, etc.).
- Large rewrite of the worker runtime or Hermes agent beyond the minimum needed to pass a phase-specific template path.
- Making MiMo the default model for structured phases.
- Solving all provider-specific malformed-output behavior in one pass.

## Locked Decisions

- The canonical artifact remains owned by the harness. The model fills a scratch/template file; the harness validates and promotes it.
- Do not duplicate template JSON in multiple prompt strings. Use code-owned builders or a central registry.
- Consistency rule: any phase or subphase with an enforced model-generated structured schema gets a fillable template builder; handler file-fill wiring may be staged, but the template contract itself is not optional.
- The model must not choose output paths. The handler computes the path and passes it into the prompt.
- For doc/metaplan finalize, the final task is prose review/polish, not tests.
- `plan` and `revise` are not JSON-template phases; they may use Markdown section skeletons, but they should not be forced into strict JSON.
- For MiMo, prefer fill-only templates plus narrow recovery over permissive freeform parsing.

## Open Questions

- Should file-fill be required only for Hermes/file-tool workers, with chat-only workers still returning JSON?
- Should repeated malformed structured-output failures trigger auto strategy changes, or should that be a follow-up sprint?
- Which lower-priority enforced contracts beyond this sprint (`feedback`, prep subphases, loop phases, tiebreakers) need immediate handler integration, versus builder/parity coverage now and handler integration in a follow-up?

## Constraints

- Existing tests around strict schema auditing must continue to pass.
- Existing canonical artifacts and downstream consumers must not change paths.
- Recovery may strip unknown keys only before promotion; promoted artifacts must remain schema-valid.
- Do not allow a model to overwrite `finalize.json` directly.

## Done Criteria

- Each covered structured phase creates its scratch template file before model invocation where applicable.
- Every enforced model-generated structured contract has a template builder registered, or a documented non-model-generated exemption.
- Each covered prompt names the absolute scratch file path and says only that file counts when file tools are available.
- The parser reads and validates the scratch file, then promotes to the canonical artifact.
- Doc/metaplan finalize succeeds with a filled template shape in tests.
- Tests cover wrong-path writes being ignored or rejected.
- Tests cover unknown top-level keys not reaching the canonical artifact.
- Tests cover `critique`, `critique_evaluator`, `gate`, `finalize`, `execute`, and `review` template paths.
- Tests cover `critique_evaluator` accepting empty `flag_verifications` and rejecting non-list evaluator fields.
- Existing targeted suites for critique, gate, finalize, execute, review, doc mode, prompts, model seam, and worker parsing pass.

## Touchpoints

- `arnold/pipelines/megaplan/handlers/finalize.py`
- `arnold/pipelines/megaplan/handlers/critique.py`
- `arnold/pipelines/megaplan/handlers/gate.py`
- `arnold/pipelines/megaplan/handlers/execute.py`
- `arnold/pipelines/megaplan/handlers/review.py`
- `arnold/pipelines/megaplan/prompts/finalize.py`
- `arnold/pipelines/megaplan/prompts/critique.py`
- `arnold/pipelines/megaplan/prompts/critique_evaluator.py`
- `arnold/pipelines/megaplan/prompts/gate.py`
- `arnold/pipelines/megaplan/prompts/execute.py`
- `arnold/pipelines/megaplan/prompts/review.py`
- `arnold/pipelines/megaplan/prompts/review_doc.py`
- `arnold/pipelines/megaplan/audits/critique_evaluator.py`
- `arnold/pipelines/megaplan/step_contracts.py`
- `arnold/pipelines/megaplan/workers/_impl.py`
- `arnold/pipelines/megaplan/model_seam.py`
- `arnold/pipelines/megaplan/schemas/runtime.py`
- `arnold/pipelines/megaplan/runtime/doc_assembly.py`
- `tests/test_finalize.py`
- `tests/test_critique.py`
- `tests/test_critique_evaluator.py`
- `tests/test_gate.py`
- `tests/test_execute.py`
- `tests/test_review.py`
- `tests/test_doc_mode.py`
- `tests/test_prompts.py`
- `tests/arnold/pipelines/megaplan/test_model_seam.py`

## Anti-Scope

- Do not hand-edit generated plan state under `.megaplan/plans/`.
- Do not loosen canonical schemas just to accept weak model output.
- Do not add provider-specific special cases where a generic template-fill contract would solve the issue.
