# Sprint 4a — De-duplicate shared helpers (`directed/full/medium @codex`)

Shared context: read `docs/structural_audit_2026-05.md` (j6 cross-tree duplication), `handoff-m2b.md`, and `handoff-m3.md`. The safety net, consistency gate, and IR import contract are already in place. Sprint 4b owns schema-driven node classification.

## Outcome
Known cross-package duplicate helpers are consolidated to single sources of truth without changing behavior.

## Scope (IN)
1. **Consolidate graph/format clone clusters**:
   - one topological sort in `_graph_utils.py`, parameterized by dep-extractor callable, sort-key callable, and cycle-strategy enum, replacing copies in `porting/naming.py`, `emitter.py`, `testing/dry_run.py`, and `analysis/graph.py`;
   - one `is_api_link` in `_graph_utils.py`, replacing copies across emitter/parity/analysis/testing paths;
   - shared `CURATED_SCHEMA_DEFAULTS` in `vibecomfy/porting/_schema_defaults.py`;
   - one `vibecomfy/paths.py` for `REPO_ROOT`/`READY_ROOT`;
   - one `GENERATED_HEADER` and a shared `SubgraphFreshnessError` action constant.
2. **Backport emitter variable naming** into `porting/naming.py`: `_safe_var`, `_connection_role_name`, and `_compute_variable_names` become the shared implementation.
3. **Prove the seven j6 clone clusters are gone** with the lightest focused check that works. A small `tools/detect_clones.py --clusters m4 --format json` is acceptable if scoped only to known clusters; a threshold-tuned general detector is not required.
4. **Create `handoff-m4a.md`** recording consolidated helpers, moved imports, clone-check output or equivalent proof, and any helper sites intentionally deferred to sprint 4b/5.

## Locked decisions
- `_graph_utils.py` owns graph/format utilities.
- `vibecomfy/porting/_schema_defaults.py` owns curated schema defaults.
- `vibecomfy/paths.py` owns repo/path constants.
- Clone verification is locked to the seven known j6 clusters, not a general clone-discovery effort.
- Sprint 5 must rerun this sprint's clone check after decomposition to prove helpers were not forked again.

## Prep deliverables
- `prep-m4a.md` maps each j6 cluster to the target owner and the tests that currently exercise divergent call sites.

## Constraints
- Differential harness, snapshots, sprint-2a/2b gates, and sprint-3 import-linter contract stay green.
- No behavior changes beyond import/source consolidation.
- No schema-driven classification work; sprint 4b owns it.

## Done criteria
- Seven j6 clone clusters are consolidated to single sources of truth.
- Focused clone check reports `"status": "clean"` or `handoff-m4a.md` records equivalent structural proof.
- Existing tests for affected call sites pass.
- Sprint-1 differential harness, sprint-2a/2b gates, and sprint-3 import-linter contract pass.
- `handoff-m4a.md` satisfies the shared handoff contract.

## Touchpoints
`vibecomfy/_graph_utils.py`, `vibecomfy/paths.py`, `vibecomfy/porting/_schema_defaults.py`, `vibecomfy/porting/naming.py`, `vibecomfy/porting/emitter.py`, `vibecomfy/porting/parity.py`, `vibecomfy/testing/*`, `vibecomfy/analysis/graph.py`, optional `tools/detect_clones.py`.

## Anti-scope
Do NOT introduce `classify_node()` or route substring-detection sites. Do NOT split god modules beyond the minimal imports needed for consolidation; sprint 5 owns decomposition.
