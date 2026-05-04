Video editor developer platform Sprint 7: UI slots, theming, and panel registry.

Depends on Sprints 1-6:
Use headless core, ports, command bus, clip registry, and render pipeline hooks.

Goal:
Make the frontend easy to customize without forking the whole shell.

Primary outcomes:
- Add shell slots for header, toolbar, leftPanel, rightPanel, timelineFooter/statusBar, dialogs, asset panel, inspector panel.
- Add panel registry so developers can contribute panels and inspector sections.
- Audit hardcoded styling/colors and route through theme tokens where practical.
- Provide a minimal custom two-pane editor shell example.

Important constraints:
- Current Reigh shell remains the default.
- Do not make all panels generic at once if it creates churn; prioritize high-value extension points.

Success criteria:
- A developer can mount the core with a custom layout and reuse timeline/preview/inspector primitives.
- Common frontend tweaks do not require editing VideoEditorShell internals.
