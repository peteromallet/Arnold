Video editor developer platform Sprint 4: clip-type plugin registry and capability manifest.

Depends on Sprints 1-3:
Use canonical timeline types, command facade, and core/adapter boundary.

Goal:
Make clip behavior extension-oriented. Developers and agents should be able to discover clip types, schemas, inspectors, render capability, and defaults through registration descriptors.

Primary outcomes:
- Define defineClipType({ id, paramsSchema, defaults, render, Inspector, timelineDisplay, resize, drag, commands, renderCapabilities }).
- Migrate built-in clip types into descriptors where feasible: media/visual, audio, text, effect-layer.
- Centralize clip-type dispatch in renderer/overlay/inspector through the registry.
- Add a machine-readable capability manifest that lists clip types, commands, params schemas, render routes, and known limitations.
- Add one example third-party-style clip type, such as title-card, to prove the API.

Important constraints:
- Avoid breaking existing persisted clip configs.
- Do not overfit the registry to Reigh-specific workflows.
- Existing editor UI remains working.

Success criteria:
- Adding a simple new clip type requires one descriptor plus registration and tests, not edits across unrelated switch sites.
- Agents can inspect the manifest and determine required params and legal commands for a clip type.
