import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const WEB_ROOT = path.join(REPO_ROOT, "vibecomfy", "comfy_nodes", "web");

function source(name) {
  return readFileSync(path.join(WEB_ROOT, name), "utf8");
}

const roundtripSource = source("vibecomfy_roundtrip.js");
const schedulerSource = source("panel_scheduler.js");

function declarationPattern(name) {
  return new RegExp(
    String.raw`(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+${name}\s*\(`
      + String.raw`|(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+${name}\b`,
  );
}

function assertNotDeclaredInRoundtrip(name) {
  assert.equal(
    declarationPattern(name).test(roundtripSource),
    false,
    `vibecomfy_roundtrip.js must not declare ${name}`,
  );
}

function assertImportFrom(ownerModule, importedName) {
  const importPattern = new RegExp(
    String.raw`import\s*\{[\s\S]*?\b${importedName}\b[\s\S]*?\}\s*from\s*["']\./${ownerModule}\.js["']`,
  );
  assert.match(
    roundtripSource,
    importPattern,
    `vibecomfy_roundtrip.js must import ${importedName} from ${ownerModule}.js`,
  );
}

test("roundtrip does not re-own status poller declarations", () => {
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
    "normalizeModelPreference",
    "normalizeRoutePreference",
    "persistAgentSettings",
    "storeOpenRouterCredential",
    "configureAgentStatusDeps",
    "getRouteOptions",
    "getRouteDescriptor",
    "buildStatusUrl",
    "routeStatusState",
    "routeOptionsFromStatus",
    "projectRouteStatus",
    "clearAgentStatusRetry",
    "scheduleAgentStatusRetry",
    "populateRouteSelect",
    "refreshAgentStatus",
    "syncChooseEngineGate",
    "testAgentSettings",
  ]) {
    assertNotDeclaredInRoundtrip(name);
  }

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
    "normalizeModelPreference",
    "normalizeRoutePreference",
    "persistAgentSettings",
    "storeOpenRouterCredential",
    "getRouteDescriptor",
    "populateRouteSelect",
    "refreshAgentStatus",
    "refreshResearchContributionSetting",
    "saveResearchContributionSetting",
    "scheduleAgentStatusRetry",
    "syncChooseEngineGate",
    "testAgentSettings",
  ]) {
    assertImportFrom("agent_status_poller", name);
  }
});

test("roundtrip does not re-own composer or candidate action declarations", () => {
  for (const name of [
    "renderSettings",
    "renderSettingsSection",
    "renderDeveloper",
    "renderDeveloperDisclosure",
    "renderDeveloperSubsection",
    "renderDeveloperSection",
    "APPLY_ELIGIBILITY_REASON",
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
    "composerApplyDisplayState",
  ]) {
    assertNotDeclaredInRoundtrip(name);
  }

  assertImportFrom("panel_composer", "renderSettingsSection");
  assertImportFrom("panel_composer", "renderDeveloperSection");
  assertImportFrom("agent_candidate_actions", "APPLY_ELIGIBILITY_REASON");
  assertImportFrom("agent_candidate_actions", "applyEligibility");
  assertImportFrom("agent_candidate_actions", "disabledApplyEligibility");
  assertImportFrom("agent_candidate_actions", "candidateActionState");
});

test("roundtrip scheduler ownership stays delegated", () => {
  const schedulerOwnerApis = [
    "normalizeDirtySectionList",
    "agentPanelPendingDirtySections",
    "isAgentPanelRootConnected",
    "hasPendingAgentPanelFlush",
    "noteAgentPanelCommit",
    "markAgentPanelDirty",
    "markAllAgentPanelDirty",
    "consumeAgentPanelDirtySections",
    "markAgentPanelDirtyAfterCommit",
    "ensureScheduledAgentPanelDirtyFlush",
    "scheduleRenderAgentPanel",
    "setRenderGateway",
  ];
  for (const name of schedulerOwnerApis) {
    assertNotDeclaredInRoundtrip(name);
  }
  for (const name of schedulerOwnerApis.filter((name) => name !== "agentPanelPendingDirtySections")) {
    assertImportFrom("panel_scheduler", name);
  }
});

test("roundtrip does not re-own thread detail selector implementations", () => {
  for (const name of [
    "responseDetailForMessage",
    "turnIdForDetailLookup",
    "changeDetailsFromResponseDetail",
    "renderCandidate",
    "renderFailure",
    "renderQueue",
  ]) {
    assertNotDeclaredInRoundtrip(name);
  }

  for (const name of [
    "appendCandidateDetail",
    "appendFailureDetail",
    "appendQueueDetail",
    "changeDetailsForMessage",
    "createBubbleDetailSection",
  ]) {
    assertImportFrom("panel_thread", name);
  }
});

test("roundtrip does not re-own preview DOM renderer declarations", () => {
  for (const name of [
    "syncPreviewDomOverlay",
    "ensurePreviewDomOverlayRoot",
    "appendPreviewDomChip",
    "previewChipGeometry",
  ]) {
    assertNotDeclaredInRoundtrip(name);
  }

  assertImportFrom("panel_overlay", "clearPreviewDomOverlay");
  assertImportFrom("panel_overlay", "drawPreviewOverlay");
  assertImportFrom("panel_overlay", "installAgentPreviewOverlay");
  assertImportFrom("panel_overlay", "invalidateOverlayDrawModelCache");
});

test("scheduler owns status render sections with notice invalidation", () => {
  assertNotDeclaredInRoundtrip("SETTINGS_STATUS_RENDER_SECTIONS");
  assertImportFrom("panel_scheduler", "SETTINGS_STATUS_RENDER_SECTIONS");

  const match = schedulerSource.match(
    /export\s+const\s+SETTINGS_STATUS_RENDER_SECTIONS\s*=\s*Object\.freeze\(\[([\s\S]*?)\]\);/,
  );
  assert.ok(match, "panel_scheduler.js must export SETTINGS_STATUS_RENDER_SECTIONS");
  assert.match(match[1], /\bRENDER_SECTIONS\.THREAD\b/);
  assert.match(match[1], /\bRENDER_SECTIONS\.SETTINGS\b/);
  assert.match(match[1], /\bRENDER_SECTIONS\.COMPOSER\b/);
  assert.match(match[1], /\bRENDER_SECTIONS\.NOTICE\b/);
  assert.doesNotMatch(match[1], /\bRENDER_SECTIONS\.DEVELOPER\b/);
});
