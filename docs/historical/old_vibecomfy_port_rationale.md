# Old VibeComfy Port Rationale

Status: Historical rationale. Current user-facing guidance lives in
[`../../README.md`](../../README.md) and [`../authoring.md`](../authoring.md);
current public API names are recorded in
[`../api/m6-public-api.md`](../api/m6-public-api.md).

The old `peteromallet/VibeComfy` project was useful because it helped agents inspect, search, edit, and submit existing ComfyUI workflow JSON. The new VibeComfy has a different center: workflows are normalized into `VibeWorkflow`, edited through Python scratchpads, compiled to Comfy API JSON, and run through managed or embedded runtime paths.

Because of that, old features should be ported as capabilities on top of the new model, not copied in as a parallel raw-JSON tool.

## Port Early

### Schema-aware workflow validation

Current `VibeWorkflow.validate()` only checks basic internal structure, such as empty workflows and edges pointing at missing nodes. It does not prove that a workflow is valid for an actual ComfyUI runtime.

The first useful port is the old tool's `/object_info`-aware behavior:

- confirm `class_type` exists in the active runtime
- map UI `widgets_values` to real input names during fallback normalization
- detect missing required inputs
- detect unknown input names
- check rough edge input/output type compatibility

This should become a shared schema layer used by normalization, validation, trace output, node search, and later editing.

### Workflow analysis

Port the old graph-understanding commands to operate on `VibeWorkflow`:

- `analyze`
- `trace`
- `upstream`
- `downstream`
- `path`
- `subgraph`
- `values`
- `diff`
- `unconnected`

These are valuable because they help humans and agents understand workflows before editing or running them. The implementation should live in a reusable analysis module, with CLI and future MCP commands as thin adapters.

### Node knowledge and search

Port the old registry/search ideas, especially weighted search and task aliases like `i2v`, `controlnet`, `wan`, `ltx`, and `audio reactive`.

Do not copy the old cache as the only source of truth. New search should plug into available sources:

- runtime `/object_info`
- `node_index.json`
- custom node examples
- curated workflow/template metadata
- optional remote registry data later

## Port After Redesign

### Editing commands

The old `copy`, `wire`, `set`, `delete`, `create`, `inline`, and `batch` commands are useful, but they edited ComfyUI UI JSON directly. That conflicts with the new design, where `VibeWorkflow` is the editable IR and JSON is mainly input/output.

Port these as `VibeWorkflow` editing primitives first, then expose CLI commands after the API settles. Scratchpad rewriting should wait; early edit commands can output API JSON or print Python snippets.

### Visualization and layout

The old SVG/layout features are useful, but they depend on richer graph metadata and should come after analysis and schema support.

### MCP adapter

The old MCP server should not be copied as its own implementation. A future MCP adapter should call the same analysis, schema, node-search, validation, and runtime APIs used by the CLI.

## Do Not Port Directly

- raw JSON editing as the primary UX
- old `submit`/`logs` behavior, since the new runtime surface is stronger
- Claude-specific skill files as core product structure
- duplicated MCP-only analysis logic

## Recommended Order

1. Add a shared workflow loading helper for JSON, scratchpads, and indexed templates.
2. Add schema providers around `/object_info` and local indexes.
3. Improve UI-to-API fallback normalization using schema data.
4. Add schema-backed validation.
5. Add `VibeWorkflow` graph analysis and CLI commands.
6. Add node search/spec commands.
7. Add editing primitives.
8. Add recipe/batch, visualization, and MCP adapters once the core APIs are stable.

The goal is to keep the useful old behaviors while strengthening the new architecture. Old VibeComfy should be treated as a feature backlog, not as a compatibility layer to preserve wholesale.
