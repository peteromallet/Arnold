You are a Codex subagent reviewing the Reigh extension-layer epic from the UX/runtime SURFACE perspective.

Working directory:
/Users/peteromalley/Documents/reigh-workspace/reigh-app

Context:
- Epic name: reigh-extension-layer-epic
- Current branch: reigh-extension-layer-epic
- origin/main tip referenced by the human: b7a49a0c2 ("post-M15 sense-check fixes...")
- Current local HEAD may include extra uncommitted fixes. Treat the current worktree as authoritative, but distinguish uncommitted changes from epic artifacts.
- Epic source briefs live in .megaplan/briefs/reigh-extension-layer-epic/: chain.yaml and m0 through m15 markdown files.

Review lens:
UX/runtime surface means what an extension author and editor user can actually see and use: provider-scoped runtime activation, toolbar/header/panels/dialogs/status/diagnostics surfaces, inspectors, overlays, schema forms, code/writing/stage panels, picker/inspector flows for effects/transitions/shaders/clip types, extension manager, visible empty/loading/error/disabled states, accessibility/keyboard posture, and whether "implemented" primitives have real host affordances rather than hidden types.

Tasks:
1. Read the chain and milestone briefs enough to understand the intended end state.
2. Inspect current source/tests/docs relevant to extension UI/runtime surfaces.
3. Sense-check whether the visible/runtime layer appears to fulfill the epic, especially M2, M4, M7-M10, M13-M15.
4. Produce up to 10 granular follow-up "deep-dive spots" that deserve a more detailed DeepSeek-style audit.

Output format:
- Title: "UX/Runtime Surface Anchor Review"
- Short verdict: 3-6 bullets with confidence and key evidence.
- Anchor map: 5-8 bullets mapping epic UX/runtime goals to current files/tests/docs.
- Deep-dive spots: up to 10 numbered items. Each item must include:
  - Spot title
  - Why it matters to epic alignment
  - Exact files/paths to inspect first
  - Concrete questions to answer
  - Expected evidence/output from the next agent
  - Risk if ignored
- Be opinionated. Flag "paper APIs" where types exist but visible affordance or tests may be weak.
- Keep the final answer under 2500 words.
- Do not edit files.
