# VibeComfy front-end decomposition plan

## Problem
`vibecomfy/comfy_nodes/web/vibecomfy_roundtrip.js` is still the effective boundary for most frontend behavior even after the existing extractions. It still owns graph normalization and intent-node repair, panel shell construction, settings/status polling, websocket event ingestion, executor progress heuristics, chat/session normalization, submit/apply/reject/rebaseline/undo workflows, diagnostics/report generation, and preview-diff/scoped-apply verification. That concentration is why fixes keep colliding.

## Observed subsystem map
- UI shell and mounting: `createAgentPanelShell`, launcher/sidebar setup, settings popover, issue modal, choose-engine overlay.
- Lifecycle/state machine: `PANEL_STATE` plus transitions already centralized in `agent_edit_lifecycle.js`.
- Executor flow: `submitAgentExecutor`, `buildExecutorProgressFromResult`, websocket phase handlers, progress animation.
- Agent-edit turn flow: `applyAgentCandidate`, `rejectAgentCandidate`, `postAgentRebaseline`, `undoLastApply`, batch-turn reconciliation, accept/reject payload normalization.
- Graph repair / intent decoration: serialization helpers, `decorateIntentNode`, `repairLiveIntentNodesFromCandidate`, dynamic IO relabeling, preview diff computation.
- Chat thread and history: thread rendering is partly extracted to `panel_thread.js`, but rehydrate/history/detail snapshots still live in the monolith.
- Settings / credentials / polling: duplicated in the monolith even though `agent_status_poller.js` already exists.
- Diagnostics / issue reporting / coding-agent prompt / rating: large standalone block in the monolith.
- Cross-cutting queue/apply verification: queue guard UI, scoped delta verification, rollback helpers.

## Target architecture
```text
vibecomfy_roundtrip.js
  bootstrap only: register extension, wire app/api, compose modules

state/infrastructure
  panel_runtime.js
  panel_scheduler.js
  agent_edit_lifecycle.js
  agent_edit_response_contract.js

presentation
  panel_shell.js
  panel_sections.js
  panel_thread.js
  panel_composer.js
  panel_overlay.js

domain/transport
  panel_history.js
  agent_turn_feed.js
  executor_progress.js
  panel_settings.js
  diagnostics_reporting.js
  intent_graph_adapter.js
  graph_apply_verifier.js
  agent_edit_api.js
  agent_edit_controller.js
```

## Module decisions and interfaces
- Keep `agent_edit_lifecycle.js` as the only lifecycle-state authority. Everything else feeds it payloads and fulfills returned obligations.
- Keep `agent_edit_response_contract.js` as the normalization layer for main edit responses.
- Keep `panel_thread.js` for DOM reconciliation only. It should receive normalized messages/snapshots, not fetch or websocket logic.
- Keep `panel_composer.js` presentational only.
- Keep `panel_overlay.js` as the drawer only; move diff/model prep elsewhere.
- Expand or rename `agent_status_poller.js` into `panel_settings.js`. It should export `refreshAgentStatus`, `routeStatusState`, `populateRouteSelect`, `persistAgentSettings`, `storeOpenRouterCredential`, `testAgentSettings`, `syncChooseEngineGate`.
- New `panel_shell.js`: `createAgentPanelShell`, `mount/open/closeAgentPanel`, `ensureAgentLauncher`, `ensureAgentSidebarTab`, DOM helpers. No domain state ownership.
- New `panel_sections.js`: render meta/settings/candidate/failure/queue/audit/debug/developer sections and `renderDirtyAgentPanelSections`.
- New `panel_history.js`: `normalizeChatRehydratePayload`, `normalizeChatMessagePayload`, `messageStableKey`, `resetThreadRenderState`, `upsertBatchTurn`, `reconcileResponseBatchTurns`, `pushTurnStatus`, `rememberTurnDetailSnapshot`, `detailSnapshotForMessage`, `buildSyntheticAgentMessage`. Owns `panel.state.turns`, `turnDetailSnapshots`, `threadState`.
- New `agent_turn_feed.js`: `ensureAgentTurnListener`, `handleAgentTurnEvent`, `handleExecutorPhaseEvent`, `shouldAcceptAgentTurnEvent`. Emits normalized callbacks; should not render directly.
- New `executor_progress.js`: `buildExecutorProgressFromResult`, `progressFromAgentTurnEvent`, `progressFromExecutorPhaseEvent`, `setExecutorProgress`, `executorProgressForPanel`, `runExecutorProgressAnimation`, `makeExecutorPendingMessage`.
- New `diagnostics_reporting.js`: `installBrowserDiagnosticsCapture`, `buildIssueReport`, `buildAgentSolvePrompt`, `collectIssueReportFiles`, `downloadIssueReportZip`, `submitRating`, `showIssueModal`, `buildCurrentAuditEnvelope`, `downloadCurrentAudit`.
- New `intent_graph_adapter.js`: move `normalizeForSerialize`, `normalizeForDisplay`, `normalizeForApply`, `repairLiveNodes`, `captureSerializedGraphForAgent`, `buildStructuralGraphProjection`, `structuralGraphHash`, `captureLiveCanvasToken`, `prepareCandidateGraphForPanel`, preview-diff helpers, intent-node decoration/repair.
- New `graph_apply_verifier.js`: `resolveScopedDeltaOps`, `normalizeScopedAcceptVerification`, `validateScopedCanvasPreconditions`, `verifyScopedCanvasResults`, `buildCanvasApplyVerificationDebug`, `buildInverseDeltaOps`, `attemptScopedCanvasRollback`.
- New `agent_edit_api.js`: fetch wrappers for executor submit, accept, reject, rebaseline, chat rehydrate, session bundle, credentials, rating.
- New `agent_edit_controller.js`: `submitAgentExecutor`, `stopAgentSubmit`, `newAgentConversation`, `applyAgentCandidate`, `rejectAgentCandidate`, `postAgentRebaseline`, `rebaselineCurrentCanvas`, `undoLastApply`, plus lifecycle-obligation fulfillment.

## Migration sequence
1. Freeze contracts first. Capture fixtures for `/vibecomfy/agent-executor`, `/vibecomfy/agent/status`, websocket events, accept/reject/rebaseline responses, chat rehydrate, and session bundle. Add tests around normalizers before moving code.
2. Extract diagnostics first into `diagnostics_reporting.js`. It is large, mostly independent, and immediately testable.
3. Move status/settings/credential logic into the existing `agent_status_poller.js` path and stop duplicating it in the monolith.
4. Extract websocket feed and executor progress into `agent_turn_feed.js` and `executor_progress.js`. This is the slice most directly tied to the recurring progress-row regressions.
5. Split chat/session state from thread rendering by creating `panel_history.js` and leaving `panel_thread.js` as DOM-only.
6. Extract `agent_edit_api.js` and `agent_edit_controller.js`, then move submit/apply/reject/rebaseline/undo workflows out of the entry file.
7. Extract `intent_graph_adapter.js` and `graph_apply_verifier.js` last, because they are high-risk canvas mutation surfaces.
8. Finish with `panel_shell.js` and `panel_sections.js`, leaving `vibecomfy_roundtrip.js` as bootstrap only.

## Verification per phase
- Browser smoke after each phase: open via launcher and sidebar, load settings, submit clarify/noop/candidate/failure flows, apply/reject/undo/rebaseline, reload and restore candidate/history, export issue report.
- Add tripwire tests for the known repeat offenders: executor progress row correctness, delete/apply around dynamic IO code nodes, coding-agent prompt completeness, stale-canvas apply producing rebaseline recovery instead of silent disable.

## ComfyUI JS caching
Because `WEB_DIRECTORY = "./web"` serves static ESM files directly, changing only `vibecomfy_roundtrip.js` is not enough. Child imports like `./panel_thread.js` will still be cached independently.
- Recommended: generate `web_dist/` in a build step and rewrite every relative import and asset URL to include the same build id, for example `?v=<git-sha-or-content-hash>`.
- Use the same build id on images resolved via `import.meta.url`.
- Point `WEB_DIRECTORY` at `web_dist` for shipped assets.
- Do not rely on ComfyUI to invalidate child ESM imports automatically.

## Backend changes that make the split cleaner
- Make dedicated, documented routes first-class for accept, reject, rebaseline, chat rehydrate, and session bundle. The frontend already assumes them.
- Generate schemas for executor response, executor phase websocket event, agent-edit turn websocket event, status response, chat rehydrate response, session bundle response, and accept/reject/rebaseline responses, not just main edit responses.
- Make executor progress first-class instead of inferred from timers plus two websocket channels. Include stable `executor_id`, `session_id`, `turn_id`, `phase`, `status`, `sequence`, `emitted_at`.
- Return or bind `session_id` earlier so the frontend does not need the current “drop first events until a session is known” heuristic.
- Version the scoped-apply verification payload so `graph_apply_verifier.js` can be deterministic.
- Keep `/vibecomfy/agent/status` schema stable and explicit about route options, resolved route/model, credential presence, and provider availability.

## Recommended immediate first step
Create the safety rails, then take the easiest high-value slice:
- add fixture-backed payload tests
- extract `diagnostics_reporting.js`
- then move status/settings code into the existing `agent_status_poller.js` path
