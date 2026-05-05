import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { realtimeEventProcessor } from '@/shared/realtime/RealtimeEventProcessor.ts';
import {
  fetchCurrentPrimaryVariant,
  fetchPrimaryVariantLocations,
  type PrimaryVariantInfo,
} from '@/tools/video-editor/adapters/reigh/staleVariantRepository.ts';
import { useVideoEditorRuntime } from '@/tools/video-editor/contexts/DataProviderContext.tsx';
import type { AssetRegistryEntry, ResolvedAssetRegistryEntry } from '@/tools/video-editor/types/index.ts';
import type {
  TimelinePatchRegistry,
  TimelineRegisterAsset,
} from '@/tools/video-editor/hooks/timeline-state-types.ts';

interface UseStaleVariantsArgs {
  registry: Record<string, ResolvedAssetRegistryEntry> | undefined;
  patchRegistry: TimelinePatchRegistry;
  registerAsset: TimelineRegisterAsset;
}

const POLL_INTERVAL_MS = 15_000;

/**
 * Checks which asset registry entries reference a variant that is no longer
 * the primary variant of its generation. Uses direct Supabase queries + realtime
 * subscription (no React Query) for predictable, immediate updates.
 */
export function useStaleVariants({ registry, patchRegistry, registerAsset }: UseStaleVariantsArgs) {
  const runtime = useVideoEditorRuntime();
  const [primaryLocationMap, setPrimaryLocationMap] = useState<Record<string, PrimaryVariantInfo | null>>({});
  const [dismissedAssetKeys, setDismissedAssetKeys] = useState<Set<string>>(() => new Set());
  const fetchCounterRef = useRef(0);

  // Collect all asset keys linked to a generation
  const generationAssetMap = useMemo(() => {
    if (!registry) {
      return {
        generationIds: [] as string[],
        assetsByGeneration: {} as Record<string, { assetKey: string; file: string }[]>,
        generationAssetKeys: new Set<string>(),
      };
    }

    const assetsByGeneration: Record<string, { assetKey: string; file: string }[]> = {};
    const generationAssetKeys = new Set<string>();

    for (const [assetKey, entry] of Object.entries(registry)) {
      if (entry.generationId) {
        generationAssetKeys.add(assetKey);
        if (!assetsByGeneration[entry.generationId]) {
          assetsByGeneration[entry.generationId] = [];
        }
        assetsByGeneration[entry.generationId].push({ assetKey, file: entry.file });
      }
    }

    return {
      generationIds: Object.keys(assetsByGeneration),
      assetsByGeneration,
      generationAssetKeys,
    };
  }, [registry]);

  // Fetch primary variant locations from Supabase
  const fetchPrimaryLocations = useCallback(async (generationIds: string[]) => {
    if (generationIds.length === 0) {
      setPrimaryLocationMap({});
      return;
    }

    const fetchId = ++fetchCounterRef.current;
    let map: Record<string, PrimaryVariantInfo | null>;
    try {
      map = await fetchPrimaryVariantLocations(generationIds);
    } catch (error) {
      console.error('[StaleVariants] fetch error:', error);
      return;
    }

    // Discard if a newer fetch has started
    if (fetchId !== fetchCounterRef.current) return;

    setPrimaryLocationMap(map);
  }, []);

  // Fetch on mount, when generationIds change, and on a polling interval
  useEffect(() => {
    const { generationIds } = generationAssetMap;
    if (generationIds.length === 0) return;

    // Immediate fetch
    void fetchPrimaryLocations(generationIds);

    // Poll every 15 seconds as fallback
    const interval = setInterval(() => {
      void fetchPrimaryLocations(generationIds);
    }, POLL_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [generationAssetMap, fetchPrimaryLocations]);

  // Subscribe to realtime variant/generation changes for instant updates
  useEffect(() => {
    const { generationIds } = generationAssetMap;
    if (generationIds.length === 0) return;

    const genIdSet = new Set(generationIds);

    return realtimeEventProcessor.onEvent((event) => {
      // Variant inserted/updated (e.g., new primary variant set)
      if (event.type === 'variants-changed') {
        const relevant = event.affectedGenerationIds.some((id) => genIdSet.has(id));
        if (relevant) {
          void fetchPrimaryLocations(generationIds);
        }
        return;
      }

      // Generation updated (e.g., primary_variant_id changed)
      if (event.type === 'generations-updated') {
        const relevant = event.generations.some((g) => genIdSet.has(g.id));
        if (relevant) {
          void fetchPrimaryLocations(generationIds);
        }
      }
    });
  }, [generationAssetMap, fetchPrimaryLocations]);

  // Build the set of stale asset keys (compare by file URL)
  const staleAssetKeys = useMemo(() => {
    const stale = new Set<string>();

    for (const [generationId, assets] of Object.entries(generationAssetMap.assetsByGeneration)) {
      const primaryInfo = primaryLocationMap[generationId];
      if (!primaryInfo) continue;
      for (const { assetKey, file } of assets) {
        if (file !== primaryInfo.location) {
          stale.add(assetKey);
        }
      }
    }

    return stale;
  }, [primaryLocationMap, generationAssetMap.assetsByGeneration]);

  const dismissAsset = useCallback((assetKey: string) => {
    setDismissedAssetKeys((prev) => {
      const next = new Set(prev);
      next.add(assetKey);
      return next;
    });
  }, []);

  // Apply a specific variant to a single asset (patches registry + persists)
  const applyVariantToAsset = useCallback(async (
    assetKey: string,
    variant: { id: string; location: string; thumbnail_url?: string | null },
  ) => {
    if (!registry) return;
    const entry = registry[assetKey];
    if (!entry) return;

    const previousEntry = entry;
    const previousFile = entry.file;

    const updatedEntry: AssetRegistryEntry = {
      ...entry,
      file: variant.location,
      variantId: variant.id,
    };

    patchRegistry(assetKey, updatedEntry, variant.location);

    void registerAsset(assetKey, updatedEntry).catch((err) => {
      console.error('[StaleVariants] Failed to persist variant update:', err);
      patchRegistry(assetKey, previousEntry, previousFile);
      runtime.toast.error('Failed to update variant');
    });

    setDismissedAssetKeys((prev) => {
      if (!prev.has(assetKey)) return prev;
      const next = new Set(prev);
      next.delete(assetKey);
      return next;
    });
  }, [patchRegistry, registerAsset, registry, runtime.toast]);

  // Update a single asset to the current primary variant
  const updateAssetToCurrentVariant = useCallback(async (assetKey: string) => {
    if (!registry) return;
    const entry = registry[assetKey];
    if (!entry?.generationId) return;

    // Fetch the current primary variant's data
    const newVariant = await fetchCurrentPrimaryVariant(entry.generationId);
    if (!newVariant) return;
    await applyVariantToAsset(assetKey, newVariant);
  }, [registry, applyVariantToAsset]);

  return {
    staleAssetKeys,
    dismissedAssetKeys,
    generationAssetKeys: generationAssetMap.generationAssetKeys,
    dismissAsset,
    updateAssetToCurrentVariant,
    applyVariantToAsset,
  };
}
