# VibeWorkflow v0

`VibeWorkflow` is the only editable workflow IR for milestone one. JSON files are inputs or outputs, not the patching surface.

Required flows:

```text
JSON/UI workflow source -> normalized API dict -> VibeWorkflow
authored scratchpad -> VibeWorkflow -> Comfy API dict -> runtime queue
```

Scratchpad files must return a `VibeWorkflow` from `build()`. JSON/UI workflows
are normalized first; scratchpads are the authored Python surface that compile
back to Comfy API dictionaries for execution.
