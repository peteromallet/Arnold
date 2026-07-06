import test from "node:test";
import assert from "node:assert/strict";

import {
  RENDER_SECTIONS,
  normalizeObligationDirtySections,
} from "../../vibecomfy/comfy_nodes/web/agent_edit_lifecycle.js";

import {
  SETTINGS_STATUS_RENDER_SECTIONS,
  normalizeDirtySectionList,
  markAgentPanelDirty,
  markAgentPanelDirtyAfterCommit,
  consumeAgentPanelDirtySections,
  scheduleRenderAgentPanel,
} from "../../vibecomfy/comfy_nodes/web/panel_scheduler.js";

// ── Helpers ─────────────────────────────────────────────────────────────────

const ALL_RENDER_SECTIONS = Object.freeze(Object.values(RENDER_SECTIONS));

function makePanel(overrides = {}) {
  return {
    root: overrides.root !== undefined ? overrides.root : null,
    state: overrides.state !== undefined ? overrides.state : {},
    pendingDirtySections: Array.isArray(overrides.pendingDirtySections)
      ? overrides.pendingDirtySections
      : [],
    ...overrides,
  };
}

// ── RENDER_SECTIONS.CANDIDATE absence ──────────────────────────────────────

test("RENDER_SECTIONS.CANDIDATE is undefined", () => {
  assert.equal(
    RENDER_SECTIONS.CANDIDATE,
    undefined,
    "RENDER_SECTIONS.CANDIDATE must be undefined",
  );
});

test("Object.keys(RENDER_SECTIONS) does not contain CANDIDATE", () => {
  assert.equal(
    Object.keys(RENDER_SECTIONS).includes("CANDIDATE"),
    false,
    "RENDER_SECTIONS key set must not include CANDIDATE",
  );
});

test("Object.values(RENDER_SECTIONS) does not contain CANDIDATE string", () => {
  assert.equal(
    Object.values(RENDER_SECTIONS).includes("CANDIDATE"),
    false,
    "RENDER_SECTIONS values must not include the string 'CANDIDATE'",
  );
});

test("ALL_RENDER_SECTIONS (derived from RENDER_SECTIONS values) does not contain CANDIDATE", () => {
  assert.equal(
    ALL_RENDER_SECTIONS.includes("CANDIDATE"),
    false,
    "ALL_RENDER_SECTIONS must not include 'CANDIDATE'",
  );
});

// ── SETTINGS_STATUS_RENDER_SECTIONS does not include CANDIDATE ──────────────

test("SETTINGS_STATUS_RENDER_SECTIONS does not contain CANDIDATE", () => {
  assert.equal(
    SETTINGS_STATUS_RENDER_SECTIONS.includes("CANDIDATE"),
    false,
    "SETTINGS_STATUS_RENDER_SECTIONS must not contain CANDIDATE",
  );
});

test("SETTINGS_STATUS_RENDER_SECTIONS only contains known valid sections", () => {
  for (const section of SETTINGS_STATUS_RENDER_SECTIONS) {
    assert.ok(
      ALL_RENDER_SECTIONS.includes(section),
      `SETTINGS_STATUS_RENDER_SECTIONS entry "${section}" must be a valid RENDER_SECTIONS value`,
    );
  }
});

// ── normalizeObligationDirtySections rejects CANDIDATE ─────────────────────

test("normalizeObligationDirtySections throws for CANDIDATE string", () => {
  assert.throws(
    () => normalizeObligationDirtySections({
      render: false,
      dirtySections: ["CANDIDATE"],
    }),
    /Unknown render section.*CANDIDATE/,
    "normalizeObligationDirtySections must throw for CANDIDATE",
  );
});

test("normalizeObligationDirtySections throws for CANDIDATE mixed with valid sections", () => {
  assert.throws(
    () => normalizeObligationDirtySections({
      render: false,
      dirtySections: ["THREAD", "CANDIDATE", "META"],
    }),
    /Unknown render section.*CANDIDATE/,
    "CANDIDATE must be rejected even when mixed with valid sections",
  );
});

test("normalizeObligationDirtySections throws for any unknown section", () => {
  assert.throws(
    () => normalizeObligationDirtySections({
      render: false,
      dirtySections: ["UNKNOWN_SECTION"],
    }),
    /Unknown render section/,
    "Unknown sections must be rejected",
  );
});

test("normalizeObligationDirtySections passes valid sections through", () => {
  const result = normalizeObligationDirtySections({
    render: true,
    dirtySections: ["THREAD", "META"],
  });
  assert.deepEqual(result.dirtySections, ["THREAD", "META"]);
});

test("normalizeObligationDirtySections de-duplicates valid sections", () => {
  const result = normalizeObligationDirtySections({
    render: true,
    dirtySections: ["THREAD", "THREAD", "META"],
  });
  assert.deepEqual(result.dirtySections, ["THREAD", "META"]);
});

// ── normalizeDirtySectionList rejects CANDIDATE ────────────────────────────

test("normalizeDirtySectionList throws for CANDIDATE string", () => {
  assert.throws(
    () => normalizeDirtySectionList(["CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "normalizeDirtySectionList must throw for CANDIDATE",
  );
});

test("normalizeDirtySectionList throws for CANDIDATE mixed with valid sections", () => {
  assert.throws(
    () => normalizeDirtySectionList(["THREAD", "CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "CANDIDATE must be rejected by normalizeDirtySectionList",
  );
});

test("normalizeDirtySectionList returns undefined for undefined input", () => {
  assert.equal(
    normalizeDirtySectionList(undefined),
    undefined,
    "normalizeDirtySectionList(undefined) must return undefined",
  );
});

test("normalizeDirtySectionList returns [] for null input", () => {
  assert.deepEqual(
    normalizeDirtySectionList(null),
    [],
    "normalizeDirtySectionList(null) must return []",
  );
});

test("normalizeDirtySectionList returns normalized valid sections", () => {
  const result = normalizeDirtySectionList(["META", "THREAD", "META"]);
  assert.deepEqual(result, ["META", "THREAD"]);
});

// ── markAgentPanelDirty rejects CANDIDATE ──────────────────────────────────

test("markAgentPanelDirty throws for CANDIDATE in sections (even with disconnected panel)", () => {
  const panel = makePanel();
  assert.throws(
    () => markAgentPanelDirty(panel, ["CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "markAgentPanelDirty must throw for CANDIDATE before any scheduling",
  );
});

test("markAgentPanelDirty throws for any unknown section", () => {
  const panel = makePanel();
  assert.throws(
    () => markAgentPanelDirty(panel, ["NONEXISTENT"]),
    /Unknown render section/,
    "markAgentPanelDirty must reject unknown sections",
  );
});

test("markAgentPanelDirty accepts valid sections for disconnected panel", () => {
  const panel = makePanel();
  // Should not throw — valid sections pass normalization
  const pending = markAgentPanelDirty(panel, ["THREAD"]);
  assert.deepEqual(pending, ["THREAD"]);
});

test("markAgentPanelDirty returns existing pending when passed empty sections", () => {
  const panel = makePanel({ pendingDirtySections: ["META"] });
  const pending = markAgentPanelDirty(panel, []);
  assert.deepEqual(pending, ["META"]);
});

test("markAgentPanelDirty returns [] for null panel", () => {
  const result = markAgentPanelDirty(null, ["THREAD"]);
  assert.deepEqual(result, []);
});

// ── markAgentPanelDirtyAfterCommit rejects CANDIDATE ───────────────────────

test("markAgentPanelDirtyAfterCommit throws for CANDIDATE in sections", () => {
  const panel = makePanel();
  assert.throws(
    () => markAgentPanelDirtyAfterCommit(panel, ["CANDIDATE"], "status"),
    /Unknown render section.*CANDIDATE/,
    "markAgentPanelDirtyAfterCommit must throw for CANDIDATE",
  );
});

test("markAgentPanelDirtyAfterCommit throws for CANDIDATE before any scheduling", () => {
  const panel = makePanel();
  assert.throws(
    () => markAgentPanelDirtyAfterCommit(panel, ["CANDIDATE"], "rehydrate"),
    /Unknown render section.*CANDIDATE/,
    "markAgentPanelDirtyAfterCommit must reject CANDIDATE before scheduling",
  );
});

test("markAgentPanelDirtyAfterCommit returns [] for null panel", () => {
  const result = markAgentPanelDirtyAfterCommit(null, ["THREAD"], "status");
  assert.deepEqual(result, []);
});

// ── consumeAgentPanelDirtySections rejects CANDIDATE ───────────────────────

test("consumeAgentPanelDirtySections throws for CANDIDATE in fallbackSections", () => {
  const panel = makePanel();
  assert.throws(
    () => consumeAgentPanelDirtySections(panel, ["CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "consumeAgentPanelDirtySections must throw for CANDIDATE in fallback",
  );
});

test("consumeAgentPanelDirtySections throws for unknown section in fallback", () => {
  const panel = makePanel();
  assert.throws(
    () => consumeAgentPanelDirtySections(panel, ["UNKNOWN"]),
    /Unknown render section/,
    "consumeAgentPanelDirtySections must reject unknown fallback sections",
  );
});

test("consumeAgentPanelDirtySections returns [] for null panel", () => {
  const result = consumeAgentPanelDirtySections(null);
  assert.deepEqual(result, []);
});

// ── scheduleRenderAgentPanel rejects CANDIDATE BEFORE disconnected-root check ─

test("scheduleRenderAgentPanel throws for CANDIDATE even when panel root is disconnected", () => {
  // This is the critical ordering test: validation MUST happen before
  // the disconnected-root early return so that invalid sections are
  // never silently swallowed.
  const panel = makePanel({ root: null }); // disconnected (no root)
  assert.throws(
    () => scheduleRenderAgentPanel("test", panel, ["CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "scheduleRenderAgentPanel must reject CANDIDATE before checking root connectivity",
  );
});

test("scheduleRenderAgentPanel throws for CANDIDATE with undefined-like panel", () => {
  // Even if the panel would fail connectivity, validation comes first
  const panel = makePanel({ root: undefined });
  assert.throws(
    () => scheduleRenderAgentPanel("test", panel, ["CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "scheduleRenderAgentPanel must validate sections before connectivity check",
  );
});

test("scheduleRenderAgentPanel throws for CANDIDATE with root.isConnected = false", () => {
  const panel = makePanel({ root: { isConnected: false } });
  assert.throws(
    () => scheduleRenderAgentPanel("test", panel, ["CANDIDATE"]),
    /Unknown render section.*CANDIDATE/,
    "scheduleRenderAgentPanel must reject CANDIDATE even when root.isConnected is explicitly false",
  );
});

test("scheduleRenderAgentPanel throws for unknown section before connectivity check", () => {
  const panel = makePanel({ root: null });
  assert.throws(
    () => scheduleRenderAgentPanel("test", panel, ["NONEXISTENT"]),
    /Unknown render section/,
    "Any unknown section must be rejected before connectivity check",
  );
});

test("scheduleRenderAgentPanel silently returns for disconnected panel with valid sections", () => {
  // With valid sections and no root, should silently return (no throw)
  const panel = makePanel({ root: null });
  assert.doesNotThrow(
    () => scheduleRenderAgentPanel("test", panel, ["THREAD"]),
    "Valid sections with disconnected panel must not throw",
  );
  // Verify nothing was scheduled
  assert.deepEqual(panel.pendingDirtySections || [], []);
});

test("scheduleRenderAgentPanel silently returns for disconnected panel with undefined fallbackSections", () => {
  const panel = makePanel({ root: null });
  assert.doesNotThrow(
    () => scheduleRenderAgentPanel("test", panel),
    "Undefined fallbackSections with disconnected panel must not throw",
  );
});

// ── CANDIDATE cannot enter any scheduler API path ──────────────────────────

test("CANDIDATE string cannot pass through markAgentPanelDirty", () => {
  const panel = makePanel();
  assert.throws(
    () => markAgentPanelDirty(panel, ["CANDIDATE"]),
    /Unknown render section/,
  );
});

test("CANDIDATE string cannot pass through markAgentPanelDirtyAfterCommit", () => {
  const panel = makePanel();
  assert.throws(
    () => markAgentPanelDirtyAfterCommit(panel, ["CANDIDATE"], "status"),
    /Unknown render section/,
  );
});

test("CANDIDATE string cannot pass through consumeAgentPanelDirtySections", () => {
  const panel = makePanel();
  assert.throws(
    () => consumeAgentPanelDirtySections(panel, ["CANDIDATE"]),
    /Unknown render section/,
  );
});

test("CANDIDATE string cannot pass through scheduleRenderAgentPanel", () => {
  const panel = makePanel({ root: null });
  assert.throws(
    () => scheduleRenderAgentPanel("test", panel, ["CANDIDATE"]),
    /Unknown render section/,
  );
});

test("CANDIDATE string cannot pass through normalizeDirtySectionList", () => {
  assert.throws(
    () => normalizeDirtySectionList(["CANDIDATE"]),
    /Unknown render section/,
  );
});

test("CANDIDATE string cannot pass through normalizeObligationDirtySections", () => {
  assert.throws(
    () => normalizeObligationDirtySections({
      render: false,
      dirtySections: ["CANDIDATE"],
    }),
    /Unknown render section/,
  );
});

// ── Edge cases: non-string and malformed inputs ────────────────────────────

test("normalizeObligationDirtySections throws for non-string section entries", () => {
  assert.throws(
    () => normalizeObligationDirtySections({
      render: false,
      dirtySections: [42],
    }),
    /must be a string/,
  );
});

test("normalizeObligationDirtySections returns input unchanged when dirtySections is undefined", () => {
  const input = { render: true };
  const result = normalizeObligationDirtySections(input);
  assert.equal(result, input); // Same reference when no normalization needed
});

test("normalizeObligationDirtySections returns input unchanged for non-object", () => {
  assert.equal(normalizeObligationDirtySections(null), null);
  assert.equal(normalizeObligationDirtySections("string"), "string");
  assert.equal(normalizeObligationDirtySections(42), 42);
});

test("normalizeDirtySectionList handles edge-case empty array with null panel", () => {
  // normalizeDirtySectionList([]) returns [] (via normalizeObligationDirtySections)
  const result = normalizeDirtySectionList([]);
  assert.deepEqual(result, []);
});

// ── Coverage: ALL_RENDER_SECTIONS symmetry ─────────────────────────────────

test("Every valid RENDER_SECTIONS value can pass through normalizeDirtySectionList", () => {
  // Prove that every known section passes normalization (no false rejects)
  for (const section of ALL_RENDER_SECTIONS) {
    const result = normalizeDirtySectionList([section]);
    assert.deepEqual(
      result,
      [section],
      `Valid section "${section}" must pass through normalizeDirtySectionList`,
    );
  }
});

test("Every valid RENDER_SECTIONS value can pass through markAgentPanelDirty", () => {
  for (const section of ALL_RENDER_SECTIONS) {
    const panel = makePanel();
    const pending = markAgentPanelDirty(panel, [section]);
    assert.ok(
      pending.includes(section),
      `Valid section "${section}" must be accepted by markAgentPanelDirty`,
    );
  }
});
