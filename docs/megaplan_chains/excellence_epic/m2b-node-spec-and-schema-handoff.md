# Sprint 2b — Node-spec cleanup + schema-provider handoff (`partnered/thorough/high +prep @codex`)

Shared context: read `docs/structural_audit_2026-05.md` (j3/j4/j5), `handoff-m1.md`, and `handoff-m2a.md`. Sprint 2a landed the offline consistency gate; this sprint deletes stale generated node-spec code only after the gate proves the post-delete surface is intact, then hands sprint 4b a real schema-provider contract.

## Outcome
Dead node-spec code is removed safely, node-pack catalog access becomes lazy enough to reflect lockfile changes, and `handoff-m2b.md` gives sprint 4b a concrete schema provider/API with coverage evidence instead of vague "schema truth" language.

## Scope (IN)
1. **Resolve the `models.yaml` ↔ `node_packs.py` naming mismatch** using the sprint-2a transitional alias map. Record whether sprint 7 or a follow-up should canonicalize on `CustomNodePack.name` and migrate `models.yaml` keys with a deprecation window.
2. **Make `KNOWN_NODE_PACKS` lazy**: replace the import-time constant (`node_packs.py:420`) with a `functools.cache` function that re-reads the lockfile; update consumers such as `porting/wrapper_discovery.py`, `runtime/session.py`, `node_packs_install.py`, and `commands/schemas.py`.
3. **Delete dead node-spec code** after the sprint-2a gate passes on the current tree:
   - `vibecomfy/nodes/comfyui_kjnodes.py`
   - `vibecomfy/nodes/comfyui_ltxvideo.py`
   - `vibecomfy/nodes/rgthree_comfy.py`
   Update or remove `scripts/demo_wrapper_codegen.py`.
4. **Add stale-file cleanup to `tools/generate_node_shims.py`** so regenerating prunes removed packs.
5. **Handle node-spec degraded runtime checks**: if no ComfyUI-capable CI or scheduled lane exists, `handoff-m2b.md` must record a concrete high-severity follow-up with proposed owner/workstream, target sprint/date, and the exact manual command an operator can run before releases.
6. **Define the schema-provider handoff for sprint 4b**: identify the canonical provider/API `classify_node()` may rely on, including source, extraction command, degraded/off-machine behavior, ready-template class-type coverage percentage, committed sample artifact if available, and known coverage gaps.
7. **Create `handoff-m2b.md`** with deleted files, updated consumers, generator behavior, node-spec validation status, schema-provider contract, and deferred risks.

## Locked decisions
- Dead node-spec code is deleted only after `vibecomfy check --json` passes on the current tree.
- Deletion sequence: build/pass gate on current tree; delete stale files; observe/fix resulting gate failures; update generator/data until gate passes again.
- Deleted node-spec modules must have no surviving imports or direct references in Python files.
- If schema-provider coverage is weak, sprint 4b must treat that as a blocker or explicit escalation rather than silently falling back to heuristics.
- Staged-file hash verification, symlink checks, and full asset-manifest freshness enforcement remain follow-up work unless already cheap after sprint 2a.

## Prep deliverables
- `prep-m2b.md` records the stale-file reference graph, consumers of `KNOWN_NODE_PACKS`, and candidate schema-provider sources.
- Decide the fate of `scripts/demo_wrapper_codegen.py`: keep only if rewritten to avoid deleted-pack references; otherwise remove it with the stale node-spec files.

## Constraints
- Sprint-1 differential harness and sprint-2a consistency gate must remain green.
- Off-machine degraded node-spec status is allowed only with the concrete release-validation follow-up described above.
- No classification-site routing; sprint 4b owns `classify_node()`.

## Done criteria
- `KNOWN_NODE_PACKS` is lazy and consumers are updated.
- Dead node-spec modules are removed; generator stale-file cleanup is tested.
- `rg "comfyui_kjnodes|comfyui_ltxvideo|rgthree_comfy" --type py` returns zero in non-deleted Python files.
- `scripts/demo_wrapper_codegen.py` is updated or removed.
- `vibecomfy check --json` and the sprint-1 differential harness pass after deletion.
- `handoff-m2b.md` identifies the schema provider with source, extraction command, ready-template coverage percentage, degraded behavior, sample artifact status, and gaps.

## Touchpoints
`vibecomfy/node_packs.py`, `vibecomfy/node_packs_install.py`, `vibecomfy/porting/wrapper_discovery.py`, `vibecomfy/runtime/session.py`, `vibecomfy/commands/schemas.py`, `vibecomfy/nodes/comfyui_*.py`, `tools/generate_node_shims.py`, `scripts/demo_wrapper_codegen.py`, `docs/megaplan_chains/excellence_epic/`.

## Anti-scope
Do NOT build the node-classification seam. Do NOT change plugin/ready collision behavior. Do NOT perform broad model-file staging validation unless it is already supported by sprint 2a's metadata gate.
