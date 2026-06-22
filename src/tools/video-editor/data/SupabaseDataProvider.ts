/**
 * Internal Reigh persistence adapter backed by Supabase.
 * Not part of the supported public SDK surface.
 */
import { getSupabaseClient } from '@/integrations/supabase/client.ts';
import { readAccessTokenFromStorage } from '@/shared/lib/supabaseSession';
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
import {
  loadSyncBookmark,
  saveKeepBothArtifact,
  saveSyncBookmark,
  type KeepBothArtifactRecord,
  type SyncBookmarkRecord,
} from '@/tools/video-editor/data/syncLedgerIndexedDb.ts';
import type { AssetRegistry, AssetRegistryEntry, TimelineConfig } from '@/tools/video-editor/types/index.ts';
import type { Checkpoint } from '@/tools/video-editor/types/history.ts';

import type { ExtensionDiagnostic } from '@reigh/editor-sdk';
import type {
  ExtensionPersistenceScope,
  ExtensionPersistenceService,
  ExtensionProposalStatus,
} from '@/tools/video-editor/data/DataProvider';
import type { FullSnapshotStore } from '@/tools/video-editor/runtime/extensionPersistenceCache';
import { createCachedExtensionPersistenceService } from '@/tools/video-editor/runtime/extensionPersistenceCache';

/** Local type matching the ExtensionProposal shape used by the cache layer. */
interface ExtensionProposal {
  id: string;
  extensionId: string;
  status: ExtensionProposalStatus;
  payload: Record<string, unknown>;
  createdAt: string;
  updatedAt: string;
  label?: string;
}

const TIMELINE_ASSETS_BUCKET = 'timeline-assets';
const TIMELINE_CHECKPOINT_LIMIT = 30;
const TIMELINE_CHECKPOINT_RETENTION_MS = 24 * 60 * 60 * 1000;
const APPEND_SERVICE_URL_ENV = 'VITE_REIGH_APPEND_SERVICE_URL';

type AppendServiceSuccess = {
  config_version?: unknown;
  db_head?: {
    version?: unknown;
    hash?: unknown;
    event_id?: unknown;
  };
};

type AppendServiceFailure = {
  error?: unknown;
  detail?: unknown;
  details?: unknown;
};

type DbHeadSnapshot = {
  version: number;
  hash: string | null;
  event_id: string | null;
};

type HeadRelation = 'equal' | 'advanced' | 'behind' | 'conflict';

export type AppSyncState =
  | 'up_to_date'
  | 'source_only'
  | 'destination_only'
  | 'both_advanced'
  | 'bookmark_missing'
  | 'bookmark_incompatible';

export type SyncTimelineAction =
  | 'none'
  | 'saved'
  | 'reload_required'
  | 'bookmark_bootstrapped'
  | 'divergence_recorded';

export interface SyncTimelineOptions {
  timelineId: string;
  config: TimelineConfig;
  currentConfigVersion: number;
  hasUnsavedEdits: boolean;
  registry?: AssetRegistry;
}

export interface SyncTimelineResult {
  state: AppSyncState;
  action: SyncTimelineAction;
  configVersion: number;
  dbHead: DbHeadSnapshot;
  bookmark: SyncBookmarkRecord | null;
  keepBothArtifact?: {
    id: string;
    created_at: string;
    remote_entry_id: string | null;
  };
}


type TimelineCheckpointRow = {
  id: string;
  timeline_id: string;
  config: TimelineConfig;
  created_at: string;
  trigger_type: Checkpoint['triggerType'];
  label: string;
  edits_since_last_checkpoint: number;
};

type SyncBookmarkRow = {
  timeline_id?: unknown;
  spoke?: unknown;
  spoke_version?: unknown;
  spoke_hash?: unknown;
  spoke_event_id?: unknown;
  hub_version?: unknown;
  hub_hash?: unknown;
  hub_event_id?: unknown;
  synced_at?: unknown;
};

type AppBookmarkResponse = {
  bookmark?: unknown;
};

type AppDivergenceResponse = {
  divergence?: {
    id?: unknown;
    created_at?: unknown;
  };
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

function getAppendServiceBaseUrl(): string {
  const value = (import.meta.env[APPEND_SERVICE_URL_ENV] as string | undefined)?.trim();
  if (!value) {
    throw new Error(`Missing required append service environment variable: ${APPEND_SERVICE_URL_ENV}`);
  }
  return value.replace(/\/+$/, '');
}

async function parseJsonIfPresent(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function getUserJwt(): Promise<string> {
  const cachedToken = readAccessTokenFromStorage()?.trim();
  if (cachedToken) {
    return cachedToken;
  }

  const { data, error } = await getSupabaseClient().auth.getSession();
  if (error) {
    throw error;
  }

  const accessToken = data.session?.access_token?.trim();
  if (!accessToken) {
    throw new Error('User not authenticated');
  }
  return accessToken;
}

function getAppendServiceErrorDetail(payload: unknown): string | null {
  if (typeof payload === 'string' && payload.trim()) {
    return payload;
  }
  if (!payload || typeof payload !== 'object') {
    return null;
  }
  const errorPayload = payload as AppendServiceFailure;
  if (typeof errorPayload.detail === 'string' && errorPayload.detail.trim()) {
    return errorPayload.detail;
  }
  if (typeof errorPayload.details === 'string' && errorPayload.details.trim()) {
    return errorPayload.details;
  }
  if (typeof errorPayload.error === 'string' && errorPayload.error.trim()) {
    return errorPayload.error;
  }
  return null;
}

function parseDbHead(value: unknown, label: string): DbHeadSnapshot {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is required`);
  }
  const head = value as { version?: unknown; hash?: unknown; event_id?: unknown };
  const version = head.version;
  if (!Number.isInteger(version) || (version as number) < 0) {
    throw new Error(`${label}.version must be a non-negative integer`);
  }
  if ((version as number) === 0) {
    return { version: 0, hash: null, event_id: null };
  }
  if (typeof head.hash !== 'string' || head.hash.length === 0) {
    throw new Error(`${label}.hash is required when version is non-zero`);
  }
  if (typeof head.event_id !== 'string' || head.event_id.length === 0) {
    throw new Error(`${label}.event_id is required when version is non-zero`);
  }
  return {
    version: version as number,
    hash: head.hash,
    event_id: head.event_id,
  };
}

function normalizeSyncBookmark(value: unknown): SyncBookmarkRecord | null {
  if (!value || typeof value !== 'object') {
    return null;
  }
  const row = value as SyncBookmarkRow;
  if (typeof row.timeline_id !== 'string' || (row.spoke !== 'local' && row.spoke !== 'app')) {
    return null;
  }
  const spokeVersion = row.spoke_version;
  const hubVersion = row.hub_version;
  if (!Number.isInteger(spokeVersion) || !Number.isInteger(hubVersion)) {
    return null;
  }
  const bookmark: SyncBookmarkRecord = {
    timeline_id: row.timeline_id,
    spoke: row.spoke,
    spoke_version: spokeVersion as number,
    spoke_hash: typeof row.spoke_hash === 'string' ? row.spoke_hash : null,
    spoke_event_id: typeof row.spoke_event_id === 'string' ? row.spoke_event_id : null,
    hub_version: hubVersion as number,
    hub_hash: typeof row.hub_hash === 'string' ? row.hub_hash : null,
    hub_event_id: typeof row.hub_event_id === 'string' ? row.hub_event_id : null,
    synced_at: typeof row.synced_at === 'string' ? row.synced_at : new Date(0).toISOString(),
  };
  return bookmark;
}

function buildBookmarkFromDbHead(timelineId: string, head: DbHeadSnapshot, syncedAt = new Date().toISOString()): SyncBookmarkRecord {
  return {
    timeline_id: timelineId,
    spoke: 'app',
    spoke_version: head.version,
    spoke_hash: head.hash,
    spoke_event_id: head.event_id,
    hub_version: head.version,
    hub_hash: head.hash,
    hub_event_id: head.event_id,
    synced_at: syncedAt,
  };
}

function bookmarksEqual(left: SyncBookmarkRecord | null, right: SyncBookmarkRecord | null): boolean {
  if (left === right) {
    return true;
  }
  if (!left || !right) {
    return false;
  }
  return JSON.stringify(left) === JSON.stringify(right);
}

function compareDbHeadToBookmarkHead(head: DbHeadSnapshot, bookmark: SyncBookmarkRecord): HeadRelation {
  if (head.version === bookmark.hub_version) {
    return head.hash === bookmark.hub_hash && head.event_id === bookmark.hub_event_id ? 'equal' : 'conflict';
  }
  return head.version > bookmark.hub_version ? 'advanced' : 'behind';
}


// ==========================================================================
// T10: SupabaseFullSnapshotStore — FullSnapshotStore over Supabase tables
// ==========================================================================

/** Sentinel extension_id used to store the base state in extension_install_state. */
const SNAPSHOT_SENTINEL_ID = '__reigh_snapshot__';

interface SettingsRow {
  id: string;
  user_id: string;
  timeline_id: string;
  extension_id: string;
  schema_version: number;
  values: Record<string, unknown>;
  last_written_at: string;
}

/**
 * A {@link FullSnapshotStore} that persists the cached extension state
 * snapshot across Supabase extension tables.
 *
 * ## Sentinel row pattern
 *
 * The base state (meta, packs, enablement, overrides, events, lock) is
 * stored in a single `extension_install_state` row with
 * `extension_id = '__reigh_snapshot__'`.  Settings are stored as
 * individual rows in `extension_settings`.  Proposals are stored as
 * individual rows in `extension_proposals`.
 *
 * ## Error propagation
 *
 * Every Supabase error is re-thrown — never swallowed.  This ensures
 * the cache (CachedExtensionStateRepository) can catch the error, emit
 * a diagnostic, and enter fail-closed state.
 */
class SupabaseFullSnapshotStore implements FullSnapshotStore {
  private readonly _scope: ExtensionPersistenceScope;

  constructor(scope: ExtensionPersistenceScope) {
    this._scope = scope;
  }

  // -------------------------------------------------------------------
  // FullSnapshotStore
  // -------------------------------------------------------------------

  async loadSnapshot(): Promise<string | null> {
    const supabase = getSupabaseClient();
    const { userId, timelineId } = this._scope;

    // 1. Load sentinel row (base state)
    const { data: sentinel, error: sentinelError } = await supabase
      .from('extension_install_state')
      .select('metadata')
      .eq('user_id', userId)
      .eq('timeline_id', timelineId)
      .eq('extension_id', SNAPSHOT_SENTINEL_ID)
      .maybeSingle();

    if (sentinelError) {
      throw sentinelError;
    }

    if (!sentinel?.metadata) {
      return null;
    }

    const base = sentinel.metadata as Record<string, unknown>;

    // 2. Load settings rows
    const { data: settingsRows, error: settingsError } = await supabase
      .from('extension_settings')
      .select('extension_id, schema_version, values, last_written_at')
      .eq('user_id', userId)
      .eq('timeline_id', timelineId);

    if (settingsError) {
      throw settingsError;
    }

    const settings: Record<string, unknown> = {};
    for (const row of (settingsRows ?? []) as SettingsRow[]) {
      settings[row.extension_id] = {
        extensionId: row.extension_id,
        schemaVersion: row.schema_version,
        values: row.values,
        lastWrittenAt: row.last_written_at,
      };
    }
    base.settings = settings;

    // 3. Load proposals
    const { data: proposalRows, error: proposalsError } = await supabase
      .from('extension_proposals')
      .select('id, extension_id, status, payload, label, created_at, updated_at')
      .eq('user_id', userId)
      .eq('timeline_id', timelineId);

    if (proposalsError) {
      throw proposalsError;
    }

    const proposals: Record<string, unknown> = {};
    for (const row of (proposalRows ?? []) as Array<{ id: string; extension_id: string; status: string; payload: Record<string, unknown>; label: string | null; created_at: string; updated_at: string }>) {
      proposals[row.id] = {
        id: row.id,
        extensionId: row.extension_id,
        status: row.status,
        payload: row.payload,
        createdAt: row.created_at,
        updatedAt: row.updated_at,
        ...(row.label !== null && row.label !== undefined ? { label: row.label } : {}),
      };
    }
    base.proposals = proposals;

    return JSON.stringify(base);
  }

  async saveSnapshot(serialized: string): Promise<void> {
    const supabase = getSupabaseClient();
    const { userId, timelineId } = this._scope;

    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(serialized);
    } catch {
      return; // Defensive — cache always serializes valid JSON
    }

    // Extract settings and proposals from the snapshot
    const settings =
      (parsed.settings as Record<string, Record<string, unknown>>) ?? {};
    const { settings: _settings, proposals: _proposals, ...base } = parsed;

    // 1. Upsert sentinel row with base state (excl. settings, proposals)
    // Use the unique constraint on (user_id, timeline_id, extension_id)
    const { error: sentinelError } = await supabase
      .from('extension_install_state')
      .upsert(
        {
          user_id: userId,
          timeline_id: timelineId,
          extension_id: SNAPSHOT_SENTINEL_ID,
          metadata: base,
          schema_version: 1,
        },
        {
          onConflict: 'user_id,timeline_id,extension_id',
          ignoreDuplicates: false,
        },
      );

    if (sentinelError) {
      throw sentinelError;
    }

    // 2. Upsert settings rows
    for (const [extensionId, snapshot] of Object.entries(settings)) {
      const { error: settingsError } = await supabase
        .from('extension_settings')
        .upsert(
          {
            user_id: userId,
            timeline_id: timelineId,
            extension_id: extensionId,
            schema_version:
              (snapshot as Record<string, unknown>).schemaVersion as number ?? 1,
            values:
              ((snapshot as Record<string, unknown>).values as Record<string, unknown>) ?? {},
            last_written_at:
              ((snapshot as Record<string, unknown>).lastWrittenAt as string) ??
              new Date().toISOString(),
          },
          {
            onConflict: 'user_id,timeline_id,extension_id',
            ignoreDuplicates: false,
          },
        );

      if (settingsError) {
        throw settingsError;
      }
    }

    // 3. Delete existing proposals for this scope, then re-insert
    const proposals =
      (parsed.proposals as Record<string, ExtensionProposal>) ?? {};

    // Delete all existing proposals for this scope
    const { error: deleteError } = await supabase
      .from('extension_proposals')
      .delete()
      .eq('user_id', userId)
      .eq('timeline_id', timelineId);

    if (deleteError) {
      throw deleteError;
    }

    // Insert current proposals
    for (const proposal of Object.values(proposals)) {
      const { error: insertError } = await supabase
        .from('extension_proposals')
        .insert({
          id: proposal.id,
          user_id: userId,
          timeline_id: timelineId,
          extension_id: proposal.extensionId,
          status: proposal.status,
          payload: proposal.payload,
          label: proposal.label ?? null,
          schema_version: 1,
        });

      if (insertError) {
        throw insertError;
      }
    }
  }

  async deleteSnapshot(): Promise<void> {
    const supabase = getSupabaseClient();
    const { userId, timelineId } = this._scope;

    // Delete all rows across all three tables for this scope
    const { error: installError } = await supabase
      .from('extension_install_state')
      .delete()
      .eq('user_id', userId)
      .eq('timeline_id', timelineId);

    if (installError) {
      throw installError;
    }

    const { error: settingsError } = await supabase
      .from('extension_settings')
      .delete()
      .eq('user_id', userId)
      .eq('timeline_id', timelineId);

    if (settingsError) {
      throw settingsError;
    }

    const { error: proposalsError } = await supabase
      .from('extension_proposals')
      .delete()
      .eq('user_id', userId)
      .eq('timeline_id', timelineId);

    if (proposalsError) {
      throw proposalsError;
    }
  }
}



export class SupabaseDataProvider implements DataProvider {
  constructor(
    private readonly options: {
      projectId: string;  // Retained for callers but not used in queries — RLS handles access control.
      userId: string;     // Used only for checkpoint inserts (DB column value, not query filter).
    },
  ) {}

  private async loadDbHead(timelineId: string): Promise<DbHeadSnapshot> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('timeline_events')
      .select('version, hash, event_id')
      .eq('timeline_id', timelineId)
      .order('version', { ascending: false })
      .limit(1)
      .maybeSingle();

    if (error) {
      throw error;
    }

    if (!data) {
      return { version: 0, hash: null, event_id: null };
    }

    return parseDbHead(data, 'db_head');
  }

  private async loadDbAppBookmark(timelineId: string): Promise<SyncBookmarkRecord | null> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('sync_bookmarks')
      .select('timeline_id, spoke, spoke_version, spoke_hash, spoke_event_id, hub_version, hub_hash, hub_event_id, synced_at')
      .eq('timeline_id', timelineId)
      .eq('spoke', 'app')
      .maybeSingle();

    if (error) {
      throw error;
    }

    return normalizeSyncBookmark(data);
  }

  private async saveLocalBookmark(bookmark: SyncBookmarkRecord): Promise<void> {
    await saveSyncBookmark(bookmark);
  }

  private async recordRemoteAppBookmark(timelineId: string, dbHead: DbHeadSnapshot): Promise<SyncBookmarkRecord> {
    const response = await fetch(
      `${getAppendServiceBaseUrl()}/v1/timelines/${encodeURIComponent(timelineId)}/app-bookmark`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getUserJwt()}`,
        },
        body: JSON.stringify({ db_head: dbHead }),
      },
    );
    const payload = await parseJsonIfPresent(response);
    if (!response.ok) {
      const detail = getAppendServiceErrorDetail(payload);
      throw new Error(detail ? `Append service app bookmark failed: ${detail}` : `Append service app bookmark failed with status ${response.status}`);
    }
    const bookmark = normalizeSyncBookmark((payload as AppBookmarkResponse | null)?.bookmark);
    if (!bookmark) {
      throw new Error('Append service app bookmark returned an invalid bookmark');
    }
    await this.saveLocalBookmark(bookmark);
    return bookmark;
  }

  private async createKeepBothArtifact(
    timelineId: string,
    config: TimelineConfig,
    currentConfigVersion: number,
    registry: AssetRegistry | undefined,
    dbHead: DbHeadSnapshot,
    bookmark: SyncBookmarkRecord | null,
  ): Promise<KeepBothArtifactRecord> {
    const supabase = getSupabaseClient();
    const { data, error } = await supabase
      .from('timelines')
      .select('config, config_version, asset_registry')
      .eq('id', timelineId)
      .maybeSingle();
    if (error) {
      throw error;
    }
    const remoteConfig = serializeTimelineConfigSnapshot(
      ((data as { config?: TimelineConfig | null } | null)?.config ?? createDefaultTimelineConfig()) as TimelineConfig,
    ).config;
    const remoteConfigVersion = typeof (data as { config_version?: unknown } | null)?.config_version === 'number'
      ? (data as { config_version: number }).config_version
      : 1;
    const remoteRegistry = ((data as { asset_registry?: AssetRegistry | null } | null)?.asset_registry ?? { assets: {} }) as AssetRegistry;
    const createdAt = new Date().toISOString();
    const artifact: KeepBothArtifactRecord = {
      id: `keep-both-${Date.now()}-${generateUUID()}`,
      timeline_id: timelineId,
      spoke: 'app',
      created_at: createdAt,
      artifact: {
        kind: 'app_sync_divergence',
        timeline_id: timelineId,
        created_at: createdAt,
        bookmark,
        db_head: dbHead,
        app_draft: {
          config,
          asset_registry: registry ?? null,
          config_version: currentConfigVersion,
        },
        remote_timeline: {
          config: remoteConfig,
          asset_registry: remoteRegistry,
          config_version: remoteConfigVersion,
        },
      },
    };
    await saveKeepBothArtifact(artifact);
    return artifact;
  }

  private async recordRemoteDivergence(
    timelineId: string,
    config: TimelineConfig,
    registry: AssetRegistry | undefined,
    dbHead: DbHeadSnapshot,
    artifact: KeepBothArtifactRecord,
  ): Promise<{ id: string | null; created_at: string } | null> {
    const response = await fetch(
      `${getAppendServiceBaseUrl()}/v1/timelines/${encodeURIComponent(timelineId)}/app-divergence`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getUserJwt()}`,
        },
        body: JSON.stringify({
          config,
          asset_registry: registry,
          db_head: dbHead,
          source: 'editor_sync',
          artifact_pointer: {
            kind: 'indexeddb',
            id: artifact.id,
            created_at: artifact.created_at,
          },
        }),
      },
    );
    if (response.status === 404) {
      return null;
    }
    const payload = await parseJsonIfPresent(response);
    if (!response.ok) {
      return null;
    }
    const divergence = (payload as AppDivergenceResponse | null)?.divergence;
    return {
      id: typeof divergence?.id === 'string' ? divergence.id : null,
      created_at: typeof divergence?.created_at === 'string' ? divergence.created_at : artifact.created_at,
    };
  }

  async loadTimeline(timelineId: string): Promise<LoadedTimeline> {
    const supabase = getSupabaseClient();
    const [{ data, error }, dbHead] = await Promise.all([
      supabase
        .from('timelines')
        .select('config, config_version')
        .eq('id', timelineId)
        .maybeSingle(),
      this.loadDbHead(timelineId),
    ]);

    if (error) {
      throw error;
    }

    const config = (data?.config ?? createDefaultTimelineConfig()) as TimelineConfig;
    const serialized = serializeTimelineConfigSnapshot(config);

    const loadedTimeline = {
      config: serialized.config,
      configVersion: typeof (data as { config_version?: unknown } | null)?.config_version === 'number'
        ? (data as { config_version: number }).config_version
        : 1,
    };
    await this.saveLocalBookmark(buildBookmarkFromDbHead(timelineId, dbHead));
    return loadedTimeline;
  }

  async saveTimeline(
    timelineId: string,
    config: TimelineConfig,
    expectedVersion: number,
    registry?: AssetRegistry,
  ): Promise<number> {
    const pairSerialized = registry !== undefined ? serializeTimelinePair(config, registry) : null;
    const configSerialized = pairSerialized ?? serializeTimelineConfigSnapshot(config);
    const response = await fetch(
      `${getAppendServiceBaseUrl()}/v1/timelines/${encodeURIComponent(timelineId)}/config-replaced`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${await getUserJwt()}`,
        },
        body: JSON.stringify({
          config: configSerialized.config,
          asset_registry: pairSerialized?.registry,
          expected_version: expectedVersion,
          actor: {
            type: 'human',
            id: this.options.userId,
          },
          source: 'editor_save',
        }),
      },
    );

    const payload = await parseJsonIfPresent(response);
    if (response.status === 409) {
      throw new TimelineVersionConflictError();
    }
    if (!response.ok) {
      const detail = getAppendServiceErrorDetail(payload);
      throw new Error(detail ? `Append service save failed: ${detail}` : `Append service save failed with status ${response.status}`);
    }
    if (!payload || typeof payload !== 'object' || typeof (payload as AppendServiceSuccess).config_version !== 'number') {
      throw new Error('Append service save returned an invalid config_version');
    }

    const dbHead = parseDbHead((payload as AppendServiceSuccess).db_head, 'db_head');
    await this.saveLocalBookmark(buildBookmarkFromDbHead(timelineId, dbHead));
    return (payload as AppendServiceSuccess).config_version as number;
  }

  async syncTimeline(options: SyncTimelineOptions): Promise<SyncTimelineResult> {
    const { timelineId, config, currentConfigVersion, hasUnsavedEdits, registry } = options;
    const [dbHead, localBookmark, remoteBookmark] = await Promise.all([
      this.loadDbHead(timelineId),
      loadSyncBookmark(timelineId, 'app'),
      this.loadDbAppBookmark(timelineId),
    ]);

    if (localBookmark && remoteBookmark && !bookmarksEqual(localBookmark, remoteBookmark)) {
      return {
        state: 'bookmark_incompatible',
        action: 'none',
        configVersion: currentConfigVersion,
        dbHead,
        bookmark: localBookmark,
      };
    }

    const bookmark = localBookmark ?? remoteBookmark;
    if (!bookmark) {
      if (!hasUnsavedEdits && currentConfigVersion === dbHead.version) {
        const bootstrappedBookmark = await this.recordRemoteAppBookmark(timelineId, dbHead);
        return {
          state: 'bookmark_missing',
          action: 'bookmark_bootstrapped',
          configVersion: currentConfigVersion,
          dbHead,
          bookmark: bootstrappedBookmark,
        };
      }
      if (hasUnsavedEdits && currentConfigVersion === dbHead.version) {
        const nextVersion = await this.saveTimeline(timelineId, config, currentConfigVersion, registry);
        return {
          state: 'source_only',
          action: 'saved',
          configVersion: nextVersion,
          dbHead: await this.loadDbHead(timelineId),
          bookmark: await loadSyncBookmark(timelineId, 'app'),
        };
      }
      if (!hasUnsavedEdits && currentConfigVersion < dbHead.version) {
        return {
          state: 'destination_only',
          action: 'reload_required',
          configVersion: currentConfigVersion,
          dbHead,
          bookmark: null,
        };
      }
      return {
        state: 'bookmark_incompatible',
        action: 'none',
        configVersion: currentConfigVersion,
        dbHead,
        bookmark: null,
      };
    }

    const relation = compareDbHeadToBookmarkHead(dbHead, bookmark);
    if (relation === 'equal') {
      if (!localBookmark) {
        await this.saveLocalBookmark(bookmark);
      }
      if (!remoteBookmark) {
        await this.recordRemoteAppBookmark(timelineId, dbHead);
      }
      if (hasUnsavedEdits) {
        const nextVersion = await this.saveTimeline(timelineId, config, currentConfigVersion, registry);
        return {
          state: 'source_only',
          action: 'saved',
          configVersion: nextVersion,
          dbHead: await this.loadDbHead(timelineId),
          bookmark: await loadSyncBookmark(timelineId, 'app'),
        };
      }
      return {
        state: 'up_to_date',
        action: 'none',
        configVersion: currentConfigVersion,
        dbHead,
        bookmark: await loadSyncBookmark(timelineId, 'app'),
      };
    }

    if (relation === 'advanced') {
      if (!hasUnsavedEdits) {
        return {
          state: 'destination_only',
          action: 'reload_required',
          configVersion: currentConfigVersion,
          dbHead,
          bookmark,
        };
      }
      const artifact = await this.createKeepBothArtifact(
        timelineId,
        config,
        currentConfigVersion,
        registry,
        dbHead,
        bookmark,
      );
      const remoteDivergence = await this.recordRemoteDivergence(timelineId, config, registry, dbHead, artifact);
      return {
        state: 'both_advanced',
        action: 'divergence_recorded',
        configVersion: currentConfigVersion,
        dbHead,
        bookmark,
        keepBothArtifact: {
          id: artifact.id,
          created_at: remoteDivergence?.created_at ?? artifact.created_at,
          remote_entry_id: remoteDivergence?.id ?? null,
        },
      };
    }

    return {
      state: 'bookmark_incompatible',
      action: 'none',
      configVersion: currentConfigVersion,
      dbHead,
      bookmark,
    };
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

  // -------------------------------------------------------------------------
  // Extension persistence (T10)
  // -------------------------------------------------------------------------

  /**
   * Create a Supabase-backed extension persistence service for the given
   * (userId, timelineId) scope.
   *
   * All extension state, settings, and proposals are stored in the
   * extension_install_state, extension_settings, and extension_proposals
   * Supabase tables, every query scoped by both user_id and timeline_id.
   *
   * The returned service advertises full capabilities (state, settings,
   * proposals) and is backed by a shared cache (CachedExtensionStateRepository
   * + CachedExtensionPersistenceService) wired on top of a
   * SupabaseFullSnapshotStore.
   *
   * @param scope        The (userId, timelineId) scope for all extension data.
   * @param diagnostics  An array the provider may append
   *                     {@link ExtensionDiagnostic} entries to.
   */
  createExtensionPersistenceService(
    scope: ExtensionPersistenceScope,
    diagnostics: ExtensionDiagnostic[],
  ): ExtensionPersistenceService {
    const store = new SupabaseFullSnapshotStore(scope);
    return createCachedExtensionPersistenceService(store, diagnostics, scope);
  }
}
