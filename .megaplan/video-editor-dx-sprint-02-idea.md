Video editor developer platform Sprint 2: ports, adapters, and early command facade.

Depends on Sprint 1:
Start by reading the Sprint 1 final notes/artifacts. Preserve its canonical domain boundary and use its exported helpers rather than creating parallel timeline interpretation logic.

Goal:
Name and isolate every Reigh host dependency used by the video editor, while introducing an early public command facade so developers and agents can mutate timelines without touching rows/meta/clipOrder internals.

Primary outcomes:
- Formalize DataProvider as a stable port and add related host ports where needed: AssetResolver, ShotsHost, ProjectHost, MediaLightboxHost, AgentChatHost, Toast/Telemetry/Auth.
- Split Reigh-specific implementations into adapter files.
- Add an early command facade over existing mutation internals: addClip, updateClip, moveClip, trimClip, splitClip, deleteClip, addTrack, moveTrack, registerAsset, setClipParams.
- Commands should validate through the Sprint 1 domain layer and return structured errors where practical.
- Keep undo/redo internals unchanged unless a small adaptation is needed; full command stack is Sprint 5.

Important constraints:
- Do not change visible Reigh editor behavior.
- Do not complete the full headless core split in this sprint; prepare for it.
- Do not expose raw internal mutation helpers as the recommended API.
- Existing tests must pass; add focused tests for ports and command facade behavior.

Success criteria:
- A developer can import a documented command facade and perform common timeline edits without direct rows/meta/clipOrder mutation.
- Reigh-specific external dependencies are named and concentrated behind adapter boundaries, with remaining direct imports documented.
- The work sets up Sprint 3 to mount a core editor with stub ports.
