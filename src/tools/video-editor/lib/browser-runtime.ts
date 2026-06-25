import type { Shot } from '@/domains/generation/types/index.ts';
import {
  type AssetProfile,
  type SilenceRegion,
  TimelineNotFoundError,
  type DataProvider,
} from '@/tools/video-editor/data/DataProvider.ts';
import { TimelineVersionConflictError } from '@/sdk/video/timeline/errors.ts';
import type { AssetRegistry, AssetRegistryEntry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';

export interface VideoEditorAssetResolver {
  resolveAssetUrl(file: string): Promise<string> | string;
  loadWaveform?(assetId: string): Promise<SilenceRegion[] | null>;
  loadAssetProfile?(assetId: string): Promise<AssetProfile | null>;
}

export interface VideoEditorExportRequest {
  timeline: TimelineConfig;
  registry?: AssetRegistry;
  output: {
    file: string;
    codec?: 'h264' | 'h265' | 'vp8' | 'vp9' | 'prores';
    width?: number;
    height?: number;
    fps?: number;
  };
}

export interface VideoEditorExportProgress {
  phase: 'validating' | 'rendering' | 'encoding' | 'uploading' | 'complete' | 'failed';
  progress?: number;
  log?: string;
  resultUrl?: string | null;
}

export interface VideoEditorExportJob {
  id: string;
  subscribe(listener: (progress: VideoEditorExportProgress) => void): () => void;
  cancel?(): Promise<void>;
}

export interface VideoEditorExporter {
  render(request: VideoEditorExportRequest): Promise<VideoEditorExportJob>;
}

export interface VideoEditorHostContext {
  projectId?: string | null;
  shots?: Shot[] | undefined;
  createShot?: (input: { generationIds: string[] }) => Promise<{ shotId?: string; shot?: Shot | null } | null>;
  isCreatingShot?: boolean;
  navigateToShot?: (shot: Shot, options?: { isNewlyCreated?: boolean }) => void;
}

export interface InMemoryTimelineSeed {
  config: TimelineConfig;
  configVersion?: number;
  registry?: AssetRegistry;
  checkpoints?: Checkpoint[];
}

export interface InMemoryDataProviderOptions {
  timelines?: Record<string, InMemoryTimelineSeed>;
  resolveAssetUrl?: VideoEditorAssetResolver['resolveAssetUrl'];
}

type InMemoryTimelineRecord = Required<Pick<InMemoryTimelineSeed, 'config'>> & {
  configVersion: number;
  registry: AssetRegistry;
  checkpoints: Checkpoint[];
};

const emptyRegistry = (): AssetRegistry => ({ assets: {} });

export class InMemoryDataProvider implements DataProvider {
  private readonly timelines = new Map<string, InMemoryTimelineRecord>();
  private readonly resolveAssetUrlImpl: VideoEditorAssetResolver['resolveAssetUrl'];

  constructor(options: InMemoryDataProviderOptions = {}) {
    for (const [timelineId, seed] of Object.entries(options.timelines ?? {})) {
      this.timelines.set(timelineId, {
        config: seed.config,
        configVersion: seed.configVersion ?? 1,
        registry: seed.registry ?? emptyRegistry(),
        checkpoints: seed.checkpoints ?? [],
      });
    }

    this.resolveAssetUrlImpl = options.resolveAssetUrl ?? ((file) => file);
  }

  async loadTimeline(timelineId: string) {
    const record = this.timelines.get(timelineId);
    if (!record) {
      throw new TimelineNotFoundError(timelineId);
    }

    return {
      config: record.config,
      configVersion: record.configVersion,
    };
  }

  async saveTimeline(
    timelineId: string,
    config: TimelineConfig,
    expectedVersion: number,
    registry?: AssetRegistry,
  ) {
    const current = this.timelines.get(timelineId);
    if (!current) {
      throw new TimelineNotFoundError(timelineId);
    }

    if (current.configVersion !== expectedVersion) {
      throw new TimelineVersionConflictError();
    }

    const nextVersion = current.configVersion + 1;
    this.timelines.set(timelineId, {
      ...current,
      config,
      configVersion: nextVersion,
      registry: registry ?? current.registry,
    });

    return nextVersion;
  }

  async saveCheckpoint(timelineId: string, checkpoint: Omit<Checkpoint, 'id'>) {
    const current = this.timelines.get(timelineId);
    if (!current) {
      throw new TimelineNotFoundError(timelineId);
    }

    const id = `${timelineId}-checkpoint-${current.checkpoints.length + 1}`;
    current.checkpoints = [...current.checkpoints, { ...checkpoint, id }];
    this.timelines.set(timelineId, current);
    return id;
  }

  async loadCheckpoints(timelineId: string) {
    const current = this.timelines.get(timelineId);
    if (!current) {
      throw new TimelineNotFoundError(timelineId);
    }

    return current.checkpoints;
  }

  async loadAssetRegistry(timelineId: string) {
    const current = this.timelines.get(timelineId);
    if (!current) {
      throw new TimelineNotFoundError(timelineId);
    }

    return current.registry;
  }

  async resolveAssetUrl(file: string) {
    return await this.resolveAssetUrlImpl(file);
  }

  async registerAsset(timelineId: string, assetId: string, entry: AssetRegistryEntry) {
    const current = this.timelines.get(timelineId);
    if (!current) {
      throw new TimelineNotFoundError(timelineId);
    }

    current.registry = {
      ...current.registry,
      assets: {
        ...current.registry.assets,
        [assetId]: entry,
      },
    };
    this.timelines.set(timelineId, current);
  }
}

export function createLocalAssetResolver(options: { assetRoot?: string } = {}): VideoEditorAssetResolver {
  const assetRoot = options.assetRoot?.replace(/\/+$/, '') ?? '';

  return {
    resolveAssetUrl(file: string) {
      if (/^(?:[a-z]+:)?\/\//i.test(file) || file.startsWith('data:') || file.startsWith('blob:')) {
        return file;
      }

      if (!assetRoot) {
        return file;
      }

      const normalizedFile = file.replace(/^\/+/, '');
      return `${assetRoot}/${normalizedFile}`;
    },
  };
}
