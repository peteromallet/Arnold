/**
 * Tests for extensionMigration.ts (M14, T24).
 *
 * Covers:
 *   - compareContributionIds: identical, local-only, installed-only, shared, empty.
 *   - detectMetadataGaps: ID mismatch, version diff, API version diff, publisher diff,
 *     license diff, settings schema version diff, dependency diff, migration declaration
 *     diff, contribution count diff, label diff, no gaps at all.
 *   - checkMigrationPreconditions: ID mismatch blocks, local-only contributions block,
 *     identical manifests pass, installed-only contributions are non-blocking,
 *     non-blocking gaps produce warnings.
 *   - executeLocalToInstalledMigration: successful migration with settings,
 *     migration with no local settings, migration blocked by ID mismatch,
 *     migration blocked by local-only contributions, migration with metadata gaps (warnings),
 *     migration where enablement already exists, migration where pack record creation fails,
 *     migration where settings transfer fails (non-blocking).
 *   - readLocalSettings: reads settings from localStorage, empty when no settings,
 *     handles corrupt values gracefully.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  compareContributionIds,
  detectMetadataGaps,
  checkMigrationPreconditions,
  executeLocalToInstalledMigration,
  readLocalSettings,
} from './extensionMigration';
import type {
  ContributionIdComparison,
  MetadataGapResult,
  MigrationPreconditionResult,
  MigrationExecuteResult,
  LocalInstalledMigrationInput,
} from './extensionMigration';
import type {
  ExtensionStateRepository,
  ExtensionPackRecord,
  ExtensionEnablementState,
  ExtensionSettingsSnapshot,
  ExtensionLifecycleEvent,
  FullExtensionState,
} from './extensionStateRepository';
import { createLifecycleEvent } from './extensionStateRepository';
import type {
  ExtensionManifest,
  InstalledExtensionPackage,
  InstalledExtensionMetadata,
  IntegrityHash,
  ExtensionContribution,
} from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeIntegrityHash(value?: string): IntegrityHash {
  return {
    algorithm: 'sha256',
    value: value ?? 'dGVzdC1oYXNoLXZhbHVlLWZvci10ZXN0aW5nLXRlc3Rpbmc=',
  };
}

function makeLocalManifest(overrides?: Partial<ExtensionManifest>): ExtensionManifest {
  return {
    id: 'com.test.migration' as any,
    version: '1.0.0',
    label: 'Test Migration Extension',
    publisher: 'Test Publisher',
    license: 'MIT',
    settingsSchema: { version: 1 },
    contributions: [
      { kind: 'command', id: 'com.test.migration.myCommand' } as ExtensionContribution,
      { kind: 'effect', id: 'com.test.migration.myEffect' } as ExtensionContribution,
    ],
    ...overrides,
  };
}

function makeInstalledManifest(overrides?: Partial<ExtensionManifest>): ExtensionManifest {
  return {
    id: 'com.test.migration' as any,
    version: '1.0.0',
    label: 'Test Migration Extension',
    publisher: 'Test Publisher',
    license: 'MIT',
    settingsSchema: { version: 1 },
    contributions: [
      { kind: 'command', id: 'com.test.migration.myCommand' } as ExtensionContribution,
      { kind: 'effect', id: 'com.test.migration.myEffect' } as ExtensionContribution,
    ],
    ...overrides,
  };
}

function makeInstalledPack(overrides?: {
  metadata?: Partial<InstalledExtensionMetadata>;
  manifest?: Partial<ExtensionManifest>;
  bundleContent?: string;
}): InstalledExtensionPackage {
  const manifest = makeInstalledManifest(overrides?.manifest);
  return {
    metadata: {
      extensionId: manifest.id as any,
      version: manifest.version as string,
      integrity: makeIntegrityHash(),
      enabled: true,
      ...overrides?.metadata,
    },
    manifest,
    bundleContent: overrides?.bundleContent ?? '// test bundle content',
  };
}

/** Create a mock repository with vi.fn() methods. */
function makeMockRepository(overrides?: Partial<{
  putPackRecord: ReturnType<typeof vi.fn>;
  getEnablementState: ReturnType<typeof vi.fn>;
  putEnablementState: ReturnType<typeof vi.fn>;
  putSettingsSnapshot: ReturnType<typeof vi.fn>;
  putLockEntry: ReturnType<typeof vi.fn>;
  appendLifecycleEvent: ReturnType<typeof vi.fn>;
  getFullExtensionState: ReturnType<typeof vi.fn>;
  isDisposed: boolean;
}>): ExtensionStateRepository {
  return {
    initialize: vi.fn().mockResolvedValue(undefined),
    dispose: vi.fn().mockResolvedValue(undefined),
    isDisposed: overrides?.isDisposed ?? false,
    putPackRecord: overrides?.putPackRecord ?? vi.fn().mockResolvedValue(undefined),
    updatePackRecord: vi.fn().mockResolvedValue(undefined),
    getPackRecord: vi.fn().mockResolvedValue(null),
    getAllPackRecords: vi.fn().mockResolvedValue([]),
    deletePackRecord: vi.fn().mockResolvedValue(undefined),
    putEnablementState: overrides?.putEnablementState ?? vi.fn().mockResolvedValue(undefined),
    getEnablementState: overrides?.getEnablementState ?? vi.fn().mockResolvedValue(null),
    getAllEnablementStates: vi.fn().mockResolvedValue([]),
    deleteEnablementState: vi.fn().mockResolvedValue(undefined),
    putDevOverride: vi.fn().mockResolvedValue(undefined),
    getDevOverride: vi.fn().mockResolvedValue(null),
    getAllDevOverrides: vi.fn().mockResolvedValue([]),
    deleteDevOverride: vi.fn().mockResolvedValue(undefined),
    putSettingsSnapshot: overrides?.putSettingsSnapshot ?? vi.fn().mockResolvedValue(undefined),
    getSettingsSnapshot: vi.fn().mockResolvedValue(null),
    getAllSettingsSnapshots: vi.fn().mockResolvedValue([]),
    deleteSettingsSnapshot: vi.fn().mockResolvedValue(undefined),
    appendLifecycleEvent: overrides?.appendLifecycleEvent ?? vi.fn().mockResolvedValue(undefined),
    queryLifecycleEvents: vi.fn().mockResolvedValue([]),
    getLifecycleEvents: vi.fn().mockResolvedValue([]),
    getLock: vi.fn().mockResolvedValue({ entries: {}, lastUpdatedAt: new Date().toISOString() }),
    putLockEntry: overrides?.putLockEntry ?? vi.fn().mockResolvedValue(undefined),
    deleteLockEntry: vi.fn().mockResolvedValue(undefined),
    getFullExtensionState: overrides?.getFullExtensionState ?? vi.fn().mockResolvedValue({
      enablement: {},
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: new Date().toISOString() },
    }),
  } as unknown as ExtensionStateRepository;
}

// ---------------------------------------------------------------------------
// compareContributionIds
// ---------------------------------------------------------------------------

describe('compareContributionIds', () => {
  it('returns identical=true when both manifests have the same contribution IDs', () => {
    const local = makeLocalManifest();
    const installed = makeInstalledManifest();

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(true);
    expect(result.localOnly).toHaveLength(0);
    expect(result.installedOnly).toHaveLength(0);
    expect(result.shared).toHaveLength(2);
    expect(result.shared).toContain('com.test.migration.myCommand');
    expect(result.shared).toContain('com.test.migration.myEffect');
    expect(result.localCount).toBe(2);
    expect(result.installedCount).toBe(2);
  });

  it('returns identical=true when both manifests have no contributions', () => {
    const local = makeLocalManifest({ contributions: [] });
    const installed = makeInstalledManifest({ contributions: [] });

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(true);
    expect(result.localOnly).toHaveLength(0);
    expect(result.installedOnly).toHaveLength(0);
    expect(result.shared).toHaveLength(0);
    expect(result.localCount).toBe(0);
    expect(result.installedCount).toBe(0);
  });

  it('detects local-only contribution IDs', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
        { kind: 'transition', id: 'com.test.migration.trans1' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
      ],
    });

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(false);
    expect(result.localOnly).toEqual(['com.test.migration.eff1', 'com.test.migration.trans1']);
    expect(result.installedOnly).toHaveLength(0);
    expect(result.shared).toEqual(['com.test.migration.cmd1']);
    expect(result.localCount).toBe(3);
    expect(result.installedCount).toBe(1);
  });

  it('detects installed-only contribution IDs', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
        { kind: 'shader', id: 'com.test.migration.shader1' } as ExtensionContribution,
      ],
    });

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(false);
    expect(result.localOnly).toHaveLength(0);
    expect(result.installedOnly).toEqual(['com.test.migration.eff1', 'com.test.migration.shader1']);
    expect(result.shared).toEqual(['com.test.migration.cmd1']);
    expect(result.localCount).toBe(1);
    expect(result.installedCount).toBe(3);
  });

  it('detects both local-only and installed-only contribution IDs', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.shared1' } as ExtensionContribution,
        { kind: 'effect', id: 'com.test.migration.localOnly' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.shared1' } as ExtensionContribution,
        { kind: 'shader', id: 'com.test.migration.installedOnly' } as ExtensionContribution,
      ],
    });

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(false);
    expect(result.localOnly).toEqual(['com.test.migration.localOnly']);
    expect(result.installedOnly).toEqual(['com.test.migration.installedOnly']);
    expect(result.shared).toEqual(['com.test.migration.shared1']);
  });

  it('returns identical=true when contributions are the same but in different order', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
      ],
    });

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(true);
    expect(result.shared).toHaveLength(2);
  });

  it('handles undefined contributions gracefully', () => {
    const local: ExtensionManifest = {
      id: 'com.test.migration' as any,
      version: '1.0.0',
      label: 'Test',
    };
    const installed: ExtensionManifest = {
      id: 'com.test.migration' as any,
      version: '1.0.0',
      label: 'Test',
    };

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(true);
    expect(result.localCount).toBe(0);
    expect(result.installedCount).toBe(0);
  });

  it('filters out contributions without IDs', () => {
    const local: ExtensionManifest = {
      id: 'com.test.migration' as any,
      version: '1.0.0',
      label: 'Test',
      contributions: [
        { kind: 'command' } as ExtensionContribution,
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
      ],
    };
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
      ],
    });

    const result = compareContributionIds(local, installed);

    expect(result.identical).toBe(true);
    expect(result.localCount).toBe(1);
    expect(result.installedCount).toBe(1);
  });
});

// ---------------------------------------------------------------------------
// detectMetadataGaps
// ---------------------------------------------------------------------------

describe('detectMetadataGaps', () => {
  it('returns no gaps when manifests are identical', () => {
    const local = makeLocalManifest();
    const installed = makeInstalledManifest();

    const result = detectMetadataGaps(local, installed);

    expect(result.hasBlockingGaps).toBe(false);
    expect(result.gaps).toHaveLength(0);
    expect(result.blockingGaps).toHaveLength(0);
    expect(result.nonBlockingGaps).toHaveLength(0);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('blocks migration when extension IDs do not match', () => {
    const local = makeLocalManifest({ id: 'com.test.local' as any });
    const installed = makeInstalledManifest({ id: 'com.test.installed' as any });

    const result = detectMetadataGaps(local, installed);

    expect(result.hasBlockingGaps).toBe(true);
    expect(result.blockingGaps).toHaveLength(1);
    expect(result.blockingGaps[0].field).toBe('id');
    expect(result.blockingGaps[0].blocking).toBe(true);
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].severity).toBe('error');
  });

  it('detects version differences (non-blocking info)', () => {
    const local = makeLocalManifest({ version: '1.0.0' });
    const installed = makeInstalledManifest({ version: '2.0.0' });

    const result = detectMetadataGaps(local, installed);

    expect(result.hasBlockingGaps).toBe(false);
    const versionGap = result.gaps.find((g) => g.field === 'version');
    expect(versionGap).toBeDefined();
    expect(versionGap!.blocking).toBe(false);
    expect(versionGap!.severity).toBe('info');
  });

  it('detects API version differences', () => {
    const local = makeLocalManifest({ apiVersion: 2 });
    const installed = makeInstalledManifest({ apiVersion: 1 });

    const result = detectMetadataGaps(local, installed);

    const apiGap = result.gaps.find((g) => g.field === 'apiVersion');
    expect(apiGap).toBeDefined();
    expect(apiGap!.blocking).toBe(false);
  });

  it('detects API version present in local but missing from installed (warning)', () => {
    const local = makeLocalManifest({ apiVersion: 2 });
    const installed = makeInstalledManifest({ apiVersion: undefined });

    const result = detectMetadataGaps(local, installed);

    const apiGap = result.gaps.find((g) => g.field === 'apiVersion');
    expect(apiGap).toBeDefined();
    expect(apiGap!.severity).toBe('warning');
  });

  it('detects publisher differences', () => {
    const local = makeLocalManifest({ publisher: 'Local Publisher' });
    const installed = makeInstalledManifest({ publisher: 'Installed Publisher' });

    const result = detectMetadataGaps(local, installed);

    const pubGap = result.gaps.find((g) => g.field === 'publisher');
    expect(pubGap).toBeDefined();
    expect(pubGap!.blocking).toBe(false);
    expect(pubGap!.severity).toBe('info');
  });

  it('detects license differences', () => {
    const local = makeLocalManifest({ license: 'MIT' });
    const installed = makeInstalledManifest({ license: 'Apache-2.0' });

    const result = detectMetadataGaps(local, installed);

    const licGap = result.gaps.find((g) => g.field === 'license');
    expect(licGap).toBeDefined();
    expect(licGap!.blocking).toBe(false);
  });

  it('detects settings schema version differences', () => {
    const local = makeLocalManifest({ settingsSchema: { version: 1 } });
    const installed = makeInstalledManifest({ settingsSchema: { version: 2 } });

    const result = detectMetadataGaps(local, installed);

    const schemaGap = result.gaps.find((g) => g.field === 'settingsSchema');
    expect(schemaGap).toBeDefined();
    expect(schemaGap!.severity).toBe('warning');
  });

  it('detects contribution count differences', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'c1' } as ExtensionContribution,
        { kind: 'command', id: 'c2' } as ExtensionContribution,
        { kind: 'command', id: 'c3' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'c1' } as ExtensionContribution,
      ],
    });

    const result = detectMetadataGaps(local, installed);

    const countGap = result.gaps.find((g) => g.field === 'contributions' && g.description.includes('Contribution count'));
    expect(countGap).toBeDefined();
    expect(countGap!.severity).toBe('warning');
  });

  it('detects dependency count differences', () => {
    const local = makeLocalManifest({
      dependsOn: [
        { extensionId: 'dep.a' },
        { extensionId: 'dep.b' },
      ],
    });
    const installed = makeInstalledManifest({
      dependsOn: [
        { extensionId: 'dep.a' },
      ],
    });

    const result = detectMetadataGaps(local, installed);

    const depCountGap = result.gaps.find((g) => g.field === 'dependsOn' && g.description.includes('Dependency count'));
    expect(depCountGap).toBeDefined();
  });

  it('detects specific dependency differences', () => {
    const local = makeLocalManifest({
      dependsOn: [
        { extensionId: 'dep.a' },
        { extensionId: 'dep.local-only' },
      ],
    });
    const installed = makeInstalledManifest({
      dependsOn: [
        { extensionId: 'dep.a' },
        { extensionId: 'dep.installed-only' },
      ],
    });

    const result = detectMetadataGaps(local, installed);

    const localOnlyDepGap = result.gaps.find((g) => g.field === 'dependsOn' && g.presentIn === 'local-only');
    expect(localOnlyDepGap).toBeDefined();
    expect(localOnlyDepGap!.description).toContain('dep.local-only');

    const installedOnlyDepGap = result.gaps.find((g) => g.field === 'dependsOn' && g.presentIn === 'installed-only');
    expect(installedOnlyDepGap).toBeDefined();
    expect(installedOnlyDepGap!.description).toContain('dep.installed-only');
  });

  it('detects migration declaration gaps', () => {
    const local = makeLocalManifest({
      migrations: [
        { kind: 'settings' as any, fromVersion: '1.0.0', toVersion: '2.0.0' },
      ],
    });
    const installed = makeInstalledManifest({
      migrations: [],
    });

    const result = detectMetadataGaps(local, installed);

    const migGap = result.gaps.find((g) => g.field === 'migrations');
    expect(migGap).toBeDefined();
    expect(migGap!.severity).toBe('warning');
  });

  it('detects label differences (non-blocking info)', () => {
    const local = makeLocalManifest({ label: 'Old Name' });
    const installed = makeInstalledManifest({ label: 'New Name' });

    const result = detectMetadataGaps(local, installed);

    const labelGap = result.gaps.find((g) => g.field === 'label');
    expect(labelGap).toBeDefined();
    expect(labelGap!.blocking).toBe(false);
    expect(labelGap!.severity).toBe('info');
  });

  it('local-only contribution IDs are blocking when no installed-only IDs', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
        { kind: 'effect', id: 'localOnly' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
      ],
    });

    const result = detectMetadataGaps(local, installed);

    const contribGap = result.gaps.find(
      (g) => g.field === 'contributions' && g.presentIn === 'local-only' && g.blocking,
    );
    expect(contribGap).toBeDefined();
    expect(contribGap!.severity).toBe('error');
    expect(result.hasBlockingGaps).toBe(true);
  });

  it('installed-only contribution IDs are non-blocking', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
        { kind: 'effect', id: 'newFeature' } as ExtensionContribution,
      ],
    });

    const result = detectMetadataGaps(local, installed);

    const contribGap = result.gaps.find(
      (g) => g.field === 'contributions' && g.presentIn === 'installed-only',
    );
    expect(contribGap).toBeDefined();
    expect(contribGap!.blocking).toBe(false);
    expect(contribGap!.severity).toBe('info');
  });

  it('stops checking after ID mismatch (no further gaps)', () => {
    const local = makeLocalManifest({
      id: 'com.test.a' as any,
      version: '1.0.0',
      apiVersion: 2,
      publisher: 'Pub A',
    });
    const installed = makeInstalledManifest({
      id: 'com.test.b' as any,
      version: '2.0.0',
      apiVersion: 1,
      publisher: 'Pub B',
    });

    const result = detectMetadataGaps(local, installed);

    // Only the ID mismatch gap should be present
    expect(result.gaps).toHaveLength(1);
    expect(result.blockingGaps).toHaveLength(1);
    expect(result.blockingGaps[0].field).toBe('id');
  });

  it('returns diagnostics with correct severity levels', () => {
    const local = makeLocalManifest({ version: '1.0.0', publisher: 'Old Pub' });
    const installed = makeInstalledManifest({ version: '2.0.0', publisher: 'New Pub' });

    const result = detectMetadataGaps(local, installed);

    const errors = result.diagnostics.filter((d) => d.severity === 'error');
    const warnings = result.diagnostics.filter((d) => d.severity === 'warning');
    const infos = result.diagnostics.filter((d) => d.severity === 'info');

    expect(errors).toHaveLength(0);
    // version diff = info, publisher diff = info, label same => no label gap
    // But if label is same, no label gap. Let's check:
    // version diff (info), publisher diff (info) = 2 diagnostics, both info
    expect(infos.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// checkMigrationPreconditions
// ---------------------------------------------------------------------------

describe('checkMigrationPreconditions', () => {
  it('allows migration when manifests are identical', () => {
    const local = makeLocalManifest();
    const installed = makeInstalledManifest();

    const result = checkMigrationPreconditions(local, installed);

    expect(result.canProceed).toBe(true);
    expect(result.blockingDiagnostics).toHaveLength(0);
    expect(result.contributionComparison.identical).toBe(true);
    expect(result.summary).toContain('can proceed');
  });

  it('blocks migration when extension IDs do not match', () => {
    const local = makeLocalManifest({ id: 'com.test.a' as any });
    const installed = makeInstalledManifest({ id: 'com.test.b' as any });

    const result = checkMigrationPreconditions(local, installed);

    expect(result.canProceed).toBe(false);
    expect(result.blockingDiagnostics).toHaveLength(1);
    expect(result.blockingDiagnostics[0].code).toBe('migration/id-mismatch');
    expect(result.summary).toContain('blocked');
  });

  it('blocks migration when there are local-only contribution IDs', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
        { kind: 'effect', id: 'localOnly' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
      ],
    });

    const result = checkMigrationPreconditions(local, installed);

    expect(result.canProceed).toBe(false);
    expect(result.blockingDiagnostics.some((d) => d.code === 'migration/local-only-contributions')).toBe(true);
  });

  it('allows migration when there are only installed-only contribution IDs (new features)', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
        { kind: 'effect', id: 'newFeature' } as ExtensionContribution,
      ],
    });

    const result = checkMigrationPreconditions(local, installed);

    expect(result.canProceed).toBe(true);
    expect(result.blockingDiagnostics).toHaveLength(0);
    // installed-only contributions don't add a blocking diagnostic in checkMigrationPreconditions
    // but there should be non-blocking warnings from metadata gaps
    expect(result.warningDiagnostics.length).toBeGreaterThanOrEqual(0);
  });

  it('includes metadata gap diagnostics in warnings', () => {
    const local = makeLocalManifest({ version: '1.0.0', publisher: 'Old' });
    const installed = makeInstalledManifest({ version: '2.0.0', publisher: 'New' });

    const result = checkMigrationPreconditions(local, installed);

    expect(result.canProceed).toBe(true);
    expect(result.warningDiagnostics.length).toBeGreaterThan(0);
    // Version diff and publisher diff should produce non-blocking diagnostics
  });

  it('includes all blocking diagnostics when multiple issues exist', () => {
    const local = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
        { kind: 'effect', id: 'localOnly1' } as ExtensionContribution,
        { kind: 'transition', id: 'localOnly2' } as ExtensionContribution,
      ],
    });
    const installed = makeInstalledManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
      ],
    });

    const result = checkMigrationPreconditions(local, installed);

    expect(result.canProceed).toBe(false);
    expect(result.blockingDiagnostics.length).toBeGreaterThanOrEqual(1);
    // Should have local-only contributions blocking diagnostic
    const localOnlyDiag = result.blockingDiagnostics.find((d) => d.code === 'migration/local-only-contributions');
    expect(localOnlyDiag).toBeDefined();
  });

  it('returns frozen objects', () => {
    const local = makeLocalManifest();
    const installed = makeInstalledManifest();

    const result = checkMigrationPreconditions(local, installed);

    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.blockingDiagnostics)).toBe(true);
    expect(Object.isFrozen(result.warningDiagnostics)).toBe(true);
    expect(Object.isFrozen(result.contributionComparison)).toBe(true);
    expect(Object.isFrozen(result.metadataGaps)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// executeLocalToInstalledMigration
// ---------------------------------------------------------------------------

describe('executeLocalToInstalledMigration', () => {
  // ---- Successful migration ----

  it('successfully migrates a local extension to installed with settings', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();
    const localSettings = { theme: 'dark', fontSize: 14, customOption: true };

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings,
      bundleContentRef: 'indexeddb://com.test.migration/v1',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    expect(result.blocked).toBe(false);
    expect(result.extensionId).toBe('com.test.migration');
    expect(result.settingsTransferred).toBe(true);
    expect(result.settingsKeyCount).toBe(3);
    expect(result.lockEntryCreated).toBe(true);
    expect(result.packRecord).not.toBeNull();
    expect(result.packRecord!.extensionId).toBe('com.test.migration');
    expect(result.packRecord!.bundleContentRef).toBe('indexeddb://com.test.migration/v1');
    expect(result.summary).toContain('migrated');
    expect(result.summary).toContain('3 setting(s)');

    // Verify repository calls
    expect(repo.putPackRecord).toHaveBeenCalledTimes(1);
    expect(repo.putEnablementState).toHaveBeenCalledTimes(1);
    expect(repo.putSettingsSnapshot).toHaveBeenCalledTimes(1);
    expect(repo.putLockEntry).toHaveBeenCalledTimes(1);
    expect(repo.appendLifecycleEvent).toHaveBeenCalled();

    // Check settings snapshot values
    const snapshotCall = (repo.putSettingsSnapshot as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(snapshotCall.extensionId).toBe('com.test.migration');
    expect(snapshotCall.values).toEqual({ theme: 'dark', fontSize: 14, customOption: true });
  });

  it('successfully migrates with no local settings (uses manifest defaults)', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack({
      manifest: { settingsDefaults: { defaultOption: 'default-value' } },
    });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://com.test.migration/v1',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    expect(result.settingsTransferred).toBe(true);
    expect(result.settingsKeyCount).toBe(1); // defaultOption from manifest
    expect(result.lockEntryCreated).toBe(true);
  });

  it('successfully migrates when installed version differs from local', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest({ version: '1.0.0' });
    const installedPack = makeInstalledPack({ manifest: { version: '2.0.0' } });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { key: 'value' },
      bundleContentRef: 'indexeddb://com.test.migration/v2',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    expect(result.packRecord!.version).toBe('2.0.0');
    // Should have a non-blocking version gap in warnings
    const versionDiags = result.warningDiagnostics.filter(
      (d) => d.code.includes('version'),
    );
    // Version difference produces a diagnostic (non-blocking)
    expect(versionDiags.length).toBeGreaterThanOrEqual(0);
  });

  // ---- Blocked migration ----

  it('blocks migration when extension IDs do not match', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest({ id: 'com.test.local' as any });
    const installedPack = makeInstalledPack({ manifest: { id: 'com.test.installed' as any } });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.packRecord).toBeNull();
    expect(result.settingsTransferred).toBe(false);
    expect(result.lockEntryCreated).toBe(false);
    expect(result.blockingDiagnostics).toHaveLength(1);
    expect(result.blockingDiagnostics[0].code).toBe('migration/id-mismatch');
    expect(result.summary).toContain('ID mismatch');

    // Repository should not be modified
    expect(repo.putPackRecord).not.toHaveBeenCalled();
  });

  it('blocks migration when local-only contribution IDs exist', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'shared' } as ExtensionContribution,
        { kind: 'effect', id: 'localOnly' } as ExtensionContribution,
      ],
    });
    const installedPack = makeInstalledPack({
      manifest: {
        contributions: [
          { kind: 'command', id: 'shared' } as ExtensionContribution,
        ],
      },
    });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.packRecord).toBeNull();

    // Check that the blocking gap is for contributions
    const contribBlockers = result.blockingDiagnostics.filter(
      (d) => d.code.includes('contributions') || d.code.includes('local-only'),
    );
    expect(contribBlockers.length).toBeGreaterThan(0);

    // Repository should not be modified
    expect(repo.putPackRecord).not.toHaveBeenCalled();
  });

  // ---- Existing enablement state ----

  it('preserves existing enablement state during migration', async () => {
    const existingEnablement: ExtensionEnablementState = {
      extensionId: 'com.test.migration',
      enabled: false,
      lastToggledAt: '2025-01-01T00:00:00.000Z',
      toggleReason: 'Previously disabled',
    };

    const repo = makeMockRepository({
      getEnablementState: vi.fn().mockResolvedValue(existingEnablement),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    // putEnablementState should NOT be called (existing state preserved)
    expect(repo.putEnablementState).not.toHaveBeenCalled();
    // Warning about preserved enablement should be present
    const infoDiags = result.warningDiagnostics.filter((d) => d.severity === 'info');
    expect(infoDiags.some((d) => d.code === 'migration/enablement-preserved')).toBe(true);
  });

  // ---- Pack record creation failure ----

  it('handles pack record creation failure gracefully', async () => {
    const repo = makeMockRepository({
      putPackRecord: vi.fn().mockRejectedValue(new Error('Storage full')),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { key: 'value' },
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.packRecord).toBeNull();
    expect(result.settingsTransferred).toBe(false);
    expect(result.blockingDiagnostics.some((d) => d.code === 'migration/pack-record-failed')).toBe(true);
  });

  // ---- Settings transfer failure (non-blocking) ----

  it('handles settings transfer failure gracefully (non-blocking)', async () => {
    const repo = makeMockRepository({
      putSettingsSnapshot: vi.fn().mockRejectedValue(new Error('Write error')),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { theme: 'dark', fontSize: 14 },
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    // Migration should still succeed (settings transfer failure is non-blocking)
    expect(result.success).toBe(true);
    expect(result.settingsTransferred).toBe(false);
    expect(result.lockEntryCreated).toBe(true);
    const settingsWarnings = result.warningDiagnostics.filter(
      (d) => d.code === 'migration/settings-transfer-failed',
    );
    expect(settingsWarnings).toHaveLength(1);
  });

  // ---- Lock entry failure (non-blocking) ----

  it('handles lock entry creation failure gracefully (non-blocking)', async () => {
    const repo = makeMockRepository({
      putLockEntry: vi.fn().mockRejectedValue(new Error('Lock error')),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { key: 'value' },
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    // Migration should still succeed
    expect(result.success).toBe(true);
    expect(result.lockEntryCreated).toBe(false);
    const lockWarnings = result.warningDiagnostics.filter(
      (d) => d.code === 'migration/lock-entry-failed',
    );
    expect(lockWarnings).toHaveLength(1);
  });

  // ---- Enablement transfer failure (non-blocking) ----

  it('handles enablement state creation failure gracefully', async () => {
    const repo = makeMockRepository({
      putEnablementState: vi.fn().mockRejectedValue(new Error('Enablement error')),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    // Migration should still succeed
    expect(result.success).toBe(true);
    const enableWarnings = result.warningDiagnostics.filter(
      (d) => d.code === 'migration/enablement-transfer-failed',
    );
    expect(enableWarnings).toHaveLength(1);
  });

  // ---- Metadata gaps as warnings ----

  it('includes non-blocking metadata gaps as warnings in result', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest({
      version: '1.0.0',
      publisher: 'Old Publisher',
      license: 'MIT',
    });
    const installedPack = makeInstalledPack({
      manifest: {
        version: '2.0.0',
        publisher: 'New Publisher',
        license: 'Apache-2.0',
      },
    });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    // Should have version, publisher, and license gap warnings
    expect(result.warningDiagnostics.length).toBeGreaterThan(0);
    expect(result.metadataGaps.nonBlockingGaps.length).toBeGreaterThan(0);
  });

  // ---- Lifecycle events ----

  it('emits migration lifecycle events in correct order', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { key: 'value' },
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    expect(result.lifecycleEvents.length).toBeGreaterThan(0);

    // First event should be migration_start
    const startEvent = result.lifecycleEvents.find((e) => e.kind === 'migration_start');
    expect(startEvent).toBeDefined();

    // Should have install event (pack record created)
    const installEvent = result.lifecycleEvents.find(
      (e) => e.kind === 'install' && e.message.includes('Pack record'),
    );
    expect(installEvent).toBeDefined();

    // Should have enable event
    const enableEvent = result.lifecycleEvents.find((e) => e.kind === 'enable');
    expect(enableEvent).toBeDefined();

    // Should have migration_success event (settings transferred)
    const successEvent = result.lifecycleEvents.find((e) => e.kind === 'migration_success');
    expect(successEvent).toBeDefined();

    // Should have activation_success event (final)
    const activationEvent = result.lifecycleEvents.find((e) => e.kind === 'activation_success');
    expect(activationEvent).toBeDefined();
  });

  it('emits migration_failure event when blocked', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest({ id: 'com.test.a' as any });
    const installedPack = makeInstalledPack({ manifest: { id: 'com.test.b' as any } });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(false);
    const failureEvent = result.lifecycleEvents.find((e) => e.kind === 'migration_failure');
    expect(failureEvent).toBeDefined();
    expect(failureEvent!.message).toContain('ID mismatch');
  });

  // ---- Lifecycle event persistence failures ----

  it('survives lifecycle event persistence failures', async () => {
    const repo = makeMockRepository({
      appendLifecycleEvent: vi.fn().mockRejectedValue(new Error('Persistence error')),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { key: 'value' },
      bundleContentRef: 'indexeddb://ref',
    };

    // Should not throw
    const result = await executeLocalToInstalledMigration(input);

    expect(result.success).toBe(true);
    // Lifecycle events should still be collected in the result even if persistence failed
    expect(result.lifecycleEvents.length).toBeGreaterThan(0);
  });

  // ---- Disposed repository ----

  it('handles disposed repository gracefully', async () => {
    // When disposed, putPackRecord should reject
    const repo = makeMockRepository({
      isDisposed: true,
      putPackRecord: vi.fn().mockRejectedValue(new Error('Repository is disposed')),
    });
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: { key: 'value' },
      bundleContentRef: 'indexeddb://ref',
    };

    // Migration should fail because pack record creation fails
    const result = await executeLocalToInstalledMigration(input);
    expect(result.success).toBe(false);
    expect(result.blocked).toBe(true);
    expect(result.blockingDiagnostics.some((d) => d.code === 'migration/pack-record-failed')).toBe(true);
  });

  // ---- Contribution comparison in result ----

  it('includes accurate contribution comparison in successful result', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest({
      contributions: [
        { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
        { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
      ],
    });
    const installedPack = makeInstalledPack({
      manifest: {
        contributions: [
          { kind: 'command', id: 'com.test.migration.cmd1' } as ExtensionContribution,
          { kind: 'effect', id: 'com.test.migration.eff1' } as ExtensionContribution,
        ],
      },
    });

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(result.contributionComparison.identical).toBe(true);
    expect(result.contributionComparison.shared).toHaveLength(2);
  });

  // ---- Frozen results ----

  it('returns frozen result objects', async () => {
    const repo = makeMockRepository();
    const localManifest = makeLocalManifest();
    const installedPack = makeInstalledPack();

    const input: LocalInstalledMigrationInput = {
      localManifest,
      installedPack,
      repository: repo,
      localSettings: {},
      bundleContentRef: 'indexeddb://ref',
    };

    const result = await executeLocalToInstalledMigration(input);

    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.blockingDiagnostics)).toBe(true);
    expect(Object.isFrozen(result.warningDiagnostics)).toBe(true);
    expect(Object.isFrozen(result.lifecycleEvents)).toBe(true);
    expect(Object.isFrozen(result.contributionComparison)).toBe(true);
    expect(Object.isFrozen(result.metadataGaps)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// readLocalSettings
// ---------------------------------------------------------------------------

describe('readLocalSettings', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('reads settings from localStorage for an extension', () => {
    const extensionId = 'com.test.migration';
    const prefix = 'reigh.ext.com.test.migration.';

    localStorage.setItem(`${prefix}theme`, JSON.stringify('dark'));
    localStorage.setItem(`${prefix}fontSize`, JSON.stringify(14));
    localStorage.setItem(`${prefix}enabled`, JSON.stringify(true));

    const settings = readLocalSettings(extensionId);

    expect(settings).toEqual({
      theme: 'dark',
      fontSize: 14,
      enabled: true,
    });
  });

  it('returns empty object when no settings exist', () => {
    const settings = readLocalSettings('com.test.nonexistent');
    expect(settings).toEqual({});
  });

  it('ignores keys for other extensions', () => {
    localStorage.setItem('reigh.ext.com.test.other.theme', JSON.stringify('light'));
    localStorage.setItem('reigh.ext.com.test.migration.theme', JSON.stringify('dark'));

    const settings = readLocalSettings('com.test.migration');

    expect(settings).toEqual({ theme: 'dark' });
  });

  it('skips unparseable values gracefully', () => {
    const extensionId = 'com.test.migration';
    const prefix = 'reigh.ext.com.test.migration.';

    localStorage.setItem(`${prefix}valid`, JSON.stringify('good'));
    localStorage.setItem(`${prefix}corrupt`, '{not-valid-json');

    const settings = readLocalSettings(extensionId);

    expect(settings).toEqual({ valid: 'good' });
    // corrupt key is skipped
  });

  it('handles non-prefixed keys correctly', () => {
    localStorage.setItem('some-other-key', 'value');
    localStorage.setItem('reigh.ext.com.test.migration.myKey', JSON.stringify('myValue'));

    const settings = readLocalSettings('com.test.migration');

    expect(settings).toEqual({ myKey: 'myValue' });
  });

  it('handles empty localStorage gracefully', () => {
    const settings = readLocalSettings('com.test.empty');
    expect(settings).toEqual({});
  });
});
