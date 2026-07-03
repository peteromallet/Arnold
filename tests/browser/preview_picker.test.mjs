import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";
import {
  PANEL_STATE,
  RENDER_SECTIONS,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

const LS_DEMO_PICKER_ENABLED = "vibecomfy_demo_picker_enabled";

function waitFor(predicate, { attempts = 50 } = {}) {
  return new Promise((resolve, reject) => {
    let index = 0;
    function tick() {
      if (predicate()) {
        resolve();
        return;
      }
      if (index >= attempts) {
        reject(new Error("waitFor timed out"));
        return;
      }
      index += 1;
      setTimeout(tick, 0);
    }
    tick();
  });
}

function makeScenarioResponse(overrides = {}) {
  return {
    status: 200,
    body: {
      ok: true,
      scenario: {
        id: "demo_a",
        title: "Demo A",
        query: "Add a demo node",
      },
      original_graph: {
        nodes: [{ id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } }],
        links: [],
      },
      candidate_graph: {
        nodes: [
          { id: 1, type: "Input", properties: { vibecomfy_uid: "uid-1" } },
          { id: 2, type: "Output", properties: { vibecomfy_uid: "uid-2" } },
        ],
        links: [],
      },
      agent_reply: "I added a demo node for you.",
      session_id: "demo-sess-a",
      turn_id: "demo-turn-a",
      eligibility: { applyable: true, reason: "applyable" },
      change_details: {
        summary: "Added a demo output node.",
        statements: [{ op_kind: "add_node", message: "Added Output node" }],
      },
      ...overrides,
    },
  };
}

function makeScenarioList() {
  return {
    status: 200,
    body: {
      ok: true,
      scenarios: [
        { id: "demo_a", title: "Demo A" },
        { id: "demo_b", title: "Demo B" },
      ],
    },
  };
}

function makeStatusResponse() {
  return {
    status: 200,
    body: {
      ready: true,
      requested_route: "auto",
      route: "auto",
      provider_available: true,
      route_options: {
        auto: { label: "Auto", models: [] },
        deepseek: { label: "DeepSeek", models: [] },
      },
    },
  };
}

function makePanelState() {
  return {
    chatMessages: [],
    transcriptMessages: [],
    expandedBubbleTurnKeys: {},
    responseDetails: {},
    undoStack: [],
    history: [],
  };
}

// ── Isolation tests for the preview picker module ───────────────────────────

test("disabled picker returns null and emits no UI or network traffic", async () => {
  const harness = await createBrowserHarness();
  try {
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const result = picker.installPreviewPicker({ shell });
    assert.equal(result, null, "installPreviewPicker should return null when disabled");
    assert.equal(shell.children.length, 0, "picker should not mount DOM when disabled");
    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/demo/scenarios"),
      "disabled picker should not fetch scenarios",
    );
  } finally {
    await harness.dispose();
  }
});

test("enabled picker fetches the scenario list and renders the toolbar", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const controls = picker.installPreviewPicker({ shell }, { headerRight });
    assert.ok(controls, "installPreviewPicker should return controls when enabled");
    await waitFor(() => controls.select.children.length > 1);

    assert.ok(
      harness.requests.some((r) => r.url === "/vibecomfy/demo/scenarios"),
      "enabled picker should fetch /vibecomfy/demo/scenarios",
    );
    assert.equal(controls.select.children[0].value, "", "first option is placeholder");
    assert.equal(controls.select.children[1].value, "demo_a", "second option is demo_a");
    assert.equal(controls.select.children[2].value, "demo_b", "third option is demo_b");
    assert.equal(headerRight.children.length, 1, "toggle button is placed in headerRight");
    assert.equal(headerRight.children[0].textContent, "▦ Demo", "toggle button label");
    assert.equal(controls.container.style.display, "none", "picker toolbar starts hidden");
  } finally {
    await harness.dispose();
  }
});

test("Load & Play replays transcript and populates AWAITING_REVIEW candidate state", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const headerRight = harness.document.createElement("div");
    const appliedGraphs = [];
    const scheduledRenders = [];
    const panel = {
      shell,
      state: makePanelState(),
    };
    const controls = picker.installPreviewPicker(panel, {
      headerRight,
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: (appArg, graph, opts) => {
          appliedGraphs.push({ app: appArg, graph, opts });
        },
        scheduleRenderAgentPanel: (reason, p, sections) => {
          scheduledRenders.push({ reason, panel: p, sections });
        },
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
    });
    await waitFor(() => controls.select.children.length > 1);

    controls.select.value = "demo_a";
    controls.select.dispatchEvent({ type: "change", target: controls.select });
    assert.equal(controls.loadButton.disabled, false, "load button enabled after selection");

    controls.loadButton.click();
    await waitFor(() => controls.loadButton.textContent === "Load & Play" && !controls.loadButton.disabled);

    assert.equal(appliedGraphs.length, 1, "original graph was applied to the canvas");
    assert.equal(appliedGraphs[0].graph.nodes.length, 1, "original graph has one node");

    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "phase is AWAITING_REVIEW");
    assert.equal(panel.state.__demoMode, true, "__demoMode flag is set");
    assert.equal(panel.state.sessionId, "demo-sess-a", "session id populated");
    assert.equal(panel.state.turnId, "demo-turn-a", "turn id populated");
    assert.ok(panel.state.candidateGraph, "candidate graph populated");
    assert.equal(panel.state.applyAllowed, true, "apply allowed when eligible");
    assert.equal(panel.state.canvasApplyAllowed, true, "canvas apply allowed when eligible");
    assert.equal(panel.state.queueAllowed, false, "queue stays disabled for demo");
    assert.equal(panel.state.applyEligibility?.reason, "applyable", "eligibility reason stored");
    assert.equal(
      panel.state.expandedBubbleTurnKeys["turn:demo-turn-a"],
      true,
      "agent bubble details auto-expanded",
    );

    assert.equal(panel.state.chatMessages.length, 2, "two transcript messages");
    assert.equal(panel.state.chatMessages[0].role, "user", "first message is from user");
    assert.equal(panel.state.chatMessages[0].text, "Add a demo node", "user message text is query");
    assert.equal(panel.state.chatMessages[1].role, "agent", "second message is from agent");
    assert.equal(
      panel.state.chatMessages[1].text,
      "I added a demo node for you.",
      "agent message text is reply",
    );
    assert.deepEqual(panel.state.transcriptMessages, panel.state.chatMessages, "transcript mirrors chat");
    assert.equal(panel.state.changeDetails.summary, "Added a demo output node.", "change details stored");

    assert.equal(scheduledRenders.length, 1, "render scheduled once");
    assert.equal(scheduledRenders[0].reason, "demo-picker");
    assert.ok(scheduledRenders[0].sections.includes(RENDER_SECTIONS.THREAD));
    assert.ok(scheduledRenders[0].sections.includes(RENDER_SECTIONS.CANDIDATE));
  } finally {
    await harness.dispose();
  }
});

test("non-applyable eligibility disables apply/canvasApply while still expanding details", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_b": makeScenarioResponse({
        id: "demo_b",
        eligibility: { applyable: false, reason: "server_blocked", message: "Blocked by server" },
      }),
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    const picker = await harness.loadPreviewPicker();
    const shell = harness.document.createElement("div");
    const panel = { shell, state: makePanelState() };
    const controls = picker.installPreviewPicker(panel, {
      helpers: {
        app: harness.app,
        applyGraphCandidateInPlace: () => {},
        scheduleRenderAgentPanel: () => {},
        currentAgentPanel: () => panel,
        PANEL_STATE,
        RENDER_SECTIONS,
      },
    });
    await waitFor(() => controls.select.children.length > 1);

    controls.select.value = "demo_b";
    controls.select.dispatchEvent({ type: "change", target: controls.select });
    controls.loadButton.click();
    await waitFor(() => controls.loadButton.textContent === "Load & Play");

    assert.equal(panel.state.applyAllowed, false, "apply disallowed");
    assert.equal(panel.state.canvasApplyAllowed, false, "canvas apply disallowed");
    assert.equal(panel.state.applyEligibility?.reason, "server_blocked", "eligibility reason preserved");
    assert.equal(
      panel.state.expandedBubbleTurnKeys["turn:demo-turn-a"],
      true,
      "details still expanded",
    );
  } finally {
    await harness.dispose();
  }
});

// ── End-to-end demo Apply/Reject no-post behavior ───────────────────────────

test("demo Apply and Reject do not POST to the backend accept/reject routes", async () => {
  const harness = await createBrowserHarness({
    withGraphMutation: true,
    responses: {
      "/vibecomfy/ping": { status: 200, body: "pong" },
      "/vibecomfy/agent/status?route=auto": makeStatusResponse(),
      "/vibecomfy/demo/scenarios": makeScenarioList(),
      "/vibecomfy/demo/scenario?id=demo_a": makeScenarioResponse(),
      "/vibecomfy/agent-edit/accept": { status: 500, body: { ok: false, error: "should not be reached" } },
      "/vibecomfy/agent-edit/reject": { status: 500, body: { ok: false, error: "should not be reached" } },
    },
  });
  try {
    globalThis.localStorage.setItem(LS_DEMO_PICKER_ENABLED, "1");
    await harness.loadExtension();
    await harness.invokeCommand("VibeComfy.AgentEdit");

    const runtime = await harness.loadPanelRuntime();
    const panel = runtime.currentAgentPanel();
    assert.ok(panel, "panel is open");
    assert.ok(panel.previewPicker, "preview picker is installed on the panel");

    await waitFor(() => panel.previewPicker.select.children.length > 1);
    panel.previewPicker.select.value = "demo_a";
    panel.previewPicker.select.dispatchEvent({ type: "change", target: panel.previewPicker.select });
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.previewPicker.loadButton.textContent === "Load & Play");

    assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW, "panel is in review state");
    assert.equal(panel.state.__demoMode, true, "panel is in demo mode");

    // The button click handler does not consult the disabled attribute; ensure the
    // button itself is enabled to confirm the UI considers the action available.
    panel.buttons.apply.disabled = false;
    panel.buttons.reject.disabled = false;

    // Count requests before clicking Apply.
    const preApplyCount = harness.requests.length;
    panel.buttons.apply.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/accept"),
      "demo Apply must not POST /vibecomfy/agent-edit/accept",
    );
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "demo Apply transitions to IDLE");
    assert.equal(panel.state.__demoMode, undefined, "__demoMode is cleared after demo Apply");

    // Restore demo state to exercise Reject on the same panel.
    panel.previewPicker.loadButton.click();
    await waitFor(() => panel.previewPicker.loadButton.textContent === "Load & Play");
    assert.equal(panel.state.__demoMode, true, "demo mode restored after replay");

    panel.buttons.apply.disabled = false;
    panel.buttons.reject.disabled = false;
    panel.buttons.reject.click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    assert.ok(
      !harness.requests.some((r) => r.url === "/vibecomfy/agent-edit/reject"),
      "demo Reject must not POST /vibecomfy/agent-edit/reject",
    );
    assert.equal(panel.state.phase, PANEL_STATE.IDLE, "demo Reject transitions to IDLE");
    assert.equal(panel.state.__demoMode, undefined, "__demoMode is cleared after demo Reject");
  } finally {
    await harness.dispose();
  }
});
