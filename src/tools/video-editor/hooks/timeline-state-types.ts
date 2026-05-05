import { useQueryClient } from '@tanstack/react-query';
import type { ApplyEditOptions, TimelineEditMutation } from '@/tools/video-editor/hooks/useTimelineCommit.ts';
import type { CompositionMetadata } from '@/tools/video-editor/hooks/useDerivedTimeline.ts';
import type { RenderRuntime } from '@/tools/video-editor/render/renderRuntime.ts';
import type { AssetRegistryEntry, TrackDefinition } from '@/tools/video-editor/types/index.ts';
import type { AssetRegistry } from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';
import type { TimelineData } from '@/tools/video-editor/lib/timeline-data.ts';

export type TimelineResolvedConfig = TimelineData['resolvedConfig'] | null;
export type TimelineSelectedClip = TimelineData['resolvedConfig']['clips'][number] | null;
export type TimelineSelectedTrack = TrackDefinition | null;
export type TimelineRenderProgress = {
  current: number;
  total: number;
  percent: number;
  phase: string;
} | null;
export type TimelineQueuedRender = {
  providerId: string;
  taskId: string | null;
  correlationId: string | null;
  message: string;
} | null;
export type TimelineRenderRequest = {
  timelineId: string;
  assetRegistry: AssetRegistry | null;
  resolvedConfig: TimelineResolvedConfig;
  renderMetadata: CompositionMetadata | null;
  renderRuntime: RenderRuntime;
};

export type TimelineDataRef = React.MutableRefObject<TimelineData | null>;
export type TimelinePendingOpsRef = React.MutableRefObject<number>;
export type TimelineSetSelectedTrackId = React.Dispatch<React.SetStateAction<string | null>>;
export type TimelineSetRenderLog = React.Dispatch<React.SetStateAction<string>>;
export type TimelineSetRenderDirty = React.Dispatch<React.SetStateAction<boolean>>;
export type TimelineSetScaleWidth = (updater: number | ((value: number) => number)) => void;

export type TimelineApplyEdit = (
  mutation: TimelineEditMutation,
  options?: ApplyEditOptions,
) => void;
export type TimelinePatchRegistry = (
  assetId: string,
  entry: AssetRegistryEntry,
  src?: string,
) => void;
export type TimelineUnpatchRegistry = (assetId: string) => void;
export type TimelineRegisterAsset = (
  assetId: string,
  entry: AssetRegistryEntry,
) => Promise<void>;
export type TimelineQueryClient = ReturnType<typeof useQueryClient>;
export type TimelineUploadAsset = (
  file: File,
) => Promise<{ assetId: string; entry: AssetRegistryEntry }>;
export type TimelineUploadFiles = (files: File[]) => Promise<void>;
export type TimelineInvalidateAssetRegistry = () => Promise<void>;
export type TimelineReloadFromServer = () => Promise<void>;
export type TimelineRetrySaveAfterConflict = () => Promise<void>;
export type TimelineStartRender = () => Promise<void>;
export type TimelineJumpToCheckpoint = (checkpointId: string) => void;
export type TimelineCreateManualCheckpoint = (label?: string) => Promise<void>;
export type TimelineCheckpoints = Checkpoint[];
