// vibecomfy/comfy_nodes/web/agentic_replay.js
// Agentic replay toolbar for the VibeComfy chat panel.
//
// This module is a dev-only, self-contained installer. It reads
// `localStorage["vibecomfy_agentic_replay_enabled"]`: when that key is `"1"`,
// the installer mounts a "▶ Replay" toggle in the panel header and a hideable
// toolbar that lets you step through agentic batch evidence tracked under
// `out/agentic/`.  When the localStorage flag is absent this module is a
// no-op: no UI is created, no fetches are made, and no panel state is touched.
//
// Two-tier selector cascade:
//   1. Run selector  → GET /vibecomfy/agentic-replay/runs
//   2. Test selector → GET /vibecomfy/agentic-replay/runs/{run_id}/tests
//
// Once a run+test is selected, a "Load" button fetches the full scenario
// payload from GET /vibecomfy/agentic-replay/runs/{run_id}/tests/{test_id}
// and populates the replay stage navigator.  Left/right arrow keys step
// through the returned stages; each stage snapshots the panel (chat messages,
// transcript, phase, candidate fields, graph) and canvas graph through the
// existing panel/canvas affordances.

import { app } from "../../scripts/app.js";
import { applyGraphCandidateInPlace } from "./comfy_adapter.js";
import { scheduleRenderAgentPanel } from "./panel_scheduler.js";
import { currentAgentPanel } from "./panel_runtime.js";
import { PANEL_STATE, RENDER_SECTIONS } from "./agent_edit_lifecycle.js";
import {
  commitApplyResolved,
  commitLatestCandidateRestore,
  commitLifecycleReset,
  commitOptimisticSubmit,
  commitTerminalResponse,
  commitTranscriptRehydrate,
} from "./agent_lifecycle_commit.js";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LS_REPLAY_ENABLED = "vibecomfy_agentic_replay_enabled";
const RUNS_ENDPOINT = "/vibecomfy/agentic-replay/runs";
const TESTS_ENDPOINT_TEMPLATE = "/vibecomfy/agentic-replay/runs/{run_id}/tests";
const SCENARIO_ENDPOINT_TEMPLATE = "/vibecomfy/agentic-replay/runs/{run_id}/tests/{test_id}";

const STAGE_ORDER = Object.freeze(["sent", "thinking", "ready_to_apply", "applied"]);

// ---------------------------------------------------------------------------
// Helpers (overridable for testing)
// ---------------------------------------------------------------------------

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

export function isReplayEnabled() {
  try {
    return localStorage.getItem(LS_REPLAY_ENABLED) === "1";
  } catch (_e) {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Tiny DOM helpers
// ---------------------------------------------------------------------------

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

function normalizeEligibility(raw, fallbackReason = "applyable", fallbackMessage = "") {
  if (raw && typeof raw === "object" && typeof raw.reason === "string") {
    return {
      applyable: raw.applyable !== false,
      reason: raw.reason,
      message: typeof raw.message === "string" ? raw.message : fallbackMessage,
      warnings: Array.isArray(raw.warnings) ? raw.warnings.slice() : [],
    };
  }
  return {
    applyable: fallbackReason === "applyable",
    reason: fallbackReason,
    message: fallbackMessage,
    warnings: [],
  };
}

// ---------------------------------------------------------------------------
// Replay state machine snapshot helpers
// ---------------------------------------------------------------------------

/**
 * Create a synthetic pending agent message for the "thinking" stage.
 */
function makePendingAgentMessage(sessionId, turnId) {
  const now = new Date().toISOString();
  return {
    role: "agent",
    text: "",
    session_id: sessionId,
    turn_id: turnId,
    source: "replay",
    timestamp: now,
    synthetic: true,
    optimistic: false,
    pending_response: true,
    executor_pending: true,
  };
}

/**
 * Create a user message from a query string.
 */
function makeUserMessage(query, sessionId, turnId) {
  const now = new Date().toISOString();
  return {
    role: "user",
    text: String(query || ""),
    session_id: sessionId,
    turn_id: turnId,
    source: "replay",
    timestamp: now,
    synthetic: false,
    optimistic: false,
  };
}

/**
 * Create an agent reply message.
 */
function makeAgentMessage(reply, sessionId, turnId) {
  const now = new Date().toISOString();
  return {
    role: "agent",
    text: String(reply || ""),
    session_id: sessionId,
    turn_id: turnId,
    source: "replay",
    timestamp: now,
    synthetic: false,
    optimistic: false,
  };
}

// ---------------------------------------------------------------------------
// Replay controller
// ---------------------------------------------------------------------------

/**
 * Install the agentic replay toolbar on a panel shell.
 *
 * @param {object} panel - An agent panel object (must have `.shell` + `.state`).
 * @param {object} [options] - Mount configuration.
 * @param {HTMLElement} [options.headerRight] - Header right container for the toggle.
 * @param {HTMLElement} [options.mountContainer] - Where to mount the toolbar.
 * @param {object} [options.helpers] - Dependency overrides for testing.
 * @param {function} [options.applyReplayGraphCandidate] - Local helper that applies
 *   a candidate graph with intent decoration and repair. Called as
 *   `applyReplayGraphCandidate(candidateGraph)`.
 * @param {function} [options.applyReplayOriginalGraph] - Local helper that applies
 *   the original (pre-edit) graph. Called as
 *   `applyReplayOriginalGraph(originalGraph)`.
 * @returns {object|null} - Controls object, or null if disabled.
 */
export function installAgenticReplay(panel, options = {}) {
  if (!isReplayEnabled()) {
    return null;
  }
  if (!panel?.shell || typeof document === "undefined") {
    console.warn("[vibecomfy] installAgenticReplay requires a panel with .shell and a document");
    return null;
  }

  const helpers = makeHelpers(options.helpers);
  const headerRight = options.headerRight || null;
  const mountContainer = options.mountContainer || panel.shell;
  const applyReplayGraphCandidate = options.applyReplayGraphCandidate || null;
  const applyReplayOriginalGraph = options.applyReplayOriginalGraph || null;

  // ── Toolbar DOM ──────────────────────────────────────────────────────

  const toolbar = el("div");
  Object.assign(toolbar.style, {
    display: "none",
    flexDirection: "column",
    gap: "8px",
    padding: "8px 14px",
    borderBottom: "1px solid #282a32",
    background: "#14161b",
  });

  // Run selector row
  const runRow = el("div");
  Object.assign(runRow.style, {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    flexWrap: "wrap",
  });

  const runSelect = el("select");
  Object.assign(runSelect.style, {
    flex: "1 1 auto",
    minWidth: "100px",
    background: "#101115",
    color: "#edf2f7",
    border: "1px solid #282a32",
    borderRadius: "4px",
    padding: "4px 6px",
    fontSize: "11px",
    fontFamily: "monospace",
  });
  const runPlaceholder = el("option", "Select a run...");
  runPlaceholder.value = "";
  runPlaceholder.disabled = true;
  runPlaceholder.selected = true;
  runSelect.appendChild(runPlaceholder);

  // Test selector row
  const testRow = el("div");
  Object.assign(testRow.style, {
    display: "flex",
    gap: "8px",
    alignItems: "center",
    flexWrap: "wrap",
  });

  const testSelect = el("select");
  Object.assign(testSelect.style, {
    flex: "1 1 auto",
    minWidth: "100px",
    background: "#101115",
    color: "#edf2f7",
    border: "1px solid #282a32",
    borderRadius: "4px",
    padding: "4px 6px",
    fontSize: "11px",
    fontFamily: "monospace",
  });
  const testPlaceholder = el("option", "Select a test...");
  testPlaceholder.value = "";
  testPlaceholder.disabled = true;
  testPlaceholder.selected = true;
  testSelect.appendChild(testPlaceholder);

  // Actions row: Load + stage navigation
  const actionsRow = el("div");
  Object.assign(actionsRow.style, {
    display: "flex",
    gap: "6px",
    alignItems: "center",
    flexWrap: "wrap",
  });

  const loadBtn = button("Load", null);
  Object.assign(loadBtn.style, {
    padding: "4px 10px",
    fontSize: "11px",
    whiteSpace: "nowrap",
  });
  loadBtn.disabled = true;

  const prevBtn = button("◀", null);
  Object.assign(prevBtn.style, {
    padding: "4px 8px",
    fontSize: "11px",
    whiteSpace: "nowrap",
  });
  prevBtn.disabled = true;
  prevBtn.title = "Previous stage (←)";

  const nextBtn = button("▶", null);
  Object.assign(nextBtn.style, {
    padding: "4px 8px",
    fontSize: "11px",
    whiteSpace: "nowrap",
  });
  nextBtn.disabled = true;
  nextBtn.title = "Next stage (→)";

  const stageLabel = el("span", "");
  Object.assign(stageLabel.style, {
    fontSize: "11px",
    color: "#9da1ac",
    fontFamily: "monospace",
    marginLeft: "6px",
  });

  const clearBtn = button("✕ Clear", null);
  Object.assign(clearBtn.style, {
    padding: "4px 10px",
    fontSize: "11px",
    whiteSpace: "nowrap",
    marginLeft: "auto",
  });
  clearBtn.disabled = true;
  clearBtn.title = "Clear replay and restore original graph";

  const errorDisplay = buildErrorDisplay();

  actionsRow.appendChild(loadBtn);
  actionsRow.appendChild(prevBtn);
  actionsRow.appendChild(nextBtn);
  actionsRow.appendChild(stageLabel);
  actionsRow.appendChild(clearBtn);

  toolbar.appendChild(runRow);
  toolbar.appendChild(testRow);
  toolbar.appendChild(actionsRow);
  toolbar.appendChild(errorDisplay);

  runRow.appendChild(runSelect);
  testRow.appendChild(testSelect);

  // Toggle button in header
  const toggleBtn = button("▶ Replay", () => {
    const expanded = toolbar.style.display === "none";
    setVisible(toolbar, expanded);
    toggleBtn.style.opacity = expanded ? "1" : "0.7";
  });
  Object.assign(toggleBtn.style, {
    padding: "4px 8px",
    fontSize: "11px",
    lineHeight: "1",
    opacity: "0.7",
  });
  toggleBtn.title = "Agentic replay toolbar";

  if (headerRight) {
    headerRight.appendChild(toggleBtn);
  } else {
    toolbar.appendChild(toggleBtn);
  }

  // Insert toolbar after the first child of mountContainer
  const firstChild = mountContainer.firstChild;
  if (firstChild) {
    mountContainer.insertBefore(toolbar, firstChild.nextSibling);
  } else {
    mountContainer.appendChild(toolbar);
  }

  // ── State ─────────────────────────────────────────────────────────────

  let selectedRunId = null;
  let selectedTestId = null;
  let scenarioData = null;       // raw backend payload
  let stages = [];               // array of stage objects from backend
  let currentStageIdx = -1;
  let originalGraphSnapshot = null;  // canvas graph before replay started
  let replayBaseline = null;
  let _replayActive = false;

  // ── Helpers ──────────────────────────────────────────────────────────

  function showError(message) {
    errorDisplay.textContent = String(message || "");
    errorDisplay.style.display = message ? "block" : "none";
  }

  function updateNavButtons() {
    prevBtn.disabled = currentStageIdx <= 0;
    nextBtn.disabled = currentStageIdx >= stages.length - 1 || stages.length === 0;
    if (currentStageIdx >= 0 && currentStageIdx < stages.length) {
      const s = stages[currentStageIdx];
      stageLabel.textContent = `${currentStageIdx + 1}/${stages.length} — ${s.label || s.id}`;
    } else {
      stageLabel.textContent = "";
    }
  }

  /**
   * Snapshot the current canvas graph so we can restore it on Clear.
   */
  function captureOriginalGraph() {
    try {
      const graph = helpers.app?.graph;
      if (graph && typeof graph.serialize === "function") {
        originalGraphSnapshot = graph.serialize();
      }
    } catch (_e) {
      originalGraphSnapshot = null;
    }
  }

  /**
   * Apply the candidate graph with intent decoration and repair, mirroring
   * the existing demo Apply branch in applyAgentCandidate.
   */
  function _defaultApplyReplayGraphCandidate(candidateGraph) {
    if (!candidateGraph) return;
    if (applyReplayGraphCandidate) {
      applyReplayGraphCandidate(candidateGraph);
      return;
    }
    try {
      helpers.applyGraphCandidateInPlace(helpers.app, candidateGraph, { repaint: true });
    } catch (e) {
      console.warn("[vibecomfy] replay candidate graph apply failed:", e);
    }
  }

  /**
   * Apply the original graph, restoring the pre-replay canvas state.
   */
  function _defaultApplyReplayOriginalGraph(originalGraph) {
    if (!originalGraph) return;
    if (applyReplayOriginalGraph) {
      applyReplayOriginalGraph(originalGraph);
      return;
    }
    try {
      helpers.applyGraphCandidateInPlace(helpers.app, originalGraph, { repaint: true });
    } catch (e) {
      console.warn("[vibecomfy] replay original graph apply failed:", e);
    }
  }

  function scheduleReplayRender(panel, reason) {
    helpers.scheduleRenderAgentPanel(reason, panel, [
      helpers.RENDER_SECTIONS.THREAD,
      helpers.RENDER_SECTIONS.META,
      helpers.RENDER_SECTIONS.COMPOSER,
      helpers.RENDER_SECTIONS.NOTICE,
    ]);
  }

  function setReplayMeta(panel, stageId, demoMode = false) {
    panel.state._replay = {
      active: true,
      runId: selectedRunId,
      testId: selectedTestId,
      stage: stageId,
      originalGraphSnapshot,
    };
    if (demoMode) {
      panel.state.__demoMode = true;
    } else {
      delete panel.state.__demoMode;
    }
  }

  function captureReplayBaseline(panel) {
    const { state } = panel;
    replayBaseline = {
      chatMessages: clonePlainData(state.chatMessages || []),
      transcriptMessages: clonePlainData(state.transcriptMessages || []),
      sessionId: state.sessionId || null,
      turnId: state.turnId || null,
      baselineTurnId: state.baselineTurnId || null,
      chatScopeId: state.chatScopeId || null,
      chatScopeFingerprint: state.chatScopeFingerprint || null,
      candidateScopeId: state.candidateScopeId || null,
      submittingScopeId: state.submittingScopeId || null,
      candidateGraph: clonePlainData(state.candidateGraph || null),
      candidateGraphHash: state.candidateGraphHash || null,
      candidateReport: clonePlainData(state.candidateReport || null),
      serverSubmitGraphHash: state.serverSubmitGraphHash || null,
      applyEligibility: clonePlainData(state.applyEligibility || null),
      applyAllowed: state.applyAllowed === true,
      canvasApplyAllowed: state.canvasApplyAllowed === true,
      queueAllowed: state.queueAllowed === true,
      auditRef: state.auditRef || null,
      changeDetails: clonePlainData(state.changeDetails || null),
      responseDetails: clonePlainData(state.responseDetails || {}),
      lastAppliedChanges: clonePlainData(state.lastAppliedChanges || null),
      phase: state.phase || helpers.PANEL_STATE.IDLE,
      message: state.message || null,
      clarification: clonePlainData(state.clarification || null),
      failure: clonePlainData(state.failure || null),
      lastSubmit: clonePlainData(state.lastSubmit || null),
      submitEpoch: state.submitEpoch || null,
      inFlightSubmit: state.inFlightSubmit === true,
      inFlightApply: state.inFlightApply === true,
      inFlightRebaseline: state.inFlightRebaseline === true,
      demoMode: state.__demoMode === true,
    };
  }

  function restoreReplayBaseline(panel) {
    if (!replayBaseline) {
      commitLifecycleReset(panel, {
        rejected: {},
        message: null,
        debugPayload: { source: "replay", stage: "restore:empty" },
      });
      commitTranscriptRehydrate(panel, { messages: [], latestCandidate: null });
      delete panel.state.__demoMode;
      delete panel.state._replay;
      return;
    }

    commitLifecycleReset(panel, {
      rejected: {},
      message: replayBaseline.phase === helpers.PANEL_STATE.ERROR ? replayBaseline.message : null,
      debugPayload: { source: "replay", stage: "restore:reset" },
    });

    if (replayBaseline.phase === helpers.PANEL_STATE.SUBMITTING) {
      commitOptimisticSubmit(panel, {
        lastSubmit: replayBaseline.lastSubmit,
        submitEpoch: replayBaseline.submitEpoch,
        debugPayload: { source: "replay", stage: "restore:submitting" },
      });
    }

    if (replayBaseline.phase === helpers.PANEL_STATE.ERROR && replayBaseline.failure) {
      commitTerminalResponse(panel, {
        failure: replayBaseline.failure,
        message: replayBaseline.message,
        debugPayload: { source: "replay", stage: "restore:error" },
      });
    }

    const latestCandidate = replayBaseline.candidateGraph
      ? {
          session_id: replayBaseline.sessionId,
          turn_id: replayBaseline.turnId,
        }
      : null;
    commitTranscriptRehydrate(panel, {
      messages: replayBaseline.chatMessages || [],
      sessionId: replayBaseline.sessionId,
      latestTurnId: replayBaseline.turnId,
      latestCandidate,
    });

    if (replayBaseline.candidateGraph) {
      commitLatestCandidateRestore(panel, {
        requestScopeId: replayBaseline.chatScopeId,
        candidateSessionId: replayBaseline.sessionId,
        sessionId: replayBaseline.sessionId,
        turnId: replayBaseline.turnId,
        baselineTurnId: replayBaseline.baselineTurnId,
        candidateGraph: replayBaseline.candidateGraph,
        candidateGraphHash: replayBaseline.candidateGraphHash,
        candidateReport: replayBaseline.candidateReport,
        serverSubmitGraphHash: replayBaseline.serverSubmitGraphHash,
        message: replayBaseline.message,
        applyEligibility: replayBaseline.applyEligibility,
        applyAllowed: replayBaseline.applyAllowed,
        canvasApplyAllowed: replayBaseline.canvasApplyAllowed,
        queueAllowed: replayBaseline.queueAllowed,
        auditRef: replayBaseline.auditRef,
        changeDetails: replayBaseline.changeDetails,
        debugPayload: { source: "replay", stage: "restore:candidate" },
      });
    }

    if (replayBaseline.demoMode) {
      panel.state.__demoMode = true;
    } else {
      delete panel.state.__demoMode;
    }
    delete panel.state._replay;
  }

  function applyStage(index) {
    if (index < 0 || index >= stages.length) return;
    const stage = stages[index];
    const panel = options._panel || helpers.currentAgentPanel();
    if (!panel?.state) {
      showError("No active agent panel");
      return;
    }

    currentStageIdx = index;
    updateNavButtons();

    const data = scenarioData;
    const sessionId = data.session_id || "replay";
    const turnId = data.turn_id || "0000";
    const userMsg = makeUserMessage(data.query || "", sessionId, turnId);
    const agentMsg = makeAgentMessage(data.reply || "", sessionId, turnId);

    switch (stage.id) {
      case "sent": {
        commitLifecycleReset(panel, {
          rejected: {},
          message: null,
          debugPayload: { source: "replay", stage: "sent" },
        });
        commitTranscriptRehydrate(panel, {
          messages: [userMsg],
          sessionId,
          latestTurnId: turnId,
          latestCandidate: null,
        });
        setReplayMeta(panel, stage.id, false);
        if (data.original_graph) {
          _defaultApplyReplayOriginalGraph(clonePlainData(data.original_graph));
        }
        break;
      }

      case "thinking": {
        const pendingAgent = makePendingAgentMessage(sessionId, turnId);
        commitLifecycleReset(panel, {
          rejected: {},
          message: null,
          debugPayload: { source: "replay", stage: "thinking:reset" },
        });
        commitOptimisticSubmit(panel, {
          lastSubmit: { prompt: data.query || "", source: "replay" },
          debugPayload: { source: "replay", stage: "thinking" },
        });
        commitTranscriptRehydrate(panel, {
          messages: [userMsg, pendingAgent],
          sessionId,
          latestTurnId: turnId,
          latestCandidate: null,
        });
        setReplayMeta(panel, stage.id, false);
        if (data.original_graph) {
          _defaultApplyReplayOriginalGraph(clonePlainData(data.original_graph));
        }
        break;
      }

      case "ready_to_apply": {
        const candidateGraph = data.candidate_graph || null;
        const terminalResult = {
          ok: true,
          session_id: sessionId,
          turn_id: turnId,
          message: data.message || data.reply || null,
          outcome: { kind: "candidate" },
          eligibility: normalizeEligibility(data.eligibility),
          report: clonePlainData(data.candidate_report || {}),
        };
        commitTerminalResponse(panel, {
          result: terminalResult,
          outcome: { kind: "candidate" },
          candidateGraph,
          candidateGraphHash: data.candidate_graph_hash || null,
          applyEligibility: normalizeEligibility(data.eligibility),
          queueAllowed: false,
          changeDetails: clonePlainData(data.change_details || null),
          debugPayload: { source: "replay", stage: "ready_to_apply" },
        });
        commitTranscriptRehydrate(panel, {
          messages: [userMsg, agentMsg],
          sessionId,
          latestTurnId: turnId,
          latestCandidate: terminalResult,
        });
        setReplayMeta(panel, stage.id, true);
        if (data.original_graph) {
          _defaultApplyReplayOriginalGraph(clonePlainData(data.original_graph));
        }
        break;
      }

      case "applied": {
        const candidateGraph = data.candidate_graph || null;
        commitTerminalResponse(panel, {
          result: {
            ok: true,
            session_id: sessionId,
            turn_id: turnId,
            message: data.message || data.reply || null,
            outcome: { kind: "candidate" },
            eligibility: normalizeEligibility(data.eligibility),
            report: clonePlainData(data.candidate_report || {}),
          },
          outcome: { kind: "candidate" },
          candidateGraph,
          candidateGraphHash: data.candidate_graph_hash || null,
          applyEligibility: normalizeEligibility(data.eligibility),
          queueAllowed: false,
          changeDetails: clonePlainData(data.change_details || null),
          debugPayload: { source: "replay", stage: "applied:candidate" },
        });
        commitTranscriptRehydrate(panel, {
          messages: [userMsg, agentMsg],
          sessionId,
          latestTurnId: turnId,
          latestCandidate: { session_id: sessionId, turn_id: turnId },
        });
        commitApplyResolved(panel, {
          accepted: { ok: true, session_id: sessionId, turn_id: turnId },
          lastAppliedChanges: clonePlainData(data.change_details || null),
          debugPayload: { source: "replay", stage: "applied" },
        });
        setReplayMeta(panel, stage.id, true);
        if (candidateGraph) {
          _defaultApplyReplayGraphCandidate(clonePlainData(candidateGraph));
        }
        break;
      }

      default:
        break;
    }

    // Schedule render
    scheduleReplayRender(panel, "agentic-replay");
  }

  function exitReplay(panel) {
    if (!panel?.state) return;
    if (originalGraphSnapshot) {
      _defaultApplyReplayOriginalGraph(originalGraphSnapshot);
    }
    restoreReplayBaseline(panel);
    currentStageIdx = -1;
    _replayActive = false;
    updateNavButtons();
    clearBtn.disabled = true;
  }

  // ── Event handlers ───────────────────────────────────────────────────

  async function fetchRuns() {
    try {
      const res = await fetch(RUNS_ENDPOINT);
      if (!res.ok) {
        throw new Error(`Failed to fetch runs: ${res.status}`);
      }
      const data = await res.json();
      if (!data?.ok || !Array.isArray(data.runs)) {
        throw new Error("Invalid runs response");
      }
      return data.runs;
    } catch (e) {
      showError(e?.message || String(e));
      return [];
    }
  }

  async function fetchTests(runId) {
    try {
      const url = TESTS_ENDPOINT_TEMPLATE.replace("{run_id}", encodeURIComponent(runId));
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch tests: ${res.status}`);
      }
      const data = await res.json();
      if (!data?.ok || !Array.isArray(data.tests)) {
        throw new Error("Invalid tests response");
      }
      return data.tests;
    } catch (e) {
      showError(e?.message || String(e));
      return [];
    }
  }

  async function fetchScenario(runId, testId) {
    try {
      const url = SCENARIO_ENDPOINT_TEMPLATE
        .replace("{run_id}", encodeURIComponent(runId))
        .replace("{test_id}", encodeURIComponent(testId));
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Failed to fetch scenario: ${res.status}`);
      }
      const data = await res.json();
      if (!data?.ok) {
        throw new Error("Invalid scenario response");
      }
      return data;
    } catch (e) {
      showError(e?.message || String(e));
      return null;
    }
  }

  loadBtn.addEventListener("click", async () => {
    if (!selectedRunId || !selectedTestId) {
      showError("Select a run and test first");
      return;
    }
    showError("");
    loadBtn.disabled = true;
    loadBtn.textContent = "Loading...";

    try {
      const data = await fetchScenario(selectedRunId, selectedTestId);
      if (!data) {
        loadBtn.disabled = false;
        loadBtn.textContent = "Load";
        return;
      }

      scenarioData = data;
      stages = Array.isArray(data.stages) ? data.stages : [];
      const panel = options._panel || helpers.currentAgentPanel();
      if (!panel?.state) {
        throw new Error("No active agent panel");
      }
      const panelPhase = panel.state.phase;
      if (panelPhase === helpers.PANEL_STATE.SUBMITTING || panelPhase === helpers.PANEL_STATE.APPLYING) {
        throw new Error("Replay is blocked while a production submit/apply is in flight");
      }

      captureReplayBaseline(panel);
      captureOriginalGraph();
      if (data.original_graph) {
        originalGraphSnapshot = clonePlainData(data.original_graph);
      }

      _replayActive = true;
      clearBtn.disabled = false;

      if (stages.length > 0) {
        applyStage(0);
      } else {
        showError("No replay stages available");
        currentStageIdx = -1;
        updateNavButtons();
      }
    } catch (e) {
      showError(e?.message || String(e));
    } finally {
      loadBtn.disabled = !(selectedRunId && selectedTestId);
      loadBtn.textContent = "Load";
    }
  });

  prevBtn.addEventListener("click", () => {
    if (currentStageIdx > 0) {
      applyStage(currentStageIdx - 1);
    }
  });

  nextBtn.addEventListener("click", () => {
    if (currentStageIdx < stages.length - 1) {
      applyStage(currentStageIdx + 1);
    }
  });

  clearBtn.addEventListener("click", () => {
    const panel = helpers.currentAgentPanel();
    exitReplay(panel);
    showError("");
    scenarioData = null;
    stages = [];
    currentStageIdx = -1;
    _replayActive = false;
    updateNavButtons();
    clearBtn.disabled = true;
    loadBtn.disabled = !(selectedRunId && selectedTestId);
    // Re-render to clear replay state
    if (panel) {
      scheduleReplayRender(panel, "agentic-replay-clear");
    }
  });

  // Keyboard navigation (left/right arrows)
  toolbar.addEventListener("keydown", (e) => {
    if (!_replayActive) return;
    if (e.key === "ArrowLeft") {
      e.preventDefault();
      e.stopPropagation();
      if (currentStageIdx > 0) {
        applyStage(currentStageIdx - 1);
      }
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      e.stopPropagation();
      if (currentStageIdx < stages.length - 1) {
        applyStage(currentStageIdx + 1);
      }
    }
  });
  // Make toolbar focusable for keyboard events
  toolbar.tabIndex = 0;

  // ── Selector event handlers ──────────────────────────────────────────

  runSelect.addEventListener("change", async () => {
    selectedRunId = runSelect.value || null;
    loadBtn.disabled = !(selectedRunId && selectedTestId);
    showError("");

    // Clear test selector
    while (testSelect.options.length > 1) {
      testSelect.remove(1);
    }
    testSelect.value = "";
    selectedTestId = null;

    if (selectedRunId) {
      const tests = await fetchTests(selectedRunId);
      for (const t of tests) {
        const opt = el("option", t.label || t.test_id);
        opt.value = t.test_id;
        testSelect.appendChild(opt);
      }
      if (tests.length === 0) {
        showError("No tests available for this run");
      }
    }
  });

  testSelect.addEventListener("change", () => {
    selectedTestId = testSelect.value || null;
    loadBtn.disabled = !(selectedRunId && selectedTestId);
    showError("");
  });

  // ── Load runs on mount ───────────────────────────────────────────────

  fetchRuns().then((runs) => {
    for (const r of runs) {
      const opt = el("option", r.label || r.run_id);
      opt.value = r.run_id;
      runSelect.appendChild(opt);
    }
    if (runs.length === 0) {
      showError("No replay runs available");
    }
  });

  return {
    toggle: toggleBtn,
    toolbar,
    runSelect,
    testSelect,
    loadButton: loadBtn,
    prevButton: prevBtn,
    nextButton: nextBtn,
    clearButton: clearBtn,
    stageLabel,
    /** Expose for tests */
    _applyStage: applyStage,
    _exitReplay: exitReplay,
    _getStages: () => stages,
    _getCurrentStageIdx: () => currentStageIdx,
    _getReplayActive: () => _replayActive,
  };
}
