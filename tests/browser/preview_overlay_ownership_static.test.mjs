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
const panelOverlaySource = source("panel_overlay.js");

function declarationPattern(name) {
  return new RegExp(
    String.raw`(?:^|\n)\s*(?:export\s+)?(?:async\s+)?function\s+${name}\s*\(`
      + String.raw`|(?:^|\n)\s*(?:export\s+)?(?:const|let|var)\s+${name}\b`,
  );
}

function functionBody(name) {
  const match = roundtripSource.match(
    new RegExp(String.raw`(?:export\s+)?function\s+${name}\s*\([^)]*\)\s*\{([\s\S]*?)\n\}`),
  );
  assert.ok(match, `expected ${name} wrapper in vibecomfy_roundtrip.js`);
  return match[1];
}

test("panel_overlay owns preview overlay implementation details", () => {
  for (const name of [
    "drawPreviewOverlay",
    "buildOverlayDrawModel",
    "computeGhostDimensions",
    "overlayDrawCacheKey",
    "safePreviewOverlayText",
    "clearPreviewDomOverlay",
    "syncPreviewDomOverlay",
    "ensurePreviewDomOverlayRoot",
    "appendPreviewDomChip",
  ]) {
    assert.match(panelOverlaySource, declarationPattern(name), `panel_overlay.js must declare ${name}`);
  }

  for (const removedDomOwner of [
    "previewChipGeometry",
  ]) {
    assert.doesNotMatch(
      panelOverlaySource,
      declarationPattern(removedDomOwner),
      `panel_overlay.js must not keep the removed DOM preview renderer ${removedDomOwner}`,
    );
  }
});

test("roundtrip preview overlay export stays a thin owner-module facade", () => {
  for (const forbidden of [
    "_overlayDrawCacheKey",
    "_buildOverlayDrawModel",
    "_computeGhostDimensions",
    "_warnOverlayUnresolved",
    "FORBIDDEN_PREVIEW_OVERLAY_TEXT_PATTERNS",
    "safePreviewOverlayText",
    "syncPreviewDomOverlay",
    "clearPreviewDomOverlay",
    "ensurePreviewDomOverlayRoot",
    "appendPreviewDomChip",
  ]) {
    assert.equal(
      declarationPattern(forbidden).test(roundtripSource),
      false,
      `vibecomfy_roundtrip.js must not declare preview overlay owner symbol ${forbidden}`,
    );
  }

  assert.match(
    roundtripSource,
    /import\s*\{[\s\S]*?drawPreviewOverlay\s+as\s+panelOverlayDrawPreviewOverlay[\s\S]*?\}\s*from\s*["']\.\/panel_overlay\.js["']/,
    "roundtrip must import the canonical panel_overlay drawPreviewOverlay",
  );

  const body = functionBody("drawPreviewOverlay");
  assert.match(body, /panelOverlayDrawPreviewOverlay\(ctx,\s*diff,\s*previewOverlayDeps\(\)\)/);
  assert.doesNotMatch(body, /\bctx\.(?:fillRect|strokeRect|fillText|measureText|beginPath|bezierCurveTo|roundRect)\b/);
  assert.doesNotMatch(body, /\b(?:liveByUid|candidateByUid|ghostDimsByUid|editedFieldsByUid)\b/);
});

test("runtime installer passes the owner renderer and syncs live DOM chips from the owner module", () => {
  const installBody = functionBody("installAgentPreviewOverlay");
  assert.match(installBody, /installAgentPreviewOverlayImpl\(app,\s*\{/);
  assert.match(installBody, /drawPreviewOverlay:\s*panelOverlayDrawPreviewOverlay/);
  assert.doesNotMatch(installBody, /drawPreviewOverlay:\s*drawPreviewOverlay\b/);
  assert.doesNotMatch(installBody, /syncPreviewDomOverlay/);

  const ownerInstallMatch = panelOverlaySource.match(
    /export\s+function\s+installAgentPreviewOverlay\s*\([^)]*\)\s*\{([\s\S]*?)\n\}/,
  );
  assert.ok(ownerInstallMatch, "panel_overlay installAgentPreviewOverlay must exist");
  assert.match(
    ownerInstallMatch[1],
    /syncPreviewDomOverlay\(app,\s*ctx/,
    "live preview draw loop must sync fixed-position DOM preview chips above Comfy text widgets",
  );
});
