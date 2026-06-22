You are a DeepSeek subagent doing second-wave adversarial review.

Working directory: /Users/peteromalley/Documents/reigh-workspace/reigh-app

Context: Wave one claimed proposal policy is not enforced end to end: frontend omits it on first invoke, backend ignores it, edge response discards proposal data, some tools bypass proposal mode, and proposal persistence does not exist.

Task: Independently verify whether those claims are true and propose the minimum plan changes needed. Do not accept wave-one claims blindly.

Inspect:
- src/tools/video-editor/hooks/useAgentSession.ts
- supabase/functions/ai-timeline-agent/index.ts
- supabase/functions/ai-timeline-agent/loop.ts
- supabase/functions/ai-timeline-agent/tools/registry.ts
- src/tools/video-editor/commands
- .megaplan/briefs/reigh-extension-layer-foundation/m3-proposal-agent-policy-spine.md

Return:
## Confirmed
## Rejected Or Overstated
## Required Plan Changes
Keep it under 900 words.
