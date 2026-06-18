import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  normalizeAgentEditResponse,
  readCandidate,
  readCandidateGraph,
  readEligibility,
  readLatestCandidate,
  readOutcome,
  readRebaselineRecovery,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_response_contract.js";

import {
  normalizeAgentTurnPayload,
  extractAgentTurnPayload,
  isTerminalAgentTurnStatus,
  agentTurnProgressLabel,
  AGENT_TURN_STATUSES,
  AGENT_TURN_ENTRY_TYPES,
} from "../../vibecomfy/comfy_nodes/web/agent_turn_feed.js";

import {
  normalizeExecutorPhasePayload,
  extractExecutorPhasePayload,
  normalizeExecutorProgressSnapshot,
  createExecutorProgressSnapshot,
  progressFromExecutorPhase,
  isExecutorProgressComplete,
  executorProgressLabel,
  EXECUTOR_PHASES,
  EXECUTOR_PHASE_STATUSES,
} from "../../vibecomfy/comfy_nodes/web/executor_progress.js";

import {
  buildStatusUrl,
  routeOptionsFromStatus,
  ROUTE_STATUS_KIND,
} from "../../vibecomfy/comfy_nodes/web/agent_status_poller.js";

// ── Fixture loader ────────────────────────────────────────────────────────

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FIXTURES_DIR = path.resolve(__dirname, "..", "fixtures", "payload_contracts");

function loadFixture(name) {
  const filePath = path.join(FIXTURES_DIR, name);
  const raw = readFileSync(filePath, "utf-8");
  return JSON.parse(raw);
}

// ── Agent edit response fixtures (routed through normalizeAgentEditResponse) ─

test("normalizeAgentEditResponse — agent_edit_accept_response.json", () => {
  const raw = loadFixture("agent_edit_accept_response.json");
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/fixture/accept" });

  // Stable public fields
  assert.equal(typeof normalized.ok, "boolean");
  assert.equal(normalized.ok, true);
  assert.equal(normalized.outcome.kind, "candidate");
  assert.ok(normalized.candidateGraph, "should have candidateGraph");
  assert.ok(normalized.candidate, "should have candidate");
  assert.deepEqual(normalized.eligibility, {
    applyable: true,
    reason: "applyable",
    message: "Ready to apply.",
    warnings: [],
  });
  assert.equal(normalized.sessionId, "session-stale-arrival");

  // Idempotent
  const second = normalizeAgentEditResponse(normalized, { endpoint: "/fixture/accept" });
  assert.equal(normalized, second);
});

test("normalizeAgentEditResponse — agent_edit_reject_response.json (legacy-inference-limited)", () => {
  const raw = loadFixture("agent_edit_reject_response.json");

  // This fixture lacks graph/outcome/clarification hints, so legacy inference throws.
  // It's a minimal reject acknowledgment.
  assert.throws(
    () => normalizeAgentEditResponse(raw, { endpoint: "/fixture/reject" }),
    /missing outcome/i,
  );

  // Allowable: assert at least one stable public field exists on the raw fixture
  assert.equal(raw.ok, true);
  assert.equal(raw.action, "reject");
  assert.equal(raw.session_id, "session-reject");
});

test("normalizeAgentEditResponse — agent_edit_rebaseline_response.json (legacy-inference-limited)", () => {
  const raw = loadFixture("agent_edit_rebaseline_response.json");

  // This fixture has apply_eligibility but no graph/outcome/clarification, so legacy inference throws.
  assert.throws(
    () => normalizeAgentEditResponse(raw, { endpoint: "/fixture/rebaseline" }),
    /missing outcome/i,
  );

  // Assert stable public fields
  assert.equal(raw.ok, true);
  assert.equal(raw.action, "rebaseline");
  assert.equal(typeof raw.apply_eligibility, "object");
  assert.equal(raw.apply_eligibility.applyable, false);
});

test("normalizeAgentEditResponse — agent_executor_clarify_response.json", () => {
  const raw = loadFixture("agent_executor_clarify_response.json");
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/fixture/clarify" });

  assert.equal(typeof normalized.ok, "boolean");
  assert.equal(normalized.ok, true);
  assert.equal(normalized.outcome.kind, "clarify");
  assert.equal(normalized.outcome.question, "Should I replace the sampler?");
  assert.equal(normalized.clarificationRequired, true);
});

test("normalizeAgentEditResponse — agent_executor_failure_response.json", () => {
  const raw = loadFixture("agent_executor_failure_response.json");
  const normalized = normalizeAgentEditResponse(raw, { endpoint: "/fixture/failure" });

  assert.equal(typeof normalized.ok, "boolean");
  assert.equal(normalized.ok, false);
  assert.equal(normalized.outcome.kind, "error");
  assert.equal(normalized.outcome.failureKind, "ProviderError");
  assert.ok(normalized.outcome.agentFailureContext);
});

// ── Executor response fixtures (not agent-edit responses; validated structurally) ─

test("agent_executor_success_response.json — structural contract", () => {
  const raw = loadFixture("agent_executor_success_response.json");

  // This is an executor response, not an agent-edit response. Validate known fields.
  assert.equal(raw.ok, true);
  assert.equal(raw.mode, "respond");
  assert.equal(typeof raw.reply, "string");
  assert.ok(raw.reply.length > 0);
  assert.equal(raw.session_id, "session-1");
  assert.ok(raw.report, "should have executor report");
  assert.equal(raw.report.executor.plan.reply, true);
});

test("agent_executor_request.json — structural contract", () => {
  const raw = loadFixture("agent_executor_request.json");

  // This is a submit request, not a response. Validate known fields.
  assert.equal(typeof raw.query, "string");
  assert.ok(raw.query.length > 0);
  assert.equal(raw.session_id, "sess-abc");
  assert.ok(raw.graph, "should have graph");
  assert.ok(Array.isArray(raw.graph.nodes));
  assert.ok(raw.graph.nodes.length >= 2);
  assert.equal(raw.route, "arnold");
  assert.equal(raw.model, "default");
  assert.equal(typeof raw.idempotency_key, "string");
  assert.ok(raw.idempotency_key.length > 0);
});

// ── Chat rehydrate and session bundle fixtures (structural contract) ──────

test("chat_rehydrate_response.json — structural contract", () => {
  const raw = loadFixture("chat_rehydrate_response.json");

  // This is a chat rehydrate response. Validate known fields.
  assert.equal(raw.ok, true);
  assert.equal(raw.exists, true);
  assert.equal(raw.session_id, "sess-123");
  assert.ok(raw.session_path, "should have session_path");
  assert.ok(raw.detail_json_path, "should have detail_json_path");
  assert.ok(Array.isArray(raw.messages));
  assert.ok(raw.messages.length >= 2);

  // Latest candidate is an agent-edit sub-payload; validate it normalizes
  assert.ok(raw.latest_candidate, "should have latest_candidate");
  const candidateNorm = normalizeAgentEditResponse(raw.latest_candidate, {
    endpoint: "/fixture/chat_rehydrate:latest_candidate",
  });
  assert.equal(candidateNorm.outcome.kind, "candidate");
  assert.ok(candidateNorm.candidateGraph);

  // Baseline fields
  assert.equal(raw.baseline.baseline_turn_id, "0000");
  assert.equal(typeof raw.baseline.baseline_graph_hash, "string");
});

test("session_bundle_response.json — structural contract", () => {
  const raw = loadFixture("session_bundle_response.json");

  // This is a session bundle response. Validate known fields.
  assert.equal(raw.ok, true);
  assert.equal(raw.exists, true);
  assert.ok(raw.session_path, "should have session_path");
  assert.equal(typeof raw.total_bytes, "number");
  assert.ok(raw.total_bytes > 0);
  assert.ok(Array.isArray(raw.files));
  assert.ok(raw.files.length >= 2);
  assert.equal(raw.files[0].name, "turns/0001/response.json");
  assert.ok(typeof raw.files[0].text, "string");
});

// ── Websocket agent turn fixtures ─────────────────────────────────────────

const agentTurnFixtures = [
  "websocket_agent_edit_turn_clarify.json",
  "websocket_agent_edit_turn_done.json",
  "websocket_agent_edit_turn_progress.json",
];

for (const fixtureName of agentTurnFixtures) {
  test(`normalizeAgentTurnPayload — ${fixtureName}`, () => {
    const raw = loadFixture(fixtureName);
    const normalized = normalizeAgentTurnPayload(raw);

    assert.ok(typeof normalized === "object" && normalized !== null,
      `${fixtureName}: normalized should be an object`);
    assert.ok(typeof normalized.session_id === "string" && normalized.session_id.length > 0,
      `${fixtureName}: normalized.session_id should be a non-empty string`);
    assert.ok(typeof normalized.turn_id === "string" && normalized.turn_id.length > 0,
      `${fixtureName}: normalized.turn_id should be a non-empty string`);
    assert.ok(typeof normalized.status === "string" && normalized.status.length > 0,
      `${fixtureName}: normalized.status should be a non-empty string`);

    // Verify status is a recognized agent turn status
    assert.ok(AGENT_TURN_STATUSES.includes(normalized.status),
      `${fixtureName}: normalized.status "${normalized.status}" should be a valid AGENT_TURN_STATUS`);

    // Verify entry_type is recognized
    assert.ok(AGENT_TURN_ENTRY_TYPES.includes(normalized.entry_type),
      `${fixtureName}: normalized.entry_type "${normalized.entry_type}" should be valid`);

    // Verify isTerminalAgentTurnStatus works
    const isTerminal = isTerminalAgentTurnStatus(normalized.status);
    assert.equal(typeof isTerminal, "boolean",
      `${fixtureName}: isTerminalAgentTurnStatus should return boolean`);

    // Verify agentTurnProgressLabel returns a string
    const label = agentTurnProgressLabel(normalized);
    assert.ok(typeof label === "string",
      `${fixtureName}: agentTurnProgressLabel should return a string`);

    // Verify extractAgentTurnPayload handles both direct and detail-wrapped
    const directExtract = extractAgentTurnPayload(raw);
    assert.ok(typeof directExtract === "object" && directExtract !== null,
      `${fixtureName}: extractAgentTurnPayload(direct) should extract payload`);

    const wrappedExtract = extractAgentTurnPayload({ detail: raw });
    assert.ok(typeof wrappedExtract === "object" && wrappedExtract !== null,
      `${fixtureName}: extractAgentTurnPayload(wrapped) should extract payload`);
    assert.deepEqual(directExtract, wrappedExtract,
      `${fixtureName}: extractAgentTurnPayload should return same payload for direct and wrapped`);
  });
}

// ── Websocket executor phase fixtures ─────────────────────────────────────

const executorPhaseFixtures = [
  "websocket_executor_phase_classify.json",
  "websocket_executor_phase_implement.json",
  "websocket_executor_phase_reply.json",
  "websocket_executor_phase_research.json",
];

for (const fixtureName of executorPhaseFixtures) {
  test(`normalizeExecutorPhasePayload — ${fixtureName}`, () => {
    const raw = loadFixture(fixtureName);
    const normalized = normalizeExecutorPhasePayload(raw);

    assert.ok(typeof normalized === "object" && normalized !== null,
      `${fixtureName}: normalized should be an object`);
    assert.ok(typeof normalized.phase === "string" && normalized.phase.length > 0,
      `${fixtureName}: normalized.phase should be a non-empty string`);
    assert.ok(EXECUTOR_PHASES.includes(normalized.phase),
      `${fixtureName}: normalized.phase "${normalized.phase}" should be a valid EXECUTOR_PHASE`);
    assert.ok(typeof normalized.status === "string" && normalized.status.length > 0,
      `${fixtureName}: normalized.status should be a non-empty string`);
    assert.ok(EXECUTOR_PHASE_STATUSES.includes(normalized.status),
      `${fixtureName}: normalized.status "${normalized.status}" should be a valid EXECUTOR_PHASE_STATUS`);

    // Verify extractExecutorPhasePayload handles both direct and detail-wrapped
    const directExtract = extractExecutorPhasePayload(raw);
    assert.ok(typeof directExtract === "object" && directExtract !== null,
      `${fixtureName}: extractExecutorPhasePayload(direct) should extract payload`);

    const wrappedExtract = extractExecutorPhasePayload({ detail: raw });
    assert.ok(typeof wrappedExtract === "object" && wrappedExtract !== null,
      `${fixtureName}: extractExecutorPhasePayload(wrapped) should extract payload`);

    // Verify progress derivation
    const progress = progressFromExecutorPhase(normalized);
    assert.ok(typeof progress === "object" && progress !== null,
      `${fixtureName}: progressFromExecutorPhase should return a progress snapshot`);
    assert.ok(typeof progress.decide === "string",
      `${fixtureName}: progress snapshot should have decide field`);
    assert.ok(typeof progress.research === "string",
      `${fixtureName}: progress snapshot should have research field`);
    assert.ok(typeof progress.execute === "string",
      `${fixtureName}: progress snapshot should have execute field`);
    assert.ok(typeof progress.review === "string",
      `${fixtureName}: progress snapshot should have review field`);

    // Verify progress utilities
    const validated = normalizeExecutorProgressSnapshot(progress);
    assert.ok(validated !== null,
      `${fixtureName}: normalizeExecutorProgressSnapshot should validate derived progress`);
    const complete = isExecutorProgressComplete(progress);
    assert.equal(typeof complete, "boolean",
      `${fixtureName}: isExecutorProgressComplete should return boolean`);
    const label = executorProgressLabel(progress);
    assert.ok(typeof label === "string",
      `${fixtureName}: executorProgressLabel should return a string`);
  });
}

// ── Agent status fixtures ─────────────────────────────────────────────────

test("agent status helpers — agent_status_ready.json", () => {
  const raw = loadFixture("agent_status_ready.json");

  // buildStatusUrl
  assert.equal(buildStatusUrl("arnold", "default"),
    "/vibecomfy/agent/status?route=arnold&model=default");
  assert.equal(buildStatusUrl("", ""),
    "/vibecomfy/agent/status");

  // routeOptionsFromStatus
  const routeOptions = routeOptionsFromStatus(raw);
  assert.ok(routeOptions !== null);
  assert.ok(typeof routeOptions === "object" && !Array.isArray(routeOptions));
  assert.ok(routeOptions.auto);
  assert.ok(routeOptions.deepseek);
  assert.equal(routeOptions.auto.normalized_route, "arnold");
  assert.equal(routeOptions.deepseek.browser_api_key_allowed, true);

  // Stable public fields on raw fixture
  assert.equal(raw.ok, true);
  assert.equal(raw.provider_available, true);
  assert.equal(raw.route, "arnold");
});

test("agent status helpers — agent_status_malformed.json (malformed route_options)", () => {
  const raw = loadFixture("agent_status_malformed.json");

  // route_options is "not-an-object" — should return null
  const routeOptions = routeOptionsFromStatus(raw);
  assert.equal(routeOptions, null);

  // Stable public fields
  assert.equal(raw.ok, true);
  assert.equal(raw.provider_available, true);
  assert.equal(raw.route, "arnold");
  assert.equal(raw.route_options, "not-an-object");
});

test("agent status helpers — agent_status_unavailable.json (unavailable status)", () => {
  const raw = loadFixture("agent_status_unavailable.json");

  // No route_options field — should return null
  const routeOptions = routeOptionsFromStatus(raw);
  assert.equal(routeOptions, null);

  // Stable public fields
  assert.equal(raw.ok, false);
  assert.equal(raw.provider_available, false);
  assert.equal(typeof raw.message, "string");
  assert.ok(raw.message.length > 0);
});

// ── Malformed / missing-option behavior tests ─────────────────────────────

test("routeOptionsFromStatus handles null and non-object inputs", () => {
  assert.equal(routeOptionsFromStatus(null), null);
  assert.equal(routeOptionsFromStatus(undefined), null);
  assert.equal(routeOptionsFromStatus("string"), null);
  assert.equal(routeOptionsFromStatus(42), null);
  assert.equal(routeOptionsFromStatus([]), null);
  assert.equal(routeOptionsFromStatus({}), null);
  assert.equal(routeOptionsFromStatus({ route_options: [] }), null);
  assert.equal(routeOptionsFromStatus({ route_options: "string" }), null);
});

test("routeOptionsFromStatus handles missing route_options gracefully", () => {
  const status = { ok: true, provider_available: true, route: "arnold" };
  assert.equal(routeOptionsFromStatus(status), null);
});

test("normalizeAgentTurnPayload returns null for non-object input", () => {
  assert.equal(normalizeAgentTurnPayload(null), null);
  assert.equal(normalizeAgentTurnPayload(undefined), null);
  assert.equal(normalizeAgentTurnPayload("string"), null);
  assert.equal(normalizeAgentTurnPayload(42), null);
  assert.equal(normalizeAgentTurnPayload([]), null);
  assert.equal(normalizeAgentTurnPayload({}), null); // missing session_id
});

test("normalizeExecutorPhasePayload returns null for non-object input", () => {
  assert.equal(normalizeExecutorPhasePayload(null), null);
  assert.equal(normalizeExecutorPhasePayload(undefined), null);
  assert.equal(normalizeExecutorPhasePayload("string"), null);
  assert.equal(normalizeExecutorPhasePayload(42), null);
  assert.equal(normalizeExecutorPhasePayload([]), null);
  assert.equal(normalizeExecutorPhasePayload({}), null); // missing phase
});

test("normalizeExecutorPhasePayload returns null for unrecognized phase", () => {
  assert.equal(normalizeExecutorPhasePayload({ phase: "invalid_phase", status: "start" }), null);
});

test("createExecutorProgressSnapshot defaults missing stages to pending", () => {
  const empty = createExecutorProgressSnapshot();
  assert.deepEqual(empty, {
    decide: "pending",
    research: "pending",
    execute: "pending",
    review: "pending",
  });
});

test("createExecutorProgressSnapshot with partial overrides", () => {
  const partial = createExecutorProgressSnapshot({ decide: "done", research: "active" });
  assert.equal(partial.decide, "done");
  assert.equal(partial.research, "active");
  assert.equal(partial.execute, "pending");
  assert.equal(partial.review, "pending");
});

test("isExecutorProgressComplete returns false for pending snapshot", () => {
  const pending = createExecutorProgressSnapshot();
  assert.equal(isExecutorProgressComplete(pending), false);
});

test("isExecutorProgressComplete returns true for fully done snapshot", () => {
  const done = createExecutorProgressSnapshot({
    decide: "done",
    research: "done",
    execute: "done",
    review: "done",
  });
  assert.equal(isExecutorProgressComplete(done), true);
});

test("executorProgressLabel returns correct labels", () => {
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "active" })), "Decide");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "active" })), "Research");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "done", execute: "active" })), "Execute");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "done", execute: "done", review: "active" })), "Review");
  assert.equal(executorProgressLabel(createExecutorProgressSnapshot({ decide: "done", research: "done", execute: "done", review: "done" })), "Complete");
  assert.equal(executorProgressLabel(null), "Unknown");
  assert.equal(executorProgressLabel("invalid"), "Unknown");
});
