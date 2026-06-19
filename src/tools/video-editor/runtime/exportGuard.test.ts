import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import {
  collectBuiltInKnownIds,
  collectExtensionDeclaredIds,
  scanExportConfig,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import type {
  KnownIdCollection,
  InactiveKnownIds,
  ExportGuardResult,
} from '@/tools/video-editor/runtime/exportGuard.ts';
import type { ExtensionContribution } from '@reigh/editor-sdk';
import type {
  EffectRegistryRecord,
  EffectRegistrySnapshot,
} from '@/tools/video-editor/effects/registry/types.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeClip(
  id: string,
  overrides?: Partial<ResolvedTimelineConfig['clips'][number]>,
): ResolvedTimelineConfig['clips'][number] {
  return {
    id,
    at: 0,
    track: 'V1',
    clipType: 'media',
    ...overrides,
  };
}

function makeConfig(
  clips: ResolvedTimelineConfig['clips'],
): ResolvedTimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips,
    registry: {},
  };
}

const RegistryEffect: FC<EffectComponentProps> = ({ children }) => children;

function effectRecord(
  effectId: string,
  overrides: Partial<EffectRegistryRecord> = {},
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `test:effect:${effectId}`,
    component: RegistryEffect,
    provenance: 'trusted-loader',
    renderability: {
      defaultRoute: 'preview',
      determinism: 'deterministic',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'deterministic',
        },
        {
          route: 'browser-export',
          status: 'supported',
          determinism: 'deterministic',
        },
      ],
    },
    status: 'active',
    ...overrides,
  };
}

function snapshotWith(records: readonly EffectRegistryRecord[]): EffectRegistrySnapshot {
  const byId = new Map(records.map((record) => [record.effectId, record]));
  return Object.freeze({
    records: Object.freeze([...records]),
    diagnostics: Object.freeze([]),
    get: (effectId: string) => byId.get(effectId),
    has: (effectId: string) => byId.has(effectId),
  });
}

// ---------------------------------------------------------------------------
// Built-in ID collection
// ---------------------------------------------------------------------------

describe('collectBuiltInKnownIds', () => {
  it('returns a frozen KnownIdCollection', () => {
    const ids = collectBuiltInKnownIds();
    expect(Object.isFrozen(ids)).toBe(true);
  });

  it('includes BUILTIN_CLIP_TYPES', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.clipTypes.has('media')).toBe(true);
    expect(ids.clipTypes.has('hold')).toBe(true);
    expect(ids.clipTypes.has('text')).toBe(true);
    expect(ids.clipTypes.has('effect-layer')).toBe(true);
  });

  it('includes TRUSTED_CLIP_TYPES', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.clipTypes.has('image-jump')).toBe(true);
    expect(ids.clipTypes.has('title-card')).toBe(true);
    expect(ids.clipTypes.has('section-hook')).toBe(true);
    expect(ids.clipTypes.has('art-card')).toBe(true);
    expect(ids.clipTypes.has('resource-card')).toBe(true);
    expect(ids.clipTypes.has('cta-card')).toBe(true);
  });

  it('includes built-in entrance effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('slide-up')).toBe(true);
    expect(ids.effectTypes.has('fade')).toBe(true);
    expect(ids.effectTypes.has('zoom-in')).toBe(true);
    expect(ids.effectTypes.has('bounce')).toBe(true);
  });

  it('includes built-in exit effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('fade-out')).toBe(true);
    expect(ids.effectTypes.has('dissolve')).toBe(true);
    expect(ids.effectTypes.has('shrink')).toBe(true);
  });

  it('includes built-in continuous effect types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.effectTypes.has('ken-burns')).toBe(true);
    expect(ids.effectTypes.has('float')).toBe(true);
    expect(ids.effectTypes.has('glitch')).toBe(true);
    expect(ids.effectTypes.has('slow-zoom')).toBe(true);
    expect(ids.effectTypes.has('drift')).toBe(true);
  });

  it('includes built-in transition types', () => {
    const ids = collectBuiltInKnownIds();
    expect(ids.transitionTypes.has('crossfade')).toBe(true);
    expect(ids.transitionTypes.has('wipe')).toBe(true);
    expect(ids.transitionTypes.has('slide-push')).toBe(true);
    expect(ids.transitionTypes.has('zoom-through')).toBe(true);
  });

  it('has no effect/transition overlap with clip types', () => {
    const ids = collectBuiltInKnownIds();
    // Clip types and effect types are separate namespaces
    for (const ct of ids.clipTypes) {
      expect(ids.effectTypes.has(ct)).toBe(false);
    }
  });
});

// ---------------------------------------------------------------------------
// Extension-declared ID collection
// ---------------------------------------------------------------------------

describe('collectExtensionDeclaredIds', () => {
  it('returns frozen empty sets for empty input', () => {
    const result = collectExtensionDeclaredIds([]);
    expect(Object.isFrozen(result)).toBe(true);
    expect(result.effectIds.size).toBe(0);
    expect(result.transitionIds.size).toBe(0);
    expect(result.clipTypeIds.size).toBe(0);
  });

  it('ignores bridged contribution kinds (slot, dialog, panel, inspectorSection)', () => {
    // M1-bridged kinds are skipped — they are active, not inactive
    const contributions: ExtensionContribution[] = [
      { id: 'c1' as any, kind: 'slot', slot: 'toolbar' },
      { id: 'c2' as any, kind: 'dialog' },
      { id: 'c3' as any, kind: 'panel' },
      { id: 'c4' as any, kind: 'inspectorSection' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(0);
    expect(result.transitionIds.size).toBe(0);
    expect(result.clipTypeIds.size).toBe(0);
  });

  it('ignores inactive contributions without effectId/transitionId/clipTypeId', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(0);
  });

  it('collects effectId from effect-kind inactive contributions', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect', effectId: 'my-custom-effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.has('my-custom-effect')).toBe(true);
  });

  it('collects transitionId from transition-kind inactive contributions', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.2' as any, kind: 'transition', transitionId: 'my-custom-transition' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.transitionIds.has('my-custom-transition')).toBe(true);
  });

  it('collects clipTypeId from clipType-kind inactive contributions', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.3' as any, kind: 'clipType', clipTypeId: 'my-custom-clip' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.clipTypeIds.has('my-custom-clip')).toBe(true);
  });

  it('deduplicates across multiple contributions', () => {
    const contributions: ExtensionContribution[] = [
      { id: 'contrib.1' as any, kind: 'effect', effectId: 'shared-effect' },
      { id: 'contrib.2' as any, kind: 'effect', effectId: 'shared-effect' },
    ];
    const result = collectExtensionDeclaredIds(contributions);
    expect(result.effectIds.size).toBe(1);
    expect(result.effectIds.has('shared-effect')).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — empty / null config
// ---------------------------------------------------------------------------

describe('scanExportConfig — empty config', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('returns empty result for null config', () => {
    const result = scanExportConfig(null, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
    expect(Object.isFrozen(result)).toBe(true);
  });

  it('returns empty result for config with no clips', () => {
    const result = scanExportConfig(makeConfig([]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known clip types pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known clip types', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes built-in clip type "media"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'media' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes built-in clip type "text"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'text' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes trusted clip type "title-card"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'title-card' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes trusted clip type "art-card"', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'art-card' })]);
    const result = scanExportConfig(config, builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown clip type
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown clip type', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error diagnostic for truly unknown clip type', () => {
    const config = makeConfig([makeClip('c1', { clipType: 'alien-format' })]);
    const result = scanExportConfig(config, builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    const diag = result.diagnostics[0];
    expect(diag.severity).toBe('error');
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.detail?.clipId).toBe('c1');
    expect(diag.detail?.clipType).toBe('alien-format');
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning diagnostic for extension-declared (inactive) clip type', () => {
    const extIdsWithClip = collectExtensionDeclaredIds([
      {
        id: 'contrib.c' as any,
        kind: 'clipType',
        clipTypeId: 'future-clip',
      } as ExtensionContribution,
    ]);

    const config = makeConfig([makeClip('c1', { clipType: 'future-clip' })]);
    const result = scanExportConfig(config, builtIn, extIdsWithClip);

    expect(result.diagnostics.length).toBe(1);
    const diag = result.diagnostics[0];
    expect(diag.severity).toBe('warning');
    expect(diag.code).toBe('export/unknown-clip-type');
    expect(diag.message).toContain('inactive extension');
    // Extension-declared clip types do NOT appear in unknownClipTypes
    expect(result.unknownClipTypes).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known effects pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known effects', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known entrance effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'fade', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known continuous effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known exit effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'fade-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes provider snapshot effect IDs that are absent from legacy known IDs', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'provider-glow', intensity: 0.5 },
    });
    const snapshot = snapshotWith([effectRecord('provider-glow')]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([]);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown effects
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown effects', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error for unknown entrance effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('crazy-spin');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.unknownEffects).toEqual(['crazy-spin']);
    expect(result.hasBlockingErrors).toBe(true);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.crazy-spin.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
        detail: { effectType: 'crazy-spin', slot: 'entrance' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.entrance.crazy-spin.missing',
        severity: 'error',
        route: 'browser-export',
        reason: 'missing-contribution',
        clipId: 'c1',
      }),
    ]);
  });

  it('emits error for unknown continuous effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'hyperspace', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.unknownEffects).toEqual(['hyperspace']);
  });

  it('emits error for unknown exit effect', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      exit: { type: 'explode-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.unknownEffects).toEqual(['explode-out']);
  });

  it('emits warning for extension-declared (inactive) effect', () => {
    const extIdsWithEffect = collectExtensionDeclaredIds([
      {
        id: 'contrib.e' as any,
        kind: 'effect',
        effectId: 'future-effect',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: { type: 'future-effect', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithEffect);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
    expect(result.findings).toEqual([]);
    expect(result.blockers).toEqual([]);
  });

  it('emits shared export blocker vocabulary for provider snapshot effects that cannot browser-export', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      continuous: { type: 'preview-glow', intensity: 0.5 },
    });
    const snapshot = snapshotWith([
      effectRecord('preview-glow', {
        ownerExtensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'preview-only',
          capabilities: [
            {
              route: 'preview',
              status: 'supported',
              determinism: 'preview-only',
            },
            {
              route: 'browser-export',
              status: 'blocked',
              determinism: 'preview-only',
              blockerReason: 'preview-only',
              message: 'Preview Glow only supports interactive preview.',
            },
          ],
        },
      }),
    ]);

    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds, snapshot);

    expect(result.diagnostics).toEqual([
      expect.objectContaining({
        severity: 'error',
        code: 'export/unrenderable-effect',
        message: 'Preview Glow only supports interactive preview.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        detail: expect.objectContaining({
          clipId: 'c1',
          effectType: 'preview-glow',
          renderRoute: 'browser-export',
          blockerReason: 'preview-only',
        }),
      }),
    ]);
    expect(result.findings).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.continuous.preview-glow.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
        message: 'Preview Glow only supports interactive preview.',
        extensionId: 'ext.preview',
        contributionId: 'ext.preview:effect:preview-glow',
        clipId: 'c1',
        detail: { effectType: 'preview-glow', slot: 'continuous' },
      }),
    ]);
    expect(result.blockers).toEqual([
      expect.objectContaining({
        id: 'export.effect.c1.continuous.preview-glow.preview-only',
        severity: 'error',
        route: 'browser-export',
        reason: 'preview-only',
      }),
    ]);
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — known transitions pass
// ---------------------------------------------------------------------------

describe('scanExportConfig — known transitions', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known transition "crossfade"', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'crossfade', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });

  it('passes known transition "wipe"', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'wipe', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// Export config scan — unknown transitions
// ---------------------------------------------------------------------------

describe('scanExportConfig — unknown transitions', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('emits error for unknown transition', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'star-wipe', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-transition-type');
    expect(result.diagnostics[0].detail?.transitionType).toBe('star-wipe');
    expect(result.unknownTransitions).toEqual(['star-wipe']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for extension-declared (inactive) transition', () => {
    const extIdsWithTrans = collectExtensionDeclaredIds([
      {
        id: 'contrib.t' as any,
        kind: 'transition',
        transitionId: 'future-transition',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'media',
      transition: { type: 'future-transition', duration: 1 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithTrans);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownTransitions).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Multiple diagnostics
// ---------------------------------------------------------------------------

describe('scanExportConfig — multiple diagnostics', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('collects multiple unknown types in one scan', () => {
    const clips = [
      makeClip('c1', {
        clipType: 'alien-format',
        entrance: { type: 'crazy-spin', duration: 0.5 },
      }),
      makeClip('c2', {
        clipType: 'media',
        transition: { type: 'star-wipe', duration: 1 },
        continuous: { type: 'hyperspace', intensity: 0.5 },
      }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 4 diagnostics: unknown clip type + unknown entrance + unknown transition + unknown continuous
    expect(result.diagnostics.length).toBe(4);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
    expect(result.unknownTransitions).toEqual(['star-wipe']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('handles multiple clips with same unknown types without duplication', () => {
    const clips = [
      makeClip('c1', { clipType: 'alien-format' }),
      makeClip('c2', { clipType: 'alien-format' }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 2 diagnostics (one per clip) but only one entry in unknownClipTypes
    expect(result.diagnostics.length).toBe(2);
    expect(result.unknownClipTypes).toEqual(['alien-format']);
  });
});

// ---------------------------------------------------------------------------
// Effect-layer clips (built-in clip type with effects)
// ---------------------------------------------------------------------------

describe('scanExportConfig — effect-layer clips', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('passes known continuous effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'ken-burns', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes known entrance effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      entrance: { type: 'fade', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('passes known exit effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      exit: { type: 'fade-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('emits error for unknown continuous effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'hyperspace', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('hyperspace');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.unknownEffects).toEqual(['hyperspace']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for unknown entrance effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      entrance: { type: 'crazy-spin', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('crazy-spin');
    expect(result.unknownEffects).toEqual(['crazy-spin']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits error for unknown exit effect on effect-layer clip', () => {
    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      exit: { type: 'explode-out', duration: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('error');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('explode-out');
    expect(result.unknownEffects).toEqual(['explode-out']);
    expect(result.hasBlockingErrors).toBe(true);
  });

  it('emits warning for extension-declared continuous effect on effect-layer clip', () => {
    const extIdsWithEffect = collectExtensionDeclaredIds([
      {
        id: 'contrib.el' as any,
        kind: 'effect',
        effectId: 'future-continuous',
      } as ExtensionContribution,
    ]);

    const clip = makeClip('c1', {
      clipType: 'effect-layer',
      continuous: { type: 'future-continuous', intensity: 0.5 },
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIdsWithEffect);

    expect(result.diagnostics.length).toBe(1);
    expect(result.diagnostics[0].severity).toBe('warning');
    expect(result.diagnostics[0].code).toBe('export/unknown-effect-type');
    expect(result.diagnostics[0].detail?.effectType).toBe('future-continuous');
    expect(result.diagnostics[0].detail?.clipId).toBe('c1');
    expect(result.diagnostics[0].message).toContain('inactive extension');
    expect(result.unknownEffects).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Effect-layer clip with unknown clip type + unknown effects combined
// ---------------------------------------------------------------------------

describe('scanExportConfig — effect-layer combined diagnostics', () => {
  it('collects both unknown clip type and unknown effect for effect-layer style clips', () => {
    const builtIn = collectBuiltInKnownIds();
    const extIds = collectExtensionDeclaredIds([]);

    const clips = [
      makeClip('c1', {
        clipType: 'custom-effect-layer',
        continuous: { type: 'hyperspace', intensity: 0.5 },
        entrance: { type: 'crazy-spin', duration: 0.5 },
      }),
    ];
    const result = scanExportConfig(makeConfig(clips), builtIn, extIds);

    // 3 diagnostics: unknown clip type + unknown continuous + unknown entrance
    expect(result.diagnostics.length).toBe(3);
    expect(result.unknownClipTypes).toEqual(['custom-effect-layer']);
    expect(result.unknownEffects).toEqual(['crazy-spin', 'hyperspace']);
    expect(result.hasBlockingErrors).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

describe('scanExportConfig — edge cases', () => {
  const builtIn = collectBuiltInKnownIds();
  const extIds = collectExtensionDeclaredIds([]);

  it('handles clip with no clipType', () => {
    const clip = makeClip('c1', { clipType: undefined });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('handles clip without effects or transitions', () => {
    const clip = makeClip('c1', {
      clipType: 'media',
      entrance: undefined,
      exit: undefined,
      continuous: undefined,
      transition: undefined,
    });
    const result = scanExportConfig(makeConfig([clip]), builtIn, extIds);
    expect(result.diagnostics).toEqual([]);
    expect(result.hasBlockingErrors).toBe(false);
  });

  it('frozen result cannot be mutated', () => {
    const result = scanExportConfig(null, builtIn, extIds);
    expect(() => {
      (result as { diagnostics: unknown[] }).diagnostics = [];
    }).toThrow();
  });

  it('preserves inactiveExtensionIds in result', () => {
    const extIdsWithEffect = collectExtensionDeclaredIds([
      {
        id: 'contrib.e' as any,
        kind: 'effect',
        effectId: 'future-effect',
      } as ExtensionContribution,
    ]);

    const result = scanExportConfig(
      makeConfig([makeClip('c1', { clipType: 'media' })]),
      builtIn,
      extIdsWithEffect,
    );

    expect(result.inactiveExtensionIds.effectIds.has('future-effect')).toBe(true);
  });
});
