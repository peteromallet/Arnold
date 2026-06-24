import test from "node:test";
import assert from "node:assert/strict";

import * as candidateActions from "../../vibecomfy/comfy_nodes/web/agent_candidate_actions.js";

const {
  APPLY_ELIGIBILITY_REASON,
  applyEligibility,
  disabledApplyEligibility,
  normalizeApplyEligibility,
  candidateGraphPresentForBubble,
  candidateActionState,
} = candidateActions;

test("agent_candidate_actions exposes the candidate action owner API", () => {
  assert.deepEqual(Object.keys(candidateActions).sort(), [
    "APPLY_ELIGIBILITY_REASON",
    "applyEligibility",
    "candidateActionState",
    "candidateGraphPresentForBubble",
    "disabledApplyEligibility",
    "normalizeApplyEligibility",
  ].sort());
});

test("applyEligibility preserves canonical active eligibility behavior", () => {
  const panel = {
    state: {
      candidateGraph: { nodes: [] },
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Ready.",
        warnings: ["copied"],
      },
      applyEligibilityWarning: { stale: true },
      applyEligibilityWarningKey: "stale",
    },
  };

  const eligibility = applyEligibility(panel);

  assert.deepEqual(eligibility, {
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready.",
    warnings: ["copied"],
  });
  assert.equal(panel.state.applyEligibilityWarning, null);
  assert.equal(panel.state.applyEligibilityWarningKey, null);
  assert.notEqual(eligibility.warnings, panel.state.applyEligibility.warnings);
});

test("candidateActionState keeps active and historical candidate semantics", () => {
  const panel = {
    state: {
      phase: "AWAITING_REVIEW",
      candidateGraph: { nodes: [] },
      turnId: "0002",
      applyEligibility: {
        applyable: true,
        reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
        message: "Ready.",
        warnings: [],
      },
    },
  };

  assert.deepEqual(candidateActionState(panel), {
    visible: true,
    active: true,
    turnId: "0002",
    eligibility: {
      applyable: true,
      reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
      message: "Ready.",
      warnings: [],
    },
    blockerMessage: "",
    applyDisabled: false,
    rejectDisabled: false,
  });

  assert.deepEqual(
    candidateActionState(
      panel,
      { turn_id: "0001", candidateGraph: { nodes: [] } },
      {
        applyEligibility: {
          applyable: false,
          reason: APPLY_ELIGIBILITY_REASON.SUPERSEDED,
          message: "Already replaced.",
          warnings: ["superseded"],
        },
      },
    ).eligibility,
    {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.SUPERSEDED,
      message: "Already replaced.",
      warnings: ["superseded"],
    },
  );

  const staleHistorical = candidateActionState(panel, { turn_id: "0001", candidateGraph: { nodes: [] } });
  assert.equal(staleHistorical.active, false);
  assert.equal(staleHistorical.eligibility.reason, APPLY_ELIGIBILITY_REASON.NOT_LATEST);
  assert.equal(staleHistorical.applyDisabled, true);
  assert.equal(staleHistorical.rejectDisabled, true);
});

test("disabledApplyEligibility and no-candidate action states remain immutable payload builders", () => {
  const warnings = ["server_blocked"];
  const disabled = disabledApplyEligibility(
    APPLY_ELIGIBILITY_REASON.SERVER_BLOCKED,
    "Blocked.",
    warnings,
  );
  warnings.push("mutated");

  assert.deepEqual(disabled, {
    applyable: false,
    reason: APPLY_ELIGIBILITY_REASON.SERVER_BLOCKED,
    message: "Blocked.",
    warnings: ["server_blocked"],
  });

  assert.deepEqual(candidateActionState({ state: { phase: "IDLE" } }), {
    visible: false,
    active: false,
    turnId: null,
    eligibility: {
      applyable: false,
      reason: APPLY_ELIGIBILITY_REASON.NO_CANDIDATE,
      message: "No candidate is available to apply.",
      warnings: [],
    },
    applyDisabled: true,
    rejectDisabled: true,
  });
});

test("exported helper APIs preserve normalization and bubble candidate detection", () => {
  const warnings = ["copied"];
  const normalized = normalizeApplyEligibility({
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready.",
    warnings,
  });
  warnings.push("mutated");

  assert.deepEqual(normalized, {
    applyable: true,
    reason: APPLY_ELIGIBILITY_REASON.APPLYABLE,
    message: "Ready.",
    warnings: ["copied"],
  });
  assert.equal(normalizeApplyEligibility({ reason: "unknown" }), null);
  assert.equal(candidateGraphPresentForBubble({ candidateGraph: { nodes: [] } }), true);
  assert.equal(candidateGraphPresentForBubble({}, { candidateGraphPresent: false }), false);
});
