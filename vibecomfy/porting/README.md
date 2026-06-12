# Porting

The porting subsystem converts ComfyUI workflows into VibeComfy Python
scratchpads or ready templates, validates porting fidelity, and exports
workflows back to runtime or UI JSON forms.

Important subpackages:

| Path | Purpose |
|---|---|
| `edit/` | Edit-session IR, patch application, edit-projection helpers, and private session mixins. |
| `emit/` | Split emitter internals and the canonical UI JSON emitter. Root `emitter.py` remains the current Python template emitter boundary until parity migration is complete. |
| `layout/` | UI layout preservation and recovery. |
| `widgets/` | Widget alias and widget-schema resolution. |
| `identity/` | Stable identity, UID, and codec helpers. |
| `wrappers/` | Custom-node wrapper discovery/codegen support. |
| `object_info/` | Object-info consumer and serializer code; snapshots live under `cache/`. |
| `cache/` | Checked-in object-info/cache snapshots used for offline validation. |
