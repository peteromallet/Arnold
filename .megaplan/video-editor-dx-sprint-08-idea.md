Video editor developer platform Sprint 8: API freeze, docs, and embed demo.

Depends on Sprints 1-7:
Treat prior APIs as candidate public surface and tighten them into an internal SDK.

Goal:
Make the developer experience discoverable, documented, and testable.

Primary outcomes:
- Add src/tools/video-editor/index.ts exporting only the supported public surface.
- Mark internals explicitly.
- Add docs for: mount full editor, build custom frontend, use timeline data, run commands, add clip type, add effect/sequence, swap persistence, add render provider/exporter, add panel.
- Add examples/embed-demo with in-memory DataProvider, local/file AssetResolver, no Supabase, no Reigh contexts.
- Add fixture timelines and acceptance tests for developer/agent workflows.

Important constraints:
- Do not expose unstable internals as public API just because current code imports them.
- Keep docs aligned with actual tests/examples.

Success criteria:
- A developer new to the repo can read one doc and add a custom clip type or custom shell in under an hour.
- An agent can inspect docs/manifests, create a custom clip in a fixture timeline, validate/dry-run/apply edits, and pass tests without importing internal files.
