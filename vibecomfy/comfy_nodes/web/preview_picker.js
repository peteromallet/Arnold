// vibecomfy/comfy_nodes/web/preview_picker.js
// Hideable "Preview query" picker for the VibeComfy chat panel.
//
// This module is a dev/demo-only, self-contained installer. It reads
// `localStorage["vibecomfy_demo_picker_enabled"]`: when that key is not `"0"`,
// the installer probes `/vibecomfy/demo/scenarios`. A successful manifest
// response mounts a small "▦ Demo" toggle in the panel header and a hideable
// toolbar that lists curated demo scenarios.
// Selecting a scenario and clicking "Load & Play" replays it as a fake agent
// turn: the original graph is applied to the canvas, a user query + agent reply
// are pushed to the chat thread, and the panel state is populated to mirror a
// normal AWAITING_REVIEW candidate (including `__demoMode` for the demo-only
// Apply/Reject branches defined later in the lifecycle).
//
// The server endpoint is the source of truth for whether demo mode exists. A
// missing/disabled endpoint leaves no UI mounted and no panel state touched.

import { app } from "../../scripts/app.js";
import { applyGraphCandidateInPlace } from "./comfy_adapter.js";
import { scheduleRenderAgentPanel } from "./panel_scheduler.js";
import { currentAgentPanel } from "./panel_runtime.js";
import { PANEL_STATE, RENDER_SECTIONS } from "./agent_edit_lifecycle.js";
import {
  commitApplyResolved,
  commitLifecycleReset,
  commitOptimisticSubmit,
  commitTerminalResponse,
  commitTranscriptRehydrate,
} from "./agent_lifecycle_commit.js";

const LS_DEMO_PICKER_ENABLED = "vibecomfy_demo_picker_enabled";
const SCENARIOS_ENDPOINT = "/vibecomfy/demo/scenarios";
const SCENARIO_ENDPOINT = "/vibecomfy/demo/scenario";
const DEMO_STAGES = Object.freeze(["before_send", "sent_loading", "ready_to_apply", "applied"]);

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
  if (globalThis.__VIBECOMFY_FORCE_DEMO_PICKER__ === true) {
    return true;
  }
  try {
    return localStorage.getItem(LS_DEMO_PICKER_ENABLED) !== "0";
  } catch (_e) {
    return true;
  }
}

function isDemoUnavailableError(error) {
  return error?.code === "demo_unavailable" || error?.status === 404;
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

function clonePlainData(value) {
  if (value == null) {
    return value;
  }
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (_e) {
    return value;
  }
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
    display: "flex",
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

  const prevBtn = button("◀", null);
  const nextBtn = button("▶", null);
  for (const navBtn of [prevBtn, nextBtn]) {
    Object.assign(navBtn.style, {
      padding: "4px 8px",
      fontSize: "11px",
      lineHeight: "1",
      whiteSpace: "nowrap",
    });
    navBtn.disabled = true;
  }
  prevBtn.title = "Previous demo stage";
  nextBtn.title = "Next demo stage";

  const errorDisplay = buildErrorDisplay();

  controlsRow.appendChild(select);
  controlsRow.appendChild(prevBtn);
  controlsRow.appendChild(nextBtn);
  controlsRow.appendChild(loadBtn);
  pickerContainer.appendChild(controlsRow);
  pickerContainer.appendChild(errorDisplay);

  let selectedScenarioId = null;
  let loadedScenario = null;
  let stageIndex = -1;
  let loadingScenario = false;

  function showError(message) {
    errorDisplay.textContent = String(message || "");
    errorDisplay.style.display = message ? "block" : "none";
  }

  async function fetchScenarios() {
    const res = await fetch(SCENARIOS_ENDPOINT);
    if (!res.ok) {
      const error = new Error(`Failed to fetch demo scenarios: ${res.status}`);
      error.status = res.status;
      if (res.status === 404) {
        error.code = "demo_unavailable";
      }
      throw error;
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

  function stagePayload() {
    if (!loadedScenario) {
      return null;
    }
    const originalGraph = loadedScenario.original_graph;
    const candidateGraph = loadedScenario.candidate_graph;
    const sessionId = loadedScenario.session_id;
    const turnId = loadedScenario.turn_id;
    const query = loadedScenario.scenario?.query || loadedScenario.query || "";
    const agentReply = loadedScenario.agent_reply || "";
    const userMessage = makeMessage({ role: "user", text: query, sessionId, turnId });
    const agentMessage = makeMessage({ role: "agent", text: agentReply, sessionId, turnId });
    return {
      originalGraph,
      candidateGraph,
      sessionId,
      turnId,
      query,
      agentReply,
      userMessage,
      agentMessage,
      candidateGraphHash: loadedScenario.__candidateGraphHash || null,
      eligibility: normalizeEligibility(loadedScenario.eligibility),
      changeDetails: loadedScenario.change_details || null,
    };
  }

  function updateStageButtons() {
    const hasStage = Boolean(loadedScenario) && stageIndex >= 0;
    prevBtn.disabled = loadingScenario || !hasStage || stageIndex <= 0;
    nextBtn.disabled = loadingScenario || !hasStage || stageIndex >= DEMO_STAGES.length - 1;
    loadBtn.disabled = loadingScenario || !selectedScenarioId;
    if (hasStage) {
      loadBtn.textContent = "Reload";
    } else {
      loadBtn.textContent = loadingScenario ? "Loading..." : "Load & Play";
    }
  }

  function schedulePanelRender(currentPanel) {
    helpers.scheduleRenderAgentPanel(
      "demo-picker",
      currentPanel,
      [
        helpers.RENDER_SECTIONS.THREAD,
        helpers.RENDER_SECTIONS.META,
        helpers.RENDER_SECTIONS.COMPOSER,
        helpers.RENDER_SECTIONS.NOTICE,
      ].filter(Boolean),
    );
  }

  function clearCandidateState(currentPanel) {
    delete currentPanel.state._previewDiff;
    delete currentPanel.state._previewDiffGraphHash;
  }

  function commitDemoTranscript(currentPanel, payload, messages, latestCandidate = null) {
    commitTranscriptRehydrate(currentPanel, {
      messages,
      sessionId: payload.sessionId,
      latestTurnId: payload.turnId,
      latestCandidate,
    });
  }

  function applyOriginalGraph(payload) {
    try {
      helpers.applyGraphCandidateInPlace(helpers.app, clonePlainData(payload.originalGraph), { repaint: true });
    } catch (graphError) {
      console.warn("[vibecomfy] demo original graph apply failed:", graphError);
    }
  }

  function applyCandidateGraph(payload) {
    helpers.applyGraphCandidateInPlace(helpers.app, clonePlainData(payload.candidateGraph), { repaint: true });
  }

  function isLayoutPreviewScenario() {
    const report = loadedScenario?.report;
    return Boolean(
      report
      && typeof report === "object"
      && (report.kind === "reorganise" || report.route === "reorganise" || report.reorganise),
    );
  }

  function renderDemoStage(nextStageIndex, options = {}) {
    const currentPanel = panel || helpers.currentAgentPanel();
    const payload = stagePayload();
    if (!currentPanel?.state || !payload) {
      return;
    }
    const boundedStage = Math.max(0, Math.min(DEMO_STAGES.length - 1, nextStageIndex));
    stageIndex = boundedStage;
    const stage = DEMO_STAGES[stageIndex];

    currentPanel.state.__demoMode = true;
    currentPanel.state.__demoStage = stage;
    currentPanel.state.__demoStageIndex = stageIndex;

    if (stage === "before_send") {
      applyOriginalGraph(payload);
      commitLifecycleReset(currentPanel, {
        rejected: {},
        message: null,
        debugPayload: { source: "demo", stage },
      });
      commitDemoTranscript(currentPanel, payload, [], null);
      clearCandidateState(currentPanel);
    } else if (stage === "sent_loading") {
      applyOriginalGraph(payload);
      commitLifecycleReset(currentPanel, {
        rejected: {},
        message: null,
        debugPayload: { source: "demo", stage, reset: true },
      });
      commitOptimisticSubmit(currentPanel, {
        lastSubmit: { prompt: payload.query, source: "demo" },
        debugPayload: { source: "demo", stage },
      });
      commitDemoTranscript(currentPanel, payload, [payload.userMessage], null);
      clearCandidateState(currentPanel);
    } else if (stage === "ready_to_apply") {
      if (isLayoutPreviewScenario()) {
        applyCandidateGraph(payload);
      } else {
        applyOriginalGraph(payload);
      }
      const terminalResult = {
        ok: true,
        session_id: payload.sessionId,
        turn_id: payload.turnId,
        baseline_turn_id: null,
        message: payload.agentReply || null,
        outcome: { kind: "candidate" },
        eligibility: payload.eligibility,
        report: loadedScenario.report || {},
      };
      commitTerminalResponse(currentPanel, {
        result: terminalResult,
        outcome: { kind: "candidate" },
        candidateGraph: payload.candidateGraph,
        candidateGraphHash: payload.candidateGraphHash,
        applyEligibility: payload.eligibility,
        queueAllowed: false,
        changeDetails: payload.changeDetails,
        debugPayload: {
          source: "demo",
          stage,
          scenarioId: loadedScenario?.scenario?.id || loadedScenario?.id || null,
        },
      });
      commitDemoTranscript(currentPanel, payload, [payload.userMessage, payload.agentMessage], terminalResult);
    } else if (stage === "applied") {
      if (!options.alreadyApplied) {
        applyCandidateGraph(payload);
      }
      commitApplyResolved(currentPanel, {
        accepted: { ok: true, session_id: payload.sessionId, turn_id: payload.turnId },
        lastAppliedChanges: options.lastAppliedChanges || payload.changeDetails || {
          summary: "Demo candidate applied.",
        },
        debugPayload: { source: "demo", stage },
      });
      commitDemoTranscript(currentPanel, payload, [payload.userMessage, payload.agentMessage], null);
      clearCandidateState(currentPanel);
      currentPanel.state.__demoMode = false;
    }

    updateStageButtons();
    showError("");
    schedulePanelRender(currentPanel);
  }

  async function loadAndPlay() {
    const id = selectedScenarioId;
    if (!id) {
      showError("Select a scenario first");
      return;
    }
    showError("");
    loadingScenario = true;
    updateStageButtons();

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

      loadedScenario = {
        ...scenario,
        original_graph: clonePlainData(originalGraph),
        candidate_graph: clonePlainData(candidateGraph),
        __candidateGraphHash: await sha256Hex(JSON.stringify(candidateGraph)),
      };
      renderDemoStage(0);
    } catch (error) {
      showError(error?.message || String(error));
    } finally {
      loadingScenario = false;
      updateStageButtons();
    }
  }

  select.addEventListener("change", () => {
    selectedScenarioId = select.value || null;
    loadedScenario = null;
    stageIndex = -1;
    loadBtn.disabled = !selectedScenarioId;
    updateStageButtons();
    showError("");
  });

  loadBtn.addEventListener("click", loadAndPlay);
  prevBtn.addEventListener("click", () => {
    if (loadedScenario && stageIndex > 0) {
      renderDemoStage(stageIndex - 1);
    }
  });
  nextBtn.addEventListener("click", () => {
    if (loadedScenario && stageIndex < DEMO_STAGES.length - 1) {
      renderDemoStage(stageIndex + 1);
    }
  });

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

  let mounted = false;

  function mountPicker() {
    if (mounted) {
      return;
    }
    mounted = true;
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
  }

  function unmountPicker() {
    mounted = false;
    if (toggleBtn.parentNode) {
      toggleBtn.parentNode.removeChild(toggleBtn);
    }
    if (pickerContainer.parentNode) {
      pickerContainer.parentNode.removeChild(pickerContainer);
    }
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
      mountPicker();
      if (scenarios.length === 0) {
        showError("No demo scenarios available");
      }
    })
    .catch((error) => {
      if (isDemoUnavailableError(error)) {
        unmountPicker();
        return;
      }
      mountPicker();
      showError(error?.message || String(error));
    });

  return {
    toggle: toggleBtn,
    container: pickerContainer,
    select,
    prevButton: prevBtn,
    nextButton: nextBtn,
    loadButton: loadBtn,
    get mounted() {
      return mounted;
    },
    showAppliedStage(options = {}) {
      if (loadedScenario) {
        renderDemoStage(3, { ...options, alreadyApplied: true });
      }
    },
  };
}

export function isDemoPickerEnabled() {
  return isPickerEnabled();
}
