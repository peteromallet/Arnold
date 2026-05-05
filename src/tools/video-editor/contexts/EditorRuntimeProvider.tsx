import type { ReactNode } from 'react';
import { useLayoutEffect } from 'react';
import { useEffects } from '@/tools/video-editor/hooks/useEffects';
import { useEffectRegistry } from '@/tools/video-editor/hooks/useEffectRegistry';
import {
  EffectCatalogProvider,
  useResolvedEffectCatalog,
  type VideoEditorEffectCatalog,
} from '@/tools/video-editor/hooks/useEffectResources';
import {
  SequenceComponentCatalogProvider,
  useResolvedSequenceComponentCatalog,
  type VideoEditorSequenceComponentCatalog,
} from '@/tools/video-editor/hooks/useSequenceResources';
import { SequenceComponentRegistryProvider } from '@/tools/video-editor/sequences/SequenceComponentRegistryContext';
import { TimelineStoreProvider } from '@/tools/video-editor/hooks/timelineStore';
import { useTimelineState } from '@/tools/video-editor/hooks/useTimelineState';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider';
import {
  DataProviderWrapper,
  type VideoEditorRuntimeContextValue,
} from '@/tools/video-editor/contexts/DataProviderContext';

export interface EditorRuntimeProviderProps {
  dataProvider: DataProvider;
  timelineId: string;
  timelineName?: string | null;
  userId?: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  sequenceComponentCatalog?: VideoEditorSequenceComponentCatalog | null;
  runtime?: Pick<VideoEditorRuntimeContextValue, 'assetResolver' | 'exporter' | 'hostContext'>;
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
  children,
}: EditorRuntimeProviderProps) {
  return (
    <DataProviderWrapper
      value={{
        provider: dataProvider,
        timelineId,
        timelineName,
        userId,
        assetResolver: runtime?.assetResolver ?? null,
        exporter: runtime?.exporter ?? null,
        hostContext: runtime?.hostContext ?? null,
      }}
    >
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

