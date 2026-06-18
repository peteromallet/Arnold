import { useEffect, useMemo, useRef, type ReactNode } from 'react';
import { useLayoutEffect } from 'react';
import { useEffects } from '@/tools/video-editor/hooks/useEffects.ts';
import { useEffectRegistry } from '@/tools/video-editor/hooks/useEffectRegistry.ts';
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
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import {
  normalizeExtensionRuntime,
  type ExtensionRuntime,
} from '@/tools/video-editor/runtime/extensionSurface.ts';
import {
  createExtensionLifecycleHost,
  type ExtensionLifecycleHost,
} from '@/tools/video-editor/runtime/extensionLifecycle.ts';
import { createExtensionContext, type ReighExtension } from '@reigh/editor-sdk';
import type {
  VideoEditorAuthHost,
  VideoEditorProjectHost,
  VideoEditorShotsHost,
  VideoEditorMediaLightboxHost,
  VideoEditorAgentChatHost,
  VideoEditorToastHost,
  VideoEditorTelemetryHost,
} from '@/tools/video-editor/runtime/ports.ts';

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
}: {
  children: ReactNode;
  userId: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
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

  useLayoutEffect(() => {
    store.getState().syncSlices({
      availability: { mounted: true },
    });
  }, [store]);

  return (
    <EffectCatalogProvider value={effectResources}>
      <SequenceComponentCatalogProvider value={sequenceComponentResources}>
        <SequenceComponentRegistryProvider components={sequenceComponentResources.components}>
          <TimelineStoreProvider store={store}>
            {children}
          </TimelineStoreProvider>
        </SequenceComponentRegistryProvider>
      </SequenceComponentCatalogProvider>
    </EffectCatalogProvider>
  );
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

  useEffect(() => {
    const host = lifecycleHostRef.current!;
    host.synchronize(extensionRuntime.extensions, createExtensionContext);
  }, [extensionRuntime.extensions]);

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
      >
        {children}
      </EditorRuntimeProviderInner>
    </DataProviderWrapper>
  );
}

