# Agentic Replay Viewer

## Purpose

We want a demo surface inside the Comfy/VibeComfy frontend for replaying agentic
test runs. It should let a user choose a batch of agentic tests, choose an
individual test/check, and move backward or forward through the user-visible
states of that test.

This is not the same thing as normal chat rehydration. Chat rehydration restores
a real conversation history. The replay viewer should project recorded artifacts
into a small set of demo-friendly states and hide internal model/debug chatter by
default.

## Has This Already Been Built?

Partially.

We have most of the raw ingredients, but not the complete demo UX.

Already built:

- Agentic harness outputs under `out/agentic/<run-tag>/<scenario-id>/`.
- Batch/run summaries under `out/agentic/` such as run summary JSON files.
- Durable editor-session artifacts under `out/editor_sessions/<session>/turns/<turn>/`.
- Comfy agent panel chat rehydration from `out/editor_sessions`.
- Session inspection endpoints:
  - `GET /vibecomfy/agent-edit/chat`
  - `GET /vibecomfy/agent-edit/session-json`
  - `GET /vibecomfy/agent-edit/session-bundle`
- A dev/demo picker in `vibecomfy/comfy_nodes/web/preview_picker.js`.
- Demo-mode frontend state projection that can populate the panel with a user
  message, agent reply, candidate graph, and local Apply/Reject behavior.

Not yet built:

- A frontend selector for agentic test runs/batches.
- A frontend selector for individual tests/checks inside a run.
- A normalized replay-stage model.
- Left/right keyboard navigation through replay stages.
- A backend endpoint that lists `out/agentic` runs.
- A backend endpoint that lists tests/checks inside an agentic run.
- A backend endpoint that returns sanitized, demo-ready replay data.
- A bridge that consistently maps `out/agentic` evidence into Comfy panel
  replay state.

## Existing Artifact Shapes

### Agentic Run Evidence

The live agentic harness writes per-scenario evidence to:

```text
out/agentic/<run-tag>/<scenario-id>/
```

Common files include:

- `request.json`: headless agent request, including query and graph/context.
- `response.json`: full executor response, often large and internal.
- `flow_metadata.json`: run metadata and readiness/status.
- `classification.json`: route/intent/classification evidence.
- `research.json`: research evidence when present.
- `implementation_payload.json`: payload sent to implementation.
- `implementation_result.json`: implementation outcome.
- `agentic_summary.json`: per-scenario summary, guard/check status, failure
  class, and score class when present.

The batch/run-level summaries are generally under `out/agentic/` and encode run
status, scenario counts, and per-scenario outcomes.

### Editor Sessions

The Comfy frontend already knows how to rehydrate:

```text
out/editor_sessions/<session-id>/
  session_state.json
  turns/<turn-id>/
    request.json
    response.json
    chat.json
    candidate.ui.json
    original.ui.json
    model_request.json
    model_response.json
    messages.jsonl
```

This shape supports real panel continuity and candidate Apply/Reject lifecycle.

### Current Gap Between Them

`out/agentic` is organized by test run and scenario. `out/editor_sessions` is
organized by frontend session and turn. Some agentic outputs contain references
back to durable editor-session artifacts, but this is not currently exposed as a
stable replay API.

The replay viewer should treat `out/agentic` as the test-run index and use
editor-session artifacts opportunistically when they are available.

## Proposed UX

Name: **Agentic Replay**.

Primary controls:

```text
Run:    <agentic batch/run selector>
Test:   <scenario selector>
Check:  <guard/check selector>
Stage:  Sent | Thinking | Ready to apply | Applied
```

Keyboard:

- Left/right arrows move between replay stages.
- Up/down or selector changes test, if the replay panel has focus.
- Enter can load the selected test.

The panel should show only frontend-visible messages by default:

1. **Sent**
   - Show only the user's message.
   - Canvas shows the original graph.

2. **Thinking**
   - Show user's message plus the normal pending/loading assistant state.
   - Canvas still shows the original graph.

3. **Ready to Apply**
   - Show user message and final assistant reply.
   - Show candidate pending application.
   - Canvas can show candidate graph or candidate preview.

4. **Applied**
   - Show the accepted/applied state.
   - Canvas shows the candidate/applied graph.

Internal data such as `batch_turns`, model prompts, diagnostics, and research
logs should stay behind a developer details disclosure.

## Proposed Backend API

Add routes alongside the agent-edit/demo routes:

```text
GET /vibecomfy/agentic-replay/runs
GET /vibecomfy/agentic-replay/runs/{run_id}/tests
GET /vibecomfy/agentic-replay/runs/{run_id}/tests/{scenario_id}
```

### `GET /vibecomfy/agentic-replay/runs`

Returns available agentic runs from `out/agentic`.

Example shape:

```json
{
  "ok": true,
  "runs": [
    {
      "run_id": "agentic-100-20260630T231158Z",
      "label": "agentic-100-20260630T231158Z",
      "scenario_count": 100,
      "passed": 82,
      "failed": 18,
      "created_at": "2026-06-30T23:11:58Z"
    }
  ]
}
```

### `GET /vibecomfy/agentic-replay/runs/{run_id}/tests`

Returns scenarios/checks for one run.

Example shape:

```json
{
  "ok": true,
  "run_id": "agentic-100-20260630T231158Z",
  "tests": [
    {
      "scenario_id": "hotshot-16-frames-agent-edit",
      "title": "Hotshot 16 frames agent edit",
      "status": "passed",
      "failure_class": null,
      "score_class": "success",
      "checks": [
        {"id": "guard", "label": "Guard", "status": "passed"},
        {"id": "intent", "label": "Intent", "status": "passed"}
      ]
    }
  ]
}
```

### `GET /vibecomfy/agentic-replay/runs/{run_id}/tests/{scenario_id}`

Returns sanitized replay data for one scenario.

Example shape:

```json
{
  "ok": true,
  "run_id": "agentic-100-20260630T231158Z",
  "scenario_id": "hotshot-16-frames-agent-edit",
  "query": "Make the Hotshot workflow generate 16 frames.",
  "reply": "I updated the workflow to generate 16 frames.",
  "status": "passed",
  "checks": [
    {"id": "guard", "label": "Guard", "status": "passed"}
  ],
  "graphs": {
    "original": {},
    "candidate": {}
  },
  "stages": [
    {
      "id": "sent",
      "label": "Sent",
      "messages": [
        {"role": "user", "text": "Make the Hotshot workflow generate 16 frames."}
      ],
      "graph_ref": "original",
      "panel_phase": "IDLE"
    },
    {
      "id": "thinking",
      "label": "Thinking",
      "messages": [
        {"role": "user", "text": "Make the Hotshot workflow generate 16 frames."},
        {"role": "agent", "pending_response": true}
      ],
      "graph_ref": "original",
      "panel_phase": "SUBMITTING"
    },
    {
      "id": "ready_to_apply",
      "label": "Ready to apply",
      "messages": [
        {"role": "user", "text": "Make the Hotshot workflow generate 16 frames."},
        {"role": "agent", "text": "I updated the workflow to generate 16 frames."}
      ],
      "graph_ref": "candidate",
      "panel_phase": "AWAITING_REVIEW"
    },
    {
      "id": "applied",
      "label": "Applied",
      "messages": [
        {"role": "user", "text": "Make the Hotshot workflow generate 16 frames."},
        {"role": "agent", "text": "I updated the workflow to generate 16 frames."}
      ],
      "graph_ref": "candidate",
      "panel_phase": "IDLE",
      "applied": true
    }
  ]
}
```

## Proposed Frontend Implementation

Reuse the dev/demo picker pattern, but keep the new viewer separate from
`preview_picker.js`:

```text
vibecomfy/comfy_nodes/web/agentic_replay_picker.js
```

Gating:

```js
localStorage["vibecomfy_agentic_replay_enabled"] === "1"
```

Panel state projection should be pure and testable:

```js
projectReplayStageToPanel(panel, replayPayload, stageIndex)
```

For each stage:

- Set `panel.state.chatMessages` to the stage's sanitized messages.
- Mirror to `panel.state.transcriptMessages`.
- Set `panel.state.phase` from `stage.panel_phase`.
- Set or clear `candidateGraph`, `candidateGraphHash`, `applyEligibility`,
  `applyAllowed`, `canvasApplyAllowed`, and `queueAllowed`.
- Apply the referenced graph to canvas using existing Comfy adapter helpers.
- Mark replay mode using a flag such as `panel.state.__agenticReplayMode = true`.
- Schedule render for thread, meta, and candidate sections.

The existing `__demoMode` machinery is useful but should not be overloaded
without thought. Agentic Replay is closer to deterministic artifact playback
than a single curated demo scenario.

## MVP

Build the smallest useful version:

1. Backend run listing from `out/agentic`.
2. Backend test listing for a selected run.
3. Backend single-test replay projection with four fixed stages:
   - Sent
   - Thinking
   - Ready to apply
   - Applied
4. Frontend replay toolbar with run selector, test selector, stage buttons, and
   left/right keyboard navigation.
5. Projection into existing panel thread and candidate state.

## Later Enhancements

- Check-level filtering and navigation.
- Pass/fail/failure-class filters.
- Modality filters: image, video, audio, 3D, multi.
- Curated demo playlists.
- Auto-advance/slideshow mode.
- Side-by-side original/candidate graph view.
- Changed-node highlighting.
- Developer details drawer for diagnostics, batch turns, model request/response,
  research, and guard evidence.
- A converter that promotes selected `out/agentic` scenarios into durable
  `out/editor_sessions` replay fixtures.

## Risks

- `response.json` can be very large. The replay API should not send raw
  responses to the browser.
- `out/agentic` schemas are less frontend-stable than `out/editor_sessions`.
  The backend should normalize them into a small replay schema.
- Some failed or early-aborted scenarios will not have candidate graphs.
  The viewer must still show Sent/Thinking/failure states gracefully.
- Canvas projection is destructive if it writes to the live Comfy canvas. The UI
  should make replay mode explicit and avoid surprising users who have work open.
- Comfy may use arrow keys elsewhere. Keyboard handlers should be scoped to the
  replay panel and stop propagation only while the replay UI has focus.

## Recommended Build Order

1. Implement backend read-only discovery and projection endpoints.
2. Add unit tests for run discovery and single-test replay projection.
3. Add frontend replay picker module, gated by localStorage.
4. Add browser tests for selector loading and stage projection.
5. Add one Playwright smoke test against a seeded artifact run.
6. Polish with filters, check selection, and developer details.

