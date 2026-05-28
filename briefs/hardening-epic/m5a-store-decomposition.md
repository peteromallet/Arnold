# M5a — Store decomposition

**Rubric:** `partnered//high`, robustness `full`
**Position in epic:** milestone 7 of 12. Depends on M2 (parity already fixed) + M4 (names already canonical). Pure behavior-preserving refactor of the store god-files.

## Outcome
Split the two store god-classes into per-entity vertical slices without changing behavior. The `Store` protocol method surface and all public import paths stay intact.

## Scope (IN)
- `store/file.py` `FileStore` (~244 methods) and `store/db.py` `DBStore` (~169 methods) implement one protocol. Split each into per-entity slices using the internal `_*_dir()` helper blocks as the seam (epics, messages, turns, tool-calls, sprints, checklists, images, feedback, codebases, leases/locks, cloud-runs, control-messages, tickets).
- Reorganize implementations; **keep the assembled `FileStore`/`DBStore` classes' external API identical** (composition/mixins behind the same class name, or a thin assembling class).
- **(Added per gap-hunt) Collapse the `EpicSummary` / `EpicSearchSummary` fork** — two identically-shaped `Epic` subclasses (`snippet`/`rank`/`match_tier`/`backend`) live in `store/base.py:96-100` and `schemas/arnold.py:269-273`; the store protocol uses the `store/base.py` one, the `schemas/arnold.py` one is exported but unused by the store. While reorganizing store models, eliminate the redundant class (or make one re-export the other). Verify the `schemas` copy truly has no live consumers before removing.

## Locked decisions
- **Behavior-preserving only.** No logic, no signature changes beyond import location.
- **Keep ONE `Store` protocol (per review — this is the safe answer).** Splitting into sub-protocols forces signature changes across `multi.py:92-93`'s `Store | None` typing in 19 files — that's behavior-change territory. Do NOT split the protocol; split only the implementations.
- Preserve public import paths via `__init__.py` re-exports; collapse-and-re-export, don't fork new permanent shims.

## Open questions (for plan to resolve)
- Mixin composition vs delegation for the assembled backend class — which keeps the public surface most exactly identical?
- Which deep imports of store internals exist in tests, and do they need re-export shims? (the M0 import-smoke test enumerates these)

## Constraints
- Full suite + M0 import-smoke + extended store-contract test green with no test-body changes beyond import paths.
- No circular imports across the new slice boundaries.

## Done criteria
- `db.py` and `file.py` decomposed into per-entity modules; no new module exceeds ~800 loc.
- The single `Store` protocol is unchanged.
- All prior public import paths resolve (M0 import-smoke green).
- Zero behavior diff — extended store-contract test + goldens pass unchanged.

## Touchpoints
`megaplan/store/{base,db,file,multi}.py` → per-entity modules under `store/`, `tests/contract/store_contract.py` (import paths only).

## Anti-scope
- Do NOT change behavior, fix bugs, or alter error handling (M3*) / parity (M2) — only move code.
- Do NOT rename domain concepts (M4 already did).
- Do NOT split the protocol into sub-protocols.
- **Guardrail:** do NOT touch next-step resolution or the drive engines.
