Video editor developer platform Sprint 3: headless core and Reigh adapter shell.

Depends on Sprints 1-2:
Use the canonical domain layer and ports/command facade from prior sprints. Do not reintroduce direct Reigh app-context dependencies into the core.

Goal:
Create a headless/core editor composition that can mount with stub ports, while keeping the current Reigh editor behavior via a Reigh adapter shell.

Primary outcomes:
- Introduce a TimelineEditorCore/CoreProvider that takes ports as props and avoids direct Reigh domain/shared imports except stable UI primitives if still needed.
- Introduce ReighTimelineEditor/ReighVideoEditorShell that wires ShotsContext, ProjectContext, MediaLightbox, AgentChat, router behavior, and current workflow affordances into the core.
- Move workflow logic out of TimelineEditor.tsx/VideoEditorProvider.tsx where it is Reigh-specific.
- Add a smoke test or demo harness that mounts the core with stub ports and in-memory data.

Important constraints:
- The existing app route must remain functionally equivalent.
- Avoid full UI slot work; Sprint 7 owns layout customization.
- Avoid full plugin registry work; Sprint 4 owns clip-type extension.

Success criteria:
- Core editor can mount without Reigh project/shots/media-lightbox/agent-chat contexts.
- Reigh app uses the adapter shell and remains working.
- Remaining direct host dependencies in core are documented as follow-up items.
