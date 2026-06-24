import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import * as candidateActions from "../../vibecomfy/comfy_nodes/web/agent_candidate_actions.js";
import * as panelComposer from "../../vibecomfy/comfy_nodes/web/panel_composer.js";
import * as statusPoller from "../../vibecomfy/comfy_nodes/web/agent_status_poller.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

const roundtripSource = source("vibecomfy_roundtrip.js");

function assertNoOwnerDefinition(name) {
  const definitionPattern = new RegExp(
    String.raw`(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+${name}\s*\(|(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+${name}\b`,
  );
  assert.equal(
    definitionPattern.test(roundtripSource),
    false,
    `vibecomfy_roundtrip.js must not define owner implementation ${name}`,
  );
}

function functionBody(name) {
  const match = roundtripSource.match(
    new RegExp(String.raw`(?:async\s+)?function\s+${name}\s*\([^)]*\)\s*\{([\s\S]*?)\n\}`),
  );
  assert.ok(match, `expected wrapper function ${name} in vibecomfy_roundtrip.js`);
  return match[1];
}

function assertDelegatingWrapper(name, ownerPattern) {
  const body = functionBody(name);
  assert.match(body, ownerPattern, `${name} must delegate to canonical owner`);
  assert.doesNotMatch(body, /\bfetch\s*\(/, `${name} must not issue requests locally`);
  assert.doesNotMatch(body, /\blocalStorage\b/, `${name} must not access storage locally`);
  assert.doesNotMatch(body, /\/vibecomfy\/agent\//, `${name} must not own endpoint strings`);
  assert.doesNotMatch(body, /\broute_options\b/, `${name} must not inspect status payloads locally`);
}

test("vibecomfy_roundtrip keeps status and settings/provider-test ownership delegated", () => {
  for (const name of [
    "ROUTE_STATUS_KIND",
    "AGENT_STATUS_RETRY_DELAYS_MS",
    "ROUTE_ALIASES",
    "ROUTE_LABELS",
    "CANONICAL_AGENT_PROVIDERS",
    "_lsGet",
    "_lsSet",
    "_lsRemove",
    "getPersistedAgentProvider",
    "setPersistedAgentProvider",
    "persistAgentSettings",
    "storeOpenRouterCredential",
  ]) {
    assertNoOwnerDefinition(name);
  }

  assertDelegatingWrapper("buildStatusUrl", /buildStatusUrlImpl\(/);
  assertDelegatingWrapper("clearAgentStatusRetry", /clearAgentStatusRetryImpl\(/);
  assertDelegatingWrapper("scheduleAgentStatusRetry", /pollerScheduleAgentStatusRetry\(/);
  assertDelegatingWrapper("populateRouteSelect", /pollerPopulateRouteSelect\(/);
  assertDelegatingWrapper("refreshAgentStatus", /pollerRefreshAgentStatus\(/);
  assertDelegatingWrapper("syncChooseEngineGate", /pollerSyncChooseEngineGate\(/);
  assertDelegatingWrapper("testAgentSettings", /testAgentSettingsImpl\(/);

  assert.match(roundtripSource, /persistAgentSettings\(panel,\s*\{\s*includeCredential\s*\},\s*agentStatusDeps\(\)\)/);
  assert.match(roundtripSource, /testAgentSettingsImpl\(panel,\s*agentStatusDeps\(\)\)/);
  assert.doesNotMatch(roundtripSource, /fetch\(\s*["'`]\/vibecomfy\/agent\/settings/);
  assert.doesNotMatch(roundtripSource, /fetch\(\s*["'`]\/vibecomfy\/agent\/test/);
  assert.doesNotMatch(roundtripSource, /fetch\(\s*["'`]\/vibecomfy\/agent\/credential/);
});

test("vibecomfy_roundtrip keeps composer and candidate selector ownership delegated", () => {
  for (const name of [
    "renderDeveloperSubsection",
    "normalizeApplyEligibility",
    "ensureMissingEligibilityWarning",
    "missingContractApplyEligibility",
    "noCandidateApplyEligibility",
    "applyEligibility",
    "disabledApplyEligibility",
    "candidateActionState",
    "candidateTurnId",
    "candidateGraphPresentForBubble",
    "snapshotEligibilityForBubble",
  ]) {
    assertNoOwnerDefinition(name);
  }

  assert.match(roundtripSource, /renderDeveloperImpl\(panel,\s*buildPanelComposerRenderDeps\(\)\)/);
  assert.match(roundtripSource, /renderDeveloperDisclosureImpl\(panel,\s*buildPanelComposerRenderDeps\(\)\)/);
  assert.match(roundtripSource, /renderSettingsImpl\(panel,\s*buildPanelComposerRenderDeps\(\)\)/);
  assert.match(roundtripSource, /from\s+["']\.\/agent_candidate_actions\.js["']/);

  for (const name of ["renderDeveloper", "renderDeveloperDisclosure", "renderSettings"]) {
    const body = functionBody(name);
    assert.doesNotMatch(body, /\bel\s*\(/, `${name} must not construct DOM locally`);
    assert.doesNotMatch(body, /\.appendChild\b/, `${name} must not render DOM locally`);
    assert.doesNotMatch(body, /\.textContent\s*=/, `${name} must not render copy locally`);
  }
});

test("canonical frontend owners expose the expected public APIs", () => {
  for (const name of [
    "AGENT_STATUS_RETRY_DELAYS_MS",
    "ROUTE_ALIASES",
    "ROUTE_LABELS",
    "CANONICAL_AGENT_PROVIDERS",
    "buildStatusUrl",
    "routeStatusState",
    "routeOptionsFromStatus",
    "projectRouteStatus",
    "getRouteDescriptor",
    "refreshAgentStatus",
    "persistAgentSettings",
    "testAgentSettings",
    "storeOpenRouterCredential",
  ]) {
    assert.ok(Object.hasOwn(statusPoller, name), `agent_status_poller.js exports ${name}`);
  }

  assert.deepEqual(Object.keys(candidateActions).sort(), [
    "APPLY_ELIGIBILITY_REASON",
    "applyEligibility",
    "candidateActionState",
    "candidateGraphPresentForBubble",
    "disabledApplyEligibility",
    "normalizeApplyEligibility",
  ].sort());

  for (const name of [
    "renderDeveloper",
    "renderDeveloperDisclosure",
    "renderDeveloperSection",
    "renderSettings",
    "renderSettingsSection",
  ]) {
    assert.equal(typeof panelComposer[name], "function", `panel_composer.js exports ${name}`);
  }
  assert.equal(Object.hasOwn(panelComposer, "renderDeveloperSubsection"), false);
});

test("canonical route policy keeps DeepSeek as an OpenRouter alias only", () => {
  assert.equal(statusPoller.ROUTE_ALIASES.deepseek, "openrouter");
  assert.equal(Object.hasOwn(statusPoller.ROUTE_LABELS, "deepseek"), false);
  assert.equal(statusPoller.CANONICAL_AGENT_PROVIDERS.has("deepseek"), false);
});
