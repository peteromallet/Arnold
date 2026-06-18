// executor_progress.js — Browser-safe ESM normalizer for vibecomfy.executor.phase events
//
// Exports pure helpers that validate and normalize websocket payloads emitted
// for executor phase transitions, plus the executor progress snapshot shape
// used in panel state.  No Node, filesystem, or test-only dependencies.

// ── Internal helpers ────────────────────────────────────────────────────────

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function asString(value) {
  return typeof value === "string" ? value : null;
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

// ── Phase taxonomy ──────────────────────────────────────────────────────────

export const EXECUTOR_PHASES = Object.freeze([
  "classify",
  "research",
  "implement",
  "reply",
]);

export const EXECUTOR_PHASE_STATUSES = Object.freeze([
  "start",
  "progress",
  "skipped",
  "done",
  "error",
]);

// ── Progress snapshot fields ────────────────────────────────────────────────

export const EXECUTOR_PROGRESS_STAGES = Object.freeze([
  "decide",
  "research",
  "execute",
  "review",
]);

export const EXECUTOR_PROGRESS_VALUES = Object.freeze([
  "pending",
  "active",
  "done",
]);

/**
 * All four progress stages must be present with one of the canonical values
 * for the snapshot to be considered valid.
 */
const REQUIRED_PROGRESS_STAGES = new Set(EXECUTOR_PROGRESS_STAGES);
const VALID_PROGRESS_VALUES = new Set(EXECUTOR_PROGRESS_VALUES);

// ── Normalizers ─────────────────────────────────────────────────────────────

/**
 * Normalize a raw vibecomfy.executor.phase websocket event payload.
 *
 * Accepts both the direct payload and the event detail wrapper.
 * Returns a frozen normalized object, or null if the payload is invalid.
 *
 * @param {*} raw - raw websocket event or event.detail
 * @returns {object|null} frozen normalized payload, or null
 */
export function normalizeExecutorPhasePayload(raw) {
  // Accept event.detail style or direct payload
  const payload = isObject(raw?.detail) ? raw.detail : raw;
  if (!isObject(payload)) {
    return null;
  }

  const phase = asString(payload.phase);
  if (!phase || !EXECUTOR_PHASES.includes(phase.toLowerCase())) {
    return null;
  }

  const normalized = compactObject({
    // Phase (required)
    phase: phase.toLowerCase(),

    // Status (default to "start" per the existing handler)
    status: (asString(payload.status) || "start").toLowerCase(),

    // Session identity (optional — may not be present on first event)
    session_id: asString(payload.session_id),

    // Executor identity
    executor_id: asString(payload.executor_id),

    // Timing
    emitted_at: asString(payload.emitted_at),
  });

  return Object.freeze(normalized);
}

/**
 * Extract a payload from a websocket event argument.
 *
 * @param {*} event - websocket event or plain payload
 * @returns {object|null} the raw payload object, or null
 */
export function extractExecutorPhasePayload(event) {
  if (isObject(event?.detail)) {
    return event.detail;
  }
  return isObject(event) ? event : null;
}

/**
 * Normalize an executor progress snapshot (the shape stored in panel.state.executorProgress).
 *
 * Returns a frozen object with all four stages set to canonical values,
 * or null if the input is invalid.
 *
 * @param {*} raw - raw progress snapshot
 * @returns {object|null} frozen normalized progress, or null
 */
export function normalizeExecutorProgressSnapshot(raw) {
  if (!isObject(raw)) {
    return null;
  }

  const decide = asString(raw.decide);
  const research = asString(raw.research);
  const execute = asString(raw.execute);
  const review = asString(raw.review);

  if (
    !decide || !VALID_PROGRESS_VALUES.has(decide)
    || !research || !VALID_PROGRESS_VALUES.has(research)
    || !execute || !VALID_PROGRESS_VALUES.has(execute)
    || !review || !VALID_PROGRESS_VALUES.has(review)
  ) {
    return null;
  }

  return Object.freeze({
    decide,
    research,
    execute,
    review,
  });
}

/**
 * Create an executor progress snapshot with explicit stage values.
 * Missing stages default to "pending".
 *
 * @param {object} [overrides] - partial stage values
 * @returns {object} frozen progress snapshot
 */
export function createExecutorProgressSnapshot(overrides = {}) {
  const snapshot = {
    decide: EXECUTOR_PROGRESS_VALUES.includes(overrides.decide) ? overrides.decide : "pending",
    research: EXECUTOR_PROGRESS_VALUES.includes(overrides.research) ? overrides.research : "pending",
    execute: EXECUTOR_PROGRESS_VALUES.includes(overrides.execute) ? overrides.execute : "pending",
    review: EXECUTOR_PROGRESS_VALUES.includes(overrides.review) ? overrides.review : "pending",
  };
  return Object.freeze(snapshot);
}

/**
 * Derive a progress snapshot from a normalized executor phase payload.
 * Returns a frozen progress snapshot, or null if the phase is unrecognized.
 *
 * Mirrors the logic in progressFromExecutorPhaseEvent in vibecomfy_roundtrip.js.
 */
export function progressFromExecutorPhase(normalized) {
  if (!isObject(normalized)) {
    return null;
  }
  const phase = String(normalized.phase || "").toLowerCase();
  const status = String(normalized.status || "start").toLowerCase();

  // Skipped phases
  if (status === "skipped") {
    if (phase === "research") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "pending",
        execute: "pending",
        review: "pending",
      });
    }
    if (phase === "implement") {
      return createExecutorProgressSnapshot({
        decide: "done",
        research: "done",
        execute: "pending",
        review: "pending",
      });
    }
    // classify skipped means the executor skipped classification entirely
    if (phase === "classify") {
      return createExecutorProgressSnapshot({
        decide: "pending",
        research: "pending",
        execute: "pending",
        review: "pending",
      });
    }
  }

  // Active phases
  if (phase === "classify") {
    return createExecutorProgressSnapshot({
      decide: "active",
      research: "pending",
      execute: "pending",
      review: "pending",
    });
  }
  if (phase === "research") {
    return createExecutorProgressSnapshot({
      decide: "done",
      research: "active",
      execute: "pending",
      review: "pending",
    });
  }
  if (phase === "implement") {
    return createExecutorProgressSnapshot({
      decide: "done",
      research: "done",
      execute: "active",
      review: "pending",
    });
  }
  if (phase === "reply") {
    return createExecutorProgressSnapshot({
      decide: "done",
      research: "done",
      execute: "done",
      review: "active",
    });
  }

  return null;
}

/**
 * Check whether all four progress stages are "done".
 */
export function isExecutorProgressComplete(snapshot) {
  const norm = normalizeExecutorProgressSnapshot(snapshot);
  if (!norm) {
    return false;
  }
  return norm.decide === "done"
    && norm.research === "done"
    && norm.execute === "done"
    && norm.review === "done";
}

/**
 * Derive a human-readable label for an executor progress snapshot.
 */
export function executorProgressLabel(snapshot) {
  const norm = normalizeExecutorProgressSnapshot(snapshot);
  if (!norm) {
    return "Unknown";
  }
  if (norm.decide === "active") return "Decide";
  if (norm.research === "active") return "Research";
  if (norm.execute === "active") return "Execute";
  if (norm.review === "active") return "Review";
  if (isExecutorProgressComplete(norm)) return "Complete";
  return "Pending";
}

export {
  isObject,
  asString,
  compactObject,
};
