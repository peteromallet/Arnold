import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { EditorRuntimeProvider } from '@/tools/video-editor/contexts/EditorRuntimeProvider.tsx';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type { VideoEditorEffectCatalog } from '@/tools/video-editor/hooks/useEffectResources.ts';
import type {
  VideoEditorAssetResolver,
  VideoEditorExporter,
  VideoEditorHostContext,
} from '@/tools/video-editor/lib/browser-runtime.ts';

export interface BrowserVideoEditorProviderProps {
  dataProvider: DataProvider;
  timelineId: string;
  timelineName?: string | null;
  userId?: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  assetResolver?: VideoEditorAssetResolver | null;
  exporter?: VideoEditorExporter | null;
  hostContext?: VideoEditorHostContext | null;
  queryClient?: QueryClient;
  initialEntries?: string[];
  children: ReactNode;
}

function createDefaultQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
}

/**
 * @publicContract
 * Browser-only runtime provider for custom shells that use the supported
 * public hooks instead of the stock editor chrome.
 */
export function BrowserVideoEditorProvider({
  dataProvider,
  timelineId,
  timelineName,
  userId = null,
  effectCatalog,
  assetResolver = null,
  exporter = null,
  hostContext = null,
  queryClient,
  initialEntries,
  children,
}: BrowserVideoEditorProviderProps) {
  const [ownedQueryClient] = useState(() => queryClient ?? createDefaultQueryClient());

  return (
    <QueryClientProvider client={ownedQueryClient}>
      <MemoryRouter initialEntries={initialEntries ?? ['/tools/video-editor']}>
        <EditorRuntimeProvider
          dataProvider={dataProvider}
          timelineId={timelineId}
          timelineName={timelineName}
          userId={userId}
          effectCatalog={effectCatalog}
          runtime={{ assetResolver, exporter, hostContext }}
        >
          {children}
        </EditorRuntimeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
