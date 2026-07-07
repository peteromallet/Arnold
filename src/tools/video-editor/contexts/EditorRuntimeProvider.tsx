import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useLayoutEffect } from 'react';
import { useEffects } from '@/tools/video-editor/hooks/useEffects.ts';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader.ts';
import { createProposalRuntime, createProposalPersistenceBridge, type ProposalPersistenceProvider } from '@/tools/video-editor/lib/proposal-runtime.ts';
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
import type { DataProvider, ExtensionPersistenceService } from '@/tools/video-editor/data/DataProvider.ts';
import {
  DataProviderWrapper,
  useVideoEditorRuntime,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  normalizeExtensionRuntime,
  type ExtensionRuntime,
  type PackageStateInventoryEntry,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createExtensionDiagnosticsService,
  createExtensionLifecycleHost,
  type ExtensionLifecycleHost,
} from '@/tools/video-editor/runtime/extensionLifecycle.ts';
import {
  createCreativeContext,
  type ReighExtension,
  type CommandContribution,
  type KeybindingContribution,
  type ContextMenuItemContribution,
  type ExtensionCommandService,
  createDiagnosticCollection,
  type DiagnosticCollection,
} from '@reigh/editor-sdk';
import { createExtensionContext } from '@/tools/video-editor/runtime/extensionContextFactory';
import { createRendererRegistry } from '@/tools/video-editor/runtime/extensionRendererRegistry';
import {
  createInternalExtensionRenderSurface,
  resolveRegisteredSlotRenderers,
} from '@/tools/video-editor/runtime/extensionRenderSurface';
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
import { createShaderRegistrationService } from '@/tools/video-editor/runtime/shaderRegistrationService.ts';
import type { ShaderEffectRegistry } from '@/tools/video-editor/shaders/registry/types.ts';
import { createClipTypeRegistrationService } from '@/tools/video-editor/runtime/clipTypeRegistrationService.ts';
import type { ClipTypeRegistry } from '@/tools/video-editor/clip-types/ClipTypeRegistry.ts';
import { createAgentToolRegistry, type AgentToolRegistry } from '@/tools/video-editor/runtime/agentToolRegistry.ts';
import { createAgentToolInvocationService, type AgentToolInvocationService } from '@/tools/video-editor/runtime/agentToolInvocationService.ts';
import type { AgentToolContribution, AgentToolRegistrationService, AgentToolHandler, ShaderRegistrationService } from '@reigh/editor-sdk';
import type { ProcessStatus } from '@/sdk/video/families/processes';
import {
  clearExtensionSettingsFromLocalStorage,
  removeExtensionDiagnosticsFromCollection,
  syncExtensionDiagnosticsToCollection,
  syncLiveDiagnosticsToCollection,
} from '@/tools/video-editor/runtime/diagnosticCollectionSync.ts';
import { createLiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import { createProcessManager, type ProcessManager } from '@/tools/video-editor/runtime/processes/ProcessManager.ts';
import type { ProcessResultAttachRecord } from '@/tools/video-editor/runtime/composition/processResultAttach.ts';
import type { LiveDataRegistry } from '@/tools/video-editor/runtime/liveDataRegistry.ts';
import { createLivePermissionService } from '@/tools/video-editor/runtime/livePermissions.ts';
import type { LivePermissionService } from '@/tools/video-editor/runtime/livePermissions.ts';
import type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';
import type { ExtensionSettingsSnapshot } from '@/tools/video-editor/runtime/extensionStateRepository';
import {
  createExtensionSettingsNotificationRegistry,
  type ExtensionSettingsNotificationRegistry,
} from '@/tools/video-editor/runtime/extensionSettingsNotification';
import type { CreateExtensionSettingsServiceOptions, SettingsPersistenceError } from '@reigh/editor-sdk';
import {
  TransitionRegistryProvider,
  useTransitionRegistryContext,
} from '@/tools/video-editor/transitions/registry/index.ts';
import {
  ClipTypeRegistryProvider,
  useClipTypeRegistryContext,
} from '@/tools/video-editor/clip-types/index.ts';
import {
  ShaderEffectRegistryProvider,
  useShaderEffectRegistryContext,
} from '@/tools/video-editor/shaders/registry/index.ts';

export interface EditorRuntimeProviderProps {
  dataProvider: DataProvider;
  timelineId: string;
  timelineName?: string | null;
  userId?: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
  runtime?: Pick<VideoEditorRuntimeContextValue, 'assetResolver' | 'exporter' | 'hostContext'>;
  extensions?: readonly ReighExtension[];
  /** Package-state inventory entries propagated from the loader (M5). */
  packageStateEntries?: readonly PackageStateInventoryEntry[];
  /** M5: Extension state repository for enable/disable persistence. */
  extensionStateRepository?: ExtensionStateRepository | null;
  /** M5: Trigger extension re-resolution after persistence writes. */
  triggerExtensionRefresh?: () => void;
  /** M6b: Host-provided process manager override. When absent, a default
   *  ProcessManager is created from the extension runtime's declared process
   *  specs. */
  processManager?: ProcessManager;
  children: ReactNode;
}

function createExtensionLiveSessions(
  registry: LiveDataRegistry,
  extensionId: string,
): CreativeContext['sessions'] {
  return {
    registerSource(source) {
      return registry.registerSourceWithOwner(source, extensionId);
    },
    getSource(sourceId) {
      return registry.getSource(sourceId);
    },
    listSources() {
      return registry.listSources();
    },
    openChannel(sourceId, kind, metadata) {
      return registry.openChannel(sourceId, kind, metadata);
    },
    closeChannel(channelId) {
      registry.closeChannel(channelId);
    },
    getChannelMetadata(channelId) {
      return registry.getChannelMetadata(channelId);
    },
    pushSample(channelId, frame) {
      registry.pushSample(channelId, frame);
    },
    subscribeSamples(channelId, listener) {
      return registry.subscribeSamples(channelId, listener);
    },
    bake(selection) {
      return registry.bake(selection);
    },
    removeLiveBindings(sourceId) {
      registry.removeLiveBindings(sourceId);
    },
    resolveBinding(bindingId) {
      return registry.resolveBinding(bindingId);
    },
    getBindingMetadata() {
      return registry.getBindingMetadata();
    },
    applySteeringDecision(decision) {
      registry.applySteeringDecision(decision);
    },
    getDiagnostics(sourceId) {
      return registry.getDiagnostics(sourceId);
    },
  };
}

function publishSettingsPersistenceDiagnostic(
  diagnosticCollection: DiagnosticCollection | null | undefined,
  event: SettingsPersistenceError,
): void {
  diagnosticCollection?.publish({
    id: `settings-persistence:${event.extensionId}:${event.revision}`,
    extensionId: event.extensionId,
    severity: 'warning',
    code: 'extension.settings.persistence_failed',
    message: `Failed to persist extension settings: ${event.message}`,
    source: 'provider',
    detail: {
      source: 'settings-persistence',
      operation: event.operation,
      revision: event.revision,
      message: event.message,
      ...(event.key !== undefined ? { key: event.key } : {}),
    },
  });
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
  shaderRegistryRef,
  clipTypeRegistryRef,
  agentToolRegistryRef,
  rendererRegistryRef,
  liveDataRegistryRef,
  proposalPersistenceProvider,
  settingsSnapshotsRef,
  settingsNotificationRegistryRef,
  extensionStateRepository,
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
  shaderRegistryRef: React.MutableRefObject<ShaderEffectRegistry | null>;
  clipTypeRegistryRef: React.MutableRefObject<ClipTypeRegistry | null>;
  agentToolRegistryRef: React.MutableRefObject<AgentToolRegistry | null>;
  rendererRegistryRef: React.MutableRefObject<ReturnType<typeof createRendererRegistry>>;
  liveDataRegistryRef: React.MutableRefObject<LiveDataRegistry | null>;
  proposalPersistenceProvider: ProposalPersistenceProvider | null | undefined;
  settingsSnapshotsRef: React.MutableRefObject<Record<string, ExtensionSettingsSnapshot> | null>;
  settingsNotificationRegistryRef: React.MutableRefObject<ExtensionSettingsNotificationRegistry | null>;
  extensionStateRepository: ExtensionStateRepository | null | undefined;
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

  // ── M3: Provider-owned proposal persistence bridge (lifecycle owned by
  //        EditorRuntimeProvider; gated on initialization readiness) ────
  const proposalRuntimeRef = useRef<ReturnType<typeof createProposalRuntime> | null>(null);
  if (!proposalRuntimeRef.current && proposalPersistenceProvider !== undefined) {
    const ops = store.getState().timelineOps;
    if (ops) {
      proposalRuntimeRef.current = createProposalRuntime({
        timelineOps: ops,
        reader: timelineReader,
        persistenceProvider: proposalPersistenceProvider ?? undefined,
      });
      store.getState().syncSlices({ proposalRuntime: proposalRuntimeRef.current });
    }
  }

  // ---- M10: Agent tool invocation service (composes registry + ProposalRuntime) -
  const agentToolInvocationServiceRef = useRef<AgentToolInvocationService | null>(null);
  if (!agentToolInvocationServiceRef.current) {
    const registry = agentToolRegistryRef.current;
    const pr = proposalRuntimeRef.current;
    if (registry && pr) {
      agentToolInvocationServiceRef.current = createAgentToolInvocationService({
        registry,
        proposalRuntime: pr,
      });
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
            case 'agentTool':
              agentToolRegistryRef.current?.ingestAgentToolContribution(extId, contrib as AgentToolContribution);
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
        const shaderRegistry = shaderRegistryRef.current;
        const clipTypeRegistry = clipTypeRegistryRef.current;
        const agentToolRegistry = agentToolRegistryRef.current;
        const diagnosticsService =
          host.lifecycles.get(extId)?.diagnosticsService ??
          createExtensionDiagnosticsService(extId);
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
              diagnosticsService,
            })
          : undefined;
        // Create per-extension transitions service backed by the shared TransitionRegistry.
        const transitionsService = transitionRegistry
          ? createTransitionRegistrationService({
              extension: ext,
              transitionRegistry,
              diagnosticsService,
            })
          : undefined;
        const shadersService: ShaderRegistrationService | undefined = shaderRegistry
          ? createShaderRegistrationService({
              extension: ext,
              shaderRegistry,
              diagnosticsService,
            })
          : undefined;
        // Create per-extension clipTypes service backed by the shared ClipTypeRegistry.
        const clipTypesService = clipTypeRegistry
          ? createClipTypeRegistrationService({
              extension: ext,
              clipTypeRegistry,
              diagnosticsService,
            })
          : undefined;
        // Create per-extension agent tools service backed by the shared AgentToolRegistry.
        const agentToolsService: AgentToolRegistrationService | undefined = agentToolRegistry
          ? {
              registerTool(toolId: string, handler: AgentToolHandler) {
                return agentToolRegistry.registerTool(extId, toolId, handler);
              },
              async invokeProcess(_toolId: string, _config: any) {
                return {
                  family: 'process' as const,
                  diagnostics: [{
                    severity: 'info' as const,
                    code: 'agent-tool/process-not-available',
                    message: `Process invocation is not available until M12.`,
                  }],
                };
              },
            }
          : undefined;
        const liveRegistry = liveDataRegistryRef.current;
        const creativeOverrides = liveRegistry
          ? {
              ...liveCreativeOverrides,
              sessions: createExtensionLiveSessions(liveRegistry, extId),
            }
          : liveCreativeOverrides;
        // T9: Build settings service options when repository is available
        const settingsOptions: CreateExtensionSettingsServiceOptions | undefined =
          extensionStateRepository && !extensionStateRepository.isDisposed
            ? {
                repository: extensionStateRepository,
                initialSnapshot:
                  settingsSnapshotsRef.current?.[extId] ??
                  undefined,
                onPersistenceSuccess(event) {
                  const notifyReg = settingsNotificationRegistryRef.current;
                  if (notifyReg && !notifyReg.isDisposed && event.extensionId === extId) {
                    notifyReg.notifySettingsChanged(extId);
                  }
                },
                onPersistenceError(event) {
                  if (event.extensionId === extId) {
                    publishSettingsPersistenceDiagnostic(diagnosticCollection, event);
                  }
                },
              }
            : undefined;

        const ctx = createExtensionContext(
          ext,
          creativeOverrides,
          commandsService,
          effectsService,
          transitionsService,
          clipTypesService,
          agentToolsService,
          shadersService,
          settingsOptions,
          createInternalExtensionRenderSurface({
            extension: ext,
            diagnosticsService,
            rendererRegistry: rendererRegistryRef.current,
          }),
        );

        // Register the settings service for explicit local-only listeners.
        // Manager-visible reload notifications are published from the
        // post-persist success callback above.
        const notifyReg = settingsNotificationRegistryRef.current;
        if (notifyReg && !notifyReg.isDisposed) {
          notifyReg.registerService(extId, ctx.services.settings);
        }

        return ctx;
      },
    );
    syncExtensionDiagnosticsToCollection(diagnosticCollection, 'extension-lifecycle', [
      ...extensionRuntime.diagnostics,
      ...host.diagnostics,
    ], { activeExtensionIds });
  }, [activeExtensionIds, diagnosticCollection, lifecycleHostRef, extensionRuntime, liveCreativeOverrides, commandRegistryRef, shaderRegistryRef, settingsNotificationRegistryRef, settingsSnapshotsRef, extensionStateRepository]);

  // Sync live registry diagnostics into the provider diagnostic collection
  useEffect(() => {
    const registry = liveDataRegistryRef.current;
    if (!registry || !diagnosticCollection) return;
    const sync = () => {
      syncLiveDiagnosticsToCollection(diagnosticCollection, registry.getDiagnostics());
    };
    sync();
    const handle = registry.subscribe(sync);
    return () => handle.dispose();
  }, [diagnosticCollection, liveDataRegistryRef]);

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
        <ShaderEffectRegistryProvider>
          <ClipTypeRegistryProvider>
            <EffectCatalogProvider value={effectResources}>
              <EditorRuntimeEffectRegistryLifecycle
                effectsQueryData={effectsQuery.data}
                effectResources={effectResources.effects}
                lifecycleHostRef={lifecycleHostRef}
                commandRegistryRef={commandRegistryRef}
                effectRegistryRef={effectRegistryRef}
                agentToolRegistryRef={agentToolRegistryRef}
                rendererRegistryRef={rendererRegistryRef}
                activeExtensionIds={activeExtensionIds}
              />
              <EditorRuntimeTransitionRegistryLifecycle
                lifecycleHostRef={lifecycleHostRef}
                commandRegistryRef={commandRegistryRef}
                transitionRegistryRef={transitionRegistryRef}
                activeExtensionIds={activeExtensionIds}
              />
              <EditorRuntimeShaderRegistryLifecycle
                lifecycleHostRef={lifecycleHostRef}
                shaderRegistryRef={shaderRegistryRef}
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
        </ShaderEffectRegistryProvider>
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
  agentToolRegistryRef,
  rendererRegistryRef,
  activeExtensionIds,
}: {
  effectsQueryData: Array<{ slug: string; code: string }> | undefined;
  effectResources: VideoEditorEffectCatalog['effects'];
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
  effectRegistryRef: React.MutableRefObject<EffectRegistry | null>;
  agentToolRegistryRef: React.MutableRefObject<AgentToolRegistry | null>;
  rendererRegistryRef: React.MutableRefObject<ReturnType<typeof createRendererRegistry>>;
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
    const agentToolRegistry = agentToolRegistryRef.current;
    if (!host) return;
    // Contribution cleanup per-family:
    // - command, effect, diagnostics, settings: production lifecycle-owned
    // - agentTool: future-only scaffolding, not yet a public contribution system
    const handle = host.onLifecycleDisposed((extensionId: string) => {
      commandRegistry?.unregisterAll(extensionId);
      rendererRegistryRef.current.unregisterAll(extensionId);
      effectRegistry.unregisterOwner(extensionId);
      agentToolRegistry?.unregisterAll(extensionId);
      removeExtensionDiagnosticsFromCollection(diagnosticCollection, extensionId);
      clearExtensionSettingsFromLocalStorage(extensionId);
    });
    return () => handle.dispose();
  }, [commandRegistryRef, diagnosticCollection, effectRegistry, lifecycleHostRef, agentToolRegistryRef, rendererRegistryRef]);

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
      clearExtensionSettingsFromLocalStorage(extensionId);
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

function EditorRuntimeShaderRegistryLifecycle({
  lifecycleHostRef,
  shaderRegistryRef,
  activeExtensionIds,
}: {
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  shaderRegistryRef: React.MutableRefObject<ShaderEffectRegistry | null>;
  activeExtensionIds: ReadonlySet<string>;
}) {
  const { registry: shaderRegistry, snapshot: shaderRegistrySnapshot } = useShaderEffectRegistryContext();
  shaderRegistryRef.current = shaderRegistry;
  const diagnosticCollection = useVideoEditorRuntime().diagnosticCollection;

  useEffect(() => {
    const host = lifecycleHostRef.current;
    if (!host) return;
    const handle = host.onLifecycleDisposed((extensionId: string) => {
      shaderRegistry.unregisterOwner(extensionId);
      removeExtensionDiagnosticsFromCollection(diagnosticCollection, extensionId);
      clearExtensionSettingsFromLocalStorage(extensionId);
    });
    return () => handle.dispose();
  }, [diagnosticCollection, shaderRegistry, lifecycleHostRef]);

  useEffect(() => {
    const shaderDiagnostics = [
      ...shaderRegistrySnapshot.diagnostics,
      ...shaderRegistrySnapshot.records.flatMap((record) =>
        (record.diagnostics ?? []).map((diagnostic) => ({
          ...diagnostic,
          extensionId: diagnostic.extensionId ?? record.ownerExtensionId,
          contributionId: diagnostic.contributionId ?? record.contributionId,
          detail: {
            shaderId: record.shaderId,
            ...(diagnostic.detail ?? {}),
          },
        })),
      ),
    ];

    syncExtensionDiagnosticsToCollection(
      diagnosticCollection,
      'shader-effect-registry',
      shaderDiagnostics,
      { activeExtensionIds },
    );
  }, [activeExtensionIds, diagnosticCollection, shaderRegistrySnapshot]);

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
      clearExtensionSettingsFromLocalStorage(extensionId);
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
  packageStateEntries,
  extensionStateRepository,
  triggerExtensionRefresh,
  processManager: hostProcessManager,
  children,
}: EditorRuntimeProviderProps) {
  // ---- extension normalization & lifecycle --------------------------------
  const extensionRuntime = useMemo<ExtensionRuntime>(
    () => normalizeExtensionRuntime(extensions ?? [], packageStateEntries),
    [extensions, packageStateEntries],
  );

  // ---- M11: live data registry (one per provider mount) -----------------------
  const liveDataRegistryRef = useRef<LiveDataRegistry | null>(null);
  if (!liveDataRegistryRef.current) {
    liveDataRegistryRef.current = createLiveDataRegistry();
  }

  const lifecycleHostRef = useRef<ExtensionLifecycleHost | null>(null);
  if (!lifecycleHostRef.current) {
    lifecycleHostRef.current = createExtensionLifecycleHost(liveDataRegistryRef.current ?? undefined);
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
  const rendererRegistryRef = useRef(createRendererRegistry());
  const [rendererRegistrySnapshot, setRendererRegistrySnapshot] = useState(
    () => rendererRegistryRef.current.getSnapshot(),
  );

  // ---- M13: shader registry ref (registry is created by ShaderEffectRegistryProvider,
  //        exposed via context and stored here for the synchronize effect) ----
  const shaderRegistryRef = useRef<ShaderEffectRegistry | null>(null);

  // ---- M9: clip-type registry ref (registry is created by ClipTypeRegistryProvider,
  //        exposed via context and stored here for the synchronize effect) ----
  const clipTypeRegistryRef = useRef<ClipTypeRegistry | null>(null);

  // ---- M10: agent tool registry (one per provider mount) ---------------------
  const agentToolRegistryRef = useRef<AgentToolRegistry | null>(null);
  if (!agentToolRegistryRef.current) {
    agentToolRegistryRef.current = createAgentToolRegistry({
      liveDataRegistry: liveDataRegistryRef.current ?? undefined,
    });
  }

  // ---- M11: live permission service (one per provider mount) ------------------
  const livePermissionServiceRef = useRef<LivePermissionService | null>(null);
  if (!livePermissionServiceRef.current) {
    livePermissionServiceRef.current = createLivePermissionService();
  }

  // ---- T9: Host-visible settings notification registry (one per provider) -----
  const settingsNotificationRegistryRef = useRef<ExtensionSettingsNotificationRegistry | null>(null);
  if (!settingsNotificationRegistryRef.current) {
    settingsNotificationRegistryRef.current = createExtensionSettingsNotificationRegistry();
  }

  // ---- M6b: Process manager (host override or default from declared process specs) ----
  const processManagerRef = useRef<ProcessManager | null>(null);
  if (hostProcessManager) {
    processManagerRef.current = hostProcessManager;
  } else if (!processManagerRef.current) {
    const declaredProcessSpecs = extensionRuntime.processes.map((d) => d.spec);
    processManagerRef.current = declaredProcessSpecs.length > 0
      ? createProcessManager({ processes: declaredProcessSpecs })
      : null;
  }

  // ---- M6b: Host-session scoped process result attach records (memory only) -----
  const [processResultAttachRecords, setProcessResultAttachRecords] = useState<
    readonly ProcessResultAttachRecord[]
  >([]);
  const recordProcessResultAttach = useCallback(
    (record: ProcessResultAttachRecord) => {
      setProcessResultAttachRecords((prev) => [...prev, record]);
    },
    [],
  );

  // ---- M6b: Derived process statuses snapshot (reactive) ----
  const processStatuses = useMemo<readonly ProcessStatus[] | undefined>(() => {
    const manager = processManagerRef.current;
    if (!manager) return undefined;
    return manager.listStatuses();
    // Recompute when attach records change to pick up status changes after execute.
  }, [processResultAttachRecords, processManagerRef.current]);

  // Dispose process manager on unmount (only when provider-owned)
  useEffect(() => {
    const manager = processManagerRef.current;
    if (!manager || hostProcessManager) return;
    return () => {
      void manager.dispose();
    };
  }, [hostProcessManager]);

  // ---- T9: Pre-load settings snapshots from repository for context factory ----
  const [settingsSnapshots, setSettingsSnapshots] = useState<
    Record<string, ExtensionSettingsSnapshot> | null
  >(null);
  const settingsSnapshotsRef = useRef<Record<string, ExtensionSettingsSnapshot> | null>(null);

  useEffect(() => {
    const repo = extensionStateRepository;
    if (!repo || repo.isDisposed) {
      setSettingsSnapshots(null);
      settingsSnapshotsRef.current = null;
      return;
    }

    let cancelled = false;

    repo.getAllSettingsSnapshots().then((snapshots) => {
      if (cancelled) return;
      const byId: Record<string, ExtensionSettingsSnapshot> = {};
      for (const snap of snapshots) {
        byId[snap.extensionId] = snap;
      }
      setSettingsSnapshots(byId);
      settingsSnapshotsRef.current = byId;
    }).catch(() => {
      if (!cancelled) {
        setSettingsSnapshots(null);
        settingsSnapshotsRef.current = null;
      }
    });

    return () => {
      cancelled = true;
    };
  }, [extensionStateRepository]);

  const diagnosticCollectionRef = useRef<DiagnosticCollection | null>(null);
  if (!diagnosticCollectionRef.current) {
    diagnosticCollectionRef.current = createDiagnosticCollection();
  }

  useEffect(() => {
    const registry = rendererRegistryRef.current;
    const handle = registry.subscribe(setRendererRegistrySnapshot);
    setRendererRegistrySnapshot(registry.getSnapshot());
    return () => handle.dispose();
  }, []);

  // ---- M1: Proposal persistence service lifecycle (provider-owned) ----------
  const proposalPersistenceBridgeRef = useRef<ProposalPersistenceProvider | null | undefined>(undefined);
  const [, setPersistenceInitVersion] = useState(0);

  // Track the current scope so we can detect userId / timelineId / provider
  // changes and tear down the old persistence service before creating a new
  // one.  Without this the lazy-init guard never resets and a disposed service
  // is re-used for the new scope (rework item T5-scope).
  const persistedServiceRef = useRef<ExtensionPersistenceService | null>(null);
  const scopeKeyRef = useRef<string | undefined>(undefined);
  const currentScopeKey = `${userId ?? 'unknown'}::${timelineId}::${!!dataProvider.createExtensionPersistenceService}`;

  if (scopeKeyRef.current !== undefined && scopeKeyRef.current !== currentScopeKey) {
    // Scope changed — reset so a fresh service is created for the new scope.
    // Disposal of the *old* service is handled by the effect cleanup below
    // (which captures the old svc in its closure), so we only null the refs here.
    persistedServiceRef.current = null;
    proposalPersistenceBridgeRef.current = undefined;
  }
  scopeKeyRef.current = currentScopeKey;

  // Lazy-initialize the persistence service when the provider supports it.
  if (!persistedServiceRef.current && dataProvider.createExtensionPersistenceService) {
    persistedServiceRef.current = dataProvider.createExtensionPersistenceService(
      { userId: userId ?? 'unknown', timelineId },
      [],
    );
  }

  // When the provider does NOT support extension persistence, mark the bridge
  // null immediately so ProposalRuntime is created without persistence on the
  // first render.  When the provider DOES support persistence, the bridge stays
  // undefined until the initialize effect succeeds (fail-closed contract).
  if (
    proposalPersistenceBridgeRef.current === undefined
    && !dataProvider.createExtensionPersistenceService
  ) {
    proposalPersistenceBridgeRef.current = null;
  }

  // Initialize persistence and gate downstream readiness on success.
  useEffect(() => {
    const svc = persistedServiceRef.current;
    if (!svc) {
      // No persistence service — inner already has a null bridge.
      return;
    }

    let cancelled = false;
    svc.initialize().then(() => {
      if (cancelled) return;
      proposalPersistenceBridgeRef.current = svc.capabilities.proposals
        ? createProposalPersistenceBridge(svc)
        : null;
      setPersistenceInitVersion((v) => v + 1);
    }).catch((err: unknown) => {
      if (cancelled) return;
      console.error(
        '[EditorRuntimeProvider] Extension persistence initialization failed:',
        err,
      );
      // Fail-closed: bridge stays undefined, so ProposalRuntime is never
      // exposed. The provider advertised persistence support but could not
      // initialize — operating without it would violate the contract.
    });

    return () => {
      cancelled = true;
      svc.dispose();
    };
  }, [userId, timelineId, dataProvider]);

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
      // Dispose live data registry and permission service on provider unmount
      liveDataRegistryRef.current?.dispose();
      livePermissionServiceRef.current?.getDisposeHandle().dispose();
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
  const resolvedExtensionsConfig = useMemo(
    () => resolveRegisteredSlotRenderers(extensionRuntime, rendererRegistrySnapshot),
    [extensionRuntime, rendererRegistrySnapshot],
  );

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
    extensions: resolvedExtensionsConfig,
    extensionRuntime,
    commandRegistry: commandRegistryRef.current ?? undefined,
    agentToolRegistry: agentToolRegistryRef.current ?? undefined,
    liveDataRegistry: liveDataRegistryRef.current ?? undefined,
    livePermissionService: livePermissionServiceRef.current ?? undefined,
    diagnosticCollection: diagnosticCollectionRef.current ?? undefined,
    extensionStateRepository: extensionStateRepository ?? null,
    triggerExtensionRefresh,
    settingsNotificationRegistry: settingsNotificationRegistryRef.current ?? undefined,
    getRecoveryKey: (extensionId: string) =>
      lifecycleHostRef.current?.getRecoveryKey(extensionId) ?? "0",
    incrementRecoveryKey: (extensionId: string) =>
      lifecycleHostRef.current?.incrementRecoveryKey(extensionId) ?? "0",
    processManager: processManagerRef.current ?? undefined,
    processStatuses,
    processResultAttachRecords: processResultAttachRecords.length > 0
      ? processResultAttachRecords
      : undefined,
    recordProcessResultAttach,
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
    resolvedExtensionsConfig,
    extensionRuntime,
    extensionStateRepository,
    triggerExtensionRefresh,
    processResultAttachRecords,
    processStatuses,
    recordProcessResultAttach,
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
        shaderRegistryRef={shaderRegistryRef}
        clipTypeRegistryRef={clipTypeRegistryRef}
        agentToolRegistryRef={agentToolRegistryRef}
        rendererRegistryRef={rendererRegistryRef}
        liveDataRegistryRef={liveDataRegistryRef}
        proposalPersistenceProvider={proposalPersistenceBridgeRef.current}
        settingsSnapshotsRef={settingsSnapshotsRef}
        settingsNotificationRegistryRef={settingsNotificationRegistryRef}
        extensionStateRepository={extensionStateRepository}
      >
        {children}
      </EditorRuntimeProviderInner>
    </DataProviderWrapper>
  );
}
