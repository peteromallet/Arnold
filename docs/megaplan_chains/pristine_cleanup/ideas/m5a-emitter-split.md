# M5a — Decompose emitter.py

## Outcome
`vibecomfy/porting/emitter.py` is split from a 3304-line god-module into cohesive,
navigable modules, with its public `port convert` output unchanged. Done as its own
milestone (split out from the old combined M5) because the emitter depends only on M2,
while session/errors (M5b) depends on M4 — different dependencies, different blast radius.

## Dependency note
**Depends on M2 only** (verified: `emitter.py` does not import the validation triad or
`provider.py` — only a stray comment references schema at ~line 2748). It uses M2's
shared AST/util layer (`UI_ONLY_CLASS_TYPES`, `_is_link` @ ~2516, the widget-translation
helpers). It does **not** depend on M3. It does depend on M4 only insofar as M4 unifies
the diagnostic dataclass base that `EmissionDiagnostic` (`emitter.py:52`) joins — so run
after M4 to avoid re-touching the same lines. (M3 and this milestone are independent and
could run in parallel in a cloud/manual schedule; the chain serializes them only for
simplicity.)

## Problem (audit lens 2)
`emitter.py` (3304 LOC) bundles 50+ functions: codegen, widget-alias resolution, constant
hoisting, subgraph handling, type hints, section grouping, AST formatting, plus a 37-line
inline `_NODE_HELPER_SOURCE` string literal. `_emit_build_function` is ~300 lines;
`_node_kwargs` is ~270 lines. Internal helpers are unreachable by other porting modules
without importing the whole surface.

## Scope
1. Split `emitter.py` along its natural seams into cohesive modules — propose:
   `emit_build` (the build-function emitter), `node_kwargs`/widget-translation,
   `subgraph` emission, `formatting`/section grouping, and extract the
   `_NODE_HELPER_SOURCE` template out of the logic module into a data/template file.
2. Use M2's shared AST utils throughout; remove emitter-local copies.
3. Join `EmissionDiagnostic` to M4's shared diagnostic base (if M4 landed first) rather
   than re-declaring fields.

## Locked decisions
- **Behavior-preserving.** `port convert` output stays byte-identical where
  snapshot/parity tests assert it. The **9/9 parity fixtures from M1** are the gate — this
  is exactly why the parity backfill was pulled forward into M1.
- No public API rename. Internal module boundaries only.

## Done criteria
- No single emitter module exceeds ~600 LOC; no multi-hundred-line string literal remains
  inside a logic module.
- All 9 parity fixtures pass byte-for-byte (or any snapshot change is explicitly
  re-blessed with written justification).
- The M1 golden gate (`docs/audits/m1-safety-gate.md`) passes in full.
- Full `pytest` green; `port convert`/`port check` CLI smoke pass with stable output.

## Touchpoints
`vibecomfy/porting/emitter.py` (+ new sibling modules under `vibecomfy/porting/`),
`vibecomfy/porting/convert.py` (the `EmissionDiagnostic → PortIssue` mapping),
parity/snapshot tests under `tests/`.

## Anti-scope
Do not touch `session.py`, the run path, or error architecture (M5b). Do not re-open
validation (M3) or eval/diagnostics (M4) beyond joining the shared diagnostic base. No
doc edits (M7).
