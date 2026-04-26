import React, { useState, useCallback, useMemo } from 'react';
import { useFileDragTracking } from '@/shared/hooks/useFileDragTracking';
import { preventDefaultDragOver, createSingleFileDropHandler } from '@/shared/lib/dnd/dragDropUpload';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import {
  Film
} from 'lucide-react';
import { Skeleton } from '@/shared/components/ui/skeleton';
import { GenerationRow } from '@/domains/generation/types';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { useAsyncOperation } from '@/shared/hooks/async/useAsyncOperation';
import { getSupabaseClient as supabase } from '@/integrations/supabase/client';
import { storagePaths, getFileExtension, MEDIA_BUCKET } from '@/shared/lib/storagePaths';
import { InlineEditVideoView } from '../components/InlineEditVideoView';
import { cn } from '@/shared/components/ui/contracts/cn';
import { useIsMobile } from '@/shared/hooks/mobile';
import { extractVideoPosterFrame } from '@/shared/lib/media/videoPosterExtractor';
import { VARIANT_TYPE } from '@/shared/constants/variantTypes';
import type { PortionSelection } from '@/shared/components/VideoPortionTimeline';
import { parseRatio } from '@/shared/lib/media/aspectRatios';
import { MediaSelectionPanel } from '@/shared/components/MediaSelectionPanel';
import { useEditToolMediaPersistence } from '@/shared/hooks/media/useEditToolMediaPersistence';
import { EditMediaSelectionLayout } from '@/shared/editMedia/EditMediaSelectionLayout';
import { navigateToGenerationById } from '@/domains/generation/navigation';
import { requireProjectAndUserId } from '@/shared/editMedia/uploadGuards';

// Preload video poster helper - warm up the browser cache
const preloadedVideoRef = { current: null as string | null };
const preloadVideoPoster = (gen: GenerationRow) => {
  const urlToPreload = gen.thumbnail_url || gen.location;
  if (!urlToPreload || preloadedVideoRef.current === urlToPreload) return;
  const img = new Image();
  img.src = urlToPreload;
  preloadedVideoRef.current = urlToPreload;
};

const VIDEO_EXTRA_CLEAR_DATA = { lastEditedMediaSegments: null };

export default function EditVideoPage() {
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();

  // Get project aspect ratio for skeleton sizing
  const selectedProject = projects.find(p => p.id === selectedProjectId);
  const projectAspectRatio = selectedProject?.aspectRatio || '16:9';
  const aspectRatioValue = parseRatio(projectAspectRatio);
  const [savedSegments, setSavedSegments] = useState<PortionSelection[] | undefined>(undefined);

  // Upload operation with automatic loading state
  const uploadOperation = useAsyncOperation<GenerationRow>();
  const { isDraggingOver, handleDragEnter, handleDragLeave, resetDrag: resetDragState } = useFileDragTracking();
  const isMobile = useIsMobile();

  // Restore saved segments when settings are loaded from DB
  const handleSettingsLoaded = useCallback((settings: Record<string, unknown>) => {
    const storedSegments = settings.lastEditedMediaSegments as PortionSelection[] | undefined;
    if (storedSegments && storedSegments.length > 0) {
      setSavedSegments(storedSegments);
    }
  }, []);

  // Persisted media selection (load/save last-edited media ID to project settings)
  const {
    selectedMedia,
    setSelectedMedia,
    handleEditorClose: handleEditorCloseBase,
    showSkeleton,
    updateUISettings,
    isUISettingsLoading,
    isLoading: isLoadingPersistedMedia,
    uiSettings,
    userClosedEditor,
  } = useEditToolMediaPersistence({
    settingsToolId: 'edit-video-ui',
    projectId: selectedProjectId ?? undefined,
    preloadMedia: preloadVideoPoster,
    onSettingsLoaded: handleSettingsLoaded,
    extraClearData: VIDEO_EXTRA_CLEAR_DATA,
  });

  // Wrap editor close to also clear saved segments
  const handleEditorClose = useCallback(() => {
    handleEditorCloseBase();
    setSavedSegments(undefined);
  }, [handleEditorCloseBase]);

  // Callback to save segments when they change in InlineEditVideoView
  const handleSegmentsChange = useCallback((segments: PortionSelection[]) => {
    if (!selectedProjectId || isUISettingsLoading) return;
    updateUISettings('project', { lastEditedMediaSegments: segments });
  }, [selectedProjectId, isUISettingsLoading, updateUISettings]);

  // Shared upload logic for both file input and drag-drop
  const uploadVideo = useCallback(async (file: File): Promise<GenerationRow> => {
    const { projectId, userId } = await requireProjectAndUserId(selectedProjectId);
    const timestamp = Date.now();

    // Extract poster frame from video
    let posterUrl = '';
    try {
      const posterBlob = await extractVideoPosterFrame(file);
      const posterFileName = storagePaths.thumbnail(userId, `${timestamp}-poster.jpg`);
      const { error: posterError } = await supabase().storage
        .from(MEDIA_BUCKET)
        .upload(posterFileName, posterBlob, {
          cacheControl: '3600',
          upsert: false,
          contentType: 'image/jpeg'
        });

      if (!posterError) {
        const { data: { publicUrl } } = supabase().storage
          .from(MEDIA_BUCKET)
          .getPublicUrl(posterFileName);
        posterUrl = publicUrl;
      }
    } catch { /* intentionally ignored */ }

    const fileExt = getFileExtension(file.name, file.type, 'mp4');
    const fileName = storagePaths.upload(userId, `${timestamp}.${fileExt}`);

    const { error: uploadError } = await supabase().storage
      .from(MEDIA_BUCKET)
      .upload(fileName, file, { cacheControl: '3600', upsert: false });
    if (uploadError) throw uploadError;

    const { data: { publicUrl: videoUrl } } = supabase().storage
      .from(MEDIA_BUCKET)
      .getPublicUrl(fileName);

    const generationParams = {
      prompt: 'Uploaded video',
      status: 'completed',
      is_uploaded: true,
      model: 'upload'
    };

    const { data: generation, error: dbError } = await supabase().from('generations')
      .insert({
        project_id: projectId,
        location: videoUrl,
        thumbnail_url: posterUrl || videoUrl,
        type: 'video',
        params: generationParams
      })
      .select()
      .single();

    if (dbError) throw dbError;

    await supabase().from('generation_variants').insert({
      generation_id: generation.id,
      location: videoUrl,
      thumbnail_url: posterUrl || videoUrl,
      is_primary: true,
      variant_type: VARIANT_TYPE.ORIGINAL,
      name: 'Original',
      params: generationParams,
    });

    return generation as unknown as GenerationRow;
  }, [selectedProjectId]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    if (!selectedProjectId) {
      toast.error("Please select a project first");
      return;
    }

    const file = files[0];
    if (!file.type.startsWith('video/')) {
      toast.error("Please upload a video file");
      return;
    }

    const result = await uploadOperation.execute(
      () => uploadVideo(file),
      { context: 'EditVideoPage', toastTitle: 'Failed to upload video' }
    );
    if (result) {
      setSelectedMedia(result);
    }
  };

  const isEditingOnMobile = selectedMedia && isMobile;

  // Drag and drop handlers
  const handleDragOver = preventDefaultDragOver;

  const handleDrop = useMemo(() =>
    createSingleFileDropHandler({
      mimePrefix: 'video/',
      mimeErrorMessage: "Please drop a video file",
      resetDrag: resetDragState,
      getProjectId: () => selectedProjectId ?? undefined,
      upload: (file) => uploadVideo(file),
      onResult: (result) => setSelectedMedia(result),
      context: 'EditVideoPage',
      toastTitle: 'Failed to upload video',
      uploadOperation,
    }),
    [selectedProjectId, resetDragState, uploadOperation, uploadVideo, setSelectedMedia]
  );

  const handleNavigateToGeneration = useCallback(async (generationId: string) => {
    await navigateToGenerationById(generationId, {
      context: 'EditVideoPage',
      onResolved: (generation) => setSelectedMedia(generation),
      onAfterResolved: () => setSavedSegments(undefined),
    });
  }, [setSavedSegments, setSelectedMedia]);

  return (
    <div 
      className={cn(
        "w-full flex flex-col relative",
        isEditingOnMobile ? "min-h-[calc(100dvh-96px)]" : "h-[calc(100dvh-96px)]"
      )}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="px-4 pt-6 pb-6 max-w-7xl mx-auto w-full">
        <h1 className="text-3xl font-light tracking-tight text-foreground">Edit Videos</h1>
      </div>
      
      {/* Show skeleton when loading settings, loading persisted media, OR we have a stored ID but no media yet (and user didn't just close it) */}
      {showSkeleton && (
        <div className="w-full px-4 overflow-y-auto" style={{ minHeight: 'calc(100dvh - 96px)' }}>
          <div className="max-w-7xl mx-auto relative">
            <div className={cn(
              "rounded-2xl overflow-hidden bg-black",
              isEditingOnMobile ? "flex flex-col min-h-[72vh]" : "h-[calc(100dvh-190px)]"
            )}>
              {isMobile ? (
                // Mobile: Match InlineEditVideoView mobile stacked layout
                <div className="w-full flex flex-col bg-transparent">
                  <div 
                    className="flex items-center justify-center relative bg-black w-full shrink-0 rounded-t-2xl overflow-hidden"
                    style={{ height: '35vh' }}
                  >
                    <Skeleton 
                      className="rounded-lg"
                      style={{ 
                        aspectRatio: aspectRatioValue,
                        maxWidth: '100%',
                        maxHeight: '100%',
                        width: aspectRatioValue >= 1 ? '90%' : 'auto',
                        height: aspectRatioValue >= 1 ? 'auto' : '90%'
                      }} 
                    />
                  </div>
                  {/* Timeline skeleton */}
                  <div className="p-4 bg-background">
                    <Skeleton className="h-16 w-full rounded-lg" />
                  </div>
                </div>
              ) : (
                // Desktop: Match InlineEditVideoView desktop layout (60% video + 40% settings)
                <div className="w-full h-full flex flex-row bg-transparent overflow-hidden">
                  {/* Left side: Video + Timeline stacked */}
                  <div className="flex-1 flex flex-col min-h-0 h-full">
                    {/* Video area */}
                    <div className="relative flex items-center justify-center bg-zinc-900 overflow-hidden flex-shrink rounded-t-lg p-4 pt-24">
                      <Skeleton 
                        className="rounded-lg"
                        style={{ 
                          aspectRatio: aspectRatioValue,
                          maxWidth: '90%',
                          maxHeight: '40vh',
                          width: aspectRatioValue >= 1 ? '80%' : 'auto',
                          height: aspectRatioValue >= 1 ? 'auto' : '80%'
                        }} 
                      />
                    </div>
                    {/* Spacer */}
                    <div className="h-4 bg-zinc-900" />
                    {/* Timeline skeleton */}
                    <div className="bg-zinc-900 px-4 pt-3 pb-4 rounded-b-lg flex-shrink-0">
                      <Skeleton className="h-16 w-full rounded-lg" />
                      <div className="flex justify-center mt-2">
                        <Skeleton className="h-8 w-32" />
                      </div>
                    </div>
                  </div>
                  {/* Right panel skeleton for controls - 40% width */}
                  <div className="w-[40%] bg-background border-l border-border p-4 overflow-y-auto">
                    <div className="space-y-4">
                      <Skeleton className="h-8 w-full" />
                      <Skeleton className="h-16 w-full" />
                      <Skeleton className="h-24 w-full" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      
      {!selectedMedia && !isUISettingsLoading && !isLoadingPersistedMedia && (!uiSettings?.lastEditedMediaId || userClosedEditor.current) && (
        <EditMediaSelectionLayout
          isMobile={Boolean(isMobile)}
          isDraggingOver={isDraggingOver}
          isUploading={uploadOperation.isLoading}
          dropIcon={Film}
          dropLabel="Drop video to upload"
          uploadLabel="Upload Video"
          uploadingLabel="Uploading video..."
          mobileHint="Select or upload a video"
          desktopHint="Select a video from the right or upload a new one to regenerate portions."
          accept="video/*"
          onFileUpload={handleFileUpload}
          rightPanel={(
            <VideoSelectionPanel
              onSelect={(media) => {
                preloadVideoPoster(media);
                setSelectedMedia(media);
              }}
            />
          )}
        />
      )}
      
      {selectedMedia && (
        <div className="w-full px-4 pb-6 overflow-y-auto" style={{ minHeight: 'calc(100dvh - 96px)' }}>
          <div className="max-w-7xl mx-auto relative">
            <div className={cn(
              "rounded-2xl overflow-hidden",
              isEditingOnMobile ? "flex flex-col min-h-[72vh]" : "h-[calc(100dvh-190px)]"
            )}>
              <InlineEditVideoView
                key={selectedMedia.id} // Force remount when media changes
                media={selectedMedia}
                onClose={handleEditorClose}
                onVideoSaved={async (_newUrl) => {
                }}
                onNavigateToGeneration={handleNavigateToGeneration}
                initialSegments={savedSegments}
                onSegmentsChange={handleSegmentsChange}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function VideoSelectionPanel({ onSelect }: { onSelect: (media: GenerationRow) => void }) {
  return <MediaSelectionPanel onSelect={onSelect} mediaType="video" />;
}
