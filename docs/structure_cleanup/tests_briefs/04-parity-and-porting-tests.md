# Tests Layer Audit 04: Parity And Porting Tests

Audit tests for porting, UI/API parity, strict-ready gates, conversion, lowering,
and template alignment.

Questions:
- Which dirs/files form the porting/parity test surface?
- Are fixture paths hard-coded to docs/templates/ready_templates/workflow_corpus?
- Are any old test names misleading after the docs/template moves already made?
- What safe structure cleanup exists without changing assertions?

Return exact references to inspect before any move.
