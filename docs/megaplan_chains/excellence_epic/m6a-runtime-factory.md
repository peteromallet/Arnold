# Sprint 6a — Runtime factory + protocol (`partnered/thorough/high +prep @codex`)

Shared context: read `docs/structural_audit_2026-05.md` (j8/j9 change amplification), `handoff-m3.md`, `handoff-m4b.md`, and `handoff-m5.md`. Modules are decomposed, IR is pure, and nets are in place. Sprint 6b owns RunPod.

## Outcome
Runtime selection becomes a registry-backed `VibeSession` abstraction for embedded, server, and dry-run sessions, with a tested `RunResult` shape. Adding a runtime becomes a dict entry + class before any RunPod-specific work begins.

## Scope (IN)
1. **Define and implement the `VibeSession` protocol**:
   - `config: SessionConfig`
   - `last_fingerprint: tuple[Any, ...] | None`
   - async `start()`
   - async `run(wf, *, backend: Literal["api", "comfy"] = "api", strict_drift: bool = False) -> RunResult`
   - async `flush()`
   - async `reconfigure(config) -> bool`
   - async `stop(wait_for_inflight=True)`
2. **Add `_RUNTIME_REGISTRY: dict[str, type[VibeSession]]`** keyed by runtime name and `create_session(name, config) -> VibeSession`.
3. **Dispatch public runtime selection through the factory**: `run(wf, runtime=...)` and CLI `--runtime` use `create_session`; collapse the current if/elif chains in `commands/run.py`.
4. **Adapt `EmbeddedSession` and `ServerSession`** to declare/behave as protocol implementations. Tighten current `reconfigure() -> Any` to `-> bool` via wrapper/adaptation as needed.
5. **Add `DryRunSession(VibeSession)`** as a pure no-op runtime proving factory dispatch end-to-end.
6. **Update `RunResult`** with `runtime: str` and `timings: dict[str, float]`, preserving current fields: `run_id`, `prompt_id`, `outputs`, `metadata_path`, `log_path`.
7. **Harden runtime/eval testing** with offline mocked `ComfyClient` coverage plus at least one recorded/real Comfy payload for known-misclassified node types. Add behavioral assertions alongside snapshots, e.g. `z_image` compiles to exactly one `SaveImage`.
8. **Create `handoff-m6a.md`** recording protocol/API decisions, registry behavior, compatibility tests, dry-run evidence, and explicit prerequisites for sprint 6b.

## Locked decisions
- Session factory = dict keyed by runtime name.
- Keep `run()`/`run_embedded()` as thin back-compat wrappers over the factory unless a version bump explicitly removes them.
- `backend` maps to the M3 `VibeWorkflow.compile(backend)` contract.
- `strict_drift=True` elevates M2 drift-check warnings to hard failures at session start; `False` preserves current behavior.
- A hypothetical fourth runtime must require only a dict entry + class.
- All `RunResult(...)` construction sites must be updated.

## Prep deliverables
- `prep-m6a.md` maps existing runtime entry points, `RunResult` constructors, and protocol mismatches before edits.

## Constraints
- Existing public `run()` / `run_embedded()` callers keep working.
- Sprint-3 import-linter contract stays green.
- Differential harness and current fast-suite command stay green.
- No RunPod SDK/network integration in this sprint.

## Done criteria
- Embedded, server, and dry-run sessions implement the protocol and dispatch through the registry.
- CLI runtime selection and public `run()` wrappers use the factory.
- `RunResult` shape is documented and tested across embedded/server/dry-run paths.
- Runtime/eval blind spot has offline tests plus recorded/real payload regression coverage.
- A fourth-runtime amplification test passes.
- `handoff-m6a.md` satisfies the shared handoff contract and names sprint-6b inputs.

## Touchpoints
`runtime/run.py`, `runtime/session.py`, `runtime/__init__.py`, `commands/run.py`, `runtime/eval*.py`, tests, docs.

## Anti-scope
Do NOT implement `RunPodSession`. Do NOT change plugin collision semantics or wire new verbs. Do NOT alter emitter or IR-core semantics.
