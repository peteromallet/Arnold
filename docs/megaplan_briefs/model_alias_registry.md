vibecomfy: model-alias-registry v1 — collapse the four duplicated `materialize_model` heredoc blocks in `runpod_corpus_matrix.py` and the inline name-normalization rules in `runpod_matrix_remote.py` into one declarative YAML registry. No resolver service, no runtime indirection. Just a flat file that staging and normalization both read from.

Source repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

# Problem

Model staging and aliasing knowledge is currently spread across:

1. **Four near-identical heredoc Python blocks** in `scripts/runpod_corpus_matrix.py` (lines ~380, ~447, ~521, ~647) that each define a local `materialize_model(repo, filename, targets, min_size)` function and a hardcoded `downloads = [...]` list. Adding a new model means editing all four (or remembering which one applies). Drift is inevitable.

2. **Inline name-normalization rules** in `scripts/runpod_matrix_remote.py` (lines ~143–195) that hardcode "if value is `ltx-2.3-22b-dev.safetensors` map it to X" branching — one branch per known alias. Adding a new model that ships under multiple node-pack names means appending another `elif` branch.

3. **Module-level constants** at the top of `scripts/runpod_matrix_remote.py` (lines 12–19) — `LTX_CHECKPOINT`, `LTX_TEXT_ENCODER`, etc. — that pin canonical names per model. These are referenced from the normalization branches.

4. **Workflow-embedded URLs** that the materializer already extracts via `vibecomfy/model_assets.py` (this work is done; do not redo it). But the *staging* path on RunPod still doesn't read from those — it uses the hardcoded heredoc lists instead.

The result: a "downloaded but invisible" failure class (entry `model_layout` in `docs/hiddenswitch_incompatibilities.md`) where a model is correctly downloaded but lives at the wrong path for the node pack that needs it. Each new node pack adds another inline branch instead of declaring its expected paths once.

# Goal

One YAML file that staging and normalization both consume. Five mechanical steps:

1. Define a YAML schema: canonical model id → source (HF repo + filename or generic URL) → list of `(node_pack, target_path)` pairs that should be created via hardlink/symlink → minimum size for sanity check → optional list of accepted alias names that should be normalized to the canonical filename.
2. Author the registry by extracting the existing four `downloads = [...]` lists and the existing alias branches from the two scripts. Verify exhaustively against current matrix behavior.
3. Replace the four heredoc `materialize_model` blocks in `runpod_corpus_matrix.py` with a single loader that reads the YAML and runs the same `hardlink-or-symlink, size-check, fail-loud` logic.
4. Replace the alias-normalization branches in `runpod_matrix_remote.py` with a single lookup against the YAML's `aliases` field.
5. Add a one-shot `vibecomfy models stage <registry.yaml>` CLI command that any local dev box (not just RunPod) can use to materialize the registry into a target models root.

The registry is **append-only and flat**. No resolver service. No background daemon. No precedence rules across multiple registries. One file, in repo, edited via PR.

# Verified facts (do not re-research)

- `scripts/runpod_corpus_matrix.py` contains the four heredoc blocks: lines 380, 447, 521, 647. Each defines `materialize_model(repo, filename, targets, min_size)` with the same body (hardlink-or-symlink fallback, size check) and a different `downloads = [...]` list scoped to a different matrix phase.
- `scripts/runpod_corpus_matrix.py:67` already pip-installs `huggingface_hub[hf_xet]>=0.32.0`, so `hf_hub_download` is available.
- `scripts/runpod_matrix_remote.py:12-19` declares the LTX/Flux module constants. Lines 143–195 contain the cascade of `if value == "X": inputs[key] = "Y"` normalization branches (LTX-specific). Lines 376–379 contain Wan-specific equivalents.
- `vibecomfy/model_assets.py` already extracts `(name, subdir, url)` triples from upstream Comfy-Org workflow JSONs. Those triples populate `READY_REQUIREMENTS["models"]` in materialized scratchpads. The registry should *complement* that mechanism, not replace it: the registry covers models whose canonical staging path differs across node packs (LTX, Wan, ACE Step), while the model-assets path covers the simple "URL embedded in the workflow" case.
- `vibecomfy/fetch.py` already exists with `download_many` and atomic-rename semantics. The registry CLI should reuse `vibecomfy.fetch` for non-HF URLs and `huggingface_hub.hf_hub_download` for HF entries (matching the heredoc behavior).
- The doc entry `Model name and directory conventions differ across node packs` in `docs/hiddenswitch_incompatibilities.md` (Root cause: `model_layout`) is the spec for what this registry exists to solve.

# Steps

## S1: YAML schema

Single file at `vibecomfy/registry/models.yaml` (or `data/models.yaml` — pick one and document). Schema per entry:

```yaml
- id: ltx_2_3_22b_dev_fp8                   # canonical id, used for cross-references
  source:
    kind: huggingface                        # or "url"
    repo: Lightricks/LTX-Video               # for kind=huggingface
    filename: ltx-2.3-22b-dev-fp8.safetensors
    # url: https://...                        # for kind=url (uses vibecomfy.fetch)
  min_size: 1_000_000_000                    # bytes, fail loud if smaller
  targets:                                    # paths to materialize via hardlink-or-symlink
    - node_pack: lightricks
      path: models/diffusion_models/ltx-2.3-22b-dev-fp8.safetensors
    - node_pack: kjnodes
      path: models/checkpoints/ltx-2.3-22b-dev-fp8.safetensors
  aliases:                                    # accepted names that normalize to canonical
    - ltx-2.3-22b-dev.safetensors
    - LTX23_22B_dev.safetensors
  notes: |
    Multi-pack model. Lightricks expects diffusion_models/, KJNodes expects checkpoints/.
```

The schema must be expressive enough to reproduce every download in the four existing heredoc blocks AND every alias branch in `runpod_matrix_remote.py`. If any current behavior cannot be expressed, the schema is wrong — extend it before proceeding.

## S2: Author the registry

- Read all four `downloads = [...]` lists in `runpod_corpus_matrix.py`. Convert each to a registry entry. Preserve `min_size` exactly.
- Read every alias branch in `runpod_matrix_remote.py` (the `if value == X: inputs[key] = Y` and `value in {A, B}: ...` blocks). Convert each to an `aliases:` list under the canonical entry.
- Read the module-level constants (`LTX_CHECKPOINT`, etc.) and confirm each maps to a registry entry's `id`.
- The registry must be **complete enough** that S3 and S4 can be dropped in without behavioral change. If the registry is incomplete, S3/S4 will silently break workflows.

## S3: Replace heredoc blocks in runpod_corpus_matrix.py

- Add a small loader: `vibecomfy/registry/models_loader.py`. Functions:
  - `load_registry(path: str | Path) -> list[ModelEntry]`
  - `stage_entry(entry: ModelEntry, *, models_root: Path) -> list[Path]` — hardlink-or-symlink into every `targets[].path` under `models_root`, run size check, raise on mismatch. Pure mirror of the existing heredoc behavior.
  - `stage_many(entries: list[ModelEntry], *, models_root: Path, ids: list[str] | None = None) -> None` — stage all (or a subset by id).
- In `runpod_corpus_matrix.py`, replace each of the four heredoc blocks with a single call:
  ```python
  $PY -m vibecomfy.registry.models_loader stage \
      --registry vibecomfy/registry/models.yaml \
      --models-root models \
      --ids ltx_2_3_22b_dev_fp8 ltx_2_3_text_encoder ...
  ```
  Each phase passes the subset of ids it needs. The four phases stay distinct (different model subsets) but share the loader.

## S4: Replace alias normalization in runpod_matrix_remote.py

- Add a function in `vibecomfy/registry/models_loader.py`: `normalize_alias(value: str, *, registry: list[ModelEntry], node_pack: str | None = None) -> str | None` — returns the canonical filename if `value` matches any entry's `aliases` (optionally constrained by node_pack), else None.
- In `runpod_matrix_remote.py`, replace the cascade of `if value == X: inputs[key] = Y` branches with one call to `normalize_alias`. If it returns a value, use it; otherwise leave the input untouched (current behavior preserves unknown values).
- The module constants (`LTX_CHECKPOINT`, etc.) become thin wrappers that look up the canonical filename by id from the registry. Keep them for source-code readability; they no longer carry the source of truth.

## S5: vibecomfy models stage CLI

- New file `vibecomfy/commands/models.py` exposing `vibecomfy models stage <registry.yaml> [--ids id1 id2 ...] [--models-root PATH] [--dry-run]`.
- Reuses `vibecomfy.registry.models_loader.stage_many`.
- For HF entries, use `huggingface_hub.hf_hub_download` (matching heredoc behavior — falls back to authentication via `HF_TOKEN` env var if set).
- For URL entries, use `vibecomfy.fetch.download` (already exists).
- `--dry-run` prints what would be staged and where, with size checks against any already-present files.
- Register in `vibecomfy/cli.py`.

# Out of scope (do NOT add)

- A resolver service. No HTTP API, no background process, no caching layer beyond what `huggingface_hub` already provides.
- Auto-detection of node packs from installed Python packages.
- SHA256 verification (`vibecomfy/.megaplan-idea.md` already defers this to a follow-up; same applies here).
- A "models doctor" that gates execution. Doctor work is deferred per the `hiddenswitch_incompatibilities.md` decision; the registry is consumed by staging only, not by submit-gating.
- Multi-registry composition (overlay registries, project-local overrides). One file.
- Migration of `vibecomfy/model_assets.py` extraction logic — that path stays as-is for workflow-embedded URLs.
- A web UI / inspector.

# Design constraints

- **Flat file**: a single YAML, source-of-truth for all model staging/aliasing. Append-only in normal operation; edits go through PRs.
- **No new top-level deps**: `pyyaml` is in the matrix's pip install line; confirm it's also in `pyproject.toml`. If not, add it (it's tiny).
- **Reversibility**: keep the heredoc blocks behind a `--legacy-staging` flag for one release cycle in case the registry has a gap that needs an emergency revert. Remove after one passing matrix run.
- **Behavioral parity**: every download and alias the matrix currently handles must be representable. The registry is wrong if it cannot reproduce the current behavior bit-for-bit.
- **Loud failure**: if a registry entry is referenced by id but missing, fail at load time, not at stage time. If a target path collides with an unrelated existing file (not a symlink/hardlink we own), fail rather than overwriting.
- **Doc cross-reference**: when adding a new entry to the registry, the PR description must reference the `model_layout` row in `hiddenswitch_incompatibilities.md` (per the Contributing rules in that doc) if the addition was driven by a documented incompatibility.

# No prereq clauses

This brief has no hard-halt prereqs. Independent of the validator brief (#1), the watchdog/override/fixture subagents (#2/#3/#4), and the doc-discipline work (#6, already shipped). Ship as soon as ready.

# Validation evidence to produce

- A full RunPod matrix run completes with the registry-driven staging, producing the same set of staged files as the previous heredoc behavior. Diff `find models -type f` before/after. Zero diff is the bar.
- The 14 existing runtime-green workflows still go green.
- A new fictional workflow that uses the same model under a third node-pack name can be supported by appending one `aliases:` line and one `targets:` entry to the registry — no code changes elsewhere.
- Unit tests in `tests/test_models_registry.py`: load+roundtrip a sample registry, stage with mocked `hf_hub_download`, normalize aliases (hits and misses), reject collisions with non-owned files.

# Open questions

- Should the registry live at `vibecomfy/registry/models.yaml` (next to the loader) or `data/models.yaml` (a top-level data dir)? Lean toward `vibecomfy/registry/models.yaml` for proximity to the loader; revisit if other registries appear.
- Should `normalize_alias` be node-pack-aware (i.e., scope which alias maps activate based on the workflow's source family)? V1: no — global alias namespace. Revisit if two node packs ship the same alias pointing to different canonical models, which would require disambiguation.
- Should the loader cache the parsed registry in-memory across calls within a single process? Yes — parse once per process, stash on a module-level singleton or pass through explicitly. Avoid re-parsing per stage call.
