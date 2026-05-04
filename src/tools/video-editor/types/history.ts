import type {
  TimelineCommandHistoryMetadata,
  TimelineCommandTransaction,
} from '@/tools/video-editor/commands';
import type { AssetRegistry, TimelineConfig } from './index';

export type UndoSnapshot = {
  config: TimelineConfig;
  registry?: AssetRegistry;
  signature: string;
};

export type UndoEntry = {
  snapshot: UndoSnapshot;
  timestamp: string;
  label?: string;
  transactionId?: string;
  command?: {
    history: TimelineCommandHistoryMetadata;
    undoTransaction: TimelineCommandTransaction;
    redoTransaction: TimelineCommandTransaction;
  };
};

export type CheckpointTriggerType =
  | 'session_boundary'
  | 'edit_distance'
  | 'semantic'
  | 'manual';

export type Checkpoint = {
  id: string;
  timelineId: string;
  config: TimelineConfig;
  createdAt: string;
  triggerType: CheckpointTriggerType;
  label: string;
  editsSinceLastCheckpoint: number;
};
