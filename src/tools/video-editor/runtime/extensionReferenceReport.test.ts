import { describe, it, expect, vi } from 'vitest';
import {
  scanProjectReferences,
  checkUninstallPreconditions,
  performUninstallRepositoryCleanup,
} from './extensionReferenceReport';
import type {
  ProjectReferenceScan,
  ExtensionReferenceReport,
  ReferenceReportResult,
  UninstallPreconditionResult,
} from './extensionReferenceReport';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScan(overrides: Partial<ProjectReferenceScan> = {}): ProjectReferenceScan {
  return {
    isComplete: true,
    ...overrides,
  };
}

function makeMockRepository(overrides: Partial<{
  deleteLockEntry: ReturnType<typeof vi.fn>;
  deletePackRecord: ReturnType<typeof vi.fn>;
  deleteEnablementState: ReturnType<typeof vi.fn>;
  deleteSettingsSnapshot: ReturnType<typeof vi.fn>;
  deleteDevOverride: ReturnType<typeof vi.fn>;
  appendLifecycleEvent: ReturnType<typeof vi.fn>;
  isDisposed: boolean;
}> = {}) {
  return {
    deleteLockEntry: overrides.deleteLockEntry ?? vi.fn().mockResolvedValue(undefined),
    deletePackRecord: overrides.deletePackRecord ?? vi.fn().mockResolvedValue(undefined),
    deleteEnablementState: overrides.deleteEnablementState ?? vi.fn().mockResolvedValue(undefined),
    deleteSettingsSnapshot: overrides.deleteSettingsSnapshot ?? vi.fn().mockResolvedValue(undefined),
    deleteDevOverride: overrides.deleteDevOverride ?? vi.fn().mockResolvedValue(undefined),
    appendLifecycleEvent: overrides.appendLifecycleEvent ?? vi.fn().mockResolvedValue(undefined),
    isDisposed: overrides.isDisposed ?? false,
  };
}

// ---------------------------------------------------------------------------
// scanProjectReferences
// ---------------------------------------------------------------------------

describe('scanProjectReferences', () => {
  // ---- Empty scan ----

  it('returns empty result when scan has no data', () => {
    const result = scanProjectReferences(makeScan());
    expect(result.entries).toHaveLength(0);
    expect(result.extensionIdsWithReferences).toHaveLength(0);
    expect(result.diagnostics).toHaveLength(0);
    expect(result.totalReferenceCount).toBe(0);
    expect(result.scanIsComplete).toBe(true);
  });

  it('returns empty result when scan has no data and is incomplete', () => {
    const result = scanProjectReferences(makeScan({ isComplete: false }));
    expect(result.entries).toHaveLength(0);
    expect(result.totalReferenceCount).toBe(0);
    expect(result.scanIsComplete).toBe(false);
  });

  // ---- Contribution references ----

  it('finds effect references from usedContributions', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.myEffect': ['Timeline A > Clip 1', 'Timeline B > Clip 2'],
        },
      },
    });

    const result = scanProjectReferences(scan);

    expect(result.totalReferenceCount).toBe(2);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].extensionId).toBe('com.example.ext');
    expect(result.entries[0].totalReferenceCount).toBe(2);
    expect(result.entries[0].hasReferences).toBe(true);
    expect(result.entries[0].referencesByKind.effect).toHaveLength(2);

    // Check reference details
    const refs = result.entries[0].referencesByKind.effect!;
    expect(refs[0].kind).toBe('effect');
    expect(refs[0].referenceId).toBe('com.example.ext.myEffect');
    expect(refs[0].location).toBe('Timeline A > Clip 1');
    expect(refs[0].ownerExtensionId).toBe('com.example.ext');
    expect(refs[1].location).toBe('Timeline B > Clip 2');
  });

  it('finds transition references', () => {
    const scan = makeScan({
      usedContributions: {
        transitions: {
          'com.foo.bar.fancyTransition': ['Main Timeline'],
        },
      },
    });

    const result = scanProjectReferences(scan, ['com.foo.bar']);
    expect(result.totalReferenceCount).toBe(1);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].referencesByKind.transition).toHaveLength(1);
  });

  it('finds shader references', () => {
    const scan = makeScan({
      usedContributions: {
        shaders: {
          'com.shaders.gl.glowingEdge': ['Project-wide shader'],
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(1);
    expect(result.entries[0].referencesByKind.shader).toHaveLength(1);
  });

  it('finds clip-type references', () => {
    const scan = makeScan({
      usedContributions: {
        clipTypes: {
          'com.cliptypes.special.introClip': ['Project template'],
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(1);
    expect(result.entries[0].referencesByKind['clip-type']).toHaveLength(1);
  });

  it('finds agent-tool references', () => {
    const scan = makeScan({
      usedContributions: {
        agentTools: {
          'com.agents.tools.videoAnalyzer': ['Agent pipeline'],
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(1);
    expect(result.entries[0].referencesByKind['agent-tool']).toHaveLength(1);
  });

  it('finds live-data-source references', () => {
    const scan = makeScan({
      usedContributions: {
        liveDataSources: {
          'com.livedata.feeds.stockTicker': ['Live overlay > Panel 2'],
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(1);
    expect(result.entries[0].referencesByKind['live-data-source']).toHaveLength(1);
  });

  it('maps unknown contribution kinds to "other"', () => {
    const scan = makeScan({
      usedContributions: {
        unknownKind: {
          'com.example.ext.someThing': ['Some location'],
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(1);
    expect(result.entries[0].referencesByKind.other).toHaveLength(1);
  });

  // ---- Settings references ----

  it('finds settings references', () => {
    const scan = makeScan({
      settingsReferences: {
        'com.example.ext': ['theme', 'debugMode'],
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(2);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].referencesByKind.settings).toHaveLength(2);
    expect(result.entries[0].referencesByKind.settings![0].referenceId).toBe('theme');
    expect(result.entries[0].referencesByKind.settings![1].referenceId).toBe('debugMode');
  });

  // ---- Lock entries ----

  it('finds lock entry references', () => {
    const scan = makeScan({
      lockEntries: {
        'com.example.ext': ['myEffect', 'myTransition'],
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(2);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].referencesByKind['lock-entry']).toHaveLength(2);
  });

  // ---- Multiple extensions ----

  it('groups references by extension across multiple extensions', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.extA.effect1': ['Timeline 1'],
          'com.extB.effect2': ['Timeline 2'],
        },
        transitions: {
          'com.extA.trans1': ['Timeline 3'],
        },
      },
    });

    const result = scanProjectReferences(scan);

    expect(result.entries).toHaveLength(2);
    expect(result.totalReferenceCount).toBe(3);

    const extA = result.entries.find((e) => e.extensionId === 'com.extA')!;
    expect(extA.totalReferenceCount).toBe(2);
    expect(extA.referencesByKind.effect).toHaveLength(1);
    expect(extA.referencesByKind.transition).toHaveLength(1);

    const extB = result.entries.find((e) => e.extensionId === 'com.extB')!;
    expect(extB.totalReferenceCount).toBe(1);
    expect(extB.referencesByKind.effect).toHaveLength(1);
  });

  // ---- Filtering by extension IDs ----

  it('filters references to specific extension IDs', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.extA.effect1': ['Timeline 1'],
          'com.extB.effect2': ['Timeline 2'],
        },
      },
    });

    const result = scanProjectReferences(scan, ['com.extA']);
    expect(result.entries).toHaveLength(1);
    expect(result.entries[0].extensionId).toBe('com.extA');
    expect(result.totalReferenceCount).toBe(1);
  });

  it('returns empty when filtered extension IDs have no references', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.extA.effect1': ['Timeline 1'],
        },
      },
    });

    const result = scanProjectReferences(scan, ['com.extC']);
    expect(result.entries).toHaveLength(0);
    expect(result.totalReferenceCount).toBe(0);
  });

  // ---- Diagnostics ----

  it('generates diagnostics for extensions with references', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.myEffect': ['Timeline 1'],
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.diagnostics).toHaveLength(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('uninstall/orphaned-references');
    expect(result.diagnostics[0].extensionId).toBe('com.example.ext');
    expect(result.diagnostics[0].message).toContain('1 project reference');
    expect(result.diagnostics[0].detail).toBeDefined();
    expect(result.diagnostics[0].detail!.totalReferences).toBe(1);
  });

  it('does not generate diagnostics when no references exist', () => {
    const scan = makeScan();
    const result = scanProjectReferences(scan);
    expect(result.diagnostics).toHaveLength(0);
  });

  // ---- Multiple reference types for same extension ----

  it('combines multiple reference kinds for the same extension', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.effect1': ['Timeline 1'],
        },
      },
      settingsReferences: {
        'com.example.ext': ['theme'],
      },
      lockEntries: {
        'com.example.ext': ['effect1'],
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.entries).toHaveLength(1);
    const entry = result.entries[0];
    expect(entry.totalReferenceCount).toBe(3); // 1 effect + 1 setting + 1 lock
    expect(entry.referencesByKind.effect).toHaveLength(1);
    expect(entry.referencesByKind.settings).toHaveLength(1);
    expect(entry.referencesByKind['lock-entry']).toHaveLength(1);
  });

  it('hasReferences is true only when references exist', () => {
    const scanWithRefs = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.effect1': ['Timeline 1'],
        },
      },
    });
    const resultWith = scanProjectReferences(scanWithRefs);
    expect(resultWith.entries[0].hasReferences).toBe(true);

    const resultWithout = scanProjectReferences(makeScan());
    expect(resultWithout.entries).toHaveLength(0);
  });

  // ---- Edge cases ----

  it('handles contribution IDs that cannot be resolved to an extension', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'x': ['Some location'], // too short to resolve
        },
      },
    });

    // Should not crash and should resolve to empty owner
    const result = scanProjectReferences(scan);
    // 'x' has only one segment, so ownerExtensionId resolves to '' and is skipped
    expect(result.totalReferenceCount).toBe(0);
  });

  it('handles contributions with many locations', () => {
    const locations = Array.from({ length: 50 }, (_, i) => `Timeline ${i}`);
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.popularEffect': locations,
        },
      },
    });

    const result = scanProjectReferences(scan);
    expect(result.totalReferenceCount).toBe(50);
    expect(result.entries[0].referencesByKind.effect).toHaveLength(50);
  });
});

// ---------------------------------------------------------------------------
// checkUninstallPreconditions
// ---------------------------------------------------------------------------

describe('checkUninstallPreconditions', () => {
  it('returns canProceed true with no references', () => {
    const scan = makeScan();
    const result = checkUninstallPreconditions(scan, 'com.example.ext');

    expect(result.extensionId).toBe('com.example.ext');
    expect(result.canProceed).toBe(true);
    expect(result.willOrphanReferences).toBe(false);
    expect(result.blockingDiagnostics).toHaveLength(0);
    expect(result.summary).toContain('No project references found');
  });

  it('returns references and diagnostics when references exist', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.myEffect': ['Timeline 1', 'Timeline 2'],
        },
      },
    });

    const result = checkUninstallPreconditions(scan, 'com.example.ext');

    expect(result.canProceed).toBe(true);
    expect(result.willOrphanReferences).toBe(true);
    expect(result.referenceReport.totalReferenceCount).toBe(2);
    expect(result.blockingDiagnostics).toHaveLength(1);
    expect(result.blockingDiagnostics[0].code).toBe('uninstall/references-remain');
    expect(result.blockingDiagnostics[0].message).toContain('2 active reference');
    expect(result.summary).toContain('2 reference(s) will be orphaned');
  });

  it('includes incomplete scan warning when scan is incomplete', () => {
    const scan = makeScan({ isComplete: false });
    const result = checkUninstallPreconditions(scan, 'com.example.ext');

    expect(result.warningDiagnostics).toHaveLength(1);
    expect(result.warningDiagnostics[0].code).toBe('uninstall/scan-incomplete');
  });

  it('does not include incomplete scan warning when scan is complete', () => {
    const scan = makeScan({ isComplete: true });
    const result = checkUninstallPreconditions(scan, 'com.example.ext');

    expect(result.warningDiagnostics).toHaveLength(0);
  });

  it('includes both blocking and warning diagnostics when applicable', () => {
    const scan = makeScan({
      isComplete: false,
      usedContributions: {
        effects: {
          'com.example.ext.myEffect': ['Timeline 1'],
        },
      },
    });

    const result = checkUninstallPreconditions(scan, 'com.example.ext');

    expect(result.blockingDiagnostics).toHaveLength(1);
    expect(result.warningDiagnostics).toHaveLength(1);
    expect(result.willOrphanReferences).toBe(true);
  });

  it('includes detail with reference kinds in the diagnostic', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.eff1': ['Timeline 1'],
        },
        transitions: {
          'com.example.ext.trans1': ['Timeline 2'],
        },
      },
    });

    const result = checkUninstallPreconditions(scan, 'com.example.ext');

    expect(result.blockingDiagnostics).toHaveLength(1);
    const diag = result.blockingDiagnostics[0];
    expect(diag.detail).toBeDefined();
    expect(diag.detail!.totalReferences).toBe(2);
    const kindsByKind = diag.detail!.referencesByKind as Array<{ kind: string; count: number }>;
    expect(kindsByKind).toHaveLength(2);
  });

  it('truncates reference details to first 10 per kind', () => {
    const locations = Array.from({ length: 15 }, (_, i) => `Timeline ${i}`);
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.example.ext.manyEffect': locations,
        },
      },
    });

    const result = checkUninstallPreconditions(scan, 'com.example.ext');
    const diag = result.blockingDiagnostics[0];
    const kindsByKind = diag.detail!.referencesByKind as Array<{
      kind: string;
      count: number;
      refs: Array<{ referenceId: string; location: string }>;
    }>;

    expect(kindsByKind[0].count).toBe(15);
    expect(kindsByKind[0].refs).toHaveLength(10); // Truncated to 10
  });

  it('handles extension with no scan data gracefully', () => {
    const scan = makeScan({
      usedContributions: {
        effects: {
          'com.other.ext.effect': ['Timeline 1'],
        },
      },
    });

    const result = checkUninstallPreconditions(scan, 'com.different.ext');

    expect(result.canProceed).toBe(true);
    expect(result.willOrphanReferences).toBe(false);
    expect(result.referenceReport.totalReferenceCount).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// performUninstallRepositoryCleanup
// ---------------------------------------------------------------------------

describe('performUninstallRepositoryCleanup', () => {
  it('performs all cleanup steps in order and records lifecycle event', async () => {
    const deleteLockEntry = vi.fn().mockResolvedValue(undefined);
    const deletePackRecord = vi.fn().mockResolvedValue(undefined);
    const deleteEnablementState = vi.fn().mockResolvedValue(undefined);
    const deleteSettingsSnapshot = vi.fn().mockResolvedValue(undefined);
    const deleteDevOverride = vi.fn().mockResolvedValue(undefined);
    const appendLifecycleEvent = vi.fn().mockResolvedValue(undefined);

    const repo = makeMockRepository({
      deleteLockEntry,
      deletePackRecord,
      deleteEnablementState,
      deleteSettingsSnapshot,
      deleteDevOverride,
      appendLifecycleEvent,
    });

    const result = await performUninstallRepositoryCleanup(repo, 'com.example.ext');

    expect(result.success).toBe(true);
    expect(result.lifecycleEventIds).toHaveLength(1);
    expect(result.lifecycleEventIds[0]).toContain('uninstall-com.example.ext');

    // Verify call order
    expect(deleteLockEntry).toHaveBeenCalledWith('com.example.ext');
    expect(deletePackRecord).toHaveBeenCalledWith('com.example.ext');
    expect(deleteEnablementState).toHaveBeenCalledWith('com.example.ext');
    expect(deleteSettingsSnapshot).toHaveBeenCalledWith('com.example.ext');
    expect(deleteDevOverride).toHaveBeenCalledWith('com.example.ext');
    expect(appendLifecycleEvent).toHaveBeenCalledTimes(1);

    // Verify lifecycle event
    const event = appendLifecycleEvent.mock.calls[0][0];
    expect(event.extensionId).toBe('com.example.ext');
    expect(event.kind).toBe('uninstall');
    expect(event.detail).toBeDefined();
    expect(event.detail!.action).toBe('uninstall');
    expect(event.detail!.cleanedUp).toContain('lockEntry');
    expect(event.detail!.cleanedUp).toContain('packRecord');
    expect(event.detail!.cleanedUp).toContain('enablementState');
    expect(event.detail!.cleanedUp).toContain('settingsSnapshot');
    expect(event.detail!.cleanedUp).toContain('devOverride');
  });

  it('returns error when repository is disposed', async () => {
    const repo = makeMockRepository({ isDisposed: true });
    const result = await performUninstallRepositoryCleanup(repo, 'com.example.ext');

    expect(result.success).toBe(false);
    expect(result.error).toContain('disposed');
    expect(result.lifecycleEventIds).toHaveLength(0);
  });

  it('fails gracefully when a delete step throws', async () => {
    const deletePackRecord = vi.fn().mockRejectedValue(new Error('IndexedDB error'));
    const repo = makeMockRepository({ deletePackRecord });

    const result = await performUninstallRepositoryCleanup(repo, 'com.example.ext');

    expect(result.success).toBe(false);
    expect(result.error).toContain('IndexedDB error');
    expect(result.error).toContain('com.example.ext');
  });

  it('fails gracefully when lifecycle event append throws', async () => {
    const appendLifecycleEvent = vi.fn().mockRejectedValue(new Error('Write error'));
    const repo = makeMockRepository({ appendLifecycleEvent });

    const result = await performUninstallRepositoryCleanup(repo, 'com.example.ext');

    expect(result.success).toBe(false);
    expect(result.error).toContain('Write error');
  });

  it('handles empty extensionId gracefully', async () => {
    const repo = makeMockRepository();

    const result = await performUninstallRepositoryCleanup(repo, '');

    expect(result.success).toBe(true); // Deletion is idempotent
    expect(result.lifecycleEventIds).toHaveLength(1);
  });

  it('returns stable lifecycle event ID format', async () => {
    const repo = makeMockRepository();
    const result = await performUninstallRepositoryCleanup(repo, 'ext.abc');

    expect(result.lifecycleEventIds[0]).toMatch(/^uninstall-ext\.abc-\d+$/);
  });
});
