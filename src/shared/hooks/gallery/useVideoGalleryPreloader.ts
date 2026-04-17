import { useRef, useEffect, useMemo, useCallback } from 'react';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { useShots } from '@/shared/contexts/ShotsContext';
import { useProjectSelectionContext } from "@/shared/contexts/ProjectContext";
import { useToolSettings } from '@/shared/hooks/settings/useToolSettings';
import { useProjectVideoCountsCache } from '@/shared/hooks/projects/useProjectVideoCountsCache';
import { Shot } from '@/domains/generation/types';
import { preloadingService, hasLoadedImage, PRIORITY } from '@/shared/lib/preloading';
import { dispatchAppEvent } from '@/shared/lib/typedEvents';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';

/**
 * Smart thumbnail preloader for video gallery performance optimization
 *
 * Preloads thumbnail images for:
 * 1. First page of shots in ShotsPane (likely to be clicked)
 * 2. When viewing a shot: ensures page 1 is preloaded, then preloads page 2
 * 3. Newest shots (for quick browsing)
 *
 * Only preloads placeholder images, not videos. Uses network-aware strategies.
 *
 * Uses the shared PreloadingService for actual image loading and tracking.
 * Keeps shot/page-specific tracking locally.
 */
export const useVideoGalleryPreloader = (options?: {
  selectedShot?: Shot | null;
  shouldShowShotEditor?: boolean;
}) => {
  const { selectedShot, shouldShowShotEditor } = options || {};

  // Track previous project ID to detect actual project switches
  const prevProjectIdRef = useRef<string | null>(null);

  const GALLERY_PAGE_SIZE = 6; // Match VideoGallery's itemsPerPage
  const SHOTS_PANE_PAGE_SIZE = 5; // Match ShotsPane's pageSize

  // Reduce target cache size on mobile to prevent performance issues
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768;
  const TARGET_CACHED_IMAGES = isMobile ? 12 : 48; // 2 shots × 6 images on mobile, 8 shots × 6 images on desktop

  // Get project and shots data from contexts
  const { selectedProjectId } = useProjectSelectionContext();
  const { shots } = useShots();
  const { getShotVideoCount } = useProjectVideoCountsCache(selectedProjectId);

  // Local tracking for shot-specific state (doesn't need to be global)
  const preloadedPagesByShot = useRef<Record<string, Set<number>>>({});
  const hasStartedPreloadForProject = useRef<Record<string, boolean>>({});
  const preloadedUrlCount = useRef<Record<string, number>>({});

  // Get shots pane sort order settings to match ShotsPane behavior
  const { settings: shotsPaneSettings } = useToolSettings<{
    sortOrder?: 'oldest' | 'newest';
  }>(SETTINGS_IDS.SHOTS_PANE_UI_STATE, {
    projectId: selectedProjectId ?? undefined,
    enabled: !!selectedProjectId
  });

  const sortOrder = shotsPaneSettings?.sortOrder || 'newest';

  // Network condition checks
  const shouldSkipPreload = useMemo(() => {
    if (typeof navigator === 'undefined') return false;

    // Check for data saver mode
    if ((navigator as { connection?: { saveData?: boolean } }).connection?.saveData) {
      return true;
    }

    // Check for slow connection
    const effectiveType = (navigator as { connection?: { effectiveType?: string } }).connection?.effectiveType;
    if (effectiveType === '2g' || effectiveType === 'slow-2g') {
      return true;
    }

    return false;
  }, []);

  // Helper to build thumbnail URLs for a shot's video gallery page
  const buildThumbnailUrlsForPage = useCallback(async (shotId: string, pageIndex: number): Promise<string[]> => {
    if (!selectedProjectId) return [];

    const startIndex = pageIndex * GALLERY_PAGE_SIZE;
    const endIndex = startIndex + GALLERY_PAGE_SIZE - 1;

    try {
      // Fetch thumbnail URLs for the specific page using the same query as VideoGallery
      const { data, error } = await supabase().from('shot_generations')
        .select(`
          generation:generations!shot_generations_generation_id_generations_id_fk(
            id,
            thumbnail_url,
            location
          )
        `)
        .eq('shot_id', shotId)
        // IMPORTANT: Match gallery sort (newest first)
        .order('created_at', { ascending: false })
        .order('timeline_frame', { ascending: true })
        .range(startIndex, endIndex);

      if (error) {
        return [];
      }

      const urls = (data || [])
        .filter(sg => sg.generation)
        .map(sg => {
          const thumbUrl = sg.generation.thumbnail_url;
          const mainUrl = sg.generation.location;

          // Use exact same logic as useUnifiedGenerations: thumbnail_url || location
          // Don't try to construct URLs - trust what the database returns
          return thumbUrl || mainUrl;
        })
        .filter((url): url is string => typeof url === 'string' && url.length > 0);

      return urls;
    } catch {
      return [];
    }
  }, [selectedProjectId]);

  // Queue preload tasks for a shot's specific page
  const queuePreloadForShotPage = useCallback(async (shotId: string, pageIndex: number) => {
    if (shouldSkipPreload) return;
    if (!selectedProjectId) return;

    // Check if already preloaded
    const shotCache = preloadedPagesByShot.current[shotId] || new Set();
    if (shotCache.has(pageIndex)) {
      return;
    }

    const urls = await buildThumbnailUrlsForPage(shotId, pageIndex);

    // Filter out already-loaded URLs (using shared tracker)
    const newUrls = urls.filter(url => !hasLoadedImage(url));

    if (newUrls.length === 0) {
      // Still mark page as preloaded
      if (!preloadedPagesByShot.current[shotId]) {
        preloadedPagesByShot.current[shotId] = new Set();
      }
      preloadedPagesByShot.current[shotId].add(pageIndex);
      return;
    }

    // Convert URLs to PreloadableImage format and use shared service
    const images = newUrls.map(url => ({ url, thumbUrl: url }));
    await preloadingService.preloadImages(images, PRIORITY.low);

    // Update local URL count for debugging
    preloadedUrlCount.current[selectedProjectId] =
      (preloadedUrlCount.current[selectedProjectId] || 0) + newUrls.length;

    // Notify listeners of cache update (for useThumbnailLoader)
    dispatchAppEvent('videogallery-cache-updated', {
      projectId: selectedProjectId,
      updatedUrls: newUrls
    });

    // Mark page as preloaded
    if (!preloadedPagesByShot.current[shotId]) {
      preloadedPagesByShot.current[shotId] = new Set();
    }
    preloadedPagesByShot.current[shotId].add(pageIndex);

  }, [shouldSkipPreload, selectedProjectId, buildThumbnailUrlsForPage]);

  // Effect: Preload images until target cache size is reached
  useEffect(() => {
    if (!selectedProjectId || !shots || shouldSkipPreload) return;

    // Reduce preloading when shot editor is open on mobile to prevent performance issues
    if (shouldShowShotEditor && isMobile) {
      return;
    }

    // Check if we've already started preloading for this project
    if (hasStartedPreloadForProject.current[selectedProjectId]) {
      return;
    }

    // Check current cache size (approximate)
    const currentCacheSize = preloadedUrlCount.current[selectedProjectId] || 0;

    if (currentCacheSize >= TARGET_CACHED_IMAGES) {
      hasStartedPreloadForProject.current[selectedProjectId] = true;
      return;
    }

    // Mark that we've started preloading for this project
    hasStartedPreloadForProject.current[selectedProjectId] = true;

    // Sort shots by priority: ShotsPane order first, then newest
    const sortedShots = [...shots].sort((a, b) => {
      const dateA = new Date(a.created_at || 0).getTime();
      const dateB = new Date(b.created_at || 0).getTime();

      if (sortOrder === 'oldest') {
        return dateA - dateB;
      } else {
        return dateB - dateA;
      }
    });

    // Create priority-ordered shot list
    const shotsPaneFirstPage = sortedShots.slice(0, SHOTS_PANE_PAGE_SIZE);
    const remainingShots = sortedShots.slice(SHOTS_PANE_PAGE_SIZE);

    // Prioritize: ShotsPane first page, then newest shots
    const priorityOrderedShots = [
      ...shotsPaneFirstPage,
      ...remainingShots.sort((a, b) => {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        return dateB - dateA; // Always newest first for remaining shots
      })
    ];

    // Queue preload for shots until we estimate reaching target
    let estimatedCacheSize = currentCacheSize;
    for (const shot of priorityOrderedShots) {
      if (estimatedCacheSize >= TARGET_CACHED_IMAGES) break;

      // Estimate how many images this shot will add (page 1 only for now)
      const estimatedImagesInShot = Math.min(GALLERY_PAGE_SIZE, getShotVideoCount?.(shot.id) || GALLERY_PAGE_SIZE);

      // Only queue if this shot's page 1 hasn't been preloaded yet
      const shotCache = preloadedPagesByShot.current[shot.id] || new Set();
      if (!shotCache.has(0)) {
        queuePreloadForShotPage(shot.id, 0);
        estimatedCacheSize += estimatedImagesInShot;
      }
    }

  }, [
    selectedProjectId,
    shots,
    shouldSkipPreload,
    shouldShowShotEditor,
    isMobile,
    sortOrder,
    getShotVideoCount,
    queuePreloadForShotPage,
    TARGET_CACHED_IMAGES,
  ]);

  // Effect: When viewing a shot, ensure page 1 is preloaded and preload page 2
  useEffect(() => {
    if (!shouldShowShotEditor || !selectedShot || shouldSkipPreload) return;

    // Ensure page 1 is preloaded
    queuePreloadForShotPage(selectedShot.id, 0);

    // Preload page 2 if shot has enough videos
    if (getShotVideoCount) {
      const videoCount = getShotVideoCount(selectedShot.id);
      if (videoCount && videoCount > GALLERY_PAGE_SIZE) {
        queuePreloadForShotPage(selectedShot.id, 1); // Page 2 = index 1
      }
    }
  }, [shouldShowShotEditor, selectedShot, shouldSkipPreload, queuePreloadForShotPage, getShotVideoCount]);

  // Cleanup on project change - Clear local tracking
  useEffect(() => {
    const prevProjectId = prevProjectIdRef.current;

    if (!selectedProjectId) {
      prevProjectIdRef.current = null;
    } else if (prevProjectId && prevProjectId !== selectedProjectId) {
      // Clear local tracking for the old project

      delete hasStartedPreloadForProject.current[prevProjectId];
      delete preloadedUrlCount.current[prevProjectId];

      // Clear shot-specific tracking
      preloadedPagesByShot.current = {};

      prevProjectIdRef.current = selectedProjectId;
    } else if (!prevProjectId && selectedProjectId) {
      // First time setting a project ID
      prevProjectIdRef.current = selectedProjectId;
    }
  }, [selectedProjectId]);

  return {
    // Expose some state for debugging if needed
    preloadedProjectUrls: preloadedUrlCount.current[selectedProjectId || ''] || 0,
    targetCacheSize: TARGET_CACHED_IMAGES,
    cacheUtilization: selectedProjectId
      ? Math.round(((preloadedUrlCount.current[selectedProjectId] || 0) / TARGET_CACHED_IMAGES) * 100)
      : 0,
  };
};
