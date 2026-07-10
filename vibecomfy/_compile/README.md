# Compile Internals

Private helpers for turning `VibeWorkflow` graphs into ComfyUI API JSON.

Import public compile behavior through `VibeWorkflow.compile(...)` or the
package-level compatibility shims. Direct imports from this package should stay
inside VibeComfy internals and tests that intentionally cover compiler details.
