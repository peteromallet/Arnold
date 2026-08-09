# M4: BoundaryTurn Template Promotion Integration

> Superseded as an executable milestone by C1-C6. Preserved only as historical
> checklist material; it cannot add a prompt, gate, or policy choice to the
> corrective chain.

## Outcome

BoundaryTurn and structured-output template promotion emit durable boundary
promotion evidence conforming to `BoundaryContract`.

Model-filled templates, canonical artifact promotion, receipts, and
`phase_result` become one coherent boundary record.

## Scope

IN:

- Integrate structured-output template registry entries with
  `BoundaryContract`.
- Where a structured output represents a common boundary shape, integrate it
  with the reusable template profiles from M3 instead of creating a
  phase-local proof schema. At minimum, artifact promotion should map cleanly to
  `ArtifactHandoffBoundary`, validation/check outputs to `ValidationBoundary`,
  revision suggestions to `RevisionBoundary`, and approval/waiver outputs to
  `ApprovalBoundary` where applicable.
- For each covered structured phase, record:
  - scratch template path;
  - model-filled output path;
  - validation result;
  - canonical promoted artifact path;
  - artifact hash/fingerprint;
  - receipt path;
  - `phase_result` relation;
  - invocation/run identity.
- Reject direct model writes to canonical outputs where the contract requires
  scratch-to-canonical promotion.
- Keep existing canonical artifact paths stable.
- Preserve phase-specific policies for gate/finalize/review/execute.

OUT:

- Replacing canonical artifacts.
- Flattening stage policy into BoundaryTurn.
- Changing route decisions.

## Locked Decisions

- The model fills scratch/template files; the harness validates and promotes.
- BoundaryTurn can propose workflow transitions but does not bypass transition
  policy.
- Child turns do not write parent canonical artifacts.

## Done Criteria

1. Covered structured phases emit boundary promotion records.
2. Promotion records are enough for semantic health to distinguish:
   - scratch written but not promoted;
   - canonical promoted but no receipt;
   - receipt exists but phase result missing;
   - model wrote wrong path.
3. Existing template-boundary tests continue to pass.
4. New tests assert semantic-health findings for broken promotion sequences.
5. At least two structured-output paths use reusable boundary templates rather
   than ad hoc phase-local metadata.

## Touchpoints

- `arnold_pipelines/megaplan/handlers/structured_output.py`
- `arnold_pipelines/megaplan/template_registry.py`
- BoundaryTurn foundation code
- critique/gate/finalize/execute/review handlers
- template-boundary tests
