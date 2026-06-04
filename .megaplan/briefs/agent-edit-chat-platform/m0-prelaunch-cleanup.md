# M0 — Pre-launch cleanup (test-support leak)

The first chain milestone: leave `main` clean so M1 builds on a sound base.

## Outcome
No production module imports from `tests/`. The test-support normalizer that
production currently depends on is moved into production code, with tests importing
it from the new location. Reviewer checks: `grep -rn "import tests" vibecomfy/`
returns nothing; full suite green.

## Scope — IN
1. **Move `tests.support.agent_edit_normalize` into production.** Production
   `guard_full_ui` imports it at `edit_apply.py:426`. Relocate the module into a
   production package (e.g. `vibecomfy/porting/` or `vibecomfy/comfy_nodes/`), update
   the production import, and repoint the tests to import it from the new production
   home (tests import production, never the reverse).
2. Keep behavior identical — this is a pure relocation, no logic change.

## Locked decisions
- Production code must not import from `tests/`.
- Pure move; the normalizer's behavior is unchanged.

## Constraints
- `pytest tests/test_comfy_nodes_agent_*.py` and the broader suite stay green
  (modulo the 2 known baseline failures); browser smoke green.

## Done criteria
- No `import tests` (or `from tests`) anywhere under `vibecomfy/`.
- The normalizer lives in a production module; tests import it from there.
- Suite + browser smoke green.

## Touchpoints
- `vibecomfy/comfy_nodes/edit_apply.py:426`, `tests/support/agent_edit_normalize.py`,
  the new production home, and the test imports.

## Anti-scope
- Don't change the normalizer's behavior, the apply engine, gates, or anything else.
  Relocation only.

## Note
Assumes the two live-verified UI fixes (clarify-as-question + redundant post-apply
repaint) are already committed to `main` as the manual pre-req before the chain.

## Sizing
Small but import-topology-sensitive (a module relocation that reshapes the import
graph) — `directed/full` @codex: premium PLANNER (the topological-risk rule applies
to relocations even when behavior-preserving), DeepSeek executes the mechanical move.
