/**
 * surface-coverage — Comprehensive M2 SDK surface coverage example.
 *
 * Imports and exercises every public SDK export that isn't already
 * covered by the focused examples (toolbar, inspector, overlay,
 * status, code-panel, writing-canary, stage-canary).
 *
 * This file is a governance fixture: it exists to prove that every
 * public type/interface/function in @reigh/editor-sdk is importable
 * by SDK-only extension code and has a documented usage pattern.
 *
 * @publicContract
 */

import {
  defineExtension,
  validateExtensionId,
  validateContributionId,
  setEditorShellRoot,
  getEditorShellRoot,
  createExtensionContext,
} from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionContext,
  DisposeHandle,
  ExtensionId,
  ContributionId,
  ExtensionManifest,
  ExtensionActivateFn,
  DefineExtensionOptions,
  ExtensionSettingsService,
  ExtensionI18nService,
  ExtensionDiagnosticsService,
  ExtensionChromeService,
  ProcessSpawnConfig,
  ProcessManifestEntry,
  ExtensionPermissionDeclaration,
  ProjectExtensionRequirement,
  ProjectExtensionRequirements,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Type-level demonstrations (compile-time only, no runtime side effects)
// ---------------------------------------------------------------------------

/** Demonstrate branded ExtensionId shape. */
const exampleExtensionId: ExtensionId = 'com.example.coverage' as ExtensionId;

/** Demonstrate branded ContributionId shape. */
const exampleContributionId: ContributionId =
  'coverage-demo' as ContributionId;

/** Demonstrate ExtensionManifest shape (the full manifest contract). */
const exampleManifest: ExtensionManifest = {
  id: exampleExtensionId,
  version: '1.0.0',
  label: 'Surface Coverage Example',
  description: 'Covers all remaining public SDK surface types.',
  apiVersion: 1,
  contributions: [
    {
      id: exampleContributionId,
      kind: 'slot',
      slot: 'toolbar',
      label: 'Coverage toolbar slot',
    },
  ],
};

/** Demonstrate ExtensionActivateFn alias. */
const exampleActivate: ExtensionActivateFn = (
  _ctx: ExtensionContext,
): DisposeHandle => ({
  dispose(): void {
    /* noop */
  },
});

/** Demonstrate DefineExtensionOptions shape. */
const exampleOptions: DefineExtensionOptions = {
  manifest: exampleManifest,
  activate: exampleActivate,
};

/** Demonstrate ProcessSpawnConfig (reserved, descriptive only). */
const exampleProcessSpawn: ProcessSpawnConfig = {
  command: 'node',
  args: ['--version'],
  env: { NODE_ENV: 'development' },
  cwd: '/tmp',
};

/** Demonstrate ProcessManifestEntry (reserved, descriptive only). */
const exampleProcessManifest: ProcessManifestEntry = {
  id: 'coverage-process',
  label: 'Coverage helper process',
  spawn: exampleProcessSpawn,
  protocol: 'stdio-jsonrpc',
  restartPolicy: 'on-failure',
};

/** Demonstrate ExtensionPermissionDeclaration (reserved, descriptive only). */
const examplePermission: ExtensionPermissionDeclaration = {
  reason: 'Network access for fetching project assets.',
  posture: { network: true },
};

/** Demonstrate ProjectExtensionRequirement shape. */
const exampleProjectReq: ProjectExtensionRequirement = {
  extensionId: 'com.example.dependency',
  versionRange: '>=1.0.0',
  posture: 'required',
};

/** Demonstrate ProjectExtensionRequirements container. */
const exampleProjectReqs: ProjectExtensionRequirements = {
  requirements: [exampleProjectReq],
};

/** Demonstrate shell root registry helpers in a noop fashion. */
function demonstrateShellRoot(): void {
  // Get current (null when no shell is mounted)
  const current = getEditorShellRoot();
  // Set to null (clear) — safe noop when already null
  setEditorShellRoot(null);
  // Restore whatever was there
  setEditorShellRoot(current);
}

// ---------------------------------------------------------------------------
// Extension definition
// ---------------------------------------------------------------------------

export const surfaceCoverageExtension: ReighExtension = defineExtension(
  exampleOptions,
);

/** Activate the coverage extension, demonstrating all service interfaces. */
export function activateCoverageExtension(
  ctx: ExtensionContext,
): DisposeHandle {
  // ---- ExtensionSettingsService -----------------------------------------
  const settings: ExtensionSettingsService = ctx.services.settings;
  settings.set('coverage.activated', true);
  const activated = settings.get<boolean>('coverage.activated');
  const allKeys = settings.keys();

  // ---- ExtensionI18nService ----------------------------------------------
  const i18n: ExtensionI18nService = ctx.services.i18n;
  const greeting = i18n.t('coverage.greeting', { name: 'world' });

  // ---- ExtensionDiagnosticsService ---------------------------------------
  const diag: ExtensionDiagnosticsService = ctx.services.diagnostics;
  diag.report({
    severity: 'info',
    code: 'coverage/activated',
    message: `Coverage activated. Settings keys: ${allKeys.join(', ')}`,
    detail: { activated, greeting },
  });

  // ---- ExtensionChromeService --------------------------------------------
  const chrome: ExtensionChromeService = ctx.chrome;
  chrome.toast('Coverage extension ready.', 'info');
  chrome.progress(100, 'Coverage complete');
  chrome.announce('Coverage extension activated.');

  // ---- ID validation -----------------------------------------------------
  const idErrors = validateExtensionId(exampleExtensionId);
  const contribErrors = validateContributionId(exampleContributionId);
  if (idErrors.length > 0 || contribErrors.length > 0) {
    chrome.toast('ID validation failed unexpectedly.', 'error');
  }

  // ---- Shell root helpers ------------------------------------------------
  demonstrateShellRoot();

  // ---- Reserved manifest fields (descriptive only, no runtime effect) -----
  // These are exercised above as type-level demonstrations.
  void exampleProcessManifest;
  void examplePermission;
  void exampleProcessSpawn;
  void exampleProjectReqs;

  return {
    dispose(): void {
      settings.delete('coverage.activated');
      chrome.toast('Coverage extension disposed.', 'info');
    },
  };
}
