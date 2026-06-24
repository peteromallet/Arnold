import test from "node:test";
import assert from "node:assert/strict";

import {
  PROJECTION_SURFACES,
  assertCanonicalNormalPathHasNoLegacyAliases,
  assertNormalDomTextHasNoForbiddenFieldOrValue,
  assertNormalProjectionHasNoForbiddenFieldOrValue,
  assertPublicEnvelopeHasNoPathAliases,
  assertRehydratePayloadIsProjectionInputOnly,
  isExplicitProjectionAffordance,
} from "./projection_boundary_helpers.mjs";

test("normal projection helper allows safe TranscriptMessage and ResponseDetail shapes", () => {
  const normalTranscriptMessage = {
    role: "agent",
    text: "Candidate ready for review.",
    turn_id: "turn-safe",
    session_id: "session-safe",
    local_id: "local-safe",
    source: "durable",
    pending_response: false,
    progress: { phase: "done", headline: "Ready" },
    progress_label: "Ready",
  };
  const normalResponseDetail = {
    turn: { turnId: "turn-safe", status: "done" },
    changes: [{ uid: "ksampler", fieldPath: "widgets.steps", before: 20, after: 24 }],
    candidate: { graphHash: "hash-safe", nodeCount: 2 },
    progress: { completed: 1, total: 1, headline: "Ready" },
  };

  assertNormalProjectionHasNoForbiddenFieldOrValue(normalTranscriptMessage, {
    projectionName: PROJECTION_SURFACES.NORMAL_TRANSCRIPT_MESSAGE,
  });
  assertNormalProjectionHasNoForbiddenFieldOrValue(normalResponseDetail, {
    projectionName: PROJECTION_SURFACES.NORMAL_RESPONSE_DETAIL,
  });
  assertNormalDomTextHasNoForbiddenFieldOrValue("Candidate ready for review.");
});

test("normal projection helper rejects raw diagnostic keys and values", () => {
  assert.throws(
    () => assertNormalProjectionHasNoForbiddenFieldOrValue(
      {
        text: "Looks good.",
        change_details: {
          batch_turns: [{ message: "internal step" }],
        },
      },
      { projectionName: PROJECTION_SURFACES.NORMAL_RESPONSE_DETAIL },
    ),
    /forbidden internal key .*batch_turns/,
  );

  assert.throws(
    () => assertNormalDomTextHasNoForbiddenFieldOrValue(
      "ProviderError stack trace in /real/ComfyUI/out/editor_sessions/sess/turns/0001/response.json",
    ),
    /forbidden diagnostic value/,
  );
});

test("explicit audit debug and diagnostic affordance names are separate from normal projections", () => {
  assert.equal(isExplicitProjectionAffordance(PROJECTION_SURFACES.EXPLICIT_AUDIT_ARTIFACT), true);
  assert.equal(isExplicitProjectionAffordance(PROJECTION_SURFACES.EXPLICIT_DEBUG_PAYLOAD), true);
  assert.equal(isExplicitProjectionAffordance(PROJECTION_SURFACES.EXPLICIT_DIAGNOSTIC_EVENT), true);
  assert.equal(isExplicitProjectionAffordance(PROJECTION_SURFACES.NORMAL_RESPONSE_DETAIL), false);

  assert.throws(
    () => assertNormalProjectionHasNoForbiddenFieldOrValue(
      { audit_ref: { path: "out/audits/turn.json" } },
      { projectionName: PROJECTION_SURFACES.EXPLICIT_AUDIT_ARTIFACT },
    ),
    /explicit affordance/,
  );
});

test("rehydrate payload helper treats raw payloads as projection input only", () => {
  const rehydrateProjectionInput = {
    messages: [
      {
        role: "agent",
        text: "Candidate ready.",
        raw_payload: { provider_payload: { model: "internal" } },
        audit_ref: { path: "out/audits/turn.json" },
        change_details: {
          batch_turns: [
            {
              message: "internal reasoning",
              diagnostics: [{ code: "ENGINE_DIAG", message: "raw diagnostic" }],
            },
          ],
        },
      },
    ],
  };
  const projected = {
    normalTranscriptMessage: {
      role: "agent",
      text: "Candidate ready.",
      turn_id: "turn-1",
      session_id: "session-1",
    },
    normalResponseDetail: {
      turn: { turnId: "turn-1" },
      changes: [],
      progress: { headline: "Ready" },
    },
    explicitDiagnosticEvent: {
      rawPayload: rehydrateProjectionInput.messages[0].raw_payload,
      batchTurns: rehydrateProjectionInput.messages[0].change_details.batch_turns,
    },
  };

  assertRehydratePayloadIsProjectionInputOnly(rehydrateProjectionInput, projected);
  assert.throws(
    () => assertRehydratePayloadIsProjectionInputOnly(
      rehydrateProjectionInput,
      {
        normalTranscriptMessage: {
          ...projected.normalTranscriptMessage,
          raw_payload: rehydrateProjectionInput.messages[0].raw_payload,
        },
      },
    ),
    /forbidden internal key .*raw_payload/,
  );
});

test("public envelope helper rejects old path aliases in snake_case and camelCase", () => {
  assertPublicEnvelopeHasNoPathAliases({
    ok: true,
    session_id: "sess-public",
    latest_candidate: {
      candidate_graph_hash: "hash-safe",
      audit_artifacts: [{ sha256: "abc123", preview: "safe" }],
    },
    diagnostics: [{ source: "messages.change_details", message: "safe" }],
  });

  for (const [key, value] of [
    ["session_path", "out/editor_sessions/sess-public"],
    ["sessionPath", "out/editor_sessions/sess-public"],
    ["detail_json_path", "out/editor_sessions/sess-public/session.json"],
    ["detailJsonPath", "out/editor_sessions/sess-public/session.json"],
    ["audit_path", "turns/0001/audit.json"],
    ["auditPath", "turns/0001/audit.json"],
    ["baseline_graph_source_path", "turns/0000/response.json"],
    ["baselineGraphSourcePath", "turns/0000/response.json"],
  ]) {
    assert.throws(
      () => assertPublicEnvelopeHasNoPathAliases({ ok: true, [key]: value }),
      /public envelope path alias/,
      `expected ${key} to be rejected`,
    );
  }
});

test("legacy alias helper remains available for canonical payload fixtures", () => {
  assertCanonicalNormalPathHasNoLegacyAliases({
    ok: true,
    change_details: {
      batch_turns: [
        { field_changes: [{ uid: "ksampler", field_path: "widgets.steps" }] },
      ],
    },
  });

  assert.throws(
    () => assertCanonicalNormalPathHasNoLegacyAliases({ applyAllowed: true }),
    /legacy alias/,
  );
});
