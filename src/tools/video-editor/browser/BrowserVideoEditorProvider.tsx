import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { EditorRuntimeProvider } from '@/tools/video-editor/contexts/EditorRuntimeProvider.tsx';
import type { DataProvider } from '@/tools/video-editor/data/DataProvider.ts';
import type { VideoEditorEffectCatalog } from '@/tools/video-editor/hooks/useEffectResources.ts';
import type {
  VideoEditorAssetResolver,
  VideoEditorExporter,
  VideoEditorHostContext,
} from '@/tools/video-editor/lib/browser-runtime.ts';
import type { ExtensionDiagnostic, ReighExtension } from '@reigh/editor-sdk';
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
  repository: explicitRepository,
  bundleStore: explicitBundleStore,
  queryClient,
  initialEntries,
  children,
}: BrowserVideoEditorProviderProps) {
  const [ownedQueryClient] = useState(() => queryClient ?? createDefaultQueryClient());

  // ---- M2: Derive effective repository / bundleStore from DataProvider when
  //        explicit props are not supplied ----------------------------------

  // Stabilize dataProvider identity so the effect doesn't re-fire on new
  // object references with the same logical dataProvider.
  const dataProviderRef = useRef(dataProvider);
  dataProviderRef.current = dataProvider;

  const [effectiveRepository, setEffectiveRepository] = useState<
    ExtensionStateRepository | null | undefined
  >(undefined);
  const [effectiveBundleStore, setEffectiveBundleStore] = useState<
    BundleContentStore | null | undefined
  >(undefined);

  useEffect(() => {
    // If explicit repository is provided, use it directly (caller-owned,
    // assumed pre-hydrated). This is the backward-compatible path.
    if (explicitRepository !== undefined) {
      setEffectiveRepository(explicitRepository);
      setEffectiveBundleStore(explicitBundleStore ?? null);
      return;
    }

    // No explicit repository: try to derive from DataProvider.
    // We need both a userId and a factory method to proceed.
    if (!userId || !dataProviderRef.current.createExtensionPersistenceService) {
      setEffectiveRepository(null);
      setEffectiveBundleStore(null);
      return;
    }

    const diagnostics: ExtensionDiagnostic[] = [];
    const service = dataProviderRef.current.createExtensionPersistenceService(
      { userId, timelineId },
      diagnostics,
    );

    let cancelled = false;

    service.initialize().then(() => {
      if (cancelled) {
        service.dispose().catch(() => {});
        return;
      }
      const repo = service.stateRepository ?? null;
      setEffectiveRepository(repo);

      // Derive bundleStore: if the repository has getBundleContent, use it.
      if (
        repo &&
        typeof (repo as Record<string, unknown>).getBundleContent === "function"
      ) {
        setEffectiveBundleStore(repo as unknown as BundleContentStore);
      } else {
        setEffectiveBundleStore(null);
      }
    }).catch(() => {
      if (!cancelled) {
        setEffectiveRepository(null);
        setEffectiveBundleStore(null);
      }
    });

    return () => {
      cancelled = true;
      service.dispose().catch(() => {});
    };
  }, [explicitRepository, explicitBundleStore, userId, timelineId]);

  // ---- M14: extension loader wiring (host-owned) --------------------------
  const {
    resolvedExtensions,
    isResolving: _loaderIsResolving,
  } = useExtensionLoaderWiring({
    directExtensions: extensions,
    repository: effectiveRepository ?? null,
    bundleStore: effectiveBundleStore ?? null,
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
