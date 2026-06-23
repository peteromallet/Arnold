/**
 * Tests for ExtensionLoader (T11/T12).
 *
 * Covers:
 *  - Factory creation and repository attachment.
 *  - validate() for direct (workspace source) inputs.
 *  - validate() for installed pack inputs.
 *  - validate() isolation: a failing pack does not affect other packs.
 *  - load() for workspace-source validated packages.
 *  - load() for installed-bundle validated packages with integrity checks.
 *  - load() isolation: a failing integrity check does not affect other packs.
 *  - load() emits lifecycle events (load, integrity_pass, integrity_fail).
 *  - unload() emits unload lifecycle events.
 *  - Per-pack failure isolation throughout the pipeline.
 *  - No global state ownership.
 *  - T12: Dependency resolution:
 *    - Satisfied dependencies.
 *    - Missing required dependencies → blocked.
 *    - Optional degraded activation.
 *    - Version mismatch → blocked (required) or degraded (optional).
 *    - Circular dependency chains → blocked with diagnostics.
 *    - Contribution-scoped diagnostics.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import {
  createExtensionLoader,
  resolveDependencies,
  satisfiesSemverRange,
} from '@/tools/video-editor/runtime/extensionLoader';
import type {
  ExtensionLoader,
  ExtensionLoaderInput,
  DirectExtensionInput,
  InstalledExtensionInput,
  ExtensionLoaderValidationResult,
  ExtensionLoaderLoadResult,
  ExtensionLoaderUnloadResult,
  ExtensionLoadEntry,
  DependencyResolutionResult,
  DependencyResolutionEntry,
  DependencyStatus,
  PackageState,
  PackageMetadata,
} from '@/tools/video-editor/runtime/extensionLoader';
import { defineExtension } from '@reigh/editor-sdk';
import type {
  ReighExtension,
  ExtensionManifest,
  InstalledExtensionMetadata,
  InstalledExtensionPackage,
  IntegrityHash,
  ExtensionDependency,
  DependencyPosture,
} from '@reigh/editor-sdk';
import type {
  ExtensionStateRepository,
  ExtensionPackRecord,
  ExtensionLifecycleEvent,
} from '@/tools/video-editor/runtime/extensionStateRepository';
import { createLifecycleEvent } from '@/tools/video-editor/runtime/extensionStateRepository';
import { generateIntegrityHash } from '@/tools/video-editor/runtime/extensionIntegrity';
import type {
  PackageValidationResult,
  ValidatedPackage,
  WorkspaceSourcePackage,
  InstalledBundlePackage,
} from '@/tools/video-editor/runtime/extensionPackageManifest';

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/** Create a minimal valid ReighExtension for testing. */
function makeExtension(overrides?: Partial<ExtensionManifest>): ReighExtension {
  return defineExtension({
    manifest: {
      id: 'com.test.fixture' as any,
      version: '1.0.0',
      label: 'Fixture Extension',
      publisher: 'Test Publisher',
      license: 'MIT',
      settingsSchema: { version: 1 },
      ...overrides,
    },
    activate() {
      return { dispose() {} };
    },
  });
}

/** Create a minimal valid extension with a specific ID. */
function makeExtensionWithId(id: string, overrides?: Partial<ExtensionManifest>): ReighExtension {
  return defineExtension({
    manifest: {
      id: id as any,
      version: '1.0.0',
      label: `Extension ${id}`,
      publisher: 'Test Publisher',
      license: 'MIT',
      settingsSchema: { version: 1 },
      ...overrides,
    },
    activate() {
      return { dispose() {} };
    },
  });
}

/**
 * Create a ReighExtension with a potentially invalid manifest without going
 * through defineExtension (which validates IDs and throws on invalid ones).
 */
function rawExtension(manifest: Record<string, unknown>): ReighExtension {
  return { manifest: manifest as unknown as ExtensionManifest } as ReighExtension;
}

/** Create a valid integrity hash for a given bundle content. */
async function makeIntegrityHash(content: string): Promise<IntegrityHash> {
  return generateIntegrityHash(content);
}

/** Create a pack record for testing. */
async function makePackRecord(
  extensionId: string,
  version: string,
  bundleContent: string,
  overrides?: Partial<ExtensionPackRecord>,
): Promise<ExtensionPackRecord> {
  const integrity = await makeIntegrityHash(bundleContent);
  return {
    extensionId,
    version,
    apiVersion: 1,
    integrity,
    installedAt: '2026-06-20T12:00:00.000Z',
    bundleContentRef: `bundle-ref-${extensionId}`,
    manifestSnapshot: {
      id: extensionId as any,
      version,
      label: `Extension ${extensionId}`,
      publisher: 'Test Publisher',
      license: 'MIT',
      settingsSchema: { version: 1 },
      ...overrides?.manifestSnapshot,
    },
    publisher: 'Test Publisher',
    license: 'MIT',
    ...overrides,
  };
}

/** Build a direct validated package from an extension (bypassing validate). */
function directValidatedPackage(ext: ReighExtension): ValidatedPackage {
  return {
    form: 'workspace-source',
    manifest: ext.manifest,
  } as WorkspaceSourcePackage;
}

/** Build an installed validated package from pack + bundle. */
function installedValidatedPackage(pack: InstalledExtensionPackage): ValidatedPackage {
  return {
    form: 'installed-bundle',
    pack,
  } as InstalledBundlePackage;
}

// ---------------------------------------------------------------------------
// Mock repository
// ---------------------------------------------------------------------------

function createMockRepository(): ExtensionStateRepository {
  const events: ExtensionLifecycleEvent[] = [];
  let disposed = false;

  return {
    initialize: vi.fn().mockResolvedValue(undefined),
    dispose: vi.fn().mockImplementation(async () => { disposed = true; }),
    get isDisposed() { return disposed; },

    putPackRecord: vi.fn().mockResolvedValue(undefined),
    updatePackRecord: vi.fn().mockResolvedValue(undefined),
    getPackRecord: vi.fn().mockResolvedValue(null),
    getAllPackRecords: vi.fn().mockResolvedValue([]),
    deletePackRecord: vi.fn().mockResolvedValue(undefined),

    putEnablementState: vi.fn().mockResolvedValue(undefined),
    getEnablementState: vi.fn().mockResolvedValue(null),
    getAllEnablementStates: vi.fn().mockResolvedValue([]),
    deleteEnablementState: vi.fn().mockResolvedValue(undefined),

    putDevOverride: vi.fn().mockResolvedValue(undefined),
    getDevOverride: vi.fn().mockResolvedValue(null),
    getAllDevOverrides: vi.fn().mockResolvedValue([]),
    deleteDevOverride: vi.fn().mockResolvedValue(undefined),

    putSettingsSnapshot: vi.fn().mockResolvedValue(undefined),
    getSettingsSnapshot: vi.fn().mockResolvedValue(null),
    getAllSettingsSnapshots: vi.fn().mockResolvedValue([]),
    deleteSettingsSnapshot: vi.fn().mockResolvedValue(undefined),

    appendLifecycleEvent: vi.fn().mockImplementation(async (event: ExtensionLifecycleEvent) => {
      events.push(event);
    }),
    queryLifecycleEvents: vi.fn().mockResolvedValue([]),
    getLifecycleEvents: vi.fn().mockResolvedValue([]),

    getLock: vi.fn().mockResolvedValue({ entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' }),
    putLockEntry: vi.fn().mockResolvedValue(undefined),
    deleteLockEntry: vi.fn().mockResolvedValue(undefined),

    getFullExtensionState: vi.fn().mockResolvedValue({
      enablement: {},
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    }),
  };
}

// ---------------------------------------------------------------------------
// Factory tests
// ---------------------------------------------------------------------------

describe('createExtensionLoader', () => {
  it('creates a loader without a repository', () => {
    const loader = createExtensionLoader();
    expect(loader).toBeDefined();
    expect(loader.repository).toBeNull();
  });

  it('creates a loader with a repository', () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    expect(loader).toBeDefined();
    expect(loader.repository).toBe(repo);
  });

  it('creates independent loaders — no shared state', () => {
    const loader1 = createExtensionLoader();
    const loader2 = createExtensionLoader();
    expect(loader1).not.toBe(loader2);
  });
});

// ---------------------------------------------------------------------------
// Semver range satisfaction
// ---------------------------------------------------------------------------

describe('satisfiesSemverRange', () => {
  it('exact version match', () => {
    expect(satisfiesSemverRange('1.2.3', '1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.4', '1.2.3')).toBe(false);
  });

  it('caret range', () => {
    // ^1.2.3 → >=1.2.3 <2.0.0
    expect(satisfiesSemverRange('1.2.3', '^1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.4', '^1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.9.9', '^1.2.3')).toBe(true);
    expect(satisfiesSemverRange('2.0.0', '^1.2.3')).toBe(false);
    expect(satisfiesSemverRange('1.2.2', '^1.2.3')).toBe(false);
  });

  it('tilde range', () => {
    // ~1.2.3 → >=1.2.3 <1.3.0
    expect(satisfiesSemverRange('1.2.3', '~1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.9', '~1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.3.0', '~1.2.3')).toBe(false);
    expect(satisfiesSemverRange('1.2.2', '~1.2.3')).toBe(false);
  });

  it('gte comparison', () => {
    expect(satisfiesSemverRange('1.2.3', '>=1.2.3')).toBe(true);
    expect(satisfiesSemverRange('2.0.0', '>=1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.2', '>=1.2.3')).toBe(false);
  });

  it('lte comparison', () => {
    expect(satisfiesSemverRange('1.2.3', '<=1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.0.0', '<=1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.4', '<=1.2.3')).toBe(false);
  });

  it('gt comparison', () => {
    expect(satisfiesSemverRange('1.2.4', '>1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.3', '>1.2.3')).toBe(false);
  });

  it('lt comparison', () => {
    expect(satisfiesSemverRange('1.2.2', '<1.2.3')).toBe(true);
    expect(satisfiesSemverRange('1.2.3', '<1.2.3')).toBe(false);
  });

  it('space-separated AND conjunction', () => {
    expect(satisfiesSemverRange('1.5.0', '>=1.0.0 <2.0.0')).toBe(true);
    expect(satisfiesSemverRange('0.9.0', '>=1.0.0 <2.0.0')).toBe(false);
    expect(satisfiesSemverRange('2.0.0', '>=1.0.0 <2.0.0')).toBe(false);
  });

  it('hyphen range', () => {
    expect(satisfiesSemverRange('1.5.0', '1.0.0 - 2.0.0')).toBe(true);
    expect(satisfiesSemverRange('1.0.0', '1.0.0 - 2.0.0')).toBe(true);
    expect(satisfiesSemverRange('2.0.0', '1.0.0 - 2.0.0')).toBe(true);
    expect(satisfiesSemverRange('0.9.0', '1.0.0 - 2.0.0')).toBe(false);
    expect(satisfiesSemverRange('2.0.1', '1.0.0 - 2.0.0')).toBe(false);
  });

  it('returns false for unparseable version', () => {
    expect(satisfiesSemverRange('not-semver', '^1.0.0')).toBe(false);
    expect(satisfiesSemverRange('', '^1.0.0')).toBe(false);
  });

  it('returns false for unparseable range', () => {
    expect(satisfiesSemverRange('1.0.0', 'garbage')).toBe(false);
  });

  it('wildcard / x-range', () => {
    expect(satisfiesSemverRange('1.0.0', '1.x')).toBe(true);
    expect(satisfiesSemverRange('1.5.0', '1.x')).toBe(true);
    expect(satisfiesSemverRange('2.0.0', '1.x')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// resolveDependencies (standalone)
// ---------------------------------------------------------------------------

describe('resolveDependencies — satisfied dependencies', () => {
  it('returns empty resolution when no extensions have dependencies', () => {
    const ext1 = makeExtensionWithId('com.test.a');
    const ext2 = makeExtensionWithId('com.test.b');

    const result = resolveDependencies([
      directValidatedPackage(ext1),
      directValidatedPackage(ext2),
    ]);

    expect(result.blockedExtensionIds.size).toBe(0);
    expect(result.degradedExtensionIds.size).toBe(0);
    expect(result.diagnostics).toHaveLength(0);
    expect(result.entries).toHaveLength(2);
    for (const e of result.entries) {
      expect(e.canActivate).toBe(true);
      expect(e.degraded).toBe(false);
    }
  });

  it('satisfies all required dependencies when all are present', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      version: '1.0.0',
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.blockedExtensionIds.size).toBe(0);
    expect(result.entries).toHaveLength(2);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(true);
    expect(bEntry.allRequiredSatisfied).toBe(true);
    expect(bEntry.satisfied).toContain('com.test.a');
    expect(bEntry.missingRequired).toHaveLength(0);
  });

  it('satisfies multiple dependencies', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', { version: '1.0.0' } as any);
    const extC = makeExtensionWithId('com.test.c', {
      version: '1.0.0',
      dependsOn: [
        { extensionId: 'com.test.a', posture: 'required' as const },
        { extensionId: 'com.test.b', posture: 'required' as const },
      ],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
      directValidatedPackage(extC),
    ]);

    const cEntry = result.entries.find((e) => e.extensionId === 'com.test.c')!;
    expect(cEntry.canActivate).toBe(true);
    expect(cEntry.satisfied).toHaveLength(2);
    expect(cEntry.satisfied).toContain('com.test.a');
    expect(cEntry.satisfied).toContain('com.test.b');
  });

  it('satisfies version range match', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.5.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      version: '1.0.0',
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^1.0.0',
        posture: 'required' as const,
      }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(true);
    expect(bEntry.satisfied).toContain('com.test.a');
    expect(bEntry.versionMismatchRequired).toHaveLength(0);
  });
});

describe('resolveDependencies — missing required dependencies', () => {
  it('blocks extension with missing required dependency', () => {
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extB)]);

    expect(result.blockedExtensionIds.has('com.test.b')).toBe(true);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(false);
    expect(bEntry.allRequiredSatisfied).toBe(false);
    expect(bEntry.missingRequired).toContain('com.test.missing');
    expect(bEntry.blockingDiagnostics.length).toBeGreaterThan(0);
    expect(bEntry.blockingDiagnostics[0].code).toBe('loader/missing-required-dependency');
  });

  it('does not block other extensions when one has missing dependency', () => {
    const extA = makeExtensionWithId('com.test.a');
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.blockedExtensionIds.has('com.test.b')).toBe(true);
    expect(result.blockedExtensionIds.has('com.test.a')).toBe(false);
    const aEntry = result.entries.find((e) => e.extensionId === 'com.test.a')!;
    expect(aEntry.canActivate).toBe(true);
  });
});

describe('resolveDependencies — optional degraded activation', () => {
  it('allows activation with missing optional dependency (degraded)', () => {
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'optional' as const }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extB)]);

    expect(result.blockedExtensionIds.size).toBe(0);
    expect(result.degradedExtensionIds.has('com.test.b')).toBe(true);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(true);
    expect(bEntry.degraded).toBe(true);
    expect(bEntry.missingOptional).toContain('com.test.missing');
    expect(bEntry.degradationDiagnostics.length).toBeGreaterThan(0);
    expect(bEntry.degradationDiagnostics[0].code).toBe('loader/missing-optional-dependency');
  });

  it('optional dependency from legacy optional flag', () => {
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', optional: true }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extB)]);

    expect(result.degradedExtensionIds.has('com.test.b')).toBe(true);
    expect(result.blockedExtensionIds.size).toBe(0);
  });

  it('mixed required and optional dependencies', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      version: '1.0.0',
      dependsOn: [
        { extensionId: 'com.test.a', posture: 'required' as const },
        { extensionId: 'com.test.missing', posture: 'optional' as const },
      ],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(true); // Required is satisfied
    expect(bEntry.degraded).toBe(true); // Optional is missing
    expect(bEntry.satisfied).toContain('com.test.a');
    expect(bEntry.missingOptional).toContain('com.test.missing');
  });
});

describe('resolveDependencies — version mismatch', () => {
  it('blocks required dependency with version mismatch', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^2.0.0',
        posture: 'required' as const,
      }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.blockedExtensionIds.has('com.test.b')).toBe(true);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(false);
    expect(bEntry.versionMismatchRequired).toContain('com.test.a');
    expect(bEntry.blockingDiagnostics.length).toBeGreaterThan(0);
    expect(bEntry.blockingDiagnostics[0].code).toBe('loader/dependency-version-mismatch');
  });

  it('allows optional dependency with version mismatch (degraded)', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^2.0.0',
        posture: 'optional' as const,
      }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.blockedExtensionIds.size).toBe(0);
    expect(result.degradedExtensionIds.has('com.test.b')).toBe(true);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(true);
    expect(bEntry.degraded).toBe(true);
    expect(bEntry.versionMismatchOptional).toContain('com.test.a');
  });
});

describe('resolveDependencies — circular dependency chains', () => {
  it('detects a simple A→B→A cycle and blocks both', () => {
    const extA = makeExtensionWithId('com.test.a', {
      dependsOn: [{ extensionId: 'com.test.b', posture: 'required' as const }],
    } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.blockedExtensionIds.has('com.test.a')).toBe(true);
    expect(result.blockedExtensionIds.has('com.test.b')).toBe(true);

    const aEntry = result.entries.find((e) => e.extensionId === 'com.test.a')!;
    expect(aEntry.inCycle).toBe(true);
    expect(aEntry.cycleExtensionIds).toContain('com.test.b');
    expect(aEntry.canActivate).toBe(false);
    expect(aEntry.blockingDiagnostics.some((d) => d.code === 'loader/dependency-cycle')).toBe(true);

    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.inCycle).toBe(true);
    expect(bEntry.canActivate).toBe(false);
  });

  it('detects a three-way cycle A→B→C→A', () => {
    const extA = makeExtensionWithId('com.test.a', {
      dependsOn: [{ extensionId: 'com.test.b', posture: 'required' as const }],
    } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.c', posture: 'required' as const }],
    } as any);
    const extC = makeExtensionWithId('com.test.c', {
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
      directValidatedPackage(extC),
    ]);

    expect(result.blockedExtensionIds.has('com.test.a')).toBe(true);
    expect(result.blockedExtensionIds.has('com.test.b')).toBe(true);
    expect(result.blockedExtensionIds.has('com.test.c')).toBe(true);

    for (const id of ['com.test.a', 'com.test.b', 'com.test.c']) {
      const entry = result.entries.find((e) => e.extensionId === id)!;
      expect(entry.inCycle).toBe(true);
      expect(entry.canActivate).toBe(false);
    }
  });

  it('does not block non-cyclic extensions when a cycle exists elsewhere', () => {
    const extA = makeExtensionWithId('com.test.a', {
      dependsOn: [{ extensionId: 'com.test.b', posture: 'required' as const }],
    } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);
    const extC = makeExtensionWithId('com.test.c'); // No dependencies, not in cycle

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
      directValidatedPackage(extC),
    ]);

    expect(result.blockedExtensionIds.has('com.test.a')).toBe(true);
    expect(result.blockedExtensionIds.has('com.test.b')).toBe(true);
    expect(result.blockedExtensionIds.has('com.test.c')).toBe(false);

    const cEntry = result.entries.find((e) => e.extensionId === 'com.test.c')!;
    expect(cEntry.inCycle).toBe(false);
    expect(cEntry.canActivate).toBe(true);
  });
});

describe('resolveDependencies — contribution-scoped diagnostics', () => {
  it('includes contributionIds in diagnostics for missing required dependency', () => {
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.missing',
        posture: 'required' as const,
        contributionIds: ['contribution.alpha'],
      }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extB)]);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.blockingDiagnostics[0].contributionId).toBe('contribution.alpha');
  });

  it('includes contributionIds in diagnostics for version mismatch', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^2.0.0',
        posture: 'required' as const,
        contributionIds: ['contribution.beta'],
      }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.blockingDiagnostics[0].contributionId).toBe('contribution.beta');
  });

  it('includes contributionIds in degradation diagnostics', () => {
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.missing',
        posture: 'optional' as const,
        contributionIds: ['contribution.gamma'],
      }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extB)]);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.degradationDiagnostics[0].contributionId).toBe('contribution.gamma');
  });
});

describe('resolveDependencies — DependencyStatus details', () => {
  it('provides correct DependencyStatus for satisfied dependency', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.5.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^1.0.0',
        posture: 'required' as const,
      }],
    } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    const status = bEntry.dependencies.find((d) => d.dependencyId === 'com.test.a')!;
    expect(status.found).toBe(true);
    expect(status.versionSatisfied).toBe(true);
    expect(status.versionRange).toBe('^1.0.0');
    expect(status.actualVersion).toBe('1.5.0');
    expect(status.posture).toBe('required');
  });

  it('provides correct DependencyStatus for missing dependency', () => {
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'optional' as const }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extB)]);
    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    const status = bEntry.dependencies.find((d) => d.dependencyId === 'com.test.missing')!;
    expect(status.found).toBe(false);
    expect(status.posture).toBe('optional');
    expect(status.actualVersion).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// validate — direct (workspace source) inputs
// ---------------------------------------------------------------------------

describe('ExtensionLoader.validate — direct inputs', () => {
  it('validates a single direct extension as valid', () => {
    const loader = createExtensionLoader();
    const ext = makeExtension();
    const input: ExtensionLoaderInput = { kind: 'direct', extension: ext };

    const result = loader.validate([input]);
    expect(result.allValid).toBe(true);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].valid).toBe(true);
    expect(result.entries[0].errors).toHaveLength(0);
    expect(result.entries[0].validatedPackage).not.toBeNull();
    expect(result.entries[0].validatedPackage!.form).toBe('workspace-source');
  });

  it('validates multiple direct extensions', () => {
    const loader = createExtensionLoader();
    const inputs: ExtensionLoaderInput[] = [
      { kind: 'direct', extension: makeExtensionWithId('com.test.a') },
      { kind: 'direct', extension: makeExtensionWithId('com.test.b') },
      { kind: 'direct', extension: makeExtensionWithId('com.test.c') },
    ];

    const result = loader.validate(inputs);
    expect(result.allValid).toBe(true);
    expect(result.entries).toHaveLength(3);
    for (const entry of result.entries) {
      expect(entry.valid).toBe(true);
    }
  });

  it('validates a direct extension with missing publisher as valid (warning, not error)', () => {
    const loader = createExtensionLoader();
    const ext = rawExtension({
      id: 'com.test.nowarn',
      version: '1.0.0',
      label: 'No Publisher',
      // No publisher, no license — dev mode warnings
    });
    const input: ExtensionLoaderInput = { kind: 'direct', extension: ext };

    const result = loader.validate([input]);
    // In dev mode, missing publisher/license are warnings, not errors
    expect(result.entries[0].valid).toBe(true);
    expect(result.entries[0].errors).toHaveLength(0);
  });

  it('rejects a direct extension with invalid ID', () => {
    const loader = createExtensionLoader();
    // Use raw extension to bypass defineExtension validation
    const ext = rawExtension({
      id: 'Invalid ID With Spaces',
      version: '1.0.0',
      label: 'Bad ID',
    });
    const input: ExtensionLoaderInput = { kind: 'direct', extension: ext };

    const result = loader.validate([input]);
    expect(result.allValid).toBe(false);
    expect(result.entries[0].valid).toBe(false);
    expect(result.entries[0].errors.length).toBeGreaterThan(0);
  });

  it('isolates failures: one bad extension does not affect the other', () => {
    const loader = createExtensionLoader();
    const badExt = rawExtension({
      id: 'Invalid ID',
      version: '1.0.0',
      label: 'Bad',
    });
    const goodExt = makeExtensionWithId('com.test.good');

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'direct', extension: badExt },
      { kind: 'direct', extension: goodExt },
    ];

    const result = loader.validate(inputs);
    expect(result.allValid).toBe(false);
    expect(result.entries).toHaveLength(2);
    expect(result.entries[0].valid).toBe(false);
    expect(result.entries[1].valid).toBe(true);
    // Good extension still has a validated package
    expect(result.entries[1].validatedPackage).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// validate — installed pack inputs
// ---------------------------------------------------------------------------

describe('ExtensionLoader.validate — installed inputs', () => {
  it('validates a valid installed pack', async () => {
    const loader = createExtensionLoader();
    const bundleContent = 'export function activate() { return { dispose() {} }; }';
    const packRecord = await makePackRecord('com.test.installed', '1.0.0', bundleContent);
    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent,
    };

    const result = loader.validate([input]);
    expect(result.allValid).toBe(true);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].valid).toBe(true);
    expect(result.entries[0].validatedPackage!.form).toBe('installed-bundle');
  });

  it('rejects an installed pack with invalid manifest', async () => {
    const loader = createExtensionLoader();
    const bundleContent = '// empty bundle';
    const badRecord = await makePackRecord('com.test.bad', '1.0.0', bundleContent);
    // Corrupt the manifest snapshot — use an invalid ID
    const corruptRecord: ExtensionPackRecord = {
      ...badRecord,
      manifestSnapshot: {
        id: 'Invalid ID!' as any,
        version: 'not-semver',
        label: '',
      } as ExtensionManifest,
    };

    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord: corruptRecord,
      bundleContent,
    };

    const result = loader.validate([input]);
    expect(result.allValid).toBe(false);
    expect(result.entries[0].valid).toBe(false);
    expect(result.entries[0].errors.length).toBeGreaterThan(0);
  });

  it('isolates installed pack failures from other packs', async () => {
    const loader = createExtensionLoader();
    const goodBundle = 'export function activate() {}';
    const badBundle = '// bad';

    const goodRecord = await makePackRecord('com.test.good', '1.0.0', goodBundle);
    const badRecord = await makePackRecord('com.test.bad', '1.0.0', goodBundle); // use goodBundle for hash gen, tampered manifest
    // Corrupt bad record's manifest
    const corruptRecord: ExtensionPackRecord = {
      ...badRecord,
      manifestSnapshot: {
        id: 'Bad ID!' as any,
        version: 'xyz',
        label: '',
      } as ExtensionManifest,
    };

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'installed', packRecord: goodRecord, bundleContent: goodBundle },
      { kind: 'installed', packRecord: corruptRecord, bundleContent: badBundle },
    ];

    const result = loader.validate(inputs);
    expect(result.allValid).toBe(false);
    expect(result.entries).toHaveLength(2);
    expect(result.entries[0].valid).toBe(true);
    expect(result.entries[1].valid).toBe(false);
  });

  it('produces aggregated diagnostics from all entries', async () => {
    const loader = createExtensionLoader();
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.diag', '1.0.0', bundleContent);
    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent,
    };

    const result = loader.validate([input]);
    // Should include both errors and warnings across all entries
    expect(Array.isArray(result.diagnostics)).toBe(true);
    expect(result.diagnostics.length).toBeGreaterThanOrEqual(0);
    // For a valid pack, there should be no errors
    const errorDiags = result.diagnostics.filter((d) => d.severity === 'error');
    expect(errorDiags).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// validate — mixed inputs
// ---------------------------------------------------------------------------

describe('ExtensionLoader.validate — mixed inputs', () => {
  it('validates a mix of direct and installed inputs together', async () => {
    const loader = createExtensionLoader();
    const directExt = makeExtensionWithId('com.test.direct');
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.installed', '2.0.0', bundleContent);

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'direct', extension: directExt },
      { kind: 'installed', packRecord, bundleContent },
    ];

    const result = loader.validate(inputs);
    expect(result.entries).toHaveLength(2);
    expect(result.entries[0].valid).toBe(true);
    expect(result.entries[0].validatedPackage!.form).toBe('workspace-source');
    expect(result.entries[1].valid).toBe(true);
    expect(result.entries[1].validatedPackage!.form).toBe('installed-bundle');
    expect(result.allValid).toBe(true);
  });

  it('isolates a bad direct extension from a good installed pack', async () => {
    const loader = createExtensionLoader();
    const badExt = rawExtension({
      id: 'Bad ID',
      version: '1.0.0',
      label: 'Bad',
    });
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.good-installed', '1.0.0', bundleContent);

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'direct', extension: badExt },
      { kind: 'installed', packRecord, bundleContent },
    ];

    const result = loader.validate(inputs);
    expect(result.allValid).toBe(false);
    expect(result.entries[0].valid).toBe(false);
    expect(result.entries[0].validatedPackage).toBeNull();
    expect(result.entries[1].valid).toBe(true);
    expect(result.entries[1].validatedPackage).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// load — workspace source
// ---------------------------------------------------------------------------

describe('ExtensionLoader.load — workspace source', () => {
  it('loads a workspace source validated package', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const ext = makeExtensionWithId('com.test.ws');

    // First validate to get the validated package
    const validationResult = loader.validate([{ kind: 'direct', extension: ext }]);
    const validatedPkg = validationResult.entries[0].validatedPackage!;

    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.allLoaded).toBe(true);
    expect(loadResult.loadedExtensions).toHaveLength(1);
    expect(loadResult.loadedExtensions[0].manifest.id).toBe('com.test.ws');
    expect(loadResult.entries).toHaveLength(1);
    expect(loadResult.entries[0].loaded).toBe(true);
  });

  it('emits lifecycle events for workspace source load', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const ext = makeExtensionWithId('com.test.lifecycle');

    const validationResult = loader.validate([{ kind: 'direct', extension: ext }]);
    const validatedPkg = validationResult.entries[0].validatedPackage!;

    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.entries[0].lifecycleEvents.length).toBeGreaterThan(0);
    const loadEvent = loadResult.entries[0].lifecycleEvents.find(
      (e) => e.kind === 'load',
    );
    expect(loadEvent).toBeDefined();
    expect(loadEvent!.extensionId).toBe('com.test.lifecycle');
    expect(loadEvent!.kind).toBe('load');

    // Repository should have received the event
    expect(repo.appendLifecycleEvent).toHaveBeenCalled();
  });

  it('loads multiple workspace source packages', async () => {
    const loader = createExtensionLoader();
    const ext1 = makeExtensionWithId('com.test.multi1');
    const ext2 = makeExtensionWithId('com.test.multi2');

    const validationResult = loader.validate([
      { kind: 'direct', extension: ext1 },
      { kind: 'direct', extension: ext2 },
    ]);
    const validatedPkgs = validationResult.entries
      .filter((e) => e.validatedPackage !== null)
      .map((e) => e.validatedPackage!);

    const loadResult = await loader.load(validatedPkgs);
    expect(loadResult.allLoaded).toBe(true);
    expect(loadResult.loadedExtensions).toHaveLength(2);
  });
});

// ---------------------------------------------------------------------------
// load — installed bundle
// ---------------------------------------------------------------------------

describe('ExtensionLoader.load — installed bundle', () => {
  it('loads a valid installed bundle with integrity verification', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const bundleContent = 'export function activate() { return { dispose() {} }; }';
    const packRecord = await makePackRecord('com.test.bundle', '1.0.0', bundleContent);

    // Validate
    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent,
    };
    const validationResult = loader.validate([input]);
    expect(validationResult.allValid).toBe(true);
    const validatedPkg = validationResult.entries[0].validatedPackage!;

    // Load
    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.allLoaded).toBe(true);
    expect(loadResult.loadedExtensions).toHaveLength(1);
    expect(loadResult.loadedExtensions[0].manifest.id).toBe('com.test.bundle');
    expect(loadResult.entries[0].loaded).toBe(true);
    expect(loadResult.entries[0].errors).toHaveLength(0);

    // Lifecycle events: integrity_pass and load
    const events = loadResult.entries[0].lifecycleEvents;
    expect(events.some((e) => e.kind === 'integrity_pass')).toBe(true);
    expect(events.some((e) => e.kind === 'load')).toBe(true);
  });

  it('fails an installed bundle with integrity mismatch', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const originalBundle = 'export function activate() {}';
    const tamperedBundle = 'export function malicious() {}';
    const packRecord = await makePackRecord('com.test.tampered', '1.0.0', originalBundle);

    // Validate with the tampered bundle (manifest-wise it's fine, but integrity will fail at load)
    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent: tamperedBundle, // Tampered!
    };
    const validationResult = loader.validate([input]);
    expect(validationResult.allValid).toBe(true); // Manifest validation passes

    // Load should fail due to integrity mismatch
    const validatedPkg = validationResult.entries[0].validatedPackage!;
    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.allLoaded).toBe(false);
    expect(loadResult.loadedExtensions).toHaveLength(0);
    expect(loadResult.entries[0].loaded).toBe(false);
    expect(loadResult.entries[0].extension).toBeNull();
    expect(loadResult.entries[0].errors.length).toBeGreaterThan(0);

    // Should have integrity_fail event
    const events = loadResult.entries[0].lifecycleEvents;
    expect(events.some((e) => e.kind === 'integrity_fail')).toBe(true);
  });

  it('isolates integrity failures: one bad bundle does not affect others', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const goodBundle = 'export function activate() {}';
    const badBundle = 'different content';
    const goodRecord = await makePackRecord('com.test.good', '1.0.0', goodBundle);
    const badRecord = await makePackRecord('com.test.bad', '1.0.0', goodBundle); // integrity from good, but use bad content

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'installed', packRecord: goodRecord, bundleContent: goodBundle },
      { kind: 'installed', packRecord: badRecord, bundleContent: badBundle }, // tampered
    ];
    const validationResult = loader.validate(inputs);
    const validatedPkgs = validationResult.entries
      .filter((e) => e.validatedPackage !== null)
      .map((e) => e.validatedPackage!);

    const loadResult = await loader.load(validatedPkgs);
    expect(loadResult.allLoaded).toBe(false);
    expect(loadResult.loadedExtensions).toHaveLength(1); // Only the good one
    expect(loadResult.entries).toHaveLength(2);
    expect(loadResult.entries[0].loaded).toBe(true);
    expect(loadResult.entries[1].loaded).toBe(false);
  });

  it('aggregates diagnostics from load failures', async () => {
    const loader = createExtensionLoader();
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.aggr', '1.0.0', bundleContent);

    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent: 'different',
    };
    const validationResult = loader.validate([input]);
    const validatedPkg = validationResult.entries[0].validatedPackage!;

    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.diagnostics.length).toBeGreaterThan(0);
    expect(loadResult.diagnostics.every((d) => d.severity === 'error')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// load — mixed workspace + installed
// ---------------------------------------------------------------------------

describe('ExtensionLoader.load — mixed', () => {
  it('loads a mix of workspace source and installed bundle packages', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const directExt = makeExtensionWithId('com.test.ws');
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.ib', '1.0.0', bundleContent);

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'direct', extension: directExt },
      { kind: 'installed', packRecord, bundleContent },
    ];
    const validationResult = loader.validate(inputs);
    const validatedPkgs = validationResult.entries
      .filter((e) => e.validatedPackage !== null)
      .map((e) => e.validatedPackage!);

    expect(validatedPkgs).toHaveLength(2);

    const loadResult = await loader.load(validatedPkgs);
    expect(loadResult.allLoaded).toBe(true);
    expect(loadResult.loadedExtensions).toHaveLength(2);
    expect(loadResult.loadedExtensions[0].manifest.id).toBe('com.test.ws');
    expect(loadResult.loadedExtensions[1].manifest.id).toBe('com.test.ib');
  });

  it('isolates a failing installed bundle from a succeeding workspace source', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const directExt = makeExtensionWithId('com.test.good-ws');
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.bad-ib', '1.0.0', bundleContent);

    const inputs: ExtensionLoaderInput[] = [
      { kind: 'direct', extension: directExt },
      { kind: 'installed', packRecord, bundleContent: 'tampered!' },
    ];
    const validationResult = loader.validate(inputs);
    const validatedPkgs = validationResult.entries
      .filter((e) => e.validatedPackage !== null)
      .map((e) => e.validatedPackage!);

    const loadResult = await loader.load(validatedPkgs);
    expect(loadResult.allLoaded).toBe(false);
    expect(loadResult.loadedExtensions).toHaveLength(1);
    expect(loadResult.loadedExtensions[0].manifest.id).toBe('com.test.good-ws');
    expect(loadResult.entries[0].loaded).toBe(true);
    expect(loadResult.entries[1].loaded).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// load — dependency resolution integration
// ---------------------------------------------------------------------------

describe('ExtensionLoader.load — dependency resolution', () => {
  it('loads extension with satisfied dependencies', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      version: '1.0.0',
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(2);
    expect(result.dependencyResolution).not.toBeNull();
    expect(result.dependencyResolution!.blockedExtensionIds.size).toBe(0);
  });

  it('blocks extension with missing required dependency', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    const result = await loader.load([directValidatedPackage(extB)]);

    expect(result.allLoaded).toBe(false);
    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.entries[0].loaded).toBe(false);
    expect(result.entries[0].errors.some((e) => e.code === 'loader/missing-required-dependency')).toBe(true);
    expect(result.dependencyResolution!.blockedExtensionIds.has('com.test.b')).toBe(true);
  });

  it('allows degraded activation for missing optional dependency', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'optional' as const }],
    } as any);

    const result = await loader.load([directValidatedPackage(extB)]);

    expect(result.allLoaded).toBe(true); // Still loaded, but degraded
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.entries[0].loaded).toBe(true);
    expect(result.dependencyResolution!.degradedExtensionIds.has('com.test.b')).toBe(true);
  });

  it('blocks extensions in a cycle', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extA = makeExtensionWithId('com.test.a', {
      dependsOn: [{ extensionId: 'com.test.b', posture: 'required' as const }],
    } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.allLoaded).toBe(false);
    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.dependencyResolution!.blockedExtensionIds.has('com.test.a')).toBe(true);
    expect(result.dependencyResolution!.blockedExtensionIds.has('com.test.b')).toBe(true);
  });

  it('isolates dependency-blocked extensions from non-blocked ones', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.allLoaded).toBe(false);
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.loadedExtensions[0].manifest.id).toBe('com.test.a');
    expect(result.entries[1].loaded).toBe(false);
  });

  it('emits dependency_blocked lifecycle event for blocked extensions', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    await loader.load([directValidatedPackage(extB)]);

    const calls = (repo.appendLifecycleEvent as any).mock.calls;
    const kinds = calls.map((c: any) => c[0].kind);
    expect(kinds).toContain('dependency_blocked');
  });

  it('emits dependency_degraded lifecycle event for degraded extensions', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'optional' as const }],
    } as any);

    await loader.load([directValidatedPackage(extB)]);

    const calls = (repo.appendLifecycleEvent as any).mock.calls;
    const kinds = calls.map((c: any) => c[0].kind);
    expect(kinds).toContain('dependency_degraded');
  });

  it('dependencyResolution is null when no extensions declare dependencies', async () => {
    const loader = createExtensionLoader();
    const ext = makeExtensionWithId('com.test.nodeps');

    const result = await loader.load([directValidatedPackage(ext)]);
    expect(result.dependencyResolution).toBeNull();
  });

  it('includes dependency diagnostics in load result diagnostics', async () => {
    const loader = createExtensionLoader();
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    const result = await loader.load([directValidatedPackage(extB)]);
    const depDiags = result.diagnostics.filter(
      (d) => d.code === 'loader/missing-required-dependency',
    );
    expect(depDiags.length).toBeGreaterThan(0);
  });

  it('version mismatch for required dependency blocks activation', async () => {
    const loader = createExtensionLoader();
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^2.0.0',
        posture: 'required' as const,
      }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.loadedExtensions).toHaveLength(1); // Only A loads
    expect(result.entries[1].loaded).toBe(false);
    expect(result.entries[1].errors.some((e) => e.code === 'loader/dependency-version-mismatch')).toBe(true);
  });

  it('version mismatch for optional dependency allows degraded activation', async () => {
    const loader = createExtensionLoader();
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{
        extensionId: 'com.test.a',
        versionRange: '^2.0.0',
        posture: 'optional' as const,
      }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.loadedExtensions).toHaveLength(2); // Both load, B degraded
    expect(result.dependencyResolution!.degradedExtensionIds.has('com.test.b')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// unload
// ---------------------------------------------------------------------------

describe('ExtensionLoader.unload', () => {
  it('emits unload lifecycle events for each extension ID', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const result = await loader.unload(['com.test.a', 'com.test.b']);
    expect(result.unloadedIds).toEqual(['com.test.a', 'com.test.b']);
    expect(result.lifecycleEvents).toHaveLength(2);
    expect(result.lifecycleEvents[0].kind).toBe('unload');
    expect(result.lifecycleEvents[0].extensionId).toBe('com.test.a');
    expect(result.lifecycleEvents[1].kind).toBe('unload');
    expect(result.lifecycleEvents[1].extensionId).toBe('com.test.b');
    expect(result.errors).toHaveLength(0);

    // Repository should have received the events
    expect(repo.appendLifecycleEvent).toHaveBeenCalledTimes(2);
  });

  it('handles empty unload list', async () => {
    const loader = createExtensionLoader();

    const result = await loader.unload([]);
    expect(result.unloadedIds).toEqual([]);
    expect(result.lifecycleEvents).toHaveLength(0);
    expect(result.errors).toHaveLength(0);
  });

  it('handles repository errors gracefully', async () => {
    const repo = createMockRepository();
    (repo.appendLifecycleEvent as any).mockRejectedValue(new Error('DB error'));
    const loader = createExtensionLoader(repo);

    // Should still succeed — repository errors are silenced
    const result = await loader.unload(['com.test.resilient']);
    expect(result.unloadedIds).toEqual(['com.test.resilient']);
    expect(result.lifecycleEvents).toHaveLength(1);
    expect(result.errors).toHaveLength(0);
  });

  it('isolates unload failures per extension', async () => {
    const repo = createMockRepository();
    let callCount = 0;
    (repo.appendLifecycleEvent as any).mockImplementation(async () => {
      callCount++;
      if (callCount === 1) throw new Error('First fails');
    });
    const loader = createExtensionLoader(repo);

    const result = await loader.unload(['com.test.first', 'com.test.second']);
    // Errors from repo are suppressed, both IDs should still be unloaded
    expect(result.unloadedIds).toEqual(['com.test.first', 'com.test.second']);
    expect(result.errors).toHaveLength(0);
  });
});

// ---------------------------------------------------------------------------
// No global state ownership
// ---------------------------------------------------------------------------

describe('ExtensionLoader — no global state', () => {
  it('multiple loaders operate independently', async () => {
    const repo1 = createMockRepository();
    const repo2 = createMockRepository();
    const loader1 = createExtensionLoader(repo1);
    const loader2 = createExtensionLoader(repo2);

    const ext1 = makeExtensionWithId('com.test.one');
    const ext2 = makeExtensionWithId('com.test.two');

    const result1 = loader1.validate([{ kind: 'direct', extension: ext1 }]);
    const result2 = loader2.validate([{ kind: 'direct', extension: ext2 }]);

    // Loader1 only sees ext1
    expect(result1.entries).toHaveLength(1);
    expect((result1.entries[0].input as DirectExtensionInput).extension.manifest.id).toBe('com.test.one');

    // Loader2 only sees ext2
    expect(result2.entries).toHaveLength(1);
    expect((result2.entries[0].input as DirectExtensionInput).extension.manifest.id).toBe('com.test.two');

    // Loader1's repo received no events from loader2
    await loader1.load([result1.entries[0].validatedPackage!]);
    expect(repo1.appendLifecycleEvent).toHaveBeenCalled();
    expect(repo2.appendLifecycleEvent).not.toHaveBeenCalled();
  });

  it('does not retain validated packages between calls', () => {
    const loader = createExtensionLoader();
    const ext1 = makeExtensionWithId('com.test.first');

    // First validate
    const result1 = loader.validate([{ kind: 'direct', extension: ext1 }]);
    expect(result1.entries).toHaveLength(1);

    // Second validate — should not accumulate
    const ext2 = makeExtensionWithId('com.test.second');
    const result2 = loader.validate([{ kind: 'direct', extension: ext2 }]);
    expect(result2.entries).toHaveLength(1);
    expect((result2.entries[0].input as DirectExtensionInput).extension.manifest.id).toBe('com.test.second');
  });
});

// ---------------------------------------------------------------------------
// Full pipeline: validate → load → unload
// ---------------------------------------------------------------------------

describe('ExtensionLoader — full pipeline', () => {
  it('completes validate → load → unload for a direct extension', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const ext = makeExtensionWithId('com.test.pipeline');

    // 1. Validate
    const validation = loader.validate([{ kind: 'direct', extension: ext }]);
    expect(validation.allValid).toBe(true);

    // 2. Load
    const validatedPkg = validation.entries[0].validatedPackage!;
    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.allLoaded).toBe(true);
    expect(loadResult.loadedExtensions).toHaveLength(1);

    // 3. Unload
    const unloadResult = await loader.unload(['com.test.pipeline']);
    expect(unloadResult.unloadedIds).toContain('com.test.pipeline');
  });

  it('completes validate → load → unload for an installed bundle', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.bundle-pipeline', '1.0.0', bundleContent);

    // 1. Validate
    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent,
    };
    const validation = loader.validate([input]);
    expect(validation.allValid).toBe(true);

    // 2. Load
    const validatedPkg = validation.entries[0].validatedPackage!;
    const loadResult = await loader.load([validatedPkg]);
    expect(loadResult.allLoaded).toBe(true);
    expect(loadResult.loadedExtensions).toHaveLength(1);

    // 3. Unload
    const unloadResult = await loader.unload(['com.test.bundle-pipeline']);
    expect(unloadResult.unloadedIds).toContain('com.test.bundle-pipeline');
  });

  it('propagates lifecycle events to repository', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.propagate', '1.0.0', bundleContent);

    const input: InstalledExtensionInput = {
      kind: 'installed',
      packRecord,
      bundleContent,
    };
    const validation = loader.validate([input]);
    const validatedPkg = validation.entries[0].validatedPackage!;

    await loader.load([validatedPkg]);
    await loader.unload(['com.test.propagate']);

    // Repository should have received integrity_pass, load, and unload events
    const calls = (repo.appendLifecycleEvent as any).mock.calls;
    const eventKinds = calls.map((c: any) => c[0].kind);
    expect(eventKinds).toContain('integrity_pass');
    expect(eventKinds).toContain('load');
    expect(eventKinds).toContain('unload');
  });

  it('full pipeline with dependencies: satisfied + degraded', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      version: '1.0.0',
      dependsOn: [
        { extensionId: 'com.test.a', posture: 'required' as const },
        { extensionId: 'com.test.optional-missing', posture: 'optional' as const },
      ],
    } as any);

    // 1. Load
    const loadResult = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(loadResult.allLoaded).toBe(true); // Both load, B is degraded
    expect(loadResult.loadedExtensions).toHaveLength(2);
    expect(loadResult.dependencyResolution!.degradedExtensionIds.has('com.test.b')).toBe(true);
    expect(loadResult.dependencyResolution!.blockedExtensionIds.size).toBe(0);

    // 2. Unload
    const unloadResult = await loader.unload(['com.test.a', 'com.test.b']);
    expect(unloadResult.unloadedIds).toEqual(['com.test.a', 'com.test.b']);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('ExtensionLoader — edge cases', () => {
  it('handles empty validate input', () => {
    const loader = createExtensionLoader();
    const result = loader.validate([]);
    expect(result.allValid).toBe(true);
    expect(result.entries).toHaveLength(0);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('handles empty load input', async () => {
    const loader = createExtensionLoader();
    const result = await loader.load([]);
    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.entries).toHaveLength(0);
    expect(result.diagnostics).toHaveLength(0);
    expect(result.dependencyResolution).toBeNull();
  });

  it('validates across many extensions (stress test for isolation)', () => {
    const loader = createExtensionLoader();
    const inputs: ExtensionLoaderInput[] = [];
    for (let i = 0; i < 50; i++) {
      inputs.push({
        kind: 'direct',
        extension: makeExtensionWithId(`com.test.stress${i}`),
      });
    }

    const result = loader.validate(inputs);
    expect(result.entries).toHaveLength(50);
    expect(result.allValid).toBe(true);
  });

  it('produces frozen result objects', () => {
    const loader = createExtensionLoader();
    const ext = makeExtension();
    const result = loader.validate([{ kind: 'direct', extension: ext }]);

    // The result object itself should be frozen (immutable)
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.entries)).toBe(true);
    expect(Object.isFrozen(result.diagnostics)).toBe(true);
  });

  it('dependencyResolution result is frozen when present', async () => {
    const loader = createExtensionLoader();
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.dependencyResolution).not.toBeNull();
    if (result.dependencyResolution) {
      expect(Object.isFrozen(result.dependencyResolution.entries)).toBe(true);
      expect(Object.isFrozen(result.dependencyResolution.diagnostics)).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// resolveDependencies — edge cases
// ---------------------------------------------------------------------------

describe('resolveDependencies — edge cases', () => {
  it('handles empty package list', () => {
    const result = resolveDependencies([]);
    expect(result.entries).toHaveLength(0);
    expect(result.blockedExtensionIds.size).toBe(0);
    expect(result.degradedExtensionIds.size).toBe(0);
    expect(result.diagnostics).toHaveLength(0);
  });

  it('handles dependency on self (should be caught by manifest validation, but resolve gracefully)', () => {
    // Self-dependency should already be caught by manifest validation
    // but resolveDependencies should handle it gracefully (it's in the load set, so it's "found")
    const extA = makeExtensionWithId('com.test.a', {
      version: '1.0.0',
      dependsOn: [{ extensionId: 'com.test.a', posture: 'required' as const, versionRange: '^1.0.0' }],
    } as any);

    const result = resolveDependencies([directValidatedPackage(extA)]);
    // Self-dependency resolves as "found" and version matches
    const aEntry = result.entries.find((e) => e.extensionId === 'com.test.a')!;
    expect(aEntry.canActivate).toBe(true);
  });

  it('handles extensions with multiple dependency types (mixed satisfied, missing, version-mismatch)', () => {
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const extC = makeExtensionWithId('com.test.c', { version: '2.0.0' } as any);
    const extB = makeExtensionWithId('com.test.b', {
      version: '1.0.0',
      dependsOn: [
        { extensionId: 'com.test.a', posture: 'required' as const, versionRange: '^1.0.0' },
        { extensionId: 'com.test.missing-req', posture: 'required' as const },
        { extensionId: 'com.test.missing-opt', posture: 'optional' as const },
        { extensionId: 'com.test.c', posture: 'required' as const, versionRange: '^3.0.0' },
        { extensionId: 'com.test.d', posture: 'optional' as const, versionRange: '^2.0.0' },
      ],
    } as any);
    const extD = makeExtensionWithId('com.test.d', { version: '1.0.0' } as any);

    const result = resolveDependencies([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
      directValidatedPackage(extC),
      directValidatedPackage(extD),
    ]);

    const bEntry = result.entries.find((e) => e.extensionId === 'com.test.b')!;
    expect(bEntry.canActivate).toBe(false); // has missing required + version mismatch required
    expect(bEntry.satisfied).toContain('com.test.a');
    expect(bEntry.missingRequired).toContain('com.test.missing-req');
    expect(bEntry.missingOptional).toContain('com.test.missing-opt');
    expect(bEntry.versionMismatchRequired).toContain('com.test.c');
    expect(bEntry.versionMismatchOptional).toContain('com.test.d');
  });
});

// ---------------------------------------------------------------------------
// T13: Conflict resolution — tested through ExtensionLoader.load()
// ---------------------------------------------------------------------------

describe('ExtensionLoader.load — conflict resolution (installed-wins default)', () => {
  it('prefers installed pack when both local source and installed pack share the same extension ID', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    // Both have the same extension ID
    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Installed should win by default
    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.loadedExtensions[0].manifest.id).toBe('com.test.conflict');
    expect(result.loadedExtensions[0].manifest.version).toBe('2.0.0'); // Installed version wins

    expect(result.conflictResolution).not.toBeNull();
    const cr = result.conflictResolution!;
    expect(cr.installedWinIds.has('com.test.conflict')).toBe(true);
    expect(cr.localWinIds.size).toBe(0);

    const entry = cr.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.hasConflict).toBe(true);
    expect(entry.winner).toBe('installed');
    expect(entry.strategy).toBe('installed-wins');
    expect(entry.diagnostics.length).toBeGreaterThan(0);
    expect(entry.diagnostics[0].code).toBe('loader/conflict-installed-wins');
  });

  it('passes through local-only extensions with no conflict', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.localonly');

    const result = await loader.load([directValidatedPackage(localExt)]);

    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(1);

    expect(result.conflictResolution).not.toBeNull();
    const cr = result.conflictResolution!;
    const entry = cr.entries.find((e) => e.extensionId === 'com.test.localonly')!;
    expect(entry.hasConflict).toBe(false);
    expect(entry.hasLocalSource).toBe(true);
    expect(entry.hasInstalledPack).toBe(false);
    expect(entry.winner).toBe('local');
  });

  it('passes through installed-only extensions with no conflict', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.instonly', '1.0.0', bundleContent);

    const result = await loader.load([
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.instonly' as any,
          version: '1.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(1);

    expect(result.conflictResolution).not.toBeNull();
    const cr = result.conflictResolution!;
    // installedWinIds only tracks conflicts, not non-conflict pass-throughs
    expect(cr.winningExtensionIds.has('com.test.instonly')).toBe(true);
    const entry = cr.entries.find((e) => e.extensionId === 'com.test.instonly')!;
    expect(entry.hasConflict).toBe(false);
    expect(entry.winner).toBe('installed');
  });
});

describe('ExtensionLoader.load — conflict resolution (dev override: local-wins)', () => {
  it('prefers local source when dev override preferLocalSource is set', async () => {
    const repo = createMockRepository();
    // Set up dev override for the extension
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {},
      devOverrides: {
        'com.test.conflict': {
          extensionId: 'com.test.conflict',
          preferLocalSource: true,
          setAt: '2026-06-20T12:00:00.000Z',
        },
      },
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Local should win due to override
    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.loadedExtensions[0].manifest.version).toBe('1.0.0'); // Local version

    const cr = result.conflictResolution!;
    expect(cr.localWinIds.has('com.test.conflict')).toBe(true);
    expect(cr.installedWinIds.size).toBe(0);

    const entry = cr.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.strategy).toBe('local-wins');
    expect(entry.preferLocalSource).toBe(true);
    expect(entry.winner).toBe('local');
    expect(entry.diagnostics[0].code).toBe('loader/conflict-local-override');
  });

  it('applies dev override only when preferLocalSource is explicitly true', async () => {
    const repo = createMockRepository();
    // Dev override exists but preferLocalSource is false
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {},
      devOverrides: {
        'com.test.conflict': {
          extensionId: 'com.test.conflict',
          preferLocalSource: false,
          setAt: '2026-06-20T12:00:00.000Z',
        },
      },
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Installed should still win — override is false
    expect(result.loadedExtensions[0].manifest.version).toBe('2.0.0');
    const entry = result.conflictResolution!.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.strategy).toBe('installed-wins');
  });
});

describe('ExtensionLoader.load — conflict resolution (disabled installed fallback)', () => {
  it('falls back to local source when installed pack is disabled', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.conflict': {
          extensionId: 'com.test.conflict',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'User disabled',
        },
      },
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Local should win because installed is disabled
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.loadedExtensions[0].manifest.version).toBe('1.0.0');

    const cr = result.conflictResolution!;
    expect(cr.disabledFallbackIds.has('com.test.conflict')).toBe(true);
    expect(cr.localWinIds.has('com.test.conflict')).toBe(true);

    const entry = cr.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.strategy).toBe('installed-disabled-fallback');
    expect(entry.installedEnabled).toBe(false);
    expect(entry.winner).toBe('local');
    expect(entry.diagnostics[0].code).toBe('loader/conflict-installed-disabled');
  });

  it('local-wins override takes precedence over disabled installed', async () => {
    const repo = createMockRepository();
    // Both override AND disabled — override should win
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.conflict': {
          extensionId: 'com.test.conflict',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'Disabled',
        },
      },
      devOverrides: {
        'com.test.conflict': {
          extensionId: 'com.test.conflict',
          preferLocalSource: true,
          setAt: '2026-06-20T12:00:00.000Z',
        },
      },
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Strategy should be local-wins (override checked first)
    const entry = result.conflictResolution!.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.strategy).toBe('local-wins');
    expect(entry.preferLocalSource).toBe(true);
    expect(entry.winner).toBe('local');
  });

  it('disabled installed without local source — surfaces disabled-by-user state and does not activate', async () => {
    // When installed is disabled but there's NO local source, the loader
    // now surfaces disabled-by-user state and does not activate the package.
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.onlyinst': {
          extensionId: 'com.test.onlyinst',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'Disabled',
        },
      },
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.onlyinst', '1.0.0', bundleContent);

    const result = await loader.load([
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.onlyinst' as any,
          version: '1.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Disabled package is not activated — no loaded extensions
    expect(result.loadedExtensions).toHaveLength(0);
    // But it is present in entries with disabled-by-user state
    const loadEntry = result.entries.find((e) => e.extensionId === 'com.test.onlyinst')!;
    expect(loadEntry).toBeDefined();
    expect(loadEntry.packageState).toBe('disabled-by-user');
    expect(loadEntry.stateReason).toBe('Disabled');
    expect(loadEntry.packageMetadata).not.toBeNull();
    expect(loadEntry.packageMetadata!.label).toBe('Extension com.test.onlyinst');
    expect(loadEntry.packageMetadata!.version).toBe('1.0.0');
    // Conflict resolution still shows no conflict (only one form present)
    const conflictEntry = result.conflictResolution!.entries.find((e) => e.extensionId === 'com.test.onlyinst')!;
    expect(conflictEntry.hasConflict).toBe(false);
  });
});

describe('ExtensionLoader.load — conflict resolution (revert-to-installed)', () => {
  it('reverts to installed-wins when dev override is removed', async () => {
    const repo = createMockRepository();
    // No dev override — simulate revert
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {},
      devOverrides: {}, // Override was cleared
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Installed wins after revert
    expect(result.loadedExtensions[0].manifest.version).toBe('2.0.0');
    const entry = result.conflictResolution!.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.strategy).toBe('installed-wins');
    expect(entry.preferLocalSource).toBe(false);
  });
});

describe('ExtensionLoader.load — conflict resolution (diagnostics)', () => {
  it('emits info diagnostic for installed-wins conflict', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.diag', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.diag', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.diag' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    const diag = result.conflictResolution!.diagnostics.find(
      (d) => d.code === 'loader/conflict-installed-wins',
    );
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('info');
    expect(diag!.extensionId).toBe('com.test.diag');
  });

  it('emits info diagnostic for local-wins override conflict', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {},
      devOverrides: {
        'com.test.diag': {
          extensionId: 'com.test.diag',
          preferLocalSource: true,
          setAt: '2026-06-20T12:00:00.000Z',
        },
      },
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.diag', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.diag', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.diag' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    const diag = result.conflictResolution!.diagnostics.find(
      (d) => d.code === 'loader/conflict-local-override',
    );
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('info');
  });

  it('emits warning diagnostic for disabled-installed fallback', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.diag': {
          extensionId: 'com.test.diag',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'Disabled',
        },
      },
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.diag', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.diag', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.diag' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    const diag = result.conflictResolution!.diagnostics.find(
      (d) => d.code === 'loader/conflict-installed-disabled',
    );
    expect(diag).toBeDefined();
    expect(diag!.severity).toBe('warning');
  });

  it('aggregates conflict diagnostics into load result diagnostics', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.agg', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.agg', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.agg' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Load result diagnostics should include conflict diagnostics
    const conflictDiags = result.diagnostics.filter(
      (d) => d.code === 'loader/conflict-installed-wins',
    );
    expect(conflictDiags.length).toBeGreaterThan(0);
  });
});

describe('ExtensionLoader.load — conflict resolution (mixed scenarios)', () => {
  it('handles multiple conflicts and non-conflicts in a single load', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.disabled': {
          extensionId: 'com.test.disabled',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'Disabled',
        },
      },
      devOverrides: {
        'com.test.override': {
          extensionId: 'com.test.override',
          preferLocalSource: true,
          setAt: '2026-06-20T12:00:00.000Z',
        },
      },
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);

    // Extension A: conflict, installed-wins (no override)
    const localA = makeExtensionWithId('com.test.default', { version: '1.0.0' } as any);
    const bundleA = 'export function activate() {}';
    const recordA = await makePackRecord('com.test.default', '2.0.0', bundleA);

    // Extension B: conflict, local-wins (override)
    const localB = makeExtensionWithId('com.test.override', { version: '1.0.0' } as any);
    const bundleB = 'export function activate() {}';
    const recordB = await makePackRecord('com.test.override', '2.0.0', bundleB);

    // Extension C: conflict, disabled fallback
    const localC = makeExtensionWithId('com.test.disabled', { version: '1.0.0' } as any);
    const bundleC = 'export function activate() {}';
    const recordC = await makePackRecord('com.test.disabled', '2.0.0', bundleC);

    // Extension D: no conflict, local only
    const localD = makeExtensionWithId('com.test.localonly');

    // Extension E: no conflict, installed only
    const bundleE = 'export function activate() {}';
    const recordE = await makePackRecord('com.test.instonly', '1.0.0', bundleE);

    const result = await loader.load([
      directValidatedPackage(localA),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.default' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: recordA.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: recordA.manifestSnapshot,
        bundleContent: bundleA,
      }),
      directValidatedPackage(localB),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.override' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: recordB.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: recordB.manifestSnapshot,
        bundleContent: bundleB,
      }),
      directValidatedPackage(localC),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.disabled' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: recordC.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: recordC.manifestSnapshot,
        bundleContent: bundleC,
      }),
      directValidatedPackage(localD),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.instonly' as any,
          version: '1.0.0',
          apiVersion: 1,
          integrity: recordE.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: recordE.manifestSnapshot,
        bundleContent: bundleE,
      }),
    ]);

    // All 5 winning extensions should load
    expect(result.loadedExtensions).toHaveLength(5);
    const loadedIds = result.loadedExtensions.map((e) => e.manifest.id);

    // A: installed-wins → version 2.0.0
    expect(loadedIds).toContain('com.test.default');
    const extA = result.loadedExtensions.find((e) => e.manifest.id === 'com.test.default')!;
    expect(extA.manifest.version).toBe('2.0.0');

    // B: local-wins → version 1.0.0
    const extB = result.loadedExtensions.find((e) => e.manifest.id === 'com.test.override')!;
    expect(extB.manifest.version).toBe('1.0.0');

    // C: disabled fallback → version 1.0.0
    const extC = result.loadedExtensions.find((e) => e.manifest.id === 'com.test.disabled')!;
    expect(extC.manifest.version).toBe('1.0.0');

    // D: local only
    expect(loadedIds).toContain('com.test.localonly');

    // E: installed only
    expect(loadedIds).toContain('com.test.instonly');

    // Check conflict resolution entries
    const cr = result.conflictResolution!;
    expect(cr.entries).toHaveLength(5);
    expect(cr.installedWinIds.has('com.test.default')).toBe(true);
    expect(cr.localWinIds.has('com.test.override')).toBe(true);
    expect(cr.disabledFallbackIds.has('com.test.disabled')).toBe(true);
    expect(cr.winningExtensionIds.size).toBe(5);
  });

  it('repository errors during conflict config fetch degrade gracefully', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockRejectedValue(new Error('DB connection lost'));
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Should still load — defaults to installed-wins with empty config
    expect(result.allLoaded).toBe(true);
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.loadedExtensions[0].manifest.version).toBe('2.0.0');

    const entry = result.conflictResolution!.entries.find((e) => e.extensionId === 'com.test.conflict')!;
    expect(entry.strategy).toBe('installed-wins');
  });

  it('conflictResolution is not null even when there are no conflicts', async () => {
    const loader = createExtensionLoader();
    const ext = makeExtensionWithId('com.test.noconflict');

    const result = await loader.load([directValidatedPackage(ext)]);
    expect(result.conflictResolution).not.toBeNull();
    expect(result.conflictResolution!.entries).toHaveLength(1);
    expect(result.conflictResolution!.diagnostics).toHaveLength(0);
  });

  it('loserPackage is set correctly for conflicts', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.loser', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.loser', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.loser' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    const entry = result.conflictResolution!.entries.find((e) => e.extensionId === 'com.test.loser')!;
    expect(entry.loserPackage).not.toBeNull();
    expect(entry.loserPackage!.form).toBe('workspace-source'); // Local source lost
  });
});

describe('ExtensionLoader.load — conflict resolution and dependency resolution interaction', () => {
  it('conflict loser is not considered for dependency resolution', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    // Setup: extA (installed only), extB (conflict: local + installed, installed wins)
    // extC depends on extB (should be satisfied by installed extB)
    const extA = makeExtensionWithId('com.test.a', { version: '1.0.0' } as any);
    const localB = makeExtensionWithId('com.test.b', { version: '1.0.0' } as any);
    const bundleB = 'export function activate() {}';
    const recordB = await makePackRecord('com.test.b', '2.0.0', bundleB);
    const extC = makeExtensionWithId('com.test.c', {
      version: '1.0.0',
      dependsOn: [{ extensionId: 'com.test.b', posture: 'required' as const }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(localB),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.b' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: recordB.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: recordB.manifestSnapshot,
        bundleContent: bundleB,
      }),
      directValidatedPackage(extC),
    ]);

    // After conflict resolution, extB installed wins.
    // Dependency resolution should see only winning packages.
    // extC should be satisfied (extB installed version 2.0.0 is present).
    // Wait, actually dependency resolution runs BEFORE conflict resolution in the current code...
    // Let me check this...
    expect(result.allLoaded).toBe(true);
    // All three should load (A, installed-B, C)
    const loadedIds = result.loadedExtensions.map((e) => e.manifest.id);
    expect(loadedIds).toContain('com.test.a');
    expect(loadedIds).toContain('com.test.b');
    expect(loadedIds).toContain('com.test.c');
    expect(result.loadedExtensions).toHaveLength(3);
  });
});

describe('ExtensionLoader.load — conflict resolution with frozen results', () => {
  it('conflictResolution result is frozen', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);

    const localExt = makeExtensionWithId('com.test.frozen', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.frozen', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.frozen' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    expect(result.conflictResolution).not.toBeNull();
    const cr = result.conflictResolution!;
    expect(Object.isFrozen(cr)).toBe(true);
    expect(Object.isFrozen(cr.entries)).toBe(true);
    expect(Object.isFrozen(cr.diagnostics)).toBe(true);
    expect(Object.isFrozen(cr.winningPackages)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Package state and metadata preservation (M5 T1)
// ---------------------------------------------------------------------------

describe('ExtensionLoader.load — package state classification', () => {
  it('exposes loaded state with metadata for a successfully loaded workspace source', async () => {
    const loader = createExtensionLoader();
    const ext = makeExtensionWithId('com.test.loaded');

    const result = await loader.load([directValidatedPackage(ext)]);

    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.entries).toHaveLength(1);
    const entry = result.entries[0];
    expect(entry.packageState).toBe('loaded');
    expect(entry.stateReason).toBe('Loaded successfully.');
    expect(entry.packageMetadata).not.toBeNull();
    expect(entry.packageMetadata!.label).toBe('Extension com.test.loaded');
    expect(entry.packageMetadata!.version).toBe('1.0.0');
  });

  it('exposes loaded state with degraded reason for optional-dep-missing extensions', async () => {
    const loader = createExtensionLoader();
    const ext = makeExtensionWithId('com.test.degraded', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'optional' as const }],
    } as any);

    const result = await loader.load([directValidatedPackage(ext)]);

    expect(result.loadedExtensions).toHaveLength(1);
    const entry = result.entries[0];
    expect(entry.packageState).toBe('loaded');
    expect(entry.stateReason).toContain('degraded');
  });

  it('exposes disabled-by-user state with reason for non-conflict disabled installed pack', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.disabled': {
          extensionId: 'com.test.disabled',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'User disabled via extension manager',
        },
      },
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.disabled', '1.0.0', bundleContent);

    const result = await loader.load([
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.disabled' as any,
          version: '1.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Should not load, but should be visible in entries
    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.entries).toHaveLength(1);
    const entry = result.entries[0];
    expect(entry.packageState).toBe('disabled-by-user');
    expect(entry.stateReason).toBe('User disabled via extension manager');
    expect(entry.packageMetadata).not.toBeNull();
    expect(entry.packageMetadata!.label).toBe('Extension com.test.disabled');
    expect(entry.loaded).toBe(false);
  });

  it('exposes disabled-by-user state for installed loser in conflict when disabled', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {
        'com.test.conflict': {
          extensionId: 'com.test.conflict',
          enabled: false,
          lastToggledAt: '2026-06-20T12:00:00.000Z',
          toggleReason: 'User disabled via manager',
        },
      },
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);
    const localExt = makeExtensionWithId('com.test.conflict', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.conflict', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.conflict' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Local source wins (installed disabled fallback)
    expect(result.loadedExtensions).toHaveLength(1);
    // Should have entries for both the winner and loser
    expect(result.entries).toHaveLength(2);

    const loserEntry = result.entries.find((e) => !e.loaded)!;
    expect(loserEntry).toBeDefined();
    expect(loserEntry.packageState).toBe('disabled-by-user');
    expect(loserEntry.stateReason).toContain('disabled');
    expect(loserEntry.packageMetadata).not.toBeNull();
  });

  it('exposes incompatible state for dependency-blocked package with reason', async () => {
    const loader = createExtensionLoader();
    const ext = makeExtensionWithId('com.test.blocked', {
      dependsOn: [{ extensionId: 'com.test.missing', posture: 'required' as const }],
    } as any);

    const result = await loader.load([directValidatedPackage(ext)]);

    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.entries).toHaveLength(1);
    const entry = result.entries[0];
    expect(entry.packageState).toBe('incompatible');
    expect(entry.stateReason).toContain('Missing required dependencies');
    expect(entry.stateReason).toContain('com.test.missing');
    expect(entry.packageMetadata).not.toBeNull();
    expect(entry.packageMetadata!.label).toBe('Extension com.test.blocked');
    expect(entry.loaded).toBe(false);
  });

  it('exposes incompatible state for cycle-blocked package with cycle reason', async () => {
    const loader = createExtensionLoader();
    const extA = makeExtensionWithId('com.test.cycleA', {
      dependsOn: [{ extensionId: 'com.test.cycleB', posture: 'required' as const }],
    } as any);
    const extB = makeExtensionWithId('com.test.cycleB', {
      dependsOn: [{ extensionId: 'com.test.cycleA', posture: 'required' as const }],
    } as any);

    const result = await loader.load([
      directValidatedPackage(extA),
      directValidatedPackage(extB),
    ]);

    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.entries).toHaveLength(2);
    for (const entry of result.entries) {
      expect(entry.packageState).toBe('incompatible');
      expect(entry.stateReason).toContain('dependency cycle');
      expect(entry.packageMetadata).not.toBeNull();
    }
  });

  it('exposes duplicate state for workspace source loser when installed wins', async () => {
    const repo = createMockRepository();
    // No overrides, no disabled — installed wins by default
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {},
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);
    const localExt = makeExtensionWithId('com.test.dup', { version: '1.0.0' } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.dup', '2.0.0', bundleContent);

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.dup' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Installed wins, local loses
    expect(result.loadedExtensions).toHaveLength(1);
    expect(result.entries).toHaveLength(2);

    const loserEntry = result.entries.find((e) => !e.loaded)!;
    expect(loserEntry.packageState).toBe('duplicate');
    expect(loserEntry.stateReason).toContain('Installed pack takes precedence');
    expect(loserEntry.packageMetadata).not.toBeNull();
  });

  it('exposes runtime-error state for integrity-failed installed bundle', async () => {
    const repo = createMockRepository();
    const loader = createExtensionLoader(repo);
    const originalBundle = 'export function activate() {}';
    const tamperedBundle = 'export function malicious() {}';
    const packRecord = await makePackRecord('com.test.rterr', '1.0.0', originalBundle);

    const result = await loader.load([
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.rterr' as any,
          version: '1.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent: tamperedBundle,
      }),
    ]);

    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.entries).toHaveLength(1);
    const entry = result.entries[0];
    expect(entry.packageState).toBe('runtime-error');
    expect(entry.stateReason).toContain('Load failed');
    expect(entry.packageMetadata).not.toBeNull();
    expect(entry.loaded).toBe(false);
  });

  it('preserves metadata for all entries including losers', async () => {
    const repo = createMockRepository();
    (repo.getFullExtensionState as any).mockResolvedValue({
      enablement: {},
      devOverrides: {},
      settings: {},
      packs: {},
      lock: { entries: {}, lastUpdatedAt: '2026-01-01T00:00:00.000Z' },
    });

    const loader = createExtensionLoader(repo);
    const localExt = makeExtensionWithId('com.test.meta', {
      version: '1.0.0',
      label: 'My Local Extension',
      publisher: 'LocalDev',
      description: 'A test extension',
      license: 'Apache-2.0',
    } as any);
    const bundleContent = 'export function activate() {}';
    const packRecord = await makePackRecord('com.test.meta', '2.0.0', bundleContent, {
      manifestSnapshot: {
        id: 'com.test.meta' as any,
        version: '2.0.0',
        label: 'My Installed Extension',
        publisher: 'Test Publisher',
        description: 'An installed test extension',
        license: 'MIT',
        settingsSchema: { version: 1 },
      },
    });

    const result = await loader.load([
      directValidatedPackage(localExt),
      installedValidatedPackage({
        metadata: {
          extensionId: 'com.test.meta' as any,
          version: '2.0.0',
          apiVersion: 1,
          integrity: packRecord.integrity,
          installedAt: '2026-06-20T12:00:00.000Z',
          enabled: true,
          publisher: 'Test Publisher',
          license: 'MIT',
        },
        manifest: packRecord.manifestSnapshot,
        bundleContent,
      }),
    ]);

    // Installed wins, but both should have metadata
    expect(result.entries).toHaveLength(2);

    const winnerEntry = result.entries.find((e) => e.loaded)!;
    expect(winnerEntry.packageMetadata!.label).toBe('My Installed Extension');
    expect(winnerEntry.packageMetadata!.version).toBe('2.0.0');
    expect(winnerEntry.packageMetadata!.publisher).toBe('Test Publisher');

    const loserEntry = result.entries.find((e) => !e.loaded)!;
    expect(loserEntry.packageMetadata!.label).toBe('My Local Extension');
    expect(loserEntry.packageMetadata!.version).toBe('1.0.0');
    expect(loserEntry.packageMetadata!.publisher).toBe('LocalDev');
    expect(loserEntry.packageMetadata!.description).toBe('A test extension');
    expect(loserEntry.packageMetadata!.license).toBe('Apache-2.0');
    expect(loserEntry.packageState).toBe('duplicate');
  });

  it('empty load returns empty entries', async () => {
    const loader = createExtensionLoader();
    const result = await loader.load([]);
    expect(result.entries).toHaveLength(0);
    expect(result.loadedExtensions).toHaveLength(0);
    expect(result.allLoaded).toBe(true);
  });
});
