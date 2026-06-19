import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useLayoutEffect } from 'react';
import { useEffects } from '@/tools/video-editor/hooks/useEffects.ts';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader.ts';
import { createProposalRuntime } from '@/tools/video-editor/lib/proposal-runtime.ts';
import { useEffectRegistry } from '@/tools/video-editor/hooks/useEffectRegistry.ts';
import {
  EffectRegistryProvider,
  useEffectRegistryContext,
} from '@/tools/video-editor/effects/registry/EffectRegistryContext.tsx';
import {
  EffectCatalogProvider,
  useResolvedEffectCatalog,
  type VideoEditorEffectCatalog,
} from '@/tools/video-editor/hooks/useEffectResources.ts';
import {
  SequenceComponentCatalogProvider,
  useResolvedSequenceComponentCatalog,
  type VideoEditorSequenceComponentCatalog,
} from '@/tools/video-editor/hooks/useSequenceResources.ts';
import { SequenceComponentRegistryProvider } from '@/tools/video-editor/sequences/SequenceComponentRegistryContext.tsx';
import { TimelineStoreProvider } from '@/tools/video-editor/hooks/timelineStore.ts';
import { useTimelineState } from '@/tools/video-editor/hooks/useTimelineState.ts';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import {
  DataProviderWrapper,
  useVideoEditorRuntime,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  normalizeExtensionRuntime,
  type ExtensionRuntime,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createExtensionDiagnosticsService,
  createExtensionLifecycleHost,
  type ExtensionLifecycleHost,
} from '@/tools/video-editor/runtime/extensionLifecycle.ts';
import {
  createExtensionContext,
  createCreativeContext,
  type ReighExtension,
  type CommandContribution,
  type KeybindingContribution,
  type ContextMenuItemContribution,
  type ExtensionCommandService,
  createDiagnosticCollection,
  type DiagnosticCollection,
} from '@reigh/editor-sdk';
import type { CreativeContext } from '@reigh/editor-sdk';
import type {
  VideoEditorAuthHost,
  VideoEditorProjectHost,
  VideoEditorShotsHost,
  VideoEditorMediaLightboxHost,
  VideoEditorAgentChatHost,
  VideoEditorToastHost,
  VideoEditorTelemetryHost,
} from '@/tools/video-editor/runtime/ports.ts';
import { createCommandRegistry, type CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry.ts';
import { createEffectRegistrationService } from '@/tools/video-editor/runtime/effectRegistrationService.ts';
import type { EffectRegistry } from '@/tools/video-editor/effects/registry/types.ts';
import { createTransitionRegistrationService } from '@/tools/video-editor/runtime/transitionRegistrationService.ts';
import type { TransitionRegistry } from '@/tools/video-editor/transitions/registry/types.ts';
import { createClipTypeRegistrationService } from '@/tools/video-editor/runtime/clipTypeRegistrationService.ts';
import type { ClipTypeRegistry } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import {
  removeExtensionDiagnosticsFromCollection,
  syncExtensionDiagnosticsToCollection,
} from '@/tools/video-editor/runtime/diagnosticCollectionSync.ts';
import {
  TransitionRegistryProvider,
  useTransitionRegistryContext,
} from '@/tools/video-editor/transitions/registry/index.ts';
import {
  ClipTypeRegistryProvider,
  useClipTypeRegistryContext,
} from '@/tools/video-editor/clip-types/index.ts';

export interface EditorRuntimeProviderProps {
  dataProvider: DataProvider;
  timelineId: string;
  timelineName?: string | null;
  userId?: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
  runtime?: Pick<VideoEditorRuntimeContextValue, 'assetResolver' | 'exporter' | 'hostContext'>;
  extensions?: readonly ReighExtension[];
  children: ReactNode;
}

function EditorRuntimeProviderInner({
  children,
  userId,
  effectCatalog,
  sequenceComponentCatalog,
  lifecycleHostRef,
  extensionRuntime,
  commandRegistryRef,
  effectRegistryRef,
  transitionRegistryRef,
}: {
  children: ReactNode;
  userId: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  extensionRuntime: ExtensionRuntime;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
  effectRegistryRef: React.MutableRefObject<EffectRegistry | null>;
  transitionRegistryRef: React.MutableRefObject<TransitionRegistry | null>;
  clipTypeRegistryRef: React.MutableRefObject<ClipTypeRegistry | null>;
}) {
  const effectsQuery = useEffects(userId, { enabled: !effectCatalog && Boolean(userId) });
  const effectResources = useResolvedEffectCatalog(userId, effectCatalog);
  const sequenceComponentResources = useResolvedSequenceComponentCatalog(
    userId,
    sequenceComponentCatalog,
  );
  useEffectRegistry(
    effectsQuery.data?.map((effect) => ({
      slug: effect.slug,
      code: effect.code,
    })),
    effectResources.effects,
  );

  const { store } = useTimelineState();
  const diagnosticCollection = useVideoEditorRuntime().diagnosticCollection;
  const activeExtensionIds = useMemo(
    () => new Set(extensionRuntime.extensions.map((ext) => ext.manifest.id as string)),
    [extensionRuntime.extensions],
  );

  // ---- M3: live creative context for extensions --------------------------
  const timelineReader = useMemo(
    () =>
      createTimelineReader({
        data: () => {
          const data = store.getState().data.data;
          if (!data) {
            throw new Error('Timeline data is not ready.');
          }
          return data;
        },
        projectId: null,
        extensionRequirements: extensionRuntime.requirements,
      }),
    [store, extensionRuntime.requirements],
  );

  const proposalRuntimeRef = useRef<ReturnType<typeof createProposalRuntime> | null>(null);
  if (!proposalRuntimeRef.current) {
    const ops = store.getState().timelineOps;
    if (ops) {
      proposalRuntimeRef.current = createProposalRuntime({
        timelineOps: ops,
        reader: timelineReader,
      });
      store.getState().syncSlices({ proposalRuntime: proposalRuntimeRef.current });
    }
  }

  const liveCreativeOverrides = useMemo<Partial<CreativeContext>>(() => {
    const ops = store.getState().timelineOps ?? undefined;
    const proposals = proposalRuntimeRef.current ?? undefined;
    return {
      timeline: ops as any,
      reader: timelineReader,
      proposals: proposals as any,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timelineReader, store]);

  useEffect(() => {
    const host = lifecycleHostRef.current;
    const registry = commandRegistryRef.current;
    if (!host) return;

    // Ingest declarative command/keybinding/context-menu contributions
    if (registry) {
      for (const ext of extensionRuntime.extensions) {
        const extId = ext.manifest.id as string;
        for (const contrib of ext.manifest.contributions ?? []) {
          switch (contrib.kind) {
            case 'command':
              registry.ingestCommandContribution(extId, contrib as CommandContribution);
              break;
            case 'keybinding':
              registry.ingestKeybindingContribution(extId, contrib as KeybindingContribution);
              break;
            case 'contextMenuItem':
              registry.ingestContextMenuItemContribution(extId, contrib as ContextMenuItemContribution);
              break;
          }
        }
      }
    }

    host.synchronize(
      extensionRuntime.extensions,
      (ext) => {
        const extId = ext.manifest.id as string;
        const effectRegistry = effectRegistryRef.current;
        const transitionRegistry = transitionRegistryRef.current;
        const clipTypeRegistry = clipTypeRegistryRef.current;
        // Create per-extension commands service backed by the shared registry
        const commandsService: ExtensionCommandService | undefined = registry
          ? {
              registerCommand(commandId, handler, options) {
                return registry.registerCommand(extId, commandId, handler, options);
              },
            }
          : undefined;
        // Create per-extension effects service backed by the shared EffectRegistry.
        // The lifecycle host creates per-extension diagnostics services during
        // synchronize() before calling contextFactory, so we can obtain the
        // correct one from the host.
        const effectsService = effectRegistry
          ? createEffectRegistrationService({
              extension: ext,
              effectRegistry,
              diagnosticsService:
                host.lifecycles.get(extId)?.diagnosticsService ??
                createExtensionDiagnosticsService(extId),
            })
          : undefined;
        // Create per-extension transitions service backed by the shared TransitionRegistry.
        const transitionsService = transitionRegistry
          ? createTransitionRegistrationService({
              extension: ext,
              transitionRegistry,
              diagnosticsService:
                host.lifecycles.get(extId)?.diagnosticsService ??
                createExtensionDiagnosticsService(extId),
            })
          : undefined;
        // Create per-extension clipTypes service backed by the shared ClipTypeRegistry.
        const clipTypesService = clipTypeRegistry
          ? createClipTypeRegistrationService({
              extension: ext,
              clipTypeRegistry,
              diagnosticsService:
                host.lifecycles.get(extId)?.diagnosticsService ??
                createExtensionDiagnosticsService(extId),
            })
          : undefined;
        return createExtensionContext(ext, liveCreativeOverrides, commandsService, effectsService, transitionsService, clipTypesService);
      },
    );
    syncExtensionDiagnosticsToCollection(diagnosticCollection, 'extension-lifecycle', [
      ...extensionRuntime.diagnostics,
      ...host.diagnostics,
    ], { activeExtensionIds });
  }, [activeExtensionIds, diagnosticCollection, lifecycleHostRef, extensionRuntime, liveCreativeOverrides, commandRegistryRef]);

  // Sync proposalRuntime to the store so host-owned UI (ProposalPanel) can access it.
  useEffect(() => {
    const pr = proposalRuntimeRef.current;
    if (pr) {
      store.getState().syncSlices({ proposalRuntime: pr });
    }
  }, [store, extensionRuntime.requirements]);

  useLayoutEffect(() => {
    store.getState().syncSlices({
      availability: { mounted: true },
    });
  }, [store]);

  return (
    <EffectRegistryProvider>
      <TransitionRegistryProvider>
        <ClipTypeRegistryProvider>
        <EffectCatalogProvider value={effectResources}>
          <EditorRuntimeEffectRegistryLifecycle
            effectsQueryData={effectsQuery.data}
            effectResources={effectResources.effects}
            lifecycleHostRef={lifecycleHostRef}
            commandRegistryRef={commandRegistryRef}
            effectRegistryRef={effectRegistryRef}
            activeExtensionIds={activeExtensionIds}
          />
          <EditorRuntimeTransitionRegistryLifecycle
            lifecycleHostRef={lifecycleHostRef}
            commandRegistryRef={commandRegistryRef}
            transitionRegistryRef={transitionRegistryRef}
            activeExtensionIds={activeExtensionIds}
          />
          <EditorRuntimeClipTypeRegistryLifecycle
            lifecycleHostRef={lifecycleHostRef}
            commandRegistryRef={commandRegistryRef}
            clipTypeRegistryRef={clipTypeRegistryRef}
            activeExtensionIds={activeExtensionIds}
          />
          <SequenceComponentCatalogProvider value={sequenceComponentResources}>
            <SequenceComponentRegistryProvider components={sequenceComponentResources.components}>
              <TimelineStoreProvider store={store}>
                {children}
              </TimelineStoreProvider>
            </SequenceComponentRegistryProvider>
          </SequenceComponentCatalogProvider>
        </EffectCatalogProvider>
        </ClipTypeRegistryProvider>
      </TransitionRegistryProvider>
    </EffectRegistryProvider>
  );
}

function EditorRuntimeEffectRegistryLifecycle({
  effectsQueryData,
  effectResources,
  lifecycleHostRef,
  commandRegistryRef,
  effectRegistryRef,
  activeExtensionIds,
}: {
  effectsQueryData: Array<{ slug: string; code: string }> | undefined;
  effectResources: VideoEditorEffectCatalog['effects'];
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
  effectRegistryRef: React.MutableRefObject<EffectRegistry | null>;
  activeExtensionIds: ReadonlySet<string>;
}) {
  const { registry: effectRegistry, snapshot: effectRegistrySnapshot } = useEffectRegistryContext();
  // Expose the effect registry to the outer synchronize effect via ref.
  // Set during render so the parent's useEffect can read it after commit.
  effectRegistryRef.current = effectRegistry;
  const diagnosticCollection = useVideoEditorRuntime().diagnosticCollection;

  useEffectRegistry(
    effectsQueryData?.map((effect) => ({
      slug: effect.slug,
      code: effect.code,
    })),
    effectResources,
  );

  useEffect(() => {
    const host = lifecycleHostRef.current;
    const commandRegistry = commandRegistryRef.current;
    if (!host) return;
    const handle = host.onLifecycleDisposed((extensionId: string) => {
      commandRegistry?.unregisterAll(extensionId);
      effectRegistry.unregisterOwner(extensionId);
      removeExtensionDiagnosticsFromCollection(diagnosticCollection, extensionId);
    });
    return () => handle.dispose();
  }, [commandRegistryRef, diagnosticCollection, effectRegistry, lifecycleHostRef]);

  useEffect(() => {
    syncExtensionDiagnosticsToCollection(
      diagnosticCollection,
      'effect-registry',
      effectRegistrySnapshot.diagnostics,
      { activeExtensionIds },
    );
  }, [activeExtensionIds, diagnosticCollection, effectRegistrySnapshot]);

  useEffect(() => {
    const registry = commandRegistryRef.current;
    if (!registry) return;
    const sync = () => {
      syncExtensionDiagnosticsToCollection(
        diagnosticCollection,
        'command-registry',
        registry.diagnostics,
        { activeExtensionIds },
      );
    };
    sync();
    const handle = registry.subscribe(sync);
    return () => handle.dispose();
  }, [activeExtensionIds, commandRegistryRef, diagnosticCollection]);

  return null;
}

function EditorRuntimeTransitionRegistryLifecycle({
  lifecycleHostRef,
  commandRegistryRef,
  transitionRegistryRef,
  activeExtensionIds,
}: {
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
  transitionRegistryRef: React.MutableRefObject<TransitionRegistry | null>;
  activeExtensionIds: ReadonlySet<string>;
}) {
  const { registry: transitionRegistry, snapshot: transitionRegistrySnapshot } = useTransitionRegistryContext();
  // Expose the transition registry to the outer synchronize effect via ref.
  transitionRegistryRef.current = transitionRegistry;
  const diagnosticCollection = useVideoEditorRuntime().diagnosticCollection;

  useEffect(() => {
    const host = lifecycleHostRef.current;
    const commandRegistry = commandRegistryRef.current;
    if (!host) return;
    const handle = host.onLifecycleDisposed((extensionId: string) => {
      commandRegistry?.unregisterAll(extensionId);
      transitionRegistry.unregisterOwner(extensionId);
      removeExtensionDiagnosticsFromCollection(diagnosticCollection, extensionId);
    });
    return () => handle.dispose();
  }, [commandRegistryRef, diagnosticCollection, transitionRegistry, lifecycleHostRef]);

  useEffect(() => {
    syncExtensionDiagnosticsToCollection(
      diagnosticCollection,
      'transition-registry',
      transitionRegistrySnapshot.diagnostics,
      { activeExtensionIds },
    );
  }, [activeExtensionIds, diagnosticCollection, transitionRegistrySnapshot]);

  return null;
}

function EditorRuntimeClipTypeRegistryLifecycle({
  lifecycleHostRef,
  commandRegistryRef,
  clipTypeRegistryRef,
  activeExtensionIds,
}: {
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
  clipTypeRegistryRef: React.MutableRefObject<ClipTypeRegistry | null>;
  activeExtensionIds: ReadonlySet<string>;
}) {
  const { registry: clipTypeRegistry, snapshot: clipTypeRegistrySnapshot } = useClipTypeRegistryContext();
  // Expose the clip-type registry to the outer synchronize effect via ref.
  clipTypeRegistryRef.current = clipTypeRegistry;
  const diagnosticCollection = useVideoEditorRuntime().diagnosticCollection;

  useEffect(() => {
    const host = lifecycleHostRef.current;
    const commandRegistry = commandRegistryRef.current;
    if (!host) return;
    const handle = host.onLifecycleDisposed((extensionId: string) => {
      commandRegistry?.unregisterAll(extensionId);
      clipTypeRegistry.unregisterOwner(extensionId);
      removeExtensionDiagnosticsFromCollection(diagnosticCollection, extensionId);
    });
    return () => handle.dispose();
  }, [commandRegistryRef, diagnosticCollection, clipTypeRegistry, lifecycleHostRef]);

  useEffect(() => {
    syncExtensionDiagnosticsToCollection(
      diagnosticCollection,
      'clip-type-registry',
      clipTypeRegistrySnapshot.diagnostics,
      { activeExtensionIds },
    );
  }, [activeExtensionIds, diagnosticCollection, clipTypeRegistrySnapshot]);

  return null;
}

export function EditorRuntimeProvider({
  dataProvider,
  timelineId,
  timelineName,
  userId = null,
  effectCatalog,
  sequenceComponentCatalog,
  runtime,
  extensions,
  children,
}: EditorRuntimeProviderProps) {
  // ---- extension normalization & lifecycle --------------------------------
  const extensionRuntime = useMemo<ExtensionRuntime>(
    () => normalizeExtensionRuntime(extensions ?? []),
    [extensions],
  );

  const lifecycleHostRef = useRef<ExtensionLifecycleHost | null>(null);
  if (!lifecycleHostRef.current) {
    lifecycleHostRef.current = createExtensionLifecycleHost();
  }

  // ---- M4: command registry (one per provider mount) -----------------------
  const commandRegistryRef = useRef<CommandRegistry | null>(null);
  if (!commandRegistryRef.current) {
    commandRegistryRef.current = createCommandRegistry();
  }

  // ---- M7: effect registry ref (registry is created by EffectRegistryProvider,
  //        exposed via context and stored here for the synchronize effect) ----
  const effectRegistryRef = useRef<EffectRegistry | null>(null);

  // ---- M8: transition registry ref (registry is created by TransitionRegistryProvider,
  //        exposed via context and stored here for the synchronize effect) ----
  const transitionRegistryRef = useRef<TransitionRegistry | null>(null);

  // ---- M9: clip-type registry ref (registry is created by ClipTypeRegistryProvider,
  //        exposed via context and stored here for the synchronize effect) ----
  const clipTypeRegistryRef = useRef<ClipTypeRegistry | null>(null);

  const diagnosticCollectionRef = useRef<DiagnosticCollection | null>(null);
  if (!diagnosticCollectionRef.current) {
    diagnosticCollectionRef.current = createDiagnosticCollection();
  }

  // Wire registry callbacks (stub — no host toast in browser context)
  useEffect(() => {
    const registry = commandRegistryRef.current;
    if (!registry) return;
    registry.setCallbacks({
      onCommandFailure: (commandId, error, extensionId) => {
        console.error(`[CommandRegistry] Command "${commandId}" failed (${extensionId}): ${error.message}`);
      },
      onReservedCommand: (commandId, extensionId) => {
        console.warn(`[CommandRegistry] Reserved command "${commandId}" rejected for extension "${extensionId}".`);
      },
      onReservedKeybinding: (key, extensionId, commandId) => {
        console.warn(`[CommandRegistry] Reserved keybinding "${key}" for "${commandId}" rejected for extension "${extensionId}".`);
      },
      onDuplicateCommand: (commandId, originalExtension, conflictingExtension) => {
        console.warn(`[CommandRegistry] Command "${commandId}" already registered by "${originalExtension}". Extension "${conflictingExtension}" cannot override it.`);
      },
      onKeybindingConflict: (key, originalExtension, conflictingExtension) => {
        console.warn(`[CommandRegistry] Keybinding "${key}" already bound by "${originalExtension}". Extension "${conflictingExtension}" cannot override it.`);
      },
      onContextMenuStaleTarget: (commandId, extensionId, reason) => {
        console.warn(`[CommandRegistry] Context menu command "${commandId}" rejected for extension "${extensionId}": ${reason}`);
      },
    });
  }, []);

  useEffect(() => {
    const host = lifecycleHostRef.current;
    return () => {
      host?.disposeAll();
    };
  }, []);

  // ---- stub hosts for browser-embedded contexts that don't provide full Reigh shell ----
  const stubShotsHost = useMemo<VideoEditorShotsHost>(() => ({
    shots: undefined,
    isLoading: false,
    error: null,
    refetchShots: () => {},
    finalVideoMap: new Map(),
    dismissFinalVideo: () => {},
  }), []);

  const stubMediaLightboxHost = useMemo<VideoEditorMediaLightboxHost>(() => ({
    Lightbox: (() => null) as unknown as VideoEditorMediaLightboxHost['Lightbox'],
    loadGenerationForLightbox: async () => null,
  }), []);

  const stubAgentChatHost = useMemo<VideoEditorAgentChatHost>(() => ({
    registerTimeline: () => {},
    unregisterTimeline: () => {},
  }), []);

  const stubToastHost = useMemo<VideoEditorToastHost>(() => ({
    error: () => '',
    success: () => '',
    warning: () => '',
    info: () => '',
  }), []);

  const stubTelemetryHost = useMemo<VideoEditorTelemetryHost>(() => ({
    log: (..._args: unknown[]) => {},
    warn: (..._args: unknown[]) => {},
    error: (..._args: unknown[]) => {},
  }), []);

  const defaultAssetResolver = useMemo(() => ({
    resolveAssetUrl: async (file: string) => file,
  }), []);

  const contextValue = useMemo<VideoEditorRuntimeContextValue>(() => ({
    provider: dataProvider,
    assetResolver: runtime?.assetResolver ?? defaultAssetResolver,
    auth: { userId } satisfies VideoEditorAuthHost,
    project: { projectId: null } satisfies VideoEditorProjectHost,
    shots: stubShotsHost,
    mediaLightbox: stubMediaLightboxHost,
    agentChat: stubAgentChatHost,
    toast: stubToastHost,
    telemetry: stubTelemetryHost,
    timelineId,
    timelineName,
    userId,
    exporter: runtime?.exporter ?? null,
    hostContext: runtime?.hostContext ?? null,
    extensions: extensionRuntime.config,
    extensionRuntime,
    commandRegistry: commandRegistryRef.current ?? undefined,
    diagnosticCollection: diagnosticCollectionRef.current ?? undefined,
  }), [
    dataProvider,
    runtime?.assetResolver,
    runtime?.exporter,
    runtime?.hostContext,
    userId,
    stubShotsHost,
    stubMediaLightboxHost,
    stubAgentChatHost,
    stubToastHost,
    stubTelemetryHost,
    defaultAssetResolver,
    timelineId,
    timelineName,
    extensionRuntime.config,
    extensionRuntime,
  ]);

  return (
    <DataProviderWrapper value={contextValue}>
      <EditorRuntimeProviderInner
        userId={userId}
        effectCatalog={effectCatalog}
        sequenceComponentCatalog={sequenceComponentCatalog}
        lifecycleHostRef={lifecycleHostRef}
        extensionRuntime={extensionRuntime}
        commandRegistryRef={commandRegistryRef}
        effectRegistryRef={effectRegistryRef}
        transitionRegistryRef={transitionRegistryRef}
        clipTypeRegistryRef={clipTypeRegistryRef}
      >
        {children}
      </EditorRuntimeProviderInner>
    </DataProviderWrapper>
  );
}
