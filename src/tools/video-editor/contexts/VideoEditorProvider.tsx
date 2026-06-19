/**
 * Internal host-only provider wiring for the Reigh app shell.
 * Not part of the supported public SDK surface.
 */
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { toast } from '@/shared/components/ui/runtime/sonner.tsx';
import { MediaLightbox } from '@/domains/media-lightbox/MediaLightbox.tsx';
import type { GenerationRow } from '@/domains/generation/types/index.ts';
import { VideoEditorLightboxOverlay } from '@/tools/video-editor/components/VideoEditorLightboxOverlay.tsx';
import { useReighShotsHost } from '@/tools/video-editor/adapters/reigh/useReighShotsHost.ts';
import {
  DEFAULT_VIDEO_EDITOR_EXTENSION_RUNTIME,
  normalizeExtensionRuntime,
  type ExtensionRuntime,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import {
  DataProviderWrapper,
  useVideoEditorRuntime,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
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
import { useAgentChatRegistry } from '@/shared/contexts/AgentChatContext.tsx';
import { clearTimelineClipData, setTimelineClipData } from '@/shared/state/selectionStore.ts';
import { useEffects } from '@/tools/video-editor/hooks/useEffects.ts';
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
import { useTimelineClipsForAttachments } from '@/tools/video-editor/hooks/useTimelineClipsForAttachments.ts';
import { useTimelineState } from '@/tools/video-editor/hooks/useTimelineState.ts';
import { TimelineStoreProvider } from '@/tools/video-editor/hooks/timelineStore.ts';
import type {
  TimelineActionResizeStart,
  TimelineClipEdgeResizeEnd,
  TimelineEditorOpsContextValue,
} from '@/tools/video-editor/hooks/useTimelineState.types.ts';
import { useVideoEditorLightboxNavigation } from '@/tools/video-editor/hooks/useVideoEditorLightboxNavigation.ts';
import { isOpenableAssetType } from '@/tools/video-editor/lib/editor-utils.ts';
import { loadGenerationForLightbox } from '@/tools/video-editor/lib/generation-utils.ts';
import { getClipTimelineDuration } from '@/tools/video-editor/lib/config-utils.ts';
import {
  ADD_GENERATION_QUERY_PARAM,
  readPendingAdds,
  writePendingAdds,
} from '@/domains/media-lightbox/hooks/addToVideoEditorConstants.ts';
import {
  executeGenerationAssetRegistrationPlan,
  planGenerationAssetRegistration,
} from '@/tools/video-editor/lib/timeline-asset-plans.ts';
import { useRenderDiagnostic } from '@/tools/video-editor/hooks/usePerfDiagnostics.ts';
import { createTimelineReader } from '@/tools/video-editor/lib/timeline-reader.ts';
import { createProposalRuntime } from '@/tools/video-editor/lib/proposal-runtime.ts';
import { createCommandRegistry, type CommandRegistry } from '@/tools/video-editor/runtime/commandRegistry.ts';

import { useTimelineOpsFromStore } from '@/tools/video-editor/hooks/timelineStore.ts';
import type { SaveStatus } from '@/tools/video-editor/hooks/useTimelinePersistence.ts';
import type { ResolvedAssetRegistryEntry } from '@/tools/video-editor/types/index.ts';
import {
  removeExtensionDiagnosticsFromCollection,
  syncExtensionDiagnosticsToCollection,
} from '@/tools/video-editor/runtime/diagnosticCollectionSync.ts';

const log = import.meta.env.DEV ? (...args: Parameters<typeof console.log>) => console.log(...args) : () => {};

export function buildVideoEditorLightboxMedia(
  assetKey: string | null,
  asset: ResolvedAssetRegistryEntry | undefined,
): GenerationRow | null {
  if (!assetKey || !asset) {
    return null;
  }

  const src = asset.src || asset.file;
  if (!src || !isOpenableAssetType(asset.type, src)) {
    return null;
  }

  const isVideo = asset.type?.startsWith('video/')
    || /\.(mp4|mov|webm|m4v)(\?.*)?$/i.test(src);

  return {
    id: assetKey,
    generation_id: asset.generationId || assetKey,
    location: src,
    imageUrl: src,
    thumbUrl: asset.thumbnailUrl || src,
    type: isVideo ? 'video' : 'image',
    primary_variant_id: asset.variantId || null,
    name: asset.file,
  };
}

/** Registers video-editor state into the app-level AgentChatContext and keeps
 *  timeline attachment metadata synchronized in the selection store. */
function AgentChatBridgeRegistration() {
  const { timelineId, agentChat } = useVideoEditorRuntime();
  const allClips = useTimelineClipsForAttachments();

  useEffect(() => {
    setTimelineClipData(allClips);
    return () => clearTimelineClipData();
  }, [allClips]);

  useEffect(() => {
    agentChat.registerTimeline({ timelineId });
    return agentChat.unregisterTimeline;
  }, [agentChat, timelineId]);

  return null;
}

function InnerProvider({
  children,
  effectCatalog,
  sequenceComponentCatalog,
  onSaveStatusChange,
  lifecycleHostRef,
  extensionRuntime,
  commandRegistryRef,
}: {
  children: React.ReactNode;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
  onSaveStatusChange?: (status: SaveStatus) => void;
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  extensionRuntime: ExtensionRuntime;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
}) {
  useRenderDiagnostic('VideoEditorProvider');
  const runtime = useVideoEditorRuntime();
  const effectsQuery = useEffects(runtime.auth.userId, { enabled: !effectCatalog });
  const effectResources = useResolvedEffectCatalog(runtime.auth.userId, effectCatalog);
  const sequenceComponentResources = useResolvedSequenceComponentCatalog(
    runtime.auth.userId,
    sequenceComponentCatalog,
  );
  const { store, editor, chrome } = useTimelineState();
  const diagnosticCollection = runtime.diagnosticCollection;
  const activeExtensionIds = useMemo(
    () => new Set(extensionRuntime.extensions.map((ext) => ext.manifest.id as string)),
    [extensionRuntime.extensions],
  );
  useEffect(() => {
    onSaveStatusChange?.(chrome.saveStatus);
  }, [chrome.saveStatus, onSaveStatusChange]);

  // ---- M3: live creative context for extensions --------------------------
  // Create stable TimelineReader from the data ref (always reads latest data).
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
        projectId: runtime.project.projectId,
        extensionRequirements: runtime.extensionRuntime.requirements,
      }),
    [store, runtime.project.projectId, runtime.extensionRuntime.requirements],
  );

  // One ProposalRuntime per provider mount, stable for the provider lifetime.
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

  // When timelineOps first becomes available, create ProposalRuntime if not yet created.
  useEffect(() => {
    if (proposalRuntimeRef.current) return;
    const ops = store.getState().timelineOps;
    if (ops) {
      proposalRuntimeRef.current = createProposalRuntime({
        timelineOps: ops,
        reader: timelineReader,
      });
    }
  }, [store, timelineReader]);

  // Sync proposalRuntime to the store so host-owned UI (ProposalPanel) can access it.
  useEffect(() => {
    const pr = proposalRuntimeRef.current;
    if (pr) {
      store.getState().syncSlices({ proposalRuntime: pr });
    }
  }, [store, timelineReader]);

  // Sync extensions with live creative context.
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
        // Create per-extension commands service backed by the shared registry
        const commandsService: ExtensionCommandService | undefined = registry
          ? {
              registerCommand(commandId, handler, options) {
                return registry.registerCommand(extId, commandId, handler, options);
              },
            }
          : undefined;
        return createExtensionContext(ext, liveCreativeOverrides, commandsService);
      },
    );
    syncExtensionDiagnosticsToCollection(diagnosticCollection, 'extension-lifecycle', [
      ...extensionRuntime.diagnostics,
      ...host.diagnostics,
    ], { activeExtensionIds });
  }, [activeExtensionIds, diagnosticCollection, lifecycleHostRef, extensionRuntime, liveCreativeOverrides, commandRegistryRef]);
  const [searchParams, setSearchParams] = useSearchParams();
  const pendingAddGenerationId = searchParams.get(ADD_GENERATION_QUERY_PARAM);
  const consumedAddGenerationRef = useRef<string | null>(null);

  const drainedStagedRef = useRef(false);
  const drainInFlightRef = useRef(false);
  const editorRef = useRef(editor);
  editorRef.current = editor;

  useEffect(() => {
    if (editor.isLoading) return;
    if (drainInFlightRef.current) return;

    const queue: string[] = [];
    if (pendingAddGenerationId && consumedAddGenerationRef.current !== pendingAddGenerationId) {
      consumedAddGenerationRef.current = pendingAddGenerationId;
      queue.push(pendingAddGenerationId);
    }
    if (!drainedStagedRef.current) {
      drainedStagedRef.current = true;
      for (const id of readPendingAdds()) {
        if (!queue.includes(id)) queue.push(id);
      }
    }
    if (queue.length === 0) return;

    drainInFlightRef.current = true;

    void (async () => {
      const processed: string[] = [];
      try {
        for (const generationId of queue) {
          const generation = await runtime.mediaLightbox.loadGenerationForLightbox(generationId);
          if (!generation) {
            runtime.toast.error('Could not load asset');
            processed.push(generationId);
            continue;
          }
          const registrationPlan = planGenerationAssetRegistration({
            generationId: generation.id,
            variantType: generation.type === 'video' ? 'video' : 'image',
            imageUrl: generation.location ?? generation.imageUrl ?? '',
            thumbUrl: generation.thumbUrl ?? generation.imageUrl ?? generation.location ?? '',
          });
          if (!registrationPlan.ok) {
            runtime.toast.error('Could not register asset');
            processed.push(generationId);
            continue;
          }
          const currentOps = store.getState().ops;
          const { assetKey, persistPromise } = executeGenerationAssetRegistrationPlan({
            plan: registrationPlan,
            patchRegistry: currentOps.patchRegistry,
            registerAsset: currentOps.registerAsset,
          });
          void persistPromise.catch((error) => {
            console.error('[video-editor] Failed to persist staged add asset:', error);
            store.getState().ops.unpatchRegistry(assetKey);
            runtime.toast.error('Failed to save asset');
          });
          // Let registry patch settle before reading resolvedConfig.
          await new Promise<void>((resolve) => setTimeout(resolve, 0));
          const editorForDrop = editorRef.current;
          const clips = editorForDrop.resolvedConfig?.clips ?? [];
          const timelineEnd = clips.reduce(
            (max, clip) => Math.max(max, clip.at + getClipTimelineDuration(clip)),
            0,
          );
          editorForDrop.handleAssetDrop(assetKey, undefined, timelineEnd, false, false);
          processed.push(generationId);
          // Allow React to commit the clip before the next iteration reads clips.
          await new Promise<void>((resolve) => setTimeout(resolve, 50));
        }
      } finally {
        const remaining = readPendingAdds().filter((id) => !processed.includes(id));
        writePendingAdds(remaining);
        if (pendingAddGenerationId && processed.includes(pendingAddGenerationId)) {
          setSearchParams((current) => {
            const next = new URLSearchParams(current);
            next.delete(ADD_GENERATION_QUERY_PARAM);
            return next;
          }, { replace: true });
        }
        drainInFlightRef.current = false;
      }
    })();
  }, [editor.isLoading, pendingAddGenerationId, runtime.mediaLightbox, runtime.toast, setSearchParams, store]);

  const [lightboxAssetKey, setLightboxAssetKey] = useState<string | null>(null);
  const [lightboxClipId, setLightboxClipId] = useState<string | null>(null);
  const lightboxAsset = lightboxAssetKey ? editor.resolvedConfig?.registry[lightboxAssetKey] : undefined;
  const lightboxFallbackMedia = useMemo(
    () => buildVideoEditorLightboxMedia(lightboxAssetKey, lightboxAsset),
    [lightboxAsset, lightboxAssetKey],
  );
  const lightboxGenerationId = lightboxAsset?.generationId ?? null;
  const lightboxQuery = useQuery({
    queryKey: ['video-editor', 'lightbox', lightboxGenerationId],
    queryFn: () => runtime.mediaLightbox.loadGenerationForLightbox(lightboxGenerationId as string),
    enabled: Boolean(lightboxGenerationId),
    staleTime: 60_000,
  });

  useEffect(() => {
    if (
      !lightboxAssetKey
      || !lightboxGenerationId
      || lightboxQuery.isLoading
      || lightboxQuery.data
      || lightboxFallbackMedia
    ) {
      return;
    }

    log('[video-editor] lightbox query returned no data; clearing asset key', {
      assetKey: lightboxAssetKey,
      clipId: lightboxClipId,
      generationId: lightboxGenerationId,
    });
    setLightboxAssetKey(null);
    setLightboxClipId(null);
  }, [lightboxAssetKey, lightboxClipId, lightboxFallbackMedia, lightboxGenerationId, lightboxQuery.data, lightboxQuery.isLoading]);

  const navResult = useVideoEditorLightboxNavigation({
    lightboxAssetKey,
    lightboxClipId,
    data: editor.data,
    shots: runtime.shots.shots,
    setLightboxAssetKey,
    setLightboxClipId,
  });

  const onDoubleClickAsset = useCallback((assetKey: string, clipId?: string) => {
    const asset = editor.resolvedConfig?.registry[assetKey];
    log('[video-editor] onDoubleClickAsset', {
      assetKey,
      clipId: clipId ?? null,
      hasAsset: Boolean(asset),
      generationId: asset?.generationId ?? null,
      file: asset?.file ?? null,
      type: asset?.type ?? null,
    });
    if (!buildVideoEditorLightboxMedia(assetKey, asset)) {
      return;
    }

    setLightboxClipId(clipId ?? null);
    setLightboxAssetKey(assetKey);
  }, [editor.resolvedConfig]);

  useEffect(() => {
    if (!lightboxAssetKey) {
      return;
    }

    log('[video-editor] lightbox state', {
      assetKey: lightboxAssetKey,
      clipId: lightboxClipId,
      generationId: lightboxGenerationId,
      isLoading: lightboxQuery.isLoading,
      hasData: Boolean(lightboxQuery.data),
      hasFallbackMedia: Boolean(lightboxFallbackMedia),
      mediaId: lightboxQuery.data?.id ?? null,
      mediaType: lightboxQuery.data?.type ?? null,
      mediaLocation: lightboxQuery.data?.location ?? null,
    });
  }, [lightboxAssetKey, lightboxClipId, lightboxFallbackMedia, lightboxGenerationId, lightboxQuery.data, lightboxQuery.isLoading]);

  const onActionResizeStart: TimelineActionResizeStart = editor.onActionResizeStart;
  const onClipEdgeResizeEnd: TimelineClipEdgeResizeEnd = editor.onClipEdgeResizeEnd;

  const editorOps = useMemo<TimelineEditorOpsContextValue>(() => ({
    setInputModality: editor.setInputModality,
    setInputModalityFromPointerType: editor.setInputModalityFromPointerType,
    setInteractionMode: editor.setInteractionMode,
    setGestureOwner: editor.setGestureOwner,
    setPrecisionEnabled: editor.setPrecisionEnabled,
    setContextTarget: editor.setContextTarget,
    setInspectorTarget: editor.setInspectorTarget,
    isClipSelected: editor.isClipSelected,
    selectClip: editor.selectClip,
    selectClips: editor.selectClips,
    addToSelection: editor.addToSelection,
    clearSelection: editor.clearSelection,
    setSelectedTrackId: editor.setSelectedTrackId,
    setActiveClipTab: editor.setActiveClipTab,
    setAssetPanelState: editor.setAssetPanelState,
    registerGenerationAsset: editor.registerGenerationAsset,
    onCursorDrag: editor.onCursorDrag,
    onClickTimeArea: editor.onClickTimeArea,
    onActionResizeStart,
    onClipEdgeResizeEnd,
    onOverlayChange: editor.onOverlayChange,
    onTimelineDragOver: editor.onTimelineDragOver,
    onTimelineDragLeave: editor.onTimelineDragLeave,
    onTimelineDrop: editor.onTimelineDrop,
    handleAssetDrop: editor.handleAssetDrop,
    handleUpdateClips: editor.handleUpdateClips,
    handleUpdateClipsDeep: editor.handleUpdateClipsDeep,
    handleDeleteClips: editor.handleDeleteClips,
    handleDeleteClip: editor.handleDeleteClip,
    handleSelectedClipChange: editor.handleSelectedClipChange,
    handleResetClipPosition: editor.handleResetClipPosition,
    handleResetClipsPosition: editor.handleResetClipsPosition,
    handleSplitSelectedClip: editor.handleSplitSelectedClip,
    handleSplitClipAtTime: editor.handleSplitClipAtTime,
    handleSplitClipsAtPlayhead: editor.handleSplitClipsAtPlayhead,
    handleToggleMuteClips: editor.handleToggleMuteClips,
    handleToggleMute: editor.handleToggleMute,
    handleDetachAudioClip: editor.handleDetachAudioClip,
    handleTrackPopoverChange: editor.handleTrackPopoverChange,
    handleMoveTrack: editor.handleMoveTrack,
    handleRemoveTrack: editor.handleRemoveTrack,
    moveSelectedClipToTrack: editor.moveSelectedClipToTrack,
    moveSelectedClipsToTrack: editor.moveSelectedClipsToTrack,
    moveClipToRow: editor.moveClipToRow,
    createTrackAndMoveClip: editor.createTrackAndMoveClip,
    uploadFiles: editor.uploadFiles,
    applyEdit: editor.applyEdit,
    patchRegistry: editor.patchRegistry,
    unpatchRegistry: editor.unpatchRegistry,
    registerAsset: editor.registerAsset,
    onDoubleClickAsset,
    setLightboxAssetKey,
  }), [editor, onActionResizeStart, onClipEdgeResizeEnd, onDoubleClickAsset, setLightboxAssetKey]);

  useLayoutEffect(() => {
    store.getState().syncOpsSlice(editorOps);
  }, [editorOps, store]);

  const resolvedLightboxMedia = lightboxQuery.data ?? lightboxFallbackMedia;
  const lightboxOnClose = useCallback(() => {
    setLightboxAssetKey(null);
    setLightboxClipId(null);
  }, []);
  const lightboxInitialVariantId =
    lightboxAsset?.variantId ?? resolvedLightboxMedia?.primary_variant_id ?? undefined;
  const lightboxFeatures = useMemo(
    () => ({ showDownload: true, showTaskDetails: true }),
    [],
  );

  return (
    <EffectRegistryProvider>
      <EffectCatalogProvider value={effectResources}>
        <VideoEditorEffectRegistryLifecycle
          effectsQueryData={effectsQuery.data}
          effectResources={effectResources.effects}
          lifecycleHostRef={lifecycleHostRef}
          commandRegistryRef={commandRegistryRef}
          activeExtensionIds={activeExtensionIds}
        />
        <SequenceComponentCatalogProvider value={sequenceComponentResources}>
          <SequenceComponentRegistryProvider components={sequenceComponentResources.components}>
            <TimelineStoreProvider store={store}>
              <AgentChatBridgeRegistration />
              {children}
              {lightboxAssetKey && resolvedLightboxMedia && (
                <>
                  <runtime.mediaLightbox.Lightbox
                    media={resolvedLightboxMedia}
                    navigation={navResult.navigation}
                    initialVariantId={lightboxInitialVariantId}
                    onClose={lightboxOnClose}
                    features={lightboxFeatures}
                  />
                  {navResult.indicator ? <VideoEditorLightboxOverlay indicator={navResult.indicator} /> : null}
                </>
              )}
            </TimelineStoreProvider>
          </SequenceComponentRegistryProvider>
        </SequenceComponentCatalogProvider>
      </EffectCatalogProvider>
    </EffectRegistryProvider>
  );
}

function VideoEditorEffectRegistryLifecycle({
  effectsQueryData,
  effectResources,
  lifecycleHostRef,
  commandRegistryRef,
  activeExtensionIds,
}: {
  effectsQueryData: Array<{ slug: string; code: string }> | undefined;
  effectResources: VideoEditorEffectCatalog['effects'];
  lifecycleHostRef: React.MutableRefObject<ExtensionLifecycleHost | null>;
  commandRegistryRef: React.MutableRefObject<CommandRegistry | null>;
  activeExtensionIds: ReadonlySet<string>;
}) {
  const { registry: effectRegistry, snapshot: effectRegistrySnapshot } = useEffectRegistryContext();
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

export interface VideoEditorProviderProps {
  dataProvider: DataProvider;
  projectId: string | null;
  timelineId: string;
  timelineName?: string | null;
  userId: string;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
  onSaveStatusChange?: (status: SaveStatus) => void;
  extensions?: readonly ReighExtension[];
  children: React.ReactNode;
}

export function VideoEditorProvider({
  dataProvider,
  projectId,
  timelineId,
  timelineName,
  userId,
  effectCatalog,
  sequenceComponentCatalog,
  onSaveStatusChange,
  extensions,
  children,
}: VideoEditorProviderProps) {
  const shotsHost = useReighShotsHost(projectId);
  const agentChatRegistry = useAgentChatRegistry();

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

  const diagnosticCollectionRef = useRef<DiagnosticCollection | null>(null);
  if (!diagnosticCollectionRef.current) {
    diagnosticCollectionRef.current = createDiagnosticCollection();
  }

  // Wire registry callbacks → host toast
  useEffect(() => {
    const registry = commandRegistryRef.current;
    if (!registry) return;
    registry.setCallbacks({
      onCommandFailure: (commandId, error, extensionId) => {
        const msg = `Command "${commandId}" failed (${extensionId}): ${error.message}`;
        toast.error(msg);
      },
      onReservedCommand: (commandId, extensionId) => {
        toast.warning(`Reserved command "${commandId}" rejected for extension "${extensionId}".`);
      },
      onReservedKeybinding: (key, extensionId, commandId) => {
        toast.warning(`Reserved keybinding "${key}" for "${commandId}" rejected for extension "${extensionId}".`);
      },
      onDuplicateCommand: (commandId, originalExtension, conflictingExtension) => {
        toast.warning(`Command "${commandId}" already registered by "${originalExtension}". Extension "${conflictingExtension}" cannot override it.`);
      },
      onKeybindingConflict: (key, originalExtension, conflictingExtension) => {
        toast.warning(`Keybinding "${key}" already bound by "${originalExtension}". Extension "${conflictingExtension}" cannot override it.`);
      },
      onContextMenuStaleTarget: (commandId, extensionId, reason) => {
        toast.warning(`Command "${commandId}" was not run for extension "${extensionId}".`, { description: reason });
      },
    });
  }, []);


  useEffect(() => {
    const host = lifecycleHostRef.current;
    return () => {
      host?.disposeAll();
    };
  }, []);

  const runtimeValue = useMemo(() => ({
    provider: dataProvider,
    assetResolver: {
      resolveAssetUrl: dataProvider.resolveAssetUrl.bind(dataProvider),
    },
    auth: {
      userId,
    },
    project: {
      projectId,
    },
    shots: shotsHost,
    mediaLightbox: {
      Lightbox: MediaLightbox,
      loadGenerationForLightbox,
    },
    agentChat: {
      registerTimeline: agentChatRegistry.register,
      unregisterTimeline: agentChatRegistry.unregister,
    },
    toast: {
      error: toast.error,
      success: toast.success,
      warning: toast.warning,
      info: toast.info,
    },
    telemetry: {
      log: (...args: unknown[]) => console.log(...args),
      warn: (...args: unknown[]) => console.warn(...args),
      error: (...args: unknown[]) => console.error(...args),
    },
    timelineId,
    timelineName,
    userId,
    extensions: extensionRuntime.config,
    extensionRuntime,
    commandRegistry: commandRegistryRef.current ?? undefined,
    diagnosticCollection: diagnosticCollectionRef.current ?? undefined,
  }), [agentChatRegistry.register, agentChatRegistry.unregister, dataProvider, projectId, shotsHost, timelineId, timelineName, userId, extensionRuntime.config, extensionRuntime]);

  return (
    <DataProviderWrapper value={runtimeValue}>
      <InnerProvider
        effectCatalog={effectCatalog}
        sequenceComponentCatalog={sequenceComponentCatalog}
        onSaveStatusChange={onSaveStatusChange}
        lifecycleHostRef={lifecycleHostRef}
        extensionRuntime={extensionRuntime}
        commandRegistryRef={commandRegistryRef}
      >
        {children}
      </InnerProvider>
    </DataProviderWrapper>
  );
}
