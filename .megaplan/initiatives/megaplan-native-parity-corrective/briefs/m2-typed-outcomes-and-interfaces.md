# M2 - Typed Outcomes And Interfaces

## Objective

Define the typed domain boundary that lets native source route on explicit
outcomes instead of raw handler strings.

## Files To Change And Instructions

- Add closed outcome types for gate, tiebreaker, review, override, suspension,
  halt, execute, and finalize outcomes.
- Keep raw string labels only in compatibility serialization adapters.
- Add retained-handler interface/protocol definitions based on
  `arnold_pipelines/megaplan/native_interfaces.py` where useful.
- Add transitive handler-purity scanner support: retained handlers declare
  allowed side effects, and the scanner checks callees for report-owned routing.
- Add tests proving unsupported outcome values fail authoring or validation.

## Verifiable Completion Criterion

- Canonical source can branch on typed outcomes.
- Report-owned decisions do not branch on raw string literals.
- Every retained handler boundary has a typed input/output contract and an
  allowed-side-effect declaration.
- The semantic checker can distinguish typed outcome routing from compatibility
  string serialization.

## Native Parity Alignment

- This milestone enables extraction; it does not claim row implementation
  unless the row's source structure and behavior scenario already pass.

