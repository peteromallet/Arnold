/**
 * Internal Reigh persistence adapter backed by Supabase.
 * Not part of the supported public SDK surface.
 */
import { getSupabaseClient } from '@/integrations/supabase/client.ts';
import { generateUUID } from '@/shared/lib/taskCreation/ids.ts';
import { createDefaultTimelineConfig } from '@/tools/video-editor/lib/defaults.ts';
import { extractAssetRegistryEntry } from '@/tools/video-editor/lib/mediaMetadata.ts';
import {
  serializeTimelineConfigSnapshot,
  serializeTimelinePair,
} from '@/tools/video-editor/lib/timeline-domain.ts';
import {
  TimelineVersionConflictError,
  type DataProvider,
  type LoadedTimeline,
  type UploadAssetOptions,
} from '@/tools/video-editor/data/DataProvider.ts';
import type { AssetRegistry, AssetRegistryEntry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';

const TIMELINE_ASSETS_BUCKET = 'timeline-assets';
const TIMELINE_CHECKPOINT_LIMIT = 30;
const TIMELINE_CHECKPOINT_RETENTION_MS = 24 * 60 * 60 * 1000;


type TimelineCheckpointRow = {
  id: string;
  timeline_id: string;
  config: TimelineConfig;
  created_at: string;
  trigger_type: Checkpoint['triggerType'];
  label: string;
  edits_since_last_checkpoint: number;
};

function mapCheckpointRow(row: TimelineCheckpointRow): Checkpoint {
  return {
    id: row.id,
    timelineId: row.timeline_id,
    config: row.config,
    createdAt: row.created_at,
    triggerType: row.trigger_type,
    label: row.label,
    editsSinceLastCheckpoint: row.edits_since_last_checkpoint,
  };
}

export class SupabaseDataProvider implements DataProvider {
  constructor(
    private readonly options: {
      projectId: string;  // Retained for callers but not used in queries — RLS handles access control.
      userId: string;     // Used only for checkpoint inserts (DB column value, not query filter).
    },
  ) {}

  async loadTimeline(timelineId: string): Promise<LoadedTimeline> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('timelines')
      .select('config, config_version')
      .eq('id', timelineId)
      .maybeSingle();

    if (error) {
      throw error;
    }

    const config = (data?.config ?? createDefaultTimelineConfig()) as TimelineConfig;
    const serialized = serializeTimelineConfigSnapshot(config);

    return {
      config: serialized.config,
      configVersion: typeof (data as { config_version?: unknown } | null)?.config_version === 'number'
        ? (data as { config_version: number }).config_version
        : 1,
    };
  }

  async saveTimeline(
    timelineId: string,
    config: TimelineConfig,
    expectedVersion: number,
    registry?: AssetRegistry,
  ): Promise<number> {
    const supabase = getSupabaseClient();
    const pairSerialized = registry !== undefined ? serializeTimelinePair(config, registry) : null;
    const configSerialized = pairSerialized ?? serializeTimelineConfigSnapshot(config);
    const rpcName = pairSerialized
      ? 'update_timeline_versioned'
      : 'update_timeline_config_versioned';
    const rpcParams = pairSerialized
      ? {
          p_timeline_id: timelineId,
          p_expected_version: expectedVersion,
          p_config: pairSerialized.config,
          p_asset_registry: pairSerialized.registry,
        }
      : {
          p_timeline_id: timelineId,
          p_expected_version: expectedVersion,
          p_config: configSerialized.config,
        };
    const { data, error } = await supabase.rpc(rpcName as never, rpcParams as never);

    if (error) {
      throw error;
    }

    const rows = data as Array<{ config_version: number }> | null;
    if (!rows || rows.length === 0) {
      throw new TimelineVersionConflictError();
    }

    return rows[0].config_version;
  }

  async saveCheckpoint(timelineId: string, checkpoint: Omit<Checkpoint, 'id'>): Promise<string> {
    const serialized = serializeTimelineConfigSnapshot(checkpoint.config);

    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('timeline_checkpoints')
      .insert({
        timeline_id: timelineId,
        user_id: this.options.userId,
        config: serialized.config,
        trigger_type: checkpoint.triggerType,
        label: checkpoint.label,
        edits_since_last_checkpoint: checkpoint.editsSinceLastCheckpoint,
        created_at: checkpoint.createdAt,
      })
      .select('id')
      .single();

    if (error) {
      throw error;
    }

    const { data: checkpointRows, error: checkpointRowsError } = await supabase
      .from('timeline_checkpoints')
      .select('id, trigger_type')
      .eq('timeline_id', timelineId)
      .neq('trigger_type', 'manual')
      .order('created_at', { ascending: false });

    if (checkpointRowsError) {
      throw checkpointRowsError;
    }

    const extraCheckpointIds = (checkpointRows ?? [])
      .slice(TIMELINE_CHECKPOINT_LIMIT)
      .map((row: { id?: unknown }) => row.id)
      .filter((id: unknown): id is string => typeof id === 'string');

    if (extraCheckpointIds.length > 0) {
      const { error: deleteError } = await supabase
        .from('timeline_checkpoints')
        .delete()
        .in('id', extraCheckpointIds);

      if (deleteError) {
        throw deleteError;
      }
    }

    return data.id;
  }

  async loadCheckpoints(timelineId: string): Promise<Checkpoint[]> {
    const supabase = getSupabaseClient();
    const retentionCutoff = new Date(Date.now() - TIMELINE_CHECKPOINT_RETENTION_MS).toISOString();

    const { error: cleanupError } = await supabase
      .from('timeline_checkpoints')
      .delete()
      .eq('timeline_id', timelineId)
      .neq('trigger_type', 'manual')
      .lt('created_at', retentionCutoff);

    if (cleanupError) {
      throw cleanupError;
    }

    const { data, error } = await supabase
      .from('timeline_checkpoints')
      .select('id, timeline_id, config, created_at, trigger_type, label, edits_since_last_checkpoint')
      .eq('timeline_id', timelineId)
      .order('created_at', { ascending: false });

    if (error) {
      throw error;
    }

    return (data ?? []).map((row: unknown) => mapCheckpointRow(row as TimelineCheckpointRow));
  }

  async loadAssetRegistry(timelineId: string): Promise<AssetRegistry> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('timelines')
      .select('asset_registry')
      .eq('id', timelineId)
      .maybeSingle();

    if (error) {
      throw error;
    }

    return (data?.asset_registry as AssetRegistry | null) ?? { assets: {} };
  }

  async resolveAssetUrl(file: string): Promise<string> {
    const sanitizedFile = file.trim();
    if (sanitizedFile.length === 0) {
      throw new Error('Cannot resolve asset URL for an empty file path');
    }

    if (/^https?:\/\//.test(sanitizedFile)) {
      return sanitizedFile;
    }

    const supabase = getSupabaseClient();
    const { data } = supabase
      .storage
      .from(TIMELINE_ASSETS_BUCKET)
      .getPublicUrl(sanitizedFile);

    return data.publicUrl;
  }

  async registerAsset(
    timelineId: string,
    assetId: string,
    entry: AssetRegistryEntry,
  ): Promise<void> {
    const supabase = getSupabaseClient();
    const { error } = await supabase
      .rpc('upsert_asset_registry_entry' as never, {
        p_timeline_id: timelineId,
        p_asset_id: assetId,
        p_entry: entry,
      } as never);

    if (error) {
      throw error;
    }
  }

  async uploadAsset(
    file: File,
    options: UploadAssetOptions,
  ): Promise<{ assetId: string; entry: Awaited<ReturnType<typeof extractAssetRegistryEntry>> }> {
    const safeFilename = (options.filename ?? file.name)
      .replace(/\s+/g, '-')
      .replace(/[^a-zA-Z0-9._-]/g, '');
    const storagePath = `${options.userId}/${options.timelineId}/${Date.now()}-${safeFilename}`;

    const supabase = getSupabaseClient();
    const { error: uploadError } = await supabase
      .storage
      .from(TIMELINE_ASSETS_BUCKET)
      .upload(storagePath, file, {
        upsert: false,
        contentType: file.type || undefined,
      });

    if (uploadError) {
      throw uploadError;
    }

    const entry = await extractAssetRegistryEntry(file, storagePath);
    const assetId = generateUUID();
    await this.registerAsset(options.timelineId, assetId, entry);

    return { assetId, entry };
  }

  async loadWaveform(): Promise<null> {
    return null;
  }

  async loadAssetProfile(): Promise<null> {
    return null;
  }
}
