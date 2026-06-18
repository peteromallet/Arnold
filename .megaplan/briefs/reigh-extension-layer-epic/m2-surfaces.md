# M2: Surfaces, Inspectors, Overlays, Subscriptions

## Outcome

Turn the initial runtime into a complete UI contribution system: static slots, inspector sections, timeline overlays, host-driven subscriptions, responsive/device signals, accessibility hooks, and polished containment.

## Execution Posture

Host coherence beats extension freedom here. UI contributions should feel native, contained, accessible, diagnosable, and calm; do not let each extension invent its own diagnostics, form language, or control center.

## Scope

IN:
- Formalize `SurfaceContribution` for toolbar, header, panels, asset panel, code panel, reserved writing/source panel placement, reserved canvas/stage preview placement, footer, status bar, and dialogs.
- Add dedicated `InspectorContribution` with host-supplied selection props.
- Add `TimelineOverlayContribution` with viewport and interaction policy props.
- Add `playback.subscribe`, `selection.subscribe`, `timeline.subscribe`, and `chrome.subscribe`.
- Add responsive/device runtime signals.
- Add `chrome.focus()` and `chrome.announce()`.
- Add `Diagnostic` and `DiagnosticCollection` for user-authored code, compiler output, and extension health messages.
- Add a host-owned `DiagnosticPanel` reachable from status bar/diagnostic fallback links.
- Add a skeletal host-owned extension status drawer/panel reachable from diagnostics/status surfaces. It lists active extensions, contribution counts, failed/disabled contributions, diagnostics, and export/render blockers. It is not the full M14 manager.
- Add a host-owned `SchemaForm` primitive for shared form rendering across extension params, command/tool inputs, keyframes, transition params, live-source settings, and shader uniforms.
- Add a host-owned schema capability registry for `SchemaForm`: supported widget types, unsupported diagnostics, layout hints, validation path mapping, and host-approved custom widget slots that later milestones can extend without bespoke form systems.
- Reserve frontend extension points and host-owned component slots that later milestones can activate without inventing new placement rules: material browser/detail surfaces, generation/session panel, export planner/config shell, asset detail sections, process result panel, recording strip, mapping table, sidecar preview panel, and timeline segment/cue editing widgets.
- Add code-panel affordance contracts for language-like extensions: source ranges, diagnostics-to-editor mapping, save/dirty state, and optional live-compile hooks. The host need not own every editor implementation, but the diagnostics/source mapping contract must be stable.
- Add writing/script reserved affordance contracts as a named use of the code/source panel model: source document identity, dirty/save state posture, diagnostics, source maps, compile/propose actions, and links to affected timeline/assets/materials when applicable. M2 proves placement and diagnostics; mature script authoring is deferred.
- Add canvas/stage reserved affordance contracts for spatial primitives: host-owned preview containment, coordinate space vocabulary, selection projection posture, gesture ownership, empty/error/disabled states, and optional timeline binding for timed composition. M2 proves placement and containment; mature direct-manipulation tooling is deferred.
- Add visible diagnostics for failed or disabled UI contributions.
- Add examples for toolbar, inspector, overlay, status surface, and code panel diagnostics.
- Establish the frontend closure checklist used by later milestones: each new public primitive must name its host surface, empty/loading/error/disabled states, diagnostic fallback, accessibility behavior, and test path before it is treated as done.

OUT:
- Runtime slot reordering.
- View-menu hide/show preferences.
- Extension manager UI.
- Install/uninstall/settings manager behavior beyond the skeletal status drawer.
- Custom gesture/drag primitives beyond overlay interaction policy.

## Locked Decisions

- V1 surfaces are statically assigned by contribution descriptors.
- `codePanel` is committed in this milestone. It is not optional.
- Inspector render receives selection from the host, avoiding polling.
- Overlays respect timeline interaction ownership and must not steal gestures by default.
- Public first slots are `toolbar`, `header`, `leftPanel`, `rightPanel`, `assetPanel`, `codePanel`, `writingPanel`, `stagePanel`, `timelineFooter`, `statusBar`, and `dialogs`.
- Failed contributions render a compact accessible fallback with the contribution label, extension ID, and a link/action to diagnostics.
- DSL/code-panel extensions own their editor widget, but the host owns diagnostic publication and display primitives.
- `codePanel` receives `ExtensionContext`, `DiagnosticCollection`, and extension-scoped draft persistence via settings/local storage. It does not receive filesystem or project-source access.
- `writingPanel` follows the same containment model as `codePanel` but is explicitly reserved for user-facing script/prompt/shot-list/source workflows. M2 may ship an inert/canary panel with diagnostics and source range display; it is not required to implement full document persistence or emit timeline proposals.
- `stagePanel` is a host-contained spatial preview/direct-manipulation surface. M2 may ship an inert/canary panel with explicit empty/error/disabled states; it does not own timeline gestures unless the host grants interaction policy. Full coordinate editing, lasso, masks, and scene graph behavior remain deferred until a milestone activates them.
- `codePanel` source diagnostics use the same 1-based range model as `Diagnostic`; language extensions can map compiler errors to editor markers without private editor APIs.
- `DiagnosticPanel` groups diagnostics by extension/contribution, filters by severity, and supports source range display for code-panel/compiler errors.
- The skeletal extension status drawer is read-only except for navigation/filter actions. Enable/disable, install, uninstall, and settings editing remain M14.
- `Diagnostic` source ranges are explicit and 1-based: `{ startLine, startCol, endLine, endCol }`; editor integrations may render squiggles/gutters, but raw range data remains available to extensions.
- `SchemaForm` handles the common subset: string, number, boolean, enum/select, and color. Unsupported schema types render a diagnostic placeholder with the unsupported type name; they do not silently disappear or crash.
- `SchemaForm` accepts existing `ParameterSchema` plus the `StandardSchema` subset used by agent tools. Milestones needing richer widgets must state the type in scope or defer it explicitly.
- Richer schema widgets, including vector, texture reference, frame binding, process env, and live-source settings controls, must register through the schema capability registry rather than bypassing `SchemaForm`.
- Shared workflow widgets are host-owned where consistency matters: proposal diff view, context preview, material detail, provenance chain, search result badge, enrichment claim detail, mapping table, learn-mode indicator, and export dry-run table. Later milestones may activate them incrementally, but they must not appear as incompatible per-extension dashboards.
- Canvas/stage and writing/script widgets are first-class reserved frontend primitives, not ad hoc dashboards. Later milestones can enrich them, but M2 should not build mini-apps for them. Their placement, diagnostics, accessibility, and lifecycle follow the same closure checklist as timeline-facing primitives.
- `TimelineOverlayContribution.interactionPolicy` exposes a minimal stable projection: current gesture owner, whether timeline pointer/scroll is claimed, and whether overlay pointer events are allowed. Custom gesture APIs remain out of scope.
- `SelectionSnapshot` starts as `{ kind, clipIds, trackId, timeRange? }`; lasso/range-edit semantics are reserved.
- `chrome.focus(selector)` is scoped to the editor shell container, not `document`; not-found/portal targets emit diagnostics.

## Constraints

- UI must remain coherent on desktop and mobile viewport sizes.
- No contribution should force repeated full editor re-renders for playhead changes.
- All render callbacks must be isolated by extension/contribution ID.
- Shared form controls must have stable labels, validation states, disabled states, and diagnostics so later milestones do not reinvent incompatible schema rendering.
- Later milestones may add richer surfaces, but they inherit M2's closure checklist; SDK-only primitives are not frontend-complete until their host affordance and diagnostics are visible.

## Done Criteria

- Example extensions demonstrate every public surface class.
- Subscriptions have cleanup tests and avoid leaked listeners.
- Inspector and overlay contributions update on real host state changes.
- Accessibility labels and announcements are testable.
- Diagnostics can represent source ranges for compiler/user-authored-code errors.
- `SchemaForm` renders and validates the common schema subset and reports unsupported schema types as diagnostics.
- Schema capability registry tests cover supported widgets, unsupported diagnostics, validation paths, and a host-approved custom widget placeholder.
- Diagnostic fallback links open `DiagnosticPanel` filtered to the failing extension/contribution.
- Extension status drawer shows active extension IDs, contribution inventory, diagnostics, and current blockers without becoming an install/settings manager.
- Code panel example publishes a syntax error diagnostic and shows it in the diagnostic panel.
- Code panel example proves source range diagnostics can be rendered in a contributed editor and linked from the diagnostic panel.
- Frontend closure checklist is documented and used by at least one example primitive.
- Reserved frontend component slots compile as inert placeholders or documented deferred rows so later milestones can wire behavior without changing the surface taxonomy.
- Writing/script and canvas/stage canaries demonstrate that an extension can expose a non-timeline-native workflow with diagnostics and visible state before it optionally produces a timeline proposal. They should stay intentionally small.

## Touchpoints

- `TimelineEditorShellCore`
- Properties/asset panels
- Timeline canvas/editor components
- Runtime contexts and SDK types
