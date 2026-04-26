import { useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { TOOL_IDS } from '@/shared/lib/tooling/toolIds';
import { useProjectCrudContext, useProjectSelectionContext } from '@/shared/contexts/ProjectContext';
import { toast } from '@/shared/components/ui/runtime/sonner';
import { useAsyncOperation } from '@/shared/hooks/async/useAsyncOperation';
import { useDeleteGenerationWithConfirm } from '@/domains/generation/hooks/useDeleteGenerationWithConfirm';
import { useToggleGenerationStar } from '@/domains/generation/hooks/useGenerationMutations';
import { useProjectGenerations, type GenerationsPaginatedResponse } from '@/shared/hooks/projects/useProjectGenerations';
import { useIsMobile } from '@/shared/hooks/mobile';

import { useCharacterAnimateGenerate } from '@/tools/character-animate/hooks/useCharacterAnimateGenerate';
import { useCharacterAnimateSettings } from '@/tools/character-animate/hooks/useCharacterAnimateSettings';
import type { CharacterImageState, MotionVideoState } from '../characterAnimate.types';

export function useCharacterAnimateBaseState() {
  const queryClient = useQueryClient();
  const { selectedProjectId } = useProjectSelectionContext();
  const { projects } = useProjectCrudContext();
  const isMobile = useIsMobile();

  const [characterImage, setCharacterImage] = useState<CharacterImageState | null>(null);
  const [motionVideo, setMotionVideo] = useState<MotionVideoState | null>(null);
  const [prompt, setPrompt] = useState('');
  const [localMode, setLocalMode] = useState<'animate' | 'replace'>('animate');

  const imageUpload = useAsyncOperation();
  const videoUpload = useAsyncOperation();

  const [characterImageLoaded, setCharacterImageLoaded] = useState(false);
  const [motionVideoLoaded, setMotionVideoLoaded] = useState(false);
  const [motionVideoPlaying, setMotionVideoPlaying] = useState(false);

  const characterImageInputRef = useRef<HTMLInputElement>(null);
  const motionVideoInputRef = useRef<HTMLInputElement>(null);
  const motionVideoRef = useRef<HTMLVideoElement>(null);

  const [isDraggingOverImage, setIsDraggingOverImage] = useState(false);
  const [isDraggingOverVideo, setIsDraggingOverVideo] = useState(false);
  const [isScrolling, setIsScrolling] = useState(false);

  const { settings, updateField, updateFields, status } = useCharacterAnimateSettings(selectedProjectId);
  const settingsLoaded = status === 'ready';

  const generateModel = useCharacterAnimateGenerate({
    selectedProjectId,
    characterImage,
    motionVideo,
    prompt,
    localMode,
    defaultPrompt: settings?.defaultPrompt,
  });

  const currentProject = projects.find((project) => project.id === selectedProjectId);
  const projectAspectRatio = currentProject?.aspectRatio;

  const generationsQuery = useProjectGenerations(
    selectedProjectId,
    1,
    100,
    !!selectedProjectId,
    {
      toolType: TOOL_IDS.CHARACTER_ANIMATE,
      mediaType: 'video',
    },
    {
      disablePolling: true,
    },
  );

  const videosData = generationsQuery.data as GenerationsPaginatedResponse | undefined;
  const videosLoading = generationsQuery.isLoading;
  const videosFetching = generationsQuery.isFetching;

  const {
    requestDelete: requestDeleteGeneration,
    confirmDialogProps,
    deletingId,
  } = useDeleteGenerationWithConfirm({ projectId: selectedProjectId });
  const toggleStarMutation = useToggleGenerationStar();

  const handleDeleteGeneration = useCallback((id: string) => {
    requestDeleteGeneration(id);
  }, [requestDeleteGeneration]);

  const handleToggleStar = useCallback((id: string, starred: boolean) => {
    if (!selectedProjectId) {
      return;
    }
    toggleStarMutation.mutate({ id, starred, projectId: selectedProjectId });
  }, [selectedProjectId, toggleStarMutation]);

  return {
    toast,
    queryClient,
    selectedProjectId,
    isMobile,
    characterImage,
    setCharacterImage,
    motionVideo,
    setMotionVideo,
    prompt,
    setPrompt,
    localMode,
    setLocalMode,
    imageUpload,
    videoUpload,
    characterImageLoaded,
    setCharacterImageLoaded,
    motionVideoLoaded,
    setMotionVideoLoaded,
    motionVideoPlaying,
    setMotionVideoPlaying,
    characterImageInputRef,
    motionVideoInputRef,
    motionVideoRef,
    isDraggingOverImage,
    setIsDraggingOverImage,
    isDraggingOverVideo,
    setIsDraggingOverVideo,
    isScrolling,
    setIsScrolling,
    settings,
    updateField,
    updateFields,
    settingsLoaded,
    generateModel,
    projectAspectRatio,
    videosData,
    videosLoading,
    videosFetching,
    confirmDialogProps,
    deletingId,
    handleDeleteGeneration,
    handleToggleStar,
  };
}

export type CharacterAnimateBaseState = ReturnType<typeof useCharacterAnimateBaseState>;
