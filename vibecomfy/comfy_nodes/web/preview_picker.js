// vibecomfy/comfy_nodes/web/preview_picker.js
// Hideable "Preview query" picker for the VibeComfy chat panel.
//
// This module is a dev/demo-only, self-contained installer. It reads
// `localStorage["vibecomfy_demo_picker_enabled"]`: when that key is `"1"`, the
// installer mounts a small "▦ Demo" toggle in the panel header and a hideable
// toolbar that lists curated demo scenarios from `/vibecomfy/demo/scenarios`.
// Selecting a scenario and clicking "Load & Play" replays it as a fake agent
// turn: the original graph is applied to the canvas, a user query + agent reply
// are pushed to the chat thread, and the panel state is populated to mirror a
// normal AWAITING_REVIEW candidate (including `__demoMode` for the demo-only
// Apply/Reject branches defined later in the lifecycle).
//
// When the localStorage flag is unset, this module is a no-op: no UI is
// created, no fetches are made, and no panel state is touched.

import { app } from "../../scripts/app.js";
import { applyGraphCandidateInPlace } from "./comfy_adapter.js";
import { scheduleRenderAgentPanel } from "./panel_scheduler.js";
import { currentAgentPanel } from "./panel_runtime.js";
import { PANEL_STATE, RENDER_SECTIONS } from "./agent_edit_lifecycle.js";

const LS_DEMO_PICKER_ENABLED = "vibecomfy_demo_picker_enabled";
const SCENARIOS_ENDPOINT = "/vibecomfy/demo/scenarios";
const SCENARIO_ENDPOINT = "/vibecomfy/demo/scenario";

function makeHelpers(overrides = {}) {
  return {
    app: overrides.app || app,
    applyGraphCandidateInPlace: overrides.applyGraphCandidateInPlace || applyGraphCandidateInPlace,
    scheduleRenderAgentPanel: overrides.scheduleRenderAgentPanel || scheduleRenderAgentPanel,
    currentAgentPanel: overrides.currentAgentPanel || currentAgentPanel,
    PANEL_STATE: overrides.PANEL_STATE || PANEL_STATE,
    RENDER_SECTIONS: overrides.RENDER_SECTIONS || RENDER_SECTIONS,
  };
}

function isPickerEnabled() {
  try {
    return localStorage.getItem(LS_DEMO_PICKER_ENABLED) === "1";
  } catch (_e) {
    return false;
  }
}

function el(tag, text = "") {
  const element = document.createElement(tag);
  if (text !== "") {
    element.textContent = String(text);
  }
  return element;
}

function button(label, onClick) {
  const btn = el("button", label);
  btn.type = "button";
  if (typeof onClick === "function") {
    btn.addEventListener("click", onClick);
  }
  return btn;
}

function setVisible(element, visible) {
  if (element) {
    element.style.display = visible ? "flex" : "none";
  }
}

async function sha256Hex(text) {
  try {
    if (typeof crypto !== "undefined" && crypto.subtle && typeof TextEncoder !== "undefined") {
      const data = new TextEncoder().encode(text);
      const hash = await crypto.subtle.digest("SHA-256", data);
      return Array.from(new Uint8Array(hash))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    }
  } catch (_e) {
    // fall through to deterministic fallback
  }
  return `demo-${text.length}-${String(text).slice(0, 16)}`;
}

function normalizeEligibility(raw) {
  if (raw && typeof raw === "object" && typeof raw.reason === "string") {
    const knownReasons = new Set([
      "applyable",
      "no_candidate",
      "missing_contract",
      "missing_durable_turn_metadata",
      "not_latest",
      "superseded",
      "server_blocked",
      "stale_canvas",
      "queue_blocked_warning",
    ]);
    const reason = knownReasons.has(raw.reason) ? raw.reason : "applyable";
    return {
      applyable: raw.applyable !== false,
      reason,
      message: typeof raw.message === "string" ? raw.message : "",
      warnings: Array.isArray(raw.warnings) ? raw.warnings.slice() : [],
    };
  }
  return {
    applyable: true,
    reason: "applyable",
    message: "Demo candidate is ready to apply.",
    warnings: [],
  };
}

function makeMessage({ role, text, sessionId, turnId }) {
  const now = new Date().toISOString();
  return {
    role: String(role || ""),
    text: String(text || ""),
    session_id: sessionId,
    turn_id: turnId,
    source: "demo",
    timestamp: now,
    synthetic: false,
    optimistic: false,
  };
}

function buildErrorDisplay() {
  const node = el("div");
  Object.assign(node.style, {
    color: "#ff6c6c",
    fontSize: "11px",
    marginTop: "6px",
    display: "none",
  });
  return node;
}

/**
 * Install the demo preview picker on a panel shell.
 *
 * @param {object} panel - An agent panel object (must have a `.shell` element).
 * @param {object} [options] - Optional mount configuration.
 * @param {HTMLElement} [options.headerRight] - The header right container to
 *   receive the "▦ Demo" toggle button. If omitted, the toggle is placed inside
 *   the picker container itself.
 * @param {HTMLElement} [options.mountContainer] - Where to mount the picker
 *   toolbar; defaults to `panel.shell`.
 * @param {object} [options.helpers] - Optional overrides for the helpers used
 *   by the picker (app, applyGraphCandidateInPlace, scheduleRenderAgentPanel,
 *   currentAgentPanel, PANEL_STATE, RENDER_SECTIONS). Defaults to the module's
 *   own ES module imports so the picker is still self-contained when called
 *   without options.
 * @returns {object|null} - Picker controls object, or `null` if disabled or
 *   the panel has no shell.
 */
export function installPreviewPicker(panel, options = {}) {
  if (!isPickerEnabled()) {
    return null;
  }
  if (!panel?.shell || typeof document === "undefined") {
    console.warn("[vibecomfy] installPreviewPicker requires a panel with .shell and a document");
    return null;
  }

  const helpers = makeHelpers(options.helpers);
  const headerRight = options.headerRight || null;
  const mountContainer = options.mountContainer || panel.shell;

  const pickerContainer = el("div");
  Object.assign(pickerContainer.style, {
    display: "none",
    flexDirection: "column",
    gap: "8px",
    padding: "8px 14px",
    borderBottom: "1px solid #282a32",
    background: "#14161b",
  });

  const controlsRow = el("div");
  Object.assign(controlsRow.style, {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    flexWrap: "wrap",
  });

  const select = el("select");
  Object.assign(select.style, {
    flex: "1 1 auto",
    minWidth: "120px",
    background: "#101115",
    color: "#edf2f7",
    border: "1px solid #282a32",
    borderRadius: "4px",
    padding: "4px 6px",
    fontSize: "11px",
    fontFamily: "monospace",
  });
  const placeholder = el("option", "Select a demo scenario...");
  placeholder.value = "";
  placeholder.disabled = true;
  placeholder.selected = true;
  select.appendChild(placeholder);

  const loadBtn = button("Load & Play", null);
  Object.assign(loadBtn.style, {
    padding: "4px 10px",
    fontSize: "11px",
    whiteSpace: "nowrap",
  });
  loadBtn.disabled = true;

  const errorDisplay = buildErrorDisplay();

  controlsRow.appendChild(select);
  controlsRow.appendChild(loadBtn);
  pickerContainer.appendChild(controlsRow);
  pickerContainer.appendChild(errorDisplay);

  let selectedScenarioId = null;

  function showError(message) {
    errorDisplay.textContent = String(message || "");
    errorDisplay.style.display = message ? "block" : "none";
  }

  async function fetchScenarios() {
    const res = await fetch(SCENARIOS_ENDPOINT);
    if (!res.ok) {
      throw new Error(`Failed to fetch demo scenarios: ${res.status}`);
    }
    const data = await res.json();
    if (!data?.ok || !Array.isArray(data.scenarios)) {
      throw new Error("Invalid demo scenarios response");
    }
    return data.scenarios;
  }

  async function fetchScenario(id) {
    const res = await fetch(`${SCENARIO_ENDPOINT}?id=${encodeURIComponent(id)}`);
    if (!res.ok) {
      throw new Error(`Failed to fetch scenario: ${res.status}`);
    }
    const data = await res.json();
    if (!data?.ok) {
      throw new Error("Invalid demo scenario response");
    }
    return data;
  }

  async function loadAndPlay() {
    const id = selectedScenarioId;
    if (!id) {
      showError("Select a scenario first");
      return;
    }
    showError("");
    loadBtn.disabled = true;
    loadBtn.textContent = "Loading...";

    try {
      const scenario = await fetchScenario(id);
      const currentPanel = panel || helpers.currentAgentPanel();
      if (!currentPanel?.state) {
        throw new Error("No active agent panel");
      }

      const originalGraph = scenario.original_graph;
      const candidateGraph = scenario.candidate_graph;
      const agentReply = scenario.agent_reply || "";
      const sessionId = scenario.session_id;
      const turnId = scenario.turn_id;
      const query = scenario.scenario?.query || scenario.query || "";

      if (!originalGraph || !candidateGraph) {
        throw new Error("Scenario response missing required graph data");
      }

      // Apply the original graph to the live canvas. If the local ComfyUI
      // cannot apply it (e.g., missing custom-node packs), the candidate is
      // still presented in the panel and the error is logged.
      try {
        helpers.applyGraphCandidateInPlace(helpers.app, originalGraph, { repaint: true });
      } catch (graphError) {
        console.warn("[vibecomfy] demo original graph apply failed:", graphError);
      }

      const candidateGraphHash = await sha256Hex(JSON.stringify(candidateGraph));

      // Deterministic transcript replay: user query followed by agent reply.
      const userMessage = makeMessage({ role: "user", text: query, sessionId, turnId });
      const agentMessage = makeMessage({ role: "agent", text: agentReply, sessionId, turnId });
      currentPanel.state.chatMessages = [userMessage, agentMessage];
      currentPanel.state.transcriptMessages = currentPanel.state.chatMessages.slice();

      // Mirror the normal AWAITING_REVIEW candidate state so Apply/Reject light
      // up exactly like a live agent-edit response.
      const eligibility = normalizeEligibility(scenario.eligibility);
      const candidateActionAllowed = Boolean(candidateGraph && eligibility.applyable === true);

      Object.assign(currentPanel.state, {
        sessionId,
        turnId,
        baselineTurnId: null,
        phase: helpers.PANEL_STATE.AWAITING_REVIEW,
        candidateGraph,
        candidateGraphHash,
        candidateReport: null,
        serverSubmitGraphHash: null,
        applyEligibility: eligibility,
        applyAllowed: candidateActionAllowed,
        canvasApplyAllowed: candidateActionAllowed,
        queueAllowed: false,
        applyEligibilityWarning: null,
        applyEligibilityWarningKey: null,
        message: null,
        failure: null,
        clarification: null,
        changeDetails: scenario.change_details || null,
        lastAppliedChanges: null,
        lastSubmitFieldChanges: null,
        deltaOps: null,
        __demoMode: true,
      });

      // Auto-expand the agent bubble's details so the candidate changes and
      // Apply button are visible without an extra click.
      const detailTurnKey = `turn:${turnId}`;
      currentPanel.state.expandedBubbleTurnKeys = {
        ...(currentPanel.state.expandedBubbleTurnKeys || {}),
        [detailTurnKey]: true,
      };

      // Clear any stale response detail for this turn so the changeDetails
      // fallback is used.
      if (currentPanel.state.responseDetails && typeof currentPanel.state.responseDetails === "object") {
        delete currentPanel.state.responseDetails[turnId];
      }

      showError("");
      helpers.scheduleRenderAgentPanel("demo-picker", currentPanel, [
        helpers.RENDER_SECTIONS.THREAD,
        helpers.RENDER_SECTIONS.META,
        helpers.RENDER_SECTIONS.CANDIDATE,
      ]);
    } catch (error) {
      showError(error?.message || String(error));
    } finally {
      loadBtn.disabled = !selectedScenarioId;
      loadBtn.textContent = "Load & Play";
    }
  }

  select.addEventListener("change", () => {
    selectedScenarioId = select.value || null;
    loadBtn.disabled = !selectedScenarioId;
    showError("");
  });

  loadBtn.addEventListener("click", loadAndPlay);

  const toggleBtn = button("▦ Demo", () => {
    const expanded = pickerContainer.style.display === "none";
    setVisible(pickerContainer, expanded);
    toggleBtn.style.opacity = expanded ? "1" : "0.7";
  });
  Object.assign(toggleBtn.style, {
    padding: "4px 8px",
    fontSize: "11px",
    lineHeight: "1",
    opacity: "0.7",
  });
  toggleBtn.title = "Demo scenario picker";

  if (headerRight) {
    headerRight.appendChild(toggleBtn);
  } else {
    pickerContainer.appendChild(toggleBtn);
  }

  // Insert the picker toolbar right after the panel header (the first child of
  // mountContainer is expected to be the header).
  const firstChild = mountContainer.firstChild;
  if (firstChild) {
    mountContainer.insertBefore(pickerContainer, firstChild.nextSibling);
  } else {
    mountContainer.appendChild(pickerContainer);
  }

  // Load scenario list. This is the only network traffic the module emits,
  // and it only happens when the picker is enabled and installed.
  fetchScenarios()
    .then((scenarios) => {
      for (const scenario of scenarios) {
        const option = el("option", scenario.title || scenario.id);
        option.value = scenario.id;
        select.appendChild(option);
      }
      if (scenarios.length === 0) {
        showError("No demo scenarios available");
      }
    })
    .catch((error) => {
      showError(error?.message || String(error));
    });

  return {
    toggle: toggleBtn,
    container: pickerContainer,
    select,
    loadButton: loadBtn,
  };
}

export function isDemoPickerEnabled() {
  return isPickerEnabled();
}
