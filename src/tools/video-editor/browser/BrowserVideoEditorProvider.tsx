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
import type { ReighExtension } from '@reigh/editor-sdk';
import { useExtensionLoaderWiring } from '@/tools/video-editor/runtime/useExtensionLoaderWiring';
import type { ExtensionStateRepository } from '@/tools/video-editor/runtime/extensionStateRepository';
import type { BundleContentStore } from '@/tools/video-editor/runtime/useExtensionLoaderWiring';

export interface BrowserVideoEditorProviderProps {
  dataProvider: DataProvider;
  timelineId: string;
  timelineName?: string | null;
  userId?: string | null;
  effectCatalog?: VideoEditorEffectCatalog | null;
  assetResolver?: VideoEditorAssetResolver | null;
  exporter?: VideoEditorExporter | null;
  hostContext?: VideoEditorHostContext | null;
  extensions?: readonly ReighExtension[];
  /** M14: Optional extension state repository for installed pack resolution. */
  repository?: ExtensionStateRepository | null;
  /** M14: Optional bundle content store for installed pack bytes (IndexedDB). */
  bundleStore?: BundleContentStore | null;
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
  extensions,
  repository,
  bundleStore,
  queryClient,
  initialEntries,
  children,
}: BrowserVideoEditorProviderProps) {
  const [ownedQueryClient] = useState(() => queryClient ?? createDefaultQueryClient());

  // ---- M14: extension loader wiring (host-owned) --------------------------
  const {
    resolvedExtensions,
    isResolving: _loaderIsResolving,
  } = useExtensionLoaderWiring({
    directExtensions: extensions,
    repository: repository ?? null,
    bundleStore: bundleStore ?? null,
  });

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
          extensions={resolvedExtensions}
        >
          {children}
        </EditorRuntimeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
