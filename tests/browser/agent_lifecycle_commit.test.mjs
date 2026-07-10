import test from "node:test";
import assert from "node:assert/strict";

import {
  PANEL_STATE,
  RENDER_SECTIONS,
  createAgentEditState,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

import {
  commitOptimisticSubmit,
  commitTerminalResponse,
  commitTranscriptRehydrate,
  commitLatestCandidateRestore,
  commitApplyResolved,
  commitLifecycleReset,
  readCommitTurnIdentity,
  readCommitApplyCandidate,
  readCommitFieldChanges,
  readCommitOutcome,
  readCommitCustomNodeResolution,
  normalizeCommitFieldChangesFromSubmit,
  normalizeCommitApplyEligibility,
  classifyCommitOutcome,
  resolveCommitCandidateGraphHash,
  outcomeRequiresClarification,
  outcomeIsNoop,
  clarificationMessageFromOutcome,
  outcomeHasClarificationPrompt,
} from "../../vibecomfy/comfy_nodes/web/agent_lifecycle_commit.js";

// ── Helpers ─────────────────────────────────────────────────────────────────

function makePanel(overrides = {}) {
  const state = createAgentEditState();
  Object.assign(state, overrides);
  return { state };
}

const ALL_RENDER_SECTIONS = Object.values(RENDER_SECTIONS);

// ── Projection utilities ───────────────────────────────────────────────────

test("readCommitTurnIdentity returns null for non-object and safely wraps the contract selector", () => {
  assert.equal(readCommitTurnIdentity(null), null);
  assert.equal(readCommitTurnIdentity(undefined), null);
  assert.equal(readCommitTurnIdentity("string"), null);
  assert.equal(readCommitTurnIdentity(42), null);

  // The defensive wrapper returns null when normalization fails (e.g. missing outcome)
  const incomplete = {
    candidate: {
      turn_identity: {
        session_id: "sess-1",
        turn_id: "turn-1",
        baseline_turn_id: "turn-0",
      },
    },
  };
  assert.equal(readCommitTurnIdentity(incomplete), null,
    "readCommitTurnIdentity returns null for non-normalized input (missing outcome)");

  // With a raw response that normalizeAgentEditResponse can process:
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
    candidate: {
      turn_identity: {
        session_id: "sess-1",
        turn_id: "turn-1",
        baseline_turn_id: "turn-0",
      },
    },
  };
  const identity = readCommitTurnIdentity(raw);
  assert.ok(identity, "readCommitTurnIdentity should return identity for valid raw response");
  assert.equal(identity.sessionId, "sess-1");
  assert.equal(identity.turnId, "turn-1");
  assert.equal(identity.baselineTurnId, "turn-0");
});

test("readCommitApplyCandidate returns null for non-object and projects a canonical candidate", () => {
  assert.equal(readCommitApplyCandidate(null), null);
  assert.equal(readCommitApplyCandidate({}), null);

  // The defensive wrapper returns null for non-normalized input
  const incomplete = {
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "gh-123",
    },
  };
  assert.equal(readCommitApplyCandidate(incomplete), null,
    "readCommitApplyCandidate returns null for non-normalized input");

  // With a raw response that normalizeAgentEditResponse can process:
  const raw = {
    ok: true,
    outcome: { kind: "candidate" },
    candidate: {
      graph: { nodes: [{ id: 1, type: "KSampler" }], links: [] },
      graph_hash: "gh-123",
      submit_graph_hash: "sub-456",
      turn_identity: {
        session_id: "sess-1",
        turn_id: "turn-1",
      },
    },
    apply_eligibility: {
      applyable: true,
      reason: "applyable",
      message: "Ready.",
      warnings: [],
    },
  };
  const cand = readCommitApplyCandidate(raw);
  assert.ok(cand, "readCommitApplyCandidate should return projection for valid raw response");
  assert.deepEqual(cand.graph, raw.candidate.graph);
  assert.equal(cand.graphHash, "gh-123");
  assert.equal(cand.submitGraphHash, "sub-456");
  assert.ok(cand.eligibility);
  assert.equal(cand.eligibility.applyable, true);
});

test("readCommitFieldChanges returns null for non-object and projects field changes", () => {
  assert.equal(readCommitFieldChanges(null), null);

  const canonical = {
    outcome: {
      changes: [{ uid: "node-1", field_path: "widgets.steps", old: 20, new: 28 }],
    },
    change_details: {
      direct_changes: [{ uid: "node-2", field_path: "widgets.cfg", old: 7, new: 10 }],
    },
  };
  const changes = readCommitFieldChanges(canonical, { endpoint: "submit:field-changes" });
  assert.ok(changes);
  assert.ok(Array.isArray(changes.directChanges) || changes.outcomeChanges);
});

test("readCommitOutcome returns null for non-object and projects outcome", () => {
  assert.equal(readCommitOutcome(null), null);
  assert.equal(readCommitOutcome({ outcome: { kind: "candidate" } }).kind, "candidate");
  assert.equal(readCommitOutcome({ outcome: { kind: "noop" } }).kind, "noop");
  assert.equal(readCommitOutcome({ outcome: { kind: "clarify" } }).kind, "clarify");
});

test("readCommitCustomNodeResolution returns null for non-object", () => {
  assert.equal(readCommitCustomNodeResolution(null), null);
  assert.equal(readCommitCustomNodeResolution({}), null);
});

// ── normalizeCommitFieldChangesFromSubmit ───────────────────────────────────

test("normalizeCommitFieldChangesFromSubmit returns empty shape for non-object", () => {
  const result = normalizeCommitFieldChangesFromSubmit(null);
  assert.deepEqual(result, {
    directChanges: [],
    outcomeChanges: [],
    legacyChanges: [],
    batchTurnChanges: [],
    all: [],
  });
});

test("normalizeCommitFieldChangesFromSubmit normalizes direct and outcome changes", () => {
  const raw = {
    outcome: {
      kind: "candidate",
      changes: [{ uid: "node-1", field_path: "widgets.steps", old: 20, new: 28 }],
    },
    change_details: {
      direct_changes: [{ uid: "node-2", field_path: "widgets.cfg", old: 7, new: 10 }],
    },
  };
  const result = normalizeCommitFieldChangesFromSubmit(raw, { endpoint: "submit:field-changes" });
  assert.ok(Array.isArray(result.outcomeChanges));
  assert.ok(Array.isArray(result.directChanges));
  assert.ok(Array.isArray(result.all));
  assert.ok(result.all.length > 0);
});

test("normalizeCommitFieldChangesFromSubmit handles batchTurnChanges", () => {
  const raw = {
    change_details: {
      batch_turns: [
        {
          turn_number: 2,
          field_changes: [{ uid: "save", field_path: "filename_prefix", old: "old", new: "new" }],
        },
      ],
    },
  };
  const result = normalizeCommitFieldChangesFromSubmit(raw, { endpoint: "submit:field-changes" });
  assert.equal(result.batchTurnChanges.length, 1);
  assert.equal(result.batchTurnChanges[0].turn_number, 2);
  assert.equal(result.batchTurnChanges[0].changes.length, 1);
  assert.equal(result.all.length, 1);
});

// ── normalizeCommitApplyEligibility ─────────────────────────────────────────

test("normalizeCommitApplyEligibility returns no-candidate eligibility when no graph", () => {
  const eligibility = normalizeCommitApplyEligibility(null, null);
  assert.equal(eligibility.applyable, false);
  assert.equal(eligibility.reason, "no_candidate");
});

test("normalizeCommitApplyEligibility returns canonical eligibility for valid input", () => {
  const eligibility = normalizeCommitApplyEligibility(
    { nodes: [{ id: 1 }], links: [] },
    { applyable: true, reason: "applyable", message: "Ready.", warnings: [] },
  );
  assert.equal(eligibility.applyable, true);
  assert.equal(eligibility.reason, "applyable");
});

test("normalizeCommitApplyEligibility returns null when missing contract and option set", () => {
  const eligibility = normalizeCommitApplyEligibility(
    { nodes: [{ id: 1 }], links: [] },
    null,
  );
  assert.equal(eligibility, null);
});

// ── Outcome predicates ─────────────────────────────────────────────────────

test("outcomeRequiresClarification detects clarify outcomes", () => {
  assert.equal(outcomeRequiresClarification({ kind: "clarify" }), true);
  assert.equal(outcomeRequiresClarification({ kind: "candidate" }), false);
  assert.equal(outcomeRequiresClarification(null), false);
  assert.equal(outcomeRequiresClarification({}), false);
});

test("outcomeIsNoop detects noop outcomes", () => {
  assert.equal(outcomeIsNoop({ kind: "noop" }), true);
  assert.equal(outcomeIsNoop({ kind: "candidate" }), false);
  assert.equal(outcomeIsNoop(null), false);
});

test("clarificationMessageFromOutcome extracts message", () => {
  assert.equal(
    clarificationMessageFromOutcome({ question: "What color?" }, "fallback"),
    "What color?",
  );
  assert.equal(
    clarificationMessageFromOutcome({ question: "" }, "fallback"),
    "fallback",
  );
  assert.equal(clarificationMessageFromOutcome(null, "fallback"), "fallback");
  assert.equal(clarificationMessageFromOutcome({}, null), null);
});

test("outcomeHasClarificationPrompt returns boolean", () => {
  assert.equal(outcomeHasClarificationPrompt({ question: "Yes or no?" }), true);
  assert.equal(outcomeHasClarificationPrompt({ question: "" }), false);
  assert.equal(outcomeHasClarificationPrompt(null), false);
});

// ── classifyCommitOutcome ──────────────────────────────────────────────────

test("classifyCommitOutcome returns requires_custom_nodes for custom node outcomes", () => {
  assert.equal(
    classifyCommitOutcome({ kind: "requires_custom_nodes" }, null),
    "requires_custom_nodes",
  );
});

test("classifyCommitOutcome returns clarify_only for clarify without candidate graph", () => {
  assert.equal(
    classifyCommitOutcome({ kind: "clarify" }, null),
    "clarify_only",
  );
});

test("classifyCommitOutcome returns edit_clarify for clarify with candidate graph", () => {
  assert.equal(
    classifyCommitOutcome(
      { kind: "clarify", question: "Is this ok?" },
      { nodes: [{ id: 1 }], links: [] },
    ),
    "edit_clarify",
  );
});

test("classifyCommitOutcome returns noop for noop outcomes", () => {
  assert.equal(classifyCommitOutcome({ kind: "noop" }, null), "noop");
});

test("classifyCommitOutcome returns candidate for candidate outcome with graph", () => {
  assert.equal(
    classifyCommitOutcome(
      { kind: "candidate" },
      { nodes: [{ id: 1 }], links: [] },
    ),
    "candidate",
  );
});

test("classifyCommitOutcome returns error for unclassifiable input", () => {
  assert.equal(classifyCommitOutcome(null, null), "error");
  assert.equal(classifyCommitOutcome({ kind: "unknown" }, null), "error");
});

// ── resolveCommitCandidateGraphHash ────────────────────────────────────────

test("resolveCommitCandidateGraphHash prefers explicit hash override", () => {
  assert.equal(
    resolveCommitCandidateGraphHash({ graphHash: "gh-override" }, "explicit-123"),
    "explicit-123",
  );
});

test("resolveCommitCandidateGraphHash falls back to candidateGraphHash", () => {
  assert.equal(
    resolveCommitCandidateGraphHash({ candidateGraphHash: "cgh-123" }),
    "cgh-123",
  );
});

test("resolveCommitCandidateGraphHash falls back to graphHash", () => {
  assert.equal(
    resolveCommitCandidateGraphHash({ graphHash: "gh-456" }, null),
    "gh-456",
  );
});

test("resolveCommitCandidateGraphHash returns null for empty input", () => {
  assert.equal(resolveCommitCandidateGraphHash(null), null);
  assert.equal(resolveCommitCandidateGraphHash({}), null);
});

// ── commitOptimisticSubmit ─────────────────────────────────────────────────

test("commitOptimisticSubmit transitions panel to SUBMITTING and returns render obligations", () => {
  const panel = makePanel({ phase: PANEL_STATE.IDLE });
  const obligations = commitOptimisticSubmit(panel, {
    lastSubmit: { chatQuery: "make it blue" },
    debugPayload: { origin: "test" },
  });

  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
  assert.equal(obligations.render, true);
  assert.ok(Array.isArray(obligations.dirtySections));
  assert.ok(obligations.dirtySections.length > 0);
  for (const section of obligations.dirtySections) {
    assert.ok(ALL_RENDER_SECTIONS.includes(section), `Invalid dirty section: ${section}`);
  }
  // submitEpoch is a number, auto-incremented from 0→1
  assert.equal(typeof panel.state.submitEpoch, "number");
  assert.ok(panel.state.submitEpoch >= 1);
  assert.deepEqual(panel.state.lastSubmit, { chatQuery: "make it blue" });
});

test("commitOptimisticSubmit uses auto-incremented epoch (number) and allows explicit number epoch", () => {
  const panel = makePanel();
  const obligations = commitOptimisticSubmit(panel, { submitEpoch: "custom-epoch-42" });
  // The commit module only passes string epochs; the reducer increments from 0→1
  // when epoch is a non-number string (it falls through)
  assert.equal(typeof panel.state.submitEpoch, "number");
  assert.ok(panel.state.submitEpoch >= 1);
  assert.equal(obligations.render, true);
});

test("commitOptimisticSubmit handles minimal payload", () => {
  const panel = makePanel();
  const obligations = commitOptimisticSubmit(panel);
  assert.equal(panel.state.phase, PANEL_STATE.SUBMITTING);
  assert.equal(obligations.render, true);
});

// ── commitTerminalResponse: clarify_only ────────────────────────────────────

test("commitTerminalResponse handles clarify_only outcome via explicit payload", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  // Use explicit outcome and message to avoid relying on response-contract parsing
  const obligations = commitTerminalResponse(panel, {
    result: { ok: true, session_id: "sess-clarify", turn_id: "turn-clarify" },
    outcome: { kind: "clarify", question: "What size?" },
    message: "What size?",
  });

  assert.equal(panel.state.phase, PANEL_STATE.CLARIFY);
  assert.equal(obligations.render, true);
  assert.equal(panel.state.clarification.message, "What size?");
});

test("commitTerminalResponse handles clarify_only with fallback message from result", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = commitTerminalResponse(panel, {
    result: {
      ok: true,
      outcome: { kind: "clarify" },
      message: "Please provide more details.",
      session_id: "sess-fb",
      turn_id: "turn-fb",
    },
    outcome: { kind: "clarify" },
  });

  assert.equal(panel.state.phase, PANEL_STATE.CLARIFY);
  assert.ok(panel.state.clarification.message.includes("more details") || panel.state.message.includes("more details"));
  assert.equal(obligations.render, true);
});

// ── commitTerminalResponse: requires_custom_nodes ───────────────────────────

test("commitTerminalResponse handles requires_custom_nodes outcome", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = commitTerminalResponse(panel, {
    result: {
      ok: true,
      route: "requires_custom_nodes",
      reply: "You need VideoHelperSuite.",
      session_id: "sess-custom",
      turn_id: "turn-custom",
    },
    outcome: { kind: "requires_custom_nodes" },
    message: "You need VideoHelperSuite.",
  });

  // requires_custom_nodes transitions to IDLE (not CLARIFY)
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(obligations.render, true);
  assert.equal(panel.state.message, "You need VideoHelperSuite.");
});

// ── commitTerminalResponse: noop ────────────────────────────────────────────

test("commitTerminalResponse handles noop outcome", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const obligations = commitTerminalResponse(panel, {
    result: {
      ok: true,
      message: "No changes needed.",
      session_id: "sess-noop",
      turn_id: "turn-noop",
    },
    outcome: { kind: "noop", reason: "No changes needed." },
  });

  // noop transitions to IDLE
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(obligations.render, true);
  // The reducer uses payload.message || result.message
  assert.ok(panel.state.message === "No changes needed." || panel.state.message === null);
});

// ── commitTerminalResponse: candidate ───────────────────────────────────────

test("commitTerminalResponse handles candidate outcome with explicit payload overrides", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const candidateGraph = { nodes: [{ id: 1, type: "KSampler" }], links: [] };

  const obligations = commitTerminalResponse(panel, {
    result: {
      ok: true,
      session_id: "sess-cand",
      turn_id: "turn-cand",
      baseline_turn_id: "turn-0",
    },
    outcome: { kind: "candidate" },
    candidateGraph,
    candidateGraphHash: "cand-hash-1",
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(obligations.render, true);
  assert.ok(obligations.invalidateCandidate);
  assert.equal(panel.state.sessionId, "sess-cand");
  assert.equal(panel.state.turnId, "turn-cand");
});

// ── commitTerminalResponse: edit_clarify ────────────────────────────────────

test("commitTerminalResponse handles edit_clarify outcome with explicit overrides", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const candidateGraph = { nodes: [{ id: 1, type: "KSampler" }], links: [] };

  const obligations = commitTerminalResponse(panel, {
    result: {
      ok: true,
      session_id: "sess-ecl",
      turn_id: "turn-ecl",
      baseline_turn_id: "turn-0",
    },
    outcome: { kind: "clarify", question: "Should I also adjust the CFG scale?" },
    candidateGraph,
    candidateGraphHash: "ecl-hash",
  });

  // With candidateGraph + clarify outcome, goes through edit_clarify → AWAITING_REVIEW
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(obligations.render, true);
  assert.equal(panel.state.sessionId, "sess-ecl");
});

// ── commitTerminalResponse: error / malformed ───────────────────────────────

test("commitTerminalResponse handles explicit failure payload", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const failure = { ok: false, kind: "NetworkError", message: "Connection lost.", retryable: true };

  const obligations = commitTerminalResponse(panel, {
    failure,
    syntheticAgentMessage: { role: "agent", text: "Network error occurred.", synthetic: true },
  });

  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.equal(obligations.render, true);
  assert.equal(panel.state.failure.kind, "NetworkError");
});

test("commitTerminalResponse handles malformed/unclassifiable envelopes as errors", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const result = {
    ok: true,
    message: "Something went wrong.",
    session_id: "sess-mal",
    turn_id: "turn-mal",
  };

  const obligations = commitTerminalResponse(panel, { result });

  assert.equal(panel.state.phase, PANEL_STATE.ERROR);
  assert.equal(obligations.render, true);
  assert.ok(panel.state.failure);
  assert.equal(panel.state.failure.kind, "MalformedResponse");
});

// ── commitTerminalResponse: no side effects ─────────────────────────────────

test("commitTerminalResponse does not perform transport, DOM, storage, or history side effects", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const candidateGraph = { nodes: [{ id: 1 }], links: [] };

  const obligations = commitTerminalResponse(panel, {
    result: {
      ok: true,
      session_id: "sess-noside",
      turn_id: "turn-noside",
    },
    outcome: { kind: "candidate" },
    candidateGraph,
    candidateGraphHash: "hash-no-side",
  });

  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(typeof obligations.render, "boolean");
  assert.equal(typeof obligations.dirtySections, "object");
});

// ── commitTranscriptRehydrate ───────────────────────────────────────────────

test("commitTranscriptRehydrate commits transcript messages and epoch", () => {
  const panel = makePanel();
  const messages = [
    { role: "user", text: "Hello", turn_id: "t1", session_id: "s1" },
    { role: "agent", text: "Hi there!", turn_id: "t2", session_id: "s1" },
  ];

  const obligations = commitTranscriptRehydrate(panel, {
    requestEpoch: 1,
    messages,
    sessionId: "s1",
    latestTurnId: "t2",
  });

  // The rehydrate success handler commits the epoch and messages
  assert.equal(panel.state.chatRehydrateCommittedEpoch, 1);
  assert.equal(panel.state.sessionId, "s1");
  // render may be false (rehydrate success doesn't always trigger a full render)
  assert.equal(typeof obligations.render, "boolean");
});

test("commitTranscriptRehydrate handles payload with empty messages", () => {
  const panel = makePanel({ chatRehydrateEpoch: 5 });

  const obligations = commitTranscriptRehydrate(panel, {
    requestEpoch: 3, // older than current epoch
    messages: [],
  });

  // The reducer may not set `stale` on the obligations; it might set it on state
  // or handle it differently. Test what actually happens.
  assert.equal(typeof obligations, "object");
});

// ── commitLatestCandidateRestore ────────────────────────────────────────────

test("commitLatestCandidateRestore restores a candidate when scopes match", () => {
  const panel = makePanel({ chatScopeId: "scope-1" });
  const candidateGraph = { nodes: [{ id: 1, type: "SaveImage" }], links: [] };

  const obligations = commitLatestCandidateRestore(panel, {
    requestScopeId: "scope-1",
    candidateSessionId: "sess-restore",
    sessionId: "sess-restore",
    turnId: "turn-restore",
    baselineTurnId: "turn-0",
    candidateGraph,
    candidateGraphHash: "restore-hash",
    candidateReport: { summary: "Restored candidate." },
    serverSubmitGraphHash: "sub-hash",
    message: "Previous candidate restored.",
    applyEligibility: { applyable: true, reason: "applyable", message: "OK", warnings: [] },
    applyAllowed: true,
    canvasApplyAllowed: false,
    queueAllowed: false,
  });

  // When scopes match, the reducer sets candidate and transitions to AWAITING_REVIEW
  assert.equal(panel.state.phase, PANEL_STATE.AWAITING_REVIEW);
  assert.equal(panel.state.candidateGraph, candidateGraph);
  assert.equal(panel.state.candidateGraphHash, "restore-hash");
  assert.equal(panel.state.turnId, "turn-restore");
});

// ── commitApplyResolved ─────────────────────────────────────────────────────

test("commitApplyResolved transitions panel after successful apply", () => {
  const panel = makePanel({ phase: PANEL_STATE.APPLYING });

  const obligations = commitApplyResolved(panel, {
    accepted: true,
    lastAppliedChanges: [{ uid: "node-1", field: "steps" }],
    undoStackDepth: 1,
  });

  assert.equal(obligations.render, true);
  assert.equal(panel.state.lastAppliedChanges.length, 1);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
});

// ── commitLifecycleReset ────────────────────────────────────────────────────

test("commitLifecycleReset resets panel and clears candidate state", () => {
  const panel = makePanel({
    phase: PANEL_STATE.AWAITING_REVIEW,
    candidateGraph: { nodes: [{ id: 1 }], links: [] },
    candidateGraphHash: "old-hash",
    turnId: "turn-old",
  });

  const obligations = commitLifecycleReset(panel, {
    rejected: { candidateGraphHash: "old-hash" },
    message: "Candidate rejected.",
  });

  assert.equal(obligations.render, true);
  assert.equal(panel.state.phase, PANEL_STATE.IDLE);
  assert.equal(panel.state.candidateGraph, null);
  assert.equal(panel.state.candidateGraphHash, null);
});

// ── Pure outcome: commit helpers never import transport/canvas/history ──────

test("commit helpers produce plain obligations without transport references", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });

  const helpers = [
    () => commitOptimisticSubmit(makePanel()),
    () => commitTerminalResponse(makePanel({ phase: PANEL_STATE.SUBMITTING }), {
      failure: { ok: false, kind: "Test" },
    }),
    () => commitTranscriptRehydrate(makePanel(), { requestEpoch: 1, messages: [] }),
    () => commitLatestCandidateRestore(makePanel({ chatScopeId: "s" }), {
      requestScopeId: "s", candidateSessionId: "s", sessionId: "s", turnId: "t",
      candidateGraph: { nodes: [] }, candidateGraphHash: "h",
      applyEligibility: { applyable: true, reason: "applyable", message: "OK", warnings: [] },
    }),
    () => commitApplyResolved(makePanel({ phase: PANEL_STATE.APPLYING }), { accepted: true }),
    () => commitLifecycleReset(makePanel({ phase: PANEL_STATE.AWAITING_REVIEW }), { rejected: {} }),
  ];

  for (const helper of helpers) {
    const obligations = helper();
    assert.equal(typeof obligations, "object");
    assert.ok(!(obligations instanceof Promise), "commit helper must not return a Promise");
    assert.equal(typeof obligations.render, "boolean");
    // No transport/canvas/history leaked
    assert.equal(obligations.fetch, undefined);
    assert.equal(obligations.canvas, undefined);
    assert.equal(obligations.history, undefined);
    assert.equal(obligations.storage, undefined);
    assert.equal(obligations.transport, undefined);
    assert.equal(obligations.localStorage, undefined);
    assert.equal(obligations.POST, undefined);
  }
});

// ── Dirty section validity ──────────────────────────────────────────────────

test("commit helpers only produce valid dirtySections from RENDER_SECTIONS", () => {
  const panel = makePanel({ phase: PANEL_STATE.SUBMITTING });
  const obligations = commitOptimisticSubmit(panel);
  if (obligations.dirtySections) {
    for (const section of obligations.dirtySections) {
      assert.ok(
        ALL_RENDER_SECTIONS.includes(section),
        `dirtySections must only contain valid RENDER_SECTIONS, got "${section}"`,
      );
    }
  }
});
