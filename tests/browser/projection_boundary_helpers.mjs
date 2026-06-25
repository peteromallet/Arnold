import assert from "node:assert/strict";

// Naming convention for M1 boundary tests:
// - normalTranscriptMessage / normalResponseDetail / normalDomText are renderer-safe projections.
// - explicitAuditArtifact / explicitDebugPayload / explicitDiagnosticEvent are opt-in affordances.
// Raw rehydrate payloads may contain diagnostic fields only while they are projection input; they
// must be split before normal renderer state or normal DOM assertions use them.

export const PROJECTION_SURFACES = Object.freeze({
  NORMAL_TRANSCRIPT_MESSAGE: "normalTranscriptMessage",
  NORMAL_RESPONSE_DETAIL: "normalResponseDetail",
  NORMAL_DOM_TEXT: "normalDomText",
  REHYDRATE_PROJECTION_INPUT: "rehydrateProjectionInput",
  EXPLICIT_AUDIT_ARTIFACT: "explicitAuditArtifact",
  EXPLICIT_DEBUG_PAYLOAD: "explicitDebugPayload",
  EXPLICIT_DIAGNOSTIC_EVENT: "explicitDiagnosticEvent",
});

export const EXPLICIT_AFFORDANCE_SURFACES = Object.freeze(new Set([
  PROJECTION_SURFACES.REHYDRATE_PROJECTION_INPUT,
  PROJECTION_SURFACES.EXPLICIT_AUDIT_ARTIFACT,
  PROJECTION_SURFACES.EXPLICIT_DEBUG_PAYLOAD,
  PROJECTION_SURFACES.EXPLICIT_DIAGNOSTIC_EVENT,
]));

export const FORBIDDEN_NORMAL_LEGACY_ALIAS_KEYS = Object.freeze(new Set([
  "executor_pending",
  "apply_allowed",
  "canvas_apply_allowed",
  "applyAllowed",
  "canvasApplyAllowed",
  "queue_allowed",
  "queueAllowed",
]));

export const FORBIDDEN_NORMAL_PROJECTION_KEYS = Object.freeze(new Set([
  ...FORBIDDEN_NORMAL_LEGACY_ALIAS_KEYS,
  "batch_turns",
  "batchTurns",
  "raw_payload",
  "rawPayload",
  "raw",
  "debug",
  "debug_payload",
  "debugPayload",
  "audit_ref",
  "auditRef",
  "audit_path",
  "auditPath",
  "provider_payload",
  "providerPayload",
  "provider_diagnostics",
  "providerDiagnostics",
  "budget",
  "budgets",
  "token_budget",
  "tokenBudget",
  "remaining_batches",
  "remainingBatches",
  "exit_mode",
  "exitMode",
  "raw_path",
  "rawPath",
  "artifact_path",
  "artifactPath",
  "session_path",
  "sessionPath",
  "session_path_resolved",
  "sessionPathResolved",
  "detail_path",
  "detailPath",
  "detail_json_path",
  "detailJsonPath",
  "turn_path",
  "turnPath",
  "request_path",
  "requestPath",
  "request_json_path",
  "requestJsonPath",
  "response_path",
  "responsePath",
  "response_json_path",
  "responseJsonPath",
  "chat_path",
  "chatPath",
  "chat_json_path",
  "chatJsonPath",
  "model_prompt",
  "modelPrompt",
  "system_prompt",
  "systemPrompt",
  "prompt_messages",
  "promptMessages",
]));

export const FORBIDDEN_PUBLIC_ENVELOPE_PATH_KEYS = Object.freeze(new Set([
  "path",
  "raw_path",
  "rawPath",
  "artifact_path",
  "artifactPath",
  "audit_path",
  "auditPath",
  "request_path",
  "requestPath",
  "response_path",
  "responsePath",
  "chat_path",
  "chatPath",
  "candidate_path",
  "candidatePath",
  "debug_path",
  "debugPath",
  "session_path",
  "sessionPath",
  "session_path_resolved",
  "sessionPathResolved",
  "detail_path",
  "detailPath",
  "detail_json_path",
  "detailJsonPath",
  "detail_json_path_resolved",
  "detailJsonPathResolved",
  "baseline_graph_source_path",
  "baselineGraphSourcePath",
  "model_request_path",
  "modelRequestPath",
  "model_response_path",
  "modelResponsePath",
]));

export const FORBIDDEN_NORMAL_PROJECTION_VALUE_PATTERNS = Object.freeze([
  /\/(?:real\/)?ComfyUI\/out\/editor_sessions\//i,
  /\bturns\/\d+\/(?:response|messages|candidate|debug)\.[a-z0-9]+/i,
  /\b(?:ProviderError|Traceback|stack trace|engine diagnostics|raw diagnostic)\b/i,
  /\b(?:model prompt|system prompt|prompt messages)\b/i,
  /\b(?:token budget|exit mode|remaining batches)\b/i,
]);

export function isExplicitProjectionAffordance(surface) {
  return EXPLICIT_AFFORDANCE_SURFACES.has(surface);
}

export function assertCanonicalNormalPathHasNoLegacyAliases(value, path = "$") {
  if (!value || typeof value !== "object") {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      assertCanonicalNormalPathHasNoLegacyAliases(entry, `${path}[${index}]`);
    });
    return;
  }

  for (const [key, entry] of Object.entries(value)) {
    const keyPath = `${path}.${key}`;
    assert.equal(
      FORBIDDEN_NORMAL_LEGACY_ALIAS_KEYS.has(key),
      false,
      `canonical normal-path payload must not carry legacy alias ${keyPath}`,
    );
    assert.equal(
      key === "field_changes" && !/\.change_details\.batch_turns\[\d+\]\.field_changes$/.test(keyPath),
      false,
      `canonical normal-path payload must not carry old field-change dictionary ${keyPath}`,
    );
    assertCanonicalNormalPathHasNoLegacyAliases(entry, keyPath);
  }
}

export function assertNormalProjectionHasNoForbiddenFieldOrValue(
  value,
  {
    projectionName = PROJECTION_SURFACES.NORMAL_RESPONSE_DETAIL,
    path = "$",
  } = {},
) {
  assert.equal(
    isExplicitProjectionAffordance(projectionName),
    false,
    `${projectionName} is an explicit affordance; use an explicit audit/debug/diagnostic assertion instead`,
  );
  assertNoForbiddenNormalProjectionContent(value, path, projectionName);
}

export function assertNormalDomTextHasNoForbiddenFieldOrValue(
  text,
  {
    projectionName = PROJECTION_SURFACES.NORMAL_DOM_TEXT,
    path = "$",
  } = {},
) {
  assertNormalProjectionHasNoForbiddenFieldOrValue(String(text ?? ""), {
    projectionName,
    path,
  });
}

export function assertRehydratePayloadIsProjectionInputOnly(
  rawRehydratePayload,
  projected,
  {
    rawName = PROJECTION_SURFACES.REHYDRATE_PROJECTION_INPUT,
    normalTranscriptName = PROJECTION_SURFACES.NORMAL_TRANSCRIPT_MESSAGE,
    normalDetailName = PROJECTION_SURFACES.NORMAL_RESPONSE_DETAIL,
  } = {},
) {
  assert.equal(
    isExplicitProjectionAffordance(rawName),
    true,
    "raw rehydrate fixtures must be named as projection input, not normal renderer state",
  );
  assert.ok(rawRehydratePayload && typeof rawRehydratePayload === "object");
  if (projected?.normalTranscriptMessage !== undefined) {
    assertNormalProjectionHasNoForbiddenFieldOrValue(projected.normalTranscriptMessage, {
      projectionName: normalTranscriptName,
      path: "$.normalTranscriptMessage",
    });
  }
  if (projected?.normalResponseDetail !== undefined) {
    assertNormalProjectionHasNoForbiddenFieldOrValue(projected.normalResponseDetail, {
      projectionName: normalDetailName,
      path: "$.normalResponseDetail",
    });
  }
}

export function assertPublicEnvelopeHasNoPathAliases(
  value,
  {
    projectionName = PROJECTION_SURFACES.REHYDRATE_PROJECTION_INPUT,
    path = "$",
  } = {},
) {
  assertNoForbiddenPublicEnvelopePathAliases(value, path, projectionName);
}

function assertNoForbiddenPublicEnvelopePathAliases(value, path, projectionName) {
  if (!value || typeof value !== "object") {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      assertNoForbiddenPublicEnvelopePathAliases(entry, `${path}[${index}]`, projectionName);
    });
    return;
  }

  for (const [key, entry] of Object.entries(value)) {
    const keyPath = `${path}.${key}`;
    assert.equal(
      FORBIDDEN_PUBLIC_ENVELOPE_PATH_KEYS.has(key),
      false,
      `${projectionName} must not expose public envelope path alias ${keyPath}`,
    );
    assertNoForbiddenPublicEnvelopePathAliases(entry, keyPath, projectionName);
  }
}

function assertNoForbiddenNormalProjectionContent(value, path, projectionName) {
  if (typeof value === "string") {
    for (const pattern of FORBIDDEN_NORMAL_PROJECTION_VALUE_PATTERNS) {
      assert.equal(
        pattern.test(value),
        false,
        `${projectionName} must not expose forbidden diagnostic value at ${path}: ${value}`,
      );
    }
    return;
  }
  if (!value || typeof value !== "object") {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => {
      assertNoForbiddenNormalProjectionContent(entry, `${path}[${index}]`, projectionName);
    });
    return;
  }

  for (const [key, entry] of Object.entries(value)) {
    const keyPath = `${path}.${key}`;
    assert.equal(
      FORBIDDEN_NORMAL_PROJECTION_KEYS.has(key),
      false,
      `${projectionName} must not expose forbidden internal key ${keyPath}`,
    );
    assertNoForbiddenNormalProjectionContent(entry, keyPath, projectionName);
  }
}
