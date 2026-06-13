# Tools

Importable developer tools for validation, code generation, template conversion,
and metadata refresh. Prefer module invocation from the repository root:

```bash
python -m tools.<name> --help
```

Use `tools/` for reusable checks and generators that are imported by tests, CI,
or other tooling. Use `scripts/` for direct-run operational scripts and local
smoke harnesses.

## Template Pipeline

| Tool | Purpose |
|---|---|
| `convert_ready_templates.py` | Bulk-convert or dry-run ready-template updates. |
| `format_as_python.py` | Legacy/delegation wrapper for Python template emission. |
| `generate_agent_contract_js.py` | Regenerates the agent-edit JavaScript response contract. |
| `populate_model_hashes.py` | Populate registry model hash pins from Hugging Face metadata. |
| `regenerate_affected_templates.py` | Regenerate templates affected by schema changes. |
| `regenerate_snapshots.py` | Rebuilds or checks compile-API snapshots. |
| `refresh_template_index.py` | Rebuild or check `template_index.json`. |
| `refresh_comfy_metadata.py` | Refresh checked-in ComfyUI metadata. |
| `fetch_hf_metadata.py` | Fetch model metadata for authored assets. |

## Validation / Audits

| Tool | Purpose |
|---|---|
| `check_markdown_links.py` | Validate tracked Markdown local links. |
| `check_canonical_parity.py` | Canonical-vs-generated template parity check. |
| `check_pack_provenance.py` | Validate custom-node pack provenance. |
| `check_strict_ready_templates.py` | Strict-ready-template gate. |
| `validate_template_traceability.py` | Template/source traceability audit. |
| `validate_templates_against_packs.py` | Template node usage against pack declarations. |
| `class_inventory_audit.py` | Node class inventory audit. |
| `profile_smoke_report.py` | Profile-smoke report helper. |

## Node / Pack Helpers

| Tool | Purpose |
|---|---|
| `generate_node_shims.py` | Generate typed node wrapper modules. |
| `backfill_custom_node_refs.py` | Backfill missing custom-node references. |
| `clone_and_extract_packs.py` | Clone upstream packs and extract class metadata. |
| `_widget_schema.py` | Internal widget-schema helper. |
