# Agent edit: switch to 16 frames with Hotshot

The user has an existing ComfyUI workflow from
`tests/fixtures/agent_edit/hotshot_base_unsaved_workflow_4.json` and asks:

> Switch to generating 16 frames with Hotshot

Run the VibeComfy agent-edit path against that graph. The actor's first
research step must find a workflow precedent for the requested Hotshot behavior
and use that workflow's pattern as the adaptation guide. Only after that should
it use the Comfy Registry / Manager to resolve missing custom-node class names
or schemas. Preserve missing custom nodes as unresolved candidate nodes when
registry evidence supplies class names or schema.

Freeze the full agent-edit result as `evidence/agent_edit_result.json`, the
candidate UI graph as `evidence/candidate.ui.json`, and the actual batch
transcript as `evidence/messages.jsonl`.
