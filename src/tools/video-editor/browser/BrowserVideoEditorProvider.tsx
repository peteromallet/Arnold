import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
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
import { getExtensionSmokeExtension } from '@/sdk/smoke/extensionSmoke';
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
  /**
   * M5: Monotonic refresh key forwarded to useExtensionLoaderWiring.
   * Increment after persistence writes (enable/disable, settings save) to
   * force re-resolution of extensions, diagnostics, and package-state
   * inventory without a page refresh.
   */
  refreshKey?: number;
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
  refreshKey,
  queryClient,
  initialEntries,
  children,
}: BrowserVideoEditorProviderProps) {
  const [ownedQueryClient] = useState(() => queryClient ?? createDefaultQueryClient());

  // ---- M5: Internal refresh key for extension re-resolution ----------------
  // When refreshKey prop is provided it takes precedence; otherwise we manage
  // an internal counter that gets incremented by triggerExtensionRefresh.
  const [internalRefreshKey, setInternalRefreshKey] = useState(0);
  const effectiveRefreshKey = refreshKey ?? internalRefreshKey;

  const triggerExtensionRefresh = useCallback(() => {
    if (refreshKey !== undefined) {
      // External refreshKey: the caller owns refresh. We still provide a
      // no-op trigger so the manager can call it without checking.
      return;
    }
    setInternalRefreshKey((prev) => prev + 1);
  }, [refreshKey]);

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

  // ---- Smoke extension wiring (prepend when ?extensionSmoke=1) -------------
  const effectiveDirectExtensions = useMemo<readonly ReighExtension[] | undefined>(() => {
    const smokeExt = getExtensionSmokeExtension(window.location.search);
    if (!smokeExt) {
      return extensions;
    }
    if (!extensions || extensions.length === 0) {
      return [smokeExt];
    }
    return [smokeExt, ...extensions];
  }, [extensions]);

  // ---- M14: extension loader wiring (host-owned) --------------------------
  const {
    resolvedExtensions,
    isResolving: _loaderIsResolving,
    packageStateEntries,
  } = useExtensionLoaderWiring({
    directExtensions: effectiveDirectExtensions,
    repository: effectiveRepository ?? null,
    bundleStore: effectiveBundleStore ?? null,
    refreshKey: effectiveRefreshKey,
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
          packageStateEntries={packageStateEntries}
          extensionStateRepository={effectiveRepository ?? null}
          triggerExtensionRefresh={triggerExtensionRefresh}
        >
          {children}
        </EditorRuntimeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
