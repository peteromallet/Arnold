# Sprint 2a — Offline consistency gate (`partnered/full/medium @codex`)

Shared context: read `docs/structural_audit_2026-05.md` (esp. Part 2 drift findings j3/j4/j5). Sprint 1 has landed the differential harness + armed parity gate. This sprint builds the offline repo consistency surface only; deletion of stale node-spec code and schema-provider handoff move to sprint 2b.

## Outcome
A single offline `vibecomfy check` command + CI gate makes drift immediately detectable across core hand-maintained data surfaces: `coverage.json` ↔ disk, `models.yaml` node-pack references, source/index freshness, and model-asset integrity metadata.

## Scope (IN)
1. **Generalize `tools/refresh_template_index.py --check`** into a repo-scoped command: `vibecomfy check` in `vibecomfy/commands/check.py`, registered explicitly in `vibecomfy/commands/__init__.py`. `doctor` remains workflow-scoped.
2. **Support `vibecomfy check [--json] [--subset coverage|models|assets|sources|node-specs]`**. A single subset per invocation is enough; comma-separated multi-subsets are optional only if cheap.
3. **Coverage checks**:
   - every `coverage.json` `path` exists on disk;
   - every `ready_templates/*.py` has a coverage row;
   - every string `ready_template` value resolves to a real file;
   - every `external_workflow_index.json` entry has a coverage row.
4. **Model/node-pack checks**: every `models.yaml` `target.node_pack` matches a known `CustomNodePack.name`, with an explicit transitional alias allowlist for legacy short names like `comfy_core`.
5. **Model-asset metadata checks**: non-gated download URLs require `sha256` unless an exception includes owner/reason; gated entries must be explicitly marked gated/token-required. Verify the model-fetch token path (`HF_TOKEN` / gated downloads) is syntactically valid and record findings in `handoff-m2a.md`.
6. **Source/index freshness**: add a `--check` flag to `sources sync` following the `refresh_template_index` pattern.
7. **Stable JSON result contract**: top-level `status`, per-subset records, machine-readable `code`, human `message`, optional `next_action`. Downstream runtime preflight consumes this contract instead of scraping text.
8. **Add missing data rows** for the 6 orphan ready templates and uncovered external workflow:
   - `smoke/empty_image_red`
   - `video/wan22_i2v_comfy_lightx2v`
   - the 3 `ltx2_3` first/last variants
   - `video/wanvideo_wrapper_22_wan_animate_preprocess_kijai`
   - `IAMCCS_LTX_2.3_T_I2V_LOW_VRAM`
9. **Wire the gate into CI** with `.github/workflows/consistency.yml` running `python -m vibecomfy.cli check --json` in normal off-machine mode. Add a lightweight pre-commit hook only if it stays fast.
10. **Create `handoff-m2a.md`**, recording exact commands, CI job name, reproduced drift examples, alias decisions, model-asset integrity exceptions, and what sprint 2b must consume.

## Locked decisions
- The consistency command lives at `vibecomfy check`, not under `doctor`, because it is repo-scoped and cross-artifact.
- Clone the `template_index.json --check` pattern; it is the repo's best existing guarded-artifact convention.
- The gate must fail CI on any base violation class and explicitly report `status: "degraded"` for off-machine node-spec checks rather than silently passing.
- Prefer a non-destructive alias layer over renaming `models.yaml`; the alias map is transitional and must be revisited by sprint 7 or a follow-up.
- Keep implementation straightforward. The stable JSON contract is the extension surface for later `imports`, `clones`, and `collisions` subsets.
- This gate makes drift immediately detectable; it does not claim to make hand-maintained data drift impossible.

## Prep deliverables
- `prep-m2a.md` records the current drift baseline and at least one reproduced violation per major subset available offline (`coverage`, `models`, `sources`, `assets`).
- Decide `asset_manifest.json` status by evidence: record whether it is machine-written or hand-maintained. Lifecycle decisions and freshness enforcement are deferred unless a deterministic writer already exists.

## Constraints
- Runs offline by default.
- Continues to run the sprint-1 differential harness before merge.
- No deletion of stale node-spec modules in this sprint; sprint 2b owns that.
- No substring classification refactor; sprint 4b owns that.

## Done criteria
- `vibecomfy check --json` exists and passes after required data fixes.
- Tests introduce each offline drift class and assert the gate fails.
- Model integrity checks cover missing-hash and gated-marker cases.
- `asset_manifest.json` status is recorded in `handoff-m2a.md`; lifecycle enforcement is deferred unless already trivial.
- CI runs the consistency gate and reports degraded node-spec status explicitly.
- `handoff-m2a.md` satisfies the shared handoff contract and names sprint-2b prerequisites.

## Touchpoints
`tools/refresh_template_index.py`, new `vibecomfy/commands/check.py`, `vibecomfy/commands/__init__.py`, `ready_templates/sources/manifests/coverage.json`, `vibecomfy/registry/models_loader.py`, `vibecomfy/registry/models.yaml`, `asset_manifest.json`, `vibecomfy/model_assets.py`, `vibecomfy/node_packs.py`, `vibecomfy/commands/sources.py`, `.github/workflows/consistency.yml`, `.pre-commit-config.yaml`.

## Anti-scope
Do NOT delete stale node-spec files. Do NOT define the schema-provider handoff for classification beyond noting current degraded/off-machine behavior. Do NOT change registry collision behavior.
