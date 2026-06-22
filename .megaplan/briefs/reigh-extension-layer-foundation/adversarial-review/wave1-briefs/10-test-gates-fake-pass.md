You are a DeepSeek subagent doing adversarial review of the Reigh extension-layer foundation plan.

Working directory: /Users/peteromalley/Documents/reigh-workspace/reigh-app

Task: Inspect the current code, docs, and milestone briefs. Do not trust the plan files. Focus only on whether the planned acceptance gates could fake-pass while the actual extension foundation remains weak.

Relevant starting points:
- .megaplan/briefs/reigh-extension-layer-foundation
- docs/extensions/reigh-extension-layer-foundation-plan.md
- docs/extensions/reigh-extension-layer-roadmap-v2.md
- src/tools/video-editor
- supabase/functions/ai-timeline-agent
- examples/video-editor-extension

Questions:
- Which milestone criteria are too vague?
- What tests or golden fixtures must be explicit?
- What should be blocking vs non-blocking?

Return only:
## Findings
For each: Finding, Evidence with file path/line if possible, Why it matters, Required plan change, Severity.
## Verdict
One paragraph.
