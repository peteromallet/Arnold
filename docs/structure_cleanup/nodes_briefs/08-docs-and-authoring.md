# Nodes Layer Audit 08: Docs and Authoring Guidance

Working directory: `/Users/peteromalley/Documents/reigh-workspace/vibecomfy`.

Goal: find docs that teach or depend on the node wrapper import paths.

Inspect:
- `README.md`
- `docs/authoring.md`
- `docs/templates/`
- `docs/historical/` only for context, not active guidance
- `AGENTS.md` and `CLAUDE.md`

Return:
1. Active docs that present `vibecomfy.nodes.<pack>` as the authoring API.
2. Whether docs should be changed to `_generated` imports or should continue presenting public pack modules.
3. Any stale phrase like "thin wrapper" or "shim" that should be revised.
4. Small doc cleanup candidates.
Keep the answer under 450 words.
