import type { AssetRegistry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';
import type { AssetResolver } from '@/tools/video-editor/data/AssetResolver.ts';
export type {
  AssetProfile,
  SilenceRegion,
  UploadedAssetResult,
  UploadAssetOptions,
} from '@/tools/video-editor/data/AssetResolver.ts';

export interface LoadedTimeline {
  config: TimelineConfig;
  configVersion: number;
}

export class TimelineVersionConflictError extends Error {
  code = 'timeline_version_conflict' as const;

  constructor(message = 'Timeline version conflict') {
    super(message);
    this.name = 'TimelineVersionConflictError';
  }
}

export function isTimelineVersionConflictError(error: unknown): error is TimelineVersionConflictError {
  return error instanceof TimelineVersionConflictError
    || (error instanceof Error && error.name === 'TimelineVersionConflictError');
}

export class TimelineNotFoundError extends Error {
  code = 'timeline_not_found' as const;

  constructor(timelineId: string) {
    super(`Timeline ${timelineId} not found — it may have been deleted`);
    this.name = 'TimelineNotFoundError';
  }
}

export function isTimelineNotFoundError(error: unknown): error is TimelineNotFoundError {
  return error instanceof TimelineNotFoundError
    || (error instanceof Error && error.name === 'TimelineNotFoundError');
}

export interface DataProvider extends AssetResolver {
  persistenceEnabled?: boolean;
  loadTimeline(timelineId: string): Promise<LoadedTimeline>;
  saveTimeline(
    timelineId: string,
    config: TimelineConfig,
    expectedVersion: number,
    registry?: AssetRegistry,
  ): Promise<number>;
  saveCheckpoint?(timelineId: string, checkpoint: Omit<Checkpoint, 'id'>): Promise<string>;
  loadCheckpoints?(timelineId: string): Promise<Checkpoint[]>;
  loadAssetRegistry(timelineId: string): Promise<AssetRegistry>;
}

export function isDataProviderPersistenceEnabled(provider: DataProvider | null | undefined): boolean {
  return provider?.persistenceEnabled !== false;
}

// The persistence boundary for the headless editor core remains the existing
// data provider contract. Core/runtime ports can rename or regroup host inputs,
// but persistence should continue to flow through this canonical interface.
export type VideoEditorPersistencePort = DataProvider;
