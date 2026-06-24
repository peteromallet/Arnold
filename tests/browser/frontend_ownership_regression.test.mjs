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
    "buildStatusUrl",
    "clearAgentStatusRetry",
    "refreshAgentStatus",
    "scheduleAgentStatusRetry",
    "populateRouteSelect",
    "syncChooseEngineGate",
    "testAgentSettings",
  ]) {
    assertNoOwnerDefinition(name);
  }

  assert.match(roundtripSource, /from\s+["']\.\/agent_status_poller\.js["']/);
  assert.match(roundtripSource, /refreshAgentStatus:\s*\(panel,\s*opts\)\s*=>\s*pollerRefreshAgentStatus\(/);
  assert.match(roundtripSource, /scheduleAgentStatusRetry:\s*\(panel,\s*route,\s*model,\s*opts\)\s*=>\s*[\s\S]*?pollerScheduleAgentStatusRetry\(/);
  assert.match(roundtripSource, /syncChooseEngineGate:\s*\(panel\)\s*=>\s*pollerSyncChooseEngineGate\(/);
  assert.match(roundtripSource, /pollerPopulateRouteSelect\(.*agentStatusDeps\(\)\)/);
  assert.match(roundtripSource, /persistAgentSettings\(panel,\s*\{\s*includeCredential\s*\},\s*agentStatusDeps\(\)\)/);
  assert.match(roundtripSource, /testAgentSettingsImpl\(currentAgentPanel\(\),\s*agentStatusDeps\(\)\)/);
  assert.match(roundtripSource, /storeOpenRouterCredential\(panel,\s*apiKey\)/);

  assert.doesNotMatch(roundtripSource, /fetch\(\s*["'`]\/vibecomfy\/agent\/settings/);
  assert.doesNotMatch(roundtripSource, /fetch\(\s*["'`]\/vibecomfy\/agent\/test/);
  assert.doesNotMatch(roundtripSource, /fetch\(\s*["'`]\/vibecomfy\/agent\/credential/);
  assert.doesNotMatch(roundtripSource, /\blocalStorage\s*[=.]/);
});

test("vibecomfy_roundtrip keeps composer and candidate selector ownership delegated", () => {
  for (const name of [
    "renderDeveloper",
    "renderDeveloperDisclosure",
    "renderDeveloperSubsection",
    "renderSettings",
    "renderSettingsSection",
    "renderDeveloperSection",
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

  assert.match(roundtripSource, /from\s+["']\.\/panel_composer\.js["']/);
  assert.match(roundtripSource, /from\s+["']\.\/agent_candidate_actions\.js["']/);
  assert.match(roundtripSource, /composerRenderSettingsSection\(nextPanel,\s*composerRenderDeps\(\)\)/);
  assert.match(roundtripSource, /composerRenderDeveloperSection\(panel,\s*composerRenderDeps\(\)\)/);
  assert.match(roundtripSource, /composerRenderDeveloperSection\(nextPanel,\s*composerRenderDeps\(\)\)/);

  const composerSectionCallPattern = /composerRender(?:Settings|Developer)Section\([^)]*,\s*composerRenderDeps\(\)\)/;
  assert.match(roundtripSource, composerSectionCallPattern);

  assert.doesNotMatch(roundtripSource, /function\s+renderDeveloper\s*\(/);
  assert.doesNotMatch(roundtripSource, /function\s+renderDeveloperDisclosure\s*\(/);
  assert.doesNotMatch(roundtripSource, /function\s+renderSettings\s*\(/);
  assert.doesNotMatch(roundtripSource, /function\s+renderDeveloperSection\s*\(/);
  assert.doesNotMatch(roundtripSource, /function\s+renderSettingsSection\s*\(/);
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

test("canonical route policy keeps DeepSeek as a distinct provider route", () => {
  assert.equal(statusPoller.ROUTE_ALIASES.deepseek, "deepseek");
  assert.equal(Object.hasOwn(statusPoller.ROUTE_LABELS, "deepseek"), true);
  assert.equal(statusPoller.CANONICAL_AGENT_PROVIDERS.has("deepseek"), true);
});
