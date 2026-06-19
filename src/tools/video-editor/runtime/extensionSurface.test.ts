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
    // parser is M6-active (bridged) — only 5 reserved kinds remain
    expect(rt.inactiveReserved).toHaveLength(5);
    const kinds = rt.inactiveReserved.map((r: InactiveReservedContribution) => r.kind);
    expect(kinds.sort()).toEqual([
      'agent', 'agentTool', 'clipType', 'effect', 'transition',
    ]);
  });

  it('emits info diagnostics for each reserved contribution', () => {
    const rt = normalizeExtensionRuntime([withReserved]);
    const infos = diagsOf(rt, 'runtime/contribution-kind-not-yet-bridged');
    // parser is M6-active (bridged) — only 5 reserved diagnostics remain
    expect(infos).toHaveLength(5);
    for (const d of infos) {
      expect(d.severity).toBe('info');
      expect(d.milestone).toBeTruthy();
    }
  });

  it('does not preserve DEFAULT when parser is bridged (M6-active)', () => {
    const rt = normalizeExtensionRuntime([withReserved]);
    // parser is M6-active, so config includes assetParsers and is not DEFAULT
    expect(rt.config).not.toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
    expect(rt.config.assetParsers).toHaveLength(1);
    expect(rt.config.assetParsers[0].id).toBe('my-parser');
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

// ---------------------------------------------------------------------------
// M6: Parser contributions (bridged, M6-active)
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 parser contributions', () => {
  it('projects parser contributions into config.assetParsers', () => {
    const ex = ext('com.example.parser', {
      manifest: {
        contributions: [
          { id: 'image-parser' as any, kind: 'parser', label: 'Image Parser', acceptMimeTypes: ['image/png', 'image/jpeg'], acceptExtensions: ['png', 'jpg'], maxBytes: 10_000_000, required: false, order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.assetParsers).toHaveLength(1);
    const p = rt.config.assetParsers[0];
    expect(p.id).toBe('image-parser');
    expect(p.extensionId).toBe('com.example.parser');
    expect(p.label).toBe('Image Parser');
    expect(p.acceptMimeTypes).toEqual(['image/png', 'image/jpeg']);
    expect(p.acceptExtensions).toEqual(['png', 'jpg']);
    expect(p.maxBytes).toBe(10_000_000);
    expect(p.required).toBe(false);
    expect(p.order).toBe(0);
  });

  it('projects parser contributions into runtime.assetParsers (same as config)', () => {
    const ex = ext('com.example.parser', {
      manifest: {
        contributions: [
          { id: 'image-parser' as any, kind: 'parser', label: 'Image Parser' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.assetParsers).toBe(rt.config.assetParsers);
    expect(rt.assetParsers).toHaveLength(1);
  });

  it('falls back to contribution ID as label when label is omitted', () => {
    const ex = ext('com.example.parser', {
      manifest: {
        contributions: [
          { id: 'default-label-parser' as any, kind: 'parser' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.assetParsers[0].label).toBe('default-label-parser');
  });

  it('orders multiple parsers by extension order, then contribution order, then ID', () => {
    const extA = ext('com.example.first', {
      manifest: {
        contributions: [
          { id: 'z-parser' as any, kind: 'parser', order: 0 },
          { id: 'a-parser' as any, kind: 'parser', order: 0 },
        ],
      },
    });
    const extB = ext('com.example.second', {
      manifest: {
        contributions: [
          { id: 'early-parser' as any, kind: 'parser', order: -10 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);
    expect(rt.config.assetParsers).toHaveLength(3);
    // extA (index 0) comes first, then extB (index 1)
    // Within extA: order=0, a-parser < z-parser alphabetically
    const ids = rt.config.assetParsers.map((p) => p.id);
    expect(ids).toEqual(['a-parser', 'z-parser', 'early-parser']);
  });

  it('does not mark parser as inactive reserved (M6-active)', () => {
    const ex = ext('com.example.parser', {
      manifest: {
        contributions: [
          { id: 'my-parser' as any, kind: 'parser' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const reserved = rt.inactiveReserved.filter((r) => r.kind === 'parser');
    expect(reserved).toEqual([]);
  });

  it('does not emit reserved diagnostics for parser', () => {
    const ex = ext('com.example.parser', {
      manifest: {
        contributions: [
          { id: 'my-parser' as any, kind: 'parser' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const infos = diagsOf(rt, 'runtime/contribution-kind-not-yet-bridged');
    expect(infos).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// M6: Metadata facet contributions (bridged, M6-active)
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 metadata facet contributions', () => {
  it('projects metadataFacet contributions into config.metadataFacets', () => {
    const ex = ext('com.example.facets', {
      manifest: {
        contributions: [
          { id: 'gps-facet' as any, kind: 'metadataFacet', fieldPath: 'gps.latitude', displayName: 'GPS Latitude', valueKind: 'number' as const, order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.metadataFacets).toHaveLength(1);
    const f = rt.config.metadataFacets[0];
    expect(f.id).toBe('gps-facet');
    expect(f.extensionId).toBe('com.example.facets');
    expect(f.fieldPath).toBe('gps.latitude');
    expect(f.displayName).toBe('GPS Latitude');
    expect(f.valueKind).toBe('number');
  });

  it('projects metadataFacet contributions into runtime.metadataFacets (same as config)', () => {
    const ex = ext('com.example.facets', {
      manifest: {
        contributions: [
          { id: 'gps-facet' as any, kind: 'metadataFacet', fieldPath: 'gps.latitude', displayName: 'GPS', valueKind: 'number' as const },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.metadataFacets).toBe(rt.config.metadataFacets);
  });

  it('passes through aggregationPosture and enumValues', () => {
    const ex = ext('com.example.facets', {
      manifest: {
        contributions: [
          { id: 'rights-facet' as any, kind: 'metadataFacet', fieldPath: 'consent.rightsNote', displayName: 'Rights', valueKind: 'enum' as const, aggregationPosture: 'exact' as const, enumValues: ['CC BY 4.0', 'All Rights Reserved'] },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const f = rt.config.metadataFacets[0];
    expect(f.aggregationPosture).toBe('exact');
    expect(f.enumValues).toEqual(['CC BY 4.0', 'All Rights Reserved']);
  });

  it('does not mark metadataFacet as inactive reserved (M6-active)', () => {
    const ex = ext('com.example.facets', {
      manifest: {
        contributions: [
          { id: 'my-facet' as any, kind: 'metadataFacet', fieldPath: 'gps.latitude', displayName: 'GPS', valueKind: 'number' as const },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const reserved = rt.inactiveReserved.filter((r) => r.kind === 'metadataFacet');
    expect(reserved).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// M6: Asset detail section contributions (bridged, M6-active)
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 asset detail section contributions', () => {
  it('projects assetDetailSection contributions into config.assetDetailSections', () => {
    const ex = ext('com.example.sections', {
      manifest: {
        contributions: [
          { id: 'integrity-section' as any, kind: 'assetDetailSection', title: 'Integrity', placement: 'after-default' as const, fieldPaths: ['integrity.algorithm', 'integrity.hash'], order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.assetDetailSections).toHaveLength(1);
    const s = rt.config.assetDetailSections[0];
    expect(s.id).toBe('integrity-section');
    expect(s.extensionId).toBe('com.example.sections');
    expect(s.title).toBe('Integrity');
    expect(s.placement).toBe('after-default');
    expect(s.fieldPaths).toEqual(['integrity.algorithm', 'integrity.hash']);
  });

  it('projects assetDetailSection contributions into runtime.assetDetailSections (same as config)', () => {
    const ex = ext('com.example.sections', {
      manifest: {
        contributions: [
          { id: 'integrity-section' as any, kind: 'assetDetailSection', title: 'Integrity', placement: 'after-default' as const },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.assetDetailSections).toBe(rt.config.assetDetailSections);
  });

  it('passes through when predicate', () => {
    const ex = ext('com.example.sections', {
      manifest: {
        contributions: [
          { id: 'conditional-section' as any, kind: 'assetDetailSection', title: 'Conditional', placement: 'before-default' as const, when: 'asset.metadata.integrity != null' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.assetDetailSections[0].when).toBe('asset.metadata.integrity != null');
  });

  it('does not mark assetDetailSection as inactive reserved (M6-active)', () => {
    const ex = ext('com.example.sections', {
      manifest: {
        contributions: [
          { id: 'my-section' as any, kind: 'assetDetailSection', title: 'Detail', placement: 'after-default' as const },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const reserved = rt.inactiveReserved.filter((r) => r.kind === 'assetDetailSection');
    expect(reserved).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// M6: OutputFormat contributions (reserved, surfaced as disabled diagnostics)
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 output format contributions', () => {
  it('surfaces compile-only outputFormat as enabled in config.outputFormats', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'Metadata JSON', requiresRender: false, outputExtension: 'json', outputMimeType: 'application/json', description: 'Export metadata as JSON', order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.outputFormats).toHaveLength(1);
    const of = rt.config.outputFormats[0];
    expect(of.id).toBe('metadata-json');
    expect(of.extensionId).toBe('com.example.export');
    expect(of.label).toBe('Metadata JSON');
    expect(of.requiresRender).toBe(false);
    expect(of.outputExtension).toBe('json');
    expect(of.outputMimeType).toBe('application/json');
    expect(of.description).toBe('Export metadata as JSON');
    expect(of.disabled).toBe(false);
    expect(of.disabledReason).toBeUndefined();
  });

  it('surfaces render-dependent outputFormat as disabled with diagnostic', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'mp4-video' as any, kind: 'outputFormat', label: 'MP4 Video', requiresRender: true, outputExtension: 'mp4', outputMimeType: 'video/mp4', description: 'Render timeline to MP4', order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.outputFormats).toHaveLength(1);
    const of = rt.config.outputFormats[0];
    expect(of.id).toBe('mp4-video');
    expect(of.requiresRender).toBe(true);
    expect(of.disabled).toBe(true);
    expect(of.disabledReason).toContain('requires render planning');
    expect(of.disabledReason).toContain('not yet available in M6');
  });

  it('projects outputFormat into runtime.outputFormats (same as config)', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.outputFormats).toBe(rt.config.outputFormats);
  });

  it('marks outputFormat as inactive reserved with M6 milestone', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const reserved = rt.inactiveReserved.filter((r) => r.kind === 'outputFormat');
    expect(reserved).toHaveLength(1);
    expect(reserved[0].milestone).toBe('M6');
    expect(reserved[0].contributionId).toBe('metadata-json');
  });

  it('emits info diagnostic for outputFormat', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const infos = diagsOf(rt, 'runtime/contribution-kind-not-yet-bridged');
    expect(infos).toHaveLength(1);
    expect(infos[0].contributionId).toBe('metadata-json');
    // kind is on inactiveReserved, not on the diagnostic
    const reserved = rt.inactiveReserved.find((r) => r.contributionId === 'metadata-json');
    expect(reserved).toBeDefined();
    expect(reserved!.kind).toBe('outputFormat');
  });

  it('orders output formats by extension order, then contribution order, then ID', () => {
    const extA = ext('com.example.first', {
      manifest: {
        contributions: [
          { id: 'z-format' as any, kind: 'outputFormat', label: 'Z', requiresRender: false, outputExtension: 'z', order: 0 },
          { id: 'a-format' as any, kind: 'outputFormat', label: 'A', requiresRender: false, outputExtension: 'a', order: 0 },
        ],
      },
    });
    const extB = ext('com.example.second', {
      manifest: {
        contributions: [
          { id: 'early-format' as any, kind: 'outputFormat', label: 'Early', requiresRender: false, outputExtension: 'early', order: -10 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);
    expect(rt.config.outputFormats).toHaveLength(3);
    // extA (index 0) first, extB (index 1) second
    const ids = rt.config.outputFormats.map((f) => f.id);
    expect(ids).toEqual(['a-format', 'z-format', 'early-format']);
  });

  it('creates non-DEFAULT config when only outputFormat contributions exist', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'metadata-json' as any, kind: 'outputFormat', label: 'JSON', requiresRender: false, outputExtension: 'json' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    // Config should NOT be DEFAULT because outputFormat descriptors need to be surfaced
    expect(rt.config).not.toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
    expect(rt.config.outputFormats).toHaveLength(1);
    // But slots/dialogs/panels should still be empty
    expect(Object.keys(rt.config.slots)).toEqual([]);
    expect(rt.config.dialogHost.dialogs).toEqual([]);
  });

  it('falls back to contribution ID as label when label is omitted', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'default-label-format' as any, kind: 'outputFormat', requiresRender: false, outputExtension: 'json' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.outputFormats[0].label).toBe('default-label-format');
  });

  it('defaults requiresRender to false when omitted', () => {
    const ex = ext('com.example.export', {
      manifest: {
        contributions: [
          { id: 'no-render-flag' as any, kind: 'outputFormat', outputExtension: 'json' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.outputFormats[0].requiresRender).toBe(false);
    expect(rt.config.outputFormats[0].disabled).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// M6: Search provider contributions (reserved, surfaced as declaration-only)
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 search provider contributions', () => {
  it('surfaces searchProvider in config.searchProviders', () => {
    const ex = ext('com.example.search', {
      manifest: {
        contributions: [
          { id: 'semantic-search' as any, kind: 'searchProvider', label: 'Semantic Search', description: 'Semantic search over image embeddings', resultKinds: ['asset'] as const, order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.searchProviders).toHaveLength(1);
    const sp = rt.config.searchProviders[0];
    expect(sp.id).toBe('semantic-search');
    expect(sp.extensionId).toBe('com.example.search');
    expect(sp.label).toBe('Semantic Search');
    expect(sp.description).toBe('Semantic search over image embeddings');
    expect(sp.resultKinds).toEqual(['asset']);
  });

  it('projects searchProvider into runtime.searchProviders (same as config)', () => {
    const ex = ext('com.example.search', {
      manifest: {
        contributions: [
          { id: 'semantic-search' as any, kind: 'searchProvider', label: 'Search' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.searchProviders).toBe(rt.config.searchProviders);
  });

  it('marks searchProvider as inactive reserved with M6 milestone', () => {
    const ex = ext('com.example.search', {
      manifest: {
        contributions: [
          { id: 'semantic-search' as any, kind: 'searchProvider', label: 'Search' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const reserved = rt.inactiveReserved.filter((r) => r.kind === 'searchProvider');
    expect(reserved).toHaveLength(1);
    expect(reserved[0].milestone).toBe('M6');
    expect(reserved[0].contributionId).toBe('semantic-search');
  });

  it('emits info diagnostic for searchProvider', () => {
    const ex = ext('com.example.search', {
      manifest: {
        contributions: [
          { id: 'semantic-search' as any, kind: 'searchProvider', label: 'Search' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const infos = diagsOf(rt, 'runtime/contribution-kind-not-yet-bridged');
    expect(infos).toHaveLength(1);
    expect(infos[0].contributionId).toBe('semantic-search');
    // kind is on inactiveReserved, not on the diagnostic
    const reserved = rt.inactiveReserved.find((r) => r.contributionId === 'semantic-search');
    expect(reserved).toBeDefined();
    expect(reserved!.kind).toBe('searchProvider');
  });

  it('orders search providers by extension order, then contribution order, then ID', () => {
    const extA = ext('com.example.first', {
      manifest: {
        contributions: [
          { id: 'z-search' as any, kind: 'searchProvider', label: 'Z', order: 0 },
          { id: 'a-search' as any, kind: 'searchProvider', label: 'A', order: 0 },
        ],
      },
    });
    const extB = ext('com.example.second', {
      manifest: {
        contributions: [
          { id: 'early-search' as any, kind: 'searchProvider', label: 'Early', order: -10 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);
    expect(rt.config.searchProviders).toHaveLength(3);
    // extA (index 0) first, extB (index 1) second
    const ids = rt.config.searchProviders.map((s) => s.id);
    expect(ids).toEqual(['a-search', 'z-search', 'early-search']);
  });

  it('creates non-DEFAULT config when only searchProvider contributions exist', () => {
    const ex = ext('com.example.search', {
      manifest: {
        contributions: [
          { id: 'semantic-search' as any, kind: 'searchProvider', label: 'Search' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config).not.toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
    expect(rt.config.searchProviders).toHaveLength(1);
    expect(Object.keys(rt.config.slots)).toEqual([]);
  });

  it('falls back to contribution ID as label when label is omitted', () => {
    const ex = ext('com.example.search', {
      manifest: {
        contributions: [
          { id: 'default-label-search' as any, kind: 'searchProvider' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    expect(rt.config.searchProviders[0].label).toBe('default-label-search');
  });
});

// ---------------------------------------------------------------------------
// M6: All contributions — extension-order-respecting ordering
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 extension-order ordering', () => {
  it('groups all contributions by extension order before contribution order', () => {
    // Extension com.example.b (index 1) has lower contribution orders than com.example.a (index 0)
    // But com.example.a contributions should come first because com.example.a is listed first
    const extA = ext('com.example.a', {
      manifest: {
        contributions: [
          { id: 'a-dialog' as any, kind: 'dialog', order: 100 },
          { id: 'a-parser' as any, kind: 'parser', order: 100 },
        ],
      },
    });
    const extB = ext('com.example.b', {
      manifest: {
        contributions: [
          { id: 'b-dialog' as any, kind: 'dialog', order: 0 },
          { id: 'b-parser' as any, kind: 'parser', order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);
    // Dialogs preserve insertion order, so we can check ordering
    const dialogIds = rt.config.dialogHost.dialogs.map((d) => d.id);
    // extA (index 0) then extB (index 1)
    expect(dialogIds).toEqual(['a-dialog', 'b-dialog']);
    // Parsers also
    const parserIds = rt.config.assetParsers.map((p) => p.id);
    expect(parserIds).toEqual(['a-parser', 'b-parser']);
  });

  it('respects extension order for M6-reserved contributions too (outputFormats)', () => {
    const extA = ext('com.example.a', {
      manifest: {
        contributions: [
          { id: 'a-output' as any, kind: 'outputFormat', label: 'A', requiresRender: false, outputExtension: 'a', order: 100 },
        ],
      },
    });
    const extB = ext('com.example.b', {
      manifest: {
        contributions: [
          { id: 'b-output' as any, kind: 'outputFormat', label: 'B', requiresRender: false, outputExtension: 'b', order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);
    const ids = rt.config.outputFormats.map((f) => f.id);
    expect(ids).toEqual(['a-output', 'b-output']);
  });

  it('respects extension order for M6-reserved contributions too (searchProviders)', () => {
    const extA = ext('com.example.a', {
      manifest: {
        contributions: [
          { id: 'a-search' as any, kind: 'searchProvider', label: 'A', order: 100 },
        ],
      },
    });
    const extB = ext('com.example.b', {
      manifest: {
        contributions: [
          { id: 'b-search' as any, kind: 'searchProvider', label: 'B', order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);
    const ids = rt.config.searchProviders.map((s) => s.id);
    expect(ids).toEqual(['a-search', 'b-search']);
  });

  it('falls back to stable ID ordering within same extension and same order', () => {
    const ex = ext('com.example.order', {
      manifest: {
        contributions: [
          { id: 'z-parser' as any, kind: 'parser', order: 0 },
          { id: 'a-parser' as any, kind: 'parser', order: 0 },
          { id: 'm-parser' as any, kind: 'parser', order: 0 },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([ex]);
    const ids = rt.config.assetParsers.map((p) => p.id);
    expect(ids).toEqual(['a-parser', 'm-parser', 'z-parser']);
  });
});

// ---------------------------------------------------------------------------
// M6: DEFAULT config field consistency
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 DEFAULT config fields', () => {
  it('has empty frozen arrays for all M6 fields in DEFAULT config', () => {
    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.assetParsers).toEqual([]);
    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.assetParsers)).toBe(true);
    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.outputFormats).toEqual([]);
    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.outputFormats)).toBe(true);
    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.searchProviders).toEqual([]);
    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.searchProviders)).toBe(true);
    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.metadataFacets).toEqual([]);
    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.metadataFacets)).toBe(true);
    expect(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.assetDetailSections).toEqual([]);
    expect(Object.isFrozen(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME.assetDetailSections)).toBe(true);
  });

  it('has all M6 fields in EMPTY_EXTENSION_RUNTIME matching DEFAULT', () => {
    const rt = normalizeExtensionRuntime([]);
    expect(rt.assetParsers).toEqual([]);
    expect(rt.outputFormats).toEqual([]);
    expect(rt.searchProviders).toEqual([]);
    expect(rt.metadataFacets).toEqual([]);
    expect(rt.assetDetailSections).toEqual([]);
    expect(Object.isFrozen(rt.assetParsers)).toBe(true);
    expect(Object.isFrozen(rt.outputFormats)).toBe(true);
    expect(Object.isFrozen(rt.searchProviders)).toBe(true);
    expect(Object.isFrozen(rt.metadataFacets)).toBe(true);
    expect(Object.isFrozen(rt.assetDetailSections)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// M6: Combined M6 contributions across multiple extensions
// ---------------------------------------------------------------------------

describe('normalizeExtensionRuntime — M6 combined contributions', () => {
  it('surfaces all M6 contribution kinds from multiple extensions', () => {
    const extA = ext('com.example.a', {
      manifest: {
        contributions: [
          { id: 'a-parser' as any, kind: 'parser', label: 'A Parser' },
          { id: 'a-facet' as any, kind: 'metadataFacet', fieldPath: 'gps.latitude', displayName: 'GPS', valueKind: 'number' as const },
          { id: 'a-section' as any, kind: 'assetDetailSection', title: 'A Section', placement: 'after-default' as const },
        ],
      },
    });
    const extB = ext('com.example.b', {
      manifest: {
        contributions: [
          { id: 'b-output' as any, kind: 'outputFormat', label: 'B Output', requiresRender: false, outputExtension: 'json' },
          { id: 'b-render-output' as any, kind: 'outputFormat', label: 'B Render', requiresRender: true, outputExtension: 'mp4' },
          { id: 'b-search' as any, kind: 'searchProvider', label: 'B Search' },
        ],
      },
    });
    const rt = normalizeExtensionRuntime([extA, extB]);

    // Bridged M6 contributions (extA first)
    expect(rt.config.assetParsers).toHaveLength(1);
    expect(rt.config.assetParsers[0].id).toBe('a-parser');
    expect(rt.config.metadataFacets).toHaveLength(1);
    expect(rt.config.metadataFacets[0].id).toBe('a-facet');
    expect(rt.config.assetDetailSections).toHaveLength(1);
    expect(rt.config.assetDetailSections[0].id).toBe('a-section');

    // Reserved M6 contributions (extB)
    expect(rt.config.outputFormats).toHaveLength(2);
    expect(rt.config.outputFormats[0].id).toBe('b-output');
    expect(rt.config.outputFormats[0].disabled).toBe(false);
    expect(rt.config.outputFormats[1].id).toBe('b-render-output');
    expect(rt.config.outputFormats[1].disabled).toBe(true);
    expect(rt.config.searchProviders).toHaveLength(1);
    expect(rt.config.searchProviders[0].id).toBe('b-search');

    // Inactive reserved should only contain the reserved kinds (outputFormat, searchProvider)
    const reservedKinds = rt.inactiveReserved.map((r) => r.kind).sort();
    expect(reservedKinds).toEqual(['outputFormat', 'outputFormat', 'searchProvider']);

    // Config should NOT be DEFAULT
    expect(rt.config).not.toBe(DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME);
  });
});
