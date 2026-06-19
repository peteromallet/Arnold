# M4: VibeComfy headless edit integration

## Outcome
`vibecomfy.comfy_nodes.agent.edit.handle_agent_edit` can be imported and called outside ComfyUI, its contract is documented, and a reference Arnold pipeline edits a workflow using a mock client without a live server. The integration explicitly reuses, wraps, or replaces any existing `arnold/pipelines/vibecomfy_executor`.

## Scope

IN:
- Inspect existing `arnold/pipelines/vibecomfy_executor` (if present) and decide: reuse, wrap, or replace with the new bridge. Document the decision.
- Refactor `vibecomfy/comfy_nodes/agent/routes.py` so HTTP route registration is in a function (`register_agent_edit_routes(app)`) rather than at module import time.
- Guard the route module with `VIBECOMFY_HEADLESS=1` so importing `vibecomfy.comfy_nodes.agent.edit` outside ComfyUI does not crash.
- Create `vibecomfy/porting/edit/agent_edit.py` as a public headless entry point that re-exports `handle_agent_edit` and related core functions without importing the route module.
- Add a complete docstring to `handle_agent_edit` documenting args and return dict keys.
- Create `vibecomfy/testing/agent_edit.py` with `StubDeepSeekClient`, `stub_schema_provider`, and `stub_session_root` helpers.
- Add `tests/fixtures/agent_edit/README.md` labeling fixtures by complexity, node coverage, and headless safety.
- Create or update the Arnold ↔ VibeComfy edit pipeline. If reusing `vibecomfy_executor`, adapt it to use the headless port; otherwise create `arnold/pipelines/megaplan/pipelines/vibecomfy_edit_bridge/`.
- Add tests for the headless import and the edit bridge using the stub client.
- Add cross-repo integration doc `docs/vibecomfy/arnold-integration.md`.

OUT:
- Do not change ComfyUI runtime behavior when routes are registered normally.
- Do not move `handle_agent_edit` out of `vibecomfy/comfy_nodes/agent/edit.py`; create the porting re-export instead.
- Do not leave two competing integration paths undocumented.

## Locked decisions
- Headless mode is opt-in via `VIBECOMFY_HEADLESS=1`.
- The public headless import path is `vibecomfy.porting.edit.agent_edit`.
- The stub client mirrors the existing test helper patterns in `tests/test_comfy_nodes_agent_edit.py`.
- Existing `vibecomfy_executor` is explicitly accounted for in the design.

## Open questions
- What is the exact return shape of `handle_agent_edit` for success, noop, clarify, and error outcomes?
- Which fixture workflows are safe for headless edits without custom-node schemas?
- Does `arnold/pipelines/vibecomfy_executor` exist and what does it do?

## Constraints
- `VIBECOMFY_HEADLESS=1 python -c "from vibecomfy.porting.edit.agent_edit import handle_agent_edit"` must succeed from the Arnold directory.
- The edit bridge test must pass without a live ComfyUI server or model API call.

## Done criteria
- Headless import succeeds.
- `handle_agent_edit` has a complete docstring.
- `pytest` for the edit bridge passes with the stub client.
- Integration doc explains PYTHONPATH setup, headless import, payload/return contracts, and credential sharing.
- Decision record explains reuse/wrap/replace choice for any existing `vibecomfy_executor`.

## Touchpoints
- `arnold/pipelines/vibecomfy_executor` (inspect first)
- `vibecomfy/comfy_nodes/agent/routes.py`
- `vibecomfy/comfy_nodes/agent/__init__.py`
- `vibecomfy/comfy_nodes/agent/edit.py`
- New `vibecomfy/porting/edit/agent_edit.py`
- New `vibecomfy/testing/agent_edit.py`
- `tests/fixtures/agent_edit/README.md`
- New or updated Arnold bridge pipeline
- New `docs/vibecomfy/arnold-integration.md`

## Anti-scope
- Do not flatten all ready templates to remove subgraphs.
- Do not add a new credential-resolution helper in this sprint; document the existing pattern.
