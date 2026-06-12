# Sprint 7 — Plugin semantics, verbs, and release hardening (`partnered//high`)

Shared context: read `docs/structural_audit_2026-05.md` (j8/j9 change-amplification, plugin/verb findings) plus the handoff artifacts from sprints 1-6b. Sprint 7 of 10. Runtime selection is a registry (sprint 6a), RunPod is a runtime session (sprint 6b), modules are decomposed (sprint 5), IR is pure (sprint 3), and the safety nets are in place.

## Outcome
The remaining half-finished public abstractions are completed: plugin collisions behave consistently, route/verb registration is data-driven, the missing user-facing verbs are callable, and release/migration docs are coherent enough for users and future agents.

## User-visible promise
The v2.8 release note must state plainly what users get from the epic: corrupted ready templates fixed, `set_prompt` / public input updates no longer silently lie, `image.edit` works, `audio.t2a` works, runtime selection is clearer, and errors include better `next_action` guidance. Infrastructure work that is not visible to users is documented as reliability/maintainability support for those outcomes, not as a feature by itself.

## Scope (IN)
1. **Unify plugin collision semantics** across ops/blocks/patches/routes/ready into a single three-tier policy. **Tier 1:** duplicate built-in registration raises `ValueError` (programmer error). **Tier 2:** plugin registration colliding with an existing built-in emits a one-shot `RuntimeWarning` and discards the plugin entry (built-in wins). **Tier 3:** plugin-on-plugin collision raises `ValueError` (`"plugin collision"`). Implementation: each registry tracks `_BUILTIN_KEYS` frozen after built-in imports; registrations gate on that set. For routes, collision key means duplicate route id/name, not duplicate `(verb_kind, verb_name)` and not predicate overlap. This is not a sandbox — plugins execute trusted local Python.
2. **Complete the missing verb surface in priority order**: Tier 1 must ship `image.edit(image, prompt, *, model=None, **kwargs)` routing to `edit/qwen_image_edit` / `edit/flux2_klein_4b_image_edit_distilled` and `audio.t2a(prompt, *, model=None, **kwargs)` routing to `audio/ace_step_1_5_t2a_song`. Tier 2 scaffolding only: `image.i2i(image, prompt, *, strength=0.8, model=None, **kwargs)` and `image.inpaint(image, mask, prompt, *, model=None, **kwargs)` with zero initial routes. Scaffolds raise clear no-route errors; wrap in `VibeComfyError` with `next_action` if that pattern is available on the path, otherwise preserve router `KeyError` and record standardization debt in `handoff-m7.md`. These four are distinct verbs, not aliases.
3. **Data-drive `router_rules.py`**: move hardcoded `register_route()` calls into a declarative config consumed at import, preserving `register_route()` as the public plugin API. `router.pick()` contract: first-matching-rule-wins in registration order. Built-in routes are registered first and therefore shadow plugin routes when predicates overlap. Two routes for the same verb with different predicates are valid routing branches, not collisions. Route declarations use M4's `NodeClassification.media_kind` values (`image`, `video`, `audio`) as the verb-namespace taxonomy.
4. **Extend user-facing acceptance smoke tests** for the canonical flow introduced in M3: discover → load → edit → validate → compile/run. At minimum, protect `workflows list --ready`, `inspect image/z_image`, `load_workflow_any("image/z_image")`, prompt/seed/steps editing, `validate`, `compile("api")`, and a no-GPU or mocked run path. Add real embedded/RunPod smoke only when env/model prerequisites are available.
5. **Verify/fix packaging and release surface**: validate `pyproject.toml`, package version exposure, console script entrypoint (`vibecomfy = "vibecomfy.cli:main"` or current equivalent), public import surface, and the versioned release-note convention. Create or update missing release artifacts rather than assuming they exist.
6. **Add release/migration docs**: versioned release-note entry under `docs/release_notes/v2.8.0.md` (the file created by M3; if M7 warrants its own version bump to `2.9.0`, create `docs/release_notes/v2.9.0.md` and update `pyproject.toml` accordingly), migration note links, README/AGENTS.md/CLAUDE.md updates for new runtime/session and verb behavior, and a short "known deferred debt" section covering any hardcoded node-ID debt, swallowed-exception inventory, plugin/scratchpad trust-model work, supply-chain hardening, observability work, alias-map retirement, or scoped plugin namespaces not fixed in this epic. Deferred debt is grouped by category; each category carries severity and a proposed owning follow-up epic/workstream.
7. **Document plugin/scratchpad trust boundaries**: plugin collision policy is not a sandbox. Document plugin/scratchpad trust boundaries in `docs/plugins.md` (create it if absent): project/user/global plugins and scratchpad Python execute trusted local code with full process access, and the collision policy prevents registration conflicts but not security isolation or Python module namespace collisions. Add a visible warning in the relevant docs/CLI path if absent, audit all dynamic plugin-loading call sites (`importlib`, `exec_module`, `__import__`, `exec`, `compile`), and record follow-up work for sandbox/signature/provenance hardening and scoped/qualified plugin namespaces.
8. **Create the final handoff artifact** at `docs/megaplan_chains/excellence_epic/handoff-m7.md`, recording plugin policy, route data format, verb coverage, packaging/version checks, acceptance commands, release docs changed, and deferred backlog.

## Locked decisions
- Collision policy = built-in-wins for plugin→built-in collisions with one-shot warning; duplicate built-ins and plugin→plugin collisions raise `ValueError`.
- Existing `router.pick()` contract remains public and compatible.
- Existing verbs keep backward compatibility; new verbs should use the same Artifact/run conventions as current ops. When exercised through `VibeSession.run()`, new-verb workflows return the M6a/M6b `RunResult` shape (`run_id`, `prompt_id`, `outputs`, `metadata_path`, `log_path`, `runtime`, `timings`).
- Release hardening is documentation and acceptance coverage, not an excuse for broad new architecture.
- Trust boundary documentation is in scope; plugin sandboxing/signing is explicitly out of scope unless already trivial.
- Release convention = versioned files under `docs/release_notes/` (`docs/release_notes/v2.7.0.md` is canonical today).
- Release note target = `docs/release_notes/v2.8.0.md` unless sprint scope justifies a separate `2.9.0` bump.
- Structured run-history UX remains a follow-up; this sprint only standardizes `--json` error shapes for commands it touches where `VibeComfyError.next_action` is already available.

## Constraints
- Sprint-1 differential harness, sprint-2a/2b gates, sprint-3 import-linter contract, and sprint-6a/6b runtime compatibility tests must stay green.
- No unbudgeted RunPod spend; optional GPU checks must document cost/env requirements and teardown.
- No hard renames of public APIs or CLI commands without migration docs and compatibility aliases.
- CLI `--json` failures for the new/changed commands should expose structured `status`, `error`, and `next_action` where the command already catches `VibeComfyError`; broader run-history tooling is follow-up debt.

## Done criteria
- Plugin collision behavior is consistent and tested across ops, blocks, patches, routes, and ready templates.
- `image.edit` and `audio.t2a` are callable through the public ops surface with working routes; `image.i2i` and `image.inpaint` are callable scaffolds with clear no-route errors until templates exist. Tests prove route selection, deferred-route errors, and Artifact/run behavior where routes exist.
- `router_rules.py` is data-driven without breaking `router.pick()`.
- Canonical user-journey acceptance tests pass in CI-safe mode.
- Packaging/version/release surface validated: package version source, console entrypoint, public import surface, and release-log convention are consistent and tested/documented.
- Trust-boundary docs/warnings for plugin and scratchpad Python execution are present.
- Canonical release note under `docs/release_notes/`, migration docs, README/AGENTS.md/CLAUDE.md updates, and `handoff-m7.md` are committed.

## Touchpoints
`ops/{image,video,audio}.py`, `ops/registry.py`, `router.py`, `router_rules.py`, `blocks/__init__.py`, `patches/registry.py`, `registry/ready.py`, `ready_templates/**`, `ready_templates/sources/manifests/coverage.json`, `pyproject.toml`, `vibecomfy/__init__.py`, `tests/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `docs/`.

## Anti-scope
Do NOT redesign the runtime factory (sprint 6a) or RunPod session boundary (sprint 6b). Do NOT re-decompose modules (sprint 5). Do NOT change IR-core or emitter semantics (sprints 1/3 own those). Do NOT turn the deferred user-testing idea into a separate framework unless the required acceptance tests force a tiny helper extraction. Do NOT attempt full plugin sandboxing, pip hash enforcement, git signature verification, or run-history UX in this sprint; name those as follow-up work with owners/severity.
