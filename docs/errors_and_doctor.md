# Errors and Doctor

`vibecomfy doctor` reports the failing layer:

- Python scratchpad import/build errors.
- VibeWorkflow validation errors.
- Missing model errors.
- Missing node errors.
- Comfy runtime errors.
- Device or VRAM profile errors.

For template porting failures, start with the cheaper porting preflight:

```bash
python -m vibecomfy.cli port check <workflow> --json
```

Use `port check` before manual template editing or RunPod validation when you see:

- unknown or missing runtime classes;
- missing required inputs, invalid link shapes, or schema type mismatches;
- unresolved `SetNode` / `GetNode` broadcasts or UI-only helper nodes;
- model asset warnings, missing URLs, duplicate URL targets, 404s, or license-gated URLs;
- positional `widget_N` aliases that need a real widget name.

`doctor` remains the runtime-readiness command for authored scratchpads and ready templates. It may point you back to `port check` when a failure is better explained by the port report. Use `validate` for schema/structure checks, `nodes install-plan` for custom-node pack plans, and `fetch` for declared model downloads.

Model URL HEAD checks are opt-in:

```bash
python -m vibecomfy.cli port check <workflow> --head-check-models --json
```

That command records status, redirects, timeouts, and likely gated or missing URLs without downloading model bodies. Normal `doctor`, `validate`, `fetch`, and `run` behavior stays offline unless you explicitly request network checks.
