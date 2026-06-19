import { describe, expect, it } from 'vitest';
import type { FC } from 'react';
import { planRender } from '@/tools/video-editor/runtime/renderPlanner.ts';
import type { EffectComponentProps } from '@/tools/video-editor/effects/entrances.tsx';
import type { EffectRegistryRecord, EffectRegistrySnapshot } from '@/tools/video-editor/effects/registry/types.ts';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types/index.ts';

const Effect: FC<EffectComponentProps> = ({ children }) => children;

function makeConfig(effectId: string): ResolvedTimelineConfig {
  return {
    output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
    tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
    clips: [{
      id: 'clip-1',
      at: 0,
      track: 'V1',
      clipType: 'media',
      continuous: { type: effectId, params: {} },
    }],
    registry: {},
  } as ResolvedTimelineConfig;
}

function snapshotWith(record: EffectRegistryRecord): EffectRegistrySnapshot {
  return Object.freeze({
    records: Object.freeze([record]),
    diagnostics: Object.freeze([]),
    get: (effectId: string) => (effectId === record.effectId ? record : undefined),
    has: (effectId: string) => effectId === record.effectId,
  });
}

describe('planRender', () => {
  it('aggregates provider registry blockers into a browser-export route summary', () => {
    const result = planRender({
      config: makeConfig('preview-only-effect'),
      builtInKnownIds: {
        clipTypes: new Set(['media']),
        effectTypes: new Set(),
        transitionTypes: new Set(),
      },
      inactiveKnownIds: {
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      },
      effectRegistrySnapshot: snapshotWith({
        effectId: 'preview-only-effect',
        contributionId: 'preview-only-contrib',
        component: Effect,
        provenance: 'trusted-loader',
        ownerExtensionId: 'ext.preview',
        status: 'active',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'preview-only',
          capabilities: [
            { route: 'preview', status: 'supported', determinism: 'preview-only' },
            {
              route: 'browser-export',
              status: 'blocked',
              determinism: 'preview-only',
              blockerReason: 'preview-only',
              message: 'Preview only.',
            },
          ],
        },
      }),
    });

    expect(result.canBrowserExport).toBe(false);
    expect(result.routes).toEqual([
      { route: 'preview', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'browser-export', blockerCount: 2, findingCount: 2, blocked: true },
      { route: 'worker-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'sidecar-export', blockerCount: 0, findingCount: 0, blocked: false },
    ]);
    expect(result.blockers[0]).toMatchObject({
      route: 'browser-export',
      reason: 'preview-only',
      severity: 'error',
      extensionId: 'ext.preview',
      contributionId: 'preview-only-contrib',
    });
  });

  it('maps registry capability statuses to findings and per-route blocker summaries without selecting a route', () => {
    const result = planRender({
      config: makeConfig('multi-route-effect'),
      builtInKnownIds: {
        clipTypes: new Set(['media']),
        effectTypes: new Set(),
        transitionTypes: new Set(),
      },
      inactiveKnownIds: {
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      },
      effectRegistrySnapshot: snapshotWith({
        effectId: 'multi-route-effect',
        contributionId: 'multi-route-contrib',
        component: Effect,
        provenance: 'trusted-loader',
        ownerExtensionId: 'ext.routes',
        status: 'active',
        renderability: {
          defaultRoute: 'preview',
          determinism: 'unknown',
          capabilities: [
            { route: 'preview', status: 'supported', determinism: 'preview-only' },
            { route: 'browser-export', status: 'supported', determinism: 'deterministic' },
            {
              route: 'worker-export',
              status: 'unknown',
              determinism: 'unknown',
              message: 'Worker route has not been classified.',
            },
            {
              route: 'sidecar-export',
              status: 'blocked',
              determinism: 'process-dependent',
              blockerReason: 'process-dependent',
              message: 'Sidecar route requires a process.',
            },
          ],
          blockers: [
            {
              id: 'registry.sidecar.process',
              severity: 'error',
              route: 'sidecar-export',
              reason: 'process-dependent',
              message: 'Sidecar route requires a process.',
            },
          ],
        },
      }),
    });

    expect(result.canBrowserExport).toBe(true);
    expect(result.routes).toEqual([
      { route: 'preview', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'browser-export', blockerCount: 0, findingCount: 0, blocked: false },
      { route: 'worker-export', blockerCount: 0, findingCount: 1, blocked: false },
      { route: 'sidecar-export', blockerCount: 2, findingCount: 1, blocked: true },
    ]);
    expect(result.findings).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'registry.effect.multi-route-effect.worker-export.unknown',
        severity: 'warning',
        route: 'worker-export',
        reason: 'unknown',
      }),
      expect.objectContaining({
        id: 'registry.effect.multi-route-effect.sidecar-export.process-dependent',
        severity: 'error',
        route: 'sidecar-export',
        reason: 'process-dependent',
      }),
    ]));
    expect(result.blockers).toEqual(expect.arrayContaining([
      expect.objectContaining({
        id: 'registry.effect.multi-route-effect.sidecar-export.process-dependent',
        route: 'sidecar-export',
        reason: 'process-dependent',
        extensionId: 'ext.routes',
        contributionId: 'multi-route-contrib',
      }),
      expect.objectContaining({
        id: 'registry.sidecar.process',
        route: 'sidecar-export',
        reason: 'process-dependent',
        extensionId: 'ext.routes',
        contributionId: 'multi-route-contrib',
      }),
    ]));
  });
});
