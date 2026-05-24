# M6 Public API Surface

This artifact records the code-level public import surface settled for M6.
It is intentionally limited to API facts; broader narrative documentation belongs
to the M7 documentation pass.

## API Export Path

Use `VibeWorkflow.compile("api")` to export a workflow to the ComfyUI API JSON
shape accepted by runtime execution.

Do not add or document a separate `export_to_json` public method for M6. Existing
source and test code does not require it, and `compile("api")` is the supported
single export path.

## Top-Level Imports

The following names are public from `vibecomfy` and are present in
`vibecomfy.__all__`.

### Loaders

- `load_workflow_any`
- `load_workflow_json`
- `workflow_from_file`
- `workflow_from_id`
- `workflow_from_ready`
- `ready_template_ids`

### Template Compatibility Aliases

- `workflow_from_template`
- `load_template`

### Runtime Helpers

- `run`
- `run_sync`
- `run_embedded`
- `run_embedded_sync`

### Ops Namespaces

- `image`
- `video`

### Core IR Types

- `VibeWorkflow`
- `VibeNode`
- `VibeEdge`
- `VibeInput`
- `VibeOutput`
- `WorkflowRequirements`
- `WorkflowSource`
- `ValidationIssue`
- `ValidationReport`

### Handles

- `Handle`

### Layer-2 Namespaces

- `blocks`
- `patches`
- `router`

### Artifact Result Types

- `Artifact`
- `Image`
- `Video`
- `Audio`
- `Latent`
- `Mask`

### Plugin Hook

- `ensure_plugins_loaded`
