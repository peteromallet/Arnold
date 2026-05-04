import type { Shot } from '@/domains/generation/types';
import type { VideoEditorPersistencePort } from '@/tools/video-editor/data/DataProvider';

export interface VideoEditorFinalVideo {
  id: string;
  location: string;
  thumbnailUrl: string | null;
  variantFetchGenerationId?: string | null;
  durationSeconds?: number | null;
}

export interface VideoEditorCorePorts {
  dataProvider: VideoEditorPersistencePort;
  selectedProjectId?: string | null;
  shots?: Shot[] | undefined;
  finalVideoMap?: Map<string, VideoEditorFinalVideo>;
}
