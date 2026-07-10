# M2 — Shared Foundation Layer (AST / graph / link utilities)

## Outcome
One canonical home for the small utility functions that are currently copy-pasted
across the codebase, with every duplicate replaced by an import from it. This is the
**kernel** the rest of the epic builds on: it removes the root-cause duplication that
independent audit agents kept rediscovering, and it shrinks the god-files before M3–M5
carve them up.

## Why this tier (apex)
Every downstream milestone touches code that currently embeds copies of these helpers.
Getting the canonical signatures and semantics right here prevents re-introducing
divergence later. A wrong call here propagates into M3/M4/M5.

## Input
`docs/megaplan_chains/pristine_cleanup/artifacts/m1-duplication-inventory.md` (produced
by M1) is the authoritative list of duplicates and how they diverge.

## Scope
1. **Create a shared util module/package** (propose: `vibecomfy/_ast_utils.py` +
   `vibecomfy/_graph_utils.py`, or a small `vibecomfy/util/` package — pick one and
   justify in the plan). It must not import heavy subpackages, to stay dependency-light.
2. **Consolidate each duplicated helper into ONE canonical implementation:**
   - `_literal_value` — 4 copies (`source_map.py` is gone after M1;
     `porting/readability_inventory.py:190`, `registry/static_contract.py:631`,
     `analysis/fields.py:204`). They diverge on sentinel (`_UNSUPPORTED` vs `None`) and
     container support (`ast.Subscript`/`ast.Call`). The canonical version must be a
     **superset** that satisfies all call sites; verify each caller still passes.
   - `_call_name` / `_ast_call_name` — 3 variants
     (`registry/static_contract.py:898`, `porting/ready.py:241`). The
     `ready.py` variant adds prefix-dotted resolution — preserve that capability.
   - `_is_link` / `is_api_link` — 8 copies across `analysis/graph.py`,
     `ingest/normalize.py`, `porting/emitter.py`, `porting/parity.py`,
     `schema/call_validation.py`, and three in `vibecomfy/testing/`. Reconcile the
     `is_api_link` variant (`testing/_helpers.py:56`) — decide if it is the same check.
   - `_sort_key` (`porting/widget_aliases.py:473`, `porting/workbench.py:920`),
     `_git_head` (`commands/doctor.py`, `commands/nodes.py`),
     `UI_ONLY_CLASS_TYPES` (`porting/emitter.py:122`, `porting/helpers.py:7`),
     and the `OPAQUE_COMPONENT_CLASS_RE` regexes (`porting/workbench.py:41`,
     `porting/strict_ready.py:27` — note the mixed-case vs `re.IGNORECASE` divergence).
3. **Replace all call sites** with imports from the canonical home. Remove the local
   copies.
4. **Produce a migration map artifact**
   (`docs/audits/m2-symbol-map.md`): `old symbol @ old location → new home`, so M3–M5
   know where shared helpers now live.

## Locked decisions
- **Behavior-preserving.** This is a pure refactor. No functional change to emitter
  output, validation results, or graph analysis. The M1 green baseline is the gate.
- Canonical implementations must be **supersets** where copies diverged — never drop a
  capability a caller relied on. Where divergence was a latent bug (e.g. a regex that
  failed to match mixed-case), call it out explicitly in the plan and fix deliberately.

## Done criteria
- Each listed helper has exactly one definition; `grep` confirms no remaining copies.
- Full `pytest` green (same baseline as M1).
- No change to emitter snapshot/parity tests, validation reports, or analyze output.
- `docs/audits/m2-symbol-map.md` exists and is accurate.

## Touchpoints
`vibecomfy/porting/{readability_inventory,static_contract... }` (note: static_contract is
under `registry/`), `vibecomfy/registry/static_contract.py`, `vibecomfy/analysis/{fields,graph}.py`,
`vibecomfy/ingest/normalize.py`, `vibecomfy/porting/{emitter,parity,ready,widget_aliases,workbench,strict_ready,helpers}.py`,
`vibecomfy/schema/call_validation.py`, `vibecomfy/commands/{doctor,nodes}.py`,
`vibecomfy/testing/{_helpers,dry_run,canonical,snapshot}.py`.

## Anti-scope
Do not consolidate the validation modules (M3), the eval modules (M4), or split the
god-files (M5). Only extract and de-duplicate the small shared helpers. Do not change
public API names. Do not edit docs.
