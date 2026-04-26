import { useCallback, useMemo, useRef } from 'react';
import { useAutoSaveSettings } from '@/shared/settings/hooks/useAutoSaveSettings';
import type { VideoMetadata } from '@/shared/lib/media/videoUploader';
import {
  DEFAULT_STRUCTURE_GUIDANCE_CONTROLS,
  DEFAULT_STRUCTURE_VIDEO,
  type StructureGuidanceConfig,
  type TravelGuidance,
  resolvePrimaryStructureVideo,
  resolveTravelStructureState,
  StructureVideoConfig,
  StructureVideoConfigWithMetadata,
} from '@/shared/lib/tasks/travelBetweenImages';
import {
  buildTravelGuidanceFromControls,
  getDefaultTravelGuidanceMode,
  getDefaultTravelGuidanceStrength,
  normalizeTravelGuidance,
  resolveTravelGuidanceControls,
  type TravelGuidanceControls,
} from '@/shared/lib/tasks/travelGuidance';
import { SETTINGS_IDS } from '@/shared/lib/settingsIds';
import { MODEL_DEFAULTS, type SelectedModel } from '@/tools/travel-between-images/settings';

interface UseStructureVideoParams {
  projectId: string;
  shotId: string | undefined;
  selectedModel?: SelectedModel;
  /** Timeline frame range for auto-calculating default video ranges */
  timelineStartFrame?: number;
  timelineEndFrame?: number;
}

// Re-export types from the shared lib for convenience.
export type { StructureVideoConfig, StructureVideoConfigWithMetadata };

export interface UseStructureVideoReturn {
  /** Array of structure video configurations */
  structureVideos: StructureVideoConfigWithMetadata[];
  /** Canonical travel guidance persisted alongside structure videos. */
  travelGuidance?: TravelGuidance;
  /** Canonical per-model travel guidance persisted alongside structure videos. */
  travelGuidanceByModel?: Partial<Record<SelectedModel, TravelGuidance | null>>;
  /** Canonical structure guidance persisted alongside structure videos. */
  structureGuidance?: StructureGuidanceConfig;
  /** Add a new structure video to the array */
  addStructureVideo: (video: StructureVideoConfigWithMetadata) => void;
  /** Update a structure video at a specific index */
  updateStructureVideo: (index: number, video: Partial<StructureVideoConfigWithMetadata>) => void;
  /** Remove a structure video at a specific index */
  removeStructureVideo: (index: number) => void;
  /** Clear all structure videos */
  clearAllStructureVideos: () => void;
  /** Set the entire array of structure videos */
  setStructureVideos: (videos: StructureVideoConfigWithMetadata[]) => void;
  /** Update canonical guidance controls without mutating structure_videos entries. */
  updateStructureGuidanceControls: (updates: Partial<TravelGuidanceControls>) => void;
  /** Loading state */
  isLoading: boolean;

  // Primary video accessors (derived from structureVideos[0])
  structureVideoPath: string | null;
  structureVideoMetadata: VideoMetadata | null;
  structureVideoTreatment: 'adjust' | 'clip';
  structureVideoMotionStrength: number;
  structureVideoType: 'uni3c' | 'flow' | 'canny' | 'depth' | 'raw' | 'pose' | 'video' | 'cameraman';
  structureVideoResourceId: string | null;
  structureVideoUni3cEndPercent: number;
  structureVideoDefaultsByModel?: Partial<Record<SelectedModel, {
    mode: 'uni3c' | 'flow' | 'canny' | 'depth' | 'raw' | 'pose' | 'video' | 'cameraman';
    motionStrength: number;
    treatment: 'adjust' | 'clip';
    uni3cEndPercent: number;
    cannyIntensity?: number;
    depthContrast?: number;
  }>>;
}

/** Canonical settings storage schema for travel structure guidance. */
interface StructureVideoSettings {
  structure_videos?: StructureVideoConfigWithMetadata[];
  travel_guidance?: TravelGuidance;
  travel_guidance_by_model?: Partial<Record<SelectedModel, TravelGuidance | null>>;
  structure_guidance?: StructureGuidanceConfig;
}

function parseString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function parseNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function parseTreatment(value: unknown): 'adjust' | 'clip' | undefined {
  return value === 'adjust' || value === 'clip' ? value : undefined;
}

function sanitizeEditableStructureVideos(
  videos: StructureVideoConfigWithMetadata[],
  defaultEndFrame: number,
): StructureVideoConfigWithMetadata[] {
  return videos
    .map((video) => {
      const path = parseString(video.path);
      if (!path) {
        return null;
      }

      return {
        path,
        start_frame: parseNumber(video.start_frame) ?? 0,
        end_frame: parseNumber(video.end_frame) ?? defaultEndFrame,
        treatment: parseTreatment(video.treatment) ?? DEFAULT_STRUCTURE_VIDEO.treatment,
        ...(parseNumber(video.source_start_frame) !== undefined
          ? { source_start_frame: parseNumber(video.source_start_frame) }
          : {}),
        ...(video.source_end_frame === null || parseNumber(video.source_end_frame) !== undefined
          ? { source_end_frame: video.source_end_frame ?? null }
          : {}),
        metadata: video.metadata ?? null,
        resource_id: video.resource_id ?? null,
      } satisfies StructureVideoConfigWithMetadata;
    })
    .filter((video): video is StructureVideoConfigWithMetadata => video !== null);
}

/**
 * Hook to manage structure video state with database persistence.
 * Loads the canonical `structure_videos` + `structure_guidance` pair and
 * migrates older shapes only at the persistence boundary.
 */
export function useStructureVideo({
  projectId,
  shotId,
  selectedModel,
  timelineEndFrame = 81,
}: UseStructureVideoParams): UseStructureVideoReturn {
  const modelName = selectedModel
    ? (MODEL_DEFAULTS[selectedModel] ?? MODEL_DEFAULTS['wan-2.2']).modelName
    : undefined;

  const settings = useAutoSaveSettings<StructureVideoSettings>({
    toolId: SETTINGS_IDS.TRAVEL_STRUCTURE_VIDEO,
    projectId,
    shotId: shotId ?? null,
    scope: 'shot',
    defaults: {
      structure_videos: [],
      travel_guidance: undefined,
      travel_guidance_by_model: {},
      structure_guidance: undefined,
    },
    enabled: !!shotId,
    debounceMs: 100,
  });
  const {
    settings: persistedSettings,
    status: persistedStatus,
    updateFields,
  } = settings;

  const storedTravelGuidance = selectedModel
    ? persistedSettings?.travel_guidance_by_model?.[selectedModel] ?? persistedSettings?.travel_guidance
    : persistedSettings?.travel_guidance;

  const resolvedStructureState = useMemo(
    () => resolveTravelStructureState(persistedSettings ?? null, {
      defaultEndFrame: timelineEndFrame,
      defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
      defaultMotionStrength: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.motionStrength,
      defaultStructureType: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.structureType,
      defaultUni3cEndPercent: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.uni3cEndPercent,
    }),
    [persistedSettings, timelineEndFrame],
  );

  const travelGuidance = useMemo(
    () => normalizeTravelGuidance({
      modelName,
      travelGuidance: storedTravelGuidance,
      structureGuidance: persistedSettings?.structure_guidance,
      structureVideos: resolvedStructureState.structureVideos,
      defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
      defaultUni3cEndPercent: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.uni3cEndPercent,
    }),
    [modelName, persistedSettings?.structure_guidance, resolvedStructureState.structureVideos, storedTravelGuidance],
  );

  const structureGuidance = resolvedStructureState.structureGuidance as StructureGuidanceConfig | undefined;

  const structureControls = useMemo(
    () => resolveTravelGuidanceControls(travelGuidance, {
      defaultMode: getDefaultTravelGuidanceMode(modelName),
      defaultStrength: getDefaultTravelGuidanceStrength(
        modelName,
        getDefaultTravelGuidanceMode(modelName),
      ),
      defaultUni3cEndPercent: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.uni3cEndPercent,
    }, modelName),
    [modelName, travelGuidance],
  );

  const structureVideos = resolvedStructureState.structureVideos;
  const travelGuidanceByModel = persistedSettings?.travel_guidance_by_model;
  const structureVideoDefaultsByModel = useMemo(
    () => {
      const firstStructureVideo = structureVideos[0];
      if (!firstStructureVideo) {
        return {};
      }

      return (Object.keys(MODEL_DEFAULTS) as SelectedModel[]).reduce((acc, model) => {
        const guidance = normalizeTravelGuidance({
          modelName: MODEL_DEFAULTS[model].modelName,
          travelGuidance: travelGuidanceByModel?.[model] ?? (model === selectedModel ? travelGuidance : undefined),
          structureGuidance: persistedSettings?.structure_guidance,
          structureVideos,
          defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
          defaultUni3cEndPercent: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.uni3cEndPercent,
        });
        const controls = resolveTravelGuidanceControls(guidance, {
          defaultMode: getDefaultTravelGuidanceMode(MODEL_DEFAULTS[model].modelName),
          defaultStrength: getDefaultTravelGuidanceStrength(
            MODEL_DEFAULTS[model].modelName,
            getDefaultTravelGuidanceMode(MODEL_DEFAULTS[model].modelName),
          ),
          defaultUni3cEndPercent: DEFAULT_STRUCTURE_GUIDANCE_CONTROLS.uni3cEndPercent,
        }, MODEL_DEFAULTS[model].modelName);

        acc[model] = {
          mode: controls.mode,
          motionStrength: controls.strength,
          treatment: firstStructureVideo.treatment,
          uni3cEndPercent: controls.uni3cEndPercent,
          cannyIntensity: controls.cannyIntensity,
          depthContrast: controls.depthContrast,
        };
        return acc;
      }, {} as NonNullable<UseStructureVideoReturn['structureVideoDefaultsByModel']>);
    },
    [persistedSettings?.structure_guidance, selectedModel, structureVideos, travelGuidance, travelGuidanceByModel],
  );

  const setStructureVideos = useCallback((videos: StructureVideoConfigWithMetadata[]) => {
    const sanitizedVideos = sanitizeEditableStructureVideos(videos, timelineEndFrame);

    // When all videos are removed, clear ALL guidance fields to prevent
    // stale video URLs from being resolved back into structure videos.
    if (sanitizedVideos.length === 0) {
      updateFields({
        structure_videos: [],
        travel_guidance: undefined,
        travel_guidance_by_model: {},
        structure_guidance: undefined,
      });
      return;
    }

    const newGuidance = buildTravelGuidanceFromControls({
      modelName,
      structureVideos: sanitizedVideos,
      controls: structureControls,
      defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
    });

    updateFields({
      structure_videos: sanitizedVideos,
      travel_guidance: newGuidance,
      travel_guidance_by_model: {
        ...(persistedSettings?.travel_guidance_by_model ?? {}),
        ...(selectedModel ? { [selectedModel]: newGuidance ?? null } : {}),
      },
      structure_guidance: undefined,
    });
  }, [modelName, persistedSettings?.travel_guidance_by_model, selectedModel, structureControls, timelineEndFrame, updateFields]);

  const updateStructureGuidanceControls = useCallback((updates: Partial<TravelGuidanceControls>) => {
    const sanitizedVideos = sanitizeEditableStructureVideos(structureVideos, timelineEndFrame);
    const nextControls = {
      ...structureControls,
      ...updates,
    };

    updateFields({
      structure_videos: sanitizedVideos,
      travel_guidance: buildTravelGuidanceFromControls({
        modelName,
        structureVideos: sanitizedVideos,
        controls: nextControls,
        defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
      }),
      ...(selectedModel
        ? {
          travel_guidance_by_model: {
            ...(persistedSettings?.travel_guidance_by_model ?? {}),
            [selectedModel]: buildTravelGuidanceFromControls({
              modelName,
              structureVideos: sanitizedVideos,
              controls: nextControls,
              defaultVideoTreatment: DEFAULT_STRUCTURE_VIDEO.treatment,
            }) ?? null,
          },
        }
        : {}),
      structure_guidance: undefined,
    });
  }, [modelName, persistedSettings?.travel_guidance_by_model, selectedModel, structureControls, structureVideos, timelineEndFrame, updateFields]);

  const addStructureVideo = useCallback((video: StructureVideoConfigWithMetadata) => {
    setStructureVideos([...structureVideos, video]);
  }, [setStructureVideos, structureVideos]);

  // Track the latest structure videos in a ref so async callbacks (like metadata
  // extraction) see the current value rather than a stale closure.
  const structureVideosRef = useRef(structureVideos);
  structureVideosRef.current = structureVideos;

  const updateStructureVideo = useCallback((index: number, updates: Partial<StructureVideoConfigWithMetadata>) => {
    const current = structureVideosRef.current;
    if (index < 0 || index >= current.length) {
      return;
    }

    const next = [...current];
    next[index] = { ...next[index], ...updates };
    setStructureVideos(next);
  }, [setStructureVideos]);

  const removeStructureVideo = useCallback((index: number) => {
    const current = structureVideosRef.current;
    if (index < 0 || index >= current.length) {
      return;
    }

    setStructureVideos(current.filter((_, i) => i !== index));
  }, [setStructureVideos]);

  const clearAllStructureVideos = useCallback(() => {
    updateFields({
      structure_videos: [],
      travel_guidance: undefined,
      travel_guidance_by_model: {},
      structure_guidance: undefined,
    });
  }, [updateFields]);

  const primaryStructureVideo = useMemo(
    () => resolvePrimaryStructureVideo(structureVideos, travelGuidance ?? structureGuidance),
    [structureGuidance, structureVideos, travelGuidance],
  );

  return {
    structureVideos,
    travelGuidance,
    travelGuidanceByModel,
    structureGuidance,
    addStructureVideo,
    updateStructureVideo,
    removeStructureVideo,
    clearAllStructureVideos,
    setStructureVideos,
    updateStructureGuidanceControls,
    isLoading: !!shotId && persistedStatus === 'loading',
    structureVideoPath: primaryStructureVideo.path,
    structureVideoMetadata: primaryStructureVideo.metadata,
    structureVideoTreatment: primaryStructureVideo.treatment,
    structureVideoMotionStrength: primaryStructureVideo.motionStrength,
    structureVideoType: primaryStructureVideo.structureType,
    structureVideoResourceId: structureVideos[0]?.resource_id ?? null,
    structureVideoUni3cEndPercent: primaryStructureVideo.uni3cEndPercent,
    structureVideoDefaultsByModel,
  };
}
