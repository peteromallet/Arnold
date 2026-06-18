import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useRenderState } from '@/tools/video-editor/hooks/useRenderState';
import type { ResolvedTimelineConfig } from '@/tools/video-editor/types';
import type { ExtensionRuntime } from '@/tools/video-editor/runtime/extensionSurface';

const mocks = vi.hoisted(() => ({
  startClientRender: vi.fn(),
}));

vi.mock('@/tools/video-editor/hooks/useClientRender', () => ({
  useClientRender: () => mocks.startClientRender,
}));

vi.mock('@/tools/video-editor/lib/renderRouter', () => ({
  decideRenderRoute: (timeline: ResolvedTimelineConfig | null | undefined) => {
    const clip = timeline?.clips?.[0];
    if (clip?.generation?.sequence_lane === 'remotion_module' && !clip?.generation?.artifact_id) {
      return {
        route: 'preview-only',
        hasThemedClip: false,
        hasMediaClip: false,
        reason: 'remotion_module_missing_artifact',
      };
    }

    if (clip?.clipType === 'generated-module') {
      return {
        route: 'worker-banodoco',
        hasThemedClip: false,
        hasMediaClip: false,
        reason: 'generated_remotion_module',
      };
    }

    return {
      route: 'browser-remotion',
      hasThemedClip: false,
      hasMediaClip: true,
      reason: 'pure_native_clips',
    };
  },
}));

const guardMocks = vi.hoisted(() => ({
  collectBuiltInKnownIds: vi.fn(),
  collectExtensionDeclaredIds: vi.fn(),
  scanExportConfig: vi.fn(),
}));

vi.mock('@/tools/video-editor/runtime/exportGuard', () => ({
  collectBuiltInKnownIds: guardMocks.collectBuiltInKnownIds,
  collectExtensionDeclaredIds: guardMocks.collectExtensionDeclaredIds,
  scanExportConfig: guardMocks.scanExportConfig,
}));

const buildConfig = (clip: ResolvedTimelineConfig['clips'][number]): ResolvedTimelineConfig => ({
  output: {
    resolution: '1920x1080',
    fps: 30,
    file: 'out.mp4',
  },
  tracks: [{ id: 'V1', kind: 'visual', label: 'V1' }],
  clips: [clip],
  registry: {},
});

function emptyExtensionRuntime(): ExtensionRuntime {
  return {
    config: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
    } as ExtensionRuntime['config'],
    extensions: [],
    diagnostics: [],
    inactiveReserved: [],
    knownRenderIds: new Set(),
    settingsDefaults: {},
  };
}

function makeExtensionRuntime(overrides?: Partial<ExtensionRuntime>): ExtensionRuntime {
  return {
    config: {
      slots: {},
      dialogHost: { dialogs: [] },
      registry: { panels: [], inspectorSections: [] },
    } as ExtensionRuntime['config'],
    extensions: [],
    diagnostics: [],
    inactiveReserved: [],
    knownRenderIds: new Set(),
    settingsDefaults: {},
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Pre-existing routing tests (with no extensionRuntime — guard skipped)
// ---------------------------------------------------------------------------

describe('useRenderState render routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
    guardMocks.collectBuiltInKnownIds.mockReturnValue({
      clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
      effectTypes: new Set(['fade', 'slide-up']),
      transitionTypes: new Set(['crossfade']),
    });
    guardMocks.collectExtensionDeclaredIds.mockReturnValue({
      effectIds: new Set(),
      transitionIds: new Set(),
      clipTypeIds: new Set(),
    });
    guardMocks.scanExportConfig.mockReturnValue({
      diagnostics: [],
      unknownClipTypes: [],
      unknownEffects: [],
      unknownTransitions: [],
      inactiveExtensionIds: {
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      },
      hasBlockingErrors: false,
    });
  });

  it('invokes the client renderer only for client-route timelines', async () => {
    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    expect(result.current.renderStatus).toBe('idle');
  });

  it('uses an injected exporter instead of the client renderer when one is supplied', async () => {
    const exporter = {
      render: vi.fn(async () => ({
        id: 'job-1',
        subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
          listener({
            phase: 'complete',
            progress: 1,
            resultUrl: 'blob:https://example.com/rendered',
            log: 'done',
          });
          return () => undefined;
        },
      })),
    };

    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-native',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
      }),
      {
        fps: 30,
        durationInFrames: 30,
        compositionWidth: 1920,
        compositionHeight: 1080,
      },
      exporter,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(exporter.render).toHaveBeenCalledTimes(1);
    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('done');
    expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
    expect(result.current.renderResultFilename).toBe('out.mp4');
  });

  it('blocks malformed remotion_module metadata without invoking the client renderer', async () => {
    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-module-bad',
        clipType: 'media',
        track: 'V1',
        at: 0,
        hold: 1,
        generation: {
          sequence_lane: 'remotion_module',
        },
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain('Render blocked');
    expect(result.current.renderLog).toContain('remotion_module_missing_artifact');
  });

  it('surfaces worker-unavailable state for valid remotion_module routes without client fallback', async () => {
    const { result } = renderHook(() => useRenderState(
      buildConfig({
        id: 'clip-module-good',
        clipType: 'generated-module',
        track: 'V1',
        at: 0,
        hold: 1,
        generation: {
          sequence_lane: 'remotion_module',
          artifact_id: 'artifact-1',
        },
      }),
      null,
    ));

    await act(async () => {
      await result.current.startRender();
    });

    expect(mocks.startClientRender).not.toHaveBeenCalled();
    expect(result.current.renderStatus).toBe('error');
    expect(result.current.renderLog).toContain('Worker render unavailable');
    expect(result.current.renderLog).toContain('generated_remotion_module');
  });
});

// ---------------------------------------------------------------------------
// Export guard tests
// ---------------------------------------------------------------------------

describe('useRenderState export guard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.startClientRender.mockResolvedValue(undefined);
  });

  describe('empty-runtime fast path', () => {
    it('skips guard work when extensionRuntime is undefined', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard was never invoked
      expect(guardMocks.collectBuiltInKnownIds).not.toHaveBeenCalled();
      expect(guardMocks.collectExtensionDeclaredIds).not.toHaveBeenCalled();
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      // Native routing preserved
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
    });

    it('skips guard work when extensionRuntime is empty (no extensions, no inactive reserved)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard was never invoked
      expect(guardMocks.collectBuiltInKnownIds).not.toHaveBeenCalled();
      expect(guardMocks.collectExtensionDeclaredIds).not.toHaveBeenCalled();
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      // Native routing preserved
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });

    it('skips guard work when resolvedConfig is null even with extensions', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      const { result } = renderHook(() => useRenderState(
        null, // no config
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard was never invoked (null config = nothing to scan)
      expect(guardMocks.collectBuiltInKnownIds).not.toHaveBeenCalled();
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
    });

    it('skips guard work when resolvedConfig has zero clips even with extensions', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      const emptyConfig: ResolvedTimelineConfig = {
        output: { resolution: '1920x1080', fps: 30, file: 'out.mp4' },
        tracks: [],
        clips: [],
        registry: {},
      };

      const { result } = renderHook(() => useRenderState(
        emptyConfig,
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
    });
  });

  describe('export guard — blocking errors', () => {
    it('blocks render when export guard finds blocking errors (truly unknown clip type)', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      // Setup guard to return a blocking error
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-clip-type',
            message: 'Clip type "alien-format" is not recognised.',
            detail: { clipId: 'c1', clipType: 'alien-format' },
          },
        ],
        unknownClipTypes: ['alien-format'],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Render was blocked
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Export guard');
      expect(result.current.renderLog).toContain('alien-format');
      // Native routing was preserved — client render was NOT invoked
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('blocks exporter render too when guard finds blocking errors', async () => {
      const exporter = {
        render: vi.fn(),
      };

      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "crazy-spin" is not recognised.',
            detail: { clipId: 'c1', effectType: 'crazy-spin' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: ['crazy-spin'],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        exporter as any,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Export guard');
      expect(exporter.render).not.toHaveBeenCalled();
    });

    it('blocks with concise structured diagnostics in render log', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-clip-type',
            message: 'Clip type "alien-format" is not recognised.',
            detail: { clipId: 'c1', clipType: 'alien-format' },
          },
          {
            severity: 'warning',
            code: 'export/unknown-transition-type',
            message: 'Transition "star-wipe" is declared by an inactive extension.',
            detail: { clipId: 'c2', transitionType: 'star-wipe' },
          },
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Continuous effect "hyperspace" is not recognised.',
            detail: { clipId: 'c3', effectType: 'hyperspace' },
          },
        ],
        unknownClipTypes: ['alien-format'],
        unknownEffects: ['hyperspace'],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(['star-wipe']),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('error');
      const log = result.current.renderLog;
      // Summary line
      expect(log).toContain('Export guard: 3 issue(s) — 2 error(s), 1 warning(s)');
      // Error diagnostics shown first
      expect(log).toContain('[export/unknown-clip-type]');
      expect(log).toContain('[export/unknown-effect-type]');
      // Warning still shown
      expect(log).toContain('[export/unknown-transition-type]');
    });
  });

  describe('export guard — warnings only (preserve native routing)', () => {
    it('allows render when only extension-declared (inactive) warnings are present', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [
                {
                  id: 'contrib.future' as any,
                  kind: 'transition' as any,
                  transitionId: 'future-transition',
                },
              ],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'warning',
            code: 'export/unknown-transition-type',
            message: 'Transition "future-transition" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', transitionType: 'future-transition' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(['future-transition']),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Native routing preserved — client render invoked
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      // But diagnostics are still emitted in the render log
      expect(result.current.renderLog).toContain('Export guard');
      expect(result.current.renderLog).toContain('future-transition');
      expect(result.current.renderLog).toContain('warning');
    });

    it('allows render when guard finds no issues at all', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderLog).toContain('Export guard: no issues found.');
    });
  });

  describe('export guard — native routing preservation', () => {
    it('preserves existing preview-only block when guard passes', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'test-ext' as any,
              version: '1.0.0',
              contributions: [],
            },
          } as any,
        ],
      });

      // Guard passes — no blocking errors
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-module-bad',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
          },
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard passed but preview-only blocked it — native routing preserved
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Render blocked');
      expect(result.current.renderLog).toContain('remotion_module_missing_artifact');
      // But guard log was set first (then overwritten by the route block)
      // The route block's log takes precedence
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('passes extension contributions to collectExtensionDeclaredIds', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'ext-a' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c1' as any, kind: 'effect' as any, effectId: 'my-effect' },
                { id: 'c2' as any, kind: 'transition' as any, transitionId: 'my-transition' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(['my-effect']),
        transitionIds: new Set(['my-transition']),
        clipTypeIds: new Set(),
      });

      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // collectExtensionDeclaredIds was called with the contributions
      expect(guardMocks.collectExtensionDeclaredIds).toHaveBeenCalledTimes(1);
      const callArg = guardMocks.collectExtensionDeclaredIds.mock.calls[0][0];
      expect(callArg).toHaveLength(2);
      expect(callArg[0].effectId).toBe('my-effect');
      expect(callArg[1].transitionId).toBe('my-transition');

      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });
  });

  describe('export guard — pure-native no-extension routing parity', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      mocks.startClientRender.mockResolvedValue(undefined);
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });
      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });
    });

    it('routes pure-native media clip through client renderer with no extension runtime (identical to pre-extension behavior)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped, client renderer invoked — same as pre-extension
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
    });

    it('routes pure-native media clip through client renderer with empty extension runtime (same as no extensions)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped because runtime is empty, client renderer invoked
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
    });

    it('routes pure-native clip through injected exporter with no extension runtime', async () => {
      const exporter = {
        render: vi.fn(async () => ({
          id: 'job-1',
          subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
            listener({
              phase: 'complete',
              progress: 1,
              resultUrl: 'blob:https://example.com/rendered',
              log: 'done',
            });
            return () => undefined;
          },
        })),
      };

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        {
          fps: 30,
          durationInFrames: 30,
          compositionWidth: 1920,
          compositionHeight: 1080,
        },
        exporter,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped, exporter used (not client renderer)
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(exporter.render).toHaveBeenCalledTimes(1);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(result.current.renderStatus).toBe('done');
      expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
    });

    it('routes pure-native clip through injected exporter with empty extension runtime (same as no extensions)', async () => {
      const exporter = {
        render: vi.fn(async () => ({
          id: 'job-1',
          subscribe(listener: (progress: { phase: string; progress?: number; resultUrl?: string | null; log?: string }) => void) {
            listener({
              phase: 'complete',
              progress: 1,
              resultUrl: 'blob:https://example.com/rendered',
              log: 'done',
            });
            return () => undefined;
          },
        })),
      };

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-native',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        {
          fps: 30,
          durationInFrames: 30,
          compositionWidth: 1920,
          compositionHeight: 1080,
        },
        exporter,
        emptyExtensionRuntime(),
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped (empty runtime), exporter used — same routing as no extensions
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(exporter.render).toHaveBeenCalledTimes(1);
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(result.current.renderStatus).toBe('done');
      expect(result.current.renderResultUrl).toBe('blob:https://example.com/rendered');
    });

    it('preserves preview-only routing with no extension runtime (identical to pre-extension behavior)', async () => {
      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'clip-module-bad',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
          generation: {
            sequence_lane: 'remotion_module',
          },
        }),
        null,
        null,
        undefined, // no extensionRuntime
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard skipped, preview-only block preserved
      expect(guardMocks.scanExportConfig).not.toHaveBeenCalled();
      expect(mocks.startClientRender).not.toHaveBeenCalled();
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Render blocked');
      expect(result.current.renderLog).toContain('remotion_module_missing_artifact');
    });
  });

  describe('export guard — project requirement diagnostics', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      mocks.startClientRender.mockResolvedValue(undefined);
    });

    it('activates guard when extensions are present and emits no-error log for known native IDs', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'project-ext' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-bridged' as any, kind: 'slot', slot: 'toolbar' },
              ],
            },
          } as any,
        ],
      });

      // Setup guard to return clean (all native IDs known)
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });
      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      expect(result.current.renderStatus).toBe('idle');
      expect(result.current.renderLog).toContain('Export guard: no issues found.');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });

    it('emits blocking errors when project uses IDs not declared by any extension', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'project-ext' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-bridged' as any, kind: 'slot', slot: 'toolbar' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'error',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "missing-effect" is not recognised. Ensure the required extension or registry is installed.',
            detail: { clipId: 'c1', effectType: 'missing-effect' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: ['missing-effect'],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: true,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Blocked because the effect is not declared by any extension and not built-in
      expect(result.current.renderStatus).toBe('error');
      expect(result.current.renderLog).toContain('Export guard');
      expect(result.current.renderLog).toContain('missing-effect');
      expect(mocks.startClientRender).not.toHaveBeenCalled();
    });

    it('preserves routing when project uses IDs declared by inactive extension contributions (warnings only)', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'future-ext' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-future-effect' as any, kind: 'effect' as any, effectId: 'future-effect' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(['future-effect']),
        transitionIds: new Set(),
        clipTypeIds: new Set(),
      });
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'warning',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "future-effect" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', effectType: 'future-effect' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(['future-effect']),
          transitionIds: new Set(),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Not blocked — warning only, routing preserved
      expect(result.current.renderStatus).toBe('idle');
      expect(result.current.renderLog).toContain('Export guard');
      expect(result.current.renderLog).toContain('future-effect');
      expect(result.current.renderLog).toContain('warning');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });

    it('scans config for project requirements when multiple extensions contribute IDs', async () => {
      const extRuntime = makeExtensionRuntime({
        extensions: [
          {
            manifest: {
              id: 'ext-fx' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-fx1' as any, kind: 'effect' as any, effectId: 'custom-fx' },
              ],
            },
          } as any,
          {
            manifest: {
              id: 'ext-trans' as any,
              version: '1.0.0',
              contributions: [
                { id: 'c-tr1' as any, kind: 'transition' as any, transitionId: 'custom-transition' },
              ],
            },
          } as any,
        ],
      });

      guardMocks.collectBuiltInKnownIds.mockReturnValue({
        clipTypes: new Set(['media', 'text', 'hold', 'effect-layer']),
        effectTypes: new Set(['fade', 'slide-up']),
        transitionTypes: new Set(['crossfade']),
      });
      guardMocks.collectExtensionDeclaredIds.mockReturnValue({
        effectIds: new Set(['custom-fx']),
        transitionIds: new Set(['custom-transition']),
        clipTypeIds: new Set(),
      });
      guardMocks.scanExportConfig.mockReturnValue({
        diagnostics: [
          {
            severity: 'warning',
            code: 'export/unknown-effect-type',
            message: 'Entrance effect "custom-fx" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', effectType: 'custom-fx' },
          },
          {
            severity: 'warning',
            code: 'export/unknown-transition-type',
            message: 'Transition "custom-transition" is declared by an inactive extension and may not be available at export time.',
            detail: { clipId: 'c1', transitionType: 'custom-transition' },
          },
        ],
        unknownClipTypes: [],
        unknownEffects: [],
        unknownTransitions: [],
        inactiveExtensionIds: {
          effectIds: new Set(['custom-fx']),
          transitionIds: new Set(['custom-transition']),
          clipTypeIds: new Set(),
        },
        hasBlockingErrors: false,
      });

      const { result } = renderHook(() => useRenderState(
        buildConfig({
          id: 'c1',
          clipType: 'media',
          track: 'V1',
          at: 0,
          hold: 1,
        }),
        null,
        null,
        extRuntime,
      ));

      await act(async () => {
        await result.current.startRender();
      });

      // Guard invoked (extensions present), warnings emitted, routing preserved
      expect(guardMocks.scanExportConfig).toHaveBeenCalledTimes(1);
      expect(result.current.renderStatus).toBe('idle');
      expect(result.current.renderLog).toContain('Export guard');
      expect(result.current.renderLog).toContain('custom-fx');
      expect(result.current.renderLog).toContain('custom-transition');
      expect(result.current.renderLog).toContain('warning');
      expect(mocks.startClientRender).toHaveBeenCalledTimes(1);
    });
  });
});
