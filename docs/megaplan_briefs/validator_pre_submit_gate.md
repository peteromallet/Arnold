vibecomfy: validator-pre-submit-gate v1 — promote the existing schema validator into a hard pre-submit gate that runs against the live runtime's `/object_info`, fail loudly with actionable messages, and add the missing checks (link shape, range/enum) that let real bugs through. Do NOT rewrite the materializer.

Source repo: /Users/peteromalley/Documents/reigh-workspace/vibecomfy

# Problem

Several "HiddenSwitch incompatibilities" in `docs/hiddenswitch_incompatibilities.md` are actually our own materializer/harness bugs that submit invalid graphs the runtime then chokes on:

- ACE materializer emitted dict-shaped links instead of standard Comfy link arrays (`KeyError: 0` in `_compress_graph_nodes`).
- ACE got `bpm=2` (declared min is 10) because we trusted UI widget positions; missing required API fields (`top_p`, `min_p`, `top_k`, `temperature`).
- Both classes are submit-invalid by the runtime's own `/object_info` schema and could be caught up-front.

The infrastructure to catch these already exists but is not wired:

- `vibecomfy/schema/validate.py:9` — `validate_against_schema(workflow, provider)` checks unknown class_types, missing required inputs, unknown inputs, edge type mismatches.
- `vibecomfy/schema/provider.py` — `SchemaProvider` fetches `/object_info` and caches it under `vibecomfy/schema/cache.py:object_info_cache_path`.
- `vibecomfy/runtime/client.py:36` — `ComfyClient.object_info()` already exists.
- `vibecomfy/workflow.py:155` — `VibeWorkflow.validate(schema_provider=None)` exists but the provider parameter is **optional and defaults to None**, so schema checks no-op.
- `vibecomfy/runtime/session.py:_prepare_prompt()` (around line 327) calls `workflow.validate()` **with no provider**. The comment explicitly says "Runtime submissions stay structural-only to avoid schema lookup cost on every invocation." — that comment justifies the bug. Caching solves the cost concern.

The validator also misses two checks that would have caught real bugs:
- **Range/enum**: ACE `bpm=2` slipped through because numeric ranges are not enforced.
- **Link shape**: dict-shaped links in API JSON pass structural checks but break the runtime; there is no API-shape sanity check.

# Goal

Make schema validation a hard pre-submit gate. Five mechanical steps:

1. Wire a SchemaProvider into `_prepare_prompt()` and gate submission on `validate(schema_provider=...)`.
2. Add range/enum enforcement to `validate_against_schema`.
3. Add API-link-shape enforcement (every connected input must be `[node_id_str, output_index_int]`, not a dict).
4. Add an opt-out list (`SCHEMA_VALIDATION_SKIP_CLASSES`) for known-lying custom-node schemas, with each entry pointing to a `hiddenswitch_incompatibilities.md` row.
5. Make failure messages name the node, class_type, input, and the violated rule — and surface them via the existing CLI surfaces (`vibecomfy run`, `vibecomfy validate`).

Materializer rewrite is explicitly OUT of scope. This is a validation gate only.

# Verified facts (do not re-research)

- `vibecomfy/schema/validate.py:9` — entry point `validate_against_schema(workflow, provider)`.
- `vibecomfy/schema/provider.py:122` — SchemaProvider caches per-server-fingerprint at `object_info_cache_path()`.
- `vibecomfy/schema/provider.py:148` — first-call fetch is async via `object_info_async()`; subsequent calls are cache-hits.
- `vibecomfy/workflow.py:155` — `validate()` already returns `ValidationReport(ok, issues)`; `ok` is False if any issue has `severity="error"`.
- `vibecomfy/runtime/session.py` `_prepare_prompt()` already raises `ValueError("Workflow validation failed: ...")` on `not report.ok`. Wiring a provider is sufficient to turn schema checks on.
- `vibecomfy/runtime/client.py:20` — `queue_prompt()` posts to `/prompt`; this is the submit boundary.
- `vibecomfy/commands/validate.py` exists as a CLI surface.

# Steps

## S1: Wire SchemaProvider into the submit gate

- In `vibecomfy/runtime/session.py`:
  - Construct or accept a `SchemaProvider` for the active runtime URL once per session (not per submit). Store it on the session/runner.
  - Pass it into `workflow.validate(schema_provider=provider)` inside `_prepare_prompt()`.
  - Update the comment that currently justifies skipping schema validation; note that caching makes per-submit cost negligible.
- Default behavior: if `/object_info` cannot be fetched and no cache exists (e.g. fully offline materialization-only path), fall back to structural-only validation with a single WARNING line printed once per session. Never silently skip; never hard-fail when the provider itself is unavailable. Hard-fail only on actual schema violations.

## S2: Range and enum enforcement

- In `vibecomfy/schema/validate.py:validate_against_schema`, after the missing/unknown input checks:
  - For each provided input whose schema spec declares numeric `min`/`max`, compare the supplied value (after coercion) and emit `ValidationIssue("value_out_of_range", ...)` on violation.
  - For each input whose schema spec declares an enum/options list, emit `ValidationIssue("value_not_in_enum", ...)` if the value is not a member.
  - Both at `severity="error"`.
- Inspect the existing schema-loading path in `vibecomfy/schema/provider.py:_schema_from_object_info` to confirm the spec shape (it likely already carries `min`/`max`/`options` from the raw `/object_info`); if not, extend it minimally to surface them.

## S3: API link-shape enforcement

- Add a new check (can live in `validate_against_schema` or a sibling `validate_api_shape` called from `VibeWorkflow.validate`):
  - For every input on every node, after compilation/edge resolution, the value must be one of: a primitive scalar, a list/tuple, a dict (only when the schema declares dict-shaped input), or an API link in the form `[node_id_str, output_index_int]`.
  - Specifically detect and reject dict-shaped links such as `{"link": ..., "node": ...}` connected to inputs whose schema type is not `DICT`/`*`. Emit `ValidationIssue("invalid_link_shape", ...)`.
- This check runs against the compiled API dict from `VibeWorkflow.compile(backend="api")` if that's the cleanest place; otherwise pre-compile inside `validate()`.

## S4: Per-class skip list for known-lying custom-node schemas

- New module-level constant in `vibecomfy/schema/validate.py`: `SCHEMA_VALIDATION_SKIP_CLASSES: dict[str, str]` mapping `class_type` → human-readable reason (and ideally a URL/anchor into `hiddenswitch_incompatibilities.md`).
- For each class_type in the skip list, suppress only `unknown_input` and `value_*` issues — still enforce `unknown_class_type` and `missing_required_input` (those are usually correct even when widget schemas are wrong).
- Initial entries: empty. Add the first entry only when a real workflow trips a check that is provably the schema's fault, not the workflow's, and add a note in the incompatibilities doc with `Root cause: custom_node_contract`.

## S5: CLI and reporting

- `vibecomfy validate <workflow>` (in `vibecomfy/commands/validate.py`): make schema validation default-on, with `--no-schema` to fall back to structural-only.
- `vibecomfy run <workflow>` and `vibecomfy session ...` paths: the gate is implicit (S1); on failure, print every issue with node id, class_type, input, and the human-readable rule violated, then exit nonzero. Do not print only the first issue.
- Update existing tests under `tests/` that currently submit invalid graphs (if any) to either fix the graph or explicitly call validate-with-skip.

# Out of scope (do NOT add)

- Materializer rewrite. The materializer keeps its current shape; the validator catches its bugs at the boundary. A separate brief will revisit the materializer if the validator surfaces a recurring class of materializer bugs (≥3 times across different workflows).
- Pre-flight doctor that bundles validator + node-presence + model-presence + preview-stripping into a single gating report. Defer.
- Per-workflow input contract / fixture declaration system. Separate brief.
- Auto-repair: the validator only diagnoses, never mutates the graph.
- Type-coercion changes (string vs int widget values). Validator should accept whatever the runtime accepts.

# Design constraints

- **Reversibility**: every behavior change must be toggleable via a single env var or flag (`VIBECOMFY_SCHEMA_VALIDATE=0` to disable, or `--no-schema` on the CLI). Do not make the gate non-bypassable.
- **Cache hits**: schema validation must be a cache-hit on every submit after the first per-runtime; first-fetch latency is acceptable.
- **No new top-level deps**.
- **Failure messages must be actionable**: every error names the node id, class_type, the input or rule violated, and the value (truncated if large). No bare "schema check failed".
- **Skip list discipline**: every entry in `SCHEMA_VALIDATION_SKIP_CLASSES` must be cross-referenced from `docs/hiddenswitch_incompatibilities.md` per the Contributing rules in that doc.
- **Do not gate non-submit code paths**: `vibecomfy convert`, `vibecomfy materialize`, etc. should not trigger the gate. Only paths that actually submit to `/prompt` enforce it.

# No prereq clauses

This brief has no hard-halt prereqs. It is independent of the model-registry brief (#5), the watchdog subagent (#2), the override-deletion subagent (#3), and the fixture-library subagent (#4). Ship as soon as ready; do not wait on any of them.

# Validation evidence to produce

- Re-run the previously-failing ACE materialization (the dict-shaped link case and the bpm=2 case): both must now hard-fail at submit with messages that name the node, the class_type, and the rule.
- Re-run the existing 14 runtime-green workflows: all must still pass the gate (no regressions).
- Add unit tests in `tests/test_schema_validate.py` for: missing required input, unknown input, value-out-of-range, value-not-in-enum, invalid-link-shape, skip-list suppression, structural-only fallback when provider is unavailable.

# Open questions

- Should the gate run on the structural workflow object or on the compiled API dict? Both shapes have different bug surfaces (link shape only matters in API form). Lean toward: structural checks on the object, link-shape checks on the compiled API. Validator returns a single combined report.
- Should `SCHEMA_VALIDATION_SKIP_CLASSES` live in code or in `docs/hiddenswitch_incompatibilities.md` as a parsed table? V1: code constant with a docstring pointer to the doc. Parsed-from-doc is a follow-up.
- Cache invalidation: what happens when the runtime upgrades and `/object_info` shape changes? The current cache is fingerprinted by `runtime_fingerprint(server_url)`; confirm that fingerprint includes a runtime version or build hash. If not, that's a separate bug worth flagging but not blocking this brief.
