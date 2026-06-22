You are a Codex subagent reviewing the Reigh extension-layer epic from the CONTRACTS/API perspective.

Working directory:
/Users/peteromalley/Documents/reigh-workspace/reigh-app

Context:
- Epic name: reigh-extension-layer-epic
- Current branch: reigh-extension-layer-epic
- origin/main tip referenced by the human: b7a49a0c2 ("post-M15 sense-check fixes...")
- Current local HEAD may include extra uncommitted fixes. Treat the current worktree as authoritative, but distinguish uncommitted changes from epic artifacts.
- Epic source briefs:
  - .megaplan/briefs/reigh-extension-layer-epic/chain.yaml
  - .megaplan/briefs/reigh-extension-layer-epic/m0-workspace-scaffold.md
  - .megaplan/briefs/reigh-extension-layer-epic/m1-sdk-kernel.md
  - .megaplan/briefs/reigh-extension-layer-epic/m2-surfaces.md
  - .megaplan/briefs/reigh-extension-layer-epic/m3-timeline-patch.md
  - .megaplan/briefs/reigh-extension-layer-epic/m4-commands.md
  - .megaplan/briefs/reigh-extension-layer-epic/m5-registry-foundation.md
  - .megaplan/briefs/reigh-extension-layer-epic/m6-assets-astrid.md
  - .megaplan/briefs/reigh-extension-layer-epic/m7-component-effects.md
  - .megaplan/briefs/reigh-extension-layer-epic/m8-transitions.md
  - .megaplan/briefs/reigh-extension-layer-epic/m9-clip-types-keyframes.md
  - .megaplan/briefs/reigh-extension-layer-epic/m10-agent-tools.md
  - .megaplan/briefs/reigh-extension-layer-epic/m11-live-data-bridge.md
  - .megaplan/briefs/reigh-extension-layer-epic/m12-render-capabilities-sidecars.md
  - .megaplan/briefs/reigh-extension-layer-epic/m13-shader-webgl-bridge.md
  - .megaplan/briefs/reigh-extension-layer-epic/m14-packaging-loader-manager.md
  - .megaplan/briefs/reigh-extension-layer-epic/m15-hardening-docs.md

Review lens:
Contracts/API means public SDK exports, manifest schemas, contribution-kind contracts, type boundaries, compatibility/migration semantics, diagnostics schemas, TimelinePatch/TimelineOps contracts, renderability/capability contracts, package metadata, and tests that freeze public behavior.

Tasks:
1. Read the chain and enough milestone briefs to understand the intended end state.
2. Inspect current source/tests/docs relevant to contracts/API. Prefer `rg` and exact files over broad summaries.
3. Sense-check whether the implemented contract surface appears aligned with the epic. Be concrete and evidence-backed.
4. Produce up to 10 granular follow-up "deep-dive spots" that deserve a more detailed DeepSeek-style audit. Each spot should be narrow enough for one subagent to investigate in 30-90 minutes.

Output format:
- Title: "Contracts/API Anchor Review"
- Short verdict: 3-6 bullets with confidence and key evidence.
- Anchor map: 5-8 bullets mapping epic goals to current files/tests/docs.
- Deep-dive spots: up to 10 numbered items. Each item must include:
  - Spot title
  - Why it matters to epic alignment
  - Exact files/paths to inspect first
  - Concrete questions to answer
  - Expected evidence/output from the next agent
  - Risk if ignored
- Keep the final answer under 2500 words.
- Do not edit files.
