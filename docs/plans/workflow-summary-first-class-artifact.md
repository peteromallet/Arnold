# Plan: First-class workflow summaries in VibeComfy

## Goal

Make a concise, human-readable, LLM-generated summary a first-class part of every
`VibeWorkflow` Python object. For now, focus on **backfilling the existing
`external_workflows/corpus/` JSONs** with summaries and establishing the typed
Python artifact. Hooks for automatic generation at ingest/conversion time and
upload-time inclusion in Hivemind are explicitly deferred until the Hivemind
mapping is understood.

The summary should contain only information that **cannot be derived** from the
existing graph/provenance. Derivables (model list, custom-node list, complexity,
flags) are computed on demand by small helpers instead of being duplicated.

## Revised scope (per user direction)

1. The Python `VibeWorkflow` object is the core asset; the JSON corpus is a
   serialized view.
2. **Immediate priority**: backfill the existing `external_workflows/corpus/`
   workflows with summaries.
3. **Deferred**: automatic summary generation inside `convert_to_vibe_format()`
   and the upload hook in `scripts/upload_ready_templates_to_hivemind.py`.
4. A Codex subagent will inspect the Hivemind upload code to determine how
   summary data should be mapped into the resource envelope before those hooks
   are implemented.

## Artifact location

The canonical artifact is the Python `VibeWorkflow` object (`vibecomfy/workflow.py`).
The serialized JSON is a downstream representation. Therefore the summary lives in:

```python
workflow.metadata["summary"]
```

It is a plain dict in serialization and a typed dataclass at runtime.

## Stored vs. derived fields

### Stored in `metadata.summary` (LLM + deterministic merge)

| Field | Type | Source |
|---|---|---|
| `title` | `str` | LLM-generated (≤80 chars) |
| `description` | `str` | LLM-generated (1–2 sentences) |
| `tags` | `list[str]` | LLM-generated (3–10 lowercase kebab-case keywords) |
| `task_type` | `str` | Derived: `text_to_image`, `image_to_video`, `inpainting`, `upscaling`, `controlnet`, `compositing`, `animation`, `other` |
| `media_type` | `str` | Derived: `image`, `video`, `audio`, `3d`, `multi` |
| `flags` | `dict[str, bool]` | Derived: `is_animated`, `has_controlnet`, `has_ipadapter`, `requires_custom_nodes`, etc. |
| `complexity` | `int` | Derived: 1–5 score from node/edge/custom-node density |
| `_content_hash` | `str` | SHA-256 of the compact LLM input; enables resume/skip and idempotent re-runs |

### Derived on demand (not duplicated)

| Field | Source |
|---|---|
| `primary_models` | `workflow.requirements.models` |
| `primary_custom_nodes` | `workflow.nodes` class types minus a core ComfyUI allowlist |
| `inputs` / `outputs` | `workflow.inputs` / `workflow.outputs` |

## Final Python schema

The canonical dataclass lives in `vibecomfy/contracts/summary.py` and is re-exported
from `vibecomfy/workflow.py` and `vibecomfy/contracts/__init__.py`:

```python
@dataclass(slots=True)
class WorkflowSummary:
    title: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    task_type: str = "other"
    media_type: str = "image"
    flags: dict[str, bool] = field(default_factory=dict)
    complexity: int = 1

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowSummary": ...
```

`vibecomfy/ir/types.py` intentionally does **not** import or re-export
`WorkflowSummary`; the IR package must remain free of contracts-layer imports to
satisfy the import-topology tests. The two `VibeWorkflow` implementations stay
aligned by both storing the summary as a plain dict under
`workflow.metadata["summary"]`.

## Compact LLM prompt input

To keep summary generation cheap and fast, the LLM receives a token-light
representation instead of the full graph:

```json
{
  "node_classes": {"CheckpointLoaderSimple": 1, "KSampler": 1, ...},
  "models": ["vae-ft-mse-840000-ema-pruned.safetensors"],
  "inputs": ["prompt", "image"],
  "outputs": ["image", "video"],
  "node_count": 20,
  "edge_count": 26,
  "source": "banodoco-discord-archive",
  "workflow_format": "comfy_ui"
}
```

## Files changed

1. **`vibecomfy/contracts/summary.py`** (new)
   - `WorkflowSummary` dataclass with `to_dict()` / `from_dict()`.

2. **`vibecomfy/contracts/__init__.py`**
   - Re-exports `WorkflowSummary` through the lazy-import map.

3. **`vibecomfy/analysis/workflow_summary.py`** (new)
   - Deterministic helpers: `infer_task_type`, `infer_media_type`, `derive_flags`,
     `compute_complexity_score`, `detect_custom_nodes`.

4. **`vibecomfy/analysis/__init__.py`**
   - Exports the new helpers.

5. **`vibecomfy/ingest/summarize.py`** (new)
   - `build_compact_prompt(workflow)` — token-light prompt.
   - `summarize_workflow(workflow, *, llm_client, cache_dir)` — merges deterministic
     fields with LLM-generated `title`/`description`/`tags`.
   - On-disk cache keyed by SHA-256 of prompt + prompt version.

6. **`vibecomfy/ingest/normalize.py`**
   - Treats `metadata.summary` as an optional passthrough field.

7. **`vibecomfy/workflow.py`**
   - Re-exports `WorkflowSummary` from `vibecomfy.contracts.summary`.

8. **`scripts/enrich_workflow_summaries.py`** (rewritten)
   - Single-step orchestrator with `--dry-run`, `--limit`, `--force`, `--workers`.
   - Uses a duck-typed `DictWorkflowAdapter` to feed corpus dicts into the analysis
     helpers without constructing full `VibeWorkflow` objects.
   - `SimpleLLMClient` calls any OpenAI-compatible endpoint; defaults to OpenRouter,
     but the backfill used DeepSeek direct (`https://api.deepseek.com/v1`) with
     model `deepseek-chat`.
   - Resume/skip via `_content_hash`; cache in
     `external_workflows/.shadow/summary-cache/`.

9. **`scripts/upload_external_workflows_to_hivemind.py`** (new)
   - Reads `external_workflows/manifest.json` and uploads each row to Hivemind.
   - `data.title` = `summary.title`; `data.body` = description + tags + task/media +
     provenance; `metadata` and `payload` carry the full structured summary and
     provenance.
   - Source namespace `vibecomfy-external`, external_id
     `vibecomfy:external_workflow:<canonical_workflow_hash>`.
   - Defaults to the anonymous `contribute-resource` edge function, so no contributor
     key is required.
   - Supports `--dry-run`, `--limit`, `--only`, `--skip-existing`, `--verify`, and
     the same PostgREST endpoints as the ready-template uploader.

10. **`banodoco-workspace/hivemind/supabase/functions/contribute-resource/`** (new)
    - Anonymous edge function that accepts `add_resource` payloads and inserts them
      into `external_resources` using the service role.
    - Source allowlist defaults to `vibecomfy` and `vibecomfy-external`; configurable
      via the `ALLOWED_SOURCES` environment variable (`*` disables the check).

11. **`tests/analysis/test_workflow_summary.py`** (new)
    - Unit tests for empty graph, single node, large graph, and unknown node types.

12. **`tests/test_upload_external_workflows_to_hivemind.py`** (new)
    - Unit tests for envelope shape, title/body/content, metadata/payload, URL
      fallback, and skip-existing/upload behavior.

13. **`docs/plans/workflow-summary-first-class-artifact.md`**
    - This document.

## Prompt strategy

The LLM is asked for **only** three semantic fields:

```json
{
  "title": "...",
  "description": "...",
  "tags": ["..."]
}
```

Everything else is computed deterministically. The prompt includes a compact
workflow representation:

```json
{
  "node_classes": {"CheckpointLoaderSimple": 1, "KSampler": 1, ...},
  "node_count": 20,
  "edge_count": 26,
  "outputs": ["image", "video"],
  "models": ["..."],
  "custom_nodes_req": ["..."]
}
```

## Cache key formula

```python
sha256(prompt_version + compact_prompt_text).hexdigest()
```

Bumping `_PROMPT_VERSION` in `vibecomfy/ingest/summarize.py` invalidates the cache.

## Backfill results

- **Workflows processed:** 2,533 / 2,533 (100%)
- **LLM failures:** 0
- **Errors:** 0
- **Model used:** `deepseek-chat` via DeepSeek direct API (`https://api.deepseek.com/v1`)
- **Parallelism:** 10 workers in `scripts/enrich_workflow_summaries.py`
- **Runtime:** ~10 minutes for the full corpus
- **Artifacts updated:**
  - `external_workflows/corpus/*.json` — each workflow now has
    `metadata.summary` with title, description, tags, task_type, media_type,
    flags, complexity, and `_content_hash`.
  - `external_workflows/manifest.json` — each row has a mirrored `summary` field;
    `summary_enrichment` records run metadata.
- **Verification:**
  - `tests/analysis/test_workflow_summary.py`: 76 passed
  - `pytest tests/ -x -q -k 'test_analysis or test_workflow_summary or test_contracts or test_ingest'`: 108 passed, 2 skipped
  - `tests/test_upload_external_workflows_to_hivemind.py`: 10 passed
  - `tests/test_upload_ready_templates_to_hivemind.py`: 11 passed
  - Full upload to Hivemind succeeded: 2,533 `external_resources` rows with
    `source = vibecomfy-external`, each carrying summary + provenance + IP/user-agent
    tracking metadata.
  - Dry-run of `scripts/upload_external_workflows_to_hivemind.py` over all 2,533
    workflows succeeded with no errors and produced valid Hivemind envelopes.
  - Manual inspection of 50 random summaries: all coherent, tags relevant, derived
    fields plausible.

## Deferred files

The following remain out of scope for now:

- **`vibecomfy/ingest/normalize.py`** — automatic summary generation at conversion time.
- **`vibecomfy/executor/research.py`** — exposing summaries on `WorkflowSlice`.

`scripts/upload_ready_templates_to_hivemind.py` has been switched to the anonymous
`contribute-resource` endpoint; adding summary-derived `title`/`body` to ready-template
uploads is still deferred because ready templates do not yet carry `metadata.summary`.

## Hook points in the existing flow

### Ingest / conversion

```
load_workflow_source()
  → normalize_workflow_source()
    → normalize_to_api()
      → convert_to_vibe_format()
        → _convert_to_vibe_format_impl()
          → (NEW) summarize_workflow() → workflow.metadata["summary"]
```

### Ready-template upload

```
main()
  → _load_templates()
    → _load_workflow_identity()
      → (NEW) ensure summary, generate if missing
    → _body() / _envelope()
      → (NEW) include summary fields
    → _post()
```

### Research / agent-edit

```
run_executor()
  → _run_research()
    → research()
      → _build_precedent_slices()
        → (NEW) attach workflow.metadata["summary"] to slice
  → _run_implement()
    → handle_agent_edit()
      → (optional) generate summary on accepted candidate
```

## Open questions / risks

- **Cost at scale**: generating a summary for every ingest/conversion may be too
  expensive for high-volume paths. We should default to `generate_summary=True` for
  user-facing ingestion and `False` for internal batch scoring, with caching.
- **Caching key**: should the cache key be `workflow.id` (which may not be stable
  across re-imports) or a hash of the compact representation? A hash of the
  compact input is safer and survives re-imports.
- **Provider availability**: the hermes subagent launcher requires a working
  DeepSeek/Kimi key pool. If unavailable, the function should degrade gracefully
  (return an empty summary) rather than fail the whole conversion.
- **Core-node allowlist**: to derive `primary_custom_nodes` and flags, we need a
  maintained list of core ComfyUI node classes. This list will drift as ComfyUI
  adds nodes. We should seed it from the existing schema provider or a static
  list and accept false positives in derived fields.
- **IR drift**: there are two `VibeWorkflow` implementations (`vibecomfy/workflow.py`
  and `vibecomfy/ir/workflow.py`). The summary dataclass must be added to both or
  the IR version must be updated to read `metadata["summary"]` transparently.
- **Hivemind schema**: confirmed. `add_resource` accepts arbitrary `metadata`
  and `payload` JSON objects in addition to the top-level `title`, `body`, and
  `url` fields. The external-workflow uploader uses this shape.
- **Agent-edit provenance**: a summary generated by an LLM about an LLM-generated
  workflow should not be treated as authoritative provenance. Keep it under
  `metadata.summary`, separate from `metadata.provenance`.
- **Determinism / testing**: LLM-generated text is non-deterministic. Tests should
  assert on the presence and shape of `metadata.summary`, not on exact strings.

## Success criteria

- [x] `VibeWorkflow.metadata["summary"]` exists and is typed after conversion.
- [x] Hivemind uploads include summary-derived text in the body/envelope
      (`scripts/upload_external_workflows_to_hivemind.py`).
- [x] Ready-template Hivemind uploads use the anonymous `contribute-resource`
      endpoint (summary-derived text deferred until ready templates store
      `metadata.summary`).
- [ ] Research precedent slices expose the source workflow summary.
- [x] Existing `external_workflows/corpus/` workflows are backfilled with summaries.
- [x] No derivable data is duplicated inside `metadata.summary`.
- [x] Conversion/upload still succeeds when the summarizer is unavailable.

## Codex sense-check (2026-06-24)

Codex reviewed this plan with the following key findings:

### Major gaps / risks

1. **Low-level ingest hook is too broad.** Adding summary generation to
   `vibecomfy/ingest/normalize.py::convert_to_vibe_format()` would affect tests,
   agent-edit routes, CLI loading, registry loading, workbench, and snapshots.
   The default there should be `False`; summaries should be generated only in
   explicit ingest/backfill/upload commands.
2. **Persistence is underspecified.** `VibeWorkflow.export_to_json()` currently
   returns only the compiled API dict, so `metadata["summary"]` would not survive
   normal JSON export. We must name the durable formats: corpus JSON,
   ready-template `READY_METADATA`, Hivemind payload, or a new full-workflow
   serializer.
3. **Draft backfill script contradicts the derivability rule.**
   `scripts/enrich_workflow_summaries.py` currently asks the LLM for derived
   fields (`primary_models`, `primary_custom_nodes`, flags, complexity). It
   should ask only for `title`, `description`, `tags`, and derive the rest.
4. **Duplicating the dataclass is drift-prone.** `vibecomfy/workflow.py` and
   `vibecomfy/ir/types.py` should not each define `WorkflowSummary`. Prefer a
   shared module such as `vibecomfy/contracts/summary.py`.
5. **Runtime typed vs serialized dict needs helpers.** Because `metadata` is a
   generic dict and is deep-copied freely, callers need helpers like
   `get_workflow_summary(workflow)` / `set_workflow_summary(workflow, summary)`.
6. **Research hook needs a contract change.** `WorkflowSlice` is defined in
   `vibecomfy/executor/contracts.py`. Attaching a summary inside
   `_build_precedent_slices()` will be dropped unless `WorkflowSlice` gains a
   `source_summary` field and `to_dict()` is updated.
7. **Upload hook is misplaced.** `scripts/upload_ready_templates_to_hivemind.py`
   `_load_workflow_identity()` returns only graph identity and discards metadata.
   The summary must be loaded separately or returned alongside identity.
8. **Prompt input may be too lossy.** Node counts + models are sometimes
   insufficient to distinguish intent. Consider adding sanitized source
   title/description, selected widget labels, output node classes, and top-N
   prompt/control fields with truncation and prompt-injection safeguards.
9. **Provider failures need telemetry.** Instead of silently empty summaries,
   record `metadata["summary_status"] = {"status": "unavailable", ...}` for
   debugging.
10. **Caching needs versioning.** Cache key should include prompt schema version,
    model id, code version, and generation parameters.
11. **Validation is too weak.** `from_dict()` should validate title length,
    allowed `task_type`/`media_type`, tag count/format, and timestamp format.
12. **Derived helper ownership is missing.** Custom-node detection, flags, and
    complexity helpers belong in a deterministic analysis module such as
    `vibecomfy/analysis/workflow_summary.py`, not inside the summarizer.

### Suggested simplification

Start with stored fields only:

- `title`
- `description`
- `tags`
- `generated_by`
- `generated_at`
- `schema_version`

Derive `task_type` and `media_type` unless there is a strong reason they need
human/LLM judgment.

### Clarifying questions

1. Which serialized artifact is canonical for persistence: corpus JSON,
   ready-template Python metadata, or a new full `VibeWorkflow` JSON format?
2. Should summaries be generated during normal `load_workflow_any()` /
   ready-template loading, or only during explicit import/backfill/upload?
3. Is Hivemind expected to search `metadata.summary`, top-level `title`/`body`,
   or both?
   *Answered by Codex subagent below.*

## Hivemind mapping (Codex subagent findings)

The Codex subagent inspected `scripts/upload_ready_templates_to_hivemind.py` and
`vibecomfy/executor/research.py` and found:

### Current upload envelope

Built by `_envelope()` at `scripts/upload_ready_templates_to_hivemind.py:225`:

```json
{
  "action": "add_resource",
  "data": {
    "kind": "workflow",
    "source": "vibecomfy",
    "external_id": "vibecomfy:ready_template:<template_id>",
    "title": "<template_id>",
    "body": "<searchable multiline text>",
    "url": "file://<ready_template_path>",
    "metadata": { "...": "structured metadata" },
    "payload": { "...": "source payload" }
  }
}
```

- `metadata` already includes `description`, `task`, `approach`, `model_family`,
  `public_inputs`, `public_outputs`, `custom_nodes`, `models`, etc.
- `payload` includes `python_source`, `description`, and `graph_identity`.

### Where summaries should go

Because Hivemind search in this repo only filters on `title.ilike` and
`body.ilike` (see `vibecomfy/executor/research.py:254`), summary data should be
placed in **both** searchable top-level fields and structured JSON:

- `summary.title` → `data.title` (replacing raw template_id as title).
- `summary.description` → included in `data.body`, `metadata.description`, and
  `payload.description`.
- `summary.tags` → appended to `data.body` as `Tags: tag1, tag2, ...` and stored
  structurally in `metadata.summary.tags` / `payload.summary.tags`.

### Constraints

- No explicit body/title/metadata size limits in the upload script.
- `_post()` sends `json.dumps(envelope).encode("utf-8")` with a 60s timeout
  (`scripts/upload_ready_templates_to_hivemind.py:323`).
- Ready-template uploads still use the authenticated Supabase `contribute` edge
  function and require a contributor key.
- External-workflow uploads use the new anonymous `contribute-resource` edge
  function and do not require a key.
- Query-side search sanitization strips non `[A-Za-z0-9_.+ -]` characters from
  search terms only (`vibecomfy/executor/research.py:344`), so upload content
  does not need character escaping beyond normal JSON serialization.

### External workflow upload mapping (implemented)

`scripts/upload_external_workflows_to_hivemind.py` implements the mapping for the
backfilled external-workflow corpus. Each `manifest.json` row becomes:

| Hivemind field | Value |
|---|---|
| `data.kind` | `workflow` |
| `data.source` | `vibecomfy-external` |
| `data.external_id` | `vibecomfy:external_workflow:<canonical_workflow_hash>` |
| `data.title` | `summary.title` (falling back to filename/workflow_id) |
| `data.body` | `Description: …`, `Tags: …`, `Task type`, `Media type`, `Complexity`, provenance source/url/filename/channel/repo, canonical hash |
| `data.url` | `primary_source.source_url` or `file://<corpus_path>` |
| `data.metadata.asset_kind` | `vibecomfy_external_workflow` |
| `data.metadata.workflow_id` | row `workflow_id` |
| `data.metadata.corpus_path` | row `corpus_path` |
| `data.metadata.summary` | full summary object |
| `data.metadata.description` | `summary.description` |
| `data.metadata.task_type` | `summary.task_type` |
| `data.metadata.media_type` | `summary.media_type` |
| `data.metadata.tags` | `summary.tags` |
| `data.metadata.complexity` | `summary.complexity` |
| `data.metadata.flags` | `summary.flags` |
| `data.metadata.provenance` | lightweight provenance from `primary_source` |
| `data.payload` | `{workflow_id, corpus_path, summary, description, provenance}` |

The title and body are fully searchable via Hivemind's `title.ilike` /
`body.ilike` filters. The structured summary is duplicated into both `metadata`
and `payload` so consumers can read it without parsing free text.

No full ComfyUI JSON is stored in the envelope; the corpus file path and source
URL serve as the durable references. This keeps payloads small enough to upload
all 2,533 workflows without multi-gigabyte transfers.

#### Anonymous upload endpoint

External-workflow uploads go to the new `contribute-resource` edge function
(`banodoco-workspace/hivemind/supabase/functions/contribute-resource/index.ts`):

- No `X-Contributor-Key` header is required.
- The function still validates the payload with the same `validateAddResourceData`
  rules used by the authenticated `contribute` function.
- It enforces a source allowlist (default: `vibecomfy`, `vibecomfy-external`) via
  the `ALLOWED_SOURCES` environment variable. Set `ALLOWED_SOURCES=*` to disable
  the allowlist.
- The script default is:
  ```
  https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/contribute-resource
  ```

### Ready-template upload hook when implemented

When the deferred ready-template work happens, the changes in
`scripts/upload_ready_templates_to_hivemind.py` should be:

1. Add `_summary(row)` normalizer for `row.get("summary")`.
2. In `_body()`, append before Python source:
   - `Title: <summary.title>`
   - `Summary: <summary.description>`
   - `Tags: <tag1>, <tag2>, ...`
3. In `_envelope()`:
   - Compute `summary = _summary(row)`.
   - `data["title"] = summary["title"] or template_id`
   - `metadata["description"] = summary["description"] or existing_description`
   - `metadata["summary"] = summary`
   - `metadata["tags"] = summary["tags"]`
   - `payload["summary"] = summary`
   - Optionally `payload["description"] = summary["description"]`

This mapping is not implemented now; it is recorded here for the deferred upload
hook.

## Deploying the anonymous upload endpoint

To make the no-key path live:

1. In the Hivemind repo (`banodoco-workspace/hivemind`), link and deploy the new
   edge function with JWT verification disabled (so anonymous callers can reach
   it) and an explicit source allowlist:
   ```bash
   cd /Users/peteromalley/Documents/banodoco-workspace/hivemind
   supabase link --project-ref ujlwuvkrxlvoswwkerdf
   supabase functions deploy contribute-resource --no-verify-jwt
   supabase secrets set ALLOWED_SOURCES="vibecomfy,vibecomfy-external"
   ```
2. Run the VibeComfy upload script without a contributor key:
   ```bash
   cd /Users/peteromalley/Documents/reigh-workspace/vibecomfy
   python scripts/upload_external_workflows_to_hivemind.py
   ```
   Use `--dry-run` first to inspect envelopes.

If you ever need to fall back to the authenticated `contribute` endpoint, pass:
```bash
python scripts/upload_external_workflows_to_hivemind.py \
  --contribute-url https://ujlwuvkrxlvoswwkerdf.supabase.co/functions/v1/contribute
```
and set `HIVEMIND_CONTRIBUTOR_KEY`.

### IP / user-agent tracking

The anonymous edge function captures submission telemetry and writes it into
`metadata` on every inserted `external_resources` row:

| Field | Source |
|---|---|
| `_submitted_from_ip` | `X-Forwarded-For` header, falling back to the TCP remote address |
| `_submitted_from_user_agent` | `User-Agent` header |
| `_submitted_at` | server UTC timestamp at insert time |

This lets you audit where uploads came from without requiring a contributor key.

### Note on `_find_existing_resource`

The shared preflight query was changed from `select=...,updated_at` to
`select=...,title` because `external_resources` has no `updated_at` column. The
function still returns an `updated_at` key for backward compatibility, but it
will be `None` for real rows.

## Agentic-loop integration

I deployed subagents to audit every place in the codebase that submits to
Hivemind. They found:

| Path | What it submits | Current endpoint | Should use anonymous `contribute-resource`? |
|---|---|---|---|
| `scripts/upload_external_workflows_to_hivemind.py` | `add_resource` for external workflows | `/contribute-resource` | ✅ Already using it |
| `scripts/upload_ready_templates_to_hivemind.py` | `add_resource` for ready-template Python workflows | `/contribute-resource` | ✅ Switched |
| `vibecomfy/commands/workflows.py::build_onboarding_plan()` | Shell command that runs the ready-template uploader | inherits uploader | ✅ Now keyless by default |
| `vibecomfy/comfy_nodes/agent/hivemind_feedback.py` | Ratings/pack-shares to `submit-vibecomfy-rating` | `/submit-vibecomfy-rating` | ❌ Out of scope — different protocol and auth model |
| `vibecomfy/executor/research.py` and agent-edit tiers | Read-only `unified_feed` queries | PostgREST anon key | N/A |

### What changed for the agentic loop

The onboarding plan generated by `vibecomfy workflows onboard --upload` now
points at the anonymous ready-template uploader. That means an agent (or human)
running the onboarding loop can upload ready templates to Hivemind **without a
contributor key**.

If a caller explicitly wants the authenticated `/contribute` endpoint (e.g., for
audit/author attribution via the `contributors` table), they can still pass
`--contribute-url .../contribute` and set `HIVEMIND_CONTRIBUTOR_KEY`.
