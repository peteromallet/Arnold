import { describe, expect, it } from 'vitest';
import {
  normalizeExtensionRuntime,
  DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME,
  getTimelineOverlayContributions,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type {
  ExtensionRuntime,
  InactiveReservedContribution,
  TimelineOverlayRenderProps,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import { defineExtension } from '@reigh/editor-sdk';
import type { ReighExtension, ExtensionDiagnostic } from '@reigh/editor-sdk';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create a minimal extension with the given id. */
function ext(
  id: string,
  overrides?: Partial<Parameters<typeof defineExtension>[0]>,
): ReighExtension {
  const { manifest: manifestOverrides, ...restOverrides } = overrides ?? {};
  return defineExtension({
    manifest: {
      id: id as any,
      version: '1.0.0',
      label: id,
      ...manifestOverrides,
    } as any,
    ...restOverrides,
  });
}

/** Find diagnostics matching a code. */
function diagsOf(runtime: ExtensionRuntime, code: string): ExtensionDiagnostic[] {
  return runtime.diagnostics.filter((d) => d.code === code);
}

// ---------------------------------------------------------------------------
// Empty / default identity
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — empty input', () => {
  it('returns a frozen runtime when given an empty array', () => {
    const rt = normalizeExtensionRuntime([]);
    expect(Object.isFrozen(rt)).toBe(true);
    expect(rt.extensions).toEqual([]);
    expect(rt.diagnostics).toEqual([]);
    expect(rt.inactiveReserved).toEqual([]);
    expect(rt.knownRenderIds.size).toBe(0);
    expect(rt.settingsDefaults).toEqual({});
  });

  it('preserves DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME identity in config', () => {
    const rt = normalizeExtensionRuntime([]);
    expect(rt.config).toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
  });

  it('returns the identical frozen empty runtime singleton on repeated calls', () => {
    const a = normalizeExtensionRuntime([]);
    const b = normalizeExtensionRuntime([]);
    expect(a).toBe(b);
    expect(a.config).toBe(b.config);
  });

  it('has frozen nested structures', () => {
    const rt = normalizeExtensionRuntime([]);
    expect(Object.isFrozen(rt.extensions)).toBe(true);
    expect(Object.isFrozen(rt.diagnostics)).toBe(true);
    expect(Object.isFrozen(rt.inactiveReserved)).toBe(true);
    expect(Object.isFrozen(rt.settingsDefaults)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Single extension — no contributions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — single extension, no contributions', () => {
  const single = ext('com.example.empty');

  it('produces an empty config (default identity preserved)', () => {
    const rt = normalizeExtensionRuntime([single]);
    expect(rt.config).toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
  });

  it('includes the extension in the extensions list', () => {
    const rt = normalizeExtensionRuntime([single]);
    expect(rt.extensions).toHaveLength(1);
    expect((rt.extensions[0].manifest.id as string)).toBe('com.example.empty');
  });

  it('has no diagnostics', () => {
    const rt = normalizeExtensionRuntime([single]);
    expect(rt.diagnostics).toEqual([]);
  });

  it('initializes settings defaults for the extension', () => {
    const rt = normalizeExtensionRuntime([single]);
    expect(rt.settingsDefaults).toHaveProperty('com.example.empty');
    expect(rt.settingsDefaults['com.example.empty']).toEqual({});
    expect(Object.isFrozen(rt.settingsDefaults['com.example.empty'])).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Slot contributions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — slot contributions', () => {
  const withSlots = ext('com.example.slots', {
    manifest: {
      contributions: [
        { id: 'toolbar-btn' as any, kind: 'slot', slot: 'toolbar', order: 10, label: 'TB' },
        { id: 'status-widget' as any, kind: 'slot', slot: 'statusBar', order: 50, label: 'SW' },
        { id: 'header-item' as any, kind: 'slot', slot: 'header', order: 0, label: 'HI' },
      ],
    },
  });

  it('projects slot contributions onto config.slots', () => {
    const rt = normalizeExtensionRuntime([withSlots]);
    expect(rt.config).not.toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
    expect(Object.keys(rt.config.slots).sort()).toEqual(['header', 'statusBar', 'toolbar']);
    expect(Object.isFrozen(rt.config.slots)).toBe(true);
  });

  it('freezes the whole config tree', () => {
    const rt = normalizeExtensionRuntime([withSlots]);
    expect(Object.isFrozen(rt.config)).toBe(true);
    expect(Object.isFrozen(rt.config.dialogHost.dialogs)).toBe(true);
    expect(Object.isFrozen(rt.config.registry.panels)).toBe(true);
    expect(Object.isFrozen(rt.config.registry.inspectorSections)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Dialog / panel / inspectorSection contributions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — dialog/panel/inspector contributions', () => {
  const withAll = ext('com.example.all', {
    manifest: {
      contributions: [
        { id: 'dlg' as any, kind: 'dialog', order: 0, layer: 'modal' as const },
        { id: 'pnl' as any, kind: 'panel', order: 5 },
        { id: 'insp' as any, kind: 'inspectorSection', order: 1, placement: 'before-default' as const },
      ],
    },
  });

  it('projects dialog contributions onto dialogHost.dialogs', () => {
    const rt = normalizeExtensionRuntime([withAll]);
    expect(rt.config.dialogHost.dialogs).toHaveLength(1);
    expect(rt.config.dialogHost.dialogs[0].id).toBe('dlg');
    expect(rt.config.dialogHost.dialogs[0].layer).toBe('modal');
  });

  it('projects panel contributions onto registry.panels', () => {
    const rt = normalizeExtensionRuntime([withAll]);
    expect(rt.config.registry.panels).toHaveLength(1);
    expect(rt.config.registry.panels[0].id).toBe('pnl');
  });

  it('projects inspectorSection contributions onto registry.inspectorSections', () => {
    const rt = normalizeExtensionRuntime([withAll]);
    expect(rt.config.registry.inspectorSections).toHaveLength(1);
    expect(rt.config.registry.inspectorSections[0].id).toBe('insp');
    expect(rt.config.registry.inspectorSections[0].placement).toBe('before-default');
  });
});

// ---------------------------------------------------------------------------
// Deterministic ordering
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — deterministic ordering', () => {
  it('orders contributions by order ascending, then by ID alphabetically', () => {
    const ex = ext('com.example.order', {
      manifest: {
        contributions: [
          { id: 'z-last' as any, kind: 'slot', slot: 'statusBar', order: 100 },
          { id: 'a-first' as any, kind: 'slot', slot: 'statusBar', order: 0 },
          { id: 'm-middle' as any, kind: 'slot', slot: 'statusBar', order: 50 },
          { id: 'b-second' as any, kind: 'slot', slot: 'statusBar', order: 0 },
        ],
      },
    });

    const rt = normalizeExtensionRuntime([ex]);

    // We can't directly inspect slot ordering since slots is a Record,
    // but we can verify via dialogs which preserve insertion order.
    const ex2 = ext('com.example.order2', {
      manifest: {
        contributions: [
          { id: 'z-last' as any, kind: 'dialog', order: 100 },
          { id: 'a-first' as any, kind: 'dialog', order: 0 },
          { id: 'm-middle' as any, kind: 'dialog', order: 50 },
          { id: 'b-second' as any, kind: 'dialog', order: 0 },
        ],
      },
    });

    const rt2 = normalizeExtensionRuntime([ex2]);
    const ids = rt2.config.dialogHost.dialogs.map((d) => d.id);
    // order=0: 'a-first' < 'b-second' alphabetically
    // order=50: 'm-middle'
    // order=100: 'z-last'
    expect(ids).toEqual(['a-first', 'b-second', 'm-middle', 'z-last']);
  });

  it('treats missing order as 0', () => {
    const ex = ext('com.example.noorder', {
      manifest: {
        contributions: [
          { id: 'bbb' as any, kind: 'dialog', order: 10 },
          { id: 'aaa' as any, kind: 'dialog' }, // no order
          { id: 'ccc' as any, kind: 'dialog', order: 10 },
        ],
      },
    });

    const rt = normalizeExtensionRuntime([ex]);
    const ids = rt.config.dialogHost.dialogs.map((d) => d.id);
    // order=0: aaa
    // order=10: bbb, ccc (bbb < ccc alphabetically)
    expect(ids).toEqual(['aaa', 'bbb', 'ccc']);
  });
});

// ---------------------------------------------------------------------------
// Duplicate extension IDs
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — duplicate extension IDs', () => {
  const extA = ext('com.example.dup');
  const extB = ext('com.example.dup', {
    manifest: { label: 'second copy' },
  });

  it('emits an error diagnostic for duplicate extension ID', () => {
    const rt = normalizeExtensionRuntime([extA, extB]);
    const dups = diagsOf(rt, 'runtime/duplicate-extension');
    expect(dups).toHaveLength(1);
    expect(dups[0].severity).toBe('error');
    expect(dups[0].extensionId).toBe('com.example.dup');
  });

  it('keeps only the first occurrence', () => {
    const rt = normalizeExtensionRuntime([extA, extB]);
    expect(rt.extensions).toHaveLength(1);
    expect((rt.extensions[0].manifest as any).label).toBe('com.example.dup');
  });

  it('handles multiple duplicates gracefully', () => {
    const rt = normalizeExtensionRuntime([extA, extB, ext('com.example.dup')]);
    const dups = diagsOf(rt, 'runtime/duplicate-extension');
    expect(dups).toHaveLength(2); // second and third are duplicates
    expect(rt.extensions).toHaveLength(1);
  });

  it('does not crash on all-duplicate input', () => {
    const rt = normalizeExtensionRuntime([extA, extB]);
    expect(rt.diagnostics.length).toBeGreaterThanOrEqual(1);
    expect(Object.isFrozen(rt)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Duplicate contribution IDs (cross-extension)
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — duplicate contribution IDs', () => {
  const ext1 = ext('com.example.one', {
    manifest: {
      contributions: [
        { id: 'shared-btn' as any, kind: 'slot', slot: 'toolbar', order: 0 },
      ],
    },
  });
  const ext2 = ext('com.example.two', {
    manifest: {
      contributions: [
        { id: 'shared-btn' as any, kind: 'slot', slot: 'statusBar', order: 10 },
      ],
    },
  });

  it('emits an error diagnostic for cross-extension duplicate contribution ID', () => {
    const rt = normalizeExtensionRuntime([ext1, ext2]);
    const dups = diagsOf(rt, 'runtime/duplicate-contribution');
    expect(dups).toHaveLength(1);
    expect(dups[0].severity).toBe('error');
    expect(dups[0].contributionId).toBe('shared-btn');
    expect(dups[0].extensionId).toBe('com.example.two');
  });

  it('skips the duplicate contribution (first owner wins)', () => {
    const rt = normalizeExtensionRuntime([ext1, ext2]);
    // The first extension's slot contribution should be present
    expect(rt.config.slots).toHaveProperty('toolbar');
    // The second extension's duplicate should be skipped
    expect(rt.config.slots).not.toHaveProperty('statusBar');
  });
});

// ---------------------------------------------------------------------------
// Inactive reserved contributions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — inactive reserved contributions', () => {
  const withReserved = ext('com.example.future', {
    manifest: {
      contributions: [
        { id: 'my-effect' as any, kind: 'effect', effectId: 'glow' },
        { id: 'my-transition' as any, kind: 'transition', transitionId: 'dissolve' },
        { id: 'my-clip' as any, kind: 'clipType', clipTypeId: 'title' },
        { id: 'my-parser' as any, kind: 'parser' },
        { id: 'my-agent-tool' as any, kind: 'agentTool' },
        { id: 'my-agent' as any, kind: 'agent' },
      ],
    },
  });

  it('collects inactive reserved contributions', () => {
    const rt = normalizeExtensionRuntime([withReserved]);
    expect(rt.inactiveReserved).toHaveLength(6);
    const kinds = rt.inactiveReserved.map((r: InactiveReservedContribution) => r.kind);
    expect(kinds.sort()).toEqual([
      'agent', 'agentTool', 'clipType', 'effect', 'parser', 'transition',
    ]);
  });

  it('emits info diagnostics for each reserved contribution', () => {
    const rt = normalizeExtensionRuntime([withReserved]);
    const infos = diagsOf(rt, 'runtime/contribution-kind-not-yet-bridged');
    expect(infos).toHaveLength(6);
    for (const d of infos) {
      expect(d.severity).toBe('info');
      expect(d.milestone).toBeTruthy();
    }
  });

  it('preserves DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME when all contributions are reserved', () => {
    const rt = normalizeExtensionRuntime([withReserved]);
    expect(rt.config).toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
  });

  it('includes milestones in inactive reserved entries', () => {
    const rt = normalizeExtensionRuntime([withReserved]);
    const effect = rt.inactiveReserved.find((r) => r.kind === 'effect')!;
    expect(effect.milestone).toBe('M3');
    const agent = rt.inactiveReserved.find((r) => r.kind === 'agent')!;
    expect(agent.milestone).toBe('M5');
  });
});

// ---------------------------------------------------------------------------
// Known render IDs
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — known render IDs', () => {
  it('collects render IDs from contributions that declare them', () => {
    const ex = ext('com.example.renders', {
      manifest: {
        contributions: [
          { id: 'r1' as any, kind: 'slot', slot: 'toolbar', render: 'render/btn' },
          { id: 'r2' as any, kind: 'dialog', render: 'render/dlg' },
          { id: 'r3' as any, kind: 'effect', effectId: 'glow', render: 'render/glow' },
        ],
      },
    });

    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.knownRenderIds.has('render/btn')).toBe(true);
    expect(rt.knownRenderIds.has('render/dlg')).toBe(true);
    // Inactive reserved also collect render IDs
    expect(rt.knownRenderIds.has('render/glow')).toBe(true);
    expect(rt.knownRenderIds.size).toBe(3);
  });

  it('returns an empty frozen set when no render IDs are declared', () => {
    const ex = ext('com.example.norender');
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.knownRenderIds.size).toBe(0);
    expect(Object.isFrozen(rt.knownRenderIds)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Settings defaults
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — settings defaults', () => {
  it('creates an empty settings bucket per extension', () => {
    const ex1 = ext('com.example.a');
    const ex2 = ext('com.example.b');
    const rt = normalizeExtensionRuntime([ex1, ex2]);

    expect(Object.keys(rt.settingsDefaults).sort()).toEqual(['com.example.a', 'com.example.b']);
    expect(rt.settingsDefaults['com.example.a']).toEqual({});
    expect(rt.settingsDefaults['com.example.b']).toEqual({});
  });

  it('freezes each settings bucket', () => {
    const ex = ext('com.example.settings');
    const rt = normalizeExtensionRuntime([ex]);
    expect(Object.isFrozen(rt.settingsDefaults['com.example.settings'])).toBe(true);
  });

  it('excludes duplicate extensions from settings defaults', () => {
    const ex1 = ext('com.example.dup');
    const ex2 = ext('com.example.dup', { manifest: { label: 'copy' } });
    const rt = normalizeExtensionRuntime([ex1, ex2]);
    expect(Object.keys(rt.settingsDefaults)).toEqual(['com.example.dup']);
  });
});

// ---------------------------------------------------------------------------
// Freezing / mutability guard
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — freezing', () => {
  it('throws when attempting to mutate the runtime', () => {
    const ex = ext('com.example.frozen', {
      manifest: {
        contributions: [
          { id: 'btn' as any, kind: 'slot', slot: 'toolbar' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);

    expect(() => {
      (rt as any).config = null;
    }).toThrow();

    expect(() => {
      (rt.diagnostics as any[]).push({ severity: 'error', code: 'x', message: 'x' });
    }).toThrow();
  });

  it('throws when attempting to mutate the config', () => {
    const ex = ext('com.example.frozen2', {
      manifest: {
        contributions: [
          { id: 'dlg' as any, kind: 'dialog' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);

    expect(() => {
      (rt.config.dialogHost.dialogs as any[]).push({ id: 'x', render: () => null });
    }).toThrow();
  });
});

// ---------------------------------------------------------------------------
// Mixed: bridged + reserved contributions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — mixed bridged and reserved', () => {
  const mixed = ext('com.example.mixed', {
    manifest: {
      contributions: [
        { id: 'active-btn' as any, kind: 'slot', slot: 'toolbar', order: 0 },
        { id: 'future-fx' as any, kind: 'effect', effectId: 'blur', order: 100 },
        { id: 'active-dlg' as any, kind: 'dialog', order: 50 },
      ],
    },
  });

  it('separates bridged from reserved contributions', () => {
    const rt = normalizeExtensionRuntime([mixed]);
    // Bridged: active-btn, active-dlg
    expect(rt.config.slots).toHaveProperty('toolbar');
    expect(rt.config.dialogHost.dialogs).toHaveLength(1);
    // Reserved: future-fx
    expect(rt.inactiveReserved).toHaveLength(1);
    expect(rt.inactiveReserved[0].contributionId).toBe('future-fx');
  });

  it('does not use DEFAULT when there are bridged contributions', () => {
    const rt = normalizeExtensionRuntime([mixed]);
    expect(rt.config).not.toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
  });

  it('includes both bridged and reserved diagnostics', () => {
    const rt = normalizeExtensionRuntime([mixed]);
    const reserved = diagsOf(rt, 'runtime/contribution-kind-not-yet-bridged');
    expect(reserved).toHaveLength(1);
    expect(reserved[0].contributionId).toBe('future-fx');
  });
});

// ---------------------------------------------------------------------------
// Multiple extensions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — multiple extensions', () => {
  const ext1 = ext('com.example.first', {
    manifest: {
      contributions: [
        { id: 'first-btn' as any, kind: 'slot', slot: 'toolbar', order: 10 },
      ],
    },
  });
  const ext2 = ext('com.example.second', {
    manifest: {
      contributions: [
        { id: 'second-btn' as any, kind: 'slot', slot: 'statusBar', order: 5 },
        { id: 'second-dlg' as any, kind: 'dialog', order: 20 },
      ],
    },
  });

  it('merges contributions from multiple extensions', () => {
    const rt = normalizeExtensionRuntime([ext1, ext2]);
    expect(Object.keys(rt.config.slots).sort()).toEqual(['statusBar', 'toolbar']);
    expect(rt.config.dialogHost.dialogs).toHaveLength(1);
    expect(rt.config.dialogHost.dialogs[0].id).toBe('second-dlg');
  });

  it('lists all extensions in order', () => {
    const rt = normalizeExtensionRuntime([ext1, ext2]);
    expect(rt.extensions).toHaveLength(2);
    expect((rt.extensions[0].manifest.id as string)).toBe('com.example.first');
    expect((rt.extensions[1].manifest.id as string)).toBe('com.example.second');
  });

  it('has no duplicate diagnostics for valid extensions', () => {
    const rt = normalizeExtensionRuntime([ext1, ext2]);
    const dupExts = diagsOf(rt, 'runtime/duplicate-extension');
    const dupConts = diagsOf(rt, 'runtime/duplicate-contribution');
    expect(dupExts).toEqual([]);
    expect(dupConts).toEqual([]);
  });

  it('initializes settings defaults for all extensions', () => {
    const rt = normalizeExtensionRuntime([ext1, ext2]);
    expect(Object.keys(rt.settingsDefaults).sort()).toEqual([
      'com.example.first',
      'com.example.second',
    ]);
  });
});

// ---------------------------------------------------------------------------
// timelineOverlay contributions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — timelineOverlay', () => {
  it('bridges timelineOverlay contributions into config.overlays', () => {
    const overlayExt = ext('com.example.overlay', {
      manifest: {
        contributions: [
          { id: 'my-overlay' as any, kind: 'timelineOverlay', order: 5 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([overlayExt]);
    expect(rt.config.overlays).toHaveLength(1);
    expect(rt.config.overlays[0].id).toBe('my-overlay');
    expect(rt.config.overlays[0].order).toBe(5);
  });

  it('orders multiple timelineOverlay contributions deterministically', () => {
    const extA = ext('com.example.a', {
      manifest: {
        contributions: [
          { id: 'zzz-overlay' as any, kind: 'timelineOverlay', order: 10 },
          { id: 'aaa-overlay' as any, kind: 'timelineOverlay', order: 10 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA]);
    expect(rt.config.overlays).toHaveLength(2);
    // Same order → alphabetical by ID
    expect(rt.config.overlays[0].id).toBe('aaa-overlay');
    expect(rt.config.overlays[1].id).toBe('zzz-overlay');
  });

  it('does NOT mark timelineOverlay as inactive reserved', () => {
    const overlayExt = ext('com.example.overlay', {
      manifest: {
        contributions: [
          { id: 'my-overlay' as any, kind: 'timelineOverlay' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([overlayExt]);
    const reserved = rt.inactiveReserved.filter(
      (r: InactiveReservedContribution) => r.kind === 'timelineOverlay',
    );
    expect(reserved).toEqual([]);
  });

  it('preserves empty overlays identity when no timelineOverlay contributions exist', () => {
    const extA = ext('com.example.slot-only', {
      manifest: {
        contributions: [
          { id: 'btn' as any, kind: 'slot', slot: 'toolbar' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA]);
    expect(rt.config.overlays).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// getTimelineOverlayContributions
// ---------------------------------------------------------------------------

describe('getTimelineOverlayContributions', () => {
  const baseRenderProps: Omit<TimelineOverlayRenderProps, 'pointerClaimed' | 'claimPointer' | 'releasePointer'> = {
    scrollLeft: 0,
    scrollTop: 0,
    viewportWidth: 800,
    viewportHeight: 600,
    totalWidth: 2000,
    totalHeight: 400,
    pixelsPerSecond: 30,
    startLeft: 160,
    playheadTime: 5,
    isPlaying: false,
    selectedClipIds: new Set<string>(),
    selectedTrackId: null,
    gestureOwner: 'none',
    setGestureOwner: () => {},
  };

  it('returns an empty frozen array when overlays list is empty', () => {
    const result = getTimelineOverlayContributions(
      [],
      { ...baseRenderProps, claimPointer: () => {}, releasePointer: () => {} },
      null,
    );
    expect(result).toEqual([]);
  });
});
