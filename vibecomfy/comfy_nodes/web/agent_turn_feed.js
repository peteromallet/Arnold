// agent_turn_feed.js — Browser-safe ESM normalizer for vibecomfy.agent_edit.turn events
//
// Exports pure helpers that validate and normalize websocket payloads emitted by
// the backend _agent_edit_turn_event_payload / _ws_send("vibecomfy.agent_edit.turn", ...)
// contract.  No Node, filesystem, or test-only dependencies.

// ── Internal helpers ────────────────────────────────────────────────────────

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value) {
  return typeof value === "string" ? value : null;
}

function asBoolean(value) {
  return typeof value === "boolean" ? value : null;
}

function asFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asInteger(value) {
  return Number.isInteger(value) ? value : null;
}

function asStringArray(value) {
  return Array.isArray(value) ? value.filter((entry) => typeof entry === "string") : null;
}

function compactObject(value) {
  const compact = {};
  for (const [key, entry] of Object.entries(value)) {
    if (entry !== null && entry !== undefined) {
      compact[key] = entry;
    }
  }
  return compact;
}

// ── Constants ───────────────────────────────────────────────────────────────

export const AGENT_TURN_STATUSES = Object.freeze([
  "progress",
  "done",
  "clarify",
  "budget_exhausted",
  "error",
]);

export const BATCH_TERMINAL_STATUSES = new Set(["done", "clarify", "budget_exhausted", "error"]);

export const AGENT_TURN_ENTRY_TYPES = Object.freeze(["batch", "durable"]);

// ── Statement summary normalization ─────────────────────────────────────────

/**
 * Normalize a single batch statement entry.
 * Returns a sorted-key object with { op_kind, status, message } or null.
 */
function normalizeStatement(entry) {
  if (!isObject(entry)) {
    return null;
  }
  const opKind = asString(entry.op_kind) || asString(entry.kind) || asString(entry.op);
  if (!opKind) {
    return null;
  }
  return compactObject({
    op_kind: opKind,
    status: asString(entry.status) || "unknown",
    message: asString(entry.message),
  });
}

/**
 * Normalize an array of statement entries. Skips invalid entries.
 */
function normalizeStatements(raw) {
  if (!Array.isArray(raw)) {
    return null;
  }
  const normalized = [];
  for (const entry of raw) {
    const norm = normalizeStatement(entry);
    if (norm) {
      normalized.push(norm);
    }
  }
  return normalized.length > 0 ? Object.freeze(normalized) : null;
}

// ── Diagnostic entry normalization ──────────────────────────────────────────

/**
 * Normalize a single diagnostic entry to { code, message }.
 */
function normalizeDiagnostic(entry) {
  if (!isObject(entry)) {
    return null;
  }
  const code = asString(entry.code);
  if (!code) {
    return null;
  }
  return compactObject({
    code,
    message: asString(entry.message),
  });
}

/**
 * Normalize an array of diagnostic entries. Skips invalid entries.
 * Caps at 5 entries (backend contract limit).
 */
function normalizeDiagnostics(raw) {
  if (!Array.isArray(raw)) {
    return null;
  }
  const normalized = [];
  for (const entry of raw) {
    const norm = normalizeDiagnostic(entry);
    if (norm) {
      normalized.push(norm);
    }
  }
  return normalized.length > 0 ? Object.freeze(normalized.slice(0, 5)) : null;
}

// ── Timing normalization ────────────────────────────────────────────────────

function normalizeTiming(raw) {
  if (!isObject(raw)) {
    return null;
  }
  return compactObject({
    model_elapsed_ms: asFiniteNumber(raw.model_elapsed_ms),
    engine_elapsed_ms: asFiniteNumber(raw.engine_elapsed_ms),
    turn_elapsed_ms: asFiniteNumber(raw.turn_elapsed_ms),
  });
}

// ── Budget normalization ────────────────────────────────────────────────────

function normalizeBudget(raw) {
  if (!isObject(raw)) {
    return null;
  }
  return compactObject({
    remaining_batches: asInteger(raw.remaining_batches),
    consecutive_errors: asInteger(raw.consecutive_errors),
  });
}

// ── Main normalizer ─────────────────────────────────────────────────────────

/**
 * Normalize a raw vibecomfy.agent_edit.turn websocket event payload.
 *
 * Accepts both the direct payload and the event detail wrapper.
 * Returns a frozen normalized object with only validated fields,
 * or null if the payload is not a valid agent turn event.
 *
 * @param {*} raw - raw websocket event or event.detail
 * @returns {object|null} frozen normalized payload, or null
 */
export function normalizeAgentTurnPayload(raw) {
  // Accept event.detail style or direct payload
  const payload = isObject(raw?.detail) ? raw.detail : raw;
  if (!isObject(payload)) {
    return null;
  }

  const sessionId = asString(payload.session_id);
  if (!sessionId) {
    return null;
  }

  const status = asString(payload.status) || "progress";
  const entryType = asString(payload.entry_type) || "batch";

  const normalized = compactObject({
    // Identity (required)
    session_id: sessionId,
    turn_id: asString(payload.turn_id),
    turn_number: asInteger(payload.turn_number),

    // Status
    entry_type: entryType,
    status,

    // Timing
    emitted_at: asString(payload.emitted_at),

    // User-facing message (truncated to 500 chars per contract)
    message: payload.message && typeof payload.message === "string"
      ? payload.message.slice(0, 500)
      : null,

    // Clarification
    clarification_required: asBoolean(payload.clarification_required),
    clarification_message: payload.clarification_message && typeof payload.clarification_message === "string"
      ? payload.clarification_message.slice(0, 500)
      : null,

    // Batch progress
    batch_ok: asBoolean(payload.batch_ok),
    statement_count: asInteger(payload.statement_count),
    landed_op_count: asInteger(payload.landed_op_count),

    // Statements
    statements: normalizeStatements(payload.statements),

    // Diagnostics
    diagnostics: normalizeDiagnostics(payload.diagnostics),

    // Exit mode / done summary
    exit_mode: asString(payload.exit_mode),
    done_summary: payload.done_summary && typeof payload.done_summary === "string"
      ? payload.done_summary.slice(0, 500)
      : null,

    // Budget snapshot
    budget: normalizeBudget(payload.budget),

    // Timing
    timing: normalizeTiming(payload.timing),
  });

  return Object.freeze(normalized);
}

/**
 * Extract a payload from a websocket event argument.
 * Handles CustomEvent-like objects (event.detail) and plain objects.
 *
 * @param {*} event - websocket event or plain payload
 * @returns {object|null} the raw payload object, or null
 */
export function extractAgentTurnPayload(event) {
  if (isObject(event?.detail)) {
    return event.detail;
  }
  return isObject(event) ? event : null;
}

/**
 * Check whether an agent turn status is terminal.
 */
export function isTerminalAgentTurnStatus(status) {
  return BATCH_TERMINAL_STATUSES.has(String(status || "").toLowerCase());
}

/**
 * Derive a human-readable progress label from a normalized agent turn payload.
 */
export function agentTurnProgressLabel(normalized) {
  if (!isObject(normalized)) {
    return "Unknown";
  }
  const status = normalized.status || "progress";
  if (status === "done") {
    return "Complete";
  }
  if (status === "clarify") {
    return "Needs Clarification";
  }
  if (status === "budget_exhausted") {
    return "Budget Exhausted";
  }
  if (status === "error") {
    return "Turn Error";
  }
  // "progress"
  const landed = normalized.landed_op_count;
  if (typeof landed === "number" && landed > 0) {
    return `Executing (${landed} ops landed)`;
  }
  const turnNum = normalized.turn_number;
  if (typeof turnNum === "number" && turnNum > 0) {
    return `Researching (turn ${turnNum})`;
  }
  return "Deciding";
}

export {
  isObject,
  asString,
  asBoolean,
  asFiniteNumber,
  asInteger,
  asStringArray,
  compactObject,
  normalizeStatement,
  normalizeStatements,
  normalizeDiagnostic,
  normalizeDiagnostics,
  normalizeTiming,
  normalizeBudget,
};
