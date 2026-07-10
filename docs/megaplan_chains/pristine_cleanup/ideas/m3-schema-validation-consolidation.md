# M3 — Collapse the Schema/Validation Triad + Decompose provider.py

## Outcome
One canonical node-call validation path and a decomposed schema-provider module. The
"three sources of truth" for the same correctness check become one, eliminating the
guaranteed-drift the audit flagged.

## Problem (audit lens 8)
Three modules independently validate node calls against a `SchemaProvider`, and they
have **already diverged**:
- `vibecomfy/schema/validate.py` — has class-specific dynamic-input handling
  (LTX/SimpleCalculator, ~lines 294-374) the others lack; uses `ValidationIssue`.
- `vibecomfy/schema/call_validation.py` — adds primitive-type checking (~lines 114-129)
  the others lack; uses `NodeCallValidationIssue`/`NodeCallValidationReport`.
- `vibecomfy/porting/validate_call.py` — skips enum, range, AND type validation
  entirely; uses `CallValidationError`/`CallValidationResult`; accesses `schema.inputs`
  as a bare attribute (others use defensive `getattr`).

Separately, `vibecomfy/schema/provider.py` is a 984-line god-module bundling 9
`SchemaProvider` implementations, the Protocol, a factory, and 20+ helpers. Its
`ConversionSchemaProvider.get_schema()` documents a 5-step precedence but the code runs
6 (an unlisted `ObjectInfoIndexSchemaProvider` step) and has a duplicate
`# 3. Source parser` comment — the precedence documentation is wrong.

## Scope
1. **Choose one canonical validation implementation** (propose folding all three into
   `vibecomfy/schema/`), with a single result/issue model. It must be the **superset**:
   class-specific dynamic-input handling + primitive-type checking + enum/range checks.
2. **Migrate all callers** — including `porting/` (`validate_call.py`'s consumers, the
   `port validate-call` CLI command) and `commands/` — to the canonical path. Preserve
   each public CLI contract (`port validate-call`, `validate`, `doctor`).
3. **Decompose `provider.py`** into cohesive modules (e.g. one per provider family, a
   `protocol.py`, a `factory.py`). Use M2's shared utils where the providers embed
   AST/literal helpers.
4. **Fix the precedence bug**: make `ConversionSchemaProvider.get_schema()`'s code and
   its docstring agree on the actual ordered precedence (currently 6 real steps).

## Locked decisions
- **Behavior-preserving for valid inputs.** Where the three validators previously
  *disagreed*, the canonical (superset) behavior is correct; document each such case in
  the plan with a test pinning the new behavior. Do not silently change which workflows
  pass/fail without an explicit, tested decision.
- Build on M2's shared utils — do not re-introduce local copies of AST helpers.

## Done criteria
- Exactly one node-call validator; `porting/validate_call.py` is gone or reduced to a
  thin re-export with a deprecation note.
- `provider.py` is decomposed; no single file in `schema/` exceeds ~400 LOC.
- Precedence code/docstring agree; a test asserts the resolution order.
- Full `pytest` green; `port check`, `port validate-call`, `validate`, `doctor` CLI
  smoke tests pass with stable output.

## Touchpoints
`vibecomfy/schema/{validate,call_validation,provider,cache,format}.py`,
`vibecomfy/porting/validate_call.py`, `vibecomfy/commands/{port,schemas,doctor}.py`,
relevant tests under `tests/`.

## Anti-scope
Do not touch the eval modules or diagnostics systems (M4). Do not split `emitter.py`
or `session.py` (M5). Do not edit docs (M6).
