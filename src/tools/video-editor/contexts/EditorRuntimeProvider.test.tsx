import { fireEvent, render, waitFor } from '@testing-library/react';
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
import { useClipTypeRegistryContext } from '@/tools/video-editor/clip-types/ClipTypeRegistryContext.tsx';
import type { ClipTypeRegistryRecord } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import { EditorRuntimeProvider } from '@/tools/video-editor/contexts/EditorRuntimeProvider.tsx';
import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import type { LivePermissionService } from '@/tools/video-editor/runtime/livePermissions.ts';
import { ExtensionSettingsPanel } from '@/tools/video-editor/components/ExtensionSettings/ExtensionSettingsPanel';

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

function transitionRecord(
  transitionId: string,
  ownerExtensionId: string,
  dispose: () => void,
): TransitionRegistryRecord {
  return {
    transitionId,
    contributionId: `${ownerExtensionId}.transition`,
    renderer: () => null,
    provenance: 'bundled-extension',
    ownerExtensionId,
    status: 'active',
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

function clipTypeRecord(
  clipTypeId: string,
  ownerExtensionId: string,
  dispose: () => void,
): ClipTypeRegistryRecord {
  return {
    clipTypeId,
    contributionId: `${ownerExtensionId}.clipType`,
    renderer: () => null,
    ownerExtensionId,
    status: 'active',
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
        // Host-owned diagnostic (no extensionId) — should survive
        // extension disable/unload without being removed.
        runtime.diagnosticCollection.publish({
          id: 'host-owned-diagnostic',
          severity: 'warning',
          code: 'host/timeline-stale',
          message: 'Host-owned stale warning',
          detail: { source: 'host-owned' },
        });
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
      // Host-owned diagnostic must be present before disable.
      expect(diagnostics.some(
        (diagnostic) =>
          diagnostic.id === 'host-owned-diagnostic'
          && diagnostic.detail?.source === 'host-owned',
      )).toBe(true);
    });

    rerender(<Host enabled={false} />);

    await waitFor(() => {
      const snapshot = collection?.getSnapshot() ?? [];
      // Extension-owned diagnostics must be cleared on disable.
      const disabledOwnerDiagnostics = snapshot.filter(
        (diagnostic) => diagnostic.extensionId === extensionId,
      );
      expect(disabledOwnerDiagnostics).toEqual([]);
      // Host-owned diagnostic (no extensionId) must survive.
      expect(snapshot.some(
        (diagnostic) =>
          diagnostic.id === 'host-owned-diagnostic'
          && diagnostic.detail?.source === 'host-owned',
      )).toBe(true);
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

// ---------------------------------------------------------------------------
// M4: Extension settings surface via SchemaForm inside EditorRuntimeProvider
// ---------------------------------------------------------------------------

describe('EditorRuntimeProvider extension settings surface', () => {
  const SETTINGS_EXTENSION_ID = 'com.example.settings';
  const settingsManifest = {
    id: SETTINGS_EXTENSION_ID as never,
    version: '1.0.0',
    label: 'Settings Extension',
    settingsSchema: {
      schema: {
        type: 'object',
        properties: {
          apiKey: {
            type: 'string',
            title: 'API Key',
            description: 'Your API key for the service',
            default: '',
            minLength: 3,
          },
          maxRetries: {
            type: 'integer',
            title: 'Max Retries',
            description: 'Maximum number of retries',
            default: 3,
            minimum: 1,
            maximum: 10,
          },
          enableDebug: {
            type: 'boolean',
            title: 'Enable Debug',
            description: 'Enable debug logging',
            default: false,
          },
        },
        required: ['apiKey'],
      },
    },
  };

  beforeEach(() => {
    // Clean up localStorage for the settings extension
    const prefix = `reigh.ext.${SETTINGS_EXTENSION_ID}.`;
    const keysToRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(prefix)) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((k) => localStorage.removeItem(k));
  });

  it('renders settings form inside EditorRuntimeProvider and loads defaults', async () => {
    let formRendered = false;

    function CaptureForm() {
      const runtime = useVideoEditorRuntime();
      const ext = runtime.extensionRuntime?.extensions.find(
        (e) => e.manifest.id === SETTINGS_EXTENSION_ID,
      );
      formRendered = ext != null;
      return ext ? (
        <ExtensionSettingsPanel
          extensionId={SETTINGS_EXTENSION_ID}
          manifest={ext.manifest}
        />
      ) : null;
    }

    render(
      <EditorRuntimeProvider
        dataProvider={{} as DataProvider}
        timelineId="timeline-1"
        userId="user-1"
        extensions={[
          defineExtension({ manifest: settingsManifest }),
        ]}
      >
        <CaptureForm />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      expect(formRendered).toBe(true);
    });

    // The form should show the apiKey field (required) with an empty default
    const apiKeyInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement | null;
    expect(apiKeyInput).not.toBeNull();
    expect(apiKeyInput?.value).toBe('');

    // The maxRetries field (integer → number, rendered as slider) should exist
    const maxRetriesField = document.querySelector(
      '[data-testid="schema-form-field-maxRetries"]',
    ) as HTMLElement | null;
    expect(maxRetriesField).not.toBeNull();

    // The enableDebug field (boolean, rendered as switch) should exist
    const enableDebugField = document.querySelector(
      '[data-testid="schema-form-field-enableDebug"]',
    ) as HTMLElement | null;
    expect(enableDebugField).not.toBeNull();
  });

  it('saves valid settings and reloads persisted values', async () => {
    function CaptureForm() {
      const runtime = useVideoEditorRuntime();
      const ext = runtime.extensionRuntime?.extensions.find(
        (e) => e.manifest.id === SETTINGS_EXTENSION_ID,
      );
      return ext ? (
        <ExtensionSettingsPanel
          extensionId={SETTINGS_EXTENSION_ID}
          manifest={ext.manifest}
        />
      ) : null;
    }

    const { rerender } = render(
      <EditorRuntimeProvider
        dataProvider={{} as DataProvider}
        timelineId="timeline-1"
        userId="user-1"
        extensions={[
          defineExtension({ manifest: settingsManifest }),
        ]}
      >
        <CaptureForm />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      const apiKeyInput = document.querySelector(
        '[data-testid="schema-form-widget-apiKey"]',
      ) as HTMLInputElement | null;
      expect(apiKeyInput).not.toBeNull();
    });

    // Fill in a valid apiKey
    const apiKeyInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement;
    fireEvent.change(apiKeyInput, { target: { value: 'my-secret-key' } });

    // Click save
    const saveBtn = document.querySelector(
      '[data-testid="extension-settings-save"]',
    ) as HTMLButtonElement;
    expect(saveBtn).not.toBeNull();
    expect(saveBtn.disabled).toBe(false);
    fireEvent.click(saveBtn);

    // Verify the value was persisted to localStorage
    await waitFor(() => {
      const raw = localStorage.getItem(
        `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
      );
      expect(raw).toBe('"my-secret-key"');
    });

    // Re-render to verify persisted values are loaded
    rerender(
      <EditorRuntimeProvider
        dataProvider={{} as DataProvider}
        timelineId="timeline-1"
        userId="user-1"
        extensions={[
          defineExtension({ manifest: settingsManifest }),
        ]}
      >
        <CaptureForm />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      const reloadedInput = document.querySelector(
        '[data-testid="schema-form-widget-apiKey"]',
      ) as HTMLInputElement | null;
      expect(reloadedInput?.value).toBe('my-secret-key');
    });
  });

  it('blocks save on invalid field and focuses error (invalid focus behavior)', async () => {
    function CaptureForm() {
      const runtime = useVideoEditorRuntime();
      const ext = runtime.extensionRuntime?.extensions.find(
        (e) => e.manifest.id === SETTINGS_EXTENSION_ID,
      );
      return ext ? (
        <ExtensionSettingsPanel
          extensionId={SETTINGS_EXTENSION_ID}
          manifest={ext.manifest}
        />
      ) : null;
    }

    render(
      <EditorRuntimeProvider
        dataProvider={{} as DataProvider}
        timelineId="timeline-1"
        userId="user-1"
        extensions={[
          defineExtension({ manifest: settingsManifest }),
        ]}
      >
        <CaptureForm />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      const apiKeyInput = document.querySelector(
        '[data-testid="schema-form-widget-apiKey"]',
      ) as HTMLInputElement | null;
      expect(apiKeyInput).not.toBeNull();
    });

    // Enter a value below minLength (3) — "ab" is only 2 chars
    const apiKeyInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement;
    fireEvent.change(apiKeyInput, { target: { value: 'ab' } });

    // Click save
    const saveBtn = document.querySelector(
      '[data-testid="extension-settings-save"]',
    ) as HTMLButtonElement;
    fireEvent.click(saveBtn);

    // The save should have been blocked — SchemaForm validateAndFocus
    // returns false, so no localStorage write should have occurred
    await waitFor(() => {
      const raw = localStorage.getItem(
        `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
      );
      // Should still be null (no save occurred)
      expect(raw).toBeNull();
    });

    // The apiKey input should still have aria-invalid="true"
    const invalidInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement | null;
    expect(invalidInput?.getAttribute('aria-invalid')).toBe('true');
  });

  it('resets to defaults after saving overrides', async () => {
    function CaptureForm() {
      const runtime = useVideoEditorRuntime();
      const ext = runtime.extensionRuntime?.extensions.find(
        (e) => e.manifest.id === SETTINGS_EXTENSION_ID,
      );
      return ext ? (
        <ExtensionSettingsPanel
          extensionId={SETTINGS_EXTENSION_ID}
          manifest={ext.manifest}
        />
      ) : null;
    }

    render(
      <EditorRuntimeProvider
        dataProvider={{} as DataProvider}
        timelineId="timeline-1"
        userId="user-1"
        extensions={[
          defineExtension({ manifest: settingsManifest }),
        ]}
      >
        <CaptureForm />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      const apiKeyInput = document.querySelector(
        '[data-testid="schema-form-widget-apiKey"]',
      ) as HTMLInputElement | null;
      expect(apiKeyInput).not.toBeNull();
    });

    // Save a value first
    const apiKeyInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement;
    fireEvent.change(apiKeyInput, { target: { value: 'some-key' } });
    const saveBtn = document.querySelector(
      '[data-testid="extension-settings-save"]',
    ) as HTMLButtonElement;
    fireEvent.click(saveBtn);

    await waitFor(() => {
      const raw = localStorage.getItem(
        `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
      );
      expect(raw).toBe('"some-key"');
    });

    // Click reset
    const resetBtn = document.querySelector(
      '[data-testid="extension-settings-reset"]',
    ) as HTMLButtonElement;
    fireEvent.click(resetBtn);

    // Verify localStorage key was cleared and form reverted to default (empty)
    await waitFor(() => {
      const raw = localStorage.getItem(
        `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
      );
      expect(raw).toBeNull();
    });

    const revertedInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement;
    expect(revertedInput.value).toBe('');
  });

  it('cancels edits and reverts to last-saved values', async () => {
    function CaptureForm() {
      const runtime = useVideoEditorRuntime();
      const ext = runtime.extensionRuntime?.extensions.find(
        (e) => e.manifest.id === SETTINGS_EXTENSION_ID,
      );
      return ext ? (
        <ExtensionSettingsPanel
          extensionId={SETTINGS_EXTENSION_ID}
          manifest={ext.manifest}
        />
      ) : null;
    }

    render(
      <EditorRuntimeProvider
        dataProvider={{} as DataProvider}
        timelineId="timeline-1"
        userId="user-1"
        extensions={[
          defineExtension({ manifest: settingsManifest }),
        ]}
      >
        <CaptureForm />
      </EditorRuntimeProvider>,
    );

    await waitFor(() => {
      const apiKeyInput = document.querySelector(
        '[data-testid="schema-form-widget-apiKey"]',
      ) as HTMLInputElement | null;
      expect(apiKeyInput).not.toBeNull();
    });

    // Save a value first
    const apiKeyInput = document.querySelector(
      '[data-testid="schema-form-widget-apiKey"]',
    ) as HTMLInputElement;
    fireEvent.change(apiKeyInput, { target: { value: 'saved-key' } });
    const saveBtn = document.querySelector(
      '[data-testid="extension-settings-save"]',
    ) as HTMLButtonElement;
    fireEvent.click(saveBtn);

    await waitFor(() => {
      const raw = localStorage.getItem(
        `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
      );
      expect(raw).toBe('"saved-key"');
    });

    // Now edit without saving
    fireEvent.change(apiKeyInput, { target: { value: 'unsaved-change' } });

    // Click cancel
    const cancelBtn = document.querySelector(
      '[data-testid="extension-settings-cancel"]',
    ) as HTMLButtonElement;
    fireEvent.click(cancelBtn);

    // The input should revert to the last-saved value
    await waitFor(() => {
      expect(apiKeyInput.value).toBe('saved-key');
    });

    // localStorage should still have the saved value (not the unsaved change)
    const raw = localStorage.getItem(
      `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
    );
    expect(raw).toBe('"saved-key"');
  });

  // T17: Shared cleanup helper — diagnostics removal and settings UI state reset
  // on disable/unload, preserving unrelated extension state.
  it('disable clears targeted extension diagnostics and settings while preserving unrelated extension state', async () => {
    const OTHER_EXTENSION_ID = 'com.example.other';
    const otherManifest = {
      id: OTHER_EXTENSION_ID as never,
      version: '1.0.0',
      label: 'Other Extension',
      settingsSchema: {
        schema: {
          type: 'object',
          properties: {
            otherKey: {
              type: 'string',
              title: 'Other Key',
              default: 'other-default',
            },
          },
        },
      },
    };

    // Pre-populate localStorage for both extensions to simulate saved settings
    localStorage.setItem(
      `reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`,
      '"settings-key"',
    );
    localStorage.setItem(
      `reigh.ext.${OTHER_EXTENSION_ID}.otherKey`,
      '"other-key"',
    );

    // Define extensions once so manifest references are stable across re-renders
    const settingsExt = defineExtension({ manifest: settingsManifest });
    const otherExt = defineExtension({ manifest: otherManifest });

    let capturedRuntime: ReturnType<typeof useVideoEditorRuntime> | null = null;

    function CaptureRuntime() {
      capturedRuntime = useVideoEditorRuntime();
      return null;
    }

    function Host({ includeSettings }: { includeSettings: boolean }) {
      const exts = includeSettings
        ? [settingsExt, otherExt]
        : [otherExt];
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={exts}
        >
          <CaptureRuntime />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host includeSettings />);

    await waitFor(() => {
      expect(capturedRuntime).not.toBeNull();
    });

    // Both extensions' settings should be in localStorage
    expect(
      localStorage.getItem(`reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`),
    ).toBe('"settings-key"');
    expect(
      localStorage.getItem(`reigh.ext.${OTHER_EXTENSION_ID}.otherKey`),
    ).toBe('"other-key"');

    // Disable the settings extension (remove from props)
    rerender(<Host includeSettings={false} />);

    await waitFor(() => {
      // Targeted extension's settings localStorage must be cleared
      expect(
        localStorage.getItem(`reigh.ext.${SETTINGS_EXTENSION_ID}.apiKey`),
      ).toBeNull();
    });

    // Unrelated extension's settings localStorage must be preserved
    expect(
      localStorage.getItem(`reigh.ext.${OTHER_EXTENSION_ID}.otherKey`),
    ).toBe('"other-key"');

    // Targeted extension's diagnostics must be cleared
    const snapshot = capturedRuntime?.diagnosticCollection?.getSnapshot() ?? [];
    const settingsExtDiags = snapshot.filter(
      (d) => d.extensionId === SETTINGS_EXTENSION_ID,
    );
    expect(settingsExtDiags).toEqual([]);

    // Unrelated extension's diagnostics should still be present
    const otherExtDiags = snapshot.filter(
      (d) => d.extensionId === OTHER_EXTENSION_ID,
    );
    expect(otherExtDiags.length).toBeGreaterThan(0);
  });
});

describe('EditorRuntimeProvider render-boundary recovery', () => {
  const SLOT_EXTENSION_ID = 'com.example.slot-ext';

  const slotManifest = {
    id: SLOT_EXTENSION_ID as never,
    version: '1.0.0',
    label: 'Slot Extension',
    contributions: [
      {
        kind: 'slot' as const,
        id: 'slot-ext-header',
        slot: 'header',
        order: 0,
      },
    ],
  };

  it('surface detach removes contributions on disable — re-enable restores them fresh', async () => {
    const slotExt = defineExtension({ manifest: slotManifest });

    let capturedConfigSlots: string[] | null = null;
    let capturedRuntime: ReturnType<typeof useVideoEditorRuntime> | null = null;

    function Capture() {
      capturedRuntime = useVideoEditorRuntime();
      capturedConfigSlots = capturedRuntime?.extensionRuntime?.config?.slots
        ? Object.keys(capturedRuntime.extensionRuntime.config.slots)
        : null;
      return null;
    }

    function Host({ includeSlot }: { includeSlot: boolean }) {
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={includeSlot ? [slotExt] : []}
        >
          <Capture />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host includeSlot />);

    await waitFor(() => {
      expect(capturedRuntime).not.toBeNull();
    });

    // Slot 'header' should be in the config while the extension is loaded
    expect(capturedConfigSlots).toContain('header');

    // Disable the extension (remove from extensions list)
    rerender(<Host includeSlot={false} />);

    await waitFor(() => {
      // After disable, the slot should be gone from the config
      expect(capturedConfigSlots).not.toContain('header');
    });

    // Re-enable the extension
    rerender(<Host includeSlot />);

    await waitFor(() => {
      // After re-enable, the slot should be back — fresh surface mount
      expect(capturedConfigSlots).toContain('header');
    });

    // Verify diagnostics are clean after re-enable (no stale error state)
    const snapshot = capturedRuntime?.diagnosticCollection?.getSnapshot() ?? [];
    const slotDiags = snapshot.filter(
      (d) => d.extensionId === SLOT_EXTENSION_ID && d.severity === 'error',
    );
    expect(slotDiags).toEqual([]);
  });

  it('re-enable after disable produces fresh contributions with no duplicates', async () => {
    const slotExt = defineExtension({ manifest: slotManifest });

    let capturedConfigSlots: string[] | null = null;

    function Capture() {
      const rt = useVideoEditorRuntime();
      capturedConfigSlots = rt?.extensionRuntime?.config?.slots
        ? Object.keys(rt.extensionRuntime.config.slots)
        : null;
      return null;
    }

    function Host({ includeSlot }: { includeSlot: boolean }) {
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={includeSlot ? [slotExt] : []}
        >
          <Capture />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host includeSlot />);

    await waitFor(() => {
      expect(capturedConfigSlots).toContain('header');
    });

    // First disable
    rerender(<Host includeSlot={false} />);
    await waitFor(() => {
      expect(capturedConfigSlots).not.toContain('header');
    });

    // Re-enable
    rerender(<Host includeSlot />);
    await waitFor(() => {
      expect(capturedConfigSlots).toContain('header');
    });

    // Disable again
    rerender(<Host includeSlot={false} />);
    await waitFor(() => {
      expect(capturedConfigSlots).not.toContain('header');
    });

    // Re-enable again — should still get exactly one slot contribution
    rerender(<Host includeSlot />);
    await waitFor(() => {
      expect(capturedConfigSlots).toContain('header');
    });

    // Only 'header' should be present, with no duplicates
    expect(capturedConfigSlots).toHaveLength(1);
    expect(capturedConfigSlots![0]).toBe('header');
  });
});

// ---------------------------------------------------------------------------
// T22: Focused per-registry scoped cleanup tests
// ---------------------------------------------------------------------------
// These tests verify that each lifecycle-owned contribution registry
// (effects, transitions, shaders, clip-types) correctly scopes cleanup to
// only the removed extension's records, preserving unrelated extensions.
//
// Agent tools and live data registries are future-only scaffolding and are
// NOT exposed as public contribution systems (see provider comments).

describe('EditorRuntimeProvider transition registry scoped cleanup', () => {
  it('clears only the removed extension transition records and preserves unrelated extension records', async () => {
    const EXT_A = 'com.example.transition-ext-a';
    const EXT_B = 'com.example.transition-ext-b';
    const transitionAId = 'transition-a';
    const transitionBId = 'transition-b';
    const disposeA = vi.fn();
    const disposeB = vi.fn();

    let latestRecords: readonly TransitionRegistryRecord[] = [];

    const extA = defineExtension({
      manifest: {
        id: EXT_A as never,
        version: '1.0.0',
        label: 'Transition Extension A',
      },
    });
    const extB = defineExtension({
      manifest: {
        id: EXT_B as never,
        version: '1.0.0',
        label: 'Transition Extension B',
      },
    });

    function CaptureTransitions() {
      const { registry } = useTransitionRegistryContext();
      latestRecords = useTransitionRegistryContext().snapshot.records;

      useEffect(() => {
        const hA = registry.register(transitionRecord(transitionAId, EXT_A, disposeA));
        const hB = registry.register(transitionRecord(transitionBId, EXT_B, disposeB));
        return () => {
          hA.dispose();
          hB.dispose();
        };
      }, [registry]);

      return null;
    }

    function Host({ includeA }: { includeA: boolean }) {
      const exts = includeA ? [extA, extB] : [extB];
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={exts}
        >
          <CaptureTransitions />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host includeA />);

    await waitFor(() => {
      expect(latestRecords.map((r) => r.transitionId)).toEqual(
        expect.arrayContaining([transitionAId, transitionBId]),
      );
    });

    // Remove extension A
    rerender(<Host includeA={false} />);

    await waitFor(() => {
      // Extension A's transition record must be removed
      expect(latestRecords.map((r) => r.transitionId)).not.toContain(transitionAId);
    });

    // Extension B's transition record must be preserved
    expect(latestRecords.map((r) => r.transitionId)).toContain(transitionBId);
    expect(latestRecords.map((r) => r.transitionId)).toHaveLength(1);
    expect(disposeA).toHaveBeenCalled();
    expect(disposeB).not.toHaveBeenCalled();
  });
});

describe('EditorRuntimeProvider shader registry scoped cleanup', () => {
  it('clears only the removed extension shader records and preserves unrelated extension records', async () => {
    const EXT_A = 'com.example.shader-ext-a';
    const EXT_B = 'com.example.shader-ext-b';
    const shaderAId = 'shader.ext.a.grade';
    const shaderBId = 'shader.ext.b.blur';
    const disposeA = vi.fn();
    const disposeB = vi.fn();

    let latestRecords: readonly ShaderEffectRegistryRecord[] = [];

    const extA = defineExtension({
      manifest: {
        id: EXT_A as never,
        version: '1.0.0',
        label: 'Shader Extension A',
      },
    });
    const extB = defineExtension({
      manifest: {
        id: EXT_B as never,
        version: '1.0.0',
        label: 'Shader Extension B',
      },
    });

    function CaptureShaders() {
      const { registry } = useShaderEffectRegistryContext();
      latestRecords = useShaderEffectRegistryContext().snapshot.records;

      useEffect(() => {
        const hA = registry.register(shaderRecord(shaderAId, EXT_A, [], disposeA));
        const hB = registry.register(shaderRecord(shaderBId, EXT_B, [], disposeB));
        return () => {
          hA.dispose();
          hB.dispose();
        };
      }, [registry]);

      return null;
    }

    function Host({ includeA }: { includeA: boolean }) {
      const exts = includeA ? [extA, extB] : [extB];
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={exts}
        >
          <CaptureShaders />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host includeA />);

    await waitFor(() => {
      expect(latestRecords.map((r) => r.shaderId)).toEqual(
        expect.arrayContaining([shaderAId, shaderBId]),
      );
    });

    // Remove extension A
    rerender(<Host includeA={false} />);

    await waitFor(() => {
      // Extension A's shader record must be removed
      expect(latestRecords.map((r) => r.shaderId)).not.toContain(shaderAId);
    });

    // Extension B's shader record must be preserved
    expect(latestRecords.map((r) => r.shaderId)).toContain(shaderBId);
    expect(latestRecords.map((r) => r.shaderId)).toHaveLength(1);
    expect(disposeA).toHaveBeenCalled();
    expect(disposeB).not.toHaveBeenCalled();
  });
});

describe('EditorRuntimeProvider clip-type registry scoped cleanup', () => {
  it('clears only the removed extension clip-type records and preserves unrelated extension records', async () => {
    const EXT_A = 'com.example.cliptype-ext-a';
    const EXT_B = 'com.example.cliptype-ext-b';
    const clipAId = 'clip-type-a';
    const clipBId = 'clip-type-b';
    const disposeA = vi.fn();
    const disposeB = vi.fn();

    let latestRecords: readonly ClipTypeRegistryRecord[] = [];

    const extA = defineExtension({
      manifest: {
        id: EXT_A as never,
        version: '1.0.0',
        label: 'ClipType Extension A',
      },
    });
    const extB = defineExtension({
      manifest: {
        id: EXT_B as never,
        version: '1.0.0',
        label: 'ClipType Extension B',
      },
    });

    function CaptureClipTypes() {
      const { registry } = useClipTypeRegistryContext();
      latestRecords = useClipTypeRegistryContext().snapshot.records;

      useEffect(() => {
        const hA = registry.register(clipTypeRecord(clipAId, EXT_A, disposeA));
        const hB = registry.register(clipTypeRecord(clipBId, EXT_B, disposeB));
        return () => {
          hA.dispose();
          hB.dispose();
        };
      }, [registry]);

      return null;
    }

    function Host({ includeA }: { includeA: boolean }) {
      const exts = includeA ? [extA, extB] : [extB];
      return (
        <EditorRuntimeProvider
          dataProvider={{} as DataProvider}
          timelineId="timeline-1"
          userId="user-1"
          extensions={exts}
        >
          <CaptureClipTypes />
        </EditorRuntimeProvider>
      );
    }

    const { rerender } = render(<Host includeA />);

    await waitFor(() => {
      expect(latestRecords.map((r) => r.clipTypeId)).toEqual(
        expect.arrayContaining([clipAId, clipBId]),
      );
    });

    // Remove extension A
    rerender(<Host includeA={false} />);

    await waitFor(() => {
      // Extension A's clip-type record must be removed
      expect(latestRecords.map((r) => r.clipTypeId)).not.toContain(clipAId);
    });

    // Extension B's clip-type record must be preserved
    expect(latestRecords.map((r) => r.clipTypeId)).toContain(clipBId);
    expect(latestRecords.map((r) => r.clipTypeId)).toHaveLength(1);
    expect(disposeA).toHaveBeenCalled();
    expect(disposeB).not.toHaveBeenCalled();
  });
});
