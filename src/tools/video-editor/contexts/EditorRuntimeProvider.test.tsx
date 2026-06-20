import { render, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import type { FC, ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { defineExtension } from '@reigh/editor-sdk';
import type { Diagnostic, ExtensionContribution } from '@reigh/editor-sdk';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type { EffectRegistryRecord } from '@/tools/video-editor/effects/registry/types.ts';
import { useEffectRegistryContext } from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
import { useTransitionRegistryContext } from '@/tools/video-editor/transitions/registry/index.ts';
import type { TransitionRegistryRecord } from '@/tools/video-editor/transitions/registry/types.ts';
import { useShaderEffectRegistryContext } from '@/tools/video-editor/shaders/registry/index.ts';
import type { ShaderEffectRegistryRecord } from '@/tools/video-editor/shaders/registry/types.ts';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { EditorRuntimeProvider } from '@/tools/video-editor/contexts/EditorRuntimeProvider.tsx';
import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import type { LivePermissionService } from '@/tools/video-editor/runtime/livePermissions.ts';

const mocks = vi.hoisted(() => {
  const syncSlices = vi.fn();
  const timelineData = {
    clips: [],
    tracks: [],
    registry: {},
    config: {},
  };
  return {
    syncSlices,
    timelineData,
    useEffectRegistry: vi.fn(),
    emptyEffectCatalog: {
      data: { entrance: [], exit: [], continuous: [] },
      effects: [],
      entrance: [],
      exit: [],
      continuous: [],
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(async () => undefined),
      canCreateEffect: false,
      canUpdateEffect: false,
      canDeleteEffect: false,
    },
    emptySequenceCatalog: {
      components: [],
      byClipType: {},
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(async () => undefined),
      canCreateComponent: false,
      canUpdateComponent: false,
      canDeleteComponent: false,
    },
    timelineStore: {
      getState: () => ({
        data: { data: timelineData },
        timelineOps: null,
        syncSlices,
      }),
    },
  };
});

vi.mock('@/tools/video-editor/hooks/useEffects.ts', () => ({
  useEffects: () => ({ data: [] }),
}));

vi.mock('@/tools/video-editor/hooks/useEffectRegistry.ts', () => ({
  useEffectRegistry: (...args: unknown[]) => mocks.useEffectRegistry(...args),
}));

vi.mock('@/tools/video-editor/hooks/useEffectResources.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/tools/video-editor/hooks/useEffectResources.ts')>();
  return {
    ...actual,
    useResolvedEffectCatalog: () => mocks.emptyEffectCatalog,
  };
});

vi.mock('@/tools/video-editor/hooks/useSequenceResources.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/tools/video-editor/hooks/useSequenceResources.ts')>();
  return {
    ...actual,
    useResolvedSequenceComponentCatalog: () => mocks.emptySequenceCatalog,
  };
});

vi.mock('@/tools/video-editor/hooks/useTimelineState.ts', () => ({
  useTimelineState: () => ({ store: mocks.timelineStore }),
}));

const Component: FC<{ children: ReactNode }> = ({ children }) => children;
const ReplacementComponent: FC<{ children: ReactNode }> = ({ children }) => children;
const SHADER_SOURCE = Object.freeze({
  kind: 'inline' as const,
  fragment: 'void main() { gl_FragColor = vec4(1.0); }',
});

interface TrustedLocalEffectPack {
  readonly extensionId: string;
  readonly records: readonly EffectRegistryRecord[];
}

function effectRecord(
  effectId: string,
  ownerExtensionId: string,
  dispose: () => void,
): EffectRegistryRecord {
  return {
    effectId,
    contributionId: `${ownerExtensionId}.effect`,
    component: Component,
    provenance: 'trusted-loader',
    ownerExtensionId,
    status: 'active',
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
    dispose,
  };
}

function shaderRecord(
  shaderId: string,
  ownerExtensionId: string,
  diagnostics: readonly Diagnostic[],
  dispose: () => void,
): ShaderEffectRegistryRecord {
  return {
    shaderId,
    contributionId: `${ownerExtensionId}.shader`,
    label: shaderId,
    source: SHADER_SOURCE,
    pass: 'postprocess',
    provenance: 'trusted-loader',
    ownerExtensionId,
    status: 'error',
    diagnostics,
    renderability: {
      defaultRoute: 'preview',
      determinism: 'preview-only',
      capabilities: [
        {
          route: 'preview',
          status: 'supported',
          determinism: 'preview-only',
        },
      ],
    },
    dispose,
  };
}

function TrustedLocalEffectPackLoader({ packs }: { packs: readonly TrustedLocalEffectPack[] }) {
  const { registry } = useEffectRegistryContext();

  useEffect(() => {
    const handles = packs.flatMap((pack) =>
      pack.records.map((record) =>
        registry.register({
          ...record,
          ownerExtensionId: pack.extensionId,
          provenance: 'trusted-loader',
        }),
      ),
    );

    return () => {
      for (const handle of handles) {
        handle.dispose();
      }
    };
  }, [packs, registry]);

  return null;
}

describe('EditorRuntimeProvider effect registry lifecycle', () => {
  it('activates and cleans up shader registrations without changing effect or transition registration', async () => {
    const extensionId = 'com.example.shader-runtime';
    const effectId = 'shader-runtime-effect';
    const transitionId = 'shader-runtime-transition';
    const shaderId = 'shader.runtime.grade';
    let latestEffectRecords: readonly EffectRegistryRecord[] = [];
    let latestTransitionRecords: readonly TransitionRegistryRecord[] = [];
    let latestShaderRecords: readonly ShaderEffectRegistryRecord[] = [];

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Shader runtime extension',
        contributions: [
          {
            id: 'shader-runtime.effect' as never,
            kind: 'effect',
            effectId,
            label: 'Runtime Effect',
          },
          {
            id: 'shader-runtime.transition' as never,
            kind: 'transition',
            transitionId,
            label: 'Runtime Transition',
          },
          {
            id: 'shader-runtime.shader' as never,
            kind: 'shader',
            shaderId,
            label: 'Runtime Shader',
            pass: 'postprocess',
            source: SHADER_SOURCE,
          },
        ],
      },
      activate(ctx) {
        const effectHandle = ctx.effects.registerComponent(effectId, Component);
        const transitionHandle = ctx.transitions.registerRenderer(transitionId, () => null);
        const shaderHandle = ctx.shaders.registerShader(shaderId, SHADER_SOURCE);

        return {
          dispose() {
            shaderHandle.dispose();
            transitionHandle.dispose();
            effectHandle.dispose();
          },
        };
      },
    });

    function CaptureRegistries() {
      latestEffectRecords = useEffectRegistryContext().snapshot.records;
      latestTransitionRecords = useTransitionRegistryContext().snapshot.records;
      latestShaderRecords = useShaderEffectRegistryContext().snapshot.records;
      return null;
    }

    function Host({ enabled }: { enabled: boolean }) {
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={enabled ? [extension] : []}
        >
          <CaptureRegistries />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host enabled />);

    await waitFor(() => {
      expect(latestEffectRecords.map((record) => record.effectId)).toContain(effectId);
      expect(latestTransitionRecords.map((record) => record.transitionId)).toContain(transitionId);
      expect(latestShaderRecords.map((record) => record.shaderId)).toContain(shaderId);
    });

    expect(latestEffectRecords.map((record) => record.effectId)).not.toContain(shaderId);
    expect(latestShaderRecords[0]).toMatchObject({
      shaderId,
      ownerExtensionId: extensionId,
      contributionId: 'shader-runtime.shader',
      provenance: 'bundled-extension',
      status: 'active',
    });
    expect(latestShaderRecords[0].renderability.capabilities).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ route: 'preview', status: 'supported' }),
        expect.objectContaining({ route: 'browser-export', status: 'blocked' }),
        expect.objectContaining({ route: 'worker-export', status: 'blocked' }),
      ]),
    );

    rerender(<Host enabled={false} />);

    await waitFor(() => {
      expect(latestEffectRecords.map((record) => record.effectId)).not.toContain(effectId);
      expect(latestTransitionRecords.map((record) => record.transitionId)).not.toContain(transitionId);
      expect(latestShaderRecords.map((record) => record.shaderId)).not.toContain(shaderId);
    });
  });

  it('cleans extension-owned effect records and command contributions on removal after HMR replacement', async () => {
    const extensionId = 'com.example.lifecycle';
    const commandId = `${extensionId}.run`;
    const disposeOriginal = vi.fn();
    const disposeReplacement = vi.fn();
    let hmrHandle: { dispose(): void } | null = null;
    let latestEffectIds: readonly string[] = [];
    let latestCommandIds: readonly string[] = [];

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Lifecycle extension',
        contributions: [
          {
            id: 'lifecycle.command' as never,
            kind: 'command',
            command: commandId,
            label: 'Run lifecycle command',
          },
        ],
      },
      activate(ctx) {
        return ctx.commands.registerCommand(commandId, vi.fn());
      },
    });

    function CaptureLifecycle() {
      const { registry, snapshot } = useEffectRegistryContext();
      const runtime = useVideoEditorRuntime();

      latestEffectIds = snapshot.records.map((record) => record.effectId);
      latestCommandIds = runtime.commandRegistry?.getSnapshot().commands.map((command) => command.commandId) ?? [];

      useEffect(() => {
        const originalHandle = registry.register(
          effectRecord('trusted-fx', extensionId, disposeOriginal),
        );
        hmrHandle = registry.updateRecord('trusted-fx', (current) => ({
          ...current,
          contributionId: `${extensionId}.effect.hmr`,
          component: ReplacementComponent,
        }), disposeReplacement);

        return () => {
          originalHandle.dispose();
          hmrHandle?.dispose();
        };
      }, [registry]);

      return null;
    }

    const props = {
      dataProvider: {} as DataProvider,
      timelineId: 'timeline-1',
      userId: 'user-1',
      extensions: [extension],
    };

    const { rerender } = render(
      <EditorRuntimeProvider {...props}>
        <CaptureLifecycle />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(latestEffectIds).toContain('trusted-fx');
      expect(latestCommandIds).toContain(commandId);
    });
    expect(disposeOriginal).toHaveBeenCalledTimes(1);
    expect(disposeReplacement).not.toHaveBeenCalled();

    rerender(
      <EditorRuntimeProvider {...props} extensions={[]}>
        <CaptureLifecycle />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(latestEffectIds).not.toContain('trusted-fx');
      expect(latestCommandIds).not.toContain(commandId);
    });
    expect(disposeOriginal).toHaveBeenCalledTimes(1);
    expect(disposeReplacement).toHaveBeenCalledTimes(1);

    hmrHandle?.dispose();
    hmrHandle?.dispose();
    expect(disposeReplacement).toHaveBeenCalledTimes(1);
  });

  it('enables and disables trusted local effect packs without public component contribution support', async () => {
    const extensionId = 'local.trusted.pack';
    const effectId = 'trusted-local-wipe';
    const disposeEffect = vi.fn();
    let latestEffectRecords: readonly EffectRegistryRecord[] = [];

    const effectContribution: ExtensionContribution = {
      id: 'trusted-local-wipe.contribution' as never,
      kind: 'effect',
      effectId,
      label: 'Trusted local wipe',
    };
    expect(effectContribution).not.toHaveProperty('component');

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Trusted local pack',
        contributions: [effectContribution],
      },
    });

    const localPack: TrustedLocalEffectPack = {
      extensionId,
      records: [
        {
          ...effectRecord(effectId, extensionId, disposeEffect),
          contributionId: effectContribution.id,
        },
      ],
    };
    const enabledPacks = [localPack];
    const disabledPacks: readonly TrustedLocalEffectPack[] = [];

    function CaptureEffects() {
      const { snapshot } = useEffectRegistryContext();
      latestEffectRecords = snapshot.records;
      return null;
    }

    function Host({ enabled }: { enabled: boolean }) {
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={enabled ? [extension] : []}
        >
          <TrustedLocalEffectPackLoader packs={enabled ? enabledPacks : disabledPacks} />
          <CaptureEffects />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host enabled />);

    await waitFor(() => {
      expect(latestEffectRecords.map((record) => record.effectId)).toContain(effectId);
    });
    const loadedRecord = latestEffectRecords.find((record) => record.effectId === effectId);
    expect(loadedRecord?.ownerExtensionId).toBe(extensionId);
    expect(loadedRecord?.provenance).toBe('trusted-loader');
    expect(loadedRecord?.component).toBe(Component);
    expect(disposeEffect).not.toHaveBeenCalled();

    rerender(<Host enabled={false} />);

    await waitFor(() => {
      expect(latestEffectRecords.map((record) => record.effectId)).not.toContain(effectId);
    });
    expect(disposeEffect).toHaveBeenCalledTimes(1);
  });

  it('feeds provider diagnostic collection from lifecycle, command, and registry sources', async () => {
    const extensionId = 'com.example.diagnostics';
    const shaderId = 'diagnostics.shader';
    let collection = null as ReturnType<typeof useVideoEditorRuntime>['diagnosticCollection'] | null;

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Diagnostics extension',
        contributions: [
          {
            id: 'diagnostics.effect' as never,
            kind: 'effect',
            effectId: 'diagnostics-effect',
            label: 'Diagnostics effect',
          },
          {
            id: 'diagnostics.command' as never,
            kind: 'command',
            command: 'reigh.reserved',
            label: 'Reserved command',
          },
        ],
      },
      activate() {
        throw new Error('activation failed for diagnostics test');
      },
    });

    function CaptureDiagnostics({ enabled }: { enabled: boolean }) {
      const runtime = useVideoEditorRuntime();
      const { registry } = useEffectRegistryContext();
      const { registry: shaderRegistry } = useShaderEffectRegistryContext();
      collection = runtime.diagnosticCollection ?? null;

      useEffect(() => {
        if (!enabled || !runtime.diagnosticCollection) return undefined;
        runtime.diagnosticCollection.publish({
          id: 'export-stale-diagnostic',
          severity: 'error',
          code: 'export/unrenderable-effect',
          message: 'Stale export blocker',
          extensionId,
          contributionId: 'diagnostics.effect',
          detail: { source: 'export-guard' },
        });
        runtime.diagnosticCollection.publish({
          id: 'planner-stale-diagnostic',
          severity: 'error',
          code: 'planner/browser-export/route-unsupported',
          message: 'Stale planner blocker',
          extensionId,
          contributionId: 'diagnostics.effect',
          detail: { source: 'render-planner' },
        });
        const first = registry.register(effectRecord('diagnostics-duplicate', extensionId, vi.fn()));
        const second = registry.register(effectRecord('diagnostics-duplicate', extensionId, vi.fn()));
        const shader = shaderRegistry.register(shaderRecord(
          shaderId,
          extensionId,
          [{
            id: 'diagnostics-shader-compile-error',
            severity: 'error',
            code: 'shader/compile-error',
            message: 'Shader compile failed',
            sourceRange: {
              startLine: 4,
              startCol: 9,
              endLine: 4,
              endCol: 17,
            },
            detail: { source: 'fragment', phase: 'fragment' },
          }],
          vi.fn(),
        ));
        return () => {
          shader.dispose();
          first.dispose();
          second.dispose();
        };
      }, [enabled, registry, runtime.diagnosticCollection, shaderRegistry]);

      return null;
    }

    function Host({ enabled }: { enabled: boolean }) {
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={enabled ? [extension] : []}
        >
          <CaptureDiagnostics enabled={enabled} />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host enabled />);

    await waitFor(() => {
      const diagnostics = collection?.getSnapshot() ?? [];
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.detail?.source === 'extension-lifecycle'
          && diagnostic.code === 'lifecycle/activation-failed',
      )).toBe(true);
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.detail?.source === 'command-registry'
          && diagnostic.code === 'command-registry/reserved-command',
      )).toBe(true);
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.detail?.source === 'effect-registry'
          && diagnostic.code === 'effect-registry/duplicate-effect',
      )).toBe(true);
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.detail?.source === 'shader-effect-registry'
          && diagnostic.code === 'shader/compile-error'
          && diagnostic.extensionId === extensionId
          && diagnostic.contributionId === `${extensionId}.shader`
          && diagnostic.detail?.shaderId === shaderId
          && diagnostic.detail?.diagnosticSource === 'fragment'
          && diagnostic.sourceRange?.startLine === 4
          && diagnostic.sourceRange?.startCol === 9,
      )).toBe(true);
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.detail?.source === 'export-guard'
          && diagnostic.code === 'export/unrenderable-effect',
      )).toBe(true);
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.detail?.source === 'render-planner'
          && diagnostic.code === 'planner/browser-export/route-unsupported',
      )).toBe(true);
    });

    rerender(<Host enabled={false} />);

    await waitFor(() => {
      const disabledOwnerDiagnostics = collection?.getSnapshot().filter(
        (diagnostic) => diagnostic.extensionId === extensionId,
      ) ?? [];
      expect(disabledOwnerDiagnostics).toEqual([]);
    });
  });
});


describe('EditorRuntimeProvider live data registry lifecycle', () => {
  it('instantiates liveDataRegistry and livePermissionService on mount and disposes on unmount', async () => {
    let capturedRegistry: LiveDataRegistry | null = null;
    let capturedPermissionService: LivePermissionService | null = null;

    function CaptureLiveServices() {
      const runtime = useVideoEditorRuntime();
      capturedRegistry = runtime.liveDataRegistry ?? null;
      capturedPermissionService = runtime.livePermissionService ?? null;
      return null;
    }

    const props = {
      dataProvider: {} as DataProvider,
      timelineId: 'timeline-1',
      userId: 'user-1',
      extensions: [],
    };

    const { unmount } = render(
      <EditorRuntimeProvider {...props}>
        <CaptureLiveServices />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(capturedRegistry).not.toBeNull();
      expect(capturedPermissionService).not.toBeNull();
    });

    // Verify registry is not disposed while mounted
    expect(capturedRegistry?.isDisposed).toBe(false);
    expect(capturedPermissionService?.isDisposed).toBe(false);

    // Unmount should dispose both
    unmount();

    expect(capturedRegistry?.isDisposed).toBe(true);
    expect(capturedPermissionService?.isDisposed).toBe(true);
  });

  it('exposes sessions through ctx.creative.sessions for extensions', async () => {
    let capturedSessions: unknown = null;
    const extensionId = 'com.example.live-sessions';

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Live sessions extension',
      },
      activate(ctx) {
        capturedSessions = ctx.creative.sessions;
        return { dispose() {} };
      },
    });

    function CaptureContext() {
      return null;
    }

    const props = {
      dataProvider: {} as DataProvider,
      timelineId: 'timeline-1',
      userId: 'user-1',
      extensions: [extension],
    };

    render(
      <EditorRuntimeProvider {...props}>
        <CaptureContext />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(capturedSessions).not.toBeNull();
    });

    // Verify the sessions object has the expected LiveSessionsService methods
    expect(typeof (capturedSessions as any)?.registerSource).toBe('function');
    expect(typeof (capturedSessions as any)?.listSources).toBe('function');
    expect(typeof (capturedSessions as any)?.openChannel).toBe('function');
    expect(typeof (capturedSessions as any)?.pushSample).toBe('function');
    expect(typeof (capturedSessions as any)?.getDiagnostics).toBe('function');
  });

  it('disposes active live sources on provider unmount', async () => {
    let capturedRegistry: LiveDataRegistry | null = null;
    const extensionId = 'com.example.live-dispose';

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Live dispose extension',
      },
      activate(ctx) {
        const sessions = ctx.creative.sessions;
        // Register a live source through the sessions API
        sessions.registerSource({
          id: 'test-source-1',
          kind: 'generated',
          label: 'Test Source',
        });
        return { dispose() {} };
      },
    });

    function CaptureRegistry() {
      const runtime = useVideoEditorRuntime();
      capturedRegistry = runtime.liveDataRegistry ?? null;
      return null;
    }

    const props = {
      dataProvider: {} as DataProvider,
      timelineId: 'timeline-1',
      userId: 'user-1',
      extensions: [extension],
    };

    const { unmount } = render(
      <EditorRuntimeProvider {...props}>
        <CaptureRegistry />
      </EditorRuntimeProvider>,
    );

    // Wait for the source to be registered
    await waitFor(() => {
      const sources = capturedRegistry?.listSources() ?? [];
      expect(sources.length).toBe(1);
      expect(sources[0].id).toBe('test-source-1');
    });

    // Unmount the provider — should dispose the source
    unmount();

    // After unmount, the registry should be disposed and sources cleared
    expect(capturedRegistry?.isDisposed).toBe(true);
    // Tombstone should exist after disposal
    const snapshot = (capturedRegistry as any)?.getSnapshot?.();
    expect(snapshot?.tombstones?.some(
      (t: any) => t.id === 'test-source-1' && t.extensionId === extensionId,
    )).toBe(true);
  });

  it('orphan-disposes extension-owned live sources on extension removal without mutating persisted bindings', async () => {
    let capturedRegistry: LiveDataRegistry | null = null;
    const extensionId = 'com.example.live-orphan';
    const sourceId = 'test-source-orphan';
    const persistedLiveBindings = [
      {
        bindingId: 'binding-1',
        sourceId,
        targetClipId: 'clip-1',
      },
    ];
    (mocks.timelineData.config as Record<string, unknown>).liveBindings = persistedLiveBindings;
    const persistedBefore = JSON.stringify(persistedLiveBindings);

    const extension = defineExtension({
      manifest: {
        id: extensionId as never,
        version: '1.0.0',
        label: 'Live orphan extension',
      },
      activate(ctx) {
        ctx.creative.sessions.registerSource({
          id: sourceId,
          kind: 'generated',
          label: 'Orphan Source',
        });
        return { dispose() {} };
      },
    });

    function CaptureRegistry() {
      const runtime = useVideoEditorRuntime();
      capturedRegistry = runtime.liveDataRegistry ?? null;
      return null;
    }

    const props = {
      dataProvider: {} as DataProvider,
      timelineId: 'timeline-1',
      userId: 'user-1',
    };

    const { rerender } = render(
      <EditorRuntimeProvider {...props} extensions={[extension]}>
        <CaptureRegistry />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(capturedRegistry?.listSources().map((source) => source.id)).toContain(sourceId);
    });

    (capturedRegistry as any)._addBinding({
      bindingId: 'binding-1',
      sourceId,
      targetClipId: 'clip-1',
      status: 'resolved',
    });

    rerender(
      <EditorRuntimeProvider {...props} extensions={[]}>
        <CaptureRegistry />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(capturedRegistry?.listSources()).toEqual([]);
      expect(capturedRegistry?.getSnapshot().tombstones.some(
        (tombstone: any) =>
          tombstone.id === sourceId && tombstone.extensionId === extensionId,
      )).toBe(true);
    });

    expect(capturedRegistry?.resolveBinding('binding-1').status).toBe('orphaned');
    expect(capturedRegistry?.getBindingMetadata().orphanedCount).toBe(1);
    expect(JSON.stringify((mocks.timelineData.config as Record<string, unknown>).liveBindings)).toBe(persistedBefore);

    rerender(
      <EditorRuntimeProvider {...props} extensions={[extension]}>
        <CaptureRegistry />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(capturedRegistry?.resolveBinding('binding-1').status).toBe('orphaned');
      expect(capturedRegistry?.getDiagnostics().some(
        (diagnostic) =>
          diagnostic.code === 'live/duplicate-source' && diagnostic.sourceId === sourceId,
      )).toBe(true);
    });
  });

  it('syncs live registry diagnostics to diagnosticCollection', async () => {
    let capturedCollection: ReturnType<typeof useVideoEditorRuntime>['diagnosticCollection'] = null;
    const sourceId = 'diagnostic-live-source';
    const extension = defineExtension({
      manifest: {
        id: 'com.example.live-diagnostic' as never,
        version: '1.0.0',
        label: 'Live diagnostic extension',
      },
      activate(ctx) {
        ctx.creative.sessions.registerSource({
          id: sourceId,
          kind: 'generated',
          label: 'Diagnostic Source',
        });
        return { dispose() {} };
      },
    });

    function CaptureDiagnostics() {
      const runtime = useVideoEditorRuntime();
      capturedCollection = runtime.diagnosticCollection ?? null;
      return null;
    }

    const props = {
      dataProvider: {} as DataProvider,
      timelineId: 'timeline-1',
      userId: 'user-1',
      extensions: [extension],
    };

    render(
      <EditorRuntimeProvider {...props}>
        <CaptureDiagnostics />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(capturedCollection).not.toBeNull();
    });

    await waitFor(() => {
      const liveDiagnostics = capturedCollection?.getSnapshot().filter(
        (d) => d.detail?.source === 'live-registry',
      ) ?? [];
      expect(liveDiagnostics.some(
        (diagnostic) =>
          diagnostic.code === 'live/source-registered'
          && diagnostic.detail?.sourceId === sourceId,
      )).toBe(true);
      expect(liveDiagnostics.every((diagnostic) => diagnostic.extensionId === undefined)).toBe(true);
    });
  });
});
