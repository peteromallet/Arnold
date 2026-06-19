/**
 * TimelineReader — stable, read-only projection of timeline state.
 *
 * Exposes TimelineSnapshot summaries while hiding raw row/meta/registry
 * internals.  Extensions and proposal machinery consume this reader
 * instead of raw TimelineData, useTimelineCommit, or store internals.
 *
 * @publicContract
 */

import type {
  TimelineReader,
  TimelineSnapshot,
  TimelineClipSummary,
  TimelineTrackSummary,
  ProjectExtensionRequirement,
  GeneratedObjectMeta,
  SourceMapEntry,
} from '@/sdk/index';

import type { TimelineData, ClipMeta } from '@/tools/video-editor/lib/timeline-data';
import { getClipSourceDuration } from '@/tools/video-editor/lib/config-utils';
import type { TimelineClip } from '@/tools/video-editor/types/index';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Compute clip duration in seconds from meta.
 * Mirrors the hold-vs-speed logic in timeline-data.ts.
 */
function computeClipDuration(meta: ClipMeta): number {
  if (typeof meta.hold === 'number') {
    return meta.hold;
  }
  const from = meta.from ?? 0;
  const to = meta.to ?? 0;
  const speed = meta.speed ?? 1;
  return to > from ? (to - from) / speed : 0;
}

/**
 * Determine whether a clip is managed by a registered extension.
 *
 * In M3 a clip is "managed" when its `app` record carries an
 * extension namespace (e.g. `app?.managedBy`), or when a
 * `source_uuid` / `generation` provenance link exists.
 */
function deriveManaged(
  clip: TimelineClip,
  extensionIds: ReadonlySet<string>,
): { managed: boolean; managedBy?: string } {
  // Explicit managedBy key in clip app data.
  if (clip.app && typeof clip.app.managedBy === 'string' && clip.app.managedBy.length > 0) {
    return { managed: true, managedBy: clip.app.managedBy };
  }

  // If the clip has an app key that matches a known extension ID,
  // treat it as managed.
  if (clip.app) {
    for (const key of Object.keys(clip.app)) {
      if (extensionIds.has(key)) {
        return { managed: true, managedBy: key };
      }
    }
  }

  // source_uuid linking to an extension.
  if (clip.source_uuid && extensionIds.has(clip.source_uuid)) {
    return { managed: true, managedBy: clip.source_uuid };
  }

  return { managed: false };
}

/**
 * Well-known key under which GeneratedObjectMeta is stored
 * in clip / track / asset app data.
 */
const GENERATED_META_KEY = '__generated__';

/**
 * Extract GeneratedObjectMeta from an object's app record if present.
 * The app record may carry arbitrary extension data; we only extract
 * the well-known `__generated__` key.
 */
function extractGeneratedMeta(
  app: Record<string, unknown> | undefined,
): GeneratedObjectMeta | undefined {
  if (!app) return undefined;
  const raw = app[GENERATED_META_KEY];
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined;
  const g = raw as Record<string, unknown>;
  if (typeof g.extensionId !== 'string') return undefined;
  const meta: GeneratedObjectMeta = {
    extensionId: g.extensionId,
  };
  if (typeof g.contributionId === 'string') meta.contributionId = g.contributionId;
  if (g.provenance !== undefined && typeof g.provenance === 'object' && !Array.isArray(g.provenance)) {
    meta.provenance = g.provenance as Record<string, unknown>;
  }
  if (typeof g.generatedAt === 'number') meta.generatedAt = g.generatedAt;
  if (typeof g.sourceMapEntryId === 'string') meta.sourceMapEntryId = g.sourceMapEntryId;
  return meta;
}

// ---------------------------------------------------------------------------
// createTimelineReader
// ---------------------------------------------------------------------------

export interface TimelineReaderOptions {
  /**
   * The current timeline data to project.
   * Can be a static snapshot or a getter that returns the latest state.
   */
  data: TimelineData | (() => TimelineData);

  /**
   * Project identifier, when available from the host / provider.
   */
  projectId?: string | null;

  /**
   * Extension requirements for this project.
   * Extracted from project metadata (e.g. TimelineConfig.app or a
   * project-level manifest).
   */
  extensionRequirements?: readonly ProjectExtensionRequirement[];
}

/**
 * Create a TimelineReader from TimelineData and optional project metadata.
 *
 * The reader hides raw row/meta/registry internals and only exposes
 * stable TimelineSnapshot projections suitable for extension and
 * proposal code.
 */
export function createTimelineReader(
  options: TimelineReaderOptions,
): TimelineReader {
  const getData: () => TimelineData =
    typeof options.data === 'function' ? options.data : () => options.data;

  const projectId = options.projectId ?? null;
  const extensionRequirements: readonly ProjectExtensionRequirement[] =
    options.extensionRequirements ?? [];

  // Pre-compute the set of known extension IDs for managed-by detection.
  const knownExtensionIds: ReadonlySet<string> = new Set(
    extensionRequirements.map((r) => r.extensionId),
  );

  return {
    snapshot(): TimelineSnapshot {
      const data = getData();
      const { config, configVersion, registry, meta: metaMap } = data;

      // ── Clips ──────────────────────────────────────────────────────
      const clipSummaries: TimelineClipSummary[] = [];

      for (const clip of config.clips) {
        const clipMeta = metaMap[clip.id];
        if (!clipMeta) continue;

        const { managed, managedBy } = deriveManaged(clip, knownExtensionIds);

        const generatedMeta: GeneratedObjectMeta | undefined =
          extractGeneratedMeta(clip.app);

        clipSummaries.push({
          id: clip.id,
          track: clip.track,
          at: clip.at,
          clipType: clip.clipType,
          duration: computeClipDuration(clipMeta),
          managed,
          ...(managedBy !== undefined ? { managedBy } : {}),
          ...(generatedMeta !== undefined ? { generatedMeta } : {}),
        });
      }

      // ── Tracks ─────────────────────────────────────────────────────
      const trackSummaries: TimelineTrackSummary[] = (config.tracks ?? []).map(
        (track) => {
          const trackGeneratedMeta: GeneratedObjectMeta | undefined =
            extractGeneratedMeta(track.app);
          return {
            id: track.id,
            kind: track.kind,
            label: track.label,
            muted: track.muted ?? false,
            ...(track.app !== undefined ? { app: track.app } : {}),
            ...(trackGeneratedMeta !== undefined ? { generatedMeta: trackGeneratedMeta } : {}),
          };
        },
      );

      // ── Asset keys ─────────────────────────────────────────────────
      const assetKeys: string[] = Object.keys(registry.assets ?? {});

      // ── App data ───────────────────────────────────────────────────
      const app: Record<string, unknown> = config.app !== undefined
        ? { ...config.app }
        : {};

      // ── Source-map entries ─────────────────────────────────────────
      const sourceMapEntries: SourceMapEntry[] = [];
      for (const [, extData] of Object.entries(app)) {
        if (!extData || typeof extData !== 'object' || Array.isArray(extData)) continue;
        const extObj = extData as Record<string, unknown>;
        for (const [key, value] of Object.entries(extObj)) {
          if (!key.startsWith('__sm__:') || !value || typeof value !== 'object') continue;
          const entry = value as Record<string, unknown>;
          if (typeof entry.id !== 'string' || typeof entry.source !== 'string') continue;
          sourceMapEntries.push({
            id: entry.id as string,
            source: entry.source as string,
            targetId: entry.targetId as string,
            targetGranularity: entry.targetGranularity as SourceMapEntry['targetGranularity'],
            sourceUri: entry.sourceUri as string,
            sourceStartLine: typeof entry.sourceStartLine === 'number' ? entry.sourceStartLine : 0,
            sourceStartColumn: typeof entry.sourceStartColumn === 'number' ? entry.sourceStartColumn : 0,
            sourceEndLine: typeof entry.sourceEndLine === 'number' ? entry.sourceEndLine : 0,
            sourceEndColumn: typeof entry.sourceEndColumn === 'number' ? entry.sourceEndColumn : 0,
            stale: entry.stale === true,
            ...(entry.meta !== undefined && typeof entry.meta === 'object' ? { meta: entry.meta as Record<string, unknown> } : {}),
          });
        }
      }

      return {
        projectId,
        baseVersion: configVersion,
        currentVersion: configVersion,
        extensionRequirements,
        clips: clipSummaries,
        tracks: trackSummaries,
        assetKeys,
        app,
        sourceMapEntries,
      };
    },
  };
}
