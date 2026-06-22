You are a DeepSeek subagent doing adversarial review of the Reigh extension-layer foundation plan.

Working directory: /Users/peteromalley/Documents/reigh-workspace/reigh-app

Task: Inspect the current code and docs. Do not trust the plan files. Focus only on contract drift between public exports, runtime validators, JSON schema, docs, examples, tests, and contribution-family support.

Relevant starting points:
- src/tools/video-editor/extension.ts
- src/tools/video-editor/runtime/contributionFamilies.ts
- src/tools/video-editor/runtime/extensionManifest.ts
- config/contracts/reigh-extension.schema.json
- docs/extensions
- examples/video-editor-extension
- .megaplan/briefs/reigh-extension-layer-foundation/m1-preview-truth-contract-freeze.md

Questions:
- What drift exists today?
- What should be canonical?
- What automated gate would catch future drift?

Return only:
## Findings
For each: Finding, Evidence with file path/line if possible, Why it matters, Required plan change, Severity.
## Verdict
One paragraph.
